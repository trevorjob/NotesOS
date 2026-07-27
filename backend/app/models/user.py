"""
NotesOS Models - User Model
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User account model with study personality preferences."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Email is optional (phone is the primary identity). Unique when present —
    # Postgres allows multiple NULLs under a unique constraint, so OAuth-linking by
    # email still works while phone-only users carry no email.
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)  # nullable for OAuth-only users
    full_name = Column(String(255), nullable=False)
    avatar_url = Column(Text, nullable=True)
    # Free-text university, retained for one release. Superseded by school_id;
    # kept nullable so the backfill can read it before it is dropped.
    university = Column(String(255), nullable=True)

    # Canonical school (grouping signal + proximity-check hard filter).
    school_id = Column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional proximity-check ranking signals. All nullable and non-load-bearing:
    # present in cohort-based systems (Nigeria), often blank elsewhere (US freshers).
    program = Column(String(255), nullable=True)  # degree / major, free text
    entry_year = Column(Integer, nullable=True)   # e.g. 2027

    # Phone is the PRIMARY identity: required, unique, password-based (no OTP).
    phone = Column(String(32), nullable=False, unique=True, index=True)
    # SHA-256 of the canonical (E.164) phone — the join key for contact matching.
    # Non-unique (two accounts could canonicalise to the same number), indexed for
    # the `WHERE phone_hash IN (...)` lookup. Nullable: backfilled for existing rows.
    phone_hash = Column(String(64), nullable=True, index=True)

    # Google OAuth
    google_id = Column(String(255), unique=True, nullable=True, index=True)

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

    # User preferences and learning tags
    preferences = Column(JSONB, nullable=True)
    personality_tags = Column(JSONB, nullable=True)  # string[]

    # Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login = Column(DateTime, nullable=True)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    school = relationship("School", back_populates="users")
    terms = relationship("Term", back_populates="user", cascade="all, delete-orphan")
