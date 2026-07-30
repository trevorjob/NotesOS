"""
Remediation end-to-end (docs/listen-audio-plan.md Phase 2, §6): the request-endpoint
gating (concept-scope only), GET /topics/{id}/weak-concepts as the surface-agnostic
suggestion source, and the worker resolving the caller's actual wrong answers before
generating.
"""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Concept, Course, Topic
from app.models.course import CourseEnrollment
from app.models.knowledge import AudioArtifact, AudioLens, AudioScopeType, KnowledgeStatus, TopicKnowledge
from app.models.retrieval import ConceptState, RetrievalAttempt
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
    async def _make(user_id, *, enrolled=True, knowledge_status=None, with_concept=False, concept_state=None):
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
            concept = Concept(topic_id=topic.id, course_id=course.id, text="ATP", definition="energy currency")
            db_session.add(concept)
            await db_session.flush()
            if concept_state is not None:
                db_session.add(ConceptState(user_id=uid, concept_id=concept.id, **concept_state))

        await db_session.commit()
        return course, topic, knowledge, concept

    return _make


# ── POST /audio/request gating ─────────────────────────────────────────────────

async def test_remediation_rejected_for_topic_scope(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(user["id"], knowledge_status=KnowledgeStatus.COMPLETED)
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "topic", "scope_ref": str(topic.id), "lens": "remediation"},
        headers=user["headers"],
    )
    assert resp.status_code == 400
    assert fake_queue["jobs"] == []


async def test_remediation_succeeds_for_concept_scope(client, db_session, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, knowledge, concept = await topic_ctx(
        user["id"], knowledge_status=KnowledgeStatus.COMPLETED, with_concept=True
    )
    resp = await client.post(
        "/api/audio/request",
        json={"scope_type": "concept", "scope_ref": str(concept.id), "lens": "remediation"},
        headers=user["headers"],
    )
    assert resp.status_code == 202
    artifact = (
        await db_session.execute(
            select(AudioArtifact).where(AudioArtifact.id == uuid.UUID(resp.json()["artifact_id"]))
        )
    ).scalar_one()
    assert artifact.lens == AudioLens.REMEDIATION
    assert artifact.scope_type == AudioScopeType.CONCEPT


async def test_remediation_rejects_instruction(client, register_user, topic_ctx, fake_queue):
    user = await register_user()
    _, topic, _, concept = await topic_ctx(
        user["id"], knowledge_status=KnowledgeStatus.COMPLETED, with_concept=True
    )
    resp = await client.post(
        "/api/audio/request",
        json={
            "scope_type": "concept",
            "scope_ref": str(concept.id),
            "lens": "remediation",
            "instruction": "please",
        },
        headers=user["headers"],
    )
    assert resp.status_code == 400


# ── GET /topics/{id}/weak-concepts ─────────────────────────────────────────────

async def test_weak_concepts_empty_when_nothing_shaky(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _, _ = await topic_ctx(
        user["id"], with_concept=True, concept_state={"reps": 3, "last_grade": "good", "lapses": 0}
    )
    resp = await client.get(f"/api/topics/{topic.id}/weak-concepts", headers=user["headers"])
    assert resp.status_code == 200
    assert resp.json()["concepts"] == []


async def test_weak_concepts_surfaces_shaky_concept(client, register_user, topic_ctx):
    user = await register_user()
    _, topic, _, concept = await topic_ctx(
        user["id"], with_concept=True, concept_state={"reps": 3, "last_grade": "again", "lapses": 2}
    )
    resp = await client.get(f"/api/topics/{topic.id}/weak-concepts", headers=user["headers"])
    assert resp.status_code == 200
    concepts = resp.json()["concepts"]
    assert len(concepts) == 1
    assert concepts[0]["concept_id"] == str(concept.id)
    assert concepts[0]["term"] == "ATP"


async def test_weak_concepts_requires_enrollment(client, register_user, topic_ctx):
    owner = await register_user()
    outsider = await register_user()
    _, topic, _, _ = await topic_ctx(owner["id"], with_concept=True)
    resp = await client.get(f"/api/topics/{topic.id}/weak-concepts", headers=outsider["headers"])
    assert resp.status_code == 403


# ── worker: resolves wrong answers for a remediation artifact ─────────────────


@pytest_asyncio.fixture
async def worker_db(monkeypatch, session_factory):
    monkeypatch.setattr(audio_worker, "AsyncSessionLocal", session_factory)


@pytest.fixture
def stub_generation(monkeypatch):
    captured = {}

    async def fake_generate_script(knowledge, *, topic_name, lens, concept_focus, instruction, wrong_answers):
        captured["wrong_answers"] = wrong_answers
        return "a script"

    async def fake_generate_audio(script, voice):
        return b"fake-mp3-bytes"

    async def fake_upload_audio(audio_bytes, artifact_id):
        return f"https://cdn.example/{artifact_id}.mp3", 42

    monkeypatch.setattr(audio_worker.audio_generator, "generate_script", fake_generate_script)
    monkeypatch.setattr(audio_worker.audio_generator, "generate_audio", fake_generate_audio)
    monkeypatch.setattr(audio_worker.audio_generator, "upload_audio", fake_upload_audio)
    return captured


async def test_worker_resolves_wrong_answers_for_remediation_artifact(
    db_session, worker_db, stub_generation, topic_ctx, register_user
):
    user = await register_user()
    _, topic, knowledge, concept = await topic_ctx(
        user["id"], knowledge_status=KnowledgeStatus.COMPLETED, with_concept=True
    )
    uid = uuid.UUID(user["id"])
    db_session.add(
        RetrievalAttempt(
            user_id=uid, concept_id=concept.id, mode="quiz", outcome_score=0.0, grade="again",
            challenge={"prompt": "What does ATP do?"}, response={"raw": "stores fat"},
            created_at=datetime.utcnow(),
        )
    )
    artifact = AudioArtifact(
        scope_type=AudioScopeType.CONCEPT,
        scope_ref=concept.id,
        knowledge_id=knowledge.id,
        lens=AudioLens.REMEDIATION,
        owner_id=uid,
        status=KnowledgeStatus.PENDING,
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)

    await audio_worker.process_audio_job({"artifact_id": str(artifact.id), "course_id": str(topic.course_id)})

    assert stub_generation["wrong_answers"] == [{"question": "What does ATP do?", "your_answer": "stores fat"}]

    await db_session.refresh(artifact)
    assert artifact.status == KnowledgeStatus.COMPLETED


async def test_worker_passes_none_wrong_answers_for_non_remediation_lens(
    db_session, worker_db, stub_generation, topic_ctx, register_user
):
    """Non-remediation lenses never look up the attempt log — wrong_answers stays None."""
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

    assert stub_generation["wrong_answers"] is None
