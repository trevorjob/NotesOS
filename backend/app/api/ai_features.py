"""
NotesOS API - AI Features Router
Fact Checker, Pre-class Research, Study Agent, and Test Generator endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.resource import Resource, FactCheck, PreClassResearch
from app.models.course import Topic
from app.models.progress import AIConversation, AIMessage
from app.models.test import Test, TestQuestion, TestAttempt, TestAnswer
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
    )

    return AskQuestionResponse(**result)


@router.get("/study/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's study conversations."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    query = (
        select(AIConversation)
        .where(
            AIConversation.user_id == current_user.id,
            AIConversation.course_id == uuid.UUID(course_id),
        )
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
    score: float
    feedback: str
    encouragement: str
    key_points_covered: List[str]
    key_points_missed: List[str]


class VoiceAnswerResponse(BaseModel):
    answer_id: str
    attempt_id: str | None = None  # For redirect to results; submit uses answer_id as attempt_id
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
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    test = await question_generator.generate_test(
        db=db,
        course_id=course_id,
        user_id=str(current_user.id),
        topic_ids=request.topic_ids,
        question_count=request.question_count,
        difficulty=request.difficulty,
        question_types=request.question_types,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
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


@router.post("/tests/{test_id}/submit", response_model=VoiceAnswerResponse)
async def submit_test_answers(
    test_id: str,
    answers: List[SubmitAnswerRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit test answers for grading.

    Workflow:
    1. Create TestAttempt
    2. Create TestAnswer records for each answer
    3. Enqueue grading jobs (async processing)
    4. Return immediately
    5. Frontend listens for WebSocket 'grading:complete' event
    """
    test_query = select(Test).where(Test.id == uuid.UUID(test_id))
    test_result = await db.execute(test_query)
    test = test_result.scalar_one_or_none()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )

    await verify_course_enrollment(db, current_user.id, test.course_id)

    # Create test attempt
    attempt = TestAttempt(
        test_id=test.id,
        user_id=current_user.id,
        max_score=test.question_count * 10,  # Assuming 10 points max per question
    )
    db.add(attempt)
    await db.flush()

    # Create TestAnswer records and enqueue grading jobs
    answer_ids = []
    for answer_req in answers:
        # Get question to verify it exists
        question_query = select(TestQuestion).where(
            TestQuestion.id == uuid.UUID(answer_req.question_id)
        )
        question_result = await db.execute(question_query)
        question = question_result.scalar_one_or_none()

        if not question:
            continue

        # Create TestAnswer record
        test_answer = TestAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text=answer_req.answer_text,
            # Score/feedback will be filled by grading worker
        )
        db.add(test_answer)
        await db.flush()  # Get the ID

        answer_ids.append(str(test_answer.id))

        # Enqueue grading job
        await redis_client.enqueue_job(
            "voice_grade",  # Reuse same queue (handles both text and voice)
            {
                "answer_id": str(test_answer.id),
                "is_voice": answer_req.is_voice,
            },
        )

    await db.commit()

    return VoiceAnswerResponse(
        answer_id=str(attempt.id),
        attempt_id=str(attempt.id),
        status="processing",
        message=f"Submitted {len(answer_ids)} answers. Grading in progress.",
    )


# ── Voice Answer Endpoints ────────────────────────────────────────────────────


@router.post("/tests/{test_id}/voice-answer", response_model=VoiceAnswerResponse)
async def upload_voice_answer(
    test_id: str,
    question_id: str,
    audio_file: UploadFile = File(...),
    attempt_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a voice answer for a test question.

    Workflow:
    1. Upload audio to Cloudinary
    2. Create TestAnswer record with audio URL
    3. Enqueue grading job (transcribe + grade)
    4. Return immediately (async grading)
    """
    if not settings.ENABLE_VOICE_GRADING:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice grading is currently disabled",
        )

    # Verify test exists
    test_query = select(Test).where(Test.id == uuid.UUID(test_id))
    test_result = await db.execute(test_query)
    test = test_result.scalar_one_or_none()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Test not found"
        )

    await verify_course_enrollment(db, current_user.id, test.course_id)

    # Verify question exists
    question_query = select(TestQuestion).where(
        TestQuestion.id == uuid.UUID(question_id)
    )
    question_result = await db.execute(question_query)
    question = question_result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )

    # Get or create test attempt
    if attempt_id:
        attempt_query = select(TestAttempt).where(
            TestAttempt.id == uuid.UUID(attempt_id)
        )
        attempt_result = await db.execute(attempt_query)
        attempt = attempt_result.scalar_one_or_none()
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
            )
    else:
        # Create new attempt
        attempt = TestAttempt(
            test_id=test.id,
            user_id=current_user.id,
            max_score=test.question_count * 10,
        )
        db.add(attempt)
        await db.flush()

    # Upload audio to Cloudinary
    audio_bytes = await audio_file.read()
    upload_result = await storage_service.upload_file(
        file=audio_bytes,
        folder=f"voice_answers/{str(current_user.id)}",
        resource_type="auto",  # Auto-detect audio type
    )

    # Create TestAnswer record
    answer = TestAnswer(
        attempt_id=attempt.id,
        question_id=question.id,
        answer_audio_url=upload_result["url"],
        # Score/feedback will be filled by grading worker
    )
    db.add(answer)
    await db.commit()

    # Enqueue grading job
    await redis_client.enqueue_job(
        "voice_grade",
        {
            "answer_id": str(answer.id),
            "is_voice": True,
        },
    )

    return VoiceAnswerResponse(
        answer_id=str(answer.id),
        attempt_id=str(attempt.id),
        status="processing",
        message="Voice answer uploaded. Grading in progress.",
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

    # Get all answers
    answers_query = select(TestAnswer).where(TestAnswer.attempt_id == attempt.id)
    answers_result = await db.execute(answers_query)
    answers = answers_result.scalars().all()

    # Build response
    graded_answers = []
    for ans in answers:
        if ans.score is not None:  # Only include graded answers
            graded_answers.append(
                GradedAnswerResponse(
                    score=float(ans.score),
                    feedback=ans.ai_feedback or "",
                    encouragement=ans.encouragement or "",
                    key_points_covered=[],  # Not stored separately
                    key_points_missed=[],
                )
            )

    return TestResultsResponse(
        attempt_id=str(attempt.id),
        total_score=float(attempt.total_score or 0),
        max_score=attempt.max_score,
        completed_at=attempt.completed_at.isoformat() if attempt.completed_at else None,
        answers=graded_answers,
    )
