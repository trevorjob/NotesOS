"""
Session derivation — sessions are a *query* over the attempt log, not a table.

Two layers: the pure ``split_sessions`` (cuts on a ≥15-min idle gap) and the DB-facing
``get_sessions`` / ``last_session`` (scoped, newest-first).
"""

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.models import Concept, Course, Topic, User
from app.services.retrieval import engine, session
from app.services.retrieval.session import SESSION_IDLE_GAP, split_sessions
from tests.conftest import unique_phone


# ── Pure split ─────────────────────────────────────────────────────────────────


def _att(minutes: float, concept="c1", mode="quiz"):
    """A stand-in attempt at ``minutes`` past a fixed epoch."""
    base = datetime(2026, 1, 1, 12, 0, 0)
    return SimpleNamespace(created_at=base + timedelta(minutes=minutes), concept_id=concept, mode=mode)


def test_empty_log_has_no_sessions():
    assert split_sessions([]) == []


def test_contiguous_attempts_are_one_session():
    attempts = [_att(0), _att(5), _att(14)]  # every gap < 15 min
    sessions = split_sessions(attempts)
    assert len(sessions) == 1
    assert sessions[0].attempt_count == 3


def test_gap_at_or_over_threshold_splits():
    # 15 min exactly closes the session (≥ gap).
    attempts = [_att(0), _att(15), _att(20)]
    sessions = split_sessions(attempts)
    assert len(sessions) == 2
    assert [s.attempt_count for s in sessions] == [1, 2]


def test_session_dedupes_concepts_in_first_touched_order():
    attempts = [_att(0, "a"), _att(1, "b"), _att(2, "a"), _att(3, "c")]
    sessions = split_sessions(attempts)
    assert sessions[0].concept_ids == ["a", "b", "c"]


def test_session_counts_modes():
    attempts = [_att(0, mode="quiz"), _att(1, mode="quiz"), _att(2, mode="ramble")]
    sessions = split_sessions(attempts)
    assert sessions[0].modes == {"quiz": 2, "ramble": 1}


def test_gap_constant_is_fifteen_minutes():
    assert SESSION_IDLE_GAP == timedelta(minutes=15)


# ── DB-facing derivation ───────────────────────────────────────────────────────


async def _seed(db, *, n_concepts=3):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="T", order_index=0)
    db.add(topic)
    await db.flush()
    concepts = []
    for i in range(n_concepts):
        c = Concept(topic_id=topic.id, course_id=course.id, text=f"c{i}", order_index=i)
        db.add(c)
        concepts.append(c)
    await db.flush()
    return user, course, topic, concepts


async def _log(db, user, concept, when):
    """Append one attempt at an explicit time (mode 'fake', good grade)."""
    from app.services.retrieval.modes import Outcome

    result = await engine.record_attempt(
        db, user_id=user.id, concept_id=concept.id, mode="fake",
        outcome=Outcome(score=1.0, grade="good"), now=when,
    )
    # record_attempt stamps created_at at flush via the default; force our time.
    result.attempt.created_at = when
    await db.flush()
    return result


async def test_get_sessions_splits_two_study_blocks(db_session):
    user, course, topic, concepts = await _seed(db_session)
    base = datetime(2026, 1, 1, 9, 0, 0)
    # Block 1: two attempts close together. Block 2: an hour later.
    await _log(db_session, user, concepts[0], base)
    await _log(db_session, user, concepts[1], base + timedelta(minutes=5))
    await _log(db_session, user, concepts[2], base + timedelta(hours=1))

    sessions = await session.get_sessions(db_session, user.id)
    assert len(sessions) == 2
    # Newest-first.
    assert sessions[0].attempt_count == 1
    assert sessions[1].attempt_count == 2


async def test_last_session_returns_the_most_recent(db_session):
    user, course, topic, concepts = await _seed(db_session)
    base = datetime(2026, 1, 1, 9, 0, 0)
    await _log(db_session, user, concepts[0], base)
    await _log(db_session, user, concepts[1], base + timedelta(hours=2))
    await _log(db_session, user, concepts[2], base + timedelta(hours=2, minutes=3))

    last = await session.last_session(db_session, user.id)
    assert last is not None
    assert last.attempt_count == 2
    assert set(last.concept_ids) == {str(concepts[1].id), str(concepts[2].id)}


async def test_last_session_is_none_without_attempts(db_session):
    user, course, topic, concepts = await _seed(db_session)
    assert await session.last_session(db_session, user.id) is None


async def test_sessions_scope_to_topic(db_session):
    user, course, topic, concepts = await _seed(db_session)
    other_topic = Topic(course_id=course.id, title="Other", order_index=1)
    db_session.add(other_topic)
    await db_session.flush()
    other_concept = Concept(topic_id=other_topic.id, course_id=course.id, text="x", order_index=0)
    db_session.add(other_concept)
    await db_session.flush()

    base = datetime(2026, 1, 1, 9, 0, 0)
    await _log(db_session, user, concepts[0], base)
    await _log(db_session, user, other_concept, base + timedelta(minutes=1))

    scoped = await session.get_sessions(db_session, user.id, topic_id=topic.id)
    assert sum(s.attempt_count for s in scoped) == 1
    assert scoped[0].concept_ids == [str(concepts[0].id)]
