"""
NotesOS Models - Knowledge System
TopicKnowledge: consolidated AI-synthesized notes per topic.
AudioArtifact: generated TTS audio over a scope (course/topic/concept/cluster),
a lens (how it's told), and an owner (global/shared vs. personal/credited).
See docs/listen-audio-plan.md for the design this generalizes.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class KnowledgeStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioScopeType(str, enum.Enum):
    COURSE = "course"
    TOPIC = "topic"
    CONCEPT = "concept"
    CONCEPT_CLUSTER = "concept_cluster"


class AudioLens(str, enum.Enum):
    DEFAULT = "default"
    USER_INSTRUCTION = "user_instruction"
    REMEDIATION = "remediation"
    EXAM_FOCUSED = "exam_focused"
    SLOWER = "slower"
    WORKED_EXAMPLE = "worked_example"


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
    audio_artifacts = relationship(
        "AudioArtifact", back_populates="knowledge", cascade="all, delete-orphan"
    )


class AudioArtifact(Base):
    """
    TTS-generated audio over a scope (course/topic/concept/concept_cluster).

    ``scope_ref`` is polymorphic (topic_id / concept_id / cluster key depending on
    ``scope_type``) so it carries no FK constraint — callers that hard-delete a
    scope (e.g. ``DELETE /topics/{id}``) must explicitly clean up matching
    artifacts themselves (see api/topics.py delete_topic).

    ``owner_id`` null = global/shared (free, deduped one-per-scope-per-lens via
    the partial unique index below); set = personal (Phase 1 request flow).
    """

    __tablename__ = "audio_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    scope_type = Column(SAEnum(AudioScopeType, name="audioscopetype"), nullable=False, index=True)
    scope_ref = Column(UUID(as_uuid=True), nullable=False, index=True)
    knowledge_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topic_knowledge.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    lens = Column(SAEnum(AudioLens, name="audiolens"), nullable=False, default=AudioLens.DEFAULT)
    instruction = Column(Text, nullable=True)  # only set for lens=user_instruction

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    cost_credits = Column(Integer, nullable=False, default=0)

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
    stale = Column(Boolean, nullable=False, default=False)  # source knowledge re-synthesized since
    generated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    knowledge = relationship("TopicKnowledge", back_populates="audio_artifacts")

    __table_args__ = (
        # The shared/global artifact is unique per (scope, lens) — dedup rule from
        # docs/listen-audio-plan.md §1. Personal artifacts (owner_id set) are exempt;
        # their own dedup key lands with the Phase 1 request flow.
        Index(
            "uq_audio_artifact_global_scope_lens",
            "scope_type",
            "scope_ref",
            "lens",
            unique=True,
            postgresql_where=text("owner_id IS NULL"),
        ),
    )
