"""
Subject-family inference at synthesis (B4).

The synthesizer's metadata pass emits a ``subject_family``; synthesis writes it onto
the topic — unless a user has overridden it, in which case re-synthesis leaves the
manual choice alone. An unrecognised / missing family degrades to GENERAL.
"""

import json
import uuid

import pytest
from sqlalchemy import select

from app.models import Concept, Course, Resource, ResourceChunk, Topic, User
from app.models.resource import ResourceKind, SourceType
from app.models.subject import SubjectFamily
from app.services import knowledge_synthesizer as ks
from tests.conftest import unique_phone

synth = ks.knowledge_synthesizer


def _install_llm(monkeypatch, *, family: str | None, body: str = "Body."):
    """Stub both LLM boundaries; the metadata call returns the given subject_family."""
    async def fake_stream(prompt, *, task, **kwargs):
        yield body

    async def fake_call(prompt, *, task, **kwargs):
        meta = {"key_points": ["k"], "concepts": [{"term": "T", "definition": "d"}]}
        if family is not None:
            meta["subject_family"] = family
        return json.dumps(meta)

    monkeypatch.setattr(ks, "call_llm_stream", fake_stream)
    monkeypatch.setattr(ks, "call_llm", fake_call)


async def _seed(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="Thermodynamics", order_index=0)
    db.add(topic)
    await db.flush()
    r = Resource(
        topic_id=topic.id, uploaded_by=user.id, title="r", content="entropy",
        resource_type=ResourceKind.TEXT, source_type=SourceType.TEXT,
    )
    db.add(r)
    await db.flush()
    db.add(ResourceChunk(resource_id=r.id, chunk_text="entropy and heat", chunk_index=0))
    await db.flush()
    return topic


async def _reload(db, topic_id) -> Topic:
    return await db.scalar(select(Topic).where(Topic.id == topic_id))


async def test_synthesis_infers_and_stores_the_family(db_session, monkeypatch):
    _install_llm(monkeypatch, family="STEM")
    topic = await _seed(db_session)

    await synth.synthesize(str(topic.id), db_session)

    reloaded = await _reload(db_session, topic.id)
    assert reloaded.subject_family == SubjectFamily.STEM
    assert reloaded.subject_family_overridden is False


async def test_unknown_family_degrades_to_general(db_session, monkeypatch):
    _install_llm(monkeypatch, family="astrology")  # not a real family
    topic = await _seed(db_session)

    await synth.synthesize(str(topic.id), db_session)

    assert (await _reload(db_session, topic.id)).subject_family == SubjectFamily.GENERAL


async def test_missing_family_degrades_to_general(db_session, monkeypatch):
    _install_llm(monkeypatch, family=None)  # metadata omits it entirely
    topic = await _seed(db_session)

    await synth.synthesize(str(topic.id), db_session)

    assert (await _reload(db_session, topic.id)).subject_family == SubjectFamily.GENERAL


async def test_override_is_never_clobbered_by_resynthesis(db_session, monkeypatch):
    _install_llm(monkeypatch, family="STEM")
    topic = await _seed(db_session)
    # User has pinned it to HUMANITIES.
    topic.subject_family = SubjectFamily.HUMANITIES
    topic.subject_family_overridden = True
    await db_session.flush()

    await synth.synthesize(str(topic.id), db_session, force_full=True)

    reloaded = await _reload(db_session, topic.id)
    assert reloaded.subject_family == SubjectFamily.HUMANITIES  # inference did NOT win
    assert reloaded.subject_family_overridden is True
