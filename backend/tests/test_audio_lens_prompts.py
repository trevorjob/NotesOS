"""
Personal-request additions to the audio script prompt (docs/listen-audio-plan.md Phase 1):
lens directives, concept-scope focus, and the user's own free-text instruction.

These are layered onto the base prompt pinned by test_audio_script.py as additive
directives, never a template swap — the guard test below confirms the default lens with
no concept/instruction is byte-identical to that base prompt.
"""

from app.models.knowledge import AudioLens
from app.services import audio_generator as ag


class _Knowledge:
    consolidated_note = "Photosynthesis converts light to chemical energy."
    key_points = ["Chlorophyll absorbs light."]
    concepts = [{"term": "ATP", "definition": "energy currency"}]


async def _generate(monkeypatch, **kwargs):
    captured = {}

    async def fake_call(prompt, *, task, **call_kwargs):
        captured["prompt"] = prompt
        return "a spoken script"

    monkeypatch.setattr(ag, "call_llm", fake_call)
    await ag.audio_generator.generate_script(_Knowledge(), topic_name="Photosynthesis", **kwargs)
    return captured["prompt"]


# ── the default lens is untouched (regression guard) ─────────────────────────────

async def test_default_lens_with_no_extras_matches_the_base_prompt(monkeypatch):
    default_prompt = await _generate(monkeypatch)
    explicit_default_prompt = await _generate(monkeypatch, lens=AudioLens.DEFAULT, concept_focus=None, instruction=None)
    assert default_prompt == explicit_default_prompt
    assert "LENS —" not in default_prompt
    assert "SCOPE — ONE CONCEPT" not in default_prompt
    assert "WHAT THE LISTENER SPECIFICALLY ASKED FOR" not in default_prompt


# ── lens directives ───────────────────────────────────────────────────────────────

async def test_exam_focused_lens_adds_its_directive(monkeypatch):
    prompt = await _generate(monkeypatch, lens=AudioLens.EXAM_FOCUSED)
    assert "LENS — EXAM-FOCUSED" in prompt
    assert "reviewing for an exam" in prompt


async def test_slower_lens_adds_its_directive(monkeypatch):
    prompt = await _generate(monkeypatch, lens=AudioLens.SLOWER)
    assert "LENS — SLOWER PACE" in prompt


async def test_worked_example_lens_adds_its_directive(monkeypatch):
    prompt = await _generate(monkeypatch, lens=AudioLens.WORKED_EXAMPLE)
    assert "LENS — WORKED EXAMPLE" in prompt
    assert "Narrate an actual worked example" in prompt


async def test_only_the_requested_lens_directive_is_present(monkeypatch):
    """Lens directives don't leak into each other's prompts."""
    prompt = await _generate(monkeypatch, lens=AudioLens.SLOWER)
    assert "LENS — EXAM-FOCUSED" not in prompt
    assert "LENS — WORKED EXAMPLE" not in prompt


# ── concept-scope focus ───────────────────────────────────────────────────────────

async def test_concept_focus_narrows_the_prompt(monkeypatch):
    prompt = await _generate(
        monkeypatch, concept_focus={"term": "ATP", "definition": "energy currency"}
    )
    assert "SCOPE — ONE CONCEPT" in prompt
    assert "ATP — energy currency" in prompt


async def test_concept_focus_without_definition_still_names_the_term(monkeypatch):
    prompt = await _generate(monkeypatch, concept_focus={"term": "Osmosis", "definition": None})
    assert "Osmosis" in prompt
    assert "SCOPE — ONE CONCEPT" in prompt


# ── user instruction ──────────────────────────────────────────────────────────────

async def test_instruction_is_woven_in_as_a_directive(monkeypatch):
    prompt = await _generate(
        monkeypatch, lens=AudioLens.USER_INSTRUCTION, instruction="Focus on why plants need light at all"
    )
    assert "WHAT THE LISTENER SPECIFICALLY ASKED FOR" in prompt
    assert "Focus on why plants need light at all" in prompt


async def test_no_instruction_means_no_instruction_section(monkeypatch):
    prompt = await _generate(monkeypatch)
    assert "WHAT THE LISTENER SPECIFICALLY ASKED FOR" not in prompt


# ── remediation (Phase 2) ──────────────────────────────────────────────────────────

async def test_remediation_grounds_itself_in_the_actual_wrong_answers(monkeypatch):
    prompt = await _generate(
        monkeypatch,
        lens=AudioLens.REMEDIATION,
        wrong_answers=[{"question": "What does ATP do?", "your_answer": "stores fat"}],
    )
    assert "LENS — REMEDIATION" in prompt
    assert "What does ATP do?" in prompt
    assert "stores fat" in prompt
    assert "Don't generically re-explain" in prompt


async def test_remediation_with_multiple_wrong_answers_lists_them_all(monkeypatch):
    prompt = await _generate(
        monkeypatch,
        lens=AudioLens.REMEDIATION,
        wrong_answers=[
            {"question": "Q1", "your_answer": "A1"},
            {"question": "Q2", "your_answer": "A2"},
        ],
    )
    assert "Q1" in prompt and "A1" in prompt
    assert "Q2" in prompt and "A2" in prompt


async def test_remediation_falls_back_gracefully_with_no_wrong_answers(monkeypatch):
    """The attempt log is external — if nothing usable turns up, still generate a
    reasonable remediation lesson rather than crashing or silently using the default."""
    prompt = await _generate(monkeypatch, lens=AudioLens.REMEDIATION, wrong_answers=None)
    assert "LENS — REMEDIATION" in prompt
    assert "struggled with this concept before" in prompt


async def test_remediation_lens_does_not_leak_into_other_lens_prompts(monkeypatch):
    prompt = await _generate(monkeypatch, lens=AudioLens.EXAM_FOCUSED)
    assert "LENS — REMEDIATION" not in prompt
