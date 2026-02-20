"""
NotesOS Models - Course Related Models
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Course(Base):
    """Course model - peer-created study groups."""

    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    semester = Column(String(50), nullable=True)

    # Course creator (but no special permissions beyond deletion)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Privacy
    is_public = Column(Boolean, default=True, nullable=False)
    invite_code = Column(String(20), unique=True, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    topics = relationship(
        "Topic", back_populates="course", cascade="all, delete-orphan"
    )
    enrollments = relationship(
        "CourseEnrollment", back_populates="course", cascade="all, delete-orphan"
    )
    tests = relationship("Test", back_populates="course", cascade="all, delete-orphan")
    user_progress = relationship(
        "UserProgress", back_populates="course", cascade="all, delete-orphan"
    )
    ai_conversations = relationship(
        "AIConversation", back_populates="course", cascade="all, delete-orphan"
    )


class CourseEnrollment(Base):
    """Course enrollment - links users to courses."""

    __tablename__ = "course_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    course = relationship("Course", back_populates="enrollments")

    __table_args__ = (
        # One enrollment per user-course pair
        {"sqlite_autoincrement": True},
    )


class Topic(Base):
    """Topic model - sections/weeks within a course."""

    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    week_number = Column(Integer, nullable=True)
    order_index = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    course = relationship("Course", back_populates="topics")
    resources = relationship(
        "Resource", back_populates="topic", cascade="all, delete-orphan"
    )
    research = relationship(
        "PreClassResearch", back_populates="topic", cascade="all, delete-orphan"
    )
    study_sessions = relationship(
        "StudySession", back_populates="topic", cascade="all, delete-orphan"
    )
    user_progress = relationship(
        "UserProgress", back_populates="topic", cascade="all, delete-orphan"
    )
    ai_conversations = relationship(
        "AIConversation", back_populates="topic", cascade="all, delete-orphan"
    )


class CourseOutline(Base):
    """Course outline/syllabus uploads."""

    __tablename__ = "course_outlines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    outline_content = Column(Text, nullable=False)
    file_url = Column(Text, nullable=True)
    parsed_topics = Column(Text, nullable=True)  # JSONB in production

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
