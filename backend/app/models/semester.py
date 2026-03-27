"""
NotesOS Models - Semester and SemesterMember Models
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Date,
    ForeignKey,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class SemesterRole(str, Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"


class Semester(Base):
    """Semester — optional grouping layer above courses."""

    __tablename__ = "semesters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    name = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Short, readable, non-expiring invite code (8 alphanumeric chars)
    invite_code = Column(String(20), unique=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    members = relationship(
        "SemesterMember", back_populates="semester", cascade="all, delete-orphan"
    )
    courses = relationship("Course", back_populates="semester_ref")


class SemesterMember(Base):
    """Join table linking users to semesters with roles."""

    __tablename__ = "semester_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    semester_id = Column(
        UUID(as_uuid=True), ForeignKey("semesters.id"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    role = Column(SQLEnum(SemesterRole), nullable=False, default=SemesterRole.MEMBER)

    # Relationships
    semester = relationship("Semester", back_populates="members")

    __table_args__ = (UniqueConstraint("semester_id", "user_id", name="uq_semester_member"),)
