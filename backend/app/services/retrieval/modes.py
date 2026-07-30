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


def score_to_grade(score: float) -> str:
    """Map a normalized 0..1 recall score to an FSRS grade.

    The shared default across modes. Thresholds are deliberately conservative —
    retrieval rewards *demonstrated* recall, and a shaky pass should schedule sooner
    (``hard``), not later. A mode may override this mapping when its science differs
    (e.g. pretest, where a miss is expected and mustn't fling the concept far out).
    """
    if score < 0.5:
        return "again"
    if score < 0.7:
        return "hard"
    if score < 0.9:
        return "good"
    return "easy"


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

    # NOTE: a mode no longer knows about subjects. How strongly a mode suits a subject
    # family lives in ``subject_profiles.PROFILES`` (keyed by mode), not on the mode.


# ── Conversational modes (teach · ramble) ──────────────────────────────────────
# Some modes are a back-and-forth, not one answer: the dialogue IS the retrieval act.
# They keep the one-shot generate/evaluate above (run_once, offline, tests) AND add the
# turn loop below. The invariant is unchanged — one FSRS grade committed once, at close.

# A hard ceiling on the back-and-forth, enforced by the driver (not the mode): after this
# many user turns the mode closes gracefully regardless of how live the thread is.
MAX_CONVO_TURNS = 7

ROLE_AI = "ai"
ROLE_USER = "user"


@dataclass(frozen=True)
class ConversationTurn:
    """One line of a conversational bout — an AI probe or the user's reply."""

    role: str  # ROLE_AI | ROLE_USER
    text: str


@dataclass(frozen=True)
class TurnResult:
    """A mode's decision after a user turn: dig with ``reply``, or ``closed`` (grade now)."""

    closed: bool
    reply: Optional[str] = None          # the next probe, when not closed
    close_reason: Optional[str] = None   # why we stopped (dug_enough, emptied_out, …)


def is_conversational(mode: Any) -> bool:
    """Whether a mode runs the open/turn/close dialogue loop instead of one-shot."""
    return bool(getattr(mode, "conversational", False))


def user_turns(history: list[ConversationTurn]) -> list[ConversationTurn]:
    return [t for t in history if t.role == ROLE_USER]


def join_user_turns(history: list[ConversationTurn]) -> str:
    """The user's side of the dialogue as one block — what close() grades over."""
    return "\n".join(t.text.strip() for t in user_turns(history) if t.text.strip())
