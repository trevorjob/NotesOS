"""
NotesOS Models - Knowledge System
TopicKnowledge: consolidated AI-synthesized notes per topic.
AudioLesson: generated TTS audio lecture per topic.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class KnowledgeStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TopicKnowledge(Base):
    """
    AI-synthesized consolidated knowledge for a topic.
    One record per topic (upserted whenever resources change).
    """

    __tablename__ = "topic_knowledge"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # AI-generated content
    consolidated_note = Column(Text, nullable=True)          # markdown synthesis
    key_points = Column(JSONB, nullable=True)                # list[str]
    concepts = Column(JSONB, nullable=True)                  # list[{term, definition}]
    source_count = Column(Integer, nullable=False, default=0)

    # Processing state
    status = Column(
        SAEnum(KnowledgeStatus, name="knowledgestatus"),
        nullable=False,
        default=KnowledgeStatus.PENDING,
    )
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    topic = relationship("Topic", back_populates="knowledge")
    audio_lessons = relationship(
        "AudioLesson", back_populates="knowledge", cascade="all, delete-orphan"
    )


class AudioLesson(Base):
    """
    TTS-generated audio lecture for a topic.
    Linked to the TopicKnowledge it was generated from.
    """

    __tablename__ = "audio_lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topic_knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content
    script = Column(Text, nullable=True)           # conversational audio script
    audio_url = Column(Text, nullable=True)        # Cloudinary MP3 URL
    duration_seconds = Column(Integer, nullable=True)
    voice = Column(String(50), nullable=False, default="nova")  # OpenAI TTS voice

    # Processing state
    status = Column(
        SAEnum(KnowledgeStatus, name="knowledgestatus"),
        nullable=False,
        default=KnowledgeStatus.PENDING,
    )
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    topic = relationship("Topic", back_populates="audio_lessons")
    knowledge = relationship("TopicKnowledge", back_populates="audio_lessons")
