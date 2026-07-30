"""
Session summary — the warm close. Derived from the attempt log over the most recent
session (≥15-min idle gap). Reports firmed / slipping concepts + the calibration delta.
"""

import uuid
from datetime import datetime, timedelta

from app.models import Concept, Course, Topic, User
from app.services.retrieval import engine, session_summary
from app.services.retrieval.modes import Outcome
from tests.conftest import unique_phone


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


async def _log(db, user, concept, when, *, grade="good", score=1.0, predicted=None):
    result = await engine.record_attempt(
        db, user_id=user.id, concept_id=concept.id, mode="fake",
        outcome=Outcome(score=score, grade=grade), predicted_confidence=predicted, now=when,
    )
    result.attempt.created_at = when
    await db.flush()
    return result


async def test_none_without_any_session(db_session):
    user, _, _, _ = await _seed(db_session)
    assert await session_summary.build_session_summary(db_session, user.id) is None


async def test_firmed_vs_slipping(db_session):
    user, _, topic, concepts = await _seed(db_session)
    base = datetime(2026, 1, 1, 9, 0, 0)
    # One good (→ solid), one lapse (→ shaky), close together = one session.
    await _log(db_session, user, concepts[0], base, grade="good", score=1.0)
    await _log(db_session, user, concepts[1], base + timedelta(minutes=2), grade="again", score=0.0)

    summary = await session_summary.build_session_summary(db_session, user.id, now=base + timedelta(minutes=3))
    assert summary is not None
    assert summary.attempt_count == 2
    assert summary.concept_count == 2
    assert [c.concept_id for c in summary.firmed] == [str(concepts[0].id)]
    assert [c.concept_id for c in summary.slipping] == [str(concepts[1].id)]
    assert summary.firmed[0].state == "solid"
    assert summary.slipping[0].state == "shaky"


async def test_only_the_last_session_is_summarized(db_session):
    user, _, _, concepts = await _seed(db_session)
    base = datetime(2026, 1, 1, 9, 0, 0)
    # Old session an hour earlier — must be excluded.
    await _log(db_session, user, concepts[0], base, grade="good")
    await _log(db_session, user, concepts[1], base + timedelta(hours=1), grade="good")
    await _log(db_session, user, concepts[2], base + timedelta(hours=1, minutes=2), grade="again", score=0.0)

    summary = await session_summary.build_session_summary(db_session, user.id, now=base + timedelta(hours=2))
    assert summary.attempt_count == 2
    assert summary.concept_count == 2
    touched = {c.concept_id for c in summary.firmed + summary.slipping}
    assert touched == {str(concepts[1].id), str(concepts[2].id)}


async def test_calibration_delta_over_predicted_attempts(db_session):
    user, _, _, concepts = await _seed(db_session)
    base = datetime(2026, 1, 1, 9, 0, 0)
    # Predicted 0.2 but scored 1.0 (delta +0.8); one attempt with no prediction is ignored.
    await _log(db_session, user, concepts[0], base, grade="good", score=1.0, predicted=0.2)
    await _log(db_session, user, concepts[1], base + timedelta(minutes=1), grade="good", score=1.0, predicted=None)

    summary = await session_summary.build_session_summary(db_session, user.id, now=base + timedelta(minutes=2))
    assert summary.predicted_count == 1
    assert summary.calibration_delta == 0.8
    assert summary.calibration_label == "underconfident"


async def test_calibration_null_when_no_predictions(db_session):
    user, _, _, concepts = await _seed(db_session)
    base = datetime(2026, 1, 1, 9, 0, 0)
    await _log(db_session, user, concepts[0], base, grade="good")

    summary = await session_summary.build_session_summary(db_session, user.id, now=base + timedelta(minutes=1))
    assert summary.calibration_delta is None
    assert summary.calibration_label is None
    assert summary.predicted_count == 0


async def test_scoped_to_topic(db_session):
    user, course, topic, concepts = await _seed(db_session)
    other_topic = Topic(course_id=course.id, title="Other", order_index=1)
    db_session.add(other_topic)
    await db_session.flush()
    other = Concept(topic_id=other_topic.id, course_id=course.id, text="x", order_index=0)
    db_session.add(other)
    await db_session.flush()

    base = datetime(2026, 1, 1, 9, 0, 0)
    await _log(db_session, user, concepts[0], base, grade="good")
    await _log(db_session, user, other, base + timedelta(minutes=1), grade="again", score=0.0)

    summary = await session_summary.build_session_summary(db_session, user.id, topic_id=topic.id, now=base + timedelta(minutes=2))
    assert summary.concept_count == 1
    assert [c.concept_id for c in summary.firmed] == [str(concepts[0].id)]
    assert summary.slipping == []
