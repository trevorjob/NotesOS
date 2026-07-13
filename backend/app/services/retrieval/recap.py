"""
Recap — free recall of the last session, many concepts in one turn.

Recap deliberately **stretches** the mode Protocol (build-guide §4/§5). A normal mode
poses one challenge for one concept and records one attempt. Recap goes the other way:
it generates over the **set of concepts the last session touched** and grades a **single**
free-recall monologue into an **attempt per concept** — the many-concepts/one-turn stretch
(orthogonal to multi-turn Socratic). Every attempt is still append-only through the engine,
so FSRS, calibration, and recognition all fire per concept exactly as elsewhere.

Because it isn't a per-concept ``RetrievalMode``, recap lives here as an orchestration —
not in the mode registry — and drives its own two-request HTTP flow. Its attempts carry
``mode="recap"`` in the log so sessions and history see them like any other.

The LLM boundary is ``_analyze_recall`` so the grader is testable without a live model.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Topic
from app.models.retrieval import Concept
from app.services.llm import call_llm
from app.services.retrieval import engine, recognition, session
from app.services.retrieval.engine import AttemptResult
from app.services.retrieval.modes import Outcome, score_to_grade

RECAP_MODE = "recap"


class NoRecapAvailable(Exception):
    """Raised when there's no prior session in scope to recap."""


@dataclass(frozen=True)
class RecapChallenge:
    """The single free-recall opener over the last session's concepts."""

    prompt: str
    topic_title: str
    concept_ids: list[str]


@dataclass(frozen=True)
class RecapConceptResult:
    """One concept's judged outcome within a recap turn, plus its recorded attempt."""

    concept: Concept
    result: AttemptResult


async def build_recap(db: AsyncSession, user_id, *, topic_id) -> RecapChallenge:
    """Open a recap for a topic: the last session's concepts, one uncued prompt.

    Raises ``NoRecapAvailable`` when the user has no prior attempts in the topic.
    The prompt names *how many* ideas to recall but never lists them — free recall is
    uncued on purpose (naming them would hand back the answer).
    """
    last = await session.last_session(db, user_id, topic_id=topic_id)
    if last is None or not last.concept_ids:
        raise NoRecapAvailable("no prior session to recap in this topic")

    topic = await db.get(Topic, topic_id)
    topic_title = topic.title if topic is not None else "your last session"
    count = len(last.concept_ids)

    prompt = (
        f"Last time you worked through **{count} idea"
        f"{'s' if count != 1 else ''}** in {topic_title}. "
        "Without looking anything up, tell me everything you remember — in your own "
        "words, in any order. Getting it out from memory is the whole point."
    )
    return RecapChallenge(prompt=prompt, topic_title=topic_title, concept_ids=list(last.concept_ids))


async def grade_recap(
    db: AsyncSession,
    user_id,
    *,
    concept_ids: list[str],
    response: Any,
    prompt: Optional[str] = None,
    predicted_confidence: Optional[float] = None,
    now: Optional[datetime] = None,
) -> list[RecapConceptResult]:
    """Grade one free-recall response against every concept → an attempt per concept.

    A concept the monologue never surfaces is a genuine miss (a lapse), not skipped —
    that's exactly the forgetting the recap is meant to expose. Each attempt is recorded
    append-only and the recognition seam fires per concept, mirroring ``/attempt``.
    """
    concepts = await _load_concepts(db, concept_ids)
    said = _extract_text(response)
    challenge = {"recap": True, "prompt": prompt, "session_size": len(concepts)}

    per_concept = {} if not said.strip() else _index_analysis(await _analyze_recall(concepts, said))

    results: list[RecapConceptResult] = []
    for idx, concept in enumerate(concepts):
        outcome = _outcome_for(said, per_concept.get(idx))
        result = await engine.record_attempt(
            db,
            user_id=user_id,
            concept_id=concept.id,
            mode=RECAP_MODE,
            outcome=outcome,
            predicted_confidence=predicted_confidence,
            challenge=challenge,
            response={"raw": said},
            now=now,
        )
        await recognition.on_attempt(
            db, attempt=result.attempt, concept=concept, learner_id=user_id
        )
        results.append(RecapConceptResult(concept=concept, result=result))
    return results


# ── grading helpers ───────────────────────────────────────────────────────────


def _outcome_for(said: str, analysis: Optional[dict]) -> Outcome:
    """Build an ``Outcome`` for one concept from its slice of the recall analysis."""
    if not said.strip() or analysis is None:
        # Blank monologue, or a concept the grader never mentioned → forgotten.
        return Outcome(
            score=0.0,
            grade="again",
            feedback="Didn't come up this time — worth another pass.",
            detail={"covered": [], "missed": []},
        )
    score = max(0.0, min(1.0, float(analysis.get("coverage", 0.0))))
    return Outcome(
        score=score,
        grade=score_to_grade(score),
        feedback=analysis.get("feedback"),
        detail={
            "covered": analysis.get("covered", []),
            "missed": analysis.get("missed", []),
        },
    )


def _index_analysis(analysis: list[dict]) -> dict[int, dict]:
    """Map the grader's per-concept rows to their 1-based ``index`` (→ 0-based)."""
    by_index: dict[int, dict] = {}
    for row in analysis:
        try:
            idx = int(row.get("index"))
        except (TypeError, ValueError):
            continue
        by_index[idx - 1] = row
    return by_index


def _extract_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return str(response.get("answer") or response.get("raw") or "")
    return ""


async def _load_concepts(db: AsyncSession, concept_ids: list[str]) -> list[Concept]:
    """Load concepts, preserving the given order (a concept may have been deleted)."""
    rows = (await db.execute(select(Concept).where(Concept.id.in_(concept_ids)))).scalars().all()
    by_id = {str(c.id): c for c in rows}
    return [by_id[cid] for cid in concept_ids if cid in by_id]


# ── LLM boundary (monkeypatched in tests) ──────────────────────────────────────


async def _analyze_recall(concepts: list[Concept], said: str) -> list[dict]:
    """Judge one free-recall monologue against the whole concept set in a single call."""
    raw = await call_llm(
        _build_prompt(concepts, said),
        task="recap_eval",
        temperature=0.3,
        max_tokens=1500,
        timeout=90.0,
    )
    return _parse(raw)


def _build_prompt(concepts: list[Concept], said: str) -> str:
    lines = []
    for i, c in enumerate(concepts, start=1):
        defn = f" — {c.definition}" if c.definition else ""
        lines.append(f"{i}. {c.text}{defn}")
    concept_block = "\n".join(lines)
    return f"""A student was asked to freely recall everything they remember from their last
study session, covering the concepts below. Judge — per concept — how much they genuinely
surfaced. Reward real understanding, not fluency or word count. A concept they never
mention is a miss (coverage 0), not an omission to smooth over.

CONCEPTS:
{concept_block}

WHAT THE STUDENT SAID:
{said}

Return ONLY a JSON object of the form:
{{
  "concepts": [
    {{
      "index": 1,                 // matches the numbered concept above
      "coverage": 0.0-1.0,        // how much of THIS concept they surfaced
      "covered": ["point they got"],
      "missed": ["point they didn't mention or got wrong"],
      "feedback": "1 short, warm, specific sentence."
    }}
  ]
}}"""


def _parse(raw: str) -> list[dict]:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("no JSON object in recap analysis response")
    data = json.loads(raw[start:end])
    concepts = data.get("concepts")
    if not isinstance(concepts, list):
        raise ValueError("recap analysis missing 'concepts' array")
    return concepts
