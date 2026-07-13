"""
Next-best-action selector (B3) — the one engine behind home (pull) + digest (push).

Pins the strict cascade (review → calibration → new → get_ahead), scope, the
never-empty-handed contract, and that review picks the topic with the most fading concepts.
"""

import uuid
from datetime import datetime, timedelta

from app.models import Concept, Course, CourseEnrollment, Topic, User
from app.models.retrieval import ConceptState, RetrievalAttempt
from app.models.subject import SubjectFamily
from app.services.retrieval import next_action
from app.services.retrieval.next_action import select_next_action
from tests.conftest import unique_phone

NOW = datetime(2026, 7, 13, 12, 0, 0)


async def _seed(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    db.add(CourseEnrollment(user_id=user.id, course_id=course.id))
    topic = Topic(course_id=course.id, title="Krebs Cycle", order_index=0)
    db.add(topic)
    await db.flush()
    return user, course, topic


async def _concept(db, topic, course, text="c", order=0):
    c = Concept(topic_id=topic.id, course_id=course.id, text=text, order_index=order)
    db.add(c)
    await db.flush()
    return c


async def _state(db, user, concept, *, due):
    db.add(ConceptState(user_id=user.id, concept_id=concept.id, due=due, reps=1))
    await db.flush()


async def _attempt(db, user, concept, *, predicted, grade, created_at=NOW):
    a = RetrievalAttempt(
        user_id=user.id, concept_id=concept.id, mode="quiz",
        predicted_confidence=predicted, grade=grade,
    )
    a.created_at = created_at
    db.add(a)
    await db.flush()


# ── The cascade ───────────────────────────────────────────────────────────────

async def test_review_wins_when_concepts_are_due(db_session):
    user, course, topic = await _seed(db_session)
    c = await _concept(db_session, topic, course, text="citrate")
    await _state(db_session, user, c, due=NOW - timedelta(days=1))  # overdue → fading

    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action is not None
    assert action.kind == "review"
    assert action.mode == "quiz"
    assert str(c.id) in [str(x) for x in action.concept_ids]
    assert "Krebs Cycle" in action.reason


async def test_falls_through_to_calibration_when_nothing_due(db_session):
    user, course, topic = await _seed(db_session)
    c = await _concept(db_session, topic, course, text="isocitrate")
    await _state(db_session, user, c, due=NOW + timedelta(days=3))       # not due → no review
    await _attempt(db_session, user, c, predicted=0.9, grade="again")     # confident but missed

    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action is not None
    assert action.kind == "calibration"
    assert "recheck" in action.reason.lower()


async def test_falls_through_to_new_when_no_state(db_session):
    user, course, topic = await _seed(db_session)
    await _concept(db_session, topic, course, text="fumarate")  # enrolled, never attempted

    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action is not None
    assert action.kind == "new"
    assert action.mode == "pretest"  # new material opens with a pretest


async def test_get_ahead_when_all_scheduled_and_none_due(db_session):
    user, course, topic = await _seed(db_session)
    c = await _concept(db_session, topic, course, text="malate")
    await _state(db_session, user, c, due=NOW + timedelta(days=5))  # scheduled, not due, not new

    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action is not None
    assert action.kind == "get_ahead"


async def test_returns_none_when_no_concepts_at_all(db_session):
    user, course, topic = await _seed(db_session)
    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action is None


# ── Ranking + scope ─────────────────────────────────────────────────────────────

async def test_review_picks_topic_with_most_fading(db_session):
    user, course, topic_a = await _seed(db_session)
    topic_b = Topic(course_id=course.id, title="Glycolysis", order_index=1)
    db_session.add(topic_b)
    await db_session.flush()

    # topic_a: 1 due concept; topic_b: 2 due concepts → b wins
    ca = await _concept(db_session, topic_a, course, text="a1")
    await _state(db_session, user, ca, due=NOW - timedelta(days=1))
    for i in range(2):
        cb = await _concept(db_session, topic_b, course, text=f"b{i}")
        await _state(db_session, user, cb, due=NOW - timedelta(days=1))

    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action.topic_id == topic_b.id
    assert len(action.concept_ids) == 2


async def test_scope_restricts_to_course(db_session):
    user, course, topic = await _seed(db_session)
    c = await _concept(db_session, topic, course, text="due-here")
    await _state(db_session, user, c, due=NOW - timedelta(days=1))

    other_course_id = uuid.uuid4()
    action = await select_next_action(
        db_session, user_id=user.id, course_id=other_course_id, now=NOW
    )
    assert action is None  # nothing due in the (empty) scoped course


# ── Subject family drives the suggested mode (B4) ─────────────────────────────────

async def _due_topic_with_family(db, family):
    """A topic of the given family with one overdue concept for its enrolled user."""
    user, course, topic = await _seed(db)
    topic.subject_family = family
    await db.flush()
    c = await _concept(db, topic, course, text="c")
    await _state(db, user, c, due=NOW - timedelta(days=1))
    return user


async def test_stem_review_uses_quiz(db_session):
    user = await _due_topic_with_family(db_session, SubjectFamily.STEM)
    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action.kind == "review"
    assert action.mode == "quiz"  # STEM's worked-example / calibration lead


async def test_language_review_uses_ramble(db_session):
    user = await _due_topic_with_family(db_session, SubjectFamily.LANGUAGE)
    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action.kind == "review"
    assert action.mode == "ramble"  # output-first family leans to free recall


async def test_humanities_review_uses_teach(db_session):
    user = await _due_topic_with_family(db_session, SubjectFamily.HUMANITIES)
    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action.kind == "review"
    assert action.mode == "teach"  # explanation-heavy family leans to teaching


async def test_new_material_stays_pretest_regardless_of_family(db_session):
    """'new' is a pedagogical invariant (answer-before-study) — family can't override it."""
    user, course, topic = await _seed(db_session)
    topic.subject_family = SubjectFamily.LANGUAGE
    await db_session.flush()
    await _concept(db_session, topic, course, text="unseen")  # no state → new

    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action.kind == "new"
    assert action.mode == "pretest"


async def test_est_minutes_bounded(db_session):
    user, course, topic = await _seed(db_session)
    for i in range(50):  # way more than a session bite
        c = await _concept(db_session, topic, course, text=f"c{i}", order=i)
        await _state(db_session, user, c, due=NOW - timedelta(days=1))

    action = await select_next_action(db_session, user_id=user.id, now=NOW)
    assert action.kind == "review"
    assert len(action.concept_ids) <= next_action._MAX_CONCEPTS_PER_ACTION
    assert next_action._MIN_MINUTES <= action.est_minutes <= next_action._MAX_MINUTES
