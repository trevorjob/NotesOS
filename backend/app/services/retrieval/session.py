"""
Study sessions — *derived*, never stored.

A session is not a table. It is a **query** over the append-only ``RetrievalAttempt``
log: order a user's attempts by time and cut a new session wherever the gap between
two consecutive attempts is ≥ ``SESSION_IDLE_GAP``. This keeps the derive-first
philosophy (build-guide §5) — the log is the single source of truth, and "what counts
as a session" stays a policy we can retune without a migration.

Used by Recap (the set of concepts the last session touched) and, later, by the
notification timing and progress surfaces.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import Concept, RetrievalAttempt

# A gap of at least this long between consecutive attempts closes a session.
SESSION_IDLE_GAP = timedelta(minutes=15)

# Safety bound on how many recent attempts we scan when deriving sessions. The newest
# session is intact as long as it holds ≤ this many attempts (far more than any real
# study block), while an unbounded log can't blow up the query.
_MAX_ATTEMPTS_SCAN = 1000


@dataclass(frozen=True)
class Session:
    """One derived study session — a contiguous run of attempts, no idle ≥ gap."""

    started_at: datetime
    ended_at: datetime
    attempt_count: int
    concept_ids: list[str]      # distinct, in first-touched order
    modes: dict[str, int]       # mode → attempt count within the session


def split_attempt_buckets(attempts: list[Any]) -> list[list[Any]]:
    """Cut time-ordered attempts into buckets on a ≥ gap of idleness, keeping raw rows.

    ``attempts`` must be ordered **ascending** by ``created_at``. The warm-close summary
    needs the attempts themselves (scores, predictions), not just the folded ``Session``.
    """
    buckets: list[list[Any]] = []
    bucket: list[Any] = []
    prev_at: Optional[datetime] = None

    for attempt in attempts:
        at = attempt.created_at
        if prev_at is not None and (at - prev_at) >= SESSION_IDLE_GAP:
            buckets.append(bucket)
            bucket = []
        bucket.append(attempt)
        prev_at = at

    if bucket:
        buckets.append(bucket)
    return buckets


def split_sessions(attempts: list[Any]) -> list[Session]:
    """Group time-ordered attempts into sessions, cutting on a ≥ gap of idleness.

    ``attempts`` must be ordered **ascending** by ``created_at``. Pure — the query
    layer feeds it; tests exercise it directly. Returns sessions oldest-first.
    """
    return [_close(bucket) for bucket in split_attempt_buckets(attempts)]


def _close(bucket: list[Any]) -> Session:
    """Fold a bucket of attempts into an immutable ``Session``."""
    concept_ids: list[str] = []
    seen: set[str] = set()
    modes: dict[str, int] = {}
    for attempt in bucket:
        cid = str(attempt.concept_id)
        if cid not in seen:
            seen.add(cid)
            concept_ids.append(cid)
        modes[attempt.mode] = modes.get(attempt.mode, 0) + 1
    return Session(
        started_at=bucket[0].created_at,
        ended_at=bucket[-1].created_at,
        attempt_count=len(bucket),
        concept_ids=concept_ids,
        modes=modes,
    )


async def get_sessions(
    db: AsyncSession,
    user_id,
    *,
    course_id=None,
    topic_id=None,
) -> list[Session]:
    """Derive this user's recent sessions, newest-first.

    Optionally scoped to a ``course_id`` / ``topic_id`` (joined through ``Concept``).
    Scans at most ``_MAX_ATTEMPTS_SCAN`` most-recent attempts.
    """
    attempts = await _recent_attempts(db, user_id, course_id=course_id, topic_id=topic_id)
    sessions = split_sessions(attempts)
    sessions.reverse()  # newest session first for callers/UX
    return sessions


async def last_session(
    db: AsyncSession,
    user_id,
    *,
    course_id=None,
    topic_id=None,
) -> Optional[Session]:
    """The most recent derived session in scope, or ``None`` if there are no attempts."""
    sessions = await get_sessions(db, user_id, course_id=course_id, topic_id=topic_id)
    return sessions[0] if sessions else None


async def last_session_attempts(
    db: AsyncSession,
    user_id,
    *,
    course_id=None,
    topic_id=None,
) -> list[Any]:
    """The raw attempts of the most recent session in scope ([] if there are none)."""
    attempts = await _recent_attempts(db, user_id, course_id=course_id, topic_id=topic_id)
    buckets = split_attempt_buckets(attempts)
    return buckets[-1] if buckets else []


async def _recent_attempts(db, user_id, *, course_id, topic_id) -> list[Any]:
    """Fetch the most-recent attempts (ascending), scoped, capped for safety."""
    stmt = select(RetrievalAttempt).where(RetrievalAttempt.user_id == user_id)
    if course_id is not None or topic_id is not None:
        stmt = stmt.join(Concept, Concept.id == RetrievalAttempt.concept_id)
        if course_id is not None:
            stmt = stmt.where(Concept.course_id == course_id)
        if topic_id is not None:
            stmt = stmt.where(Concept.topic_id == topic_id)
    # Take the newest N by pulling descending, then hand split_sessions ascending order.
    stmt = stmt.order_by(RetrievalAttempt.created_at.desc()).limit(_MAX_ATTEMPTS_SCAN)
    rows = list((await db.execute(stmt)).scalars().all())
    rows.reverse()
    return rows
