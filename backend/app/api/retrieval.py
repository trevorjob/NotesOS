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
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, verify_course_enrollment
from app.database import get_db
from app.models.retrieval import Concept
from app.models.user import User
from app.services.redis_client import redis_client
from app.services.retrieval import engine, recognition, registry
from app.services.retrieval.modes import Challenge, ModeContext

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])

# Payload keys a challenge holds for grading but the client must not see (it'd be the
# answer key). Stripped from what /next returns; kept in the server-side copy.
_SENSITIVE_PAYLOAD_KEYS = ("correct_answer", "explanation")
_CHALLENGE_TTL_SEC = 1800  # 30 min to answer before the challenge expires


# ── Schemas ──────────────────────────────────────────────────────────────────

class NextRequest(BaseModel):
    mode: str
    scope: str = engine.SCOPE_TOPIC
    topic_id: Optional[uuid.UUID] = None
    course_id: Optional[uuid.UUID] = None
    concept_id: Optional[uuid.UUID] = None  # skip selection, challenge a specific concept
    subject_type: Optional[str] = None      # tunes the mode's subject weighting


class NextResponse(BaseModel):
    challenge_id: str
    concept_id: str
    mode: str
    prompt: str
    payload: dict


class AttemptRequest(BaseModel):
    challenge_id: str
    response: Any = None
    predicted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


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


class ModeInfo(BaseModel):
    key: str
    subject_weight: float


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


async def _drop_challenge(challenge_id: str) -> None:
    client = await redis_client.get_client()
    await client.delete(_challenge_key(challenge_id))


def _sanitize(payload: Optional[dict]) -> dict:
    return {k: v for k, v in (payload or {}).items() if k not in _SENSITIVE_PAYLOAD_KEYS}


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

    ctx = ModeContext(db=db, user_id=user.id, extra={"subject_type": body.subject_type})
    challenge = await mode.generate(concept, ctx)
    challenge_id = await _store_challenge(user.id, concept, mode.key, challenge)

    return NextResponse(
        challenge_id=challenge_id,
        concept_id=str(concept.id),
        mode=mode.key,
        prompt=challenge.prompt,
        payload=_sanitize(challenge.payload),
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
    challenge = Challenge(
        concept_id=record["concept_id"], prompt=record["prompt"], payload=record["payload"] or {}
    )
    ctx = ModeContext(db=db, user_id=user.id)

    outcome = await mode.evaluate(concept, challenge, body.response, ctx)
    result = await engine.record_attempt(
        db,
        user_id=user.id,
        concept_id=concept.id,
        mode=mode.key,
        outcome=outcome,
        predicted_confidence=body.predicted_confidence,
        challenge={"prompt": challenge.prompt, **(challenge.payload or {})},
        response=body.response if isinstance(body.response, (dict, list)) else {"raw": body.response},
    )
    await recognition.on_attempt(db, attempt=result.attempt, concept=concept, learner_id=user.id)
    await _drop_challenge(body.challenge_id)

    state = result.state
    return AttemptResponse(
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
        calibration=_calibration(body.predicted_confidence, outcome.score),
    )


@router.get("/modes", response_model=list[ModeInfo])
async def list_modes(
    subject_type: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """Available modes and how strongly each suits ``subject_type`` (the mode mix knob)."""
    return [
        ModeInfo(key=key, subject_weight=registry.get_mode(key).subject_weight(subject_type))
        for key in registry.available_modes()
    ]


def _get_mode_or_400(key: str):
    try:
        return registry.get_mode(key)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
