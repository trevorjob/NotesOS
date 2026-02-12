"""
NotesOS Models - Resource Related Models

Resource = one logical piece of study material (text, PDF, DOCX, or multi-page images).
ResourceFile = individual image pages within an image Resource.
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
    Integer,
    ForeignKey,
    Enum as SQLEnum,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class ResourceKind(str, Enum):
    """What kind of resource this is."""

    TEXT = "TEXT"
    PDF = "PDF"
    DOCX = "DOCX"
    IMAGE = "IMAGE"


class SourceType(str, Enum):
    """Source type - determines if OCR cleaning is needed."""

    TEXT = "TEXT"
    PDF = "PDF"
    DOCX = "DOCX"
    HANDWRITTEN = "HANDWRITTEN"
    PRINTED = "PRINTED"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    DISPUTED = "disputed"
    UNVERIFIED = "unverified"


class Resource(Base):
    """
    Resource model - one logical piece of study material.

    Examples:
    - Text typed by user (resource_type=text, file_url=None)
    - A PDF upload (resource_type=pdf, file_url=PDF URL)
    - 5 photos of handwritten notes (resource_type=image, files=5 ResourceFiles)
    """

    __tablename__ = "resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=True)  # Optional - auto-generated if empty
    content = Column(Text, nullable=False)  # Typed text, or extracted/OCR text
    resource_type = Column(
        SQLEnum(ResourceKind, name="resourcetype"),
        default=ResourceKind.TEXT,
        nullable=False,
    )

    # File info (null for text resources, set for PDF/DOCX)
    file_url = Column(Text, nullable=True)
    file_name = Column(String(255), nullable=True)

    # Source type tracking (for OCR cleaning decision)
    source_type = Column(SQLEnum(SourceType), default=SourceType.TEXT, nullable=False)

    # OCR metadata
    is_processed = Column(Boolean, default=False, nullable=False)  # RAG chunking status
    ocr_cleaned = Column(Boolean, default=False, nullable=False)
    original_ocr_text = Column(Text, nullable=True)  # Raw OCR before cleaning
    ocr_confidence = Column(Numeric(4, 3), nullable=True)  # 0.000 - 1.000
    ocr_provider = Column(String(50), nullable=True)  # tesseract or google_vision

    # Fact-checking status
    is_verified = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    topic = relationship("Topic", back_populates="resources")
    files = relationship(
        "ResourceFile", back_populates="resource", cascade="all, delete-orphan"
    )
    chunks = relationship(
        "ResourceChunk", back_populates="resource", cascade="all, delete-orphan"
    )
    fact_checks = relationship(
        "FactCheck", back_populates="resource", cascade="all, delete-orphan"
    )


class ResourceFile(Base):
    """
    Individual image pages within a multi-page image Resource.

    When a user uploads 5 photos of class notes, each becomes a ResourceFile
    under one Resource. The combined OCR text goes in Resource.content.
    """

    __tablename__ = "resource_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"), nullable=False)

    # File info
    file_url = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    file_order = Column(Integer, default=0, nullable=False)  # Page order

    # Per-page OCR data
    ocr_text = Column(Text, nullable=True)
    ocr_confidence = Column(Numeric(4, 3), nullable=True)
    ocr_provider = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    resource = relationship("Resource", back_populates="files")


class ResourceChunk(Base):
    """Resource chunks for RAG - stores text with vector embeddings."""

    __tablename__ = "resource_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"), nullable=False)

    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)

    # Vector embedding (1536 dimensions for OpenAI text-embedding-3-small)
    embedding = Column(Vector(1536), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    resource = relationship("Resource", back_populates="chunks")


class FactCheck(Base):
    """Fact check results for resource claims."""

    __tablename__ = "fact_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"), nullable=False)

    claim_text = Column(Text, nullable=False)
    verification_status = Column(
        SQLEnum(VerificationStatus),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )

    # Sources as JSONB array
    sources = Column(JSONB, nullable=False, default=[])

    confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00 - 1.00
    ai_explanation = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    resource = relationship("Resource", back_populates="fact_checks")


class PreClassResearch(Base):
    """Pre-class research generated by AI for topics."""

    __tablename__ = "pre_class_research"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False)

    research_content = Column(Text, nullable=False)
    sources = Column(JSONB, nullable=False, default=[])
    key_concepts = Column(JSONB, nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    topic = relationship("Topic", back_populates="research")
