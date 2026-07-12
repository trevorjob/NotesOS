"""
QuizMode — the first retrieval-mode plugin.

The LLM boundary (``_generate_question`` / ``_grade``) is stubbed so we test the real
mapping logic: MCQ correctness → grade, open-answer score → grade, and that it drives
the engine end-to-end producing a mode="quiz" attempt.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Concept, ConceptState, Course, RetrievalAttempt, Topic, User
from app.services.retrieval import engine
from app.services.retrieval.modes import Challenge, ModeContext
from app.services.retrieval.quiz_mode import QuizMode, score_to_grade
from tests.conftest import unique_phone


class StubQuizMode(QuizMode):
    """QuizMode with the two LLM calls replaced by fixtures."""

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


@pytest.mark.parametrize(
    "score,expected",
    [(0.2, "again"), (0.5, "hard"), (0.6, "hard"), (0.75, "good"), (0.95, "easy")],
)
def test_score_to_grade_thresholds(score, expected):
    assert score_to_grade(score) == expected


async def test_generate_returns_challenge_from_question():
    mode = StubQuizMode(MCQ)
    challenge = await mode.generate(_concept(), ModeContext(db=None, user_id=None))
    assert challenge.prompt == "Which best explains X?"
    assert challenge.payload["correct_answer"] == "B"


async def test_mcq_correct_is_good_wrong_is_again():
    mode = StubQuizMode(MCQ)
    ctx = ModeContext(db=None, user_id=None)
    concept = _concept()
    challenge = await mode.generate(concept, ctx)

    right = await mode.evaluate(concept, challenge, "B", ctx)
    assert (right.grade, right.score) == ("good", 1.0)

    wrong = await mode.evaluate(concept, challenge, "A", ctx)
    assert (wrong.grade, wrong.score) == ("again", 0.0)


async def test_short_answer_uses_grader_score():
    q = {"question_text": "Explain X.", "question_type": "short_answer", "correct_answer": "Key points: a / b"}
    mode = StubQuizMode(q, grade_result={"score": 8, "feedback": "solid"})
    ctx = ModeContext(db=None, user_id=None)
    concept = _concept()
    challenge = await mode.generate(concept, ctx)

    outcome = await mode.evaluate(concept, challenge, "my answer", ctx)
    assert outcome.score == 0.8
    assert outcome.grade == "good"
    assert outcome.feedback == "solid"


async def test_quiz_mode_drives_engine(db_session):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
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

    mode = StubQuizMode(MCQ)
    result = await engine.run_once(
        db_session, mode=mode, concept=concept, response="B",
        ctx=ModeContext(db=db_session, user_id=user.id), predicted_confidence=0.6,
    )
    assert result.outcome.grade == "good"

    attempt = (await db_session.execute(select(RetrievalAttempt))).scalars().one()
    assert attempt.mode == "quiz"
    assert attempt.predicted_confidence == 0.6
    state = (await db_session.execute(select(ConceptState))).scalars().one()
    assert state.reps == 1 and state.due is not None


def _concept():
    c = Concept(text="A concept", definition="def")
    c.id = uuid.uuid4()
    return c
