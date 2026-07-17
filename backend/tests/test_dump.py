"""
Brain dump (B7) — uncued whole-topic free recall: recap's machine, topic-set selector.

Service tests pin the selector (all topic concepts, uncued prompt, empty-topic error),
the shared grader's mode-key parameterization (attempts land under ``brain_dump``; a
concept the monologue never surfaces is a lapse), and the next-action read→dump case
(fresh ``NOTE_VIEW`` → offer a dump; stale/acted-on/absent → the old cascade). API tests
mirror the recap surface: full two-request flow, 409 on an empty topic, enrollment,
single-use, and the per-kind handoff namespace.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Concept, Course, CourseEnrollment, Topic, User
from app.models.consume import ConsumeEvent, ConsumeKind
from app.models.retrieval import ConceptState, RetrievalAttempt
from app.services.redis_client import redis_client
from app.services.retrieval import dump, recap
from app.services.retrieval.next_action import FRESH_READ_WINDOW, select_next_action
from tests.conftest import unique_phone

NOW = datetime(2026, 7, 17, 12, 0, 0)


# ── seeding ─────────────────────────────────────────────────────────────────────

async def _seed(db, *, concepts=3, enrolled=True, user_id=None):
    if user_id is None:
        user = User(email=f"d_{uuid.uuid4().hex[:8]}@t.dev", full_name="D", password_hash="x", phone=unique_phone())
        db.add(user)
        await db.flush()
        user_id = user.id
    course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="Course", created_by=user_id)
    db.add(course)
    await db.flush()
    if enrolled:
        db.add(CourseEnrollment(user_id=user_id, course_id=course.id))
    topic = Topic(course_id=course.id, title="Glycolysis", order_index=0)
    db.add(topic)
    await db.flush()
    rows = [
        Concept(topic_id=topic.id, course_id=course.id, text=f"step {i}", order_index=i)
        for i in range(concepts)
    ]
    db.add_all(rows)
    await db.flush()
    return user_id, course, topic, rows


async def _note_view(db, user_id, topic_id, *, at):
    event = ConsumeEvent(actor_id=user_id, topic_id=topic_id, kind=ConsumeKind.NOTE_VIEW)
    event.created_at = at
    db.add(event)
    await db.flush()


# ── the selector: build_dump ────────────────────────────────────────────────────

async def test_build_dump_covers_all_topic_concepts_uncued(db_session):
    _, _, topic, concepts = await _seed(db_session, concepts=3)

    challenge = await dump.build_dump(db_session, topic_id=topic.id)

    assert set(challenge.concept_ids) == {str(c.id) for c in concepts}
    assert "Glycolysis" in challenge.prompt
    # Uncued on purpose: naming the concepts would hand back the answer.
    assert all(c.text not in challenge.prompt for c in concepts)


async def test_build_dump_raises_on_empty_topic(db_session):
    _, _, topic, _ = await _seed(db_session, concepts=0)
    with pytest.raises(dump.NoDumpAvailable):
        await dump.build_dump(db_session, topic_id=topic.id)


# ── the shared grader, mode key swapped ─────────────────────────────────────────

async def test_grade_records_attempts_under_brain_dump(db_session, monkeypatch):
    user_id, _, topic, concepts = await _seed(db_session, concepts=2)

    async def fake_analyze(cs, said):
        # Concept 1 surfaced fully; concept 2 never mentioned (absent from the analysis).
        return [{"index": 1, "coverage": 1.0, "covered": ["all"], "missed": [], "feedback": "solid"}]

    monkeypatch.setattr(recap, "_analyze_recall", fake_analyze)

    results = await recap.grade_recap(
        db_session, user_id,
        concept_ids=[str(c.id) for c in concepts],
        response="everything I remember about glycolysis...",
        mode_key=dump.DUMP_MODE,
        now=NOW,
    )

    assert len(results) == 2
    attempts = (
        await db_session.execute(select(RetrievalAttempt).where(RetrievalAttempt.user_id == user_id))
    ).scalars().all()
    assert {a.mode for a in attempts} == {"brain_dump"}          # the log-level mode key
    assert all(a.challenge["brain_dump"] is True for a in attempts)
    # The unsurfaced concept is a genuine lapse — the forgetting the dump exposes.
    by_concept = {str(a.concept_id): a for a in attempts}
    assert by_concept[str(concepts[0].id)].grade == "easy"
    assert by_concept[str(concepts[1].id)].grade == "again"
    # And FSRS state was derived per concept, exactly as recap does.
    states = (
        await db_session.execute(select(ConceptState).where(ConceptState.user_id == user_id))
    ).scalars().all()
    assert len(states) == 2


# ── next-action: the read→dump beat ─────────────────────────────────────────────

async def test_freshly_read_topic_offers_a_dump_not_a_pretest(db_session):
    user_id, _, topic, _ = await _seed(db_session)
    await _note_view(db_session, user_id, topic.id, at=NOW - timedelta(hours=1))

    action = await select_next_action(db_session, user_id=user_id, now=NOW)

    assert action is not None
    assert action.kind == "dump"
    assert action.mode == "brain_dump"
    assert action.topic_id == topic.id
    assert "read" in action.reason.lower()


async def test_unread_new_topic_still_gets_a_pretest(db_session):
    user_id, *_ = await _seed(db_session)  # no NOTE_VIEW
    action = await select_next_action(db_session, user_id=user_id, now=NOW)
    assert action.kind == "new" and action.mode == "pretest"


async def test_stale_read_falls_back_to_pretest(db_session):
    user_id, _, topic, _ = await _seed(db_session)
    await _note_view(db_session, user_id, topic.id, at=NOW - FRESH_READ_WINDOW - timedelta(hours=1))
    action = await select_next_action(db_session, user_id=user_id, now=NOW)
    assert action.kind == "new" and action.mode == "pretest"


async def test_read_then_retrieved_means_offer_is_spent(db_session):
    # They read the note, then did retrieval work — the dump offer has done its job.
    user_id, _, topic, concepts = await _seed(db_session)
    await _note_view(db_session, user_id, topic.id, at=NOW - timedelta(hours=2))
    attempt = RetrievalAttempt(user_id=user_id, concept_id=concepts[0].id, mode="quiz", grade="good")
    attempt.created_at = NOW - timedelta(hours=1)  # after the view
    db_session.add(attempt)
    await db_session.flush()

    action = await select_next_action(db_session, user_id=user_id, now=NOW)
    assert action.kind != "dump"


async def test_review_still_beats_the_dump_offer(db_session):
    # Fading knowledge outranks everything — the cascade is strict.
    user_id, course, topic, concepts = await _seed(db_session)
    await _note_view(db_session, user_id, topic.id, at=NOW - timedelta(hours=1))
    other = Topic(course_id=course.id, title="Other", order_index=1)
    db_session.add(other)
    await db_session.flush()
    due = Concept(topic_id=other.id, course_id=course.id, text="fading", order_index=0)
    db_session.add(due)
    await db_session.flush()
    db_session.add(ConceptState(user_id=user_id, concept_id=due.id, due=NOW - timedelta(days=1), reps=1))
    await db_session.flush()

    action = await select_next_action(db_session, user_id=user_id, now=NOW)
    assert action.kind == "review"


# ── API surface ─────────────────────────────────────────────────────────────────

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
    """Deterministic dump grading — full coverage for every concept."""

    async def fake_analyze(concepts, said):
        return [
            {"index": i + 1, "coverage": 1.0, "covered": ["ok"], "missed": [], "feedback": "great"}
            for i in range(len(concepts))
        ]

    monkeypatch.setattr(recap, "_analyze_recall", fake_analyze)


@pytest_asyncio.fixture
async def seeded(db_session):
    async def _make(user_id, **kw):
        out = await _seed(db_session, user_id=uuid.UUID(user_id), **kw)
        await db_session.commit()
        return out
    return _make


async def test_dump_next_then_attempt(client, register_user, seeded, db_session):
    user = await register_user()
    _, _, topic, concepts = await seeded(user["id"], concepts=2)

    nxt = await client.post(
        "/api/retrieval/dump/next", headers=user["headers"], json={"topic_id": str(topic.id)}
    )
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["concept_count"] == 2
    assert "Glycolysis" in body["prompt"]
    assert "step 0" not in body["prompt"]  # uncued

    att = await client.post(
        "/api/retrieval/dump/attempt",
        headers=user["headers"],
        json={"challenge_id": body["challenge_id"], "response": "glycolysis breaks glucose..."},
    )
    assert att.status_code == 200, att.text
    result = att.json()
    assert result["mode"] == "brain_dump"
    assert result["concept_count"] == 2
    assert {o["concept_id"] for o in result["outcomes"]} == {str(c.id) for c in concepts}


async def test_dump_next_409_on_topic_without_concepts(client, register_user, seeded):
    user = await register_user()
    _, _, topic, _ = await seeded(user["id"], concepts=0)
    resp = await client.post(
        "/api/retrieval/dump/next", headers=user["headers"], json={"topic_id": str(topic.id)}
    )
    assert resp.status_code == 409


async def test_dump_enrollment_enforced(client, register_user, seeded):
    user = await register_user()
    _, _, topic, _ = await seeded(user["id"], enrolled=False)
    resp = await client.post(
        "/api/retrieval/dump/next", headers=user["headers"], json={"topic_id": str(topic.id)}
    )
    assert resp.status_code == 403


async def test_dump_challenge_is_single_use(client, register_user, seeded):
    user = await register_user()
    _, _, topic, _ = await seeded(user["id"])
    cid = (
        await client.post(
            "/api/retrieval/dump/next", headers=user["headers"], json={"topic_id": str(topic.id)}
        )
    ).json()["challenge_id"]

    first = await client.post(
        "/api/retrieval/dump/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "x"},
    )
    assert first.status_code == 200
    again = await client.post(
        "/api/retrieval/dump/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "x"},
    )
    assert again.status_code == 410


async def test_recap_challenge_cannot_be_played_as_a_dump(client, register_user, seeded, db_session):
    # The handoff is namespaced per kind — a recap id is worthless on the dump surface.
    user = await register_user()
    _, _, topic, concepts = await seeded(user["id"])
    from app.services.retrieval import engine
    from app.services.retrieval.modes import Outcome

    for c in concepts:  # a prior session, so recap has something to open
        await engine.record_attempt(
            db_session, user_id=uuid.UUID(user["id"]), concept_id=c.id, mode="quiz",
            outcome=Outcome(score=1.0, grade="good"),
        )
    await db_session.commit()

    recap_id = (
        await client.post(
            "/api/retrieval/recap/next", headers=user["headers"], json={"topic_id": str(topic.id)}
        )
    ).json()["challenge_id"]

    resp = await client.post(
        "/api/retrieval/dump/attempt", headers=user["headers"],
        json={"challenge_id": recap_id, "response": "x"},
    )
    assert resp.status_code == 410
