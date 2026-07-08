"""
NotesOS Models - Retrieval substrate.

The data layer under the retrieval engine and the whole learning-science layer.

- **Concept** — the atomic unit of knowledge, one grain below Topic. Shared across
  the course (like the note and quizzes), extracted at synthesis. The user never
  manages these; the topic stays the unit they *consume*, the concept is the unit
  the app *measures*.
- **RetrievalAttempt** — the append-only event log: every recall event, in any mode.
  Never mutated. Forgetting-history, calibration, and decay are all queries over this.
- **ConceptState** — the per-(user, concept) projection derived from attempts, holding
  the FSRS scheduling state (spaced repetition). One row per user per concept.

FSRS (`fsrs` package) owns the scheduling maths; its serialized Card lives in
``ConceptState.fsrs_card`` with the queryable fields (due, stability, …) mirrored
into columns. See `app.services.retrieval.scheduler`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class Concept(Base):
    """A discrete unit of knowledge within a topic — shared, course-level."""

    __tablename__ = "concepts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized from the topic so course/interleaved scope queries don't need a join.
    course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    text = Column(Text, nullable=False)          # the concept statement / term
    definition = Column(Text, nullable=True)     # optional supporting definition
    embedding = Column(Vector(1536), nullable=True)
    # Provenance: which resource chunks this concept was drawn from.
    source_chunk_ids = Column(JSONB, nullable=True, default=list)
    order_index = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    states = relationship(
        "ConceptState", back_populates="concept", cascade="all, delete-orphan"
    )

    # A concept is identified within its topic by its text; re-synthesis upserts on
    # this so existing rows (and the ConceptStates hanging off them) survive.
    __table_args__ = (
        UniqueConstraint("topic_id", "text", name="uq_concept_topic_text"),
    )


class RetrievalAttempt(Base):
    """One recall event, any mode. Append-only — the source of truth for history."""

    __tablename__ = "retrieval_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id = Column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    mode = Column(String(32), nullable=False, index=True)  # quiz / ramble / teach / pretest

    # Calibration: what the user predicted before answering (0..1), vs. how they did.
    predicted_confidence = Column(Float, nullable=True)
    outcome_score = Column(Float, nullable=True)           # 0..1
    grade = Column(String(8), nullable=True)               # again / hard / good / easy

    challenge = Column(JSONB, nullable=True)  # the generated prompt/question, for audit
    response = Column(JSONB, nullable=True)   # the user's raw response

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    concept = relationship("Concept")


class ConceptState(Base):
    """Per-(user, concept) scheduling state, derived from attempts via FSRS."""

    __tablename__ = "concept_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id = Column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # FSRS scheduling. fsrs_card is the serialized source of truth; the rest mirror it
    # for cheap querying/display without deserializing every row.
    fsrs_card = Column(JSONB, nullable=True)
    due = Column(DateTime, nullable=True, index=True)   # next review time (spaced-due scope)
    stability = Column(Float, nullable=True)            # ~ storage strength (durability)
    difficulty = Column(Float, nullable=True)
    fsrs_state = Column(Integer, nullable=True)         # FSRS State (int)
    last_review = Column(DateTime, nullable=True)

    # Our own counters, off the attempt log — for the forgetting badge / display.
    reps = Column(Integer, nullable=False, default=0)
    lapses = Column(Integer, nullable=False, default=0)  # times forgotten (grade=again)
    last_grade = Column(String(8), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    concept = relationship("Concept", back_populates="states")

    __table_args__ = (
        UniqueConstraint("user_id", "concept_id", name="uq_conceptstate_user_concept"),
    )
