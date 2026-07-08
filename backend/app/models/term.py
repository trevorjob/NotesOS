"""
NotesOS Models - Term

A Term is the user's personal arrangement of a study period — "200 Level ·
Second Semester · 2026/2027". It is user-scoped and reusable: create it once,
file many courses under it. It is NOT a container — it has no members and owns
no courses; it references the courses you file into it, matching the emergent-set
model ("your position on the map, not the map").

It is built from controlled structured components so the composed `label` is
uniform across users (two people in the same 200-level second semester produce
the identical string) while still travelling across differing academic systems.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DivisionType(str, enum.Enum):
    SEMESTER = "SEMESTER"
    TERM = "TERM"
    QUARTER = "QUARTER"
    TRIMESTER = "TRIMESTER"


class Term(Base):
    __tablename__ = "terms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Structured components.
    division_type = Column(SAEnum(DivisionType, name="divisiontype"), nullable=False)
    division_value = Column(String(32), nullable=False)  # controlled per type
    study_level = Column(String(64), nullable=True)  # "200", "Year 1", "Freshman"...

    # Deterministically composed canonical display label.
    label = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="terms")
    enrollments = relationship("CourseEnrollment", back_populates="term")

    # One term per identical label per user — filing two courses under the same
    # period reuses one row instead of duplicating it.
    __table_args__ = (
        UniqueConstraint("user_id", "label", name="uq_term_user_label"),
    )
