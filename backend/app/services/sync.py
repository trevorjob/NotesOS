"""
Offline sync (B6) — the endpoints that let the native client work disconnected.

Three operations, all resting on the append-only attempt log (build-guide §5: append-only
*is* the foundation of conflict-free sync, so there's nothing to merge):

  * **snapshot**  — a bulk course pull: topics, concepts, notes, and *this user's* derived
                    knowledge state, plus a ``server_time`` the client stores as
                    ``last_synced_at``. Everything needed to read + self-quiz offline.
  * **changes**   — delta invalidation: given ``last_synced_at``, the IDs that changed
                    since (topics edited, notes re-synthesized, concepts added). The client
                    marks them stale and refetches on navigation — it never diffs blindly.
  * **push**      — replay locally-queued attempts. Each carries a client-generated
                    ``client_event_id`` (idempotent: a retried push never double-applies)
                    and its original device timestamp (honest FSRS + history). The server
                    **derives** ``ConceptState`` by replaying the events in order — it
                    stores no client-computed schedule. Only objective / self-graded modes
                    may push; AI-graded modes (ramble/teach) are online-only.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseEnrollment, Topic
from app.models.knowledge import TopicKnowledge
from app.models.retrieval import Concept, ConceptState, RetrievalAttempt
from app.services.retrieval import engine, recognition
from app.services.retrieval.modes import Outcome
from app.services.retrieval.scheduler import GRADES

# Modes whose outcome the client can decide on-device (objective MCQ / self-graded
# worked-examples). AI-graded modes need the server and are rejected on push.
OFFLINE_MODES = frozenset({"quiz", "pretest"})

# A push carrying more than this many events is almost certainly a buggy/hostile client;
# a genuine offline backlog is small. Reject the batch rather than replay unbounded work.
MAX_PUSH_BATCH = 500


# ── Push input / result ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class AttemptEvent:
    """One locally-queued attempt the client is replaying."""

    client_event_id: str
    concept_id: str
    mode: str
    grade: str
    score: Optional[float] = None
    predicted_confidence: Optional[float] = None
    created_at: Optional[datetime] = None
    challenge: Optional[dict] = None
    response: Any = None


@dataclass(frozen=True)
class PushResult:
    """The outcome of replaying one event — never raises; a bad event is reported, not fatal."""

    client_event_id: str
    status: str                       # applied | duplicate | rejected
    concept_id: Optional[str] = None
    reason: Optional[str] = None      # why it was rejected
    state: Optional[dict] = None      # the derived ConceptState after applying


# ── Serialization helpers ─────────────────────────────────────────────────────

def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _state_dict(state: ConceptState) -> dict:
    return {
        "concept_id": str(state.concept_id),
        "due": _iso(state.due),
        "reps": state.reps,
        "lapses": state.lapses,
        "stability": state.stability,
        "difficulty": state.difficulty,
        "last_grade": state.last_grade,
        "updated_at": _iso(state.updated_at),
    }


def _naive_utc(dt: datetime) -> datetime:
    """Normalise to naive-UTC — the DB columns are tz-naive."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


# ── Bulk pull ─────────────────────────────────────────────────────────────────

async def course_snapshot(db: AsyncSession, *, user_id, course_id, now: Optional[datetime] = None) -> dict:
    """The full offline bundle for one course: content + this user's derived state."""
    server_time = _naive_utc(now or datetime.utcnow())
    course = await db.get(Course, course_id)
    if course is None:
        return {}

    topics = list((await db.execute(
        select(Topic).where(Topic.course_id == course_id).order_by(Topic.order_index)
    )).scalars().all())

    concepts = list((await db.execute(
        select(Concept).where(Concept.course_id == course_id).order_by(Concept.order_index)
    )).scalars().all())

    notes = list((await db.execute(
        select(TopicKnowledge)
        .join(Topic, Topic.id == TopicKnowledge.topic_id)
        .where(Topic.course_id == course_id)
    )).scalars().all())

    states = list((await db.execute(
        select(ConceptState)
        .join(Concept, Concept.id == ConceptState.concept_id)
        .where(Concept.course_id == course_id)
        .where(ConceptState.user_id == user_id)
    )).scalars().all())

    return {
        "server_time": _iso(server_time),
        "course": {"id": str(course.id), "code": course.code, "name": course.name},
        "topics": [
            {
                "id": str(t.id),
                "title": t.title,
                "order_index": t.order_index,
                "subject_family": t.subject_family.value,
                "updated_at": _iso(t.updated_at),
            }
            for t in topics
        ],
        "concepts": [
            {
                "id": str(c.id),
                "topic_id": str(c.topic_id),
                "text": c.text,
                "definition": c.definition,
                "order_index": c.order_index,
            }
            for c in concepts
        ],
        "notes": [
            {
                "topic_id": str(n.topic_id),
                "consolidated_note": n.consolidated_note,
                "key_points": n.key_points,
                "concepts": n.concepts,
                "generated_at": _iso(n.generated_at),
            }
            for n in notes
        ],
        "states": [_state_dict(s) for s in states],
    }


# ── Delta invalidation ────────────────────────────────────────────────────────

async def changes_since(
    db: AsyncSession, *, user_id, since: datetime, course_id=None, now: Optional[datetime] = None
) -> dict:
    """IDs that changed since ``since`` across the user's enrolled courses (or one course)."""
    server_time = _naive_utc(now or datetime.utcnow())
    since = _naive_utc(since)

    if course_id is not None:
        course_ids = [course_id]
    else:
        course_ids = list((await db.execute(
            select(CourseEnrollment.course_id).where(CourseEnrollment.user_id == user_id)
        )).scalars().all())

    if not course_ids:
        return {"server_time": _iso(server_time), "topics": [], "notes": [], "concepts": []}

    topics = list((await db.execute(
        select(Topic.id)
        .where(Topic.course_id.in_(course_ids))
        .where(Topic.updated_at > since)
    )).scalars().all())

    # A re-synthesized note = a topic whose knowledge regenerated (someone contributed).
    notes = list((await db.execute(
        select(TopicKnowledge.topic_id)
        .join(Topic, Topic.id == TopicKnowledge.topic_id)
        .where(Topic.course_id.in_(course_ids))
        .where(TopicKnowledge.generated_at.isnot(None))
        .where(TopicKnowledge.generated_at > since)
    )).scalars().all())

    concepts = list((await db.execute(
        select(Concept.id)
        .where(Concept.course_id.in_(course_ids))
        .where(Concept.created_at > since)
    )).scalars().all())

    return {
        "server_time": _iso(server_time),
        "topics": [str(x) for x in topics],
        "notes": [str(x) for x in notes],
        "concepts": [str(x) for x in concepts],
    }


# ── Append-only event push (replay) ───────────────────────────────────────────

async def push_attempts(db: AsyncSession, *, user_id, events: list[AttemptEvent]) -> list[PushResult]:
    """Replay queued offline attempts, deriving ConceptState. Idempotent + partial-safe.

    Events replay in device-timestamp order so FSRS advances exactly as it would have
    online. A duplicate ``client_event_id`` (already stored, or repeated in the batch) is
    a no-op. A malformed / unauthorized / non-offline event is rejected individually — one
    bad event never sinks the batch. The caller owns the commit.
    """
    if len(events) > MAX_PUSH_BATCH:
        raise ValueError(f"push batch too large ({len(events)} > {MAX_PUSH_BATCH})")

    ordered = sorted(events, key=lambda e: e.created_at or datetime.max)
    already = await _existing_event_ids(db, [e.client_event_id for e in events])
    enrolled = await _enrolled_course_ids(db, user_id)

    results: list[PushResult] = []
    seen: set[str] = set()
    for event in ordered:
        result = await _apply_event(db, user_id, event, already=already, enrolled=enrolled, seen=seen)
        results.append(result)
    return results


async def _apply_event(db, user_id, event, *, already, enrolled, seen) -> PushResult:
    key = event.client_event_id
    if not key:
        return PushResult(client_event_id="", status="rejected", reason="missing client_event_id")
    if key in already or key in seen:
        return PushResult(client_event_id=key, status="duplicate", concept_id=event.concept_id)
    seen.add(key)

    invalid = _validate_event(event)
    if invalid:
        return PushResult(client_event_id=key, status="rejected", concept_id=event.concept_id, reason=invalid)

    concept = await db.get(Concept, _as_uuid(event.concept_id))
    if concept is None:
        return PushResult(client_event_id=key, status="rejected", concept_id=event.concept_id, reason="unknown concept")
    if concept.course_id not in enrolled:
        return PushResult(client_event_id=key, status="rejected", concept_id=event.concept_id, reason="not enrolled")

    outcome = Outcome(score=_clamp_score(event.score, event.grade), grade=event.grade)
    result = await engine.record_attempt(
        db,
        user_id=user_id,
        concept_id=concept.id,
        mode=event.mode,
        outcome=outcome,
        predicted_confidence=event.predicted_confidence,
        challenge=event.challenge,
        response=event.response,
        now=event.created_at,
        created_at=event.created_at,
        client_event_id=_as_uuid(key),
    )
    # Same recognition seam as the online /attempt path — a replayed attempt is a real event.
    await recognition.on_attempt(db, attempt=result.attempt, concept=concept, learner_id=user_id)
    return PushResult(client_event_id=key, status="applied", concept_id=str(concept.id), state=_state_dict(result.state))


def _validate_event(event: AttemptEvent) -> Optional[str]:
    """Return a rejection reason, or None if the event is well-formed + pushable."""
    if event.mode not in OFFLINE_MODES:
        return f"mode {event.mode!r} is online-only"
    if event.grade not in GRADES:
        return f"invalid grade {event.grade!r}"
    if _as_uuid(event.concept_id) is None:
        return "malformed concept_id"
    if _as_uuid(event.client_event_id) is None:
        return "malformed client_event_id"
    return None


# ── small helpers ─────────────────────────────────────────────────────────────

# Fallback score per grade when the client sends a grade but no numeric score.
_GRADE_SCORE = {"again": 0.0, "hard": 0.5, "good": 0.8, "easy": 1.0}


def _clamp_score(score: Optional[float], grade: str) -> float:
    if score is None:
        return _GRADE_SCORE.get(grade, 0.5)
    return max(0.0, min(1.0, float(score)))


def _as_uuid(value):
    import uuid as _uuid
    try:
        return _uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


async def _existing_event_ids(db: AsyncSession, keys: list[str]) -> set[str]:
    """Which of these client_event_ids are already stored (already applied on a prior push)."""
    uuids = [u for u in (_as_uuid(k) for k in keys) if u is not None]
    if not uuids:
        return set()
    rows = await db.execute(
        select(RetrievalAttempt.client_event_id).where(RetrievalAttempt.client_event_id.in_(uuids))
    )
    return {str(r[0]) for r in rows.all()}


async def _enrolled_course_ids(db: AsyncSession, user_id) -> set:
    rows = await db.execute(
        select(CourseEnrollment.course_id).where(CourseEnrollment.user_id == user_id)
    )
    return {r[0] for r in rows.all()}
