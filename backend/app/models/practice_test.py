"""
NotesOS Models — Authored practice test (B14).

A **practice test** is the second of the two "quiz" intents (product-map, LOCKED
2026-07-25): where the review loop is *the app picks what's due, per concept, on
demand*, an authored test is *a user picks scope + count + type* and produces a
**durable, course-shared object** that classmates can take.

It is the one genuinely non-derivable new table (invariant #2 holds — an *authored
artifact* can't be derived, same justification as D5's reports). It stores the
frozen, concept-anchored questions **with their answer keys**; those are sanitized
exactly like ``/next`` when a question is served to a taker.

What it deliberately does **not** store: attempts, sessions, or a test-level score.
Taking a test is an ordinary run of retrieval atoms — each answered question records
a per-concept ``RetrievalAttempt`` through the engine (FSRS / calibration / recognition),
and the "result" is derived from that append-only log. There is no test-attempt table.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base

# Generation lifecycle — plain strings (KISS: no native enum, no enum migration).
GEN_GENERATING = "generating"
GEN_READY = "ready"
GEN_FAILED = "failed"

# The only modes an authored set supports — the posed-question modes. Ramble / teach /
# brain-dump are single-dump free recall and do not set-ify (build-guide §4 B14).
AUTHORED_MODES = ("quiz", "pretest")

# Question shapes the builder can request. essay is the genuine one-off, AI-graded
# through the existing grader (an open-answer path, same as short_answer downstream).
QUESTION_TYPES = ("mcq", "short_answer", "essay")


class PracticeTest(Base):
    """A shareable, concept-anchored question set authored by one enrolled user."""

    __tablename__ = "practice_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(255), nullable=False)
    mode = Column(String(16), nullable=False)          # "quiz" | "pretest"
    question_type = Column(String(16), nullable=False)  # "mcq" | "short_answer" | "essay"

    # The chosen scope: the topic ids the set draws its concepts from. An empty list
    # means the whole course. Stored (not derived) because it's part of the authored
    # artifact — what the creator chose to test on.
    scope_topic_ids = Column(JSONB, nullable=False, default=list)

    question_count = Column(Integer, nullable=False, default=0)

    # Async generation progress (reuses A2's capture WS pattern).
    generation_status = Column(String(16), nullable=False, default=GEN_GENERATING)
    questions_done = Column(Integer, nullable=False, default=0)
    failure_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    questions = relationship(
        "PracticeTestQuestion",
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="PracticeTestQuestion.order_index",
    )


class PracticeTestQuestion(Base):
    """One frozen, concept-anchored question — generated once, then immutable.

    Freezing is what makes the test stable and shareable: nobody regenerates it, so
    every taker sees the same questions. ``payload`` carries the full ``Challenge``
    payload including the answer key; the API strips the sensitive keys before serving
    it to a taker and uses the full copy to grade.
    """

    __tablename__ = "practice_test_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(
        UUID(as_uuid=True),
        ForeignKey("practice_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id = Column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order_index = Column(Integer, nullable=False, default=0)
    prompt = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)  # frozen Challenge payload + key

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    test = relationship("PracticeTest", back_populates="questions")
    concept = relationship("Concept")
