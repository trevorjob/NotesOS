"""
Remediation support (docs/listen-audio-plan.md §6) — the "you keep missing X, want a
breakdown?" flow. Both pieces reuse signal that already exists:

  * ``weakest_concepts`` — the "shaky" mastery label from the note's own heat-map
    (``derive_mastery``) is exactly "struggling with this concept"; no new detection.
  * ``recent_wrong_answers`` — the append-only ``RetrievalAttempt`` log already holds
    the question asked and what the user answered; remediation audio grounds itself in
    those specific misses instead of re-explaining the concept generically.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import Concept, ConceptState, RetrievalAttempt
from app.services.retrieval.scheduler import MASTERY_SHAKY, derive_mastery


async def weakest_concepts(
    db: AsyncSession, *, user_id, topic_id, limit: int = 5
) -> List[Concept]:
    """The caller's shakiest concepts within a topic, most-lapsed first.

    "Shaky" is the same label the note's heat-map already shows the user — a concept
    just missed (``last_grade == "again"``) or mid-relearning. Empty when nothing in
    this topic currently reads that way.
    """
    result = await db.execute(
        select(Concept, ConceptState)
        .join(ConceptState, ConceptState.concept_id == Concept.id)
        .where(ConceptState.user_id == user_id, Concept.topic_id == topic_id)
    )

    shaky: List[tuple] = []
    for concept, state in result.all():
        mastery = derive_mastery(
            reps=state.reps, last_grade=state.last_grade, fsrs_state=state.fsrs_state, due=state.due
        )
        if mastery == MASTERY_SHAKY:
            shaky.append((concept, state))

    shaky.sort(key=lambda pair: pair[1].lapses, reverse=True)
    return [concept for concept, _ in shaky[:limit]]


async def recent_wrong_answers(
    db: AsyncSession, *, user_id, concept_id, limit: int = 3
) -> List[Dict[str, Any]]:
    """The caller's most recent missed attempts on a concept, as ``{question,
    your_answer}`` pairs — the grounding material for a remediation lesson. Attempts
    without a recorded prompt (shouldn't happen, but the log is append-only and
    external) are skipped rather than surfaced as a broken pair.
    """
    result = await db.execute(
        select(RetrievalAttempt)
        .where(
            RetrievalAttempt.user_id == user_id,
            RetrievalAttempt.concept_id == concept_id,
            RetrievalAttempt.grade == "again",
        )
        .order_by(RetrievalAttempt.created_at.desc())
        .limit(limit)
    )

    pairs: List[Dict[str, Any]] = []
    for attempt in result.scalars().all():
        question = (attempt.challenge or {}).get("prompt")
        if not question:
            continue
        response = attempt.response or {}
        answer = response.get("raw", response) if isinstance(response, dict) else response
        pairs.append({"question": question, "your_answer": answer})
    return pairs
