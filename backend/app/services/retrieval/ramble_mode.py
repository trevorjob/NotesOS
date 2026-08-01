"""
Ramble / Talk — free-recall mode.

The user speaks (or types) freely about a concept; we judge the monologue for how
much of the concept they surfaced and where the gaps are. Free recall is a stronger
retrieval event than the cued recall a quiz question gives (Learning Science Parts 3, 9)
— there's no prompt to lean on, so producing the structure is the work.

Conversational (design note): the free-recall opener is one turn, but ramble is a *hybrid*
— the user dumps, and a curious-friend persona digs into whatever thread has more in it
("why does that happen? then what?"), stopping when the well runs dry (don't badger). The
one-shot generate/evaluate stays for run_once / tests / offline — close() grades the whole
dump-and-dig, evaluate() grades a single dump, and both share ``_grade``.

The LLM call lives behind ``_analyze`` so the mode is testable without a live model.
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
    "Play a genuinely interested friend pulling the thread: latch onto whatever they just "
    "said that has more underneath it and ask them to go deeper — mechanisms, consequences, why."
)


class RambleMode:
    """Free recall over a single concept — talk about it, we find the gaps."""

    key = "ramble"
    conversational = True

    async def open(self, concept, ctx: ModeContext) -> Challenge:
        prompt = (
            f"Tell me everything you understand about **{concept.text}** — "
            "in your own words, as much as you can. Don't worry about structure; "
            "just get it all out."
        )
        return Challenge(concept_id=str(concept.id), prompt=prompt, payload={"free_recall": True})

    async def generate(self, concept, ctx: ModeContext) -> Challenge:
        return await self.open(concept, ctx)  # one-shot opener == conversational opener

    async def turn(self, concept, history: list[ConversationTurn], ctx: ModeContext) -> TurnResult:
        return await conversation.decide_next_turn(
            concept, history, persona=_PERSONA, task="ramble_turn", close_reason="ran_dry",
        )

    async def close(self, concept, history: list[ConversationTurn], ctx: ModeContext) -> Outcome:
        return await self._grade(concept, join_user_turns(history), ctx)

    async def evaluate(
        self, concept, challenge: Challenge, response: Any, ctx: ModeContext
    ) -> Outcome:
        said = response if isinstance(response, str) else (response or {}).get("answer", "")
        return await self._grade(concept, said, ctx)

    async def _grade(self, concept, said: str, ctx: ModeContext) -> Outcome:
        if not said.strip():
            # Nothing recalled — a blank is a lapse, not a zero to be graded around.
            return Outcome(score=0.0, grade="again", feedback="Nothing came out this time — that's the gap to close.")

        result = await self._analyze(concept, said, ctx)
        score = max(0.0, min(1.0, float(result.get("coverage", 0.0))))
        return Outcome(
            score=score,
            grade=score_to_grade(score),
            feedback=result.get("feedback"),
            detail={
                "covered": result.get("covered", []),
                "missed": result.get("missed", []),
            },
        )

    # --- LLM boundary (overridden in tests) --------------------------------------

    async def _analyze(self, concept, said: str, ctx: ModeContext) -> dict:
        source = await source_context(ctx.db, concept)
        raw = await call_llm(
            self._build_prompt(concept, said, source),
            task="ramble_eval",
            temperature=0.3,
            max_tokens=700,
            timeout=60.0,
        )
        return self._parse(raw)

    # --- helpers -----------------------------------------------------------------

    def _build_prompt(self, concept, said: str, source: str = "") -> str:
        definition = f"\nREFERENCE: {concept.definition}" if concept.definition else ""
        source_block = (
            f"\n\nSOURCE MATERIAL (for you, not the student — use it to judge accurately, "
            f"including crediting things they said that are correct but weren't in the "
            f"compressed reference above):\n{source}"
            if source else ""
        )
        return f"""A student was asked to freely recall everything they know about a concept.
Judge how much of the concept they actually surfaced — reward genuine understanding,
not fluency or word count. Missing the core idea matters more than missing a detail.

CONCEPT: {concept.text}{definition}{source_block}

WHAT THE STUDENT SAID:
{said}

Return ONLY a JSON object:
{{
  "coverage": 0.0-1.0,          // how much of the concept they genuinely surfaced
  "covered": ["point they got", "..."],
  "missed": ["point they didn't mention or got wrong", "..."],
  "feedback": "1-2 warm, specific sentences naming what to revisit."
}}"""

    def _parse(self, raw: str) -> dict:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("no JSON object in ramble analysis response")
        return json.loads(raw[start:end])
