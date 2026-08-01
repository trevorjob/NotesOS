"""
Teach / Protégé — explain-it mode.

The user explains the concept as if teaching a peer. Teaching forces retrieval plus
*reorganization* and gap-finding — you can't teach what you can't structure, so the
holes show up under your own hand (Learning Science Part 15). A strong explanation is
also the raw material for a note **contribution** later (the recognition loop, §7).

Conversational (design note): the "explain this" opener is one turn; a confused-classmate
persona then probes the gaps ("wait, why does that follow?") until the explanation is
complete or the student runs dry. The one-shot generate/evaluate stays for run_once / tests
/ offline — close() grades the whole dialogue, evaluate() grades a single reply, and both
share ``_grade``. The LLM judgement is isolated behind ``_judge`` for testing.
"""

import json
from typing import Any

from app.services.llm import call_llm
from app.services.retrieval import conversation
from app.services.retrieval.concepts import source_context
from app.services.retrieval.modes import (
    Challenge,
    ConversationTurn,
    ModeContext,
    Outcome,
    TurnResult,
    join_user_turns,
    score_to_grade,
)

_PERSONA = (
    "Play a curious classmate who's never seen this concept: when their explanation glosses "
    "over something or leans on a word without unpacking it, that's exactly where you ask why."
)


class TeachMode:
    """Explain a concept to a naive learner; we judge the explanation."""

    key = "teach"
    conversational = True

    async def open(self, concept, ctx: ModeContext) -> Challenge:
        prompt = (
            f"Explain **{concept.text}** as if you're teaching it to a classmate who's "
            "never seen it. Use your own words, and don't skip the parts that are hard "
            "to put into words — that's usually where it counts."
        )
        return Challenge(concept_id=str(concept.id), prompt=prompt, payload={"teach": True})

    async def generate(self, concept, ctx: ModeContext) -> Challenge:
        return await self.open(concept, ctx)  # one-shot opener == conversational opener

    async def turn(self, concept, history: list[ConversationTurn], ctx: ModeContext) -> TurnResult:
        return await conversation.decide_next_turn(
            concept, history, persona=_PERSONA, task="teach_turn", close_reason="taught_enough",
        )

    async def close(self, concept, history: list[ConversationTurn], ctx: ModeContext) -> Outcome:
        return await self._grade(concept, join_user_turns(history), ctx)

    async def evaluate(
        self, concept, challenge: Challenge, response: Any, ctx: ModeContext
    ) -> Outcome:
        explanation = response if isinstance(response, str) else (response or {}).get("answer", "")
        return await self._grade(concept, explanation, ctx)

    async def _grade(self, concept, explanation: str, ctx: ModeContext) -> Outcome:
        if not explanation.strip():
            return Outcome(score=0.0, grade="again", feedback="No explanation yet — teaching it is how it sticks.")

        result = await self._judge(concept, explanation, ctx)
        # Judge scores three axes 0..1; the overall recall score is their mean, but a
        # wrong explanation (low correctness) can't be rescued by clarity — cap on it.
        correctness = _clamp(result.get("correctness", 0.0))
        completeness = _clamp(result.get("completeness", 0.0))
        clarity = _clamp(result.get("clarity", 0.0))
        score = min(correctness, (correctness + completeness + clarity) / 3.0)
        return Outcome(
            score=score,
            grade=score_to_grade(score),
            feedback=result.get("feedback"),
            detail={
                "correctness": correctness,
                "completeness": completeness,
                "clarity": clarity,
                "confusions": result.get("confusions", []),
            },
        )

    # --- LLM boundary (overridden in tests) --------------------------------------

    async def _judge(self, concept, explanation: str, ctx: ModeContext) -> dict:
        source = await source_context(ctx.db, concept)
        raw = await call_llm(
            self._build_prompt(concept, explanation, source),
            task="teach_eval",
            temperature=0.3,
            max_tokens=700,
            timeout=60.0,
        )
        return self._parse(raw)

    # --- helpers -----------------------------------------------------------------

    def _build_prompt(self, concept, explanation: str, source: str = "") -> str:
        definition = f"\nREFERENCE: {concept.definition}" if concept.definition else ""
        source_block = (
            f"\n\nSOURCE MATERIAL (for you, not the student — use it to verify correctness "
            f"beyond the compressed reference above, and to catch a confidently wrong claim "
            f"the reference alone wouldn't expose):\n{source}"
            if source else ""
        )
        return f"""A student explained a concept as if teaching it. Judge the explanation the
way a confused classmate would: is it correct, complete, and actually clear? Reward a
real mental model over fluent-sounding filler.

CONCEPT: {concept.text}{definition}{source_block}

THE STUDENT'S EXPLANATION:
{explanation}

Return ONLY a JSON object:
{{
  "correctness": 0.0-1.0,   // is what they said accurate?
  "completeness": 0.0-1.0,  // did they cover the core of it?
  "clarity": 0.0-1.0,       // would a beginner actually follow it?
  "confusions": ["what a learner would still be unsure about", "..."],
  "feedback": "1-2 warm, specific sentences on how to teach it better."
}}"""

    def _parse(self, raw: str) -> dict:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("no JSON object in teach judgement response")
        return json.loads(raw[start:end])


def _clamp(v: Any) -> float:
    return max(0.0, min(1.0, float(v)))
