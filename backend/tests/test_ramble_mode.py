"""
RambleMode — free-recall mode.

The LLM boundary (``_analyze``) is stubbed so we test the real mapping: coverage →
grade, the blank-response short-circuit, and that it drives the engine end-to-end
producing a mode="ramble" attempt.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Concept, ConceptState, Course, RetrievalAttempt, Topic, User
from app.services.retrieval import engine
from app.services.retrieval.modes import ModeContext
from app.services.retrieval.ramble_mode import RambleMode


class StubRambleMode(RambleMode):
    """RambleMode with the LLM analysis replaced by a fixture."""

    def __init__(self, analysis: dict):
        self._analysis = analysis

    async def _analyze(self, concept, said, ctx):
        return self._analysis


async def test_generate_returns_open_prompt():
    mode = StubRambleMode({})
    challenge = await mode.generate(_concept(), ModeContext(db=None, user_id=None))
    assert "everything you understand" in challenge.prompt
    assert challenge.payload["free_recall"] is True


@pytest.mark.parametrize(
    "coverage,expected",
    [(0.2, "again"), (0.5, "hard"), (0.75, "good"), (0.95, "easy")],
)
async def test_coverage_maps_to_grade(coverage, expected):
    mode = StubRambleMode({"coverage": coverage, "feedback": "ok", "missed": ["m"]})
    ctx = ModeContext(db=None, user_id=None)
    concept = _concept()
    challenge = await mode.generate(concept, ctx)
    outcome = await mode.evaluate(concept, challenge, "I think it means...", ctx)
    assert outcome.grade == expected
    assert outcome.score == coverage
    assert outcome.detail["missed"] == ["m"]


async def test_blank_response_is_a_lapse_without_calling_llm():
    # An analyze() that would blow up proves we short-circuit before the LLM.
    class Boom(RambleMode):
        async def _analyze(self, concept, said, ctx):
            raise AssertionError("should not analyze a blank")

    ctx = ModeContext(db=None, user_id=None)
    concept = _concept()
    challenge = await Boom().generate(concept, ctx)
    outcome = await Boom().evaluate(concept, challenge, "   ", ctx)
    assert (outcome.grade, outcome.score) == ("again", 0.0)


async def test_ramble_drives_engine(db_session):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    course = Course(code="C1", name="C", created_by=user.id)
    db_session.add(course)
    await db_session.flush()
    topic = Topic(course_id=course.id, title="T")
    db_session.add(topic)
    await db_session.flush()
    concept = Concept(topic_id=topic.id, course_id=course.id, text="Entropy")
    db_session.add(concept)
    await db_session.flush()

    mode = StubRambleMode({"coverage": 0.8, "feedback": "solid", "missed": []})
    result = await engine.run_once(
        db_session, mode=mode, concept=concept, response="a full explanation",
        ctx=ModeContext(db=db_session, user_id=user.id), predicted_confidence=0.5,
    )
    assert result.outcome.grade == "good"

    attempt = (await db_session.execute(select(RetrievalAttempt))).scalars().one()
    assert attempt.mode == "ramble"
    assert attempt.predicted_confidence == 0.5
    state = (await db_session.execute(select(ConceptState))).scalars().one()
    assert state.reps == 1 and state.due is not None


def _concept():
    c = Concept(text="A concept", definition="def")
    c.id = uuid.uuid4()
    return c
