"""
STEM front-of-pipeline (B10) — the note + the tutor go subject-native.

The load-bearing decision: **family is a prior, not a gate.** So this pins two things at
once — that *every* note prompt now carries worked-example/math vocabulary regardless of
family (a GENERAL note can render its one derivation; a prose topic stays prose), and that
the family only adds a one-line *lean* on top, classified **before** the body is written and
never overriding a user's manual choice. The tutor gets the same lean as a separate axis
from persona. LLM boundaries are monkeypatched; the prompts are asserted directly.
"""

import json
import uuid

import pytest
from sqlalchemy import select

from app.models import Course, Resource, ResourceChunk, Topic, User
from app.models.resource import ResourceKind, SourceType
from app.models.subject import SubjectFamily
from app.services import knowledge_synthesizer as ks
from app.services.study_agent import StudyAgent
from tests.conftest import unique_phone

synth = ks.knowledge_synthesizer


class _LLM:
    """Drives the synthesizer's two `call_llm` uses (classify + metadata) and the streamed body."""

    def __init__(self, family: str = "GENERAL"):
        self.family = family
        self.body_prompts: list[str] = []
        self.classify_prompts: list[str] = []

    def install(self, monkeypatch, *, body: str = "Consolidated body."):
        async def fake_stream(prompt, *, task, **kwargs):
            self.body_prompts.append(prompt)
            yield body

        async def fake_call(prompt, *, task, **kwargs):
            if task == "subject_classify":
                self.classify_prompts.append(prompt)
                return self.family
            return json.dumps({"key_points": ["a fact"], "concepts": [{"term": "T", "definition": "d"}]})

        monkeypatch.setattr(ks, "call_llm_stream", fake_stream)
        monkeypatch.setattr(ks, "call_llm", fake_call)
        return self


async def _seed(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code=f"C{uuid.uuid4().hex[:4]}", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="Calculus", order_index=0)
    db.add(topic)
    await db.flush()
    return user, course, topic


async def _add_resource(db, topic, user, text):
    r = Resource(
        topic_id=topic.id, uploaded_by=user.id, title="r", content=text,
        resource_type=ResourceKind.TEXT, source_type=SourceType.TEXT,
    )
    db.add(r)
    await db.flush()
    db.add(ResourceChunk(resource_id=r.id, chunk_text=text, chunk_index=0))
    await db.flush()
    return r


# ── content picks form: vocabulary on every note; lean only on top ───────────────

async def test_stem_note_prompt_carries_form_rules_and_lean(db_session, monkeypatch):
    llm = _LLM(family="STEM").install(monkeypatch)
    user, _, topic = await _seed(db_session)
    await _add_resource(db_session, topic, user, "Integrate x^2 dx = x^3/3 + C.")
    await db_session.commit()

    await synth.synthesize(str(topic.id), db_session)

    prompt = llm.body_prompts[-1]
    assert "FORM FOLLOWS CONTENT" in prompt          # the math/worked-example vocabulary the prompt lacked
    assert "LaTeX" in prompt and "$$" in prompt
    assert "SUBJECT LEAN" in prompt and "STEM" in prompt  # the one-line prior on top
    await db_session.refresh(topic)
    assert topic.subject_family == SubjectFamily.STEM     # classified BEFORE the body


async def test_general_note_gets_form_rules_but_no_lean(db_session, monkeypatch):
    """Proof it's content-driven, not gated: a GENERAL note can still render a calculation,
    and no family lean is imposed."""
    llm = _LLM(family="GENERAL").install(monkeypatch)
    user, _, topic = await _seed(db_session)
    await _add_resource(db_session, topic, user, "Elasticity = %ΔQ / %ΔP; a worked demand example.")
    await db_session.commit()

    await synth.synthesize(str(topic.id), db_session)

    prompt = llm.body_prompts[-1]
    assert "FORM FOLLOWS CONTENT" in prompt   # the one econ derivation can be rendered as math
    assert "SUBJECT LEAN" not in prompt       # no lean/gate — content alone decides the shape


async def test_prose_family_lean_is_prose(db_session, monkeypatch):
    llm = _LLM(family="HUMANITIES").install(monkeypatch)
    user, _, topic = await _seed(db_session)
    await _add_resource(db_session, topic, user, "The causes of the French Revolution were...")
    await db_session.commit()

    await synth.synthesize(str(topic.id), db_session)
    prompt = llm.body_prompts[-1]
    assert "expect mostly prose" in prompt
    assert "FORM FOLLOWS CONTENT" in prompt   # still math-capable if the material demanded it


# ── classification: early, override-locked, no flip-flop ─────────────────────────

async def test_user_override_skips_classification_and_wins(db_session, monkeypatch):
    llm = _LLM(family="STEM").install(monkeypatch)  # the classifier WOULD say STEM
    user, _, topic = await _seed(db_session)
    topic.subject_family = SubjectFamily.HUMANITIES
    topic.subject_family_overridden = True
    await _add_resource(db_session, topic, user, "Some material.")
    await db_session.commit()

    await synth.synthesize(str(topic.id), db_session)

    assert llm.classify_prompts == []          # the override skips the LLM entirely
    await db_session.refresh(topic)
    assert topic.subject_family == SubjectFamily.HUMANITIES  # the manual choice held
    assert "expect mostly prose" in llm.body_prompts[-1]     # and drove the lean


async def test_incremental_keeps_classified_family_no_flip_flop(db_session, monkeypatch):
    llm = _LLM(family="STEM").install(monkeypatch)
    user, _, topic = await _seed(db_session)
    await _add_resource(db_session, topic, user, "Derivative rules.")
    await db_session.commit()
    await synth.synthesize(str(topic.id), db_session)  # full build → STEM
    await db_session.refresh(topic)
    assert topic.subject_family == SubjectFamily.STEM

    llm.family = "GENERAL"  # a later partial chunk would classify differently
    await _add_resource(db_session, topic, user, "A table of values.")
    await db_session.commit()
    await synth.synthesize(str(topic.id), db_session)  # incremental → keeps STEM

    await db_session.refresh(topic)
    assert topic.subject_family == SubjectFamily.STEM
    assert len(llm.classify_prompts) == 1  # only the full build classified; incremental didn't re-run it


async def test_incremental_prompt_protects_worked_examples(db_session, monkeypatch):
    llm = _LLM(family="STEM").install(monkeypatch, body="## Worked Example\n1. step one\n2. step two")
    user, _, topic = await _seed(db_session)
    await _add_resource(db_session, topic, user, "First problem set.")
    await db_session.commit()
    await synth.synthesize(str(topic.id), db_session)  # full → note holds a worked example

    await _add_resource(db_session, topic, user, "Second problem set.")
    await db_session.commit()
    await synth.synthesize(str(topic.id), db_session)  # incremental merge

    prompt = llm.body_prompts[-1]
    assert "Preserve existing worked examples" in prompt   # the merge must not tighten it away
    assert "EXISTING NOTE" in prompt and "Worked Example" in prompt  # base note fed in for preservation


async def test_chatty_classifier_reply_is_still_parsed(db_session, monkeypatch):
    llm = _LLM(family="I'd say this is STEM material.").install(monkeypatch)
    user, _, topic = await _seed(db_session)
    await _add_resource(db_session, topic, user, "Newton's second law.")
    await db_session.commit()

    await synth.synthesize(str(topic.id), db_session)
    await db_session.refresh(topic)
    assert topic.subject_family == SubjectFamily.STEM  # token extracted from a wordy reply


# ── tutor: subject shape as an axis orthogonal to persona ────────────────────────

def test_tutor_injects_subject_shape_when_directed():
    msgs = StudyAgent()._build_answer_messages(
        "q", "ctx", [], {"tone": "direct"}, subject_directive="WORK THE EXAMPLE step by step."
    )
    system = msgs[0]["content"]
    assert "SUBJECT SHAPE" in system and "WORK THE EXAMPLE" in system
    assert "efficient and no-nonsense" in system  # persona axis still applied alongside it


def test_tutor_prompt_unchanged_without_directive():
    msgs = StudyAgent()._build_answer_messages("q", "ctx", [], None)
    assert "SUBJECT SHAPE" not in msgs[0]["content"]


async def test_subject_directive_works_the_math_on_a_stem_topic(db_session):
    user, _, topic = await _seed(db_session)
    topic.subject_family = SubjectFamily.STEM
    await db_session.commit()

    directive = await StudyAgent()._subject_directive(db_session, str(topic.id))
    assert directive and "LaTeX" in directive and "WORK THE" in directive


async def test_subject_directive_is_none_on_a_prose_topic(db_session):
    user, _, topic = await _seed(db_session)
    topic.subject_family = SubjectFamily.HUMANITIES
    await db_session.commit()
    assert await StudyAgent()._subject_directive(db_session, str(topic.id)) is None


async def test_subject_directive_is_none_for_course_wide_chat(db_session):
    # No topic → neutral: course-wide chat isn't shaped by any one topic's family.
    assert await StudyAgent()._subject_directive(db_session, None) is None
