"""
Recognition (B1) — the "your work was used" loop over the §11 consume substrate.

What's pinned here:
  1. Beneficiary resolution is topic-level, excludes the learner and quarantined uploads.
  2. ``on_attempt`` never delivers per-attempt (delivery moved to the batched digest).
  3. Passive consumes are recorded as ``ConsumeEvent`` rows (best-effort, always).
  4. ``pending_recognition`` aggregates active (attempts) + passive (consumes), distinct,
     excluding the contributor's own activity, windowed by ``since``.
  5. ``deliver_pending_recognition`` fires **one** batched, warmth-tuned notification and
     is gated by ``ENABLE_RECOGNITION``.

Delivery is spied (``create_and_push_notification`` patched) so no test touches Redis.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from app.config import settings
from app.models import Concept, Course, Topic, User
from app.models.consume import ConsumeEvent, ConsumeKind
from app.models.resource import Resource
from app.models.retrieval import RetrievalAttempt
from app.services.retrieval import recognition
from tests.conftest import unique_phone


def _user(tag: str) -> User:
    return User(
        email=f"{tag}_{uuid.uuid4().hex[:8]}@t.dev",
        full_name=tag.upper(),
        password_hash="x",
        phone=unique_phone(),
    )


async def _fixture(db, *, n_other_resources=1, quarantined=False, learner_also_uploads=False):
    learner = _user("l")
    contributor = _user("c")
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


# --- Beneficiary resolution (unchanged from the dormant seam) -----------------

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


async def test_on_attempt_never_delivers_per_attempt(db_session, monkeypatch):
    """on_attempt resolves beneficiaries but delivery moved to the batched digest."""
    learner, contributor, concept = await _fixture(db_session)
    calls = []

    async def _spy(db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(recognition, "create_and_push_notification", _spy)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", True)  # even enabled: no per-attempt push

    ben = await recognition.on_attempt(db_session, attempt=None, concept=concept, learner_id=learner.id)
    assert ben == [contributor.id]
    assert calls == []


# --- Passive consume substrate ------------------------------------------------

async def test_record_consume_writes_event(db_session):
    learner, contributor, concept = await _fixture(db_session)
    await recognition.record_consume(
        db_session, actor_id=learner.id, topic_id=concept.topic_id, kind=ConsumeKind.NOTE_VIEW
    )
    from sqlalchemy import select
    rows = (await db_session.execute(select(ConsumeEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].actor_id == learner.id
    assert rows[0].kind == ConsumeKind.NOTE_VIEW


# --- Aggregation --------------------------------------------------------------

async def test_pending_recognition_counts_active_and_passive(db_session):
    learner, contributor, concept = await _fixture(db_session)
    reader = _user("r")
    db_session.add(reader)
    await db_session.flush()

    # active: learner does a retrieval attempt on the contributor's topic
    db_session.add(RetrievalAttempt(user_id=learner.id, concept_id=concept.id, mode="quiz", grade="good"))
    # passive: reader reads the note
    db_session.add(ConsumeEvent(actor_id=reader.id, topic_id=concept.topic_id, kind=ConsumeKind.NOTE_VIEW))
    await db_session.flush()

    summary = await recognition.pending_recognition(
        db_session, contributor_id=contributor.id, since=datetime.utcnow() - timedelta(days=1)
    )
    assert summary.active_studiers == 1
    assert summary.passive_consumers == 1
    assert summary.total == 2


async def test_pending_recognition_excludes_self(db_session):
    learner, contributor, concept = await _fixture(db_session)
    # contributor studies + reads their OWN topic — must not recognize themselves
    db_session.add(RetrievalAttempt(user_id=contributor.id, concept_id=concept.id, mode="quiz", grade="good"))
    db_session.add(ConsumeEvent(actor_id=contributor.id, topic_id=concept.topic_id, kind=ConsumeKind.NOTE_VIEW))
    await db_session.flush()

    summary = await recognition.pending_recognition(
        db_session, contributor_id=contributor.id, since=datetime.utcnow() - timedelta(days=1)
    )
    assert summary.total == 0


async def test_pending_recognition_windowed_by_since(db_session):
    learner, contributor, concept = await _fixture(db_session)
    old = RetrievalAttempt(user_id=learner.id, concept_id=concept.id, mode="quiz", grade="good")
    old.created_at = datetime.utcnow() - timedelta(days=10)
    db_session.add(old)
    await db_session.flush()

    summary = await recognition.pending_recognition(
        db_session, contributor_id=contributor.id, since=datetime.utcnow() - timedelta(days=1)
    )
    assert summary.total == 0  # the only event predates the window


# --- Batched, warmth-tuned delivery -------------------------------------------

async def test_deliver_is_gated_by_flag(db_session, monkeypatch):
    learner, contributor, concept = await _fixture(db_session)
    db_session.add(RetrievalAttempt(user_id=learner.id, concept_id=concept.id, mode="quiz", grade="good"))
    await db_session.flush()

    calls = []
    monkeypatch.setattr(recognition, "create_and_push_notification",
                        lambda db, **k: calls.append(k))
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", False)

    out = await recognition.deliver_pending_recognition(
        db_session, contributor_id=contributor.id, since=datetime.utcnow() - timedelta(days=1)
    )
    assert out is None
    assert calls == []


async def test_deliver_fires_one_warm_notification_for_active(db_session, monkeypatch):
    learner, contributor, concept = await _fixture(db_session)
    db_session.add(RetrievalAttempt(user_id=learner.id, concept_id=concept.id, mode="quiz", grade="good"))
    await db_session.flush()

    calls = []

    async def _spy(db, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(recognition, "create_and_push_notification", _spy)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", True)

    await recognition.deliver_pending_recognition(
        db_session, contributor_id=contributor.id, since=datetime.utcnow() - timedelta(days=1)
    )
    assert len(calls) == 1  # ONE batched notification, not one-per-event
    assert calls[0]["user_id"] == contributor.id
    assert calls[0]["meta_data"]["kind"] == "recognition"
    assert calls[0]["meta_data"]["active_studiers"] == 1
    assert "working" in calls[0]["title"].lower()  # warm-active copy


async def test_deliver_noop_when_nothing_pending(db_session, monkeypatch):
    learner, contributor, concept = await _fixture(db_session)
    calls = []

    async def _spy(db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(recognition, "create_and_push_notification", _spy)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", True)

    out = await recognition.deliver_pending_recognition(
        db_session, contributor_id=contributor.id, since=datetime.utcnow() - timedelta(days=1)
    )
    assert out is None
    assert calls == []
