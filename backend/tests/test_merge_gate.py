"""
Phase 4 — the Merge Agent quarantine gate.

Covers the pure coherence decision, the DB-facing apply (quarantine + release), and
the uploader-only visibility in the resource API.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Course, Resource, ResourceChunk, Topic, User
from app.models.resource import ResourceKind, SourceType
from app.services import merge_gate
from app.services.merge_gate import GateDecision, decide_quarantine
from tests.conftest import unique_phone


# ── Pure decision logic ───────────────────────────────────────────────────────


def test_cosine_orthogonal_and_aligned():
    assert merge_gate.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert merge_gate.cosine([1, 0], [0, 1]) == pytest.approx(0.0)


def test_below_min_corpus_passes_everything():
    # Two resources isn't enough of a topic to call either an outlier.
    decisions = decide_quarantine({"a": [1, 0], "b": [0, 1]}, min_corpus=3)
    assert all(d.quarantine is False and d.coherence is None for d in decisions.values())


def test_outlier_is_quarantined_peers_are_kept():
    centroids = {
        "on1": [1.0, 0.0],
        "on2": [0.9, 0.1],   # corroborates with on1
        "off": [0.0, 1.0],   # corroborates with nothing
    }
    decisions = decide_quarantine(centroids, threshold=0.3, min_corpus=3)
    assert decisions["off"].quarantine is True
    assert decisions["on1"].quarantine is False
    assert decisions["on2"].quarantine is False


def test_corroboration_releases():
    # Once a second off-topic-together upload arrives, the pair corroborate → kept.
    centroids = {"on1": [1.0, 0.0], "on2": [1.0, 0.0], "a": [0.0, 1.0], "b": [0.0, 1.0]}
    decisions = decide_quarantine(centroids, threshold=0.3, min_corpus=3)
    assert all(d.quarantine is False for d in decisions.values())


# ── DB-facing apply ───────────────────────────────────────────────────────────


def _vec(idx: int) -> list[float]:
    """A 1536-dim unit vector pointing along one axis (a distinct 'direction')."""
    v = [0.0] * 1536
    v[idx] = 1.0
    return v


async def _seed_topic(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="C", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="T")
    db.add(topic)
    await db.flush()
    return user, course, topic


async def _add_resource(db, topic, user, direction: int) -> Resource:
    resource = Resource(
        topic_id=topic.id,
        uploaded_by=user.id,
        title="r",
        content="x",
        resource_type=ResourceKind.TEXT,
        source_type=SourceType.TEXT,
    )
    db.add(resource)
    await db.flush()
    db.add(ResourceChunk(resource_id=resource.id, chunk_text="x", chunk_index=0, embedding=_vec(direction)))
    await db.flush()
    return resource


async def test_apply_quarantines_the_outlier(db_session):
    user, course, topic = await _seed_topic(db_session)
    r1 = await _add_resource(db_session, topic, user, direction=0)
    r2 = await _add_resource(db_session, topic, user, direction=0)
    off = await _add_resource(db_session, topic, user, direction=1000)

    summary = await merge_gate.apply_merge_gate(db_session, topic.id)
    assert summary["evaluated"] == 3
    assert str(off.id) in summary["quarantined"]

    await db_session.refresh(off)
    await db_session.refresh(r1)
    assert off.quarantined is True and off.quarantine_reason
    assert r1.quarantined is False


async def test_apply_releases_when_corroborated(db_session):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, direction=0)
    await _add_resource(db_session, topic, user, direction=0)
    off = await _add_resource(db_session, topic, user, direction=1000)

    await merge_gate.apply_merge_gate(db_session, topic.id)
    await db_session.refresh(off)
    assert off.quarantined is True

    # A second upload in the same off-axis direction corroborates the outlier.
    await _add_resource(db_session, topic, user, direction=1000)
    summary = await merge_gate.apply_merge_gate(db_session, topic.id)
    assert str(off.id) in summary["released"]
    await db_session.refresh(off)
    assert off.quarantined is False


async def test_below_min_corpus_quarantines_nothing(db_session):
    user, course, topic = await _seed_topic(db_session)
    await _add_resource(db_session, topic, user, direction=0)
    off = await _add_resource(db_session, topic, user, direction=1000)  # only 2 total

    summary = await merge_gate.apply_merge_gate(db_session, topic.id)
    assert summary["quarantined"] == []
    await db_session.refresh(off)
    assert off.quarantined is False


# ── API visibility ────────────────────────────────────────────────────────────


async def test_quarantined_resource_visible_only_to_uploader(client, register_user, db_session):
    owner = await register_user()
    course_resp = await client.post(
        "/api/courses", headers=owner["headers"], json={"code": "BIO", "name": "Bio"}
    )
    course_id = course_resp.json()["course"]["id"]
    topic_resp = await client.post(
        f"/api/courses/{course_id}/topics",
        headers=owner["headers"],
        json={"course_id": course_id, "title": "Cells", "order_index": 0},
    )
    topic_id = topic_resp.json()["id"]

    classmate = await register_user()
    await client.post("/api/courses/join", headers=classmate["headers"], json={"course_id": course_id})

    # Seed a quarantined resource uploaded by the owner.
    resource = Resource(
        topic_id=uuid.UUID(topic_id),
        uploaded_by=uuid.UUID(owner["id"]),
        title="off-topic dump",
        content="unrelated",
        resource_type=ResourceKind.TEXT,
        source_type=SourceType.TEXT,
        quarantined=True,
        quarantine_reason="Off-topic",
    )
    db_session.add(resource)
    await db_session.commit()

    # Owner sees it (flagged); the classmate never does.
    owner_list = await client.get(f"/api/topics/{topic_id}/resources", headers=owner["headers"])
    owner_ids = [(r["id"], r["quarantined"]) for r in owner_list.json()["resources"]]
    assert (str(resource.id), True) in owner_ids

    mate_list = await client.get(f"/api/topics/{topic_id}/resources", headers=classmate["headers"])
    assert str(resource.id) not in [r["id"] for r in mate_list.json()["resources"]]
    assert mate_list.json()["total"] == 0
