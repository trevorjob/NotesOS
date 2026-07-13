"""
Voice-lane gate (B5) — ``authorize_voice`` is the whole security surface of the WS lane.

The WebSocket transport itself is a thin pump with no logic to test (the httpx test
transport is HTTP-only), so the gate is unit-tested directly: premium flag → valid JWT →
enrollment, each failure mapped to its own typed error (→ its own WS close code).
"""

import uuid

import pytest
from jose import jwt

from app.api.voice import (
    NotEnrolled,
    VoiceAuthError,
    VoiceDisabled,
    authorize_voice,
)
from app.config import settings
from app.models import Course, CourseEnrollment, User
from tests.conftest import unique_phone


async def _seed_user_course(db, *, enroll=True):
    user = User(email=f"g_{uuid.uuid4().hex[:8]}@t.dev", full_name="G", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    if enroll:
        db.add(CourseEnrollment(user_id=user.id, course_id=course.id))
        await db.flush()
    return user, course


def _token(user_id) -> str:
    return jwt.encode({"sub": str(user_id)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def voice_on(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_VOICE_LANE", True)


async def test_authorize_succeeds_for_enrolled_user(db_session, voice_on):
    user, course = await _seed_user_course(db_session)
    auth = await authorize_voice(db_session, token=_token(user.id), course_id=str(course.id))
    assert auth.user.id == user.id and auth.course_id == course.id


async def test_authorize_rejected_when_lane_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_VOICE_LANE", False)
    user, course = await _seed_user_course(db_session)
    with pytest.raises(VoiceDisabled):
        await authorize_voice(db_session, token=_token(user.id), course_id=str(course.id))


async def test_authorize_rejects_bad_token(db_session, voice_on):
    _user, course = await _seed_user_course(db_session)
    with pytest.raises(VoiceAuthError):
        await authorize_voice(db_session, token="not-a-jwt", course_id=str(course.id))


async def test_authorize_rejects_unenrolled_user(db_session, voice_on):
    user, course = await _seed_user_course(db_session, enroll=False)
    with pytest.raises(NotEnrolled):
        await authorize_voice(db_session, token=_token(user.id), course_id=str(course.id))
