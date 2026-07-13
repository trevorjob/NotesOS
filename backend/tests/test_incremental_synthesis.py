"""
Incremental synthesis (A4) — append-merge instead of full rebuild.

The synthesizer folds only *new* (non-quarantined, unmerged) material into the
existing note; ``synthesized_at`` tracks what's already in. The LLM boundaries
(``call_llm_stream`` for the body, ``call_llm`` for metadata) are monkeypatched so
the merge logic runs without a model, and the streamed body is asserted directly.
"""

import json
import uuid

import pytest
from sqlalchemy import select

from app.models import Concept, Course, Resource, ResourceChunk, Topic, User
from app.models.knowledge import TopicKnowledge
from app.models.resource import ResourceKind, SourceType
from app.services import knowledge_synthesizer as ks
from tests.conftest import unique_phone

synth = ks.knowledge_synthesizer


# ── recorder + fixtures ─────────────────────────────────────────────────────


class _LLM:
    """Records what the synthesizer sent to each LLM boundary."""

    def __init__(self):
        self.stream_prompts: list[str] = []
        self.meta_calls = 0

    def install(self, monkeypatch, *, body: str = "Consolidated body."):
        rec = self

        async def fake_stream(prompt, *, task, **kwargs):
            rec.stream_prompts.append(prompt)
            for tok in (body,):
                yield tok

        async def fake_call(prompt, *, task, **kwargs):
            rec.meta_calls += 1
            return json.dumps(
                {"key_points": ["a fact"], "concepts": [{"term": "T", "definition": "d"}]}
            )

        monkeypatch.setattr(ks, "call_llm_stream", fake_stream)
        monkeypatch.setattr(ks, "call_llm", fake_call)
        return rec


@pytest.fixture
def llm(monkeypatch):
    return _LLM().install(monkeypatch)


async def _seed_topic(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="Cell Biology", order_index=0)
    db.add(topic)
    await db.flush()
    return user, course, topic


async def _add_resource(db, topic, user, text, *, quarantined=False, chunked=True):
    r = Resource(
        topic_id=topic.id, uploaded_by=user.id, title="r", content=text,
        resource_type=ResourceKind.TEXT, source_type=SourceType.TEXT, quarantined=quarantined,
    )
    db.add(r)
    await db.flush()
    if chunked:
        db.add(ResourceChunk(resource_id=r.id, chunk_text=text, chunk_index=0))
    await db.flush()
    return r


# ── full build ──────────────────────────────────────────────────────────────


async def test_first_synthesis_is_a_full_build(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    r1 = await _add_resource(db_session, topic, user, "ALPHA facts")
    r2 = await _add_resource(db_session, topic, user, "BETA facts")

    knowledge = await synth.synthesize(str(topic.id), db_session)

    assert knowledge.status.value == "completed"
    assert knowledge.consolidated_note == "Consolidated body."
    assert knowledge.key_points == ["a fact"]
    # Full build reads every source.
    assert "ALPHA facts" in llm.stream_prompts[-1]
    assert "BETA facts" in llm.stream_prompts[-1]
    assert "consolidating all class materials" in llm.stream_prompts[-1]
    # Both resources are now marked merged.
    await db_session.refresh(r1)
    await db_session.refresh(r2)
    assert r1.synthesized_at is not None and r2.synthesized_at is not None


async def test_empty_topic_yields_placeholder(db_session, llm):
    _user, _course, topic = await _seed_topic(db_session)
    knowledge = await synth.synthesize(str(topic.id), db_session)
    assert knowledge.status.value == "completed"
    assert knowledge.source_count == 0
    assert llm.meta_calls == 0  # never called the model


# ── incremental merge ───────────────────────────────────────────────────────


async def test_second_upload_merges_only_the_new_material(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, "ALPHA facts")
    await synth.synthesize(str(topic.id), db_session)  # full build

    r_new = await _add_resource(db_session, topic, user, "GAMMA the new fact")
    await synth.synthesize(str(topic.id), db_session)  # incremental

    prompt = llm.stream_prompts[-1]
    # Incremental prompt: base note + only the new material — not the old source text.
    assert "UPDATING an existing" in prompt
    assert "GAMMA the new fact" in prompt
    assert "ALPHA facts" not in prompt          # old source not re-read
    assert "Consolidated body." in prompt        # the existing note is the base
    await db_session.refresh(r_new)
    assert r_new.synthesized_at is not None


async def test_nothing_pending_skips_the_llm(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, "ALPHA facts")
    await synth.synthesize(str(topic.id), db_session)  # full build (1 stream, 1 meta)

    calls_before = (len(llm.stream_prompts), llm.meta_calls)
    knowledge = await synth.synthesize(str(topic.id), db_session)  # nothing new

    assert knowledge.status.value == "completed"
    assert (len(llm.stream_prompts), llm.meta_calls) == calls_before  # no LLM work


# ── quarantine gate ─────────────────────────────────────────────────────────


async def test_quarantined_resource_is_never_merged(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, "ALPHA facts")
    off = await _add_resource(db_session, topic, user, "OFFTOPIC junk", quarantined=True)

    await synth.synthesize(str(topic.id), db_session)

    assert "OFFTOPIC junk" not in llm.stream_prompts[-1]
    await db_session.refresh(off)
    assert off.synthesized_at is None  # held out, not marked merged


async def test_released_resource_merges_on_the_next_pass(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, "ALPHA facts")
    off = await _add_resource(db_session, topic, user, "RELEASED later", quarantined=True)
    await synth.synthesize(str(topic.id), db_session)  # full build over ALPHA only

    # The merge gate later releases it.
    off.quarantined = False
    await db_session.flush()
    await synth.synthesize(str(topic.id), db_session)  # incremental picks it up

    prompt = llm.stream_prompts[-1]
    assert "UPDATING an existing" in prompt
    assert "RELEASED later" in prompt
    await db_session.refresh(off)
    assert off.synthesized_at is not None


# ── force full + derivability ───────────────────────────────────────────────


async def test_force_full_re_merges_every_resource(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    r1 = await _add_resource(db_session, topic, user, "ALPHA facts")
    await synth.synthesize(str(topic.id), db_session)
    r2 = await _add_resource(db_session, topic, user, "GAMMA facts")
    await synth.synthesize(str(topic.id), db_session)  # incremental

    await synth.synthesize(str(topic.id), db_session, force_full=True)

    prompt = llm.stream_prompts[-1]
    assert "consolidating all class materials" in prompt  # a full build
    assert "ALPHA facts" in prompt and "GAMMA facts" in prompt
    await db_session.refresh(r1)
    await db_session.refresh(r2)
    assert r1.synthesized_at is not None and r2.synthesized_at is not None


async def test_what_changed_is_derivable_from_synthesized_at(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, "ALPHA facts")
    await synth.synthesize(str(topic.id), db_session)
    r_new = await _add_resource(db_session, topic, user, "GAMMA facts")
    await synth.synthesize(str(topic.id), db_session)

    # "What changed in the last synthesis" = the most-recently-stamped resource.
    rows = await db_session.execute(
        select(Resource).where(Resource.topic_id == topic.id).order_by(Resource.synthesized_at.desc())
    )
    newest = rows.scalars().first()
    assert newest.id == r_new.id


# ── streaming ───────────────────────────────────────────────────────────────


async def test_body_streams_start_deltas_end(db_session, monkeypatch):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, "ALPHA facts")
    _LLM().install(monkeypatch, body="Hello world")

    events: list[dict] = []

    async def collect(event):
        events.append(event)

    await synth.synthesize(str(topic.id), db_session, broadcast=collect)

    types = [e["type"] for e in events]
    assert types[0] == "knowledge_stream_start"
    assert types[-1] == "knowledge_stream_end"
    assert "knowledge_delta" in types
    start = next(e for e in events if e["type"] == "knowledge_stream_start")
    assert start["mode"] == "full"
    streamed = "".join(e["delta"] for e in events if e["type"] == "knowledge_delta")
    assert streamed == "Hello world"


async def test_broadcast_failure_never_fails_synthesis(db_session, llm):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, "ALPHA facts")

    async def boom(event):
        raise RuntimeError("socket down")

    knowledge = await synth.synthesize(str(topic.id), db_session, broadcast=boom)
    assert knowledge.status.value == "completed"  # a dead socket doesn't sink the note
