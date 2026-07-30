"""
Session summary — the warm close (system-spec §5/§6).

Derived from the attempt log over the user's most recent session (the same ≥15-min
idle-gap clustering as ``session.py``). Reports what the bout changed: concepts **firmed**
vs. **still slipping** (via the note's mastery vocabulary) and the **calibration delta**.
Never stored — recomputed from the log. Framing is design's call; the service just gives
the honest state (lead with growth, whisper the fading — §6).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import Concept, ConceptState
from app.services.retrieval import session
from app.services.retrieval.scheduler import MASTERY_SOLID, derive_mastery

# Same band as the /attempt calibration label (api/retrieval.py): |delta| ≤ 0.15 is calibrated.
_CALIB_BAND = 0.15


@dataclass(frozen=True)
class ConceptChange:
    concept_id: str
    concept_text: str
    state: str          # current mastery (derive_mastery): solid / fading / shaky
    attempts: int       # attempts on this concept within the session
    mean_score: float


@dataclass(frozen=True)
class SessionSummary:
    started_at: datetime
    ended_at: datetime
    attempt_count: int
    concept_count: int
    firmed: list[ConceptChange]      # solid now — lead with these
    slipping: list[ConceptChange]    # shaky / fading — whisper these
    calibration_delta: Optional[float]   # mean(actual − predicted); >0 underconfident
    calibration_label: Optional[str]
    predicted_count: int             # attempts that carried a prediction


def _calibration_label(delta: Optional[float]) -> Optional[str]:
    if delta is None:
        return None
    if delta > _CALIB_BAND:
        return "underconfident"
    if delta < -_CALIB_BAND:
        return "overconfident"
    return "calibrated"


async def build_session_summary(
    db: AsyncSession,
    user_id,
    *,
    course_id=None,
    topic_id=None,
    now: Optional[datetime] = None,
) -> Optional[SessionSummary]:
    """Summarize the user's most recent session in scope, or ``None`` if there is none."""
    attempts = await session.last_session_attempts(
        db, user_id, course_id=course_id, topic_id=topic_id
    )
    if not attempts:
        return None
    now = now or datetime.utcnow()

    order, counts, score_sum = _fold_by_concept(attempts)
    states = await _states_for(db, user_id, order, now=now)

    firmed: list[ConceptChange] = []
    slipping: list[ConceptChange] = []
    for cid in order:
        entry = states.get(cid)
        if entry is None:
            continue  # attempted but no state row — shouldn't happen (record_attempt writes it)
        text, mastery = entry
        change = ConceptChange(
            concept_id=cid,
            concept_text=text,
            state=mastery,
            attempts=counts[cid],
            mean_score=score_sum[cid] / counts[cid],
        )
        (firmed if mastery == MASTERY_SOLID else slipping).append(change)

    firmed.sort(key=lambda c: c.mean_score, reverse=True)   # strongest first
    slipping.sort(key=lambda c: c.mean_score)               # neediest first

    predicted = [
        (a.predicted_confidence, a.outcome_score)
        for a in attempts
        if a.predicted_confidence is not None and a.outcome_score is not None
    ]
    delta = (
        sum(score - pred for pred, score in predicted) / len(predicted)
        if predicted
        else None
    )

    return SessionSummary(
        started_at=attempts[0].created_at,
        ended_at=attempts[-1].created_at,
        attempt_count=len(attempts),
        concept_count=len(order),
        firmed=firmed,
        slipping=slipping,
        calibration_delta=delta,
        calibration_label=_calibration_label(delta),
        predicted_count=len(predicted),
    )


def _fold_by_concept(attempts) -> tuple[list[str], dict[str, int], dict[str, float]]:
    """First-touched concept order + per-concept attempt count and score sum."""
    order: list[str] = []
    counts: dict[str, int] = {}
    score_sum: dict[str, float] = {}
    for a in attempts:
        cid = str(a.concept_id)
        if cid not in counts:
            order.append(cid)
            counts[cid] = 0
            score_sum[cid] = 0.0
        counts[cid] += 1
        score_sum[cid] += a.outcome_score or 0.0
    return order, counts, score_sum


async def _states_for(db, user_id, concept_ids: list[str], *, now: datetime) -> dict:
    """``{concept_id: (concept_text, mastery)}`` for the touched concepts (current state)."""
    if not concept_ids:
        return {}
    stmt = (
        select(ConceptState, Concept.text)
        .join(Concept, Concept.id == ConceptState.concept_id)
        .where(
            ConceptState.user_id == user_id,
            ConceptState.concept_id.in_([uuid.UUID(c) for c in concept_ids]),
        )
    )
    out: dict = {}
    for cs, text in (await db.execute(stmt)).all():
        mastery = derive_mastery(
            reps=cs.reps, last_grade=cs.last_grade, fsrs_state=cs.fsrs_state, due=cs.due, now=now
        )
        out[str(cs.concept_id)] = (text, mastery)
    return out
