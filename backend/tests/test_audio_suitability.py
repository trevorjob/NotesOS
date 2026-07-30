"""
The calc-heavy modality gate (docs/listen-audio-plan.md Phase 3).

STEM's low audio_suitability withholds the generic "explainer" lenses (default via
regenerate, exam_focused, slower) — narration can't carry symbol-heavy material the
way it carries prose. worked_example (narrates solved-problem steps) and the personal
user_instruction/remediation lenses are never gated; the caller explicitly asked for
those. Also covers the worker-side backstop that skips auto-generating a global
default for an unsuitable topic, and the audio_suitable flag surfaced via GET.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Concept, Course, Topic
from app.models.course import CourseEnrollment
from app.models.knowledge import AudioArtifact, AudioScopeType, KnowledgeStatus, TopicKnowledge
from app.models.subject import SubjectFamily
from app.services.redis_client import redis_client
from app.services.retrieval.subject_profiles import is_audio_suitable
from app.workers import audio_worker


def test_stem_is_not_audio_suitable():
    assert is_audio_suitable(SubjectFamily.STEM) is False


def test_humanities_is_audio_suitable():
    assert is_audio_suitable(SubjectFamily.HUMANITIES) is True


def test_general_is_audio_suitable():
    assert is_audio_suitable(SubjectFamily.GENERAL) is True


@pytest_asyncio.fixture
async def worker_db(monkeypatch, session_factory):
    """Point the worker's own session-maker at the test engine — otherwise its
    internal commits run on a separate connection tied to a different event loop."""
    monkeypatch.setattr(audio_worker, "AsyncSessionLocal", session_factory)


@pytest.fixture
def fake_queue(monkeypatch):
    record = {"jobs": []}

    async def _enqueue(queue, payload):
        record["jobs"].append((queue, payload))
        return "job-id"

    monkeypatch.setattr(redis_client, "enqueue_job", _enqueue)
    return record


@pytest_asyncio.fixture
async def topic_ctx(db_session):
    """Factory: course + topic (+ optional concept) with a given subject_family."""

    async def _make(
        user_id,
        *,
        subject_family=SubjectFamily.STEM,
        knowledge_status=KnowledgeStatus.COMPLETED,
        with_concept=False,
    ):
        uid = uuid.UUID(user_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topic = Topic(course_id=course.id, title="T", subject_family=subject_family)
        db_session.add(topic)
        await db_session.flush()

        knowledge = TopicKnowledge(
            topic_id=topic.id,
            consolidated_note="Some note." if knowledge_status == KnowledgeStatus.COMPLETED else None,
            status=knowledge_status,
        )
        db_session.add(knowledge)
        await db_session.flush()

        concept = None
        if with_concept:
            concept = Concept(
                topic_id=topic.id, course_id=course.id, text="Integral", definition="area under curve"
            )
            db_session.add(concept)
            await db_session.flush()

        await db_session.commit()
        return course, topic, knowledge, concept

    return _make


# ── GET /api/audio/{scope_type}/{scope_ref} — audio_suitable flag ───────────────


async def test_get_audio_flags_stem_topic_as_unsuitable(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM)

    resp = await client.get(f"/api/audio/topic/{topic.id}", headers=user["headers"])

    assert resp.status_code == 200
    assert resp.json()["audio_suitable"] is False


async def test_get_audio_flags_humanities_topic_as_suitable(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.HUMANITIES)

    resp = await client.get(f"/api/audio/topic/{topic.id}", headers=user["headers"])

    assert resp.status_code == 200
    assert resp.json()["audio_suitable"] is True


async def test_get_audio_flags_stem_concept_as_unsuitable(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _, concept = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM, with_concept=True)

    resp = await client.get(
        f"/api/audio/concept/{concept.id}?lens=user_instruction&owner=me", headers=user["headers"]
    )

    assert resp.status_code == 200
    assert resp.json()["audio_suitable"] is False


# ── POST /api/audio/{scope_type}/{scope_ref}/regenerate ─────────────────────────


async def test_regenerate_rejects_stem_topic(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM)

    resp = await client.post(f"/api/audio/topic/{topic.id}/regenerate", headers=user["headers"])

    assert resp.status_code == 422
    assert fake_queue["jobs"] == []


async def test_regenerate_allows_humanities_topic(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.HUMANITIES)

    resp = await client.post(f"/api/audio/topic/{topic.id}/regenerate", headers=user["headers"])

    assert resp.status_code == 202
    assert len(fake_queue["jobs"]) == 1


# ── POST /api/audio/request ──────────────────────────────────────────────────────


async def test_request_rejects_exam_focused_for_stem_topic(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM)

    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "exam_focused"},
        headers=user["headers"],
    )

    assert resp.status_code == 422
    assert fake_queue["jobs"] == []


async def test_request_rejects_slower_for_stem_concept(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, concept = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM, with_concept=True)

    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "concept", "scope_ref": str(concept.id), "lens": "slower"},
        headers=user["headers"],
    )

    assert resp.status_code == 422
    assert fake_queue["jobs"] == []


async def test_request_allows_worked_example_for_stem_topic(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM)

    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "worked_example"},
        headers=user["headers"],
    )

    assert resp.status_code == 202
    assert len(fake_queue["jobs"]) == 1


async def test_request_allows_user_instruction_for_stem_concept(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, concept = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM, with_concept=True)

    resp = await client.post(
        "/api/audio/request",
        json={
            "scope_type": "concept",
            "scope_ref": str(concept.id),
            "lens": "user_instruction",
            "instruction": "walk me through the derivation",
        },
        headers=user["headers"],
    )

    assert resp.status_code == 202
    assert len(fake_queue["jobs"]) == 1


async def test_request_allows_remediation_for_stem_concept(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, concept = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM, with_concept=True)

    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "concept", "scope_ref": str(concept.id), "lens": "remediation"},
        headers=user["headers"],
    )

    assert resp.status_code == 202
    assert len(fake_queue["jobs"]) == 1


# ── worker backstop: skip auto-generating a global default for an unsuitable topic ──


async def test_create_global_default_skips_stem_topic(db_session, worker_db, register_user, topic_ctx):
    user = await register_user()
    _, topic, knowledge, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.STEM)

    artifact_id = await audio_worker._create_global_default(
        {"knowledge_id": str(knowledge.id), "topic_id": str(topic.id), "course_id": str(topic.course_id)}
    )

    assert artifact_id is None
    result = await db_session.execute(select(AudioArtifact).where(AudioArtifact.scope_ref == topic.id))
    assert result.scalar_one_or_none() is None


async def test_create_global_default_creates_for_humanities_topic(db_session, worker_db, register_user, topic_ctx):
    user = await register_user()
    _, topic, knowledge, _ = await topic_ctx(user["id"], subject_family=SubjectFamily.HUMANITIES)

    artifact_id = await audio_worker._create_global_default(
        {"knowledge_id": str(knowledge.id), "topic_id": str(topic.id), "course_id": str(topic.course_id)}
    )

    assert artifact_id is not None
