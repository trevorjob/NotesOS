"""A2 — capture overhaul: audio ingestion, outline scaffold, dump→auto-organize,
low-confidence flagging, and the move (tweak) primitive.

LLM/vision/Whisper/embeddings are stubbed at their single seams; the worker runs
against the real test Postgres via a patched session factory.
"""

import json
import uuid

import pytest
from sqlalchemy import select

import app.database as app_database
from app.models.course import Topic
from app.models.resource import Resource, ResourceFile, ResourceKind
from app.services import capture as capture_service
from app.services.capture_types import kind_of
from app.services.embeddings import EmbeddingService
from app.services.redis_client import redis_client
from app.services.transcription import transcription_service
from app.services.vision_transcribe import vision_transcribe
from app.workers.capture_worker import process_capture_job


# ── Shared plumbing ───────────────────────────────────────────────────────────


@pytest.fixture
def fake_queue(monkeypatch):
    """Record enqueue_job / publish calls instead of touching Redis."""
    record = {"jobs": [], "events": []}

    async def _enqueue(queue, payload):
        record["jobs"].append((queue, payload))

    async def _publish(channel, message):
        record["events"].append((channel, message))

    monkeypatch.setattr(redis_client, "enqueue_job", _enqueue)
    monkeypatch.setattr(redis_client, "publish", _publish)
    return record


@pytest.fixture
def worker_db(monkeypatch, session_factory):
    """Point worker_session() at the test database for this test."""
    monkeypatch.setattr(app_database, "async_session_maker", session_factory)


async def _make_course(client, headers, code="CAP101", name="Capture 101"):
    resp = await client.post(
        "/api/courses", headers=headers, json={"code": code, "name": name}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["course"]["id"]


async def _make_topic(client, headers, course_id, title, order_index=0):
    resp = await client.post(
        f"/api/courses/{course_id}/topics",
        headers=headers,
        json={"course_id": course_id, "title": title, "order_index": order_index},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # The courses router's create-topic route wraps the payload; tolerate both.
    return (body.get("topic") or body)["id"]


# ── Unit: shared type allow-list + confidence heuristic + clustering ─────────


def test_kind_of_classifies_extensions():
    assert kind_of(".jpg") == "image"
    assert kind_of(".pdf") == "doc"
    assert kind_of(".md") == "doc"   # text-native rides the doc path
    assert kind_of(".txt") == "doc"
    assert kind_of(".mp3") == "audio"
    assert kind_of(".exe") is None


def test_estimate_confidence_clean_text_is_high():
    assert capture_service.estimate_confidence("A perfectly clear page of notes " * 20) == 1.0


def test_estimate_confidence_marked_text_is_low_and_flagged():
    words = ["word"] * 50
    text = " ".join(words) + " [illegible] [?] [illegible]"
    score = capture_service.estimate_confidence(text)
    assert score is not None and score < capture_service.NEEDS_REVIEW_THRESHOLD
    assert capture_service.needs_review(score) is True
    assert capture_service.needs_review(1.0) is False
    assert capture_service.needs_review(None) is False


def test_cluster_items_groups_similar_vectors():
    labels = capture_service.cluster_items(
        [[1.0, 0.0], [0.99, 0.05], [0.0, 1.0], [0.02, 0.98]]
    )
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]
    assert labels[0] != labels[2]


# ── Audio ingestion (upload-urls path) ────────────────────────────────────────


async def test_upload_urls_audio_creates_audio_resource_and_job(
    client, register_user, fake_queue
):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])
    topic_id = await _make_topic(client, user["headers"], course_id, "Lectures")

    resp = await client.post(
        "/api/resources/upload-urls",
        headers=user["headers"],
        json={
            "topic_id": topic_id,
            "files": [{"url": "https://cdn.test/lecture-week1.mp3",
                       "filename": "lecture-week1.mp3", "file_order": 0}],
        },
    )
    assert resp.status_code == 201, resp.text
    (created,) = resp.json()
    assert created["resource_type"] == "AUDIO"
    assert created["file_url"] == "https://cdn.test/lecture-week1.mp3"

    audio_jobs = [
        p for q, p in fake_queue["jobs"] if q == "transcription" and p["type"] == "audio"
    ]
    assert len(audio_jobs) == 1
    assert audio_jobs[0]["resource_id"] == created["id"]
    assert audio_jobs[0]["file_ext"] == ".mp3"


async def test_upload_urls_markdown_creates_text_resource(
    client, register_user, fake_queue
):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])
    topic_id = await _make_topic(client, user["headers"], course_id, "Readings")

    resp = await client.post(
        "/api/resources/upload-urls",
        headers=user["headers"],
        json={
            "topic_id": topic_id,
            "files": [{"url": "https://cdn.test/summary.md",
                       "filename": "summary.md", "file_order": 0}],
        },
    )
    assert resp.status_code == 201, resp.text
    (created,) = resp.json()
    assert created["resource_type"] == "TEXT"

    doc_jobs = [
        p for q, p in fake_queue["jobs"]
        if q == "transcription" and p["type"] == "document"
    ]
    assert len(doc_jobs) == 1 and doc_jobs[0]["file_ext"] == ".md"


# ── Outline scaffold ──────────────────────────────────────────────────────────


OUTLINE_JSON = json.dumps(
    {
        "topics": [
            {"title": "Chemical Bonding", "description": None, "week_number": 1},
            {"title": "Aromaticity", "description": "Benzene and friends", "week_number": 2},
            {"title": "", "description": "junk row dropped"},
        ]
    }
)


async def test_outline_scaffold_creates_ordered_topics(
    client, register_user, monkeypatch
):
    async def fake_llm(prompt, **kwargs):
        return OUTLINE_JSON

    monkeypatch.setattr("app.services.capture.call_llm", fake_llm)

    user = await register_user()
    course_id = await _make_course(client, user["headers"])

    resp = await client.post(
        f"/api/courses/{course_id}/outline",
        headers=user["headers"],
        json={"text": "Week 1: Chemical Bonding\nWeek 2: Aromaticity"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    titles = [t["title"] for t in body["created"]]
    assert titles == ["Chemical Bonding", "Aromaticity"]
    assert [t["order_index"] for t in body["created"]] == [0, 1]
    assert body["created"][1]["week_number"] == 2
    assert body["skipped"] == []

    # Communal artifact: a classmate re-adding the outline duplicates nothing.
    again = await client.post(
        f"/api/courses/{course_id}/outline",
        headers=user["headers"],
        json={"text": "same outline"},
    )
    assert again.status_code == 201
    assert again.json()["created"] == []
    assert sorted(again.json()["skipped"]) == ["Aromaticity", "Chemical Bonding"]


async def test_outline_requires_text_or_images(client, register_user):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])
    resp = await client.post(
        f"/api/courses/{course_id}/outline", headers=user["headers"], json={}
    )
    assert resp.status_code == 400


# ── Dump endpoint ─────────────────────────────────────────────────────────────


async def test_capture_dump_returns_202_and_enqueues_batch(
    client, register_user, fake_queue
):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])

    resp = await client.post(
        f"/api/courses/{course_id}/capture",
        headers=user["headers"],
        json={
            "files": [
                {"url": "https://cdn.test/a.jpg", "filename": "a.jpg", "file_order": 0},
                {"url": "https://cdn.test/b.pdf", "filename": "b.pdf", "file_order": 1},
            ]
        },
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["batch_id"] and body["file_count"] == 2

    (queue, payload), = [(q, p) for q, p in fake_queue["jobs"] if q == "capture"]
    assert payload["batch_id"] == body["batch_id"]
    assert payload["course_id"] == course_id
    assert len(payload["files"]) == 2


async def test_capture_dump_rejects_unsupported_and_empty(client, register_user):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])

    bad = await client.post(
        f"/api/courses/{course_id}/capture",
        headers=user["headers"],
        json={"files": [{"url": "https://cdn.test/x.exe", "filename": "x.exe"}]},
    )
    assert bad.status_code == 400

    empty = await client.post(
        f"/api/courses/{course_id}/capture", headers=user["headers"], json={"files": []}
    )
    assert empty.status_code == 400


async def test_capture_dump_requires_enrollment(client, register_user):
    owner = await register_user()
    course_id = await _make_course(client, owner["headers"])
    outsider = await register_user()
    resp = await client.post(
        f"/api/courses/{course_id}/capture",
        headers=outsider["headers"],
        json={"files": [{"url": "https://cdn.test/a.jpg", "filename": "a.jpg"}]},
    )
    assert resp.status_code == 403


# ── Worker: outline path (classification into known buckets) ─────────────────


def _stub_transcribers(monkeypatch, image_text="Benzene ring stability notes",
                       doc_text="Ionic vs covalent bonding", audio_text="Lecture on hybridisation"):
    async def fake_vision(urls):
        return image_text

    async def fake_doc(file_url, file_format, is_handwritten=False):
        return {"text": doc_text}

    async def fake_audio(url, file_ext=""):
        return {"text": audio_text, "language": "en", "duration": 60}

    monkeypatch.setattr(vision_transcribe, "transcribe_images", fake_vision)
    monkeypatch.setattr(
        "app.workers.capture_worker.file_processor.process_uploaded_file", fake_doc
    )
    monkeypatch.setattr(transcription_service, "transcribe_audio", fake_audio)


async def test_capture_worker_outline_path_files_into_known_topics(
    client, register_user, db_session, fake_queue, worker_db, monkeypatch
):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])
    aroma_id = await _make_topic(client, user["headers"], course_id, "Aromaticity", 0)
    bonding_id = await _make_topic(client, user["headers"], course_id, "Chemical Bonding", 1)

    _stub_transcribers(monkeypatch)

    async def fake_llm(prompt, **kwargs):
        # file 0 → Aromaticity (index 0), file 1 → Chemical Bonding (index 1),
        # file 2 unmapped → falls back to a new "Unsorted" topic.
        return json.dumps(
            {"assignments": [{"file": 0, "topic_index": 0}, {"file": 1, "topic_index": 1}]}
        )

    monkeypatch.setattr("app.services.capture.call_llm", fake_llm)

    await process_capture_job(
        {
            "batch_id": "batch-1",
            "course_id": course_id,
            "user_id": user["id"],
            "uploader_name": "Test User",
            "title": None,
            "files": [
                {"url": "https://cdn.test/benzene.jpg", "filename": "benzene.jpg", "file_order": 0},
                {"url": "https://cdn.test/bonding.pdf", "filename": "bonding.pdf", "file_order": 1},
                {"url": "https://cdn.test/mystery.mp3", "filename": "mystery.mp3", "file_order": 2},
            ],
        }
    )

    res = await db_session.execute(select(Resource))
    resources = {r.file_name or "benzene.jpg": r for r in res.scalars().all()}
    assert str(resources["benzene.jpg"].topic_id) == aroma_id
    assert resources["benzene.jpg"].content == "Benzene ring stability notes"
    assert resources["benzene.jpg"].resource_type == ResourceKind.IMAGE
    assert str(resources["bonding.pdf"].topic_id) == bonding_id
    assert resources["bonding.pdf"].resource_type == ResourceKind.PDF

    # The unmapped audio file landed in a fresh "Unsorted" topic — never dropped.
    topics_res = await db_session.execute(
        select(Topic).where(Topic.course_id == uuid.UUID(course_id))
    )
    by_title = {t.title: t for t in topics_res.scalars().all()}
    assert "Unsorted" in by_title
    assert resources["mystery.mp3"].topic_id == by_title["Unsorted"].id
    assert resources["mystery.mp3"].resource_type == ResourceKind.AUDIO

    # The image keeps its figure attached.
    rf = await db_session.execute(select(ResourceFile))
    assert [f.file_url for f in rf.scalars().all()] == ["https://cdn.test/benzene.jpg"]

    # Every filed resource entered the normal pipeline.
    chunk_jobs = [p for q, p in fake_queue["jobs"] if q == "chunking"]
    assert len(chunk_jobs) == 3

    # The room heard about it.
    event_types = [m["message"]["type"] for _, m in fake_queue["events"]]
    assert event_types[0] == "capture_progress"
    assert event_types[-1] == "capture_complete"
    complete = fake_queue["events"][-1][1]["message"]
    assert complete["failed"] == []
    assert len(complete["topics"]) == 3


# ── Worker: no-outline path (cluster and propose) ─────────────────────────────


async def test_capture_worker_cluster_path_creates_named_topics(
    client, register_user, db_session, fake_queue, worker_db, monkeypatch
):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])  # no topics at all

    _stub_transcribers(monkeypatch)

    async def fake_embed(self, texts, input_type="document"):
        # Two tight clusters: files 0+1 together, file 2 alone.
        vectors = [[1.0, 0.0], [0.98, 0.1], [0.0, 1.0]]
        return vectors[: len(texts)]

    monkeypatch.setattr(EmbeddingService, "generate_embeddings_batch", fake_embed)

    async def fake_llm(prompt, **kwargs):
        return json.dumps(
            {"clusters": [
                {"index": 0, "title": "Organic Chemistry", "description": None},
                {"index": 1, "title": "Thermodynamics", "description": None},
            ]}
        )

    monkeypatch.setattr("app.services.capture.call_llm", fake_llm)

    await process_capture_job(
        {
            "batch_id": "batch-2",
            "course_id": course_id,
            "user_id": user["id"],
            "uploader_name": "Test User",
            "title": None,
            "files": [
                {"url": "https://cdn.test/o1.jpg", "filename": "o1.jpg", "file_order": 0},
                {"url": "https://cdn.test/o2.jpg", "filename": "o2.jpg", "file_order": 1},
                {"url": "https://cdn.test/thermo.pdf", "filename": "thermo.pdf", "file_order": 2},
            ],
        }
    )

    topics_res = await db_session.execute(
        select(Topic).where(Topic.course_id == uuid.UUID(course_id))
    )
    by_title = {t.title: t for t in topics_res.scalars().all()}
    assert set(by_title) == {"Organic Chemistry", "Thermodynamics"}

    res = await db_session.execute(select(Resource))
    resources = {r.file_name: r for r in res.scalars().all()}
    assert resources["o1.jpg"].topic_id == by_title["Organic Chemistry"].id
    assert resources["o2.jpg"].topic_id == by_title["Organic Chemistry"].id
    assert resources["thermo.pdf"].topic_id == by_title["Thermodynamics"].id


async def test_capture_worker_survives_a_failed_file(
    client, register_user, db_session, fake_queue, worker_db, monkeypatch
):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])
    topic_id = await _make_topic(client, user["headers"], course_id, "Aromaticity", 0)

    async def fake_vision(urls):
        if "bad" in urls[0]:
            raise RuntimeError("unreadable image")
        return "Benzene notes"

    monkeypatch.setattr(vision_transcribe, "transcribe_images", fake_vision)

    async def fake_llm(prompt, **kwargs):
        return json.dumps({"assignments": [{"file": 0, "topic_index": 0}]})

    monkeypatch.setattr("app.services.capture.call_llm", fake_llm)

    await process_capture_job(
        {
            "batch_id": "batch-3",
            "course_id": course_id,
            "user_id": user["id"],
            "uploader_name": "Test User",
            "title": None,
            "files": [
                {"url": "https://cdn.test/good.jpg", "filename": "good.jpg", "file_order": 0},
                {"url": "https://cdn.test/bad.jpg", "filename": "bad.jpg", "file_order": 1},
            ],
        }
    )

    res = await db_session.execute(select(Resource))
    resources = res.scalars().all()
    assert len(resources) == 1  # the good file landed
    assert str(resources[0].topic_id) == topic_id

    complete = fake_queue["events"][-1][1]["message"]
    assert complete["type"] == "capture_complete"
    assert [f["filename"] for f in complete["failed"]] == ["bad.jpg"]


# ── Low-confidence flag surfaces in the API ───────────────────────────────────


async def test_low_confidence_resource_flags_needs_review(
    client, register_user, db_session, fake_queue
):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])
    topic_id = await _make_topic(client, user["headers"], course_id, "Notes", 0)

    resource = Resource(
        topic_id=uuid.UUID(topic_id),
        uploaded_by=uuid.UUID(user["id"]),
        title="Blurry scan",
        content="words [illegible] more [?] words",
        resource_type=ResourceKind.IMAGE,
        ocr_confidence=0.4,
    )
    db_session.add(resource)
    await db_session.commit()

    resp = await client.get(f"/api/resources/{resource.id}", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["needs_review"] is True
    assert body["ocr_confidence"] == 0.4


# ── Move (the capture tweak) ──────────────────────────────────────────────────


async def test_move_resource_between_topics(client, register_user, fake_queue):
    user = await register_user()
    course_id = await _make_course(client, user["headers"])
    topic_a = await _make_topic(client, user["headers"], course_id, "Topic A", 0)
    topic_b = await _make_topic(client, user["headers"], course_id, "Topic B", 1)

    created = await client.post(
        f"/api/topics/{topic_a}/resources/text",
        headers=user["headers"],
        json={"topic_id": topic_a, "title": "Misfiled", "content": "some notes"},
    )
    assert created.status_code == 201, created.text
    resource_id = created.json()["id"]

    moved = await client.patch(
        f"/api/resources/{resource_id}/move",
        headers=user["headers"],
        json={"topic_id": topic_b},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["topic_id"] == topic_b

    # Both topics' notes went stale → synthesis re-enqueued for each.
    knowledge_jobs = [p["topic_id"] for q, p in fake_queue["jobs"] if q == "knowledge"]
    assert set(knowledge_jobs) >= {topic_a, topic_b}


async def test_move_resource_rejects_non_uploader_and_cross_course(
    client, register_user, fake_queue
):
    owner = await register_user()
    course_id = await _make_course(client, owner["headers"])
    topic_a = await _make_topic(client, owner["headers"], course_id, "Topic A", 0)

    created = await client.post(
        f"/api/topics/{topic_a}/resources/text",
        headers=owner["headers"],
        json={"topic_id": topic_a, "content": "notes"},
    )
    resource_id = created.json()["id"]

    # Classmate (enrolled) but not the uploader → 403.
    other = await register_user()
    await client.post(
        "/api/courses/join", headers=other["headers"],
        json={"course_id": course_id},
    )
    denied = await client.patch(
        f"/api/resources/{resource_id}/move",
        headers=other["headers"],
        json={"topic_id": topic_a},
    )
    assert denied.status_code == 403

    # Uploader, but the target topic lives in another course → 400.
    other_course = await _make_course(client, owner["headers"], code="OTH101", name="Other")
    foreign_topic = await _make_topic(client, owner["headers"], other_course, "Elsewhere", 0)
    rejected = await client.patch(
        f"/api/resources/{resource_id}/move",
        headers=owner["headers"],
        json={"topic_id": foreign_topic},
    )
    assert rejected.status_code == 400
