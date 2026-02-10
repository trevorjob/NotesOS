"""
NotesOS Models - Class & Classmate Models (Global Invites)
"""

import uuid
import secrets
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def generate_class_code() -> str:
    """Generate a unique class invite code like 'CLASS-XK4M-9N2P'."""
    segment1 = secrets.token_hex(2).upper()
    segment2 = secrets.token_hex(2).upper()
    return f"CLASS-{segment1}-{segment2}"


class Class(Base):
    """
    Class model - represents a study group for global invites.

    When someone joins via a class invite, they get enrolled in
    ALL courses that the class owner is enrolled in.
    """

    __tablename__ = "classes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Owner of this class (whose courses will be shared)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Human-readable name (optional)
    name = Column(String(100), nullable=True)  # e.g., "CS101 Study Group"

    # Invite code for joining
    invite_code = Column(
        String(20), unique=True, nullable=False, default=generate_class_code
    )

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    classmates = relationship(
        "Classmate", back_populates="class_", cascade="all, delete-orphan"
    )


class Classmate(Base):
    """
    Classmate model - tracks users who joined via a class invite.

    This allows the owner to see who joined through their invite,
    and enables future features like:
    - Auto-enrolling classmates in new courses the owner creates
    - Removing a classmate from all courses at once
    """

    __tablename__ = "classmates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Which class invite they used
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False)

    # Who joined
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # When they joined
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    class_ = relationship("Class", back_populates="classmates")

    __table_args__ = (
        # One entry per user-class pair
        {},
    )
