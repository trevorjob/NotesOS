"""
NotesOS Models - School

School is the top of the universal spine (School -> Course -> Topic -> Resources)
and the hard filter for the proximity check: nothing outside your school ever
surfaces. `normalized_name` is unique so "Unilag"/"UNILAG"/"University of Lagos"
can't fragment into separate rows. It is an institutional fact, owned by no one.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Display name, e.g. "University of Lagos".
    name = Column(String(255), nullable=False)
    # Canonical comparison key (lowercase, alnum, single-spaced). Deduplicates.
    normalized_name = Column(String(255), nullable=False, unique=True, index=True)

    # ISO country hint (e.g. "NG"). Coarse grouping signal, not load-bearing.
    country = Column(String(8), nullable=True)

    # Pre-normalised alternative spellings ("unilag") for alias matching.
    aliases = Column(JSONB, nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    users = relationship("User", back_populates="school")
    courses = relationship("Course", back_populates="school")
