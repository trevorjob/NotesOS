"""
NotesOS API — Authored practice tests (B14).

The "generate a test" surface, rebuilt **as a composition over the retrieval engine**
so a test *feeds* spaced repetition instead of running beside it. Two front doors, one
new: the **builder** (pick scope + count + type → generate → share) and the **runner**
(take a shared test → per-question → derived summary). Both are thin over the atom.

  POST /api/practice-tests                      — author a set (202, async generation)
  GET  /api/practice-tests?course_id=…          — the course's shared tests
  GET  /api/practice-tests/{id}                 — a test + its questions (answer key stripped)
  POST /api/practice-tests/{id}/questions/{qid}/answer — grade one → a per-concept attempt
  GET  /api/practice-tests/{id}/result          — the derived session summary (nothing stored)

The generation is bounded and concept-anchored; taking a test writes ordinary
``RetrievalAttempt`` rows through ``engine.record_attempt`` (FSRS / calibration /
recognition) — no new grade path, no stored score. See build-guide §4 B14.
"""

import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Reuse the retrieval router's answer-key sanitization + calibration — one source of
# truth (a shared test must never leak its key, exactly like /next).
from app.api.retrieval import _SENSITIVE_PAYLOAD_KEYS, _calibration
from app.api.auth import get_current_user, verify_course_enrollment
from app.database import get_db
from app.models.course import Course, Topic
from app.models.practice_test import (
    AUTHORED_MODES,
    GEN_GENERATING,
    GEN_READY,
    QUESTION_TYPES,
    PracticeTest,
    PracticeTestQuestion,
)
from app.models.retrieval import Concept, ConceptState, RetrievalAttempt
from app.models.user import User
from app.services.redis_client import redis_client
from app.services.retrieval import engine, recognition, registry
from app.services.retrieval.modes import Challenge, ModeContext

router = APIRouter(prefix="/api/practice-tests", tags=["practice-tests"])

# A firmed concept (in this test's run) vs. one still fading — for the derived summary.
_FIRMED_GRADES = ("good", "easy")


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateTestRequest(BaseModel):
    course_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    mode: str = "quiz"                       # quiz | pretest
    question_type: str = "mcq"               # mcq | short_answer | essay
    question_count: int = Field(default=10, ge=1, le=50)
    # An arbitrary topic subset of the course; empty ⇒ the whole course.
    topic_ids: List[uuid.UUID] = []


class TestSummary(BaseModel):
    id: str
    course_id: str
    created_by: str
    title: str
    mode: str
    question_type: str
    scope_topic_ids: List[str]
    question_count: int
    questions_done: int
    generation_status: str
    created_at: str


class QuestionOut(BaseModel):
    id: str
    concept_id: str
    order_index: int
    prompt: str
    payload: dict            # sanitized — no answer key


class TestDetail(TestSummary):
    questions: List[QuestionOut]


class AnswerRequest(BaseModel):
    response: Any = None
    predicted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AnswerResponse(BaseModel):
    concept_id: str
    mode: str
    outcome: dict
    state: dict
    calibration: dict


class ConceptResult(BaseModel):
    concept_id: str
    concept_text: str
    grade: Optional[str]
    score: Optional[float]
    due: Optional[str]


class TestResult(BaseModel):
    test_id: str
    question_count: int
    answered_count: int
    firmed_count: int          # concepts this run left in good/easy
    fading_count: int          # concepts still shaky (again/hard)
    mean_score: Optional[float]
    concepts: List[ConceptResult]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize(payload: Optional[dict]) -> dict:
    return {k: v for k, v in (payload or {}).items() if k not in _SENSITIVE_PAYLOAD_KEYS}


def _summary(test: PracticeTest) -> TestSummary:
    return TestSummary(
        id=str(test.id),
        course_id=str(test.course_id),
        created_by=str(test.created_by),
        title=test.title,
        mode=test.mode,
        question_type=test.question_type,
        scope_topic_ids=[str(t) for t in (test.scope_topic_ids or [])],
        question_count=test.question_count,
        questions_done=test.questions_done,
        generation_status=test.generation_status,
        created_at=test.created_at.isoformat(),
    )


async def _get_test_enrolled(db: AsyncSession, user: User, test_id: uuid.UUID) -> PracticeTest:
    test = await db.get(PracticeTest, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "test not found")
    await verify_course_enrollment(db, user.id, test.course_id)
    return test


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=TestSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_test(
    body: CreateTestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Author a practice test. Persists the shell + kicks off async generation.

    quiz/pretest only (the posed-question modes); ramble/teach/brain-dump are single-dump
    free recall and don't set-ify. Type is mcq/short_answer/essay. Scope is a topic subset
    or the whole course.
    """
    if body.mode not in AUTHORED_MODES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"mode must be one of {AUTHORED_MODES}; ramble/teach/brain-dump don't set-ify",
        )
    if body.question_type not in QUESTION_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"question_type must be one of {QUESTION_TYPES}"
        )

    course = await db.get(Course, body.course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "course not found")
    await verify_course_enrollment(db, user.id, body.course_id)

    # Every chosen topic must belong to the course (no cross-course scope leakage).
    if body.topic_ids:
        rows = (await db.execute(
            select(Topic.id).where(
                Topic.id.in_(body.topic_ids), Topic.course_id == body.course_id
            )
        )).scalars().all()
        if len(set(rows)) != len(set(body.topic_ids)):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "one or more topics are not in this course"
            )

    test = PracticeTest(
        course_id=body.course_id,
        created_by=user.id,
        title=body.title,
        mode=body.mode,
        question_type=body.question_type,
        scope_topic_ids=[str(t) for t in body.topic_ids],
        question_count=body.question_count,
        generation_status=GEN_GENERATING,
        questions_done=0,
    )
    db.add(test)
    await db.commit()
    await db.refresh(test)

    await redis_client.enqueue_job("practice_test", {"test_id": str(test.id)})
    return _summary(test)


@router.get("", response_model=List[TestSummary])
async def list_tests(
    course_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The shared tests for a course — everyone enrolled sees them (communal, like the note)."""
    await verify_course_enrollment(db, user.id, course_id)
    rows = (await db.execute(
        select(PracticeTest)
        .where(PracticeTest.course_id == course_id)
        .order_by(PracticeTest.created_at.desc())
    )).scalars().all()
    return [_summary(t) for t in rows]


@router.get("/{test_id}", response_model=TestDetail)
async def get_test(
    test_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A test and its questions — the answer key is stripped from every question."""
    test = await _get_test_enrolled(db, user, test_id)
    questions = (await db.execute(
        select(PracticeTestQuestion)
        .where(PracticeTestQuestion.test_id == test.id)
        .order_by(PracticeTestQuestion.order_index)
    )).scalars().all()
    detail = _summary(test).model_dump()
    detail["questions"] = [
        QuestionOut(
            id=str(q.id),
            concept_id=str(q.concept_id),
            order_index=q.order_index,
            prompt=q.prompt,
            payload=_sanitize(q.payload),
        )
        for q in questions
    ]
    return TestDetail(**detail)


@router.post("/{test_id}/questions/{question_id}/answer", response_model=AnswerResponse)
async def answer_question(
    test_id: uuid.UUID,
    question_id: uuid.UUID,
    body: AnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grade one answer and record it as a per-concept attempt — the atom feed.

    This is the exact review-loop path: ``mode.evaluate`` → ``engine.record_attempt`` →
    FSRS + calibration + recognition. No new grade path, no stored score. Each taker gets
    their own attempts over the shared questions.
    """
    test = await _get_test_enrolled(db, user, test_id)
    question = await db.get(PracticeTestQuestion, question_id)
    if question is None or question.test_id != test.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "question not found in this test")

    concept = await db.get(Concept, question.concept_id)
    if concept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "concept no longer exists")

    mode = registry.get_mode(test.mode)
    payload = dict(question.payload or {})
    challenge = Challenge(concept_id=str(concept.id), prompt=question.prompt, payload=payload)
    ctx = ModeContext(db=db, user_id=user.id)

    outcome = await mode.evaluate(concept, challenge, body.response, ctx)
    # Tag the recorded attempt with the test so the result summary is cleanly derivable
    # from the log (never a stored score).
    recorded_challenge = {"prompt": question.prompt, **payload, "practice_test_id": str(test.id)}
    result = await engine.record_attempt(
        db,
        user_id=user.id,
        concept_id=concept.id,
        mode=mode.key,
        outcome=outcome,
        predicted_confidence=body.predicted_confidence,
        challenge=recorded_challenge,
        response=body.response if isinstance(body.response, (dict, list)) else {"raw": body.response},
    )
    await recognition.on_attempt(db, attempt=result.attempt, concept=concept, learner_id=user.id)

    state = result.state
    return AnswerResponse(
        concept_id=str(concept.id),
        mode=mode.key,
        outcome={
            "score": outcome.score,
            "grade": outcome.grade,
            "feedback": outcome.feedback,
            "detail": outcome.detail,
        },
        state={
            "due": state.due.isoformat() if state.due else None,
            "reps": state.reps,
            "lapses": state.lapses,
            "stability": state.stability,
            "difficulty": state.difficulty,
            "last_grade": state.last_grade,
        },
        calibration=_calibration(body.predicted_confidence, outcome.score).model_dump(),
    )


@router.get("/{test_id}/result", response_model=TestResult)
async def get_result(
    test_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The derived summary of this user's run — aggregated from the attempt log, not stored.

    "8/10 — here's what firmed up / what's still fading." One row per test concept, using
    this user's latest attempt *tagged with this test* (so a test-taking run reads cleanly
    out of the append-only log without a test-attempt table).
    """
    test = await _get_test_enrolled(db, user, test_id)

    questions = (await db.execute(
        select(PracticeTestQuestion)
        .where(PracticeTestQuestion.test_id == test.id)
        .order_by(PracticeTestQuestion.order_index)
    )).scalars().all()
    concept_ids = [q.concept_id for q in questions]
    if not concept_ids:
        return TestResult(
            test_id=str(test.id), question_count=0, answered_count=0,
            firmed_count=0, fading_count=0, mean_score=None, concepts=[],
        )

    # Latest attempt per concept, restricted to this test (via the challenge tag).
    attempts = (await db.execute(
        select(RetrievalAttempt)
        .where(RetrievalAttempt.user_id == user.id)
        .where(RetrievalAttempt.concept_id.in_(concept_ids))
        .where(RetrievalAttempt.challenge["practice_test_id"].astext == str(test.id))
        .order_by(RetrievalAttempt.created_at.desc())
    )).scalars().all()
    latest: dict[uuid.UUID, RetrievalAttempt] = {}
    for a in attempts:
        latest.setdefault(a.concept_id, a)

    states = (await db.execute(
        select(ConceptState)
        .where(ConceptState.user_id == user.id)
        .where(ConceptState.concept_id.in_(concept_ids))
    )).scalars().all()
    due_by_concept = {s.concept_id: s.due for s in states}

    concept_texts = {
        c.id: c.text
        for c in (await db.execute(
            select(Concept).where(Concept.id.in_(concept_ids))
        )).scalars().all()
    }

    rows: list[ConceptResult] = []
    scores: list[float] = []
    firmed = fading = 0
    for cid in concept_ids:
        att = latest.get(cid)
        grade = att.grade if att else None
        score = att.outcome_score if att else None
        if att is not None:
            if score is not None:
                scores.append(score)
            if grade in _FIRMED_GRADES:
                firmed += 1
            else:
                fading += 1
        due = due_by_concept.get(cid)
        rows.append(ConceptResult(
            concept_id=str(cid),
            concept_text=concept_texts.get(cid, ""),
            grade=grade,
            score=score,
            due=due.isoformat() if due else None,
        ))

    return TestResult(
        test_id=str(test.id),
        question_count=len(concept_ids),
        answered_count=len(latest),
        firmed_count=firmed,
        fading_count=fading,
        mean_score=(sum(scores) / len(scores)) if scores else None,
        concepts=rows,
    )
