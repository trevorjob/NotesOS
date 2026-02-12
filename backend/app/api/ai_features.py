"""
NotesOS API - AI Features Router
Fact Checker and Pre-class Research endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.resource import Resource, FactCheck, PreClassResearch
from app.models.course import Topic
from app.api.auth import get_current_user, verify_course_enrollment
from app.models.user import User
from app.services.research_generator import research_generator
from app.services.redis_client import redis_client
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
