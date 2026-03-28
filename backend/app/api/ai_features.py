"""
NotesOS API - AI Features Router
Fact Checker, Pre-class Research, Study Agent, and Test Generator endpoints.
"""

from typing import List, Optional
from datetime import datetime, date, timedelta
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    Request,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
import uuid
import json

from app.database import get_db
from app.models.resource import Resource, FactCheck, PreClassResearch
from app.models.course import Course, Topic
from app.models.progress import AIConversation, AIMessage
from app.models.test import Test, TestQuestion, TestAttempt, TestAnswer, QuestionType, AnswerStatus
from app.api.auth import get_current_user, verify_course_enrollment
from app.models.user import User
from app.services.research_generator import research_generator
from app.services.redis_client import redis_client
from app.services.study_agent import study_agent
from app.services.question_generator import question_generator
from app.services.storage import storage_service
from app.config import settings


router = APIRouter(prefix="/api", tags=["AI Features"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class FactCheckResponse(BaseModel):
    id: str
    claim_text: str
    verification_status: str
    confidence_score: float
    ai_explanation: str
    sources: List[dict]
    created_at: str

    class Config:
        from_attributes = True


class PreClassResearchResponse(BaseModel):
    id: str
    topic_id: str
    research_content: str
    sources: List[dict]
    key_concepts: dict
    generated_at: str

    class Config:
        from_attributes = True


# ── Fact Checking Endpoints ──────────────────────────────────────────────────


@router.post(
    "/resources/{resource_id}/fact-check", status_code=status.HTTP_202_ACCEPTED
)
async def trigger_fact_check(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enqueue async fact-checking job for a resource.

    Returns immediately with job ID. User will receive WebSocket notification
    when fact-checking is complete.
    """
    if not settings.ENABLE_FACT_CHECK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fact checking is currently disabled",
        )

    # Verify resource exists and user has access
    resource_query = select(Resource).where(Resource.id == uuid.UUID(resource_id))
    result = await db.execute(resource_query)
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    # Verify enrollment via topic
    topic_query = select(Topic).where(Topic.id == resource.topic_id)
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if topic:
        await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Check if resource has enough content
    if not resource.content or len(resource.content) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resource content is too short for fact-checking",
        )

    # Enqueue fact-check job
    await redis_client.enqueue_job("fact_check", {"resource_id": resource_id})

    return {
        "message": "Fact check job enqueued",
        "resource_id": resource_id,
        "status": "processing",
    }


@router.get(
    "/resources/{resource_id}/fact-checks", response_model=List[FactCheckResponse]
)
async def get_fact_checks(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all fact-check results for a resource."""
    # Verify resource exists and user has access
    resource_query = select(Resource).where(Resource.id == uuid.UUID(resource_id))
    result = await db.execute(resource_query)
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    # Verify enrollment
    topic_query = select(Topic).where(Topic.id == resource.topic_id)
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if topic:
        await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Fetch fact checks
    fact_checks_query = (
        select(FactCheck)
        .where(FactCheck.resource_id == uuid.UUID(resource_id))
        .order_by(FactCheck.created_at.desc())
    )
    fc_result = await db.execute(fact_checks_query)
    fact_checks = fc_result.scalars().all()

    return [
        FactCheckResponse(
            id=str(fc.id),
            claim_text=fc.claim_text,
            verification_status=fc.verification_status.value,
            confidence_score=float(fc.confidence_score) if fc.confidence_score else 0.0,
            ai_explanation=fc.ai_explanation or "",
            sources=fc.sources or [],
            created_at=fc.created_at.isoformat(),
        )
        for fc in fact_checks
    ]


# ── Pre-class Research Endpoints ──────────────────────────────────────────────


@router.post("/topics/{topic_id}/research", response_model=PreClassResearchResponse)
async def generate_topic_research(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate AI-powered pre-class research for a topic.

    Searches web for relevant content and synthesizes it into structured research.
    """
    if not settings.ENABLE_PRE_CLASS_RESEARCH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pre-class research is currently disabled",
        )

    # Verify topic exists and user has access
    topic_query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(topic_query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Check if research already exists for this topic
    existing_query = (
        select(PreClassResearch)
        .where(PreClassResearch.topic_id == uuid.UUID(topic_id))
        .order_by(PreClassResearch.generated_at.desc())
    )
    existing_result = await db.execute(existing_query)
    existing_research = existing_result.scalar_one_or_none()

    if existing_research:
        # Return existing research
        return PreClassResearchResponse(
            id=str(existing_research.id),
            topic_id=str(existing_research.topic_id),
            research_content=existing_research.research_content,
            sources=existing_research.sources or [],
            key_concepts=existing_research.key_concepts or {},
            generated_at=existing_research.generated_at.isoformat(),
        )

    # Generate new research
    research = await research_generator.generate_research(db, topic)
    await db.commit()

    return PreClassResearchResponse(
        id=str(research.id),
        topic_id=str(research.topic_id),
        research_content=research.research_content,
        sources=research.sources or [],
        key_concepts=research.key_concepts or {},
        generated_at=research.generated_at.isoformat(),
    )


@router.get("/topics/{topic_id}/research", response_model=PreClassResearchResponse)
async def get_topic_research(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get existing pre-class research for a topic."""
    # Verify topic exists and user has access
    topic_query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(topic_query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Fetch research
    research_query = (
        select(PreClassResearch)
        .where(PreClassResearch.topic_id == uuid.UUID(topic_id))
        .order_by(PreClassResearch.generated_at.desc())
    )
    research_result = await db.execute(research_query)
    research = research_result.scalar_one_or_none()

    if not research:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No research found for this topic",
        )

    return PreClassResearchResponse(
        id=str(research.id),
        topic_id=str(research.topic_id),
        research_content=research.research_content,
        sources=research.sources or [],
        key_concepts=research.key_concepts or {},
        generated_at=research.generated_at.isoformat(),
    )


# ── Study Agent Endpoints ─────────────────────────────────────────────────────


class AskQuestionRequest(BaseModel):
    question: str
    topic_id: str | None = None
    conversation_id: str | None = None


class AskQuestionResponse(BaseModel):
    answer: str
    sources: List[dict]
    conversation_id: str


class ConversationResponse(BaseModel):
    id: str
    title: str | None
    created_at: str


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: str


@router.post("/study/ask", response_model=AskQuestionResponse)
async def ask_study_question(
    request: AskQuestionRequest,
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask a study question using RAG + AI."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    result = await study_agent.ask_question(
        db=db,
        user_id=str(current_user.id),
        course_id=course_id,
        question=request.question,
        topic_id=request.topic_id,
        conversation_id=request.conversation_id,
        personality=current_user.study_personality,
    )

    return AskQuestionResponse(**result)


@router.get("/study/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    course_id: str,
    topic_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's study conversations, optionally filtered by topic."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    filters = [
        AIConversation.user_id == current_user.id,
        AIConversation.course_id == uuid.UUID(course_id),
    ]
    if topic_id:
        filters.append(AIConversation.topic_id == uuid.UUID(topic_id))

    query = (
        select(AIConversation)
        .where(*filters)
        .order_by(AIConversation.updated_at.desc())
    )
    result = await db.execute(query)
    conversations = result.scalars().all()

    return [
        ConversationResponse(
            id=str(conv.id),
            title=conv.title,
            created_at=conv.created_at.isoformat(),
        )
        for conv in conversations
    ]


@router.delete("/study/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a conversation and all its messages."""
    conv_result = await db.execute(
        select(AIConversation).where(AIConversation.id == uuid.UUID(conversation_id))
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")
    await db.delete(conv)
    await db.commit()
    return None


@router.get(
    "/study/conversations/{conversation_id}", response_model=List[MessageResponse]
)
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get messages from a conversation."""
    query = (
        select(AIMessage)
        .where(AIMessage.conversation_id == uuid.UUID(conversation_id))
        .order_by(AIMessage.created_at.asc())
    )
    result = await db.execute(query)
    messages = result.scalars().all()

    return [
        MessageResponse(
            role=msg.role.value,
            content=msg.content,
            created_at=msg.created_at.isoformat(),
        )
        for msg in messages
    ]


# ── Test/Question Generator Endpoints ─────────────────────────────────────────


class GenerateTestRequest(BaseModel):
    topic_ids: List[str]
    question_count: int = 10
    difficulty: str = "medium"
    question_types: List[str] = ["mcq", "short_answer"]


class TestQuestionResponse(BaseModel):
    id: str
    question_text: str
    question_type: str
    answer_options: List[str] | None
    points: int
    order_index: int


class TestResponse(BaseModel):
    id: str
    title: str
    question_count: int
    questions: List[TestQuestionResponse]


class TestListItem(BaseModel):
    id: str
    title: str
    question_count: int
    created_at: str


class TestAttemptListItem(BaseModel):
    id: str
    started_at: str
    completed_at: str | None
    total_score: float | None
    max_score: int


class SubmitAnswerRequest(BaseModel):
    question_id: str
    answer_text: str
    is_voice: bool = False


class GradedAnswerResponse(BaseModel):
    question_id: str
    question_text: str
    user_answer: str
    score: float
    feedback: str
    encouragement: str
    key_points_covered: List[str]
    key_points_missed: List[str]


class VoiceAnswerResponse(BaseModel):
    answer_id: str
    attempt_id: str | None = (
        None  # For redirect to results; submit uses answer_id as attempt_id
    )
    status: str
    message: str


class TestResultsResponse(BaseModel):
    attempt_id: str
    total_score: float
    max_score: int
    completed_at: str | None
    answers: List[GradedAnswerResponse]


@router.post("/tests/generate", response_model=TestResponse)
async def generate_test(
    request: GenerateTestRequest,
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a practice test."""
    course_uuid = uuid.UUID(course_id)
    await verify_course_enrollment(db, current_user.id, course_uuid)

    # Build a descriptive title: "CS301: Topic A, Topic B — Hard"
    course_result = await db.execute(select(Course).where(Course.id == course_uuid))
    course = course_result.scalar_one_or_none()
    course_code = course.code if course else ""

    if request.topic_ids:
        topics_result = await db.execute(
            select(Topic).where(Topic.id.in_([uuid.UUID(t) for t in request.topic_ids]))
        )
        topics = topics_result.scalars().all()
        topic_names = ", ".join(t.title for t in topics[:3])
        if len(topics) > 3:
            topic_names += f" +{len(topics) - 3} more"
    else:
        topic_names = "All Topics"

    difficulty_label = request.difficulty.capitalize()
    title = f"{course_code}: {topic_names} — {difficulty_label}" if course_code else f"{topic_names} — {difficulty_label}"

    test = await question_generator.generate_test(
        db=db,
        course_id=course_id,
        user_id=str(current_user.id),
        topic_ids=request.topic_ids,
        question_count=request.question_count,
        difficulty=request.difficulty,
        question_types=request.question_types,
        title=title,
        topic_name=topic_names,
    )

    # Refresh to get questions
    await db.refresh(test)
    questions_query = (
        select(TestQuestion)
        .where(TestQuestion.test_id == test.id)
        .order_by(TestQuestion.order_index)
    )
    questions_result = await db.execute(questions_query)
    questions = questions_result.scalars().all()

    return TestResponse(
        id=str(test.id),
        title=test.title,
        question_count=test.question_count,
        questions=[
            TestQuestionResponse(
                id=str(q.id),
                question_text=q.question_text,
                question_type=q.question_type.value,
                answer_options=q.answer_options,
                points=q.points,
                order_index=q.order_index,
            )
            for q in questions
        ],
    )


@router.get("/tests", response_model=List[TestListItem])
async def list_tests(
    course_id: str = Query(..., description="Course ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tests generated for this course (user must be enrolled)."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))
    query = (
        select(Test)
        .where(Test.course_id == uuid.UUID(course_id))
        .order_by(Test.created_at.desc())
    )
    result = await db.execute(query)
    tests = result.scalars().all()
    return [
        TestListItem(
            id=str(t.id),
            title=t.title,
            question_count=t.question_count,
            created_at=t.created_at.isoformat() if t.created_at else "",
        )
        for t in tests
    ]


# ── Recent Attempts Endpoint ──────────────────────────────────────────────────
# IMPORTANT: Must be defined BEFORE /tests/{test_id} to avoid route shadowing.


@router.get("/tests/attempts/recent")
async def get_recent_attempts(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the user's most recent completed test attempts across all courses."""
    result = await db.execute(
        select(TestAttempt, Test)
        .join(Test, Test.id == TestAttempt.test_id)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.completed_at.isnot(None),
        )
        .order_by(TestAttempt.completed_at.desc())
        .limit(limit)
    )
    rows = result.all()

    return {
        "attempts": [
            {
                "attempt_id": str(attempt.id),
                "test_id": str(test.id),
                "title": test.title,
                "total_score": float(attempt.total_score or 0),
                "max_score": attempt.max_score,
                "score_pct": round(float(attempt.total_score or 0) / max(attempt.max_score, 1) * 100, 1),
                "completed_at": attempt.completed_at.isoformat(),
            }
            for attempt, test in rows
        ]
    }


# ── Test Stats Endpoint ───────────────────────────────────────────────────────
# IMPORTANT: Must be defined BEFORE /tests/{test_id} to avoid route shadowing.


@router.get("/tests/stats")
async def get_test_stats(
    course_id: str = Query(..., description="Course ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregate test statistics for the current user in a course.
    Returns average score, tests completed, and study streak (consecutive days with tests).
    """
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    attempts_result = await db.execute(
        select(TestAttempt)
        .join(Test, Test.id == TestAttempt.test_id)
        .where(
            TestAttempt.user_id == current_user.id,
            Test.course_id == uuid.UUID(course_id),
            TestAttempt.completed_at.isnot(None),
        )
        .order_by(TestAttempt.completed_at.desc())
    )
    attempts = attempts_result.scalars().all()

    tests_completed = len(attempts)
    average_score = 0.0
    if tests_completed > 0:
        total = sum(
            float(a.total_score or 0) / max(a.max_score, 1) * 100
            for a in attempts
        )
        average_score = round(total / tests_completed, 1)

    # Study streak: consecutive days (most recent first) with at least one attempt
    streak = 0
    if attempts:
        today = datetime.utcnow().date()
        distinct_days = sorted(
            {a.completed_at.date() for a in attempts if a.completed_at},
            reverse=True,
        )
        expected = today
        for d in distinct_days:
            if d == expected or d == expected - timedelta(days=1):
                streak += 1
                expected = d - timedelta(days=1)
            elif d < expected - timedelta(days=1):
                break

    return {
        "average_score": average_score,
        "tests_completed": tests_completed,
        "study_streak": streak,
    }


@router.get("/tests/{test_id}", response_model=TestResponse)
async def get_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a test with its questions."""
    test_query = select(Test).where(Test.id == uuid.UUID(test_id))
    test_result = await db.execute(test_query)
    test = test_result.scalar_one_or_none()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )

    await verify_course_enrollment(db, current_user.id, test.course_id)

    questions_query = (
        select(TestQuestion)
        .where(TestQuestion.test_id == test.id)
        .order_by(TestQuestion.order_index)
    )
    questions_result = await db.execute(questions_query)
    questions = questions_result.scalars().all()

    return TestResponse(
        id=str(test.id),
        title=test.title,
        question_count=test.question_count,
        questions=[
            TestQuestionResponse(
                id=str(q.id),
                question_text=q.question_text,
                question_type=q.question_type.value,
                answer_options=q.answer_options,
                points=q.points,
                order_index=q.order_index,
            )
            for q in questions
        ],
    )


@router.get("/tests/{test_id}/attempts", response_model=List[TestAttemptListItem])
async def list_test_attempts(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's attempts for this test."""
    test_query = select(Test).where(Test.id == uuid.UUID(test_id))
    test_result = await db.execute(test_query)
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )
    await verify_course_enrollment(db, current_user.id, test.course_id)

    attempt_query = (
        select(TestAttempt)
        .where(TestAttempt.test_id == test.id, TestAttempt.user_id == current_user.id)
        .order_by(TestAttempt.started_at.desc())
    )
    attempt_result = await db.execute(attempt_query)
    attempts = attempt_result.scalars().all()
    return [
        TestAttemptListItem(
            id=str(a.id),
            started_at=a.started_at.isoformat() if a.started_at else "",
            completed_at=a.completed_at.isoformat() if a.completed_at else None,
            total_score=float(a.total_score) if a.total_score is not None else None,
            max_score=a.max_score,
        )
        for a in attempts
    ]


@router.post("/tests/{test_id}/submit-full", response_model=VoiceAnswerResponse)
async def submit_test_full(
    request: Request,
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit all answers in a single multipart request.

    Form fields:
      answers  (required) — JSON: [{question_id, answer_text, is_voice}]
      voice_<question_id> (optional) — audio file for voice answers

    Workflow:
      1. Parse form data: JSON answers + any voice_<question_id> file fields
      2. Create one TestAttempt
      3. For each answer: create TestAnswer, upload voice if present, enqueue grading job
      4. Single commit, return attempt_id
      5. Frontend listens for WebSocket 'grading:complete'
    """
    # Read raw multipart form (supports dynamic file field names)
    form = await request.form()

    answers_raw = form.get("answers")
    if not answers_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'answers' field is required",
        )

    # Parse answers JSON
    try:
        answers_data = json.loads(str(answers_raw))
        if not isinstance(answers_data, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'answers' must be a JSON array",
        )

    # Collect any voice files keyed as voice_<question_id>
    voice_files: dict = {
        key[6:]: value  # strip "voice_" prefix → question_id
        for key, value in form.multi_items()
        if key.startswith("voice_")
    }

    # Verify test
    test_query = select(Test).where(Test.id == uuid.UUID(test_id))
    test_result = await db.execute(test_query)
    test = test_result.scalar_one_or_none()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )

    await verify_course_enrollment(db, current_user.id, test.course_id)

    # Create test attempt — max_score based on actual questions submitted
    actual_question_count = len([a for a in answers_data if a.get("question_id")])
    attempt = TestAttempt(
        test_id=test.id,
        user_id=current_user.id,
        max_score=actual_question_count * 10,
    )
    db.add(attempt)
    await db.flush()

    answer_count = 0
    queued_for_ai = 0

    for item in answers_data:
        q_id = item.get("question_id")
        answer_text = item.get("answer_text", "")
        is_voice = bool(item.get("is_voice", False))

        if not q_id:
            continue

        question_result = await db.execute(
            select(TestQuestion).where(TestQuestion.id == uuid.UUID(q_id))
        )
        question = question_result.scalar_one_or_none()
        if not question:
            continue

        audio_url: str | None = None

        # Upload voice file if present and voice grading is enabled
        if is_voice and settings.ENABLE_VOICE_GRADING:
            upload_file = voice_files.get(q_id)
            if upload_file is not None:
                audio_bytes = await upload_file.read()
                upload_result = await storage_service.upload_file(
                    file=audio_bytes,
                    folder=f"voice_answers/{current_user.id}",
                    resource_type="auto",
                )
                audio_url = upload_result["url"]

        test_answer = TestAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text=answer_text if not audio_url else None,
            answer_audio_url=audio_url,
        )

        # Auto-grade MCQ immediately — no AI needed, just compare to correct_answer
        if question.question_type == QuestionType.MCQ and not audio_url:
            correct_raw = (question.correct_answer or "").strip()
            given = answer_text.strip()

            # Resolve "Option X" labels to actual text (backward compat with old questions)
            import re as _re
            correct_text = correct_raw
            label_match = _re.match(r'^Option\s+([A-D])$', correct_raw, _re.IGNORECASE)
            if label_match and question.answer_options:
                idx = ord(label_match.group(1).upper()) - ord('A')
                if 0 <= idx < len(question.answer_options):
                    correct_text = question.answer_options[idx]

            is_correct = bool(correct_text and given.lower() == correct_text.lower())
            test_answer.score = 10.0 if is_correct else 0.0
            test_answer.ai_feedback = (
                "Correct!" if is_correct
                else f"The correct answer was: {correct_text}"
            )
            test_answer.status = AnswerStatus.CORRECT if is_correct else AnswerStatus.NEEDS_REVIEW
        else:
            queued_for_ai += 1

        db.add(test_answer)
        await db.flush()

        # Only enqueue AI grading for non-MCQ (or voice) answers
        if question.question_type != QuestionType.MCQ or audio_url:
            await redis_client.enqueue_job(
                "voice_grade",
                {
                    "answer_id": str(test_answer.id),
                    "is_voice": bool(audio_url),
                },
            )

        answer_count += 1

    # If all answers were auto-graded (pure MCQ test), finalize the attempt now
    if queued_for_ai == 0 and answer_count > 0:
        all_answers_q = select(TestAnswer).where(TestAnswer.attempt_id == attempt.id)
        all_answers_r = await db.execute(all_answers_q)
        all_answers = all_answers_r.scalars().all()
        attempt.total_score = sum(float(a.score or 0) for a in all_answers)
        attempt.completed_at = datetime.utcnow()

    await db.commit()

    # Broadcast grading:complete immediately for pure-MCQ tests
    if queued_for_ai == 0 and answer_count > 0:
        course_id_str = str(test.course_id)
        score_pct = round(float(attempt.total_score or 0) / max(attempt.max_score, 1) * 100)
        await redis_client.publish(
            channel="course_updates",
            message={
                "course_id": course_id_str,
                "message": {
                    "type": "grading:complete",
                    "data": {
                        "attempt_id": str(attempt.id),
                        "score_pct": score_pct,
                    },
                },
            },
        )

    status_msg = "Graded instantly." if queued_for_ai == 0 else "Grading in progress."
    return VoiceAnswerResponse(
        answer_id=str(attempt.id),
        attempt_id=str(attempt.id),
        status="processing" if queued_for_ai > 0 else "complete",
        message=f"Submitted {answer_count} answers. {status_msg}",
    )


@router.get("/tests/attempts/{attempt_id}/results", response_model=TestResultsResponse)
async def get_test_results(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get graded results for a test attempt."""
    # Fetch attempt with answers
    attempt_query = select(TestAttempt).where(TestAttempt.id == uuid.UUID(attempt_id))
    attempt_result = await db.execute(attempt_query)
    attempt = attempt_result.scalar_one_or_none()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
        )

    # Verify ownership
    if attempt.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this attempt",
        )

    # Get all answers with their questions
    from sqlalchemy.orm import joinedload
    answers_query = (
        select(TestAnswer)
        .options(joinedload(TestAnswer.question))
        .where(TestAnswer.attempt_id == attempt.id)
    )
    answers_result = await db.execute(answers_query)
    answers = answers_result.scalars().all()

    # Build response
    graded_answers = []
    for ans in answers:
        if ans.score is not None:
            graded_answers.append(
                GradedAnswerResponse(
                    question_id=str(ans.question_id),
                    question_text=ans.question.question_text if ans.question else "",
                    user_answer=ans.transcription or ans.answer_text or "",
                    score=float(ans.score),
                    feedback=ans.ai_feedback or "",
                    encouragement=ans.encouragement or "",
                    key_points_covered=ans.key_points_covered or [],
                    key_points_missed=ans.key_points_missed or [],
                )
            )

    # Self-healing: if all answers are scored but completed_at wasn't set (e.g. worker crash), fix it now
    if answers and not attempt.completed_at and all(ans.score is not None for ans in answers):
        attempt.total_score = sum(float(a.score or 0) for a in answers)
        attempt.completed_at = datetime.utcnow()
        await db.commit()

    return TestResultsResponse(
        attempt_id=str(attempt.id),
        total_score=float(attempt.total_score or 0),
        max_score=attempt.max_score,
        completed_at=attempt.completed_at.isoformat() if attempt.completed_at else None,
        answers=graded_answers,
    )


# ── Save Draft Endpoint ───────────────────────────────────────────────────────


class DraftAnswer(BaseModel):
    question_id: str
    answer_text: Optional[str] = None
    answer_audio_url: Optional[str] = None
    selected_option: Optional[str] = None


class SaveDraftRequest(BaseModel):
    answers: List[DraftAnswer]


@router.post("/tests/{test_id}/draft")
async def save_test_draft(
    test_id: str,
    request: SaveDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save draft answers for a test without submitting or triggering grading.
    Creates a new attempt (or reuses the latest unfinished one) and upserts answers.
    """
    test_query = select(Test).where(Test.id == uuid.UUID(test_id))
    test_result = await db.execute(test_query)
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found.")

    await verify_course_enrollment(db, current_user.id, test.course_id)

    # Find or create an unfinished attempt
    attempt_result = await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.test_id == test.id,
            TestAttempt.user_id == current_user.id,
            TestAttempt.completed_at.is_(None),
        )
        .order_by(TestAttempt.started_at.desc())
        .limit(1)
    )
    attempt = attempt_result.scalar_one_or_none()
    if not attempt:
        attempt = TestAttempt(
            test_id=test.id,
            user_id=current_user.id,
            max_score=test.question_count * 10,
        )
        db.add(attempt)
        await db.flush()

    # Validate all question IDs belong to this test
    question_ids = [uuid.UUID(a.question_id) for a in request.answers]
    valid_q_result = await db.execute(
        select(TestQuestion.id).where(
            TestQuestion.test_id == test.id,
            TestQuestion.id.in_(question_ids),
        )
    )
    valid_ids = {row[0] for row in valid_q_result}

    # Fetch existing answers for this attempt
    existing_result = await db.execute(
        select(TestAnswer).where(TestAnswer.attempt_id == attempt.id)
    )
    existing_answers = {ans.question_id: ans for ans in existing_result.scalars().all()}

    for draft in request.answers:
        q_uuid = uuid.UUID(draft.question_id)
        if q_uuid not in valid_ids:
            continue

        if q_uuid in existing_answers:
            ans = existing_answers[q_uuid]
        else:
            ans = TestAnswer(attempt_id=attempt.id, question_id=q_uuid)
            db.add(ans)

        if draft.answer_text is not None:
            ans.answer_text = draft.answer_text
        if draft.answer_audio_url is not None:
            ans.answer_audio_url = draft.answer_audio_url

    saved_at = datetime.utcnow()
    await db.commit()

    return {"saved_at": saved_at.isoformat()}
