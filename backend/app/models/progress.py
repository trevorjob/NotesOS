"""
NotesOS Models - Progress and AI Conversation Models
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Integer,
    ForeignKey,
    Enum as SQLEnum,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class SessionType(str, Enum):
    READING = "reading"
    QUIZ = "quiz"
    PRACTICE = "practice"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class StudySession(Base):
    """Track individual study sessions."""

    __tablename__ = "study_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)

    session_type = Column(
        SQLEnum(SessionType), default=SessionType.READING, nullable=False
    )
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Session metadata
    notes_reviewed = Column(JSONB, nullable=True, default=[])  # Array of note IDs
    concepts_covered = Column(JSONB, nullable=True, default=[])

    # Relationships
    topic = relationship("Topic", back_populates="study_sessions")


class UserProgress(Base):
    """Track user progress per topic."""

    __tablename__ = "user_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)

    mastery_level = Column(Numeric(3, 2), default=0.00, nullable=False)  # 0.00 - 1.00
    total_study_time = Column(Integer, default=0, nullable=False)  # Seconds
    total_attempts = Column(Integer, default=0, nullable=False)
    avg_score = Column(Numeric(5, 2), nullable=True)

    streak_days = Column(Integer, default=0, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    course = relationship("Course", back_populates="user_progress")
    topic = relationship("Topic", back_populates="user_progress")


class AIConversation(Base):
    """AI chat conversation context."""

    __tablename__ = "ai_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True)

    title = Column(String(255), nullable=True)  # Auto-generated title

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    course = relationship("Course", back_populates="ai_conversations")
    topic = relationship("Topic", back_populates="ai_conversations")


class AIMessage(Base):
    """Individual AI chat messages."""

    __tablename__ = "ai_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("ai_conversations.id"), nullable=False
    )

    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    extra_metadata = Column(JSONB, nullable=True)  # Citations, sources, etc.

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
