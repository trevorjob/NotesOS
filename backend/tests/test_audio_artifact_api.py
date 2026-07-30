"""
AudioArtifact — the generalized audio surface replacing the per-topic AudioLesson.

Covers docs/listen-audio-plan.md Phase 0's GET/regenerate endpoints for the shared
global (owner=null), default-lens, topic-scoped artifact, plus the GET endpoint's
owner=me support for the caller's own personal artifacts. course/concept_cluster
scopes still have no generation path and are rejected with a 400.

Also pins the partial unique dedup constraint (one global artifact per scope+lens,
personal artifacts exempt) and the topic-delete cleanup (scope_ref carries no FK).
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Course, Topic, User
from app.models.course import CourseEnrollment
from app.models.knowledge import AudioArtifact, AudioScopeType, AudioLens, KnowledgeStatus, TopicKnowledge
from app.services.redis_client import redis_client
from tests.conftest import unique_phone


@pytest.fixture
def fake_queue(monkeypatch):
    """Record enqueue_job instead of touching Redis."""
    record = {"jobs": []}

    async def _enqueue(queue, payload):
        record["jobs"].append((queue, payload))
        return "job-id"

    monkeypatch.setattr(redis_client, "enqueue_job", _enqueue)
    return record


@pytest_asyncio.fixture
async def topic_ctx(db_session):
    """Factory: course + topic, enrolling ``user_id`` unless ``enrolled=False``."""

    async def _make(user_id, *, enrolled=True, knowledge_status=None):
        uid = uuid.UUID(user_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        if enrolled:
            db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topic = Topic(course_id=course.id, title="T")
        db_session.add(topic)
        await db_session.flush()

        knowledge = None
        if knowledge_status is not None:
            knowledge = TopicKnowledge(
                topic_id=topic.id,
                consolidated_note="Some note." if knowledge_status == KnowledgeStatus.COMPLETED else None,
                status=knowledge_status,
            )
            db_session.add(knowledge)
            await db_session.flush()

        await db_session.commit()
        return course, topic, knowledge

    return _make


def _global_artifact(topic, knowledge, **overrides):
    kwargs = dict(
        scope_type=AudioScopeType.TOPIC,
        scope_ref=topic.id,
        knowledge_id=knowledge.id if knowledge else None,
        lens=AudioLens.DEFAULT,
        owner_id=None,
        status=KnowledgeStatus.COMPLETED,
        audio_url="https://cdn.example/lesson.mp3",
        duration_seconds=180,
    )
    kwargs.update(overrides)
    return AudioArtifact(**kwargs)


# ── GET /api/audio/{scope_type}/{scope_ref} ──────────────────────────────────


async def test_get_audio_returns_pending_stub_when_none_generated(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _ = await topic_ctx(user["id"])

    resp = await client.get(f"/api/audio/topic/{topic.id}", headers=user["headers"])

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["id"] is None
    assert body["audio_url"] is None
    assert body["scope_type"] == "topic"
    assert body["lens"] == "default"


async def test_get_audio_returns_ready_artifact(client, register_user, topic_ctx, db_session):
    user = await register_user()
    _, topic, knowledge = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    artifact = _global_artifact(topic, knowledge)
    db_session.add(artifact)
    await db_session.commit()

    resp = await client.get(f"/api/audio/topic/{topic.id}", headers=user["headers"])

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["audio_url"] == "https://cdn.example/lesson.mp3"
    assert body["owner_id"] is None
    assert body["lens"] == "default"


async def test_get_audio_rejects_unknown_scope_type(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _ = await topic_ctx(user["id"])

    resp = await client.get(f"/api/audio/planet/{topic.id}", headers=user["headers"])

    assert resp.status_code == 400


async def test_get_audio_rejects_unknown_lens(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _ = await topic_ctx(user["id"])

    resp = await client.get(f"/api/audio/topic/{topic.id}?lens=dramatic", headers=user["headers"])

    assert resp.status_code == 400


async def test_get_audio_rejects_unknown_owner(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _ = await topic_ctx(user["id"])

    resp = await client.get(f"/api/audio/topic/{topic.id}?owner=someone_else", headers=user["headers"])

    assert resp.status_code == 400


async def test_get_audio_supports_personal_owner(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _ = await topic_ctx(user["id"])

    resp = await client.get(
        f"/api/audio/topic/{topic.id}?lens=exam_focused&owner=me", headers=user["headers"]
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["lens"] == "exam_focused"


async def test_get_audio_requires_enrollment(client, register_user, topic_ctx):
    owner = await register_user()
    outsider = await register_user()
    _, topic, _ = await topic_ctx(owner["id"], enrolled=True)

    resp = await client.get(f"/api/audio/topic/{topic.id}", headers=outsider["headers"])

    assert resp.status_code == 403


# ── POST /api/audio/{scope_type}/{scope_ref}/regenerate ─────────────────────


async def test_regenerate_requires_completed_knowledge(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.PROCESSING)

    resp = await client.post(f"/api/audio/topic/{topic.id}/regenerate", headers=user["headers"])

    assert resp.status_code == 422
    assert fake_queue["jobs"] == []


async def test_regenerate_enqueues_job_when_knowledge_ready(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, knowledge = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)

    resp = await client.post(f"/api/audio/topic/{topic.id}/regenerate", headers=user["headers"])

    assert resp.status_code == 202
    assert len(fake_queue["jobs"]) == 1
    queue_name, payload = fake_queue["jobs"][0]
    assert queue_name == "audio"
    assert payload["knowledge_id"] == str(knowledge.id)
    assert payload["topic_id"] == str(topic.id)


async def test_regenerate_rejects_non_topic_scope(client, register_user, fake_queue):
    user = await register_user()
    fake_concept_id = uuid.uuid4()

    resp = await client.post(f"/api/audio/concept/{fake_concept_id}/regenerate", headers=user["headers"])

    assert resp.status_code == 400
    assert fake_queue["jobs"] == []


# ── Partial unique dedup constraint ──────────────────────────────────────────


async def test_global_artifact_is_unique_per_scope_and_lens(db_session, register_user, topic_ctx):
    user = await register_user()
    _, topic, knowledge = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)

    db_session.add(_global_artifact(topic, knowledge))
    await db_session.commit()

    db_session.add(_global_artifact(topic, knowledge))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_personal_artifact_is_exempt_from_the_global_dedup_constraint(db_session, register_user, topic_ctx):
    """Two personal (owner_id set) artifacts for the same scope+lens don't collide with
    each other or with the global one — the partial index only covers owner_id IS NULL."""
    user = await register_user()
    _, topic, knowledge = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    uid = uuid.UUID(user["id"])

    db_session.add(_global_artifact(topic, knowledge))
    db_session.add(_global_artifact(topic, knowledge, owner_id=uid))
    db_session.add(_global_artifact(topic, knowledge, owner_id=uid))
    await db_session.commit()  # no IntegrityError

    count = (
        await db_session.execute(
            select(AudioArtifact).where(AudioArtifact.scope_ref == topic.id)
        )
    ).scalars().all()
    assert len(count) == 3


# ── Topic delete cleans up its audio artifacts (no DB-level FK on scope_ref) ─


async def test_deleting_topic_removes_its_audio_artifacts(client, db_session, register_user, topic_ctx):
    user = await register_user()
    _, topic, knowledge = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    db_session.add(_global_artifact(topic, knowledge))
    await db_session.commit()
    topic_id = topic.id

    resp = await client.delete(f"/api/topics/{topic_id}", headers=user["headers"])
    assert resp.status_code == 204

    remaining = (
        await db_session.execute(
            select(AudioArtifact).where(AudioArtifact.scope_ref == topic_id)
        )
    ).scalar_one_or_none()
    assert remaining is None
