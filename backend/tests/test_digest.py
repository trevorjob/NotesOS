"""
The habit digest (B2) — the periodic decay + recognition nudge.

Pins the pure timing helpers, per-user send (pushworthy gating, preferences, batching
stamp), the tick's due/not-due + once-per-day behaviour, and the preferences API. The
LLM/Redis boundary is spied, so no test needs a live model, scheduler, or broadcast.
"""

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.models import Concept, Course, CourseEnrollment, Topic, User
from app.models.notification import NotificationPreference, NotificationType
from app.models.retrieval import ConceptState, RetrievalAttempt
from app.services import digest
from app.services.retrieval import recognition
from tests.conftest import unique_phone

NOW = datetime(2026, 7, 13, 18, 30, 0)  # hour 18


# ── Pure timing ────────────────────────────────────────────────────────────────

def test_derive_preferred_hour_is_the_mode():
    assert digest.derive_preferred_hour([9, 18, 18, 21]) == 18


def test_derive_preferred_hour_breaks_ties_earlier():
    # 8 and 20 both appear twice → the earlier one (nudge before the slot).
    assert digest.derive_preferred_hour([8, 20, 8, 20]) == 8


def test_derive_preferred_hour_defaults_when_empty():
    assert digest.derive_preferred_hour([]) == digest.DEFAULT_DIGEST_HOUR


def test_already_sent_today():
    now = NOW
    assert digest.already_sent_today(None, now) is False
    pref = NotificationPreference(user_id=uuid.uuid4(), last_digest_at=None)
    assert digest.already_sent_today(pref, now) is False
    pref.last_digest_at = now - timedelta(hours=2)  # earlier today
    assert digest.already_sent_today(pref, now) is True
    pref.last_digest_at = now - timedelta(days=1)   # yesterday
    assert digest.already_sent_today(pref, now) is False


# ── Fixtures / helpers ───────────────────────────────────────────────────────

def _spy_notifications(monkeypatch):
    """Patch the notification sink in both digest + recognition; return the call log."""
    calls = []

    async def _spy(db, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id=uuid.uuid4(), **kwargs)

    monkeypatch.setattr(digest, "create_and_push_notification", _spy)
    monkeypatch.setattr(recognition, "create_and_push_notification", _spy)
    return calls


async def _learner(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="C1", name="C", created_by=user.id)
    db.add(course)
    await db.flush()
    db.add(CourseEnrollment(user_id=user.id, course_id=course.id))
    topic = Topic(course_id=course.id, title="Krebs Cycle")
    db.add(topic)
    await db.flush()
    return user, course, topic


async def _due_concept(db, user, course, topic, *, when=NOW):
    c = Concept(topic_id=topic.id, course_id=course.id, text="citrate")
    db.add(c)
    await db.flush()
    db.add(ConceptState(user_id=user.id, concept_id=c.id, due=when - timedelta(days=1), reps=1))
    await db.flush()
    return c


async def _attempt_at_hour(db, user, concept, *, when):
    a = RetrievalAttempt(user_id=user.id, concept_id=concept.id, mode="quiz", grade="good")
    a.created_at = when
    db.add(a)
    await db.flush()


# ── send_user_digest ─────────────────────────────────────────────────────────

async def test_send_pushes_decay_nudge_for_fading(db_session, monkeypatch):
    calls = _spy_notifications(monkeypatch)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", False)
    user, course, topic = await _learner(db_session)
    await _due_concept(db_session, user, course, topic)
    pref = NotificationPreference(user_id=user.id)
    db_session.add(pref)
    await db_session.flush()

    delivered = await digest.send_user_digest(db_session, user_id=user.id, pref=pref, now=NOW)

    assert len(delivered) == 1
    assert calls[0]["notif_type"] == NotificationType.DECAY_NUDGE
    assert calls[0]["meta_data"]["kind"] == "decay_nudge"
    assert calls[0]["meta_data"]["topic_id"] == str(topic.id)
    assert pref.last_digest_at == NOW  # batching stamp set


async def test_send_skips_non_pushworthy_new_material(db_session, monkeypatch):
    calls = _spy_notifications(monkeypatch)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", False)
    user, course, topic = await _learner(db_session)
    # a concept with no state → the selector returns kind="new" (pull-only, never pushed)
    c = Concept(topic_id=topic.id, course_id=course.id, text="fumarate")
    db_session.add(c)
    await db_session.flush()
    pref = NotificationPreference(user_id=user.id)
    db_session.add(pref)
    await db_session.flush()

    delivered = await digest.send_user_digest(db_session, user_id=user.id, pref=pref, now=NOW)

    assert delivered == []            # nothing pushed
    assert pref.last_digest_at == NOW  # but still stamped (no re-run today)


async def test_send_respects_digest_disabled(db_session, monkeypatch):
    _spy_notifications(monkeypatch)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", False)
    user, course, topic = await _learner(db_session)
    await _due_concept(db_session, user, course, topic)
    pref = NotificationPreference(user_id=user.id, digest_enabled=False)
    db_session.add(pref)
    await db_session.flush()

    delivered = await digest.send_user_digest(db_session, user_id=user.id, pref=pref, now=NOW)
    assert delivered == []


# ── run_digest_tick ──────────────────────────────────────────────────────────

async def test_tick_sends_at_preferred_hour(db_session, monkeypatch):
    _spy_notifications(monkeypatch)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", False)
    user, course, topic = await _learner(db_session)
    c = await _due_concept(db_session, user, course, topic)
    await _attempt_at_hour(db_session, user, c, when=NOW)  # studies at hour 18

    sent = await digest.run_digest_tick(db_session, now=NOW)  # now is hour 18
    assert sent == 1


async def test_tick_silent_off_preferred_hour(db_session, monkeypatch):
    _spy_notifications(monkeypatch)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", False)
    user, course, topic = await _learner(db_session)
    c = await _due_concept(db_session, user, course, topic)
    await _attempt_at_hour(db_session, user, c, when=NOW)  # hour 18

    off_hour = NOW.replace(hour=9)
    sent = await digest.run_digest_tick(db_session, now=off_hour)
    assert sent == 0


async def test_tick_batches_to_once_per_day(db_session, monkeypatch):
    _spy_notifications(monkeypatch)
    monkeypatch.setattr(settings, "ENABLE_RECOGNITION", False)
    user, course, topic = await _learner(db_session)
    c = await _due_concept(db_session, user, course, topic)
    await _attempt_at_hour(db_session, user, c, when=NOW)

    first = await digest.run_digest_tick(db_session, now=NOW)
    second = await digest.run_digest_tick(db_session, now=NOW + timedelta(minutes=30))
    assert first == 1
    assert second == 0  # already processed today


# ── Preferences API ──────────────────────────────────────────────────────────

async def test_preferences_default_on(client, register_user):
    user = await register_user()
    resp = await client.get("/api/notifications/preferences", headers=user["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["digest_enabled"] is True
    assert body["recognition_enabled"] is True


async def test_preferences_patch(client, register_user):
    user = await register_user()
    resp = await client.patch(
        "/api/notifications/preferences",
        headers=user["headers"],
        json={"digest_enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["digest_enabled"] is False
    assert resp.json()["recognition_enabled"] is True  # untouched
