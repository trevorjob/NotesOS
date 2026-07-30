"""
Remediation support (docs/listen-audio-plan.md §6): the weak-concept selector and the
wrong-answer context loader that back "you keep missing X, want a breakdown?".

Both reuse existing signal rather than inventing new detection: ``weakest_concepts``
is the note's own "shaky" heat-map label; ``recent_wrong_answers`` reads straight off
the append-only ``RetrievalAttempt`` log's ``challenge``/``response`` JSON.
"""

import uuid
from datetime import datetime, timedelta

import pytest_asyncio

from app.models import Concept, Course, Topic, User
from app.models.course import CourseEnrollment
from app.models.retrieval import ConceptState, RetrievalAttempt
from app.services.retrieval.remediation import recent_wrong_answers, weakest_concepts
from tests.conftest import unique_phone


@pytest_asyncio.fixture
async def topic_with_concepts(db_session):
    """Factory: a course (enrolling ``user_id``) + topic + concepts, each optionally
    carrying a ConceptState. ``concepts`` is a list of (term, state_kwargs|None)."""

    async def _make(user_id, concepts, *, topic_title="T"):
        uid = uuid.UUID(user_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topic = Topic(course_id=course.id, title=topic_title)
        db_session.add(topic)
        await db_session.flush()

        made = []
        for i, (term, state_kwargs) in enumerate(concepts):
            concept = Concept(topic_id=topic.id, course_id=course.id, text=term, order_index=i)
            db_session.add(concept)
            await db_session.flush()
            if state_kwargs is not None:
                db_session.add(ConceptState(user_id=uid, concept_id=concept.id, **state_kwargs))
            made.append(concept)
        await db_session.commit()
        return course, topic, made

    return _make


# ── weakest_concepts ──────────────────────────────────────────────────────────

async def test_shaky_concept_is_included(db_session, register_user, topic_with_concepts):
    user = await register_user()
    _, topic, concepts = await topic_with_concepts(
        user["id"], [("Osmosis", {"reps": 3, "last_grade": "again", "lapses": 2})]
    )
    result = await weakest_concepts(db_session, user_id=uuid.UUID(user["id"]), topic_id=topic.id)
    assert [c.id for c in result] == [concepts[0].id]


async def test_solid_and_new_concepts_are_excluded(db_session, register_user, topic_with_concepts):
    user = await register_user()
    _, topic, _ = await topic_with_concepts(
        user["id"],
        [
            ("Solid", {"reps": 3, "last_grade": "good", "lapses": 0}),
            ("Untouched", None),
        ],
    )
    result = await weakest_concepts(db_session, user_id=uuid.UUID(user["id"]), topic_id=topic.id)
    assert result == []


async def test_relearning_state_counts_as_shaky(db_session, register_user, topic_with_concepts):
    user = await register_user()
    _, topic, concepts = await topic_with_concepts(
        user["id"], [("Diffusion", {"reps": 4, "last_grade": "good", "fsrs_state": 3, "lapses": 1})]
    )
    result = await weakest_concepts(db_session, user_id=uuid.UUID(user["id"]), topic_id=topic.id)
    assert [c.id for c in result] == [concepts[0].id]


async def test_sorted_by_lapses_descending(db_session, register_user, topic_with_concepts):
    user = await register_user()
    _, topic, concepts = await topic_with_concepts(
        user["id"],
        [
            ("Low", {"reps": 2, "last_grade": "again", "lapses": 1}),
            ("High", {"reps": 5, "last_grade": "again", "lapses": 4}),
        ],
    )
    result = await weakest_concepts(db_session, user_id=uuid.UUID(user["id"]), topic_id=topic.id)
    assert [c.text for c in result] == ["High", "Low"]


async def test_limit_is_respected(db_session, register_user, topic_with_concepts):
    user = await register_user()
    _, topic, _ = await topic_with_concepts(
        user["id"],
        [(f"C{i}", {"reps": 2, "last_grade": "again", "lapses": i}) for i in range(7)],
    )
    result = await weakest_concepts(db_session, user_id=uuid.UUID(user["id"]), topic_id=topic.id, limit=3)
    assert len(result) == 3


async def test_scoped_to_topic_does_not_leak_other_topics(db_session, register_user, topic_with_concepts):
    user = await register_user()
    _, topic_a, _ = await topic_with_concepts(
        user["id"], [("InA", {"reps": 2, "last_grade": "again", "lapses": 1})], topic_title="A"
    )
    _, topic_b, _ = await topic_with_concepts(
        user["id"], [("InB", {"reps": 2, "last_grade": "again", "lapses": 9})], topic_title="B"
    )
    result = await weakest_concepts(db_session, user_id=uuid.UUID(user["id"]), topic_id=topic_a.id)
    assert [c.text for c in result] == ["InA"]


async def test_does_not_leak_another_users_concept_state(db_session, register_user, topic_with_concepts):
    owner = await register_user()
    other = await register_user()
    _, topic, _ = await topic_with_concepts(
        owner["id"], [("Shared", {"reps": 2, "last_grade": "again", "lapses": 5})]
    )
    result = await weakest_concepts(db_session, user_id=uuid.UUID(other["id"]), topic_id=topic.id)
    assert result == []


# ── recent_wrong_answers ──────────────────────────────────────────────────────


def _user(name: str) -> User:
    return User(email=f"{name.lower()}_{uuid.uuid4().hex[:6]}@t.dev", full_name=name, password_hash="x", phone=unique_phone())


@pytest_asyncio.fixture
async def concept_ctx(db_session):
    async def _make():
        uid = uuid.uuid4()
        user = User(id=uid, email=f"u_{uuid.uuid4().hex[:6]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
        db_session.add(user)
        await db_session.flush()
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        topic = Topic(course_id=course.id, title="T")
        db_session.add(topic)
        await db_session.flush()
        concept = Concept(topic_id=topic.id, course_id=course.id, text="ATP", order_index=0)
        db_session.add(concept)
        await db_session.flush()
        await db_session.commit()
        return user, concept

    return _make


async def _add_attempt(db_session, *, user_id, concept_id, grade, prompt, response, created_at):
    db_session.add(
        RetrievalAttempt(
            user_id=user_id,
            concept_id=concept_id,
            mode="quiz",
            outcome_score=0.0 if grade == "again" else 1.0,
            grade=grade,
            challenge={"prompt": prompt},
            response=response,
            created_at=created_at,
        )
    )
    await db_session.commit()


async def test_only_missed_attempts_are_included(db_session, concept_ctx):
    user, concept = await concept_ctx()
    now = datetime.utcnow()
    await _add_attempt(
        db_session, user_id=user.id, concept_id=concept.id, grade="again",
        prompt="What does ATP do?", response={"raw": "stores fat"}, created_at=now,
    )
    await _add_attempt(
        db_session, user_id=user.id, concept_id=concept.id, grade="good",
        prompt="What does ATP do?", response={"raw": "energy currency"}, created_at=now,
    )
    result = await recent_wrong_answers(db_session, user_id=user.id, concept_id=concept.id)
    assert len(result) == 1
    assert result[0] == {"question": "What does ATP do?", "your_answer": "stores fat"}


async def test_most_recent_first_and_limit_respected(db_session, concept_ctx):
    user, concept = await concept_ctx()
    base = datetime.utcnow()
    for i in range(4):
        await _add_attempt(
            db_session, user_id=user.id, concept_id=concept.id, grade="again",
            prompt=f"Q{i}", response={"raw": f"A{i}"}, created_at=base - timedelta(minutes=4 - i),
        )
    result = await recent_wrong_answers(db_session, user_id=user.id, concept_id=concept.id, limit=2)
    assert [r["question"] for r in result] == ["Q3", "Q2"]


async def test_skips_attempts_with_no_recorded_prompt(db_session, concept_ctx):
    user, concept = await concept_ctx()
    db_session.add(
        RetrievalAttempt(
            user_id=user.id, concept_id=concept.id, mode="quiz",
            outcome_score=0.0, grade="again", challenge=None, response={"raw": "x"},
        )
    )
    await db_session.commit()
    result = await recent_wrong_answers(db_session, user_id=user.id, concept_id=concept.id)
    assert result == []


async def test_non_dict_response_is_used_as_is(db_session, concept_ctx):
    """MCQ-style responses may be structured (a dict without 'raw', e.g. {'choice': 'B'})."""
    user, concept = await concept_ctx()
    db_session.add(
        RetrievalAttempt(
            user_id=user.id, concept_id=concept.id, mode="quiz",
            outcome_score=0.0, grade="again", challenge={"prompt": "Pick one"},
            response={"choice": "B"},
        )
    )
    await db_session.commit()
    result = await recent_wrong_answers(db_session, user_id=user.id, concept_id=concept.id)
    assert result == [{"question": "Pick one", "your_answer": {"choice": "B"}}]
