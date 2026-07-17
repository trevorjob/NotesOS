"""
Quiz — the first retrieval mode, proving the plugin abstraction.

It reuses the existing LLM plumbing (``call_llm`` for generation, ``grader`` for
open-answer grading) but scoped to a **single concept** and shaped to the
``RetrievalMode`` interface: one question out of ``generate``, an ``Outcome`` out of
``evaluate``. The engine handles everything else.

The LLM calls live behind ``_generate_question`` / ``_grade`` so the mode is testable
without a live model — a test overrides those two and exercises the real mapping logic.
"""

import json
from typing import Any

from app.services.grader import grader
from app.services.llm import call_llm
from app.services.retrieval import worked
from app.services.retrieval.modes import Challenge, ModeContext, Outcome, score_to_grade
from app.services.retrieval.subject_profiles import GRADE_SELF_CALIBRATION

# ``score_to_grade`` now lives in ``modes.py`` (shared by every mode); re-exported here
# for backward compatibility with existing imports.
__all__ = ["QuizMode", "score_to_grade"]


class QuizMode:
    """Structured Q&A over a single concept (MCQ or short-answer)."""

    key = "quiz"

    async def generate(self, concept, ctx: ModeContext) -> Challenge:
        # STEM self-calibration (B9): the topic's profile directive — never the family
        # enum — decides whether to pose a worked problem instead of a normal question.
        # A future family that adopts self_calibration gets this for free.
        if ctx.extra.get("grading") == GRADE_SELF_CALIBRATION:
            return await self._generate_worked(concept, ctx)

        raw = await self._generate_question(concept, ctx)
        return Challenge(
            concept_id=str(concept.id),
            prompt=raw["question_text"],
            payload={
                "question_type": raw.get("question_type", "mcq"),
                "answer_options": raw.get("answer_options"),
                "correct_answer": raw.get("correct_answer"),
                "explanation": raw.get("explanation"),
            },
        )

    async def _generate_worked(self, concept, ctx: ModeContext) -> Challenge:
        """Pose a STEM problem: a worked (self-graded), numeric, or conceptual question.

        The full worked solution / expected value ride in the payload for the server to
        hold back — they're stripped from ``/next`` (``_SENSITIVE_PAYLOAD_KEYS``) exactly
        like ``correct_answer`` and only surface at ``/reveal``.
        """
        raw = await self._generate_worked_problem(concept, ctx)
        ptype = raw.get("problem_type")
        if ptype not in (worked.WORKED_TYPE, worked.NUMERIC_TYPE):
            # Conceptual STEM stays AI-graded — fall through to the normal short-answer path.
            return Challenge(
                concept_id=str(concept.id),
                prompt=raw["question_text"],
                payload={
                    "question_type": "short_answer",
                    "correct_answer": raw.get("correct_answer"),
                    "explanation": raw.get("explanation"),
                },
            )
        return Challenge(
            concept_id=str(concept.id),
            prompt=raw["question_text"],
            payload={
                "question_type": ptype,
                "worked_solution": raw.get("worked_solution"),
                "expected_value": raw.get("expected_value"),
                "tolerance": raw.get("tolerance"),
            },
        )

    async def evaluate(
        self, concept, challenge: Challenge, response: Any, ctx: ModeContext
    ) -> Outcome:
        qtype = (challenge.payload or {}).get("question_type", "mcq")

        # STEM self-calibration (B9): both branches are LLM-free.
        # ``worked`` — the student self-grades against the revealed solution.
        # ``numeric`` — one right number, compared server-side within tolerance.
        if qtype == worked.WORKED_TYPE:
            return worked.grade_self_report(response)
        if qtype == worked.NUMERIC_TYPE:
            payload = challenge.payload or {}
            return worked.grade_numeric(
                response,
                expected_value=float(payload.get("expected_value") or 0.0),
                tolerance=float(payload.get("tolerance") or 0.0),
                solution=payload.get("worked_solution"),
            )

        answer = response if isinstance(response, str) else (response or {}).get("answer", "")

        # MCQ is binary — but a right answer is "good", not "easy": guessing inflates
        # easy, and we don't want a lucky guess to push the concept far into the future.
        if qtype == "mcq":
            correct = (challenge.payload.get("correct_answer") or "").strip().lower()
            is_right = answer.strip().lower() == correct and correct != ""
            return Outcome(
                score=1.0 if is_right else 0.0,
                grade="good" if is_right else "again",
                feedback=challenge.payload.get("explanation"),
            )

        # Open answer — grade with the AI grader (0..10), normalize, bucket to a grade.
        result = await self._grade(concept, challenge, answer, ctx)
        norm = max(0.0, min(1.0, float(result.get("score", 0)) / 10.0))
        return Outcome(
            score=norm,
            grade=score_to_grade(norm),
            feedback=result.get("feedback"),
            detail={
                "encouragement": result.get("encouragement"),
                "key_points_missed": result.get("key_points_missed", []),
            },
        )

    # --- LLM boundary (overridden in tests) --------------------------------------

    async def _generate_question(self, concept, ctx: ModeContext) -> dict:
        raw = await call_llm(
            self._build_prompt(concept),
            task="question_gen",
            temperature=0.6,
            max_tokens=600,
            timeout=60.0,
        )
        return self._parse(raw)

    async def _generate_worked_problem(self, concept, ctx: ModeContext) -> dict:
        raw = await call_llm(
            self._build_worked_prompt(concept),
            task="worked_problem_gen",
            temperature=0.5,
            max_tokens=1200,
            timeout=90.0,
        )
        return self._parse(raw)

    async def _grade(self, concept, challenge: Challenge, answer: str, ctx: ModeContext) -> dict:
        return await grader.grade_answer(
            question=challenge.prompt,
            expected_answer=challenge.payload.get("correct_answer") or (concept.definition or ""),
            student_answer=answer,
            question_type=(challenge.payload or {}).get("question_type", "short_answer"),
            topic_name=concept.text,
            is_voice=bool((challenge.payload or {}).get("is_voice")),
        )

    # --- helpers -----------------------------------------------------------------

    def _build_prompt(self, concept) -> str:
        definition = f"\nDEFINITION: {concept.definition}" if concept.definition else ""
        return f"""Write ONE quiz question that tests genuine understanding of this concept.
Not a definition-recall question — a question that shows whether the student
actually understands it and could apply it.

CONCEPT: {concept.text}{definition}

Prefer "mcq" (4 plausible options, wrong ones being real misconceptions) unless the
concept is better tested by a short written answer, in which case use "short_answer".
For mcq, correct_answer must be the EXACT text of one option.
For short_answer, correct_answer is "Key points: [p1] / [p2] / [p3]".

Return ONLY a JSON object:
{{
  "question_text": "...",
  "question_type": "mcq" | "short_answer",
  "answer_options": ["A","B","C","D"] | null,
  "correct_answer": "...",
  "explanation": "1-2 sentences on why."
}}"""

    def _build_worked_prompt(self, concept) -> str:
        definition = f"\nMETHOD/DEFINITION: {concept.definition}" if concept.definition else ""
        return f"""Write ONE STEM practice problem for this concept, for a student who
learns by *solving*, not by explaining. Choose the shape that fits the concept:

- "worked"  — a multi-step problem (a derivation, proof, or procedure). The student
              solves it on paper and self-grades against a full solution. Give the
              complete step-by-step worked_solution.
- "numeric" — a problem with ONE correct number. Give expected_value (a plain number)
              and a tolerance for rounding, plus the worked_solution that reaches it.
- "conceptual" — only if the concept genuinely isn't solve-able (a definition, a
              qualitative "why"). It'll be graded as a short answer.

CONCEPT: {concept.text}{definition}

Use LaTeX for all math with $...$ inline / $$...$$ display delimiters (the client and
the handwriting transcriber both use this convention — stay consistent).

Return ONLY a JSON object:
{{
  "question_text": "the problem, in LaTeX where math appears",
  "problem_type": "worked" | "numeric" | "conceptual",
  "worked_solution": "full step-by-step solution (worked/numeric)" | null,
  "expected_value": 42.0 | null,   // numeric only, a bare number
  "tolerance": 0.01 | null,        // numeric only
  "correct_answer": "Key points: ..." | null,   // conceptual only
  "explanation": "1-2 sentences" | null          // conceptual only
}}"""

    def _parse(self, raw: str) -> dict:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("no JSON object in question response")
        return json.loads(raw[start:end])
