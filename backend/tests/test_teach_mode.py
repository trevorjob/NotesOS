"""
TeachMode — protégé / explain-it mode.

The LLM judgement (``_judge``) is stubbed. We test the three-axis → score mapping
(including the correctness cap), the blank short-circuit, and end-to-end engine drive.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Concept, ConceptState, Course, RetrievalAttempt, Topic, User
from app.services.retrieval import engine
from app.services.retrieval.modes import ModeContext
from app.services.retrieval.teach_mode import TeachMode


class StubTeachMode(TeachMode):
    def __init__(self, judgement: dict):
        self._judgement = judgement

    async def _judge(self, concept, explanation, ctx):
        return self._judgement


async def test_generate_returns_teach_prompt():
    challenge = await StubTeachMode({}).generate(_concept(), ModeContext(db=None, user_id=None))
    assert "teaching it to a classmate" in challenge.prompt
    assert challenge.payload["teach"] is True


async def test_three_axis_mean_when_correct():
    mode = StubTeachMode({"correctness": 0.9, "completeness": 0.9, "clarity": 0.9, "feedback": "great"})
    ctx = ModeContext(db=None, user_id=None)
    c = _concept()
    outcome = await mode.evaluate(c, await mode.generate(c, ctx), "an explanation", ctx)
    assert outcome.score == pytest.approx(0.9)
    assert outcome.grade == "easy"


async def test_low_correctness_caps_the_score():
    # Fluent but wrong: clarity/completeness high, correctness low → capped at correctness.
    mode = StubTeachMode({"correctness": 0.3, "completeness": 1.0, "clarity": 1.0, "feedback": "off"})
    ctx = ModeContext(db=None, user_id=None)
    c = _concept()
    outcome = await mode.evaluate(c, await mode.generate(c, ctx), "confident nonsense", ctx)
    assert outcome.score == pytest.approx(0.3)  # min(0.3, mean=0.766) = 0.3
    assert outcome.grade == "again"


async def test_blank_is_a_lapse():
    class Boom(TeachMode):
        async def _judge(self, concept, explanation, ctx):
            raise AssertionError("should not judge a blank")

    ctx = ModeContext(db=None, user_id=None)
    c = _concept()
    outcome = await Boom().evaluate(c, await Boom().generate(c, ctx), "", ctx)
    assert (outcome.grade, outcome.score) == ("again", 0.0)


async def test_teach_drives_engine(db_session):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    course = Course(code="C1", name="C", created_by=user.id)
    db_session.add(course)
    await db_session.flush()
    topic = Topic(course_id=course.id, title="T")
    db_session.add(topic)
    await db_session.flush()
    concept = Concept(topic_id=topic.id, course_id=course.id, text="Recursion")
    db_session.add(concept)
    await db_session.flush()

    mode = StubTeachMode({"correctness": 0.8, "completeness": 0.8, "clarity": 0.8, "feedback": "clear"})
    result = await engine.run_once(
        db_session, mode=mode, concept=concept, response="you call the function inside itself...",
        ctx=ModeContext(db=db_session, user_id=user.id),
    )
    assert result.outcome.grade == "good"
    attempt = (await db_session.execute(select(RetrievalAttempt))).scalars().one()
    assert attempt.mode == "teach"
    state = (await db_session.execute(select(ConceptState))).scalars().one()
    assert state.reps == 1 and state.due is not None


def _concept():
    c = Concept(text="A concept", definition="def")
    c.id = uuid.uuid4()
    return c
