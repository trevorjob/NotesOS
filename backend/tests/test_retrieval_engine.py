"""
Retrieval engine core — scope selection + attempt recording + scheduling.

Uses a FakeMode (no LLM) to prove the mode abstraction and the engine pipeline:
generate → evaluate → record → schedule. Real modes plug in the same way.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Concept, ConceptState, Course, RetrievalAttempt, Topic, User
from app.services.retrieval import engine
from app.services.retrieval.modes import Challenge, ModeContext, Outcome
from tests.conftest import unique_phone


class FakeMode:
    """A deterministic mode: the response string dictates the grade."""

    key = "fake"

    async def generate(self, concept, ctx) -> Challenge:
        return Challenge(concept_id=str(concept.id), prompt=f"Recall: {concept.text}")

    async def evaluate(self, concept, challenge, response, ctx) -> Outcome:
        mapping = {
            "right": Outcome(score=1.0, grade="good"),
            "meh": Outcome(score=0.5, grade="hard"),
            "wrong": Outcome(score=0.0, grade="again"),
        }
        return mapping[response]


async def _seed(db, *, n_topics=1, per_topic=2):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    topics = []
    for t in range(n_topics):
        topic = Topic(course_id=course.id, title=f"T{t}", order_index=t)
        db.add(topic)
        await db.flush()
        for i in range(per_topic):
            db.add(Concept(topic_id=topic.id, course_id=course.id, text=f"c{t}.{i}", order_index=i))
        topics.append(topic)
    await db.flush()
    return user, course, topics


def _ctx(db, user):
    return ModeContext(db=db, user_id=user.id)


async def test_run_once_records_attempt_and_schedule(db_session):
    user, course, topics = await _seed(db_session, per_topic=1)
    concept = (await db_session.execute(select(Concept))).scalars().first()

    result = await engine.run_once(
        db_session, mode=FakeMode(), concept=concept, response="right",
        ctx=_ctx(db_session, user), predicted_confidence=0.8,
    )

    assert result.outcome.grade == "good"
    # Append-only event captured, with calibration signal.
    attempt = (await db_session.execute(select(RetrievalAttempt))).scalars().one()
    assert attempt.mode == "fake"
    assert attempt.predicted_confidence == 0.8
    assert attempt.grade == "good"
    # Schedule created and pushed into the future.
    state = (await db_session.execute(select(ConceptState))).scalars().one()
    assert state.reps == 1
    assert state.lapses == 0
    assert state.due is not None and state.due > datetime.utcnow()


async def test_forgetting_increments_lapses(db_session):
    user, course, topics = await _seed(db_session, per_topic=1)
    concept = (await db_session.execute(select(Concept))).scalars().first()
    ctx = _ctx(db_session, user)

    await engine.run_once(db_session, mode=FakeMode(), concept=concept, response="right", ctx=ctx)
    await engine.run_once(db_session, mode=FakeMode(), concept=concept, response="wrong", ctx=ctx)

    state = (await db_session.execute(select(ConceptState))).scalars().one()
    assert state.reps == 2       # same row reused (unique user+concept)
    assert state.lapses == 1     # the "wrong" was a forgetting
    assert state.last_grade == "again"


async def test_topic_scope_returns_ordered_topic_concepts(db_session):
    user, course, topics = await _seed(db_session, n_topics=2, per_topic=2)
    got = await engine.select_concepts(
        db_session, user_id=user.id, scope=engine.SCOPE_TOPIC, topic_id=topics[0].id
    )
    assert [c.text for c in got] == ["c0.0", "c0.1"]


async def test_course_scope_spans_all_topics(db_session):
    user, course, topics = await _seed(db_session, n_topics=2, per_topic=2)
    got = await engine.select_concepts(
        db_session, user_id=user.id, scope=engine.SCOPE_COURSE, course_id=course.id
    )
    assert len(got) == 4


async def test_spaced_due_only_returns_due_concepts(db_session):
    user, course, topics = await _seed(db_session, per_topic=1)
    concept = (await db_session.execute(select(Concept))).scalars().first()
    ctx = _ctx(db_session, user)

    await engine.run_once(db_session, mode=FakeMode(), concept=concept, response="right", ctx=ctx)

    # Just reviewed → due in the future → nothing due now.
    due_now = await engine.select_concepts(
        db_session, user_id=user.id, scope=engine.SCOPE_SPACED_DUE, course_id=course.id
    )
    assert due_now == []

    # Force it overdue → it surfaces.
    state = (await db_session.execute(select(ConceptState))).scalars().one()
    state.due = datetime.utcnow() - timedelta(days=1)
    await db_session.flush()

    due_now = await engine.select_concepts(
        db_session, user_id=user.id, scope=engine.SCOPE_SPACED_DUE, course_id=course.id
    )
    assert [c.id for c in due_now] == [concept.id]


async def test_unknown_scope_raises(db_session):
    user, course, topics = await _seed(db_session)
    with pytest.raises(ValueError):
        await engine.select_concepts(db_session, user_id=user.id, scope="galaxy")
