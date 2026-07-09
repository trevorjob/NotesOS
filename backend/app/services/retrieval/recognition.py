"""
Recognition seam — the dormant hook for the recognition loop (product-map §7).

The recognition loop rewards the *contributor* whose material someone just studied:
"your notes were used → you're seen → you contribute more → the shared note improves."
A retrieval attempt is exactly such a consume event — the learner tested themselves
against a concept that someone else's upload helped build.

**Why this is a seam, not the loop yet.** Two pieces it depends on aren't built:
- *Attribution granularity.* Synthesis blends all of a topic's chunks into one note, so
  there's no per-concept chunk→resource provenance (``Concept.source_chunk_ids`` is a
  future precision hook). The honest granularity today is **topic-level**: the uploaders
  who contributed non-quarantined resources to the concept's topic.
- *Warmth / anti-spam.* The loop needs digest + batching and the aggregate-vs-personal
  warmth rules (product-map §7, §9) before it should ever ping anyone. Until then this
  is gated behind ``ENABLE_RECOGNITION`` (default off): the beneficiary set is resolved
  every attempt (cheap), but nothing is delivered.

When §11 (attribution/consumption events) lands, it flips the flag and swaps the
per-attempt notify for the real batched, attributed pipeline — the call site doesn't move.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.notification import NotificationType
from app.models.resource import Resource
from app.services.notifications import create_and_push_notification

logger = get_logger(__name__)


async def resolve_beneficiaries(
    db: AsyncSession, *, topic_id, learner_id
) -> list[uuid.UUID]:
    """Who contributed the material behind this concept's topic — minus the learner.

    Topic-level attribution: uploaders of non-quarantined resources in the topic.
    Quarantined uploads are held out of the shared note, so they earn no recognition.
    """
    rows = (
        await db.execute(
            select(Resource.uploaded_by)
            .where(Resource.topic_id == topic_id)
            .where(Resource.quarantined.is_(False))
            .distinct()
        )
    ).scalars().all()

    learner = learner_id if isinstance(learner_id, uuid.UUID) else uuid.UUID(str(learner_id))
    return [uid for uid in rows if uid != learner]


async def on_attempt(db: AsyncSession, *, attempt: Any, concept: Any, learner_id) -> list[uuid.UUID]:
    """Fire the recognition event off a recorded attempt. Returns the beneficiaries.

    Always resolves the beneficiary set (cheap); only *delivers* when
    ``ENABLE_RECOGNITION`` is on. Safe no-op when there are no other contributors —
    the common case today. Never raises into the request path: a recognition failure
    must not fail the attempt.
    """
    try:
        beneficiaries = await resolve_beneficiaries(
            db, topic_id=concept.topic_id, learner_id=learner_id
        )
    except Exception:  # pragma: no cover - defensive; recognition is best-effort
        logger.warning("recognition: beneficiary resolution failed", exc_info=True)
        return []

    if not beneficiaries or not settings.ENABLE_RECOGNITION:
        return beneficiaries

    # Aggregate + anonymous: the loop celebrates that the note was used, without naming
    # or surveilling the studier (product-map §7 warmth rule). Per-attempt delivery here
    # is a placeholder — §9 digest/batching must land before this goes live.
    for contributor_id in beneficiaries:
        try:
            await create_and_push_notification(
                db,
                user_id=contributor_id,
                notif_type=NotificationType.GENERAL,
                title="Your notes are being studied",
                body="Someone just studied a concept your uploads helped build.",
                meta_data={"kind": "recognition", "concept_id": str(concept.id)},
            )
        except Exception:  # pragma: no cover - best-effort delivery
            logger.warning("recognition: notify failed for %s", contributor_id, exc_info=True)

    return beneficiaries
