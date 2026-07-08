"""
NotesOS Models - Course Related Models
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Text,
    Integer,
    ForeignKey,
    UniqueConstraint,
)
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

    # Course creator (but no special permissions beyond deletion)
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # School this course belongs to — the hard filter for the proximity check.
    # Nullable during migration; set from the creator's school on creation.
    school_id = Column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Direct-invite code — every course has one. There is no public/private
    # distinction: courses are reached by creation, discovery through the
    # classmate graph, or a direct invite.
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
    school = relationship("School", back_populates="courses")


class CourseEnrollment(Base):
    """Course enrollment - links users to courses."""

    __tablename__ = "course_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    course_id = Column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True
    )
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # The user's personal Term this course is filed under. The term lives on the
    # enrolment, not the course: a shared course is an institutional fact, but how
    # you file it into a study period is your own view of the map. Optional —
    # a course can be unfiled and assigned a term later.
    term_id = Column(
        UUID(as_uuid=True),
        ForeignKey("terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    course = relationship("Course", back_populates="enrollments")
    term = relationship("Term", back_populates="enrollments")

    # A user appears at most once per course. This is load-bearing: the classmate
    # graph (emergent-set model) is computed from this table, so duplicate rows
    # would double-count overlap.
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_enrollment_user_course"),
    )


class Topic(Base):
    """Topic model - sections/weeks within a course."""

    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True
    )
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
    knowledge = relationship(
        "TopicKnowledge", back_populates="topic", uselist=False, cascade="all, delete-orphan"
    )
    audio_lessons = relationship(
        "AudioLesson", back_populates="topic", cascade="all, delete-orphan"
    )


class CourseOutline(Base):
    """Course outline/syllabus uploads."""

    __tablename__ = "course_outlines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True
    )
    uploaded_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    outline_content = Column(Text, nullable=False)
    file_url = Column(Text, nullable=True)
    parsed_topics = Column(Text, nullable=True)  # JSONB in production

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
