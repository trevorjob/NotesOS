"""
NotesOS Models - Test Related Models
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


class TestType(str, Enum):
    PRACTICE = "practice"
    MOCK = "mock"
    SELF_TEST = "self-test"


class QuestionType(str, Enum):
    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"


class Test(Base):
    """Test/quiz model."""

    __tablename__ = "tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    test_type = Column(SQLEnum(TestType), default=TestType.PRACTICE, nullable=False)
    topics = Column(JSONB, nullable=False, default=[])  # Array of topic IDs
    question_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


    # Relationships
    course = relationship("Course", back_populates="tests")
    questions = relationship(
        "TestQuestion", back_populates="test", cascade="all, delete-orphan"
    )
    attempts = relationship(
        "TestAttempt", back_populates="test", cascade="all, delete-orphan"
    )


class TestQuestion(Base):
    """Individual test questions."""

    __tablename__ = "test_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey("tests.id"), nullable=False)

    question_text = Column(Text, nullable=False)
    question_type = Column(
        SQLEnum(QuestionType), default=QuestionType.MCQ, nullable=False
    )
    correct_answer = Column(Text, nullable=True)
    answer_options = Column(JSONB, nullable=True)  # For MCQ
    points = Column(Integer, default=1, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)

    # Relationships
    test = relationship("Test", back_populates="questions")
    answers = relationship(
        "TestAnswer", back_populates="question", cascade="all, delete-orphan"
    )


class TestAttempt(Base):
    """User's attempt at a test."""

    __tablename__ = "test_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey("tests.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    total_score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Integer, nullable=False, default=0)

    # Relationships
    test = relationship("Test", back_populates="attempts")
    answers = relationship(
        "TestAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )


class TestAnswer(Base):
    """Individual answers to test questions."""

    __tablename__ = "test_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(
        UUID(as_uuid=True), ForeignKey("test_attempts.id"), nullable=False
    )
    question_id = Column(
        UUID(as_uuid=True), ForeignKey("test_questions.id"), nullable=False
    )

    # Answer content
    answer_text = Column(Text, nullable=True)
    answer_audio_url = Column(Text, nullable=True)
    transcription = Column(Text, nullable=True)

    # Grading
    score = Column(Numeric(5, 2), nullable=True)
    ai_feedback = Column(Text, nullable=True)
    encouragement = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    attempt = relationship("TestAttempt", back_populates="answers")
    question = relationship("TestQuestion", back_populates="answers")
