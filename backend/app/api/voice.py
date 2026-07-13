"""
Voice-lane WebSocket surface (B5, premium).

A thin transport adapter over ``services.voice.lane`` — all the real logic lives there
so it stays testable without a socket. This module's jobs are: **authorize** (JWT +
premium flag + enrollment), then **pump** client frames ↔ lane events. Barge-in is a
frame that trips the current turn's cancel event.

Not on the batch workers, not on retrieval ``/attempt`` — a separate live surface
(build-guide §82, §134). Voice is online-only by nature; there is no offline fallback here.
"""

import asyncio
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.database import async_session_maker
from app.models.course import CourseEnrollment
from app.models.retrieval import Concept
from app.models.user import User
from app.services.voice import VOICE_MODES, VoiceLane
from app.services.voice.protocol import (
    EVT_STATE,
    IN_BARGE_IN,
    IN_END,
    IN_SPEECH_FINAL,
    IN_START,
    STATE_DONE,
    STATE_LISTENING,
)

logger = get_logger(__name__)
router = APIRouter()

# Application-level WebSocket close codes (4000–4999 is the private range).
CLOSE_UNAUTHENTICATED = 4401
CLOSE_VOICE_DISABLED = 4402   # premium lane is off (launch is free — dark by default)
CLOSE_NOT_ENROLLED = 4403


class VoiceAuthError(Exception):
    """The token is missing/invalid — the connection can't be trusted."""


class VoiceDisabled(Exception):
    """The premium voice lane is switched off for this deployment/user."""


class NotEnrolled(Exception):
    """The user isn't enrolled in the course they're trying to talk about."""


@dataclass(frozen=True)
class VoiceAuth:
    user: User
    course_id: uuid.UUID


async def authorize_voice(db: AsyncSession, *, token: str, course_id: str) -> VoiceAuth:
    """Gate a voice session: premium flag → valid JWT → enrolled. Raises on any failure.

    Kept a plain async function (not socket-bound) so the gate is unit-testable directly.
    The premium check is a **seam**: today it's the ``ENABLE_VOICE_LANE`` flag (launch is
    free, so it's dark by default); per-user entitlement slots in here when billing lands.
    """
    if not settings.ENABLE_VOICE_LANE:
        raise VoiceDisabled("voice lane is not enabled")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise VoiceAuthError("invalid token") from exc
    if not user_id:
        raise VoiceAuthError("token has no subject")

    try:
        course_uuid = uuid.UUID(course_id)
    except (ValueError, AttributeError) as exc:
        raise NotEnrolled("bad course id") from exc

    user = await db.scalar(select(User).where(User.id == uuid.UUID(user_id)))
    if user is None:
        raise VoiceAuthError("unknown user")

    enrolled = await db.scalar(
        select(CourseEnrollment.id).where(
            CourseEnrollment.user_id == user.id,
            CourseEnrollment.course_id == course_uuid,
        )
    )
    if enrolled is None:
        raise NotEnrolled("not enrolled in this course")

    return VoiceAuth(user=user, course_id=course_uuid)


@router.websocket("/ws/voice/{course_id}")
async def voice_endpoint(websocket: WebSocket, course_id: str, token: str = Query(...)):
    """Live spoken retrieval over one concept. Frames: see ``services.voice.protocol``."""
    async with async_session_maker() as db:
        try:
            auth = await authorize_voice(db, token=token, course_id=course_id)
        except VoiceDisabled:
            await _reject(websocket, CLOSE_VOICE_DISABLED)
            return
        except VoiceAuthError:
            await _reject(websocket, CLOSE_UNAUTHENTICATED)
            return
        except NotEnrolled:
            await _reject(websocket, CLOSE_NOT_ENROLLED)
            return

        await websocket.accept()
        try:
            await _run_session(websocket, db, auth)
        except WebSocketDisconnect:
            pass
        finally:
            await db.commit()  # persist the turns' append-only attempts on the way out


async def _run_session(websocket: WebSocket, db: AsyncSession, auth: VoiceAuth) -> None:
    """Handle the start handshake, then pump turns until the client ends/disconnects."""
    start = await websocket.receive_json()
    if start.get("type") != IN_START:
        await _send(websocket, EVT_STATE, {"state": STATE_DONE, "reason": "expected start"})
        return

    mode = start.get("mode")
    if mode not in VOICE_MODES:
        await _send(websocket, EVT_STATE, {"state": STATE_DONE, "reason": "unsupported mode"})
        return

    concept = await db.scalar(select(Concept).where(Concept.id == uuid.UUID(start["concept_id"])))
    if concept is None or concept.course_id != auth.course_id:
        await _send(websocket, EVT_STATE, {"state": STATE_DONE, "reason": "unknown concept"})
        return

    lane = VoiceLane(db, user_id=auth.user.id, concept=concept, mode_key=mode)
    await _send(websocket, EVT_STATE, {"state": STATE_LISTENING})

    turn_task: asyncio.Task | None = None
    cancel = asyncio.Event()

    while True:
        frame = await websocket.receive_json()
        kind = frame.get("type")

        if kind == IN_END:
            break
        if kind == IN_BARGE_IN:
            cancel.set()  # trips the in-flight turn's speech; the grade still lands
            continue
        if kind == IN_SPEECH_FINAL:
            if turn_task is not None and not turn_task.done():
                await turn_task  # one turn at a time; drain the previous before the next
            cancel = asyncio.Event()
            turn_task = asyncio.create_task(_drive_turn(websocket, lane, frame.get("text", ""), cancel))

    if turn_task is not None and not turn_task.done():
        await turn_task
    await _send(websocket, EVT_STATE, {"state": STATE_DONE})


async def _drive_turn(websocket: WebSocket, lane: VoiceLane, text: str, cancel: asyncio.Event) -> None:
    async for event in lane.run_turn(text, cancel=cancel):
        await _send(websocket, event.type, event.data)


async def _send(websocket: WebSocket, type_: str, data: dict) -> None:
    await websocket.send_json({"type": type_, **data})


async def _reject(websocket: WebSocket, code: int) -> None:
    # Accept then close so the client sees a proper WS close code, not an HTTP 403.
    await websocket.accept()
    await websocket.close(code=code)
