"""
The retrieval engine core — mode-agnostic.

Given a concept and a mode, the engine:
- **selects** which concepts a session works on (scope: topic / course / interleaved /
  spaced-due), reading the FSRS schedule for what's due,
- **runs** the mode (generate → evaluate),
- **records** an append-only ``RetrievalAttempt``,
- **updates** the ``ConceptState`` schedule via FSRS,
- and returns enough for the caller to fire calibration + recognition events.

Modes are plugins (see ``modes.py``); the engine never knows which one it's running.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import Concept, ConceptState, RetrievalAttempt
from app.services.retrieval import scheduler
from app.services.retrieval.modes import Challenge, ModeContext, Outcome, RetrievalMode

# Scopes: the pool a session draws its concepts from.
SCOPE_TOPIC = "topic"
SCOPE_COURSE = "course"
SCOPE_INTERLEAVED = "interleaved"  # mixed across the course (Learning Science Part 2)
SCOPE_SPACED_DUE = "spaced_due"    # only concepts due for review (Part 5)
SCOPES = (SCOPE_TOPIC, SCOPE_COURSE, SCOPE_INTERLEAVED, SCOPE_SPACED_DUE)


@dataclass(frozen=True)
class AttemptResult:
    """What a completed retrieval produces — the event + the new schedule."""

    attempt: RetrievalAttempt
    state: ConceptState
    outcome: Outcome


async def select_concepts(
    db: AsyncSession,
    *,
    user_id,
    scope: str,
    topic_id=None,
    course_id=None,
    limit: int = 10,
    now: Optional[datetime] = None,
) -> list[Concept]:
    """Pick the concepts for a session according to ``scope``.

    - ``topic`` / ``course`` — all concepts in that topic / course (ordered).
    - ``interleaved`` — a random mix across the course (interleaving beats blocking).
    - ``spaced_due`` — only concepts this user has a schedule for that are due now,
      soonest-due first. New (never-seen) concepts are not "due"; introduce those via
      ``topic``/``course`` scope.
    """
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}; expected one of {SCOPES}")

    if scope == SCOPE_SPACED_DUE:
        cutoff = (now or datetime.utcnow())
        if cutoff.tzinfo is not None:
            cutoff = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
        stmt = (
            select(Concept)
            .join(ConceptState, ConceptState.concept_id == Concept.id)
            .where(ConceptState.user_id == user_id)
            .where(ConceptState.due.isnot(None))
            .where(ConceptState.due <= cutoff)
            .order_by(ConceptState.due.asc())
            .limit(limit)
        )
        if course_id is not None:
            stmt = stmt.where(Concept.course_id == course_id)
        if topic_id is not None:
            stmt = stmt.where(Concept.topic_id == topic_id)
        return list((await db.execute(stmt)).scalars().all())

    stmt = select(Concept)
    if scope == SCOPE_TOPIC:
        if topic_id is None:
            raise ValueError("topic scope requires topic_id")
        stmt = stmt.where(Concept.topic_id == topic_id).order_by(Concept.order_index)
    else:  # course or interleaved — both span the course
        if course_id is None:
            raise ValueError(f"{scope} scope requires course_id")
        stmt = stmt.where(Concept.course_id == course_id)
        stmt = stmt.order_by(func.random() if scope == SCOPE_INTERLEAVED else Concept.order_index)

    return list((await db.execute(stmt.limit(limit))).scalars().all())


async def record_attempt(
    db: AsyncSession,
    *,
    user_id,
    concept_id,
    mode: str,
    outcome: Outcome,
    predicted_confidence: Optional[float] = None,
    challenge: Optional[dict] = None,
    response: Any = None,
    now: Optional[datetime] = None,
) -> AttemptResult:
    """Log the event (append-only) and advance the concept's FSRS schedule.

    Creates the ``ConceptState`` on first contact. Flushes so ids are populated; the
    caller owns the transaction. Does not fire calibration/recognition side effects —
    the caller does, off the returned result.
    """
    review_at = now or datetime.now(timezone.utc)

    attempt = RetrievalAttempt(
        user_id=user_id,
        concept_id=concept_id,
        mode=mode,
        predicted_confidence=predicted_confidence,
        outcome_score=outcome.score,
        grade=outcome.grade,
        challenge=challenge,
        response=response if isinstance(response, (dict, list)) else None,
    )
    db.add(attempt)

    state = await db.scalar(
        select(ConceptState).where(
            ConceptState.user_id == user_id, ConceptState.concept_id == concept_id
        )
    )
    if state is None:
        state = ConceptState(user_id=user_id, concept_id=concept_id, reps=0, lapses=0)
        db.add(state)

    review = scheduler.apply_review(state.fsrs_card, outcome.grade, now=review_at)
    state.fsrs_card = review.card
    state.due = review.due
    state.stability = review.stability
    state.difficulty = review.difficulty
    state.fsrs_state = review.state
    state.last_review = review.last_review
    state.reps += 1
    if outcome.grade == "again":
        state.lapses += 1  # a lapse is a forgetting — the forgetting badge counts these
    state.last_grade = outcome.grade

    await db.flush()
    return AttemptResult(attempt=attempt, state=state, outcome=outcome)


async def run_once(
    db: AsyncSession,
    *,
    mode: RetrievalMode,
    concept: Concept,
    response: Any,
    ctx: ModeContext,
    predicted_confidence: Optional[float] = None,
    now: Optional[datetime] = None,
) -> AttemptResult:
    """End-to-end for a single concept: generate → evaluate → record.

    A convenience for non-interactive callers and tests. Interactive flows split this
    across two requests (generate, then evaluate+record) so the user's predicted
    confidence can be captured in between — but the pipeline is the same.
    """
    challenge = await mode.generate(concept, ctx)
    outcome = await mode.evaluate(concept, challenge, response, ctx)
    return await record_attempt(
        db,
        user_id=ctx.user_id,
        concept_id=concept.id,
        mode=mode.key,
        outcome=outcome,
        predicted_confidence=predicted_confidence,
        challenge={"prompt": challenge.prompt, **challenge.payload},
        response=response if isinstance(response, (dict, list)) else {"raw": response},
        now=now,
    )
