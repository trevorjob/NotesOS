"""
NotesOS API - Knowledge & Audio Endpoints
Consolidated topic knowledge and generated audio lessons.
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.course import CourseEnrollment, Topic
from app.models.knowledge import AudioLesson, KnowledgeStatus, TopicKnowledge
from app.models.user import User
from app.models.consume import ConsumeKind
from app.services.redis_client import redis_client
from app.services.retrieval.recognition import record_consume
from app.services.synthesis_debounce import schedule_synthesis

router = APIRouter()


# =============================================================================
# Helpers
# =============================================================================


async def _get_topic_or_404(topic_id: str, db: AsyncSession) -> Topic:
    result = await db.execute(
        select(Topic).where(Topic.id == uuid.UUID(topic_id))
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


async def _assert_enrolled(
    db: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID
):
    result = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this course",
        )


def _knowledge_response(k: TopicKnowledge) -> Dict[str, Any]:
    return {
        "id": str(k.id),
        "topic_id": str(k.topic_id),
        "status": k.status.value,
        "consolidated_note": k.consolidated_note,
        "key_points": k.key_points or [],
        "concepts": k.concepts or [],
        "source_count": k.source_count,
        "error_message": k.error_message,
        "generated_at": k.generated_at.isoformat() if k.generated_at else None,
        "updated_at": k.updated_at.isoformat(),
    }


def _audio_response(a: AudioLesson) -> Dict[str, Any]:
    return {
        "id": str(a.id),
        "topic_id": str(a.topic_id),
        "knowledge_id": str(a.knowledge_id),
        "status": a.status.value,
        "audio_url": a.audio_url,
        "duration_seconds": a.duration_seconds,
        "voice": a.voice,
        "error_message": a.error_message,
        "generated_at": a.generated_at.isoformat() if a.generated_at else None,
        "updated_at": a.updated_at.isoformat(),
    }


# =============================================================================
# Knowledge endpoints
# =============================================================================


@router.get("/topics/{topic_id}/knowledge")
async def get_topic_knowledge(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the consolidated knowledge for a topic.
    Returns the current status and content (may be pending/processing if not yet ready).
    """
    topic = await _get_topic_or_404(topic_id, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    result = await db.execute(
        select(TopicKnowledge).where(TopicKnowledge.topic_id == uuid.UUID(topic_id))
    )
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        # Return a "not yet generated" stub
        return {
            "id": None,
            "topic_id": topic_id,
            "status": "pending",
            "consolidated_note": None,
            "key_points": [],
            "concepts": [],
            "source_count": 0,
            "error_message": None,
            "generated_at": None,
            "updated_at": None,
        }

    response = _knowledge_response(knowledge)
    # Passive consume (§11): reading a ready note recognizes its contributors (best-effort).
    await record_consume(
        db, actor_id=current_user.id, topic_id=topic.id, kind=ConsumeKind.NOTE_VIEW
    )
    return response


@router.post("/topics/{topic_id}/knowledge/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_topic_knowledge(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger knowledge re-synthesis for a topic.
    Forces a full rebuild (re-merges every resource) and returns 202 Accepted.
    """
    topic = await _get_topic_or_404(topic_id, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    await schedule_synthesis(topic_id, str(topic.course_id), force_full=True)

    return {"message": "Knowledge synthesis queued"}


# =============================================================================
# Audio endpoints
# =============================================================================


@router.get("/topics/{topic_id}/audio")
async def get_topic_audio(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the latest audio lesson for a topic.
    Returns the most recently completed or in-progress lesson.
    """
    topic = await _get_topic_or_404(topic_id, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    # Return the latest audio lesson (most recently created)
    result = await db.execute(
        select(AudioLesson)
        .where(AudioLesson.topic_id == uuid.UUID(topic_id))
        .order_by(AudioLesson.created_at.desc())
        .limit(1)
    )
    lesson = result.scalar_one_or_none()

    if not lesson:
        return {
            "id": None,
            "topic_id": topic_id,
            "knowledge_id": None,
            "status": "pending",
            "audio_url": None,
            "duration_seconds": None,
            "voice": "nova",
            "error_message": None,
            "generated_at": None,
            "updated_at": None,
        }

    response = _audio_response(lesson)
    # Passive consume (§11): fetching a ready lesson is the server-side listen signal.
    if lesson.audio_url:
        await record_consume(
            db, actor_id=current_user.id, topic_id=topic.id, kind=ConsumeKind.AUDIO_LISTEN
        )
    return response


@router.post("/topics/{topic_id}/audio/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_topic_audio(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger audio re-generation for a topic.
    Requires knowledge to be in completed state first.
    Enqueues an audio job and returns 202 Accepted.
    """
    topic = await _get_topic_or_404(topic_id, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    # Verify knowledge exists and is completed
    result = await db.execute(
        select(TopicKnowledge).where(TopicKnowledge.topic_id == uuid.UUID(topic_id))
    )
    knowledge = result.scalar_one_or_none()

    if not knowledge or knowledge.status != KnowledgeStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Topic knowledge must be synthesized before generating audio. "
                   "Try regenerating knowledge first.",
        )

    job_id = await redis_client.enqueue_job(
        "audio",
        {
            "knowledge_id": str(knowledge.id),
            "topic_id": topic_id,
            "course_id": str(topic.course_id),
        },
    )

    return {"message": "Audio generation queued", "job_id": job_id}
