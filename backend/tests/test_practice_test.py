"""
B14 — authored practice test: a shareable, graded question set built ON the retrieval
atom, so taking it *feeds* spaced repetition.

We pin:
- builder validation (quiz/pretest only; type enum; enrollment; topics-in-course);
- the multi-topic engine seam (``select_concepts`` over a topic-id set);
- async generation via the worker (frozen concept-anchored questions, progress broadcasts);
- the answer key never leaving the server (sanitized like /next);
- taking a question records a per-concept ``RetrievalAttempt`` (FSRS advances, calibration
  derives) with **no new grade path**, and each taker gets their own attempts;
- the derived result summary (nothing stored).

The LLM boundary is stubbed at ``QuizMode._generate_question``; the worker runs against
the real test Postgres via the patched session factory.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

import app.database as app_database
from app.models.course import Course, CourseEnrollment, Topic
from app.models.practice_test import (
    GEN_FAILED,
    GEN_READY,
    PracticeTest,
    PracticeTestQuestion,
)
from app.models.retrieval import Concept, RetrievalAttempt
from app.services.redis_client import redis_client
from app.services.retrieval import engine
from app.services.retrieval.quiz_mode import QuizMode
from app.workers.practice_test_worker import process_practice_test_job


# ── Plumbing ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_queue(monkeypatch):
    """Record enqueue_job / publish instead of touching Redis."""
    record = {"jobs": [], "events": []}

    async def _enqueue(queue, payload):
        record["jobs"].append((queue, payload))
        return "job-id"

    async def _publish(channel, message):
        record["events"].append((channel, message))

    monkeypatch.setattr(redis_client, "enqueue_job", _enqueue)
    monkeypatch.setattr(redis_client, "publish", _publish)
    return record


@pytest.fixture
def worker_db(monkeypatch, session_factory):
    """Point worker_session() at the test database."""
    monkeypatch.setattr(app_database, "async_session_maker", session_factory)


@pytest.fixture
def stub_question_gen(monkeypatch):
    """Canned question generation — one MCQ whose correct answer is 'A'.

    Records the requested question_type so a test can assert the builder's choice
    reaches the generator.
    """
    seen = {"types": []}

    async def _fake(self, concept, ctx):
        seen["types"].append(ctx.extra.get("question_type"))
        return {
            "question_text": f"About {concept.text}?",
            "question_type": ctx.extra.get("question_type") or "mcq",
            "answer_options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "explanation": "because A",
        }

    monkeypatch.setattr(QuizMode, "_generate_question", _fake)
    return seen


@pytest_asyncio.fixture
async def seed_course(db_session):
    """Factory: a course enrolling ``user_id`` with N topics, each carrying M concepts."""

    async def _make(user_id, *, n_topics=2, per_topic=2, enrolled=True):
        uid = uuid.UUID(user_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        if enrolled:
            db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topics, concepts = [], []
        for ti in range(n_topics):
            topic = Topic(course_id=course.id, title=f"T{ti}", order_index=ti)
            db_session.add(topic)
            await db_session.flush()
            topics.append(topic)
            for ci in range(per_topic):
                c = Concept(
                    topic_id=topic.id, course_id=course.id,
                    text=f"concept-{ti}-{ci}", order_index=ci,
                )
                db_session.add(c)
                await db_session.flush()
                concepts.append(c)
        await db_session.commit()
        return course, topics, concepts

    return _make


# ── The engine seam: multi-topic selection ─────────────────────────────────────


async def test_select_concepts_topic_set(db_session, seed_course, register_user):
    user = await register_user()
    _, topics, concepts = await seed_course(user["id"], n_topics=3, per_topic=2)

    both = await engine.select_concepts(
        db_session, user_id=uuid.UUID(user["id"]), scope=engine.SCOPE_TOPIC,
        topic_ids=[topics[0].id, topics[1].id], limit=50,
    )
    got = {t.topic_id for t in both}
    assert got == {topics[0].id, topics[1].id}       # spans the chosen subset
    assert topics[2].id not in got                    # excludes the unchosen topic

    one = await engine.select_concepts(
        db_session, user_id=uuid.UUID(user["id"]), scope=engine.SCOPE_TOPIC,
        topic_ids=[topics[0].id], limit=50,
    )
    assert {t.topic_id for t in one} == {topics[0].id}


# ── Builder validation ─────────────────────────────────────────────────────────


async def _create(client, headers, course_id, **over):
    body = {
        "course_id": str(course_id),
        "title": "Mock 1",
        "mode": "quiz",
        "question_type": "mcq",
        "question_count": 3,
        "topic_ids": [],
    }
    body.update(over)
    return await client.post("/api/practice-tests", headers=headers, json=body)


async def test_create_returns_202_and_enqueues(client, register_user, seed_course, fake_queue):
    user = await register_user()
    course, _, _ = await seed_course(user["id"])
    resp = await _create(client, user["headers"], course.id)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["generation_status"] == "generating"
    assert body["mode"] == "quiz" and body["question_type"] == "mcq"
    # The generation job was enqueued for this test.
    assert fake_queue["jobs"] == [("practice_test", {"test_id": body["id"]})]


async def test_free_recall_modes_rejected(client, register_user, seed_course, fake_queue):
    """ramble / teach / brain_dump don't set-ify — the builder rejects them."""
    user = await register_user()
    course, _, _ = await seed_course(user["id"])
    for mode in ("ramble", "teach", "brain_dump"):
        resp = await _create(client, user["headers"], course.id, mode=mode)
        assert resp.status_code == 400, f"{mode} should be rejected"
    assert fake_queue["jobs"] == []


async def test_bad_question_type_rejected(client, register_user, seed_course, fake_queue):
    user = await register_user()
    course, _, _ = await seed_course(user["id"])
    resp = await _create(client, user["headers"], course.id, question_type="oral")
    assert resp.status_code == 400


async def test_create_requires_enrollment(client, register_user, seed_course, fake_queue):
    owner = await register_user()
    course, _, _ = await seed_course(owner["id"])
    intruder = await register_user()
    resp = await _create(client, intruder["headers"], course.id)
    assert resp.status_code == 403


async def test_topics_must_belong_to_course(client, register_user, seed_course, fake_queue):
    user = await register_user()
    course, _, _ = await seed_course(user["id"])
    other_course, other_topics, _ = await seed_course(user["id"])
    resp = await _create(
        client, user["headers"], course.id, topic_ids=[str(other_topics[0].id)]
    )
    assert resp.status_code == 400


# ── Generation worker ──────────────────────────────────────────────────────────


async def test_worker_generates_frozen_questions(
    client, register_user, seed_course, fake_queue, worker_db, stub_question_gen, db_session
):
    user = await register_user()
    course, topics, _ = await seed_course(user["id"], n_topics=2, per_topic=2)
    # Scope to a single topic (2 concepts), ask for 2 questions.
    resp = await _create(
        client, user["headers"], course.id,
        question_count=2, topic_ids=[str(topics[0].id)],
    )
    test_id = resp.json()["id"]

    await process_practice_test_job({"test_id": test_id})

    test = await db_session.get(PracticeTest, uuid.UUID(test_id))
    assert test.generation_status == GEN_READY
    assert test.question_count == 2 and test.questions_done == 2
    # The builder's chosen type reached the generator.
    assert stub_question_gen["types"] == ["mcq", "mcq"]

    qs = (await db_session.execute(
        select(PracticeTestQuestion).where(PracticeTestQuestion.test_id == test.id)
    )).scalars().all()
    assert len(qs) == 2
    # The frozen question carries the answer key (server-side).
    assert all(q.payload.get("correct_answer") == "A" for q in qs)
    # Concepts are all from the chosen topic.
    concept_ids = {q.concept_id for q in qs}
    topic_concepts = {
        c.id for c in (await db_session.execute(
            select(Concept).where(Concept.topic_id == topics[0].id)
        )).scalars().all()
    }
    assert concept_ids <= topic_concepts

    # A progress event per question + a completion event.
    kinds = [e[1]["message"]["type"] for e in fake_queue["events"]]
    assert kinds.count("practice_test_progress") == 2
    assert kinds[-1] == "practice_test_complete"


async def test_worker_fails_when_scope_has_no_concepts(
    client, register_user, db_session, fake_queue, worker_db, stub_question_gen
):
    user = await register_user()
    # A course + one empty topic (no concepts extracted yet).
    uid = uuid.UUID(user["id"])
    course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
    db_session.add(course)
    await db_session.flush()
    db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
    topic = Topic(course_id=course.id, title="empty")
    db_session.add(topic)
    await db_session.commit()

    resp = await _create(client, user["headers"], course.id, topic_ids=[str(topic.id)])
    test_id = resp.json()["id"]
    await process_practice_test_job({"test_id": test_id})

    test = await db_session.get(PracticeTest, uuid.UUID(test_id))
    assert test.generation_status == GEN_FAILED
    assert test.failure_reason
    assert fake_queue["events"][-1][1]["message"]["type"] == "practice_test_failed"


# ── Serving + taking ────────────────────────────────────────────────────────────


async def _build_ready_test(client, headers, course, topics, **over):
    """Create + run generation so a ready, shareable test exists."""
    resp = await _create(client, headers, course.id, **over)
    test_id = resp.json()["id"]
    await process_practice_test_job({"test_id": test_id})
    return test_id


async def test_get_test_strips_answer_key(
    client, register_user, seed_course, fake_queue, worker_db, stub_question_gen
):
    user = await register_user()
    course, topics, _ = await seed_course(user["id"], n_topics=1, per_topic=2)
    test_id = await _build_ready_test(
        client, user["headers"], course, topics,
        question_count=2, topic_ids=[str(topics[0].id)],
    )

    resp = await client.get(f"/api/practice-tests/{test_id}", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["generation_status"] == "ready"
    assert len(body["questions"]) == 2
    for q in body["questions"]:
        assert "correct_answer" not in q["payload"]
        assert "explanation" not in q["payload"]
        assert q["payload"]["answer_options"] == ["A", "B", "C", "D"]


async def test_answer_feeds_the_atom(
    client, register_user, seed_course, fake_queue, worker_db, stub_question_gen, db_session
):
    user = await register_user()
    course, topics, _ = await seed_course(user["id"], n_topics=1, per_topic=2)
    test_id = await _build_ready_test(
        client, user["headers"], course, topics,
        question_count=2, topic_ids=[str(topics[0].id)],
    )
    detail = (await client.get(f"/api/practice-tests/{test_id}", headers=user["headers"])).json()
    q0 = detail["questions"][0]

    resp = await client.post(
        f"/api/practice-tests/{test_id}/questions/{q0['id']}/answer",
        headers=user["headers"],
        json={"response": "A", "predicted_confidence": 0.5},
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["outcome"]["grade"] == "good" and out["outcome"]["score"] == 1.0
    assert out["state"]["due"] is not None and out["state"]["reps"] == 1
    assert out["calibration"]["label"] == "underconfident"  # 0.5 → 1.0

    # A per-concept attempt landed, tagged with this test (derivable summary).
    attempts = (await db_session.execute(
        select(RetrievalAttempt).where(
            RetrievalAttempt.concept_id == uuid.UUID(q0["concept_id"])
        )
    )).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].challenge["practice_test_id"] == test_id


async def test_shared_test_each_taker_own_attempt(
    client, register_user, seed_course, fake_queue, worker_db, stub_question_gen, db_session
):
    author = await register_user()
    course, topics, _ = await seed_course(author["id"], n_topics=1, per_topic=1)
    test_id = await _build_ready_test(
        client, author["headers"], course, topics,
        question_count=1, topic_ids=[str(topics[0].id)],
    )
    # A classmate enrolls and takes the *same* shared test.
    classmate = await register_user()
    db_session.add(CourseEnrollment(user_id=uuid.UUID(classmate["id"]), course_id=course.id))
    await db_session.commit()

    detail = (await client.get(f"/api/practice-tests/{test_id}", headers=classmate["headers"])).json()
    assert detail["generation_status"] == "ready"
    q0 = detail["questions"][0]
    resp = await client.post(
        f"/api/practice-tests/{test_id}/questions/{q0['id']}/answer",
        headers=classmate["headers"], json={"response": "B"},  # wrong
    )
    assert resp.status_code == 200
    assert resp.json()["outcome"]["grade"] == "again"

    # One attempt, owned by the classmate — the author has none.
    attempts = (await db_session.execute(
        select(RetrievalAttempt).where(
            RetrievalAttempt.concept_id == uuid.UUID(q0["concept_id"])
        )
    )).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].user_id == uuid.UUID(classmate["id"])


async def test_result_summary_is_derived(
    client, register_user, seed_course, fake_queue, worker_db, stub_question_gen
):
    user = await register_user()
    course, topics, _ = await seed_course(user["id"], n_topics=1, per_topic=2)
    test_id = await _build_ready_test(
        client, user["headers"], course, topics,
        question_count=2, topic_ids=[str(topics[0].id)],
    )
    detail = (await client.get(f"/api/practice-tests/{test_id}", headers=user["headers"])).json()
    qs = detail["questions"]
    # Answer one right, one wrong.
    await client.post(
        f"/api/practice-tests/{test_id}/questions/{qs[0]['id']}/answer",
        headers=user["headers"], json={"response": "A"},
    )
    await client.post(
        f"/api/practice-tests/{test_id}/questions/{qs[1]['id']}/answer",
        headers=user["headers"], json={"response": "Z"},
    )

    resp = await client.get(f"/api/practice-tests/{test_id}/result", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["question_count"] == 2
    assert result["answered_count"] == 2
    assert result["firmed_count"] == 1     # the right one
    assert result["fading_count"] == 1     # the wrong one
    assert result["mean_score"] == pytest.approx(0.5)


async def test_list_tests_for_course(
    client, register_user, seed_course, fake_queue, worker_db, stub_question_gen
):
    user = await register_user()
    course, topics, _ = await seed_course(user["id"], n_topics=1, per_topic=1)
    await _build_ready_test(
        client, user["headers"], course, topics,
        question_count=1, topic_ids=[str(topics[0].id)],
    )
    resp = await client.get(
        f"/api/practice-tests?course_id={course.id}", headers=user["headers"]
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["generation_status"] == "ready"


async def test_pretest_mode_is_allowed(client, register_user, seed_course, fake_queue):
    user = await register_user()
    course, _, _ = await seed_course(user["id"])
    resp = await _create(client, user["headers"], course.id, mode="pretest")
    assert resp.status_code == 202
    assert resp.json()["mode"] == "pretest"
