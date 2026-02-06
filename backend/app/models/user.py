"""
NotesOS Models - User Model
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class User(Base):
    """User account model with study personality preferences."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    avatar_url = Column(Text, nullable=True)

    # AI personality preferences stored as JSONB
    # Example: {"tone": "encouraging", "emoji_usage": "moderate", "explanation_style": "detailed"}
    study_personality = Column(
        JSONB,
        nullable=True,
        default={
            "tone": "encouraging",
            "emoji_usage": "moderate",
            "explanation_style": "detailed",
        },
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login = Column(DateTime, nullable=True)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
