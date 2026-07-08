"""
The retrieval-mode plugin boundary.

A *mode* is a way to trigger recall — quiz, ramble, teach, pretest. They differ only
in how they pose a challenge and judge a response; everything else (scope selection,
scheduling, attempt recording, calibration, recognition) is the engine's job. Add a
mode by implementing this Protocol, not by touching the engine.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from app.models.retrieval import Concept
from app.services.retrieval.scheduler import GRADES


@dataclass(frozen=True)
class Challenge:
    """What the user is asked to recall against — a question, a ramble opener, etc."""

    concept_id: str
    prompt: str
    payload: dict = field(default_factory=dict)  # mode-specific (e.g. MCQ options)


@dataclass(frozen=True)
class Outcome:
    """The judged result of a response. ``grade`` drives scheduling."""

    score: float          # 0..1, how well they recalled
    grade: str            # one of scheduler.GRADES
    feedback: Optional[str] = None
    detail: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.grade not in GRADES:
            raise ValueError(f"grade must be one of {GRADES}, got {self.grade!r}")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")


@dataclass
class ModeContext:
    """Everything a mode might need beyond the concept itself (RAG handles, etc.)."""

    db: Any
    user_id: Any
    extra: dict = field(default_factory=dict)


@runtime_checkable
class RetrievalMode(Protocol):
    """A pluggable way to trigger and judge recall of a concept."""

    key: str

    async def generate(self, concept: Concept, ctx: ModeContext) -> Challenge:
        """Pose a challenge for this concept, grounded in the course material."""
        ...

    async def evaluate(
        self, concept: Concept, challenge: Challenge, response: Any, ctx: ModeContext
    ) -> Outcome:
        """Judge the user's response into a score + grade."""
        ...

    def subject_weight(self, subject_type: Optional[str]) -> float:
        """How strongly this mode suits a subject (the subject-aware knob). 0..1."""
        ...
