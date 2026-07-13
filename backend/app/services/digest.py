"""
The habit loop (B2) — the periodic digest that brings a user back (system-spec §8).

This is the *reactive-worker exception*: it must fire **on a schedule, per user, whether
or not any event happened** (build-guide §2a). So it can't ride the Redis-queue loop —
the APScheduler tick lives in ``workers/notification_scheduler.py`` and calls
``run_digest_tick`` here. **All the logic lives here, apscheduler-free, so it's unit-tested
without a live scheduler.**

Two loops, both **batched and rare** (scarcity is what lets them stay gentle):
- **Decay nudge** (primary, weight-bearing) — the single highest-value thing to study now,
  from the shared B3 selector. Pushed *only* when it's fading knowledge (review/calibration)
  — never to nag about new material or "get ahead" (§8: rare + meaningful).
- **Recognition** (secondary, social) — "your work was used", one warmth-tuned aggregate
  from B1's ``deliver_pending_recognition``.

**Timing off the session log** (§8): the tick fires each user's digest at the hour of day
they actually study, derived from their attempt history — no stored schedule. **Batching:**
``last_digest_at`` caps it to one attempt per user per day. **Preferences** (§15.4): both
loops are opt-out per user; the digest is on by default.
"""

import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
)
from app.models.retrieval import RetrievalAttempt
from app.services.notifications import create_and_push_notification
from app.services.retrieval.next_action import select_next_action
from app.services.retrieval.recognition import deliver_pending_recognition

logger = get_logger(__name__)

# Fallback study hour (UTC) for a user with too little history to infer one.
DEFAULT_DIGEST_HOUR = 18
# How far back recognition reaches when a user has never been sent a digest before.
RECOGNITION_WINDOW = timedelta(days=7)
# Only these next-actions are worth a *push* — fading knowledge. New/get_ahead are pull-only
# (the home card), never a nag (§8).
PUSHWORTHY_KINDS = frozenset({"review", "calibration"})
# Recent attempts scanned to infer a user's study hour.
_HISTORY_SCAN = 200
# Safety cap on users processed per tick (launch scale; horizontal-scale later).
_MAX_USERS_PER_TICK = 5000


def _as_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def derive_preferred_hour(hours: list[int]) -> int:
    """The hour (0–23 UTC) a user most often studies; ``DEFAULT_DIGEST_HOUR`` if unknown.

    Pure — the mode of recent attempt hours, ties broken toward the earlier hour so the
    nudge lands *before* their usual slot, not after.
    """
    if not hours:
        return DEFAULT_DIGEST_HOUR
    counts = Counter(hours)
    top = max(counts.values())
    return min(h for h, c in counts.items() if c == top)


async def user_preferred_hour(db: AsyncSession, user_id) -> int:
    """Infer a user's study hour from their recent attempt timestamps (UTC)."""
    rows = (
        await db.execute(
            select(func.extract("hour", RetrievalAttempt.created_at))
            .where(RetrievalAttempt.user_id == _as_uuid(user_id))
            .order_by(RetrievalAttempt.created_at.desc())
            .limit(_HISTORY_SCAN)
        )
    ).scalars().all()
    return derive_preferred_hour([int(h) for h in rows if h is not None])


def already_sent_today(pref: Optional[NotificationPreference], now: datetime) -> bool:
    """True if the digest tick already processed this user today (batching guard)."""
    if pref is None or pref.last_digest_at is None:
        return False
    return pref.last_digest_at.date() == now.date()


async def _get_or_create_preference(db: AsyncSession, user_id) -> NotificationPreference:
    uid = _as_uuid(user_id)
    pref = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == uid)
    )
    if pref is None:
        pref = NotificationPreference(user_id=uid)
        db.add(pref)
        await db.flush()
    return pref


def _decay_copy(action) -> tuple[str, str]:
    """Warm, specific, mild (§8) — never anxiety copy."""
    title = f"Time to firm up {action.topic_title}"
    body = f"{action.reason} (~{action.est_minutes} min)"
    return title, body


async def send_user_digest(
    db: AsyncSession,
    *,
    user_id,
    pref: NotificationPreference,
    now: Optional[datetime] = None,
) -> list[Notification]:
    """Build + push this user's batched digest (decay + recognition), honoring prefs.

    Always stamps ``last_digest_at`` (the once-per-day guard) even when nothing is sent, so
    a re-run within the day is a no-op. Returns the notifications delivered (may be empty).
    """
    now = now or datetime.utcnow()
    delivered: list[Notification] = []

    if pref.digest_enabled:
        action = await select_next_action(db, user_id=user_id, now=now)
        if action is not None and action.kind in PUSHWORTHY_KINDS:
            title, body = _decay_copy(action)
            notif = await create_and_push_notification(
                db,
                user_id=_as_uuid(user_id),
                notif_type=NotificationType.DECAY_NUDGE,
                title=title,
                body=body,
                meta_data={
                    "kind": "decay_nudge",
                    "action_kind": action.kind,
                    "course_id": str(action.course_id),
                    "topic_id": str(action.topic_id),
                    "mode": action.mode,
                    "concept_ids": [str(c) for c in action.concept_ids],
                    "est_minutes": action.est_minutes,
                },
            )
            delivered.append(notif)

    if pref.recognition_enabled and settings.ENABLE_RECOGNITION:
        since = pref.last_digest_at or (now - RECOGNITION_WINDOW)
        rec = await deliver_pending_recognition(
            db, contributor_id=user_id, since=since, now=now
        )
        if rec is not None:
            delivered.append(rec)

    pref.last_digest_at = now
    await db.commit()
    return delivered


async def run_digest_tick(db: AsyncSession, now: Optional[datetime] = None) -> int:
    """One periodic pass: send each due user their digest. Returns the count delivered to.

    A user is *due* when the current hour matches their inferred study hour and they haven't
    been processed today. Candidates are active learners (they have attempts) — a user who
    never studies is never nudged. Per-user failures are isolated; one bad user can't stop
    the tick.
    """
    now = now or datetime.utcnow()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    user_ids = (
        await db.execute(
            select(distinct(RetrievalAttempt.user_id)).limit(_MAX_USERS_PER_TICK)
        )
    ).scalars().all()

    sent_to = 0
    for uid in user_ids:
        try:
            pref = await _get_or_create_preference(db, uid)
            if not pref.digest_enabled and not pref.recognition_enabled:
                continue
            if already_sent_today(pref, now):
                continue
            if await user_preferred_hour(db, uid) != now.hour:
                continue
            delivered = await send_user_digest(db, user_id=uid, pref=pref, now=now)
            if delivered:
                sent_to += 1
        except Exception:  # pragma: no cover - one user must not break the tick
            logger.warning("digest: send failed for user %s", uid, exc_info=True)
            await db.rollback()

    return sent_to
