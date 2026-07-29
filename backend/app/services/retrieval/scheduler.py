"""
Spaced-repetition scheduling — the one file that touches the ``fsrs`` package.

We don't invent a scheduler. FSRS (Free Spaced Repetition Scheduler, Anki's default)
is the proven choice, and it maps cleanly onto the model the learning-science doc
implies: FSRS *stability* ≈ Bjork's storage strength, *retrievability* ≈ retrieval
strength (Learning Science Part 7).

Every retrieval mode reduces its outcome to one of four grades; this module turns a
grade into an updated, serialized scheduling state. Isolating the library here means
the rest of the codebase deals only in plain dicts + our own ``Grade`` strings, and a
future FSRS version bump touches nothing else.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fsrs import Card, Rating, Scheduler, State

# The note's heat-map labels (system-spec §4/§5): solid glows, fading dims, shaky just
# slipped, new is untouched. The three-way lit/dim/decayed rendering is design's call —
# this only derives the per-concept state the note renders (see engine → ConceptState).
MASTERY_NEW = "new"
MASTERY_SOLID = "solid"
MASTERY_FADING = "fading"
MASTERY_SHAKY = "shaky"

# The four grades every mode maps its outcome to (mirrors FSRS ratings).
GRADES = ("again", "hard", "good", "easy")
_GRADE_TO_RATING = {
    "again": Rating.Again,  # forgot
    "hard": Rating.Hard,    # recalled with serious difficulty
    "good": Rating.Good,    # recalled after hesitation
    "easy": Rating.Easy,    # recalled easily
}

# Default desired_retention=0.9: schedule the next review for when recall probability
# is predicted to fall to 90%. A single shared, stateless scheduler is fine.
_scheduler = Scheduler()


@dataclass(frozen=True)
class ReviewResult:
    """The updated scheduling state after a graded review.

    ``card`` is the serialized FSRS card (store as-is); the rest are the fields we
    mirror into columns for querying/display, stored as naive UTC to match the DB's
    timezone-less ``DateTime`` columns.
    """

    card: dict
    due: datetime
    stability: Optional[float]
    difficulty: Optional[float]
    state: int
    last_review: Optional[datetime]


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """FSRS returns tz-aware UTC; our DateTime columns are naive UTC."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def new_card() -> dict:
    """Serialized scheduling state for a concept the user has never been tested on."""
    return Card().to_dict()


def apply_review(
    card: Optional[dict], grade: str, *, now: Optional[datetime] = None
) -> ReviewResult:
    """Apply a graded review to a (possibly new) card and return the new state.

    ``card`` is a previously serialized card, or None for a first-ever review.
    ``now`` is a tz-aware datetime (defaults to now, UTC).
    """
    if grade not in _GRADE_TO_RATING:
        raise ValueError(f"unknown grade {grade!r}; expected one of {GRADES}")

    fsrs_card = Card.from_dict(card) if card else Card()
    review_at = now or datetime.now(timezone.utc)
    if review_at.tzinfo is None:
        review_at = review_at.replace(tzinfo=timezone.utc)

    fsrs_card, _log = _scheduler.review_card(
        fsrs_card, _GRADE_TO_RATING[grade], review_datetime=review_at
    )

    return ReviewResult(
        card=fsrs_card.to_dict(),
        due=_naive_utc(fsrs_card.due),
        stability=fsrs_card.stability,
        difficulty=fsrs_card.difficulty,
        state=int(fsrs_card.state.value),
        last_review=_naive_utc(fsrs_card.last_review),
    )


def derive_mastery(
    *,
    reps: int,
    last_grade: Optional[str],
    fsrs_state: Optional[int],
    due: Optional[datetime],
    now: Optional[datetime] = None,
) -> str:
    """Collapse a user's ``ConceptState`` into the note's heat-map label.

    ``due``/``now`` are naive UTC (matching the DB columns). FSRS ``due`` is the
    predicted 90%-retrievability moment, so past-due reads as decaying (fading).
    """
    if reps <= 0:
        return MASTERY_NEW
    if last_grade == "again" or fsrs_state == State.Relearning.value:
        return MASTERY_SHAKY
    now = now or datetime.utcnow()
    if due is not None and due <= now:
        return MASTERY_FADING
    return MASTERY_SOLID
