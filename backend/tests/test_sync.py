"""
Offline sync (B6) — bulk pull, delta invalidation, append-only replay.

Service-level tests drive the event-sourcing core directly (snapshot shape, per-user
state isolation, delta windowing, and the replay: idempotency, ordering, per-event
rejection, derived ConceptState). API tests pin auth/enrollment + the batch counts.
The LLM/Redis boundaries are never touched — offline attempts arrive pre-graded.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from app.models import Concept, Course, CourseEnrollment, Topic, User
from app.models.knowledge import TopicKnowledge, KnowledgeStatus
from app.models.retrieval import ConceptState, RetrievalAttempt
from app.services import sync
from tests.conftest import unique_phone
from sqlalchemy import func, select

NOW = datetime(2026, 7, 13, 12, 0, 0)


# ── seeding ─────────────────────────────────────────────────────────────────────

async def _seed(db, *, user_id=None, enrolled=True):
    """A course with one topic + two concepts; optionally enrolling an existing user."""
    if user_id is None:
        user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
        db.add(user)
        await db.flush()
        user_id = user.id
    course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="Course", created_by=user_id)
    db.add(course)
    await db.flush()
    if enrolled:
        db.add(CourseEnrollment(user_id=user_id, course_id=course.id))
    topic = Topic(course_id=course.id, title="Krebs Cycle", order_index=0)
    db.add(topic)
    await db.flush()
    c1 = Concept(topic_id=topic.id, course_id=course.id, text="citrate", order_index=0)
    c2 = Concept(topic_id=topic.id, course_id=course.id, text="isocitrate", order_index=1)
    db.add_all([c1, c2])
    await db.flush()
    return user_id, course, topic, (c1, c2)


def _event(concept_id, *, grade="good", mode="quiz", when=NOW, key=None, score=None):
    return sync.AttemptEvent(
        client_event_id=key or str(uuid.uuid4()),
        concept_id=str(concept_id),
        mode=mode,
        grade=grade,
        score=score,
        created_at=when,
    )


# ── bulk pull ────────────────────────────────────────────────────────────────

async def test_snapshot_bundles_content_and_this_users_state(db_session):
    user_id, course, topic, (c1, c2) = await _seed(db_session)
    db_session.add(TopicKnowledge(
        topic_id=topic.id, consolidated_note="Note", key_points=["k"],
        concepts=[{"term": "T", "definition": "d"}], status=KnowledgeStatus.COMPLETED,
        generated_at=NOW,
    ))
    db_session.add(ConceptState(user_id=user_id, concept_id=c1.id, due=NOW, reps=2, lapses=0))
    await db_session.flush()

    snap = await sync.course_snapshot(db_session, user_id=user_id, course_id=course.id, now=NOW)

    assert snap["server_time"] is not None
    assert snap["course"]["id"] == str(course.id)
    assert {t["title"] for t in snap["topics"]} == {"Krebs Cycle"}
    assert len(snap["concepts"]) == 2
    assert snap["notes"][0]["consolidated_note"] == "Note"
    assert len(snap["states"]) == 1  # only this user's state
    assert snap["states"][0]["concept_id"] == str(c1.id)


async def test_snapshot_excludes_other_users_state(db_session):
    user_id, course, topic, (c1, c2) = await _seed(db_session)
    other = User(email=f"o_{uuid.uuid4().hex[:8]}@t.dev", full_name="O", password_hash="x", phone=unique_phone())
    db_session.add(other)
    await db_session.flush()
    db_session.add(ConceptState(user_id=other.id, concept_id=c1.id, due=NOW, reps=1))
    await db_session.flush()

    snap = await sync.course_snapshot(db_session, user_id=user_id, course_id=course.id, now=NOW)
    assert snap["states"] == []  # the other user's state is not mine


async def test_snapshot_unknown_course_is_empty(db_session):
    user_id, *_ = await _seed(db_session)
    snap = await sync.course_snapshot(db_session, user_id=user_id, course_id=uuid.uuid4(), now=NOW)
    assert snap == {}


# ── delta invalidation ─────────────────────────────────────────────────────────

async def test_changes_reports_notes_resynthesized_since(db_session):
    user_id, course, topic, _ = await _seed(db_session)
    db_session.add(TopicKnowledge(
        topic_id=topic.id, consolidated_note="v2", status=KnowledgeStatus.COMPLETED,
        generated_at=NOW,  # regenerated "now"
    ))
    await db_session.flush()

    since = NOW - timedelta(hours=1)
    changes = await sync.changes_since(db_session, user_id=user_id, since=since, now=NOW)
    assert str(topic.id) in changes["notes"]


async def test_changes_empty_when_nothing_moved_since(db_session):
    user_id, course, topic, _ = await _seed(db_session)
    # Everything was created at seed time; ask for changes strictly after.
    since = datetime.utcnow() + timedelta(days=1)
    changes = await sync.changes_since(db_session, user_id=user_id, since=since, course_id=course.id, now=NOW)
    assert changes["topics"] == []
    assert changes["notes"] == []
    assert changes["concepts"] == []


async def test_changes_with_no_enrollments_is_empty(db_session):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db_session.add(user)
    await db_session.flush()
    changes = await sync.changes_since(db_session, user_id=user.id, since=NOW - timedelta(days=1), now=NOW)
    assert changes["topics"] == [] and changes["concepts"] == []


# ── append-only replay ───────────────────────────────────────────────────────

async def test_push_applies_and_derives_state(db_session):
    user_id, course, topic, (c1, _) = await _seed(db_session)

    results = await sync.push_attempts(
        db_session, user_id=user_id, events=[_event(c1.id, grade="good", when=NOW)]
    )

    assert len(results) == 1 and results[0].status == "applied"
    # ConceptState was derived by the engine (FSRS), not sent by the client.
    state = await db_session.scalar(
        select(ConceptState).where(ConceptState.user_id == user_id, ConceptState.concept_id == c1.id)
    )
    assert state is not None and state.reps == 1 and state.last_grade == "good"
    # The attempt kept its original device timestamp + idempotency key.
    attempt = await db_session.scalar(select(RetrievalAttempt).where(RetrievalAttempt.concept_id == c1.id))
    assert attempt.created_at == NOW
    assert attempt.client_event_id is not None


async def test_push_is_idempotent_on_client_event_id(db_session):
    user_id, course, topic, (c1, _) = await _seed(db_session)
    key = str(uuid.uuid4())

    first = await sync.push_attempts(db_session, user_id=user_id, events=[_event(c1.id, key=key)])
    second = await sync.push_attempts(db_session, user_id=user_id, events=[_event(c1.id, key=key)])

    assert first[0].status == "applied"
    assert second[0].status == "duplicate"
    count = await db_session.scalar(
        select(func.count(RetrievalAttempt.id)).where(RetrievalAttempt.client_event_id == uuid.UUID(key))
    )
    assert count == 1  # replayed once only


async def test_push_dedupes_within_a_single_batch(db_session):
    user_id, course, topic, (c1, _) = await _seed(db_session)
    key = str(uuid.uuid4())
    results = await sync.push_attempts(
        db_session, user_id=user_id,
        events=[_event(c1.id, key=key, when=NOW), _event(c1.id, key=key, when=NOW)],
    )
    statuses = sorted(r.status for r in results)
    assert statuses == ["applied", "duplicate"]


async def test_push_replays_in_timestamp_order(db_session):
    user_id, course, topic, (c1, _) = await _seed(db_session)
    # Deliberately submit out of order; the later grade must be the one that sticks.
    events = [
        _event(c1.id, grade="easy", when=NOW + timedelta(minutes=10)),   # later
        _event(c1.id, grade="again", when=NOW),                          # earlier
    ]
    await sync.push_attempts(db_session, user_id=user_id, events=events)
    state = await db_session.scalar(
        select(ConceptState).where(ConceptState.user_id == user_id, ConceptState.concept_id == c1.id)
    )
    assert state.reps == 2
    assert state.last_grade == "easy"  # the chronologically-last event


async def test_push_rejects_online_only_mode(db_session):
    user_id, course, topic, (c1, _) = await _seed(db_session)
    results = await sync.push_attempts(
        db_session, user_id=user_id, events=[_event(c1.id, mode="ramble")]
    )
    assert results[0].status == "rejected"
    assert "online-only" in results[0].reason


async def test_push_rejects_unknown_concept_and_bad_grade(db_session):
    user_id, *_ = await _seed(db_session)
    results = await sync.push_attempts(
        db_session, user_id=user_id,
        events=[
            _event(uuid.uuid4(), grade="good"),        # concept doesn't exist
            _event(uuid.uuid4(), grade="brilliant"),   # invalid grade
        ],
    )
    assert all(r.status == "rejected" for r in results)


async def test_push_rejects_when_not_enrolled(db_session):
    # Concept belongs to a course the user is NOT enrolled in.
    owner_id, course, topic, (c1, _) = await _seed(db_session, enrolled=True)
    intruder = User(email=f"i_{uuid.uuid4().hex[:8]}@t.dev", full_name="I", password_hash="x", phone=unique_phone())
    db_session.add(intruder)
    await db_session.flush()

    results = await sync.push_attempts(db_session, user_id=intruder.id, events=[_event(c1.id)])
    assert results[0].status == "rejected"
    assert "not enrolled" in results[0].reason


async def test_push_batch_too_large_raises(db_session):
    user_id, course, topic, (c1, _) = await _seed(db_session)
    events = [_event(c1.id) for _ in range(sync.MAX_PUSH_BATCH + 1)]
    with pytest.raises(ValueError):
        await sync.push_attempts(db_session, user_id=user_id, events=events)


# ── API surface ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def seeded(db_session):
    async def _make(user_id):
        out = await _seed(db_session, user_id=uuid.UUID(user_id))
        await db_session.commit()
        return out
    return _make


async def test_pull_course_endpoint(client, register_user, seeded):
    user = await register_user()
    _, course, _, _ = await seeded(user["id"])
    resp = await client.get(f"/api/sync/courses/{course.id}", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["course"]["id"] == str(course.id)
    assert len(resp.json()["concepts"]) == 2


async def test_pull_course_requires_enrollment(client, register_user, seeded):
    owner = await register_user()
    _, course, _, _ = await seeded(owner["id"])
    intruder = await register_user()
    resp = await client.get(f"/api/sync/courses/{course.id}", headers=intruder["headers"])
    assert resp.status_code == 403


async def test_changes_endpoint(client, register_user, seeded):
    user = await register_user()
    await seeded(user["id"])
    since = (datetime.utcnow() - timedelta(days=1)).isoformat()
    resp = await client.get(f"/api/sync/changes?since={since}", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    assert "concepts" in resp.json() and "server_time" in resp.json()


async def test_push_endpoint_counts_and_idempotency(client, register_user, seeded):
    user = await register_user()
    _, course, topic, (c1, _) = await seeded(user["id"])
    key = str(uuid.uuid4())
    payload = {"attempts": [{
        "client_event_id": key, "concept_id": str(c1.id), "mode": "quiz",
        "grade": "good", "score": 0.9, "created_at": NOW.isoformat(),
    }]}

    first = await client.post("/api/sync/attempts", headers=user["headers"], json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["applied"] == 1

    second = await client.post("/api/sync/attempts", headers=user["headers"], json=payload)
    assert second.json()["duplicate"] == 1  # same key, already applied
    assert second.json()["applied"] == 0
