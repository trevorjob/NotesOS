"""
Recognition — the "your work was used" loop (product-map §7 · system-spec §8/§9).

The loop rewards the *contributor* whose material someone studied: "your notes were used
→ you're seen → you contribute more → the shared note improves." It rides the §11
consume/activity substrate (build-guide §6): recognition, creation-visibility and
join-propagation are one system — this module owns the recognition *policy* over it.

**Two consume sources, one aggregation:**
- *Active* — a ``RetrievalAttempt`` on a concept whose topic others built. Already in the
  append-only log; never duplicated (derive-before-store). The **warm** signal.
- *Passive* — a note view / audio listen, recorded as a ``ConsumeEvent`` (the only part
  of the substrate not otherwise stored). The **aggregate + anonymous** signal.

**Warmth rules (§8):** active engagement earns a warm, specific-ish line; passive
consumption is an aggregate count. Recognition is **rare, batched, never per-event** —
delivery is one digest notification, built here and fired by the B2 notifications tick,
gated behind ``ENABLE_RECOGNITION``. Nobody is surveilled: the studier is never named
("seen, not surveilled").
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.consume import ConsumeEvent, ConsumeKind
from app.models.notification import Notification, NotificationType
from app.models.resource import Resource
from app.models.retrieval import Concept, RetrievalAttempt
from app.services.notifications import create_and_push_notification

logger = get_logger(__name__)


def _as_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


async def resolve_beneficiaries(
    db: AsyncSession, *, topic_id, learner_id
) -> list[uuid.UUID]:
    """Who contributed the material behind this topic — minus the learner.

    Topic-level attribution (invariant #8): uploaders of non-quarantined resources in the
    topic. Quarantined uploads are held out of the shared note, so they earn no recognition.
    """
    rows = (
        await db.execute(
            select(Resource.uploaded_by)
            .where(Resource.topic_id == topic_id)
            .where(Resource.quarantined.is_(False))
            .distinct()
        )
    ).scalars().all()

    learner = _as_uuid(learner_id)
    return [uid for uid in rows if uid != learner]


async def record_consume(db: AsyncSession, *, actor_id, topic_id, kind: ConsumeKind) -> None:
    """Record a *passive* consume of a topic's shared material (§11 substrate).

    Cheap, append-only, best-effort. Recorded **regardless of ``ENABLE_RECOGNITION``** —
    it's the substrate that also feeds contribution-visibility / co-presence later; only
    *delivery* is gated. Never raises into the request path: a consume-record failure must
    not fail the read it rides on. Isolated commit so it can't poison the caller's session.
    """
    try:
        db.add(ConsumeEvent(actor_id=_as_uuid(actor_id), topic_id=_as_uuid(topic_id), kind=kind))
        await db.commit()
    except Exception:  # pragma: no cover - best-effort substrate write
        logger.warning("recognition: consume record failed", exc_info=True)
        await db.rollback()


@dataclass(frozen=True)
class RecognitionSummary:
    """Aggregated recent consumption of one contributor's material."""

    contributor_id: uuid.UUID
    active_studiers: int          # distinct users who did retrieval on your topics (warm)
    passive_consumers: int        # distinct users who read/listened (aggregate/anonymous)
    topic_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.active_studiers + self.passive_consumers


async def _contributor_topic_ids(db: AsyncSession, contributor_id: uuid.UUID) -> list[uuid.UUID]:
    """Topics this user has non-quarantined uploads in — the material they're behind."""
    return list(
        (
            await db.execute(
                select(distinct(Resource.topic_id))
                .where(Resource.uploaded_by == contributor_id)
                .where(Resource.quarantined.is_(False))
            )
        ).scalars().all()
    )


async def pending_recognition(
    db: AsyncSession, *, contributor_id, since: datetime, now: Optional[datetime] = None
) -> RecognitionSummary:
    """Aggregate how a contributor's material was consumed in ``[since, now]``.

    Warmth split (§8): active engagement (retrieval attempts on their topics) is the warm
    signal; passive consumption (note views / listens) is the aggregate/anonymous count.
    Both count **distinct other users** and exclude the contributor's own activity, so a
    contributor studying their own notes never recognizes themselves.
    """
    cid = _as_uuid(contributor_id)
    topic_ids = await _contributor_topic_ids(db, cid)
    if not topic_ids:
        return RecognitionSummary(contributor_id=cid, active_studiers=0, passive_consumers=0)

    active_studiers = await db.scalar(
        select(func.count(distinct(RetrievalAttempt.user_id)))
        .select_from(RetrievalAttempt)
        .join(Concept, Concept.id == RetrievalAttempt.concept_id)
        .where(Concept.topic_id.in_(topic_ids))
        .where(RetrievalAttempt.user_id != cid)
        .where(RetrievalAttempt.created_at >= since)
    ) or 0

    passive_consumers = await db.scalar(
        select(func.count(distinct(ConsumeEvent.actor_id)))
        .where(ConsumeEvent.topic_id.in_(topic_ids))
        .where(ConsumeEvent.actor_id != cid)
        .where(ConsumeEvent.created_at >= since)
    ) or 0

    return RecognitionSummary(
        contributor_id=cid,
        active_studiers=int(active_studiers),
        passive_consumers=int(passive_consumers),
        topic_ids=topic_ids,
    )


def _recognition_copy(summary: RecognitionSummary) -> tuple[str, str]:
    """Warmth-tuned copy: warm for active engagement, aggregate/anonymous for passive.

    The studier is never named — recognition is "seen, not surveilled" (§8).
    """
    n_active = summary.active_studiers
    n_passive = summary.passive_consumers
    if n_active:
        who = "A classmate" if n_active == 1 else f"{n_active} classmates"
        return (
            "Your notes are working",
            f"{who} studied concepts your uploads helped build. Nice contribution.",
        )
    who = "A classmate" if n_passive == 1 else f"{n_passive} classmates"
    return (
        "Your notes are being read",
        f"{who} read a note you helped build.",
    )


async def deliver_pending_recognition(
    db: AsyncSession, *, contributor_id, since: datetime, now: Optional[datetime] = None
) -> Optional[Notification]:
    """Build + push **one batched** recognition notification for a contributor.

    Called by the B2 notifications tick (periodic, per user), **never per event**. Returns
    ``None`` — delivering nothing — when ``ENABLE_RECOGNITION`` is off or there's nothing to
    recognize in the window. Warm for active, aggregate/anonymous for passive (§8).
    """
    if not settings.ENABLE_RECOGNITION:
        return None
    summary = await pending_recognition(db, contributor_id=contributor_id, since=since, now=now)
    if summary.total == 0:
        return None

    title, body = _recognition_copy(summary)
    return await create_and_push_notification(
        db,
        user_id=summary.contributor_id,
        notif_type=NotificationType.GENERAL,
        title=title,
        body=body,
        meta_data={
            "kind": "recognition",
            "active_studiers": summary.active_studiers,
            "passive_consumers": summary.passive_consumers,
        },
    )


async def on_attempt(db: AsyncSession, *, attempt: Any, concept: Any, learner_id) -> list[uuid.UUID]:
    """Seam kept at the /attempt + recap call sites; **no per-attempt delivery** (B1).

    Recognition is aggregated by the digest (``deliver_pending_recognition``) from the
    attempt log itself, so an attempt needs no extra recognition write. This resolves the
    beneficiary set (cheap) and returns it for telemetry/tests; it never delivers or raises
    into the request path.
    """
    try:
        return await resolve_beneficiaries(db, topic_id=concept.topic_id, learner_id=learner_id)
    except Exception:  # pragma: no cover - defensive; recognition is best-effort
        logger.warning("recognition: beneficiary resolution failed", exc_info=True)
        return []
