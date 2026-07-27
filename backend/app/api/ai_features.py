"""
NotesOS API - AI Features Router
Fact Checker, Pre-class Research, and Study Agent endpoints.
"""

from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
import json

from app.database import get_db
from app.models.resource import Resource, FactCheck, PreClassResearch
from app.models.course import Course, Topic
from app.models.progress import AIConversation, AIMessage
from app.api.auth import get_current_user, verify_course_enrollment
from app.models.user import User
from app.services.research_generator import research_generator
from app.services.redis_client import redis_client
from app.services.study_agent import study_agent
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


@router.post("/study/ask/stream")
async def ask_study_question_stream(
    request: AskQuestionRequest,
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask a study question, streaming the answer token-by-token over SSE.

    Emits ``data: {json}`` events: a ``meta`` frame (conversation_id + sources)
    first, then ``token`` frames, then a final ``done`` frame. The full answer is
    persisted server-side exactly as the blocking endpoint does.
    """
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    async def event_source():
        async for event in study_agent.ask_question_stream(
            db=db,
            user_id=str(current_user.id),
            course_id=course_id,
            question=request.question,
            topic_id=request.topic_id,
            conversation_id=request.conversation_id,
            personality=current_user.study_personality,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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

