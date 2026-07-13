"""
Next-best-action selector (B3) — the *one* engine behind "what should I study now?".

The home is a doorway, not a dashboard (system-spec §14.1): its whole job is to remove the
"what should I study?" decision that kills sessions before they start. The decay digest
(§8) asks the *same* question from the push side ("good time to firm up the Krebs cycle —
5 min"). **Both pull the same answer from here** — one selector, never two (build-guide §4).

**The signal, in strict priority (usually review wins — fading knowledge is the point):**
1. **review** — concepts past their FSRS ``due`` (fading). The core loop.
2. **calibration** — concepts the user was *confident* on but recently *missed* (the fluency
   illusion, made visible). Worth a recheck.
3. **new** — concepts in an enrolled course the user has never attempted. A pretest primes
   them (answer-before-studying).
4. **get_ahead** — nothing's due or new, but there's a schedule: firm up the soonest-due.

**Never empty-handed** (§14.1): if the user has *any* concept the selector returns an
action; it returns ``None`` only when there's genuinely nothing yet (→ the caller sends
them to capture). Everything is **topic-scoped** — the topic is the unit a student studies.
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import CourseEnrollment, Topic
from app.models.retrieval import Concept, ConceptState, RetrievalAttempt
from app.models.subject import SubjectFamily
from app.services.retrieval.subject_profiles import preferred_mode

# A predicted confidence at/above this that still ends in a miss = overconfidence.
OVERCONFIDENT_PREDICTED = 0.6
_MISS_GRADES = ("again", "hard")
CALIBRATION_LOOKBACK = timedelta(days=30)

_MINUTES_PER_CONCEPT = 1
_MIN_MINUTES = 2
_MAX_MINUTES = 15
_MAX_CONCEPTS_PER_ACTION = 20  # a session bite, not the whole backlog

# Candidate modes per action kind — the subject family's profile picks the best-affinity
# one among them (build-guide B4: the profile drives the mode mix). The order is the
# pedagogical default, which wins on an affinity tie.
#   new         → pretest only: answering-before-studying primes new material (invariant).
#   calibration → quiz only: it's the mode carrying the predicted-vs-actual mechanic.
#   review/get_ahead → ordinary effortful retrieval, where the family gets to lean
#                      (STEM→quiz worked-example, LANGUAGE→ramble, HUMANITIES→teach).
_CANDIDATE_MODES = {
    "review": ("quiz", "teach", "ramble"),
    "calibration": ("quiz",),
    "new": ("pretest",),
    "get_ahead": ("quiz", "teach", "ramble"),
}


@dataclass(frozen=True)
class NextAction:
    """The single highest-value thing to do now — topic-scoped."""

    kind: str                       # review | calibration | new | get_ahead
    course_id: uuid.UUID
    topic_id: uuid.UUID
    topic_title: str
    concept_ids: list[uuid.UUID]
    mode: str
    reason: str                     # warm, specific one-liner (§8)
    est_minutes: int


@dataclass
class _Bucket:
    """Concepts of one kind gathered under a topic, before we pick a winner."""

    topic_id: uuid.UUID
    topic_title: str
    course_id: uuid.UUID
    family: SubjectFamily = SubjectFamily.GENERAL  # topic's subject family (drives mode pick)
    concept_ids: list[uuid.UUID] = field(default_factory=list)
    # Smaller = more urgent (earliest due / oldest miss). Used only as a tie-breaker.
    urgency_key: Optional[datetime] = None


def _est_minutes(n: int) -> int:
    return max(_MIN_MINUTES, min(_MAX_MINUTES, math.ceil(n * _MINUTES_PER_CONCEPT)))


def _pick_top(buckets: dict, *, kind: str, reason_fn) -> Optional[NextAction]:
    """Choose the strongest topic in a kind: most concepts, then most urgent."""
    if not buckets:
        return None
    best = max(
        buckets.values(),
        key=lambda b: (len(b.concept_ids), -_urgency_sort(b.urgency_key)),
    )
    concept_ids = best.concept_ids[:_MAX_CONCEPTS_PER_ACTION]
    return NextAction(
        kind=kind,
        course_id=best.course_id,
        topic_id=best.topic_id,
        topic_title=best.topic_title,
        concept_ids=concept_ids,
        mode=preferred_mode(best.family, _CANDIDATE_MODES[kind]),
        reason=reason_fn(best.topic_title, len(concept_ids)),
        est_minutes=_est_minutes(len(concept_ids)),
    )


def _urgency_sort(key: Optional[datetime]) -> float:
    """Earliest timestamp = most urgent = smallest sort value; None sorts last."""
    return key.timestamp() if key is not None else float("inf")


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


# ── Candidate builders (each returns {topic_id: _Bucket}) ─────────────────────

async def _enrolled_course_ids(db: AsyncSession, user_id) -> list[uuid.UUID]:
    return list(
        (
            await db.execute(
                select(CourseEnrollment.course_id).where(CourseEnrollment.user_id == user_id)
            )
        ).scalars().all()
    )


def _scoped(stmt, *, course_id, topic_id):
    if course_id is not None:
        stmt = stmt.where(Concept.course_id == course_id)
    if topic_id is not None:
        stmt = stmt.where(Concept.topic_id == topic_id)
    return stmt


async def _review_buckets(db, user_id, *, now, course_id, topic_id) -> dict:
    stmt = _scoped(
        select(Concept.id, Concept.topic_id, Concept.course_id, Topic.title, Topic.subject_family, ConceptState.due)
        .join(ConceptState, ConceptState.concept_id == Concept.id)
        .join(Topic, Topic.id == Concept.topic_id)
        .where(ConceptState.user_id == user_id)
        .where(ConceptState.due.isnot(None))
        .where(ConceptState.due <= now)
        .order_by(ConceptState.due.asc()),
        course_id=course_id,
        topic_id=topic_id,
    )
    return _group((await db.execute(stmt)).all(), urgency_index=5)


async def _calibration_buckets(db, user_id, *, now, course_id, topic_id, exclude: set) -> dict:
    stmt = _scoped(
        select(Concept.id, Concept.topic_id, Concept.course_id, Topic.title, Topic.subject_family, RetrievalAttempt.created_at)
        .join(Concept, Concept.id == RetrievalAttempt.concept_id)
        .join(Topic, Topic.id == Concept.topic_id)
        .where(RetrievalAttempt.user_id == user_id)
        .where(RetrievalAttempt.predicted_confidence >= OVERCONFIDENT_PREDICTED)
        .where(RetrievalAttempt.grade.in_(_MISS_GRADES))
        .where(RetrievalAttempt.created_at >= now - CALIBRATION_LOOKBACK)
        .order_by(RetrievalAttempt.created_at.asc()),
        course_id=course_id,
        topic_id=topic_id,
    )
    return _group((await db.execute(stmt)).all(), urgency_index=5, exclude=exclude)


async def _new_buckets(db, user_id, *, course_id, topic_id) -> dict:
    course_ids = [course_id] if course_id is not None else await _enrolled_course_ids(db, user_id)
    if not course_ids:
        return {}
    # Concepts in enrolled courses this user has never built a state for (never attempted).
    has_state = (
        select(ConceptState.id)
        .where(ConceptState.concept_id == Concept.id)
        .where(ConceptState.user_id == user_id)
        .exists()
    )
    stmt = _scoped(
        select(Concept.id, Concept.topic_id, Concept.course_id, Topic.title, Topic.subject_family, Concept.created_at)
        .join(Topic, Topic.id == Concept.topic_id)
        .where(Concept.course_id.in_(course_ids))
        .where(~has_state)
        .order_by(Concept.created_at.desc()),
        course_id=course_id,
        topic_id=topic_id,
    )
    return _group((await db.execute(stmt)).all(), urgency_index=None)


async def _get_ahead_bucket(db, user_id, *, course_id, topic_id) -> dict:
    stmt = _scoped(
        select(Concept.id, Concept.topic_id, Concept.course_id, Topic.title, Topic.subject_family, ConceptState.due)
        .join(ConceptState, ConceptState.concept_id == Concept.id)
        .join(Topic, Topic.id == Concept.topic_id)
        .where(ConceptState.user_id == user_id)
        .where(ConceptState.due.isnot(None))
        .order_by(ConceptState.due.asc())
        .limit(_MAX_CONCEPTS_PER_ACTION),
        course_id=course_id,
        topic_id=topic_id,
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return {}
    # Just the single soonest-due topic — this is the "nothing pressing" fallback.
    first_topic = rows[0][1]
    rows = [r for r in rows if r[1] == first_topic]
    return _group(rows, urgency_index=5)


def _group(rows, *, urgency_index, exclude: Optional[set] = None) -> dict:
    """Fold (concept_id, topic_id, course_id, title, family, [urgency]) rows into buckets."""
    buckets: dict = {}
    for row in rows:
        concept_id, topic_id, course_id, title, family = row[0], row[1], row[2], row[3], row[4]
        if exclude and concept_id in exclude:
            continue
        bucket = buckets.get(topic_id)
        if bucket is None:
            bucket = _Bucket(
                topic_id=topic_id, topic_title=title, course_id=course_id, family=family
            )
            buckets[topic_id] = bucket
        if concept_id not in bucket.concept_ids:
            bucket.concept_ids.append(concept_id)
        if urgency_index is not None:
            key = row[urgency_index]
            if key is not None and (bucket.urgency_key is None or key < bucket.urgency_key):
                bucket.urgency_key = key
    return buckets


# ── The selector ──────────────────────────────────────────────────────────────

async def select_next_action(
    db: AsyncSession,
    *,
    user_id,
    course_id=None,
    topic_id=None,
    now: Optional[datetime] = None,
) -> Optional[NextAction]:
    """The single highest-value action for this user now, or ``None`` if nothing to do.

    Strict cascade: review (fading) → calibration (confident-but-missed) → new (unseen) →
    get_ahead. Scope narrows it to a course/topic (the home card is global; a course page
    can pass ``course_id``). ``None`` only when the user has no concepts at all.
    """
    now = now or datetime.utcnow()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    review = await _review_buckets(db, user_id, now=now, course_id=course_id, topic_id=topic_id)
    action = _pick_top(
        review,
        kind="review",
        reason_fn=lambda t, n: f"{n} concept{_plural(n)} fading in {t} — good time to firm up.",
    )
    if action:
        return action

    reviewed_concepts = {cid for b in review.values() for cid in b.concept_ids}
    calibration = await _calibration_buckets(
        db, user_id, now=now, course_id=course_id, topic_id=topic_id, exclude=reviewed_concepts
    )
    action = _pick_top(
        calibration,
        kind="calibration",
        reason_fn=lambda t, n: f"You were sure on {n} concept{_plural(n)} in {t} but missed — worth a recheck.",
    )
    if action:
        return action

    new = await _new_buckets(db, user_id, course_id=course_id, topic_id=topic_id)
    action = _pick_top(
        new,
        kind="new",
        reason_fn=lambda t, n: f"New in {t}: {n} concept{_plural(n)} you haven't tried — a quick pretest primes them.",
    )
    if action:
        return action

    get_ahead = await _get_ahead_bucket(db, user_id, course_id=course_id, topic_id=topic_id)
    return _pick_top(
        get_ahead,
        kind="get_ahead",
        reason_fn=lambda t, n: f"All caught up in {t} — get ahead with a few?",
    )
