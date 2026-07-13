"""
Recap + sessions HTTP surface.

The recap grader (``recap._analyze_recall``) is monkeypatched so the endpoints run
without a model. We pin: the two-request recap handoff (many concepts → one prompt →
an attempt each), enrollment enforcement, the no-prior-session 404, the expired-recap
410, and the derived /sessions query.
"""

import uuid

import pytest
import pytest_asyncio

from app.models import Concept, Course, Topic
from app.models.course import CourseEnrollment
from app.services.redis_client import redis_client
from app.services.retrieval import engine, recap
from app.services.retrieval.modes import Outcome


@pytest_asyncio.fixture(autouse=True)
async def _fresh_redis():
    """Reset the singleton Redis connection per test (function-scoped event loop)."""
    redis_client._client = None
    yield
    if redis_client._client is not None:
        await redis_client._client.aclose()
        redis_client._client = None


@pytest.fixture(autouse=True)
def _stub_grader(monkeypatch):
    """Deterministic recap grading — full coverage for every concept."""

    async def fake_analyze(concepts, said):
        return [
            {"index": i + 1, "coverage": 1.0, "covered": ["ok"], "missed": [], "feedback": "great"}
            for i in range(len(concepts))
        ]

    monkeypatch.setattr(recap, "_analyze_recall", fake_analyze)


@pytest_asyncio.fixture
async def seeded(db_session):
    """A course enrolling ``user_id`` with a topic + two concepts."""

    async def _make(user_id, *, enrolled=True):
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uuid.UUID(user_id))
        db_session.add(course)
        await db_session.flush()
        if enrolled:
            db_session.add(CourseEnrollment(user_id=uuid.UUID(user_id), course_id=course.id))
        topic = Topic(course_id=course.id, title="Genetics", order_index=0)
        db_session.add(topic)
        await db_session.flush()
        concepts = [
            Concept(topic_id=topic.id, course_id=course.id, text=f"c{i}", order_index=i)
            for i in range(2)
        ]
        db_session.add_all(concepts)
        await db_session.flush()
        await db_session.commit()
        return course, topic, concepts

    return _make


async def _prior_session(db, user_id, concepts):
    for c in concepts:
        await engine.record_attempt(
            db, user_id=uuid.UUID(user_id), concept_id=c.id, mode="quiz",
            outcome=Outcome(score=1.0, grade="good"),
        )
    await db.commit()


async def test_recap_next_then_attempt(client, register_user, seeded, db_session):
    user = await register_user()
    _, topic, concepts = await seeded(user["id"])
    await _prior_session(db_session, user["id"], concepts)

    nxt = await client.post(
        "/api/retrieval/recap/next", headers=user["headers"], json={"topic_id": str(topic.id)}
    )
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["concept_count"] == 2
    assert body["topic_title"] == "Genetics"
    assert body["challenge_id"]
    # Uncued: concept text must not appear in the prompt.
    assert "c0" not in body["prompt"]

    att = await client.post(
        "/api/retrieval/recap/attempt",
        headers=user["headers"],
        json={"challenge_id": body["challenge_id"], "response": "everything I recall..."},
    )
    assert att.status_code == 200, att.text
    result = att.json()
    assert result["mode"] == "recap"
    assert result["concept_count"] == 2
    assert result["mean_score"] == pytest.approx(1.0)
    assert {o["concept_id"] for o in result["outcomes"]} == {str(c.id) for c in concepts}
    assert all(o["grade"] == "easy" for o in result["outcomes"])


async def test_recap_challenge_is_single_use(client, register_user, seeded, db_session):
    user = await register_user()
    _, topic, concepts = await seeded(user["id"])
    await _prior_session(db_session, user["id"], concepts)

    nxt = await client.post(
        "/api/retrieval/recap/next", headers=user["headers"], json={"topic_id": str(topic.id)}
    )
    cid = nxt.json()["challenge_id"]
    first = await client.post(
        "/api/retrieval/recap/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "x"},
    )
    assert first.status_code == 200
    again = await client.post(
        "/api/retrieval/recap/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "x"},
    )
    assert again.status_code == 410


async def test_recap_next_404_without_prior_session(client, register_user, seeded):
    user = await register_user()
    _, topic, _ = await seeded(user["id"])  # no attempts logged
    resp = await client.post(
        "/api/retrieval/recap/next", headers=user["headers"], json={"topic_id": str(topic.id)}
    )
    assert resp.status_code == 404


async def test_recap_enrollment_enforced(client, register_user, seeded, db_session):
    user = await register_user()
    _, topic, concepts = await seeded(user["id"], enrolled=False)
    await _prior_session(db_session, user["id"], concepts)
    resp = await client.post(
        "/api/retrieval/recap/next", headers=user["headers"], json={"topic_id": str(topic.id)}
    )
    assert resp.status_code == 403


async def test_sessions_endpoint_returns_derived_blocks(client, register_user, seeded, db_session):
    user = await register_user()
    _, topic, concepts = await seeded(user["id"])
    await _prior_session(db_session, user["id"], concepts)

    resp = await client.get("/api/retrieval/sessions", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["attempt_count"] == 2
    assert sessions[0]["modes"] == {"quiz": 2}
