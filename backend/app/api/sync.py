"""
NotesOS API — Offline Sync Router (B6).

The HTTP surface for the native client's cache-first offline story (system-spec §10):

  GET  /api/sync/courses/{course_id}  — bulk pull: everything to read + self-quiz offline.
  GET  /api/sync/changes?since=       — delta invalidation: IDs changed since last sync.
  POST /api/sync/attempts             — replay locally-queued attempts (append-only, idempotent).

All logic lives in ``services/sync``; this layer is auth + enrollment + shape.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, verify_course_enrollment
from app.database import get_db
from app.models.user import User
from app.services import sync

router = APIRouter(prefix="/api/sync", tags=["sync"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AttemptEventIn(BaseModel):
    client_event_id: str
    concept_id: str
    mode: str
    grade: str
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predicted_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    created_at: Optional[datetime] = None
    challenge: Optional[dict] = None
    response: Any = None


class PushRequest(BaseModel):
    attempts: list[AttemptEventIn]


class PushResultOut(BaseModel):
    client_event_id: str
    status: str
    concept_id: Optional[str] = None
    reason: Optional[str] = None
    state: Optional[dict] = None


class PushResponse(BaseModel):
    results: list[PushResultOut]
    applied: int
    duplicate: int
    rejected: int


# ── Bulk pull ─────────────────────────────────────────────────────────────────

@router.get("/courses/{course_id}")
async def pull_course(
    course_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The full offline bundle for a course — content plus this user's knowledge state."""
    await verify_course_enrollment(db, user.id, course_id)
    snapshot = await sync.course_snapshot(db, user_id=user.id, course_id=course_id)
    if not snapshot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "course not found")
    return snapshot


# ── Delta invalidation ────────────────────────────────────────────────────────

@router.get("/changes")
async def get_changes(
    since: datetime = Query(..., description="last_synced_at — ISO 8601"),
    course_id: Optional[uuid.UUID] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """IDs of entities changed since ``since`` — the client marks these stale and refetches."""
    if course_id is not None:
        await verify_course_enrollment(db, user.id, course_id)
    return await sync.changes_since(db, user_id=user.id, since=since, course_id=course_id)


# ── Append-only event push ────────────────────────────────────────────────────

@router.post("/attempts", response_model=PushResponse)
async def push_attempts(
    body: PushRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replay locally-queued attempts. Idempotent (client_event_id), partial-failure safe."""
    events = [
        sync.AttemptEvent(
            client_event_id=e.client_event_id,
            concept_id=e.concept_id,
            mode=e.mode,
            grade=e.grade,
            score=e.score,
            predicted_confidence=e.predicted_confidence,
            created_at=e.created_at,
            challenge=e.challenge,
            response=e.response,
        )
        for e in body.attempts
    ]
    try:
        results = await sync.push_attempts(db, user_id=user.id, events=events)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    await db.commit()

    counts = {"applied": 0, "duplicate": 0, "rejected": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return PushResponse(
        results=[
            PushResultOut(
                client_event_id=r.client_event_id, status=r.status,
                concept_id=r.concept_id, reason=r.reason, state=r.state,
            )
            for r in results
        ],
        **counts,
    )
