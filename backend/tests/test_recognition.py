"""
Recognition seam — the dormant hook for the recognition loop.

Two things to pin: (1) beneficiary resolution is topic-level, excludes the learner and
quarantined uploads; (2) delivery is gated — nothing is sent when ``ENABLE_RECOGNITION``
is off (the default), and an aggregate notification per contributor when it's on.

Delivery is spied (``create_and_push_notification`` patched) so the test doesn't touch
Redis.
"""

import uuid

import pytest

from app.config import settings
from app.models import Concept, Course, Topic, User
from app.models.resource import Resource
from app.services.retrieval import recognition
from tests.conftest import unique_phone


async def _fixture(db, *, n_other_resources=1, quarantined=False, learner_also_uploads=False):
    learner = User(email=f"l_{uuid.uuid4().hex[:8]}@t.dev", full_name="L", password_hash="x", phone=unique_phone())
    contributor = User(email=f"c_{uuid.uuid4().hex[:8]}@t.dev", full_name="C", password_hash="x", phone=unique_phone())
    db.add_all([learner, contributor])
    await db.flush()
    course = Course(code="C1", name="C", created_by=contributor.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="T")
    db.add(topic)
    await db.flush()

    for _ in range(n_other_resources):
        db.add(Resource(
            topic_id=topic.id, uploaded_by=contributor.id, content="notes",
            quarantined=quarantined,
        ))
    if learner_also_uploads:
        db.add(Resource(topic_id=topic.id, uploaded_by=learner.id, content="my notes"))
    concept = Concept(topic_id=topic.id, course_id=course.id, text="X")
    db.add(concept)
    await db.flush()
    return learner, contributor, concept


async def test_resolves_other_contributor(db_session):
    learner, contributor, concept = await _fixture(db_session)
    ben = await recognition.resolve_beneficiaries(
        db_session, topic_id=concept.topic_id, learner_id=learner.id
    )
    assert ben == [contributor.id]


async def test_excludes_learners_own_upload(db_session):
    learner, contributor, concept = await _fixture(db_session, n_other_resources=0, learner_also_uploads=True)
    ben = await recognition.resolve_beneficiaries(
        db_session, topic_id=concept.topic_id, learner_id=learner.id
    )
    assert ben == []


async def test_excludes_quarantined_uploads(db_session):
    learner, contributor, concept = await _fixture(db_session, quarantined=True)
    ben = await recognition.resolve_beneficiaries(
        db_session, topic_id=concept.topic_id, learner_id=learner.id
    )
    assert ben == []


async def test_dormant_by_default_does_not_deliver(db_session, monkeypatch):
    learner, contributor, concept = await _fixture(db_session)
    calls = []
    monkeypatch.setattr(recognition, "create_and_push_notification",
                        lambda *a, **k: calls.append(k) or _async_none())
    assert settings.ENABLE_RECOGNITION is False
    ben = await recognition.on_attempt(db_session, attempt=None, concept=concept, learner_id=learner.id)
    assert ben == [contributor.id]   # resolved even while dormant
    assert calls == []               # but nothing delivered


async def test_delivers_when_enabled(db_session, monkeypatch):
    learner, contributor, concept = await _fixture(db_session)
    calls = []

    async def _spy(db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(recognition, "create_and_push_notification", _spy)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", True)

    ben = await recognition.on_attempt(db_session, attempt=None, concept=concept, learner_id=learner.id)
    assert ben == [contributor.id]
    assert len(calls) == 1
    assert calls[0]["user_id"] == contributor.id
    assert calls[0]["meta_data"]["kind"] == "recognition"


def _async_none():
    async def _n():
        return None
    return _n()
