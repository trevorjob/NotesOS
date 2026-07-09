"""
PretestMode — quiz-before-encoding.

It subclasses QuizMode, so we reuse the same LLM-stub pattern. The behaviour to pin is
the scheduling cap: a correct pretest answer must land at ``good``, never ``easy``, so a
pre-study guess can't fling the concept into the future.
"""

import uuid

from sqlalchemy import select

from app.models import Concept, ConceptState, Course, RetrievalAttempt, Topic, User
from app.services.retrieval import engine
from app.services.retrieval.modes import ModeContext
from app.services.retrieval.pretest_mode import PretestMode


class StubPretestMode(PretestMode):
    def __init__(self, question: dict, grade_result: dict | None = None):
        self._question = question
        self._grade_result = grade_result or {}

    async def _generate_question(self, concept, ctx):
        return self._question

    async def _grade(self, concept, challenge, answer, ctx):
        return self._grade_result


MCQ = {
    "question_text": "Which best explains X?",
    "question_type": "mcq",
    "answer_options": ["A", "B", "C", "D"],
    "correct_answer": "B",
    "explanation": "Because B.",
}


async def test_generate_tags_pretest():
    mode = StubPretestMode(MCQ)
    challenge = await mode.generate(_concept(), ModeContext(db=None, user_id=None))
    assert challenge.payload["pretest"] is True
    assert challenge.payload["correct_answer"] == "B"  # quiz payload preserved


async def test_correct_mcq_is_good_not_easy():
    mode = StubPretestMode(MCQ)
    ctx = ModeContext(db=None, user_id=None)
    c = _concept()
    challenge = await mode.generate(c, ctx)
    right = await mode.evaluate(c, challenge, "B", ctx)
    assert (right.grade, right.score) == ("good", 1.0)  # MCQ already tops out at good


async def test_high_open_score_capped_at_good():
    # An open answer that would score 'easy' (>=0.9) must be clamped to 'good' for pretest.
    q = {"question_text": "Explain X.", "question_type": "short_answer", "correct_answer": "Key points: a / b"}
    mode = StubPretestMode(q, grade_result={"score": 10, "feedback": "perfect"})
    ctx = ModeContext(db=None, user_id=None)
    c = _concept()
    challenge = await mode.generate(c, ctx)
    outcome = await mode.evaluate(c, challenge, "a great answer", ctx)
    assert outcome.score == 1.0
    assert outcome.grade == "good"  # would be 'easy' under plain quiz mapping


async def test_pretest_drives_engine(db_session):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    course = Course(code="C1", name="C", created_by=user.id)
    db_session.add(course)
    await db_session.flush()
    topic = Topic(course_id=course.id, title="T")
    db_session.add(topic)
    await db_session.flush()
    concept = Concept(topic_id=topic.id, course_id=course.id, text="X")
    db_session.add(concept)
    await db_session.flush()

    mode = StubPretestMode(MCQ)
    result = await engine.run_once(
        db_session, mode=mode, concept=concept, response="B",
        ctx=ModeContext(db=db_session, user_id=user.id), predicted_confidence=0.2,
    )
    assert result.outcome.grade == "good"
    attempt = (await db_session.execute(select(RetrievalAttempt))).scalars().one()
    assert attempt.mode == "pretest"
    assert attempt.predicted_confidence == 0.2
    state = (await db_session.execute(select(ConceptState))).scalars().one()
    assert state.reps == 1 and state.due is not None


def _concept():
    c = Concept(text="A concept", definition="def")
    c.id = uuid.uuid4()
    return c
