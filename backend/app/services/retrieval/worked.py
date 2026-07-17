"""
Worked-problem grading — the STEM self-calibration substrate (B9).

The product-map's LOCKED launch dodge for STEM (2026-07-11): you can't reliably
auto-grade a derivation, so don't try. Give a problem → the student solves on paper →
they predict how confident they are → the full worked solution is revealed → they
**self-grade** against it. Comparing your own work to a model solution *is* the learning
event, and the predicted-vs-actual gap is prime calibration data.

This module is the pure, LLM-free half of that flow:

  * ``grade_self_report`` — map a self-grade (a closed vocabulary, 1:1 onto the four FSRS
    grades) to an ``Outcome``. No model in the loop; the student is the judge.
  * ``grade_numeric``     — for problems with one right number: parse the answer, compare
    to the expected value within a tolerance, server-side. No symbolic equivalence
    (SymPy/code-exec is the deliberate post-launch upgrade — see build-guide §4/B9).

Generation lives on the mode (``QuizMode._generate_worked``); this is only the judging
logic so it's testable without a live model. The reveal-then-self-grade *ordering* is
enforced by the HTTP layer (``/reveal`` is one-shot and must precede ``/attempt``).
"""

from typing import Any, Optional

from app.services.retrieval.modes import Outcome

# Problem shapes a self-calibration topic can generate. ``worked`` is self-graded (the
# student compares their paper to the revealed solution); ``numeric`` is objective
# (one right number, checked server-side); conceptual STEM falls back to the normal
# AI-graded short-answer path and never lands here.
WORKED_TYPE = "worked"
NUMERIC_TYPE = "numeric"

# The self-grade vocabulary → (score, FSRS grade). 1:1 onto scheduler.GRADES, by design:
#   again — blank, or wrong approach entirely
#   hard  — right method, arithmetic/sign slips
#   good  — solved it
#   easy  — solved it cold, no hesitation
# Note the deliberate asymmetry with MCQ (which caps at ``good`` because guessing inflates
# ``easy``): self-grade may award ``easy`` — comparing your work to a full solution is
# honest, and the grade only ever feeds the student's *own* schedule, so there's nothing
# to win by lying (and the calibration delta exposes it anyway).
_SELF_GRADE_SCORE: dict[str, float] = {
    "again": 0.0,
    "hard": 0.4,
    "good": 0.75,
    "easy": 1.0,
}


class InvalidSelfGrade(ValueError):
    """A self-grade outside the closed vocabulary — reject, never coerce."""


def grade_self_report(self_grade: Any) -> Outcome:
    """Turn a student's self-grade into an ``Outcome`` — deterministically, no LLM.

    ``self_grade`` must be one of ``again``/``hard``/``good``/``easy``; anything else
    (free text, a typo, a number) raises :class:`InvalidSelfGrade` so the endpoint can
    return 400 rather than silently mis-scheduling the concept.
    """
    key = self_grade.strip().lower() if isinstance(self_grade, str) else self_grade
    if key not in _SELF_GRADE_SCORE:
        raise InvalidSelfGrade(
            f"self-grade must be one of {sorted(_SELF_GRADE_SCORE)}, got {self_grade!r}"
        )
    return Outcome(
        score=_SELF_GRADE_SCORE[key],
        grade=key,
        feedback=None,
        detail={"self_graded": True},
    )


def grade_numeric(
    response: Any, *, expected_value: float, tolerance: float, solution: Optional[str] = None
) -> Outcome:
    """Grade a single-number answer server-side: parse a float, compare within tolerance.

    A correct answer caps at ``good`` (like MCQ) — one right number doesn't prove the
    method, so we don't graduate the concept far out on it. An unparseable or wrong
    answer is a lapse (``again``). ``solution`` (the worked steps) rides back as feedback
    so the worked-example effect still lands *after* the student has committed an answer.
    """
    value = _parse_number(response)
    if value is None:
        return Outcome(
            score=0.0,
            grade="again",
            feedback=solution,
            detail={"numeric": True, "reason": "unparseable"},
        )
    correct = abs(value - expected_value) <= abs(tolerance)
    return Outcome(
        score=1.0 if correct else 0.0,
        grade="good" if correct else "again",
        feedback=solution,
        detail={"numeric": True, "expected": expected_value, "submitted": value},
    )


def _parse_number(response: Any) -> Optional[float]:
    """Best-effort float from a response (``"3.14"``, ``{"answer": 42}``, a bare number)."""
    if isinstance(response, (int, float)):
        return float(response)
    raw = response
    if isinstance(response, dict):
        raw = response.get("answer", response.get("raw"))
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.strip())
        except ValueError:
            return None
    return None
