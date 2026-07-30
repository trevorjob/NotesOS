"""
NotesOS API - Knowledge & Audio Endpoints
Consolidated topic knowledge and generated audio lessons.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.course import CourseEnrollment, Topic
from app.models.knowledge import AudioArtifact, AudioLens, AudioScopeType, KnowledgeStatus, TopicKnowledge
from app.models.resource import Resource
from app.models.retrieval import Concept, ConceptState
from app.models.subject import SubjectFamily
from app.models.user import User
from app.models.consume import ConsumeEvent, ConsumeKind
from app.services.audio_credits import can_generate
from app.services.redis_client import redis_client
from app.services.retrieval.recognition import record_consume
from app.services.retrieval.remediation import weakest_concepts
from app.services.retrieval.scheduler import (
    MASTERY_FADING,
    MASTERY_NEW,
    MASTERY_SHAKY,
    MASTERY_SOLID,
    derive_mastery,
)
from app.services.retrieval.subject_profiles import is_audio_suitable
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


def _audio_response(a: AudioArtifact, *, audio_suitable: bool) -> Dict[str, Any]:
    return {
        "id": str(a.id),
        "scope_type": a.scope_type.value,
        "scope_ref": str(a.scope_ref),
        "knowledge_id": str(a.knowledge_id) if a.knowledge_id else None,
        "lens": a.lens.value,
        "owner_id": str(a.owner_id) if a.owner_id else None,
        "status": a.status.value,
        "audio_url": a.audio_url,
        "duration_seconds": a.duration_seconds,
        "voice": a.voice,
        "error_message": a.error_message,
        "stale": a.stale,
        "audio_suitable": audio_suitable,
        "generated_at": a.generated_at.isoformat() if a.generated_at else None,
        "updated_at": a.updated_at.isoformat(),
    }


def _audio_pending_stub(scope_type: str, scope_ref: str, lens: str, *, audio_suitable: bool) -> Dict[str, Any]:
    return {
        "id": None,
        "scope_type": scope_type,
        "scope_ref": scope_ref,
        "knowledge_id": None,
        "lens": lens,
        "owner_id": None,
        "status": "pending",
        "audio_url": None,
        "duration_seconds": None,
        "voice": "nova",
        "error_message": None,
        "stale": False,
        "audio_suitable": audio_suitable,
        "generated_at": None,
        "updated_at": None,
    }


async def _scope_subject_family(db: AsyncSession, scope_type_enum: AudioScopeType, scope_ref) -> SubjectFamily:
    """The family behind a scope (docs/listen-audio-plan.md §7) — concepts inherit
    their topic's family; course/concept_cluster scopes have no consumer yet."""
    if scope_type_enum == AudioScopeType.TOPIC:
        family = await db.scalar(select(Topic.subject_family).where(Topic.id == scope_ref))
    elif scope_type_enum == AudioScopeType.CONCEPT:
        family = await db.scalar(
            select(Topic.subject_family).join(Concept, Concept.topic_id == Topic.id).where(Concept.id == scope_ref)
        )
    else:
        family = None
    return family or SubjectFamily.GENERAL


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


@router.get("/topics/{topic_id}/weak-concepts")
async def get_topic_weak_concepts(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The caller's shakiest concepts within this topic (docs/listen-audio-plan.md §6) — the
    remediation-suggestion candidates, most-lapsed first. Surface-agnostic: whatever UI
    shows "you keep missing X, want a breakdown?" reads this list and, on accept, fires
    POST /audio/request with scope_type=concept, lens=remediation for the chosen concept.
    """
    topic = await _get_topic_or_404(topic_id, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    concepts = await weakest_concepts(db, user_id=current_user.id, topic_id=topic.id)

    return {
        "topic_id": str(topic.id),
        "concepts": [
            {"concept_id": str(c.id), "term": c.text, "definition": c.definition} for c in concepts
        ],
    }


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
#
# Generalized over (scope_type, scope_ref, lens, owner) per docs/listen-audio-plan.md.
# course/concept_cluster scopes still aren't wired to a generation path and are
# rejected with a 400 rather than silently no-op'd. The generic "explainer" lenses
# (default/exam_focused/slower) are further gated by a scope's audio_suitability
# (§7) — worked_example and the personal user_instruction/remediation lenses aren't.
# =============================================================================

_VALID_SCOPE_TYPES = {s.value for s in AudioScopeType}

# Lenses that are just angles on the same narrated note as the default explainer —
# gated by audio_suitability alongside it (docs/listen-audio-plan.md §7). worked_example
# (narrates solved-problem steps) and the personal user_instruction/remediation lenses
# (the caller explicitly asked for them) are never gated.
_GENERIC_EXPLAINER_LENSES = {AudioLens.EXAM_FOCUSED, AudioLens.SLOWER}


@router.get("/audio/{scope_type}/{scope_ref}")
async def get_audio_artifact(
    scope_type: str,
    scope_ref: str,
    lens: str = "default",
    owner: str = "global",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Latest audio artifact for a scope + lens (``owner=global`` for the shared
    default, ``owner=me`` for the caller's own personal/lens requests).
    Returns a "pending" stub if nothing has been generated yet.
    """
    if scope_type not in _VALID_SCOPE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown scope_type '{scope_type}'")
    try:
        lens_enum = AudioLens(lens)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown lens '{lens}'")
    if owner not in ("global", "me"):
        raise HTTPException(status_code=400, detail="owner must be 'global' or 'me'")

    scope_ref_uuid = uuid.UUID(scope_ref)
    scope_type_enum = AudioScopeType(scope_type)

    if scope_type_enum == AudioScopeType.TOPIC:
        topic = await _get_topic_or_404(scope_ref, db)
        await _assert_enrolled(db, current_user.id, topic.course_id)
    elif scope_type_enum == AudioScopeType.CONCEPT:
        concept_result = await db.execute(select(Concept).where(Concept.id == scope_ref_uuid))
        concept = concept_result.scalar_one_or_none()
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        await _assert_enrolled(db, current_user.id, concept.course_id)

    owner_filter = (
        AudioArtifact.owner_id.is_(None) if owner == "global" else AudioArtifact.owner_id == current_user.id
    )
    result = await db.execute(
        select(AudioArtifact)
        .where(
            AudioArtifact.scope_type == scope_type_enum,
            AudioArtifact.scope_ref == scope_ref_uuid,
            AudioArtifact.lens == lens_enum,
            owner_filter,
        )
        .order_by(AudioArtifact.created_at.desc())
        .limit(1)
    )
    artifact = result.scalar_one_or_none()

    family = await _scope_subject_family(db, scope_type_enum, scope_ref_uuid)
    suitable = is_audio_suitable(family)

    if not artifact:
        return _audio_pending_stub(scope_type, scope_ref, lens_enum.value, audio_suitable=suitable)

    response = _audio_response(artifact, audio_suitable=suitable)
    # Passive consume (§11): fetching a ready artifact is the server-side listen signal.
    if artifact.audio_url and scope_type == AudioScopeType.TOPIC.value:
        await record_consume(
            db, actor_id=current_user.id, topic_id=scope_ref_uuid, kind=ConsumeKind.AUDIO_LISTEN
        )
    return response


@router.post("/audio/{scope_type}/{scope_ref}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_audio_artifact(
    scope_type: str,
    scope_ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger regeneration of the shared global default artifact for a scope.
    Requires the scope's knowledge to be synthesized first. Enqueues an audio
    job and returns 202 Accepted.
    """
    if scope_type != AudioScopeType.TOPIC.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio generation for scope '{scope_type}' isn't available yet",
        )

    topic = await _get_topic_or_404(scope_ref, db)
    await _assert_enrolled(db, current_user.id, topic.course_id)

    if not is_audio_suitable(topic.subject_family):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This topic doesn't suit a narrated overview — request the worked_example "
                   "lens via POST /audio/request instead, or read the note directly.",
        )

    result = await db.execute(
        select(TopicKnowledge).where(TopicKnowledge.topic_id == topic.id)
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
            "topic_id": scope_ref,
            "course_id": str(topic.course_id),
        },
    )

    return {"message": "Audio generation queued", "job_id": job_id}


class AudioRequestBody(BaseModel):
    scope_type: str
    scope_ref: uuid.UUID
    lens: str
    instruction: Optional[str] = Field(default=None, max_length=2000)


@router.post("/audio/request", status_code=status.HTTP_202_ACCEPTED)
async def request_audio_artifact(
    body: AudioRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Request a personal audio artifact — a specific lens over a scope, optionally with
    the caller's own instruction (Phase 1, docs/listen-audio-plan.md §4).

    Personal artifacts are never deduped/reused (§1) — every call creates a fresh row
    and enqueues a fresh job, unlike the shared global artifact.
    """
    if body.scope_type not in _VALID_SCOPE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown scope_type '{body.scope_type}'")
    try:
        lens_enum = AudioLens(body.lens)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown lens '{body.lens}'")

    if lens_enum == AudioLens.DEFAULT:
        raise HTTPException(
            status_code=400,
            detail="The default lens is the free shared lesson — fetch it with GET instead of requesting it.",
        )
    if lens_enum == AudioLens.USER_INSTRUCTION and not body.instruction:
        raise HTTPException(status_code=400, detail="The user_instruction lens requires an instruction")
    if lens_enum != AudioLens.USER_INSTRUCTION and body.instruction:
        raise HTTPException(status_code=400, detail="instruction is only used with the user_instruction lens")

    scope_type_enum = AudioScopeType(body.scope_type)
    if lens_enum == AudioLens.REMEDIATION and scope_type_enum != AudioScopeType.CONCEPT:
        raise HTTPException(
            status_code=400, detail="Remediation audio is scoped to a single concept — pass scope_type=concept"
        )

    topic = None
    concept = None
    subject_family = SubjectFamily.GENERAL

    if scope_type_enum == AudioScopeType.TOPIC:
        topic = await _get_topic_or_404(str(body.scope_ref), db)
        await _assert_enrolled(db, current_user.id, topic.course_id)
        knowledge_result = await db.execute(
            select(TopicKnowledge).where(TopicKnowledge.topic_id == topic.id)
        )
        knowledge = knowledge_result.scalar_one_or_none()
        course_id = topic.course_id
        subject_family = topic.subject_family
    elif scope_type_enum == AudioScopeType.CONCEPT:
        concept_result = await db.execute(select(Concept).where(Concept.id == body.scope_ref))
        concept = concept_result.scalar_one_or_none()
        if not concept:
            raise HTTPException(status_code=404, detail="Concept not found")
        await _assert_enrolled(db, current_user.id, concept.course_id)
        knowledge_result = await db.execute(
            select(TopicKnowledge).where(TopicKnowledge.topic_id == concept.topic_id)
        )
        knowledge = knowledge_result.scalar_one_or_none()
        course_id = concept.course_id
        subject_family = await _scope_subject_family(db, scope_type_enum, concept.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio generation for scope '{body.scope_type}' isn't available yet",
        )

    if lens_enum in _GENERIC_EXPLAINER_LENSES and not is_audio_suitable(subject_family):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This scope doesn't suit a narrated overview — try the worked_example lens instead.",
        )

    if not knowledge or knowledge.status != KnowledgeStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This topic's knowledge must be synthesized before generating audio.",
        )

    decision = can_generate(
        owner_id=current_user.id, scope_type=scope_type_enum, scope_ref=body.scope_ref, lens=lens_enum,
    )
    if not decision.allow:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=decision.reason or "Not enough credits"
        )

    artifact = AudioArtifact(
        scope_type=scope_type_enum,
        scope_ref=body.scope_ref,
        knowledge_id=knowledge.id,
        lens=lens_enum,
        instruction=body.instruction,
        owner_id=current_user.id,
        cost_credits=decision.cost,
        status=KnowledgeStatus.PENDING,
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)

    job_id = await redis_client.enqueue_job(
        "audio",
        {"artifact_id": str(artifact.id), "course_id": str(course_id)},
    )

    return {"message": "Audio generation queued", "job_id": job_id, "artifact_id": str(artifact.id)}
