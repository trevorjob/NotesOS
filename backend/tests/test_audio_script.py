"""
Generative-prompt quality sweep (B13) — phase 1: audio, the live complaint.

Users reported the audio is *repetitive*. The root is the same as B12's prose wall: an
over-prescriptive prompt (a fixed HOOK→loop→transition-menu→CLOSING scaffold) produces
mechanical, interchangeable output. This refits the audio prompt to *objective + judgment +
self-check*, kills the templated scaffold, and adds the inter-script nudge audio needs that
notes don't (each lesson is generated with no awareness of its siblings, so they all used to
open the same way).

The LLM is monkeypatched, so — like B10/B12 — these pin the *prompt contract*: the killed
template is gone, the principle + self-check + inter-script variety nudge are present, the
machine-parsed [PAUSE] token survives while the never-rendered [EMPHASIS] token is gone, and a
higher sampling temperature is used. The behavioural green-when (two real scripts don't share an
opening/skeleton) is a live-LLM eval, out of the deterministic suite's reach.

A guard test pins the sweep's boundary: the OUT-of-scope control prompt (`_classify_prompt`)
stays deterministic and free of the generative principle language.
"""

import pytest

from app.services import audio_generator as ag
from app.services import knowledge_synthesizer as ks


class _Knowledge:
    """Minimal stand-in for TopicKnowledge — only the fields the prompt reads."""
    consolidated_note = "Photosynthesis converts light to chemical energy."
    key_points = ["Chlorophyll absorbs light."]
    concepts = [{"term": "ATP", "definition": "energy currency"}]


async def _capture_audio_call(monkeypatch):
    """Run generate_script with the LLM faked; return (prompt, call_kwargs)."""
    captured = {}

    async def fake_call(prompt, *, task, **kwargs):
        captured["prompt"] = prompt
        captured["task"] = task
        captured["kwargs"] = kwargs
        return "a spoken script"

    monkeypatch.setattr(ag, "call_llm", fake_call)
    await ag.audio_generator.generate_script(_Knowledge(), topic_name="Photosynthesis")
    return captured["prompt"], captured["kwargs"], captured["task"]


# ── the templated scaffold is gone ───────────────────────────────────────────────

async def test_audio_prompt_drops_the_fixed_scaffold(monkeypatch):
    """The rigid arc/loop/transition-menu that made every script sound alike is removed."""
    prompt, _, _ = await _capture_audio_call(monkeypatch)
    assert "follow this arc" not in prompt          # no fixed HOOK→CORE→CLOSING arc
    assert "The loop per concept" not in prompt      # no numbered per-concept template
    assert "Here's where it gets interesting" not in prompt  # no prescribed transition menu


# ── objective + judgment + self-check + inter-script variety ─────────────────────

async def test_audio_prompt_is_principle_and_self_check(monkeypatch):
    prompt, _, _ = await _capture_audio_call(monkeypatch)
    assert "judgment, not a formula" in prompt        # judgment over template
    assert "no fixed arc to fill in" in prompt        # the default is explicitly killed
    assert "check your own script" in prompt          # the self-check
    assert "retrieval, not exposure" in prompt        # the objective (make it stick)


async def test_audio_prompt_has_inter_script_variety_nudge(monkeypatch):
    """The failure notes don't have: every lesson opening the same way."""
    prompt, _, _ = await _capture_audio_call(monkeypatch)
    assert "one of many lessons" in prompt
    assert "don't open two different topics the same way" in prompt.replace("’", "'")


# ── control tokens: keep the rendered one, drop the un-rendered one ───────────────

async def test_pause_token_kept_emphasis_token_dropped(monkeypatch):
    """[PAUSE] is machine-parsed by generate_audio; [EMPHASIS] was never rendered → spoken
    literally by TTS, so it's dropped as an incidental quality bug."""
    prompt, _, _ = await _capture_audio_call(monkeypatch)
    assert "[PAUSE]" in prompt
    assert "[EMPHASIS]" not in prompt


async def test_audio_uses_higher_temperature_for_variety(monkeypatch):
    prompt, kwargs, task = await _capture_audio_call(monkeypatch)
    assert task == "audio_script"
    assert kwargs.get("temperature", 0) >= 0.7   # low temp was part of the sameness


# ── guard: the OUT-of-scope control prompt stays rigid ───────────────────────────

def test_classifier_control_prompt_untouched_by_the_sweep():
    """`_classify_prompt` is structured/control — determinism is the feature. The sweep must
    not bleed generative-principle language into it or loosen its one-word contract."""
    prompt = ks.knowledge_synthesizer._classify_prompt("some sample material")
    assert "EXACTLY ONE word" in prompt and "One word only" in prompt  # rigid contract intact
    # none of the generative markers leaked in:
    for marker in ("judgment, not a formula", "check your own", "make it stick"):
        assert marker not in prompt
