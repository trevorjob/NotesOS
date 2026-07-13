"""
NotesOS Models — Consume-event substrate (§11 attribution / consumption layer).

Recognition, creation-visibility and join-propagation are **one system**: consume /
activity events, aggregated and warmth-tuned (build-guide §6 — "build that event layer
once; each is a policy on top"). This table is the part of that substrate that isn't
otherwise recorded: **passive** consumption — reading a topic's consolidated note or
listening to its audio.

**Active** consumption is *not* stored here. A retrieval attempt *is* an active consume,
and it already lives in the append-only ``RetrievalAttempt`` log — so recognition
aggregates over *both* sources rather than duplicating the attempt log (derive-before-store,
invariant #2).

Attribution is **topic-level on purpose** (invariant #8): synthesis blends a topic's
chunks into one note, so provenance resolves to the topic's uploaders, never a single
concept. Hence the event is tagged with ``topic_id``, not a concept or a resource.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ConsumeKind(str, Enum):
    """The passive ways a user consumes a topic's shared material."""

    NOTE_VIEW = "NOTE_VIEW"        # opened / read a topic's consolidated note
    AUDIO_LISTEN = "AUDIO_LISTEN"  # listened to a topic's audio lesson


class ConsumeEvent(Base):
    """One passive consumption of a topic's shared material. Append-only."""

    __tablename__ = "consume_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = Column(SQLEnum(ConsumeKind), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Recognition aggregates "who consumed my topics since T" — a topic+time scan.
    __table_args__ = (
        Index("ix_consume_topic_created", "topic_id", "created_at"),
    )
