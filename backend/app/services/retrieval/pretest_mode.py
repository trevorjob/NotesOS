"""
Pretest — retrieval *before* encoding.

A question posed before the student has studied a concept (on add, or at the start of a
session). Pretesting primes encoding and breaks the fluency illusion early, and the
predicted-vs-actual gap is prime calibration data (Learning Science Parts 12, 4, 8).

Mechanically it's a quiz question, so it *reuses* ``QuizMode`` wholesale — same
generation, same MCQ/open grading. The one difference is scheduling intent: this is the
first-ever exposure, so a correct answer (often a lucky guess, before any study) must
**not** graduate the concept far into the future. We cap the grade at ``good`` — never
``easy`` — so the concept still comes back soon regardless.
"""

from dataclasses import replace
from typing import Any, Optional

from app.services.retrieval.modes import Challenge, ModeContext, Outcome
from app.services.retrieval.quiz_mode import QuizMode


class PretestMode(QuizMode):
    """A quiz question asked before studying — primes encoding, feeds calibration."""

    key = "pretest"

    async def generate(self, concept, ctx: ModeContext) -> Challenge:
        challenge = await super().generate(concept, ctx)
        # Tag it so the client can frame it as a pretest ("a guess is fine").
        return replace(challenge, payload={**challenge.payload, "pretest": True})

    async def evaluate(
        self, concept, challenge: Challenge, response: Any, ctx: ModeContext
    ) -> Outcome:
        outcome = await super().evaluate(concept, challenge, response, ctx)
        if outcome.grade == "easy":
            # Cap the upside: pre-study, don't let a correct answer push the concept out.
            outcome = replace(outcome, grade="good")
        return outcome

    def subject_weight(self, subject_type: Optional[str]) -> float:
        # Pretesting is highest-value for STEM (worked-example / applied setups); still
        # useful elsewhere (Learning Science Part 12).
        if subject_type in ("stem", "science", "math", "engineering"):
            return 1.0
        return 0.7
