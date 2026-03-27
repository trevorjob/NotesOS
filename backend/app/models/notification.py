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
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class NotificationType(str, Enum):
    TEST_GRADED = "TEST_GRADED"
    AI_SUMMARY_READY = "AI_SUMMARY_READY"
    INVITE_ACCEPTED = "INVITE_ACCEPTED"
    GENERAL = "GENERAL"


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
