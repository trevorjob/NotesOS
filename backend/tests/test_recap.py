"""
Recap orchestration — the many-concepts / one-turn stretch of the mode Protocol.

One free-recall monologue is graded into an **attempt per concept** (append-only), with
a concept the grader never mentions scored as a genuine miss (a lapse). The LLM boundary
``_analyze_recall`` is monkeypatched so the grader runs without a model.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Concept, Course, RetrievalAttempt, Topic, User
from app.services.retrieval import engine, recap
from app.services.retrieval.modes import Outcome
from tests.conftest import unique_phone


async def _seed(db, *, n_concepts=3):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="Cell Biology", order_index=0)
    db.add(topic)
    await db.flush()
    concepts = []
    for i in range(n_concepts):
        c = Concept(topic_id=topic.id, course_id=course.id, text=f"concept-{i}", order_index=i)
        db.add(c)
        concepts.append(c)
    await db.flush()
    return user, course, topic, concepts


async def _prior_session(db, user, concepts):
    """Log a quiz attempt on each concept so a 'last session' exists to recap."""
    for c in concepts:
        await engine.record_attempt(
            db, user_id=user.id, concept_id=c.id, mode="quiz",
            outcome=Outcome(score=1.0, grade="good"),
        )


# ── build_recap ────────────────────────────────────────────────────────────────


async def test_build_recap_raises_without_prior_session(db_session):
    user, course, topic, concepts = await _seed(db_session)
    with pytest.raises(recap.NoRecapAvailable):
        await recap.build_recap(db_session, user.id, topic_id=topic.id)


async def test_build_recap_covers_last_session_concepts(db_session):
    user, course, topic, concepts = await _seed(db_session)
    await _prior_session(db_session, user, concepts[:2])  # only two were studied

    challenge = await recap.build_recap(db_session, user.id, topic_id=topic.id)
    assert set(challenge.concept_ids) == {str(concepts[0].id), str(concepts[1].id)}
    assert challenge.topic_title == "Cell Biology"
    # Free recall is uncued — the prompt must not leak the concept text.
    assert "concept-0" not in challenge.prompt
    assert "2 idea" in challenge.prompt


# ── grade_recap ────────────────────────────────────────────────────────────────


async def test_grade_recap_records_one_attempt_per_concept(db_session, monkeypatch):
    user, course, topic, concepts = await _seed(db_session)
    cids = [str(c.id) for c in concepts]

    async def fake_analyze(cs, said):
        # Grader surfaces the first two well, ignores the third entirely.
        return [
            {"index": 1, "coverage": 0.95, "covered": ["got it"], "missed": [], "feedback": "solid"},
            {"index": 2, "coverage": 0.6, "covered": ["some"], "missed": ["a bit"], "feedback": "close"},
        ]

    monkeypatch.setattr(recap, "_analyze_recall", fake_analyze)

    results = await recap.grade_recap(
        db_session, user.id, concept_ids=cids, response="I remember the mitochondria...",
    )

    assert len(results) == 3
    # Append-only: three attempts written, all mode='recap'.
    attempts = (await db_session.execute(select(RetrievalAttempt))).scalars().all()
    assert len(attempts) == 3
    assert {a.mode for a in attempts} == {"recap"}

    by_concept = {str(r.concept.id): r.result.outcome for r in results}
    assert by_concept[cids[0]].grade == "easy"          # 0.95
    assert by_concept[cids[1]].grade == "hard"          # 0.6
    # The concept the grader never mentioned is a genuine miss → a lapse.
    assert by_concept[cids[2]].score == 0.0
    assert by_concept[cids[2]].grade == "again"


async def test_grade_recap_blank_response_is_all_lapses(db_session, monkeypatch):
    user, course, topic, concepts = await _seed(db_session)
    cids = [str(c.id) for c in concepts]

    called = False

    async def fake_analyze(cs, said):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(recap, "_analyze_recall", fake_analyze)

    results = await recap.grade_recap(db_session, user.id, concept_ids=cids, response="   ")

    assert called is False  # a blank monologue never reaches the model
    assert all(r.result.outcome.grade == "again" for r in results)
    assert all(r.result.state.lapses == 1 for r in results)


async def test_grade_recap_advances_the_fsrs_schedule(db_session, monkeypatch):
    user, course, topic, concepts = await _seed(db_session)
    cids = [str(concepts[0].id)]

    async def fake_analyze(cs, said):
        return [{"index": 1, "coverage": 1.0, "covered": [], "missed": [], "feedback": "great"}]

    monkeypatch.setattr(recap, "_analyze_recall", fake_analyze)

    results = await recap.grade_recap(db_session, user.id, concept_ids=cids, response="lots to say")
    state = results[0].result.state
    assert state.reps == 1
    assert state.due is not None
