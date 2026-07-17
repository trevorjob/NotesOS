"""
STEM worked problems — self-calibration made real (B9).

The product-map's LOCKED launch dodge for STEM: give a problem → solve on paper →
predict confidence → reveal the full solution → self-grade. This pins the three pieces:

  * the pure grading substrate (``worked.py``) — self-grade → FSRS grade, numeric compare,
    both LLM-free;
  * the mode wiring — quiz/pretest generate a worked/numeric/conceptual problem when the
    topic's profile directive is ``self_calibration``, and never otherwise (regression);
  * the HTTP ordering — ``/next`` withholds the solution, ``/reveal`` captures the
    confidence *then* hands it back (one-shot), ``/attempt`` self-grades with zero LLM.

The generation LLM boundary (``QuizMode._generate_worked_problem`` / ``_generate_question``)
is monkeypatched throughout; the grading path is real (that's the point — no model in it).
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Concept, Course, CourseEnrollment, Topic
from app.models.retrieval import RetrievalAttempt
from app.models.subject import SubjectFamily
from app.services.redis_client import redis_client
from app.services.retrieval import worked
from app.services.retrieval.modes import Challenge, ModeContext
from app.services.retrieval.quiz_mode import QuizMode
from app.services.retrieval.subject_profiles import GRADE_SELF_CALIBRATION


# ── the pure grading substrate (no LLM, no DB) ───────────────────────────────────

@pytest.mark.parametrize(
    "self_grade,expected_grade,expected_score",
    [("again", "again", 0.0), ("hard", "hard", 0.4), ("good", "good", 0.75), ("easy", "easy", 1.0)],
)
def test_self_report_maps_1to1_onto_fsrs_grades(self_grade, expected_grade, expected_score):
    outcome = worked.grade_self_report(self_grade)
    assert outcome.grade == expected_grade
    assert outcome.score == expected_score
    assert outcome.detail["self_graded"] is True


def test_self_report_is_case_and_whitespace_tolerant():
    assert worked.grade_self_report("  Easy ").grade == "easy"


@pytest.mark.parametrize("bad", ["brilliant", "", "3", 4, None])
def test_self_report_rejects_out_of_vocabulary(bad):
    with pytest.raises(worked.InvalidSelfGrade):
        worked.grade_self_report(bad)


def test_numeric_correct_within_tolerance_caps_at_good():
    outcome = worked.grade_numeric("42.2", expected_value=42.0, tolerance=0.5, solution="steps")
    assert outcome.grade == "good" and outcome.score == 1.0  # right number ≠ proven method → not easy
    assert outcome.feedback == "steps"                       # worked-example effect lands after answering


def test_numeric_outside_tolerance_is_a_lapse():
    outcome = worked.grade_numeric("50", expected_value=42.0, tolerance=0.5)
    assert outcome.grade == "again" and outcome.score == 0.0


def test_numeric_unparseable_answer_is_a_lapse():
    outcome = worked.grade_numeric("dunno", expected_value=42.0, tolerance=0.5)
    assert outcome.grade == "again" and outcome.detail["reason"] == "unparseable"


def test_numeric_accepts_dict_and_bare_number_forms():
    assert worked.grade_numeric({"answer": 42}, expected_value=42.0, tolerance=0.1).grade == "good"
    assert worked.grade_numeric(41.95, expected_value=42.0, tolerance=0.1).grade == "good"


# ── the mode: directive drives generation, question_type drives evaluate ─────────

class _FakeConcept:
    id = uuid.uuid4()
    text = "Differentiate a composite function"
    definition = "chain rule: outer' × inner'"


def _self_calibration_ctx():
    return ModeContext(db=None, user_id=uuid.uuid4(), extra={"grading": GRADE_SELF_CALIBRATION})


async def test_generate_serves_worked_problem_under_self_calibration(monkeypatch):
    async def fake(self, concept, ctx):
        return {
            "question_text": r"Differentiate $f(x) = \sin(x^2)$.",
            "problem_type": "worked",
            "worked_solution": r"$f'(x) = 2x\cos(x^2)$ by the chain rule.",
        }

    monkeypatch.setattr(QuizMode, "_generate_worked_problem", fake)
    challenge = await QuizMode().generate(_FakeConcept(), _self_calibration_ctx())

    assert challenge.payload["question_type"] == "worked"
    assert "chain rule" in challenge.payload["worked_solution"]


async def test_generate_serves_numeric_problem_with_expected_value(monkeypatch):
    async def fake(self, concept, ctx):
        return {
            "question_text": "Compute the derivative of x^2 at x=3.",
            "problem_type": "numeric",
            "worked_solution": "f'(x)=2x, so 6.",
            "expected_value": 6.0,
            "tolerance": 0.01,
        }

    monkeypatch.setattr(QuizMode, "_generate_worked_problem", fake)
    challenge = await QuizMode().generate(_FakeConcept(), _self_calibration_ctx())

    assert challenge.payload["question_type"] == "numeric"
    assert challenge.payload["expected_value"] == 6.0


async def test_generate_falls_back_to_ai_graded_for_conceptual_stem(monkeypatch):
    """A concept that isn't solve-able stays AI-graded — self_calibration doesn't force a problem."""
    async def fake(self, concept, ctx):
        return {
            "question_text": "Why does the chain rule work?",
            "problem_type": "conceptual",
            "correct_answer": "Key points: composition / rates multiply",
            "explanation": "It composes rates of change.",
        }

    monkeypatch.setattr(QuizMode, "_generate_worked_problem", fake)
    challenge = await QuizMode().generate(_FakeConcept(), _self_calibration_ctx())

    assert challenge.payload["question_type"] == "short_answer"  # the normal AI-graded path
    assert "worked_solution" not in challenge.payload


async def test_generate_stays_normal_without_the_directive(monkeypatch):
    """No self_calibration directive → the untouched mcq path (the GENERAL regression)."""
    called = {}

    async def fake_worked(self, concept, ctx):
        called["worked"] = True
        return {}

    async def fake_question(self, concept, ctx):
        return {"question_text": "Q?", "question_type": "mcq", "answer_options": ["a", "b"], "correct_answer": "a"}

    monkeypatch.setattr(QuizMode, "_generate_worked_problem", fake_worked)
    monkeypatch.setattr(QuizMode, "_generate_question", fake_question)
    ctx = ModeContext(db=None, user_id=uuid.uuid4(), extra={"grading": "ai"})

    challenge = await QuizMode().generate(_FakeConcept(), ctx)
    assert challenge.payload["question_type"] == "mcq"
    assert "worked" not in called  # the worked generator was never reached


async def test_evaluate_worked_self_grades_without_an_llm():
    challenge = Challenge(concept_id="c", prompt="p", payload={"question_type": "worked", "worked_solution": "s"})
    outcome = await QuizMode().evaluate(_FakeConcept(), challenge, "good", ModeContext(db=None, user_id=1))
    assert outcome.grade == "good" and outcome.detail["self_graded"] is True


async def test_evaluate_numeric_compares_server_side():
    challenge = Challenge(
        concept_id="c", prompt="p",
        payload={"question_type": "numeric", "expected_value": 6.0, "tolerance": 0.01, "worked_solution": "s"},
    )
    outcome = await QuizMode().evaluate(_FakeConcept(), challenge, "6.0", ModeContext(db=None, user_id=1))
    assert outcome.grade == "good"


# ── the HTTP ordering: withhold → reveal(capture confidence) → self-grade ─────────

@pytest_asyncio.fixture(autouse=True)
async def _fresh_redis():
    redis_client._client = None
    yield
    if redis_client._client is not None:
        await redis_client._client.aclose()
        redis_client._client = None


@pytest_asyncio.fixture
async def seeded(db_session):
    async def _make(user_id, family=SubjectFamily.STEM):
        uid = uuid.UUID(user_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topic = Topic(course_id=course.id, title="Calculus", order_index=0, subject_family=family)
        db_session.add(topic)
        await db_session.flush()
        concept = Concept(topic_id=topic.id, course_id=course.id, text="Chain rule", order_index=0)
        db_session.add(concept)
        await db_session.flush()
        await db_session.commit()
        return course, topic, concept

    return _make


@pytest.fixture
def worked_gen(monkeypatch):
    """Stub the worked-problem generator; default to a self-graded worked problem."""
    def install(payload=None):
        payload = payload or {
            "question_text": r"Differentiate $\sin(x^2)$.",
            "problem_type": "worked",
            "worked_solution": r"$2x\cos(x^2)$",
        }

        async def fake(self, concept, ctx):
            return payload
        monkeypatch.setattr(QuizMode, "_generate_worked_problem", fake)

    return install


async def test_next_withholds_the_worked_solution(client, register_user, seeded, worked_gen):
    worked_gen()
    user = await register_user()
    _, _, concept = await seeded(user["id"])

    resp = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "quiz", "concept_id": str(concept.id)},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()["payload"]
    assert payload["question_type"] == "worked"
    assert "worked_solution" not in payload  # the answer key, stripped like correct_answer


async def test_reveal_captures_confidence_then_returns_solution_once(client, register_user, seeded, worked_gen):
    worked_gen()
    user = await register_user()
    _, _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"], json={"mode": "quiz", "concept_id": str(concept.id)},
    )).json()["challenge_id"]

    reveal = await client.post(
        "/api/retrieval/reveal", headers=user["headers"],
        json={"challenge_id": cid, "predicted_confidence": 0.9},
    )
    assert reveal.status_code == 200, reveal.text
    assert reveal.json()["worked_solution"] == r"$2x\cos(x^2)$"

    # One-shot: a second reveal is a conflict (can't re-predict after seeing the answer).
    again = await client.post(
        "/api/retrieval/reveal", headers=user["headers"],
        json={"challenge_id": cid, "predicted_confidence": 0.1},
    )
    assert again.status_code == 409


async def test_attempt_before_reveal_is_blocked(client, register_user, seeded, worked_gen):
    worked_gen()
    user = await register_user()
    _, _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"], json={"mode": "quiz", "concept_id": str(concept.id)},
    )).json()["challenge_id"]

    resp = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "good"},
    )
    assert resp.status_code == 409  # self-grading before revealing the solution is out of order


async def test_full_self_grade_loop_records_confidence_from_reveal(
    client, register_user, seeded, worked_gen, db_session
):
    """reveal(0.4) → self-grade 'easy': the attempt lands with the reveal-time confidence
    and a calibration delta, zero LLM in the evaluate path."""
    worked_gen()
    user = await register_user()
    _, _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"], json={"mode": "quiz", "concept_id": str(concept.id)},
    )).json()["challenge_id"]

    await client.post(
        "/api/retrieval/reveal", headers=user["headers"],
        json={"challenge_id": cid, "predicted_confidence": 0.4},
    )
    att = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "easy", "predicted_confidence": 0.99},  # body value ignored
    )
    assert att.status_code == 200, att.text
    body = att.json()
    assert body["outcome"]["grade"] == "easy"
    assert body["calibration"]["predicted"] == 0.4          # from reveal, not the attempt body
    assert body["calibration"]["label"] == "underconfident"  # predicted 0.4, actual 1.0

    attempt = await db_session.scalar(
        select(RetrievalAttempt).where(RetrievalAttempt.concept_id == concept.id)
    )
    assert attempt.grade == "easy"
    assert attempt.predicted_confidence == 0.4


async def test_invalid_self_grade_is_rejected(client, register_user, seeded, worked_gen):
    worked_gen()
    user = await register_user()
    _, _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"], json={"mode": "quiz", "concept_id": str(concept.id)},
    )).json()["challenge_id"]
    await client.post(
        "/api/retrieval/reveal", headers=user["headers"],
        json={"challenge_id": cid, "predicted_confidence": 0.5},
    )
    resp = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "pretty good tbh"},
    )
    assert resp.status_code == 400  # closed vocabulary — never coerced


async def test_numeric_problem_grades_server_side_without_reveal(client, register_user, seeded, worked_gen, db_session):
    worked_gen({
        "question_text": "d/dx x^2 at x=3?",
        "problem_type": "numeric",
        "worked_solution": "2x → 6",
        "expected_value": 6.0,
        "tolerance": 0.05,
    })
    user = await register_user()
    _, _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"], json={"mode": "quiz", "concept_id": str(concept.id)},
    )).json()["challenge_id"]

    att = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "6.02", "predicted_confidence": 0.7},
    )
    assert att.status_code == 200, att.text
    assert att.json()["outcome"]["grade"] == "good"  # within tolerance, no reveal needed

    attempt = await db_session.scalar(
        select(RetrievalAttempt).where(RetrievalAttempt.concept_id == concept.id)
    )
    assert attempt.predicted_confidence == 0.7  # numeric keeps the /attempt-time prediction


async def test_general_topic_quiz_is_unchanged(client, register_user, seeded, monkeypatch):
    """Regression: a GENERAL topic never touches the worked path — normal mcq, no worked keys."""
    async def fake_question(self, concept, ctx):
        return {"question_text": "Q?", "question_type": "mcq", "answer_options": ["a", "b"], "correct_answer": "a"}

    async def fake_worked(self, concept, ctx):
        raise AssertionError("worked generator must not run for a GENERAL topic")

    monkeypatch.setattr(QuizMode, "_generate_question", fake_question)
    monkeypatch.setattr(QuizMode, "_generate_worked_problem", fake_worked)

    user = await register_user()
    _, _, concept = await seeded(user["id"], family=SubjectFamily.GENERAL)
    resp = await client.post(
        "/api/retrieval/next", headers=user["headers"], json={"mode": "quiz", "concept_id": str(concept.id)},
    )
    payload = resp.json()["payload"]
    assert payload["question_type"] == "mcq"
    assert payload["answer_options"] == ["a", "b"]
    assert "worked_solution" not in payload and "correct_answer" not in payload


async def test_paper_origin_recorded_on_a_self_graded_attempt(client, register_user, seeded, worked_gen, db_session):
    """B8 fairness marker still flows: worked work photographed → self-grade carries origin='paper'."""
    worked_gen()
    user = await register_user()
    _, _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"], json={"mode": "quiz", "concept_id": str(concept.id)},
    )).json()["challenge_id"]
    await client.post(
        "/api/retrieval/reveal", headers=user["headers"],
        json={"challenge_id": cid, "predicted_confidence": 0.6},
    )
    att = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "hard", "answer_origin": "paper"},
    )
    assert att.status_code == 200, att.text
    attempt = await db_session.scalar(
        select(RetrievalAttempt).where(RetrievalAttempt.concept_id == concept.id)
    )
    assert attempt.challenge["origin"] == "paper"
    assert attempt.grade == "hard"
