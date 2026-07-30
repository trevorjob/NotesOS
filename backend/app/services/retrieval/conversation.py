"""
The shared turn engine for conversational modes (teach · ramble).

A conversational mode's ``turn`` decides, after each user reply, whether to *dig* (ask one
more probing question) or *close* (the thread's exhausted, or the user has gone blank).
That decision is one LLM call over the running transcript; only the persona differs
between modes, so it lives here once. The mode owns ``open`` and ``close`` (grading); this
owns the middle.

The don't-badger rule is baked into the prompt: a blank or thin reply after a nudge closes
gracefully rather than interrogating an empty brain — the line between a study partner and
a quiz robot (design note §4).
"""

import json

from app.services.llm import call_llm
from app.services.retrieval.modes import ROLE_AI, ConversationTurn, TurnResult


def format_transcript(history: list[ConversationTurn]) -> str:
    def speaker(role: str) -> str:
        return "YOU (the study partner)" if role == ROLE_AI else "THE STUDENT"

    return "\n".join(
        f"{speaker(t.role)}: {t.text.strip()}" for t in history if t.text.strip()
    )


def _build_prompt(concept, history: list[ConversationTurn], persona: str) -> str:
    definition = f"\nREFERENCE (for you, not to read out): {concept.definition}" if concept.definition else ""
    return f"""You're a study partner in a live back-and-forth with a student about a concept.
{persona}

CONCEPT: {concept.text}{definition}

CONVERSATION SO FAR:
{format_transcript(history)}

Decide your next move:
- If there's clearly more understanding to pull out, ask ONE short, specific follow-up that
  builds on what they just said ("why does that happen?", "so then what?", "you said X — why?").
  Keep it to a sentence or two, warm and curious, never a quiz.
- If they've covered it well, or their last reply is blank / thin / they've plainly run dry,
  STOP. Don't badger an empty brain — one gentle nudge is enough, then let it go.

Return ONLY a JSON object:
{{
  "done": true or false,   // true = stop and grade what we have
  "reply": "your one follow-up question, or empty string if done"
}}"""


async def decide_next_turn(
    concept, history: list[ConversationTurn], *, persona: str, task: str,
    close_reason: str = "dug_enough",
) -> TurnResult:
    """One LLM step: dig with a follow-up, or close the bout."""
    raw = await call_llm(
        _build_prompt(concept, history, persona),
        task=task, temperature=0.4, max_tokens=200, timeout=45.0,
    )
    parsed = _parse(raw)
    if parsed.get("done") or not (parsed.get("reply") or "").strip():
        return TurnResult(closed=True, close_reason=close_reason)
    return TurnResult(closed=False, reply=parsed["reply"].strip())


def _parse(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("no JSON object in conversation turn response")
    return json.loads(raw[start:end])
