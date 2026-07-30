"""
POST /api/audio/request — the personal audio request (docs/listen-audio-plan.md Phase 1).

A caller asks for a specific lens over a scope (topic or concept), optionally with their
own free-text instruction. Unlike the shared global artifact, personal requests are never
deduped — every call creates a fresh row and enqueues a fresh job (§1). The default lens
and remediation are explicitly out of scope here (default is served for free via GET;
remediation is Phase 2), so both are rejected rather than silently accepted.

Also covers the worker's personal-artifact path: given an existing PENDING artifact
(rather than the legacy knowledge_id/topic_id job shape), it generates using the
artifact's own lens/instruction/concept-focus and saves in place.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Concept, Course, Topic
from app.models.course import CourseEnrollment
from app.models.knowledge import AudioArtifact, AudioLens, AudioScopeType, KnowledgeStatus, TopicKnowledge
from app.services.redis_client import redis_client
from app.workers import audio_worker


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
    """Factory: course + topic (+ optional concept), enrolling ``user_id`` unless
    ``enrolled=False``. Optionally attaches completed TopicKnowledge."""

    async def _make(user_id, *, enrolled=True, knowledge_status=None, with_concept=False):
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

        concept = None
        if with_concept:
            concept = Concept(
                topic_id=topic.id, course_id=course.id, text="ATP", definition="energy currency"
            )
            db_session.add(concept)
            await db_session.flush()

        await db_session.commit()
        return course, topic, knowledge, concept

    return _make


# ── validation ────────────────────────────────────────────────────────────────

async def test_rejects_unknown_scope_type(client, register_user, fake_queue):
    user = await register_user()
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "planet", "scope_ref": str(uuid.uuid4()), "lens": "exam_focused"},
        headers=user["headers"],
    )
    assert resp.status_code == 400


async def test_rejects_unknown_lens(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "dramatic"},
        headers=user["headers"],
    )
    assert resp.status_code == 400


async def test_rejects_default_lens(client, register_user, topic_ctx, fake_queue):
    """Default is the free shared lesson — fetched via GET, never personally requested."""
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "default"},
        headers=user["headers"],
    )
    assert resp.status_code == 400
    assert fake_queue["jobs"] == []


async def test_rejects_remediation_lens_not_yet_available(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "remediation"},
        headers=user["headers"],
    )
    assert resp.status_code == 400
    assert fake_queue["jobs"] == []


async def test_user_instruction_lens_requires_instruction(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "user_instruction"},
        headers=user["headers"],
    )
    assert resp.status_code == 400


async def test_instruction_rejected_outside_user_instruction_lens(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    resp = await client.post(
        "/api/audio/request",
        json={
            "scope_type": "topic",
            "scope_ref": str(topic.id),
            "lens": "exam_focused",
            "instruction": "focus on X",
        },
        headers=user["headers"],
    )
    assert resp.status_code == 400


async def test_rejects_course_scope_not_yet_available(client, register_user, fake_queue):
    user = await register_user()
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "course", "scope_ref": str(uuid.uuid4()), "lens": "exam_focused"},
        headers=user["headers"],
    )
    assert resp.status_code == 400
    assert fake_queue["jobs"] == []


async def test_requires_completed_knowledge(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.PROCESSING)
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "exam_focused"},
        headers=user["headers"],
    )
    assert resp.status_code == 422


async def test_requires_enrollment_for_topic_scope(client, register_user, topic_ctx, fake_queue):
    owner = await register_user()
    outsider = await register_user()
    _, topic, _, _ = await topic_ctx(owner["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "exam_focused"},
        headers=outsider["headers"],
    )
    assert resp.status_code == 403


# ── success paths ─────────────────────────────────────────────────────────────

async def test_succeeds_for_topic_scope_with_user_instruction(client, db_session, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, knowledge, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)

    resp = await client.post(
        "/api/audio/request",
        json={
            "scope_type": "topic",
            "scope_ref": str(topic.id),
            "lens": "user_instruction",
            "instruction": "focus on the exceptions",
        },
        headers=user["headers"],
    )

    assert resp.status_code == 202
    body = resp.json()
    assert len(fake_queue["jobs"]) == 1
    queue_name, payload = fake_queue["jobs"][0]
    assert queue_name == "audio"
    assert payload["artifact_id"] == body["artifact_id"]

    artifact = (
        await db_session.execute(select(AudioArtifact).where(AudioArtifact.id == uuid.UUID(body["artifact_id"])))
    ).scalar_one()
    assert artifact.owner_id == uuid.UUID(user["id"])
    assert artifact.lens.value == "user_instruction"
    assert artifact.instruction == "focus on the exceptions"
    assert artifact.status == KnowledgeStatus.PENDING
    assert artifact.knowledge_id == knowledge.id


async def test_succeeds_for_concept_scope(client, db_session, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, knowledge, concept = await topic_ctx(
        user["id"], knowledge_status=KnowledgeStatus.COMPLETED, with_concept=True
    )

    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "concept", "scope_ref": str(concept.id), "lens": "worked_example"},
        headers=user["headers"],
    )

    assert resp.status_code == 202
    body = resp.json()
    artifact = (
        await db_session.execute(select(AudioArtifact).where(AudioArtifact.id == uuid.UUID(body["artifact_id"])))
    ).scalar_one()
    assert artifact.scope_type == AudioScopeType.CONCEPT
    assert artifact.scope_ref == concept.id
    assert artifact.knowledge_id == knowledge.id


async def test_requires_enrollment_for_concept_scope(client, register_user, topic_ctx, fake_queue):
    owner = await register_user()
    outsider = await register_user()
    _, topic, _, concept = await topic_ctx(
        owner["id"], knowledge_status=KnowledgeStatus.COMPLETED, with_concept=True
    )
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "concept", "scope_ref": str(concept.id), "lens": "worked_example"},
        headers=outsider["headers"],
    )
    assert resp.status_code == 403


async def test_personal_requests_are_never_deduped(client, register_user, topic_ctx, fake_queue):
    """Two identical requests create two artifacts — the 'always fresh' rule (§1)."""
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    payload = {"scope_type": "topic", "scope_ref": str(topic.id), "lens": "slower"}

    r1 = await client.post("/api/audio/request", json=payload, headers=user["headers"])
    r2 = await client.post("/api/audio/request", json=payload, headers=user["headers"])

    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["artifact_id"] != r2.json()["artifact_id"]
    assert len(fake_queue["jobs"]) == 2


# ── worker: personal-artifact job shape ────────────────────────────────────────


@pytest_asyncio.fixture
async def worker_db(monkeypatch, session_factory):
    monkeypatch.setattr(audio_worker, "AsyncSessionLocal", session_factory)


@pytest.fixture
def stub_generation(monkeypatch):
    captured = {}

    async def fake_generate_script(knowledge, *, topic_name, lens, concept_focus, instruction, wrong_answers=None):
        captured["lens"] = lens
        captured["concept_focus"] = concept_focus
        captured["instruction"] = instruction
        return "a script"

    async def fake_generate_audio(script, voice):
        return b"fake-mp3-bytes"

    async def fake_upload_audio(audio_bytes, artifact_id):
        return f"https://cdn.example/{artifact_id}.mp3", 42

    monkeypatch.setattr(audio_worker.audio_generator, "generate_script", fake_generate_script)
    monkeypatch.setattr(audio_worker.audio_generator, "generate_audio", fake_generate_audio)
    monkeypatch.setattr(audio_worker.audio_generator, "upload_audio", fake_upload_audio)
    return captured


async def test_worker_generates_personal_artifact_with_its_own_lens_and_instruction(
    db_session, worker_db, stub_generation, topic_ctx, register_user
):
    user = await register_user()
    _, topic, knowledge, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)

    artifact = AudioArtifact(
        scope_type=AudioScopeType.TOPIC,
        scope_ref=topic.id,
        knowledge_id=knowledge.id,
        lens=AudioLens.USER_INSTRUCTION,
        instruction="go deep on the exceptions",
        owner_id=uuid.UUID(user["id"]),
        status=KnowledgeStatus.PENDING,
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)

    await audio_worker.process_audio_job({"artifact_id": str(artifact.id), "course_id": str(topic.course_id)})

    assert stub_generation["instruction"] == "go deep on the exceptions"
    assert stub_generation["concept_focus"] is None

    await db_session.refresh(artifact)
    assert artifact.status == KnowledgeStatus.COMPLETED
    assert artifact.audio_url == f"https://cdn.example/{artifact.id}.mp3"


async def test_worker_resolves_concept_focus_for_concept_scope(
    db_session, worker_db, stub_generation, topic_ctx, register_user
):
    user = await register_user()
    _, topic, knowledge, concept = await topic_ctx(
        user["id"], knowledge_status=KnowledgeStatus.COMPLETED, with_concept=True
    )

    artifact = AudioArtifact(
        scope_type=AudioScopeType.CONCEPT,
        scope_ref=concept.id,
        knowledge_id=knowledge.id,
        lens=AudioLens.WORKED_EXAMPLE,
        owner_id=uuid.UUID(user["id"]),
        status=KnowledgeStatus.PENDING,
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)

    await audio_worker.process_audio_job({"artifact_id": str(artifact.id), "course_id": str(topic.course_id)})

    assert stub_generation["concept_focus"] == {"term": "ATP", "definition": "energy currency"}

    await db_session.refresh(artifact)
    assert artifact.status == KnowledgeStatus.COMPLETED
