"""
Ramble / Talk — free-recall mode.

The user speaks (or types) freely about a concept; we judge the monologue for how
much of the concept they surfaced and where the gaps are. Free recall is a stronger
retrieval event than the cued recall a quiz question gives (Learning Science Parts 3, 9)
— there's no prompt to lean on, so producing the structure is the work.

Single-shot: one open prompt out of ``generate``, one judged ``Outcome`` out of
``evaluate`` whose ``feedback`` names the gaps. (Multi-turn Socratic follow-ups are a
later enhancement — they'd need session state the engine doesn't model.) The response
is already text here; audio→text transcription is an upstream concern shared by every
voice mode.

The LLM call lives behind ``_analyze`` so the mode is testable without a live model.
"""

import json
from typing import Any, Optional

from app.services.llm import call_llm
from app.services.retrieval.modes import Challenge, ModeContext, Outcome, score_to_grade


class RambleMode:
    """Free recall over a single concept — talk about it, we find the gaps."""

    key = "ramble"

    async def generate(self, concept, ctx: ModeContext) -> Challenge:
        prompt = (
            f"Tell me everything you understand about **{concept.text}** — "
            "in your own words, as much as you can. Don't worry about structure; "
            "just get it all out."
        )
        return Challenge(concept_id=str(concept.id), prompt=prompt, payload={"free_recall": True})

    async def evaluate(
        self, concept, challenge: Challenge, response: Any, ctx: ModeContext
    ) -> Outcome:
        said = response if isinstance(response, str) else (response or {}).get("answer", "")
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

    def subject_weight(self, subject_type: Optional[str]) -> float:
        # Output-first modes carry content-heavy and language subjects; ramble is the
        # highest-leverage mode there (Learning Science Part 12). Neutral elsewhere.
        if subject_type in ("language", "humanities", "history"):
            return 1.0
        return 0.8

    # --- LLM boundary (overridden in tests) --------------------------------------

    async def _analyze(self, concept, said: str, ctx: ModeContext) -> dict:
        raw = await call_llm(
            self._build_prompt(concept, said),
            task="ramble_eval",
            temperature=0.3,
            max_tokens=700,
            timeout=60.0,
        )
        return self._parse(raw)

    # --- helpers -----------------------------------------------------------------

    def _build_prompt(self, concept, said: str) -> str:
        definition = f"\nREFERENCE: {concept.definition}" if concept.definition else ""
        return f"""A student was asked to freely recall everything they know about a concept.
Judge how much of the concept they actually surfaced — reward genuine understanding,
not fluency or word count. Missing the core idea matters more than missing a detail.

CONCEPT: {concept.text}{definition}

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
