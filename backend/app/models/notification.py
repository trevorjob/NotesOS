"""
NotesOS Models - Notification Model
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class NotificationType(str, Enum):
    TEST_GRADED = "TEST_GRADED"
    AI_SUMMARY_READY = "AI_SUMMARY_READY"
    INVITE_ACCEPTED = "INVITE_ACCEPTED"
    RESOURCE_UPLOADED = "RESOURCE_UPLOADED"
    CLASSMATE_JOINED = "CLASSMATE_JOINED"
    GENERAL = "GENERAL"
    # The habit loop (§8): the weight-bearing decay nudge ("time to firm up X").
    DECAY_NUDGE = "DECAY_NUDGE"


class Notification(Base):
    """In-app notification for a user."""

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    type = Column(SQLEnum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)

    # Optional structured data (e.g. {"test_id": "...", "course_id": "..."})
    meta_data = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NotificationPreference(Base):
    """Per-user control over the habit loop (§8, §15.4). One row per user, created lazily.

    Both nudge families default **on** (the digest is opt-out). Absence of a row means
    defaults — the digest tick treats a missing row as fully enabled. ``last_digest_at``
    is the once-per-day batching guard: the tick stamps it every time it processes a user
    at their preferred hour, so a user gets at most one digest attempt per day.
    """

    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    digest_enabled = Column(Boolean, default=True, nullable=False)       # decay nudge
    recognition_enabled = Column(Boolean, default=True, nullable=False)  # "your work was used"

    # Batching guard — last time the digest tick processed this user (any outcome).
    last_digest_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_notification_pref_user"),
    )
