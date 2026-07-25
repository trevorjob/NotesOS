"""
Structure-first synthesis (B12) — the note becomes a study surface, not a comprehensive dump.

B10 taught the synthesis prompt the *math* half of "form follows content"; B12 is the
humanities half: kill the prose-wall default so an entity-attribute source (five archaeological
sites, four equipment categories) gets pulled into structure, while a genuinely narrative topic
stays prose. The load-bearing decisions are (a) *comprehensive ≠ studiable* — the two-layer
framing replaces "study ONLY this document and have everything", and (b) form-by-principle,
never a `content-type → form` mapping table.

The LLM body is monkeypatched, so — exactly like B10's suite — these pin the *prompt contract*:
the structure-first principle and the two-layer framing are present, the old comprehensive-dump
framing is gone, and B10's math/worked-example behaviour is untouched. The genuine behavioural
green-when (a real model renders the archaeology case as a table and a narrative as prose) is a
live-LLM eval, out of reach of the deterministic suite — see the build note.
"""

import pytest

from app.models.subject import SubjectFamily
from app.services import knowledge_synthesizer as ks

# Reuse the B10 harness — one LLM fake driving classify + metadata + streamed body.
from tests.test_stem_pipeline import _LLM, _add_resource, _seed

synth = ks.knowledge_synthesizer


async def _full_prompt_after_synth(db, monkeypatch, *, family: str, text: str) -> str:
    """Run a full synthesis and return the body prompt the synthesizer built."""
    llm = _LLM(family=family).install(monkeypatch)
    user, _, topic = await _seed(db)
    await _add_resource(db, topic, user, text)
    await db.commit()
    await synth.synthesize(str(topic.id), db)
    return llm.body_prompts[-1]


# ── comprehensive ≠ studiable: the two-layer reframing ───────────────────────────

async def test_full_prompt_drops_comprehensive_dump_framing(db_session, monkeypatch):
    """The instruction that *caused* the prose wall is gone."""
    prompt = await _full_prompt_after_synth(
        db_session, monkeypatch, family="HUMANITIES",
        text="Five archaeological sites in Nigeria, each with date, materials, significance.",
    )
    assert "study ONLY this document" not in prompt   # the framing that pushed exhaustive prose
    assert "have everything" not in prompt


async def test_full_prompt_carries_two_layer_source_framing(db_session, monkeypatch):
    """The note is the studiable structure; the verbatim uploads are the archive."""
    prompt = await _full_prompt_after_synth(
        db_session, monkeypatch, family="GENERAL", text="Some course material.",
    )
    assert "source layer" in prompt          # the raw uploads are the complete archive
    assert "studiable structure" in prompt   # the note is the shaped surface on top


# ── structure before prose: principle, not a mapping table ───────────────────────

async def test_full_prompt_carries_structure_before_prose_principle(db_session, monkeypatch):
    prompt = await _full_prompt_after_synth(
        db_session, monkeypatch, family="HUMANITIES",
        text="The equipment falls into four categories, each with examples.",
    )
    assert "STRUCTURE BEFORE PROSE" in prompt
    assert "AT A GLANCE" in prompt                 # (a) the objective
    assert "fallback" in prompt                    # (b) kill the prose default
    assert "connective tissue" in prompt           # (c) the self-check


async def test_full_prompt_leads_sections_with_recallable_core(db_session, monkeypatch):
    prompt = await _full_prompt_after_synth(
        db_session, monkeypatch, family="GENERAL", text="A topic.",
    )
    assert "recallable core" in prompt   # each section leads with what must be recalled


async def test_structure_principle_is_not_a_content_type_mapping(db_session, monkeypatch):
    """Guard the owner steer: forms are outcomes, never a prescriptive lookup table.

    A mapping bias ('comparison→table') is just a different bug — so the prompt must not
    hard-code one. We assert the forbidden mapping arrows are absent while the *principle*
    (form follows what the material is doing) is present."""
    prompt = await _full_prompt_after_synth(
        db_session, monkeypatch, family="GENERAL", text="A topic.",
    )
    assert "comparison→table" not in prompt and "taxonomy→list" not in prompt
    assert "what its material is actually" in prompt   # derive the shape, don't look it up


# ── failure runs both ways: narrative stays prose, don't over-structure ───────────

async def test_full_prompt_guards_against_over_structuring(db_session, monkeypatch):
    """Prose-for-flow is preserved and forcing a grid onto narrative ideas is forbidden."""
    prompt = await _full_prompt_after_synth(
        db_session, monkeypatch, family="HUMANITIES",
        text="An argument about the causes of the French Revolution, in flowing prose.",
    )
    assert "needs FLOW" in prompt                    # narrative/argument stays prose
    assert "force a table" in prompt                 # don't over-structure
    assert "same bug as under-structuring" in prompt # both-ways discipline stated


# ── B10 regression: the math half is untouched ───────────────────────────────────

async def test_b10_math_and_form_rules_unchanged(db_session, monkeypatch):
    """B12 *extends* _FORM_RULES; B10's worked-example/LaTeX behaviour must still ride every prompt."""
    prompt = await _full_prompt_after_synth(
        db_session, monkeypatch, family="STEM", text="Integrate x^2 dx = x^3/3 + C.",
    )
    assert "FORM FOLLOWS CONTENT" in prompt
    assert "LaTeX" in prompt and "$$" in prompt
    assert "worked example" in prompt
    assert "SUBJECT LEAN" in prompt and "STEM" in prompt   # the B10 lean still applies


async def test_structure_rules_ride_the_incremental_prompt_too(db_session, monkeypatch):
    """An incremental merge must keep the note studiable, not just the full build."""
    llm = _LLM(family="HUMANITIES").install(
        monkeypatch, body="## Sites\n- **Iwo Eleru** — 11,000 BP; microliths; earliest skeleton."
    )
    user, _, topic = await _seed(db_session)
    await _add_resource(db_session, topic, user, "First site set.")
    await db_session.commit()
    await synth.synthesize(str(topic.id), db_session)  # full build

    await _add_resource(db_session, topic, user, "A second site with date and finds.")
    await db_session.commit()
    await synth.synthesize(str(topic.id), db_session)  # incremental merge

    prompt = llm.body_prompts[-1]
    assert "STRUCTURE BEFORE PROSE" in prompt   # the shared rules extend into the merge path
    assert "connective tissue" in prompt
