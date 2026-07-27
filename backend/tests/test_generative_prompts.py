"""
Generative-prompt quality sweep (B13) — phase 2: the rest of the read/heard prompts.

Phase 1 fixed audio (the live complaint). Phase 2 applies invariant #12 to the remaining
*generative* surfaces, and — just as important — proves the sweep did NOT bleed into the
structured/control prompts, where determinism is the feature.

Refit here:
  - `research_generator`  — killed the mandatory 5-section skeleton (the real template offender)
                            for a material-driven overview + self-check.
  - `study_agent` tutor   — added an anti-template line (answer THIS question, not a mould).
  - `grader` encouragement — added inter-instance variety (a per-question surface, like audio).

(The `question_generator` sweep-target was retired with the v1 test system on 2026-07-26 —
v2 generates questions on demand via `QuizMode`; its case is dropped here.)

Left rigid on purpose (structured judgment — consistency IS the feature): the grading rubric and
essay grading. The guard tests below prove they still carry their deterministic scoring contract
and none of the generative markers leaked in.

LLM boundaries are monkeypatched / prompts asserted directly. The behavioural green-whens (two
real research docs differ in shape, ten encouragements don't rhyme) are live-LLM evals, out of
the deterministic suite's reach.
"""

import pytest

from app.services import research_generator as rg
from app.services.grader import grader as grader
from app.services.study_agent import StudyAgent


# ── research: the fixed section skeleton is gone ─────────────────────────────────

async def test_research_prompt_drops_fixed_section_skeleton(monkeypatch):
    captured = {}

    async def fake_call(prompt, *, task, **kwargs):
        captured["prompt"] = prompt
        return '{"research_content": "x", "key_concepts": ["a"]}'

    monkeypatch.setattr(rg, "call_llm", fake_call)
    sources = [{"title": "S", "snippet": "text", "source": "web"}]
    await rg.research_generator._synthesize_research("Topic", "", sources)

    prompt = captured["prompt"]
    # the mandatory 1..5 skeleton every doc had to fill is gone
    assert "1. **Core Concepts**" not in prompt and "2. **Historical Context**" not in prompt
    assert "no fixed skeleton to fill in" in prompt        # material decides the sections
    assert "check your own output" in prompt               # self-check
    # the JSON envelope the parser depends on is intact
    assert '"research_content"' in prompt and '"key_concepts"' in prompt


# ── tutor: answer THIS question, not a template ──────────────────────────────────

def test_tutor_prompt_has_anti_template_line():
    msgs = StudyAgent()._build_answer_messages("q", "ctx", [], {"tone": "direct"})
    system = msgs[0]["content"]
    assert "Answer THIS question, not a template" in system
    assert "shaped identically" in system
    assert "efficient and no-nonsense" in system           # persona axis still intact


# ── encouragement: inter-instance variety (the audio lesson, applied to feedback) ─

def test_encouragement_prompt_asks_for_variety():
    prompt = grader._build_encouragement_prompt(
        score=7.0, verdict="mostly_correct", what_got_right="the mechanism",
        what_to_fix="the edge case", misconception="", topic_name="Photosynthesis",
        is_voice=False, personality={"tone": "encouraging"},
    )
    assert "Vary it" in prompt
    assert "stamped from a mould" in prompt


# ── guard: the structured grading prompt stays rigid, unchanged by the sweep ─────

def test_grading_rubric_prompt_untouched_by_the_sweep():
    """Grading is structured judgment — consistency is fairness. The sweep must not loosen its
    scoring contract or bleed generative-principle language into it."""
    prompt = grader._build_grading_prompt(
        question="Q", expected="key points", student="answer",
        question_type="short_answer", is_voice=False,
    )
    assert "SCORING GUIDE" in prompt and "Return ONLY valid JSON" in prompt   # rigid contract intact
    for marker in ("vary the framing", "no fixed skeleton", "answer this question, not a template"):
        assert marker not in prompt.lower()
