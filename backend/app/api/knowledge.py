"""
NotesOS API - Knowledge & Audio Endpoints
Consolidated topic knowledge and generated audio lessons.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.course import CourseEnrollment, Topic
from app.models.knowledge import AudioLesson, KnowledgeStatus, TopicKnowledge
from app.models.resource import Resource
from app.models.retrieval import Concept, ConceptState
from app.models.user import User
from app.models.consume import ConsumeEvent, ConsumeKind
from app.services.redis_client import redis_client
from app.services.retrieval.recognition import record_consume
from app.services.retrieval.scheduler import (
    MASTERY_FADING,
    MASTERY_NEW,
    MASTERY_SHAKY,
    MASTERY_SOLID,
    derive_mastery,
)
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


@router.get("/topics/{topic_id}/concept-states")
async def get_topic_concept_states(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Per-concept mastery for the caller over a topic — the note's heat-map data.
    Concepts come from synthesis (shared); the mastery state is the caller's own
    FSRS ConceptState, so this is per-user and never cached (unlike the note itself).
    """
    topic = await _get_topic_or_404(topic_id, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    result = await db.execute(
        select(Concept, ConceptState)
        .outerjoin(
            ConceptState,
            and_(
                ConceptState.concept_id == Concept.id,
                ConceptState.user_id == current_user.id,
            ),
        )
        .where(Concept.topic_id == topic.id)
        .order_by(Concept.order_index)
    )

    now = datetime.utcnow()
    concepts: List[Dict[str, Any]] = []
    summary = {MASTERY_NEW: 0, MASTERY_SOLID: 0, MASTERY_FADING: 0, MASTERY_SHAKY: 0}
    for concept, state in result.all():
        if state is None:
            mastery, reps, lapses, due = MASTERY_NEW, 0, 0, None
        else:
            mastery = derive_mastery(
                reps=state.reps,
                last_grade=state.last_grade,
                fsrs_state=state.fsrs_state,
                due=state.due,
                now=now,
            )
            reps, lapses, due = state.reps, state.lapses, state.due
        summary[mastery] += 1
        concepts.append(
            {
                "concept_id": str(concept.id),
                "term": concept.text,
                "definition": concept.definition,
                "state": mastery,
                "due": due.isoformat() if due else None,
                "reps": reps,
                "lapses": lapses,
            }
        )

    return {"topic_id": str(topic.id), "concepts": concepts, "summary": summary}


# A note read records a NOTE_VIEW on every knowledge GET, so "new since you last read" must
# ignore the current open — exclude views inside this grace window as "this session".
_READ_GRACE_SECONDS = 15
_RECENT_LIMIT = 3


@router.get("/topics/{topic_id}/contributions")
async def get_topic_contributions(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The note's attribution layer (§4/§10): who built it, what was added recently, and how
    much is new since the caller last read it. Aggregated from the non-quarantined resources
    behind the note (quarantined ones aren't in the shared note). Per-user, so uncached.
    """
    topic = await _get_topic_or_404(topic_id, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    result = await db.execute(
        select(Resource, User.full_name)
        .join(User, User.id == Resource.uploaded_by)
        .where(Resource.topic_id == topic.id, Resource.quarantined.is_(False))
        .order_by(Resource.created_at.desc())
    )
    rows = result.all()

    contributors: List[Dict[str, str]] = []
    recent: List[Dict[str, Any]] = []
    seen: set = set()
    for resource, uploader_name in rows:
        if resource.uploaded_by not in seen:
            seen.add(resource.uploaded_by)
            contributors.append({"id": str(resource.uploaded_by), "name": uploader_name})
        if len(recent) < _RECENT_LIMIT:
            recent.append(
                {
                    "resource_id": str(resource.id),
                    "title": resource.title or resource.file_name or "Untitled",
                    "uploader_name": uploader_name,
                    "created_at": resource.created_at.isoformat(),
                }
            )

    # "new since you last read": resources added after the caller's previous NOTE_VIEW
    # (the grace window drops this session's own view). None if they've never read it before.
    grace_cutoff = datetime.utcnow() - timedelta(seconds=_READ_GRACE_SECONDS)
    last_read = (
        await db.execute(
            select(func.max(ConsumeEvent.created_at)).where(
                ConsumeEvent.actor_id == current_user.id,
                ConsumeEvent.topic_id == topic.id,
                ConsumeEvent.kind == ConsumeKind.NOTE_VIEW,
                ConsumeEvent.created_at < grace_cutoff,
            )
        )
    ).scalar_one_or_none()

    new_since_last_read: Optional[int] = None
    if last_read is not None:
        new_since_last_read = (
            await db.execute(
                select(func.count())
                .select_from(Resource)
                .where(
                    Resource.topic_id == topic.id,
                    Resource.quarantined.is_(False),
                    Resource.created_at > last_read,
                )
            )
        ).scalar_one()

    return {
        "topic_id": str(topic.id),
        "contributors": contributors,
        "contributor_count": len(contributors),
        "recent": recent,
        "new_since_last_read": new_since_last_read,
    }


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
