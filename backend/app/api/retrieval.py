"""
NotesOS API - Retrieval Engine Router.

The HTTP surface that drives a retrieval session over the pass-1 engine. A session is
two requests, exactly as ``engine.run_once``'s docstring anticipates:

  POST /next     — pick a concept, have the mode *generate* a challenge, return it
                   (sanitized), and stash the full challenge server-side.
  POST /attempt  — the user submits their predicted confidence + response; we *evaluate*
                   and *record* the attempt, fire the recognition seam, and return the
                   outcome, the new schedule, and the calibration (predicted vs actual).

The split exists so predicted confidence is captured *between* seeing the challenge and
answering — the calibration signal (Learning Science Parts 4, 8) depends on that gap.
The full challenge (which for quiz/pretest contains the correct answer) is held in Redis
under an opaque ``challenge_id``, never sent to the client, and dropped on attempt.
"""

import json
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, verify_course_enrollment
from app.database import get_db
from app.models.course import Topic
from app.models.retrieval import Concept
from app.models.subject import SubjectFamily
from app.models.user import User
from app.services import paper
from app.services.audio_generator import audio_generator
from app.services.redis_client import redis_client
from app.services.retrieval import dump, engine, next_action, recap, recognition, registry, session
from app.services.retrieval import session_summary, subject_profiles, worked
from app.services.retrieval.modes import (
    MAX_CONVO_TURNS,
    ROLE_AI,
    ROLE_USER,
    Challenge,
    ConversationTurn,
    ModeContext,
    is_conversational,
    user_turns,
)

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])

# Payload keys a challenge holds for grading but the client must not see (it'd be the
# answer key). Stripped from what /next returns; kept in the server-side copy. The
# worked solution + expected value (B9) are the STEM answer key — surfaced only at
# /reveal, after the confidence prediction is captured.
_SENSITIVE_PAYLOAD_KEYS = ("correct_answer", "explanation", "worked_solution", "expected_value", "tolerance")
_CHALLENGE_TTL_SEC = 1800  # 30 min to answer before the challenge expires


# ── Schemas ──────────────────────────────────────────────────────────────────

class NextRequest(BaseModel):
    mode: str
    scope: str = engine.SCOPE_TOPIC
    topic_id: Optional[uuid.UUID] = None
    course_id: Optional[uuid.UUID] = None
    concept_id: Optional[uuid.UUID] = None  # skip selection, challenge a specific concept


class NextResponse(BaseModel):
    challenge_id: str
    concept_id: str
    concept_text: str   # the concept term, so a continuous session can label each challenge
    mode: str
    prompt: str
    payload: dict
    # teach / ramble run a back-and-forth: the client drives /turn instead of /attempt.
    conversational: bool = False


class AttemptRequest(BaseModel):
    challenge_id: str
    response: Any = None
    predicted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Paper substrate (B8): "paper" marks a response the user transcribed-and-confirmed
    # from a handwriting photo. A marker only — never an image field; /attempt stays
    # text-only (LOCKED). Folded into the recorded challenge payload for the log.
    answer_origin: Optional[Literal["paper"]] = None


class Calibration(BaseModel):
    predicted: Optional[float]
    actual: float
    delta: Optional[float]      # actual − predicted; >0 underconfident, <0 overconfident
    label: Optional[str]


class AttemptResponse(BaseModel):
    concept_id: str
    mode: str
    outcome: dict
    state: dict
    calibration: Calibration


class TurnRequest(BaseModel):
    challenge_id: str
    message: str = ""   # the user's latest turn (may be blank — a stall is a close signal)
    # Predicted confidence is captured at open, before talking — stamped on the first turn.
    predicted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    end: bool = False   # user tapped done; grade what we have


class TurnResponse(BaseModel):
    """One step of a conversational bout: either the AI's next probe, or the graded close.

    While ``closed`` is false the client keeps the loop going (show ``reply``, capture the
    next turn). On close the outcome / state / calibration land here — the single graded
    attempt, exactly as ``/attempt`` returns for one-shot modes. No trailing call needed.
    """

    challenge_id: str
    closed: bool
    turn_count: int                      # user turns so far
    reply: Optional[str] = None          # AI's next probe, when not closed
    close_reason: Optional[str] = None
    concept_id: Optional[str] = None
    mode: Optional[str] = None
    outcome: Optional[dict] = None
    state: Optional[dict] = None
    calibration: Optional[Calibration] = None


class RevealRequest(BaseModel):
    challenge_id: str
    # Captured *here*, before the solution is visible — the entire calibration guarantee.
    predicted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class RevealResponse(BaseModel):
    """The withheld worked solution for a STEM self-calibration problem (B9).

    Returned only once and only after the confidence prediction is stamped in — the
    student solves on paper, predicts, reveals, then self-grades through /attempt.
    """

    question_type: str
    worked_solution: Optional[str]


class ModeInfo(BaseModel):
    key: str
    affinity: float   # how strongly this mode suits the requested subject family (0..1)


class SubjectProfileResponse(BaseModel):
    topic_id: str
    subject_family: SubjectFamily
    overridden: bool
    render: str
    grading: str
    mode_mix: dict[str, float]


class SubjectFamilyUpdate(BaseModel):
    subject_family: SubjectFamily


class SessionInfo(BaseModel):
    started_at: str
    ended_at: str
    attempt_count: int
    concept_ids: list[str]
    modes: dict[str, int]


class RecapNextRequest(BaseModel):
    topic_id: uuid.UUID


class RecapNextResponse(BaseModel):
    challenge_id: str
    topic_id: str
    topic_title: str
    prompt: str
    concept_count: int


class RecapAttemptRequest(BaseModel):
    challenge_id: str
    response: Any = None
    predicted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Paper substrate (B8) — see AttemptRequest.answer_origin. Handwritten dumps are
    # the paper-native study pattern this exists for.
    answer_origin: Optional[Literal["paper"]] = None


class TranscribeResponse(BaseModel):
    """A handwriting transcription, pending the user's confirmation (B8).

    ``requires_confirmation`` is always true — the confirm/correct beat is the contract
    (grade what the user confirms they wrote, never what OCR guessed), mirrored in the
    shape so a client can't silently skip it. The flags point the user at exactly the
    spots the model wasn't sure about.
    """

    transcription: str
    requires_confirmation: Literal[True] = True
    page_count: int
    has_uncertain: bool
    has_illegible: bool


class RecapConceptOutcome(BaseModel):
    concept_id: str
    concept_text: str
    score: float
    grade: str
    feedback: Optional[str]
    covered: list
    missed: list
    due: Optional[str]


class RecapAttemptResponse(BaseModel):
    mode: str
    topic_id: str
    concept_count: int
    mean_score: float
    outcomes: list[RecapConceptOutcome]


class NextActionResponse(BaseModel):
    kind: str
    course_id: str
    topic_id: str
    topic_title: str
    concept_ids: list[str]
    mode: str
    reason: str
    est_minutes: int


class SessionSummaryConcept(BaseModel):
    concept_id: str
    concept_text: str
    state: str          # current mastery: solid / fading / shaky
    attempts: int
    mean_score: float


class SessionSummaryResponse(BaseModel):
    """The warm close (§6): what the last session changed. ``null`` when there's no session."""

    started_at: str
    ended_at: str
    attempt_count: int
    concept_count: int
    firmed: list[SessionSummaryConcept]      # solid now — lead with these
    slipping: list[SessionSummaryConcept]    # shaky / fading — whisper these
    calibration_delta: Optional[float]
    calibration_label: Optional[str]
    predicted_count: int


# ── Challenge store (server-side, opaque handoff between the two requests) ─────

def _challenge_key(challenge_id: str) -> str:
    return f"retrieval:challenge:{challenge_id}"


async def _store_challenge(user_id, concept: Concept, mode_key: str, challenge: Challenge) -> str:
    challenge_id = uuid.uuid4().hex
    record = {
        "user_id": str(user_id),
        "concept_id": str(concept.id),
        "mode": mode_key,
        "prompt": challenge.prompt,
        "payload": challenge.payload,
    }
    client = await redis_client.get_client()
    await client.set(_challenge_key(challenge_id), json.dumps(record), ex=_CHALLENGE_TTL_SEC)
    return challenge_id


async def _load_challenge(challenge_id: str) -> Optional[dict]:
    client = await redis_client.get_client()
    raw = await client.get(_challenge_key(challenge_id))
    return json.loads(raw) if raw else None


async def _update_challenge(challenge_id: str, record: dict) -> None:
    """Re-store a challenge record under the same id (B9 /reveal stamps confidence into it)."""
    client = await redis_client.get_client()
    await client.set(_challenge_key(challenge_id), json.dumps(record), ex=_CHALLENGE_TTL_SEC)


async def _drop_challenge(challenge_id: str) -> None:
    client = await redis_client.get_client()
    await client.delete(_challenge_key(challenge_id))


# A free-recall turn (recap / brain dump) holds a *set* of concepts (not one), so it
# gets its own record shape under a per-kind key namespace — same opaque-handoff pattern
# as the single-concept store. ``kind`` keeps a recap challenge unplayable as a dump.
def _free_recall_key(kind: str, challenge_id: str) -> str:
    return f"retrieval:{kind}:{challenge_id}"


async def _store_free_recall(kind: str, user_id, topic_id, challenge: recap.RecapChallenge) -> str:
    challenge_id = uuid.uuid4().hex
    record = {
        "user_id": str(user_id),
        "topic_id": str(topic_id),
        "prompt": challenge.prompt,
        "concept_ids": challenge.concept_ids,
    }
    client = await redis_client.get_client()
    await client.set(_free_recall_key(kind, challenge_id), json.dumps(record), ex=_CHALLENGE_TTL_SEC)
    return challenge_id


async def _load_free_recall(kind: str, challenge_id: str) -> Optional[dict]:
    client = await redis_client.get_client()
    raw = await client.get(_free_recall_key(kind, challenge_id))
    return json.loads(raw) if raw else None


async def _drop_free_recall(kind: str, challenge_id: str) -> None:
    client = await redis_client.get_client()
    await client.delete(_free_recall_key(kind, challenge_id))


# A conversational bout (teach / ramble) holds a running transcript instead of a single
# challenge. Same opaque-handoff pattern + key namespace as the one-shot store; the record
# carries the history and the confidence stamped at the first turn.
async def _store_conversation(user_id, concept: Concept, mode_key: str, challenge: Challenge) -> str:
    challenge_id = uuid.uuid4().hex
    record = {
        "user_id": str(user_id),
        "concept_id": str(concept.id),
        "mode": mode_key,
        "prompt": challenge.prompt,
        "conversational": True,
        "predicted_confidence": None,
        "history": [{"role": ROLE_AI, "text": challenge.prompt}],
    }
    client = await redis_client.get_client()
    await client.set(_challenge_key(challenge_id), json.dumps(record), ex=_CHALLENGE_TTL_SEC)
    return challenge_id


def _history_from_record(record: dict) -> list[ConversationTurn]:
    return [ConversationTurn(role=t["role"], text=t["text"]) for t in record.get("history", [])]


def _history_to_json(history: list[ConversationTurn]) -> list[dict]:
    return [{"role": t.role, "text": t.text} for t in history]


def _sanitize(payload: Optional[dict]) -> dict:
    return {k: v for k, v in (payload or {}).items() if k not in _SENSITIVE_PAYLOAD_KEYS}


def _outcome_dict(outcome) -> dict:
    return {"score": outcome.score, "grade": outcome.grade, "feedback": outcome.feedback, "detail": outcome.detail}


def _state_dict(state) -> dict:
    return {
        "due": state.due.isoformat() if state.due else None,
        "reps": state.reps,
        "lapses": state.lapses,
        "stability": state.stability,
        "difficulty": state.difficulty,
        "last_grade": state.last_grade,
    }


def _calibration(predicted: Optional[float], actual: float) -> Calibration:
    if predicted is None:
        return Calibration(predicted=None, actual=actual, delta=None, label=None)
    delta = actual - predicted
    if delta > 0.15:
        label = "underconfident"   # did better than they thought — the good surprise
    elif delta < -0.15:
        label = "overconfident"    # the fluency illusion; the one worth flagging
    else:
        label = "calibrated"
    return Calibration(predicted=predicted, actual=actual, delta=delta, label=label)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/next", response_model=NextResponse)
async def next_challenge(
    body: NextRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pick a concept and have the requested mode pose a challenge for it."""
    mode = _get_mode_or_400(body.mode)

    if body.concept_id is not None:
        concept = await db.get(Concept, body.concept_id)
        if concept is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "concept not found")
    else:
        try:
            concepts = await engine.select_concepts(
                db, user_id=user.id, scope=body.scope,
                topic_id=body.topic_id, course_id=body.course_id, limit=1,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        if not concepts:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no concepts available for this scope")
        concept = concepts[0]

    await verify_course_enrollment(db, user.id, concept.course_id)

    # The concept inherits its topic's subject family; hand the mode both the family and
    # its profile's grading *directive* (B9). Modes branch on the directive, never the
    # family enum — so STEM's self_calibration serves a worked problem here.
    family = await _topic_family(db, concept.topic_id)
    profile = subject_profiles.profile_for(family)
    ctx = ModeContext(
        db=db, user_id=user.id,
        extra={"subject_family": family.value, "grading": profile.grading},
    )
    challenge = await mode.generate(concept, ctx)
    conversational = is_conversational(mode)
    if conversational:
        challenge_id = await _store_conversation(user.id, concept, mode.key, challenge)
    else:
        challenge_id = await _store_challenge(user.id, concept, mode.key, challenge)

    return NextResponse(
        challenge_id=challenge_id,
        concept_id=str(concept.id),
        concept_text=concept.text,
        mode=mode.key,
        prompt=challenge.prompt,
        payload=_sanitize(challenge.payload),
        conversational=conversational,
    )


@router.post("/attempt", response_model=AttemptResponse)
async def submit_attempt(
    body: AttemptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate + record the user's response; return outcome, schedule, calibration."""
    record = await _load_challenge(body.challenge_id)
    if record is None:
        raise HTTPException(status.HTTP_410_GONE, "challenge expired or not found")
    if record["user_id"] != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your challenge")

    concept = await db.get(Concept, uuid.UUID(record["concept_id"]))
    if concept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "concept no longer exists")
    await verify_course_enrollment(db, user.id, concept.course_id)

    mode = _get_mode_or_400(record["mode"])
    payload = record["payload"] or {}
    challenge = Challenge(
        concept_id=record["concept_id"], prompt=record["prompt"], payload=payload
    )
    ctx = ModeContext(db=db, user_id=user.id)

    # A worked problem (B9) is self-graded: the solution must have been revealed first
    # (ordering is the calibration guarantee), and the confidence was captured *at* reveal
    # — not now, when the student already knows how they did.
    is_self_graded = payload.get("question_type") == worked.WORKED_TYPE
    if is_self_graded and not record.get("revealed"):
        raise HTTPException(status.HTTP_409_CONFLICT, "reveal the solution before self-grading")
    predicted_confidence = record.get("predicted_confidence") if is_self_graded else body.predicted_confidence

    try:
        outcome = await mode.evaluate(concept, challenge, body.response, ctx)
    except worked.InvalidSelfGrade as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    recorded_challenge = {"prompt": challenge.prompt, **payload}
    if body.answer_origin:  # paper substrate (B8): note the confirmed-handwriting origin
        recorded_challenge["origin"] = body.answer_origin
    result = await engine.record_attempt(
        db,
        user_id=user.id,
        concept_id=concept.id,
        mode=mode.key,
        outcome=outcome,
        predicted_confidence=predicted_confidence,
        challenge=recorded_challenge,
        response=body.response if isinstance(body.response, (dict, list)) else {"raw": body.response},
    )
    await recognition.on_attempt(db, attempt=result.attempt, concept=concept, learner_id=user.id)
    await _drop_challenge(body.challenge_id)

    return AttemptResponse(
        concept_id=str(concept.id),
        mode=mode.key,
        outcome=_outcome_dict(outcome),
        state=_state_dict(result.state),
        calibration=_calibration(predicted_confidence, outcome.score),
    )


@router.post("/turn", response_model=TurnResponse)
async def conversation_turn(
    body: TurnRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Advance a conversational bout (teach / ramble): dig one more turn, or grade and close.

    One graded attempt still lands, at close — the dialogue is scaffolding before that single
    commit (design note §2). Close fires on the mode's call, the user tapping done, or the
    ``MAX_CONVO_TURNS`` ceiling, whichever comes first.
    """
    record = await _load_challenge(body.challenge_id)
    if record is None:
        raise HTTPException(status.HTTP_410_GONE, "conversation expired or not found")
    if record["user_id"] != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your conversation")
    if not record.get("conversational"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not a conversational challenge — use /attempt")

    concept = await db.get(Concept, uuid.UUID(record["concept_id"]))
    if concept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "concept no longer exists")
    await verify_course_enrollment(db, user.id, concept.course_id)

    mode = _get_mode_or_400(record["mode"])
    ctx = ModeContext(db=db, user_id=user.id)

    # Confidence is captured once, at the first turn — before the well is graded.
    if body.predicted_confidence is not None and record.get("predicted_confidence") is None:
        record["predicted_confidence"] = body.predicted_confidence

    history = _history_from_record(record)
    history.append(ConversationTurn(role=ROLE_USER, text=body.message))
    turns_taken = len(user_turns(history))

    if body.end:
        closed, reason, reply = True, "user_ended", None
    elif turns_taken >= MAX_CONVO_TURNS:
        closed, reason, reply = True, "turn_cap", None
    else:
        decision = await mode.turn(concept, history, ctx)
        closed, reason, reply = decision.closed, decision.close_reason, decision.reply

    if not closed:
        history.append(ConversationTurn(role=ROLE_AI, text=reply or ""))
        record["history"] = _history_to_json(history)
        await _update_challenge(body.challenge_id, record)
        return TurnResponse(
            challenge_id=body.challenge_id, closed=False, turn_count=turns_taken, reply=reply,
        )

    predicted = record.get("predicted_confidence")
    outcome = await mode.close(concept, history, ctx)
    result = await engine.record_attempt(
        db,
        user_id=user.id,
        concept_id=concept.id,
        mode=mode.key,
        outcome=outcome,
        predicted_confidence=predicted,
        challenge={"prompt": record["prompt"], "conversational": True, "turns": turns_taken},
        response={"transcript": _history_to_json(history)},
    )
    await recognition.on_attempt(db, attempt=result.attempt, concept=concept, learner_id=user.id)
    await _drop_challenge(body.challenge_id)

    return TurnResponse(
        challenge_id=body.challenge_id,
        closed=True,
        turn_count=turns_taken,
        close_reason=reason,
        concept_id=str(concept.id),
        mode=mode.key,
        outcome=_outcome_dict(outcome),
        state=_state_dict(result.state),
        calibration=_calibration(predicted, outcome.score),
    )


@router.post("/reveal", response_model=RevealResponse)
async def reveal_solution(
    body: RevealRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Capture the confidence prediction, then reveal a worked problem's solution (B9).

    One-shot and strictly ordered: the prediction is stamped into the cached challenge
    *before* the solution is returned, and a second reveal is a 409. Only worked
    (self-graded) problems reveal this way — numeric/conceptual are judged at /attempt.
    """
    record = await _load_challenge(body.challenge_id)
    if record is None:
        raise HTTPException(status.HTTP_410_GONE, "challenge expired or not found")
    if record["user_id"] != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your challenge")

    payload = record["payload"] or {}
    if payload.get("question_type") != worked.WORKED_TYPE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "this challenge has no worked solution to reveal")
    if record.get("revealed"):
        raise HTTPException(status.HTTP_409_CONFLICT, "solution already revealed")

    record["revealed"] = True
    record["predicted_confidence"] = body.predicted_confidence
    await _update_challenge(body.challenge_id, record)

    return RevealResponse(
        question_type=worked.WORKED_TYPE,
        worked_solution=payload.get("worked_solution"),
    )


@router.get("/modes", response_model=list[ModeInfo])
async def list_modes(
    family: SubjectFamily = SubjectFamily.GENERAL,
    user: User = Depends(get_current_user),
):
    """Available modes and how strongly each suits a subject ``family`` (the mode mix knob)."""
    return [
        ModeInfo(key=key, affinity=subject_profiles.mode_affinity(family, key))
        for key in registry.available_modes()
    ]


async def _topic_family(db: AsyncSession, topic_id) -> SubjectFamily:
    """The subject family of a topic (GENERAL if the topic somehow can't be found)."""
    fam = await db.scalar(select(Topic.subject_family).where(Topic.id == topic_id))
    return fam or SubjectFamily.GENERAL


@router.get("/topics/{topic_id}/profile", response_model=SubjectProfileResponse)
async def get_subject_profile(
    topic_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A topic's subject profile: its family + the rendering / mode-mix / grading it drives."""
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "topic not found")
    await verify_course_enrollment(db, user.id, topic.course_id)
    return _profile_response(topic)


@router.patch("/topics/{topic_id}/profile", response_model=SubjectProfileResponse)
async def override_subject_family(
    topic_id: uuid.UUID,
    body: SubjectFamilyUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually set a topic's subject family. Locks it — re-synthesis won't overwrite it."""
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "topic not found")
    await verify_course_enrollment(db, user.id, topic.course_id)
    topic.subject_family = body.subject_family
    topic.subject_family_overridden = True
    await db.commit()
    await db.refresh(topic)
    return _profile_response(topic)


def _profile_response(topic: Topic) -> SubjectProfileResponse:
    profile = subject_profiles.profile_for(topic.subject_family)
    return SubjectProfileResponse(
        topic_id=str(topic.id),
        subject_family=topic.subject_family,
        overridden=topic.subject_family_overridden,
        render=profile.render,
        grading=profile.grading,
        mode_mix=profile.mode_mix,
    )


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    course_id: Optional[uuid.UUID] = None,
    topic_id: Optional[uuid.UUID] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """This user's study sessions, newest-first — derived from the attempt log.

    There is no session table: a session is a run of attempts with no ≥15-min idle
    gap. Optionally scoped to a course or topic.
    """
    sessions = await session.get_sessions(
        db, user.id, course_id=course_id, topic_id=topic_id
    )
    return [
        SessionInfo(
            started_at=s.started_at.isoformat(),
            ended_at=s.ended_at.isoformat(),
            attempt_count=s.attempt_count,
            concept_ids=s.concept_ids,
            modes=s.modes,
        )
        for s in sessions
    ]


@router.get("/next-action", response_model=Optional[NextActionResponse])
async def get_next_action(
    course_id: Optional[uuid.UUID] = None,
    topic_id: Optional[uuid.UUID] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The single highest-value thing to study now (the home doorway / digest engine).

    Strict cascade: review (fading) → calibration (confident-but-missed) → new → get_ahead.
    Optionally scoped to a course/topic. ``null`` when the user has no concepts yet — the
    client sends them to capture rather than showing an empty study surface.
    """
    if course_id is not None:
        await verify_course_enrollment(db, user.id, course_id)

    action = await next_action.select_next_action(
        db, user_id=user.id, course_id=course_id, topic_id=topic_id
    )
    if action is None:
        return None
    return NextActionResponse(
        kind=action.kind,
        course_id=str(action.course_id),
        topic_id=str(action.topic_id),
        topic_title=action.topic_title,
        concept_ids=[str(c) for c in action.concept_ids],
        mode=action.mode,
        reason=action.reason,
        est_minutes=action.est_minutes,
    )


_TTS_MAX_CHARS = 400
_TTS_VOICE = "nova"


@router.get("/tts")
async def synthesize_probe(text: str, user: User = Depends(get_current_user)):
    """Stream a short conversational probe aloud (teach / ramble voice-out).

    Proxies the shared OpenAI-TTS provider as a live MP3 stream — playback starts before the
    clip finishes, no server-side buffering. Bounded to a short probe, NOT the long-audio path
    (that's the async audio_worker → Cloudinary). A courtesy layer: the loop reads fine
    text-first if voice is unavailable.
    """
    clean = text.strip()
    if not clean:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "text is required")
    return StreamingResponse(
        audio_generator.stream_speech(clean[:_TTS_MAX_CHARS], voice=_TTS_VOICE),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/session-summary", response_model=Optional[SessionSummaryResponse])
async def get_session_summary(
    course_id: Optional[uuid.UUID] = None,
    topic_id: Optional[uuid.UUID] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The warm close for the user's most recent session — what it firmed / left slipping.

    Derived from the attempt log (uncached, per-user). ``null`` when the user has no
    session yet. Optionally scoped to a course/topic.
    """
    if course_id is not None:
        await verify_course_enrollment(db, user.id, course_id)

    summary = await session_summary.build_session_summary(
        db, user_id=user.id, course_id=course_id, topic_id=topic_id
    )
    if summary is None:
        return None
    return SessionSummaryResponse(
        started_at=summary.started_at.isoformat(),
        ended_at=summary.ended_at.isoformat(),
        attempt_count=summary.attempt_count,
        concept_count=summary.concept_count,
        firmed=[_summary_concept(c) for c in summary.firmed],
        slipping=[_summary_concept(c) for c in summary.slipping],
        calibration_delta=summary.calibration_delta,
        calibration_label=summary.calibration_label,
        predicted_count=summary.predicted_count,
    )


def _summary_concept(c: session_summary.ConceptChange) -> SessionSummaryConcept:
    return SessionSummaryConcept(
        concept_id=c.concept_id,
        concept_text=c.concept_text,
        state=c.state,
        attempts=c.attempts,
        mean_score=c.mean_score,
    )


# Recap and brain dump are two surfaces of one free-recall machine (product-map, LOCKED
# 2026-07-17): same handoff, same grader — only the opener and the logged mode differ.

async def _open_free_recall(user, topic_id, *, kind: str, challenge: recap.RecapChallenge) -> RecapNextResponse:
    challenge_id = await _store_free_recall(kind, user.id, topic_id, challenge)
    return RecapNextResponse(
        challenge_id=challenge_id,
        topic_id=str(topic_id),
        topic_title=challenge.topic_title,
        prompt=challenge.prompt,
        concept_count=len(challenge.concept_ids),
    )


async def _grade_free_recall(
    db, user, body: RecapAttemptRequest, *, kind: str, mode_key: str
) -> RecapAttemptResponse:
    """Shared second beat: load the handoff, grade the monologue, one attempt per concept."""
    record = await _load_free_recall(kind, body.challenge_id)
    if record is None:
        raise HTTPException(status.HTTP_410_GONE, f"{kind} expired or not found")
    if record["user_id"] != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"not your {kind}")

    topic_id = uuid.UUID(record["topic_id"])
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "topic no longer exists")
    await verify_course_enrollment(db, user.id, topic.course_id)

    results = await recap.grade_recap(
        db,
        user.id,
        concept_ids=record["concept_ids"],
        response=body.response,
        prompt=record.get("prompt"),
        predicted_confidence=body.predicted_confidence,
        mode_key=mode_key,
        origin=body.answer_origin,
    )
    await _drop_free_recall(kind, body.challenge_id)

    outcomes = [
        RecapConceptOutcome(
            concept_id=str(r.concept.id),
            concept_text=r.concept.text,
            score=r.result.outcome.score,
            grade=r.result.outcome.grade,
            feedback=r.result.outcome.feedback,
            covered=r.result.outcome.detail.get("covered", []),
            missed=r.result.outcome.detail.get("missed", []),
            due=r.result.state.due.isoformat() if r.result.state.due else None,
        )
        for r in results
    ]
    mean_score = (
        sum(o.score for o in outcomes) / len(outcomes) if outcomes else 0.0
    )
    return RecapAttemptResponse(
        mode=mode_key,
        topic_id=str(topic_id),
        concept_count=len(outcomes),
        mean_score=mean_score,
        outcomes=outcomes,
    )


async def _topic_or_404(db, user, topic_id) -> Topic:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "topic not found")
    await verify_course_enrollment(db, user.id, topic.course_id)
    return topic


@router.post("/recap/next", response_model=RecapNextResponse)
async def recap_next(
    body: RecapNextRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Open a recap of the last session in a topic: one uncued free-recall prompt."""
    await _topic_or_404(db, user, body.topic_id)
    try:
        challenge = await recap.build_recap(db, user.id, topic_id=body.topic_id)
    except recap.NoRecapAvailable as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return await _open_free_recall(user, body.topic_id, kind="recap", challenge=challenge)


@router.post("/recap/attempt", response_model=RecapAttemptResponse)
async def recap_attempt(
    body: RecapAttemptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grade one free-recall response into an append-only attempt per concept."""
    return await _grade_free_recall(db, user, body, kind="recap", mode_key=recap.RECAP_MODE)


@router.post("/dump/next", response_model=RecapNextResponse)
async def dump_next(
    body: RecapNextRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Open a brain dump: everything you know about the topic, one uncued prompt.

    409 when the topic has no concepts yet — there's nothing to dump against until
    synthesis has extracted a concept set.
    """
    await _topic_or_404(db, user, body.topic_id)
    try:
        challenge = await dump.build_dump(db, topic_id=body.topic_id)
    except dump.NoDumpAvailable as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return await _open_free_recall(user, body.topic_id, kind="dump", challenge=challenge)


@router.post("/dump/attempt", response_model=RecapAttemptResponse)
async def dump_attempt(
    body: RecapAttemptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grade the dump monologue against the topic's full concept set — attempt per concept."""
    return await _grade_free_recall(db, user, body, kind="dump", mode_key=dump.DUMP_MODE)


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_paper_answer(
    files: list[UploadFile] = File(...),
    _user: User = Depends(get_current_user),  # auth gate only — transcription is user-scoped, not course-scoped
):
    """Turn a photographed handwritten answer into text for the user to confirm (B8).

    The paper substrate's single seam: photo(s) in page order → transcription out. The
    client shows the transcription for the user to **confirm or correct**, then submits
    the confirmed text through the normal ``/attempt`` / ``/recap/attempt`` /
    ``/dump/attempt`` flow with ``answer_origin="paper"``. Photos are ephemeral — never
    stored; only what the user confirms is ever graded.
    """
    images = [(f.filename or "", await f.read()) for f in files]
    try:
        result = await paper.transcribe_answer(images)
    except paper.PaperValidationError as exc:
        raise HTTPException(exc.status, str(exc))
    return TranscribeResponse(
        transcription=result.text,
        page_count=result.page_count,
        has_uncertain=result.has_uncertain,
        has_illegible=result.has_illegible,
    )


def _get_mode_or_400(key: str):
    try:
        return registry.get_mode(key)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
