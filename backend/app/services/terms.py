"""
Term composition service.

A term is built from controlled components and composed into one canonical label.
The composition is deterministic: identical component choices always yield the
identical string, so two students in the same period land on the same term label
(uniformity) while each academic system uses only the pieces it needs (it travels).

- `division_type` + `division_value` are strictly controlled (enum + per-type set).
- `study_level` is suggested but a typed value is accepted (systems vary too much
  to fully enumerate).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.term import DivisionType, Term

# Allowed division_value per division_type (strict).
DIVISION_VALUES: dict[DivisionType, list[str]] = {
    DivisionType.SEMESTER: ["First", "Second", "Third", "Fall", "Spring", "Summer", "Winter"],
    DivisionType.TERM: ["1", "2", "3", "First", "Second", "Third"],
    DivisionType.QUARTER: ["Fall", "Winter", "Spring", "Summer"],
    DivisionType.TRIMESTER: ["First", "Second", "Third"],
}

# Suggested study levels for the picker. Not exhaustive — a typed value is allowed.
SUGGESTED_LEVELS: list[str] = [
    "100", "200", "300", "400", "500", "600",
    "Year 1", "Year 2", "Year 3", "Year 4",
    "Freshman", "Sophomore", "Junior", "Senior",
]


class TermValidationError(ValueError):
    """Raised when components fail validation (mapped to HTTP 400 by the route)."""


def _level_display(study_level: str) -> str:
    """Render a level for the label: bare numbers get 'Level' appended."""
    s = study_level.strip()
    return f"{s} Level" if s.isdigit() else s


def validate_components(division_type: DivisionType, division_value: str) -> None:
    """Enforce the controlled vocabulary. Raises TermValidationError."""
    allowed = DIVISION_VALUES.get(division_type, [])
    if division_value not in allowed:
        raise TermValidationError(
            f"{division_value!r} is not valid for {division_type.value}. "
            f"Allowed: {', '.join(allowed)}."
        )


def compose_label(
    division_type: DivisionType,
    division_value: str,
    study_level: str | None = None,
) -> str:
    """Jam the components into the canonical label. Empty pieces are skipped."""
    division_word = division_type.value.title()  # SEMESTER -> "Semester"
    # Numeric values read "Term 2"; named values read "Second Semester".
    if division_value.strip().isdigit():
        division_part = f"{division_word} {division_value}"
    else:
        division_part = f"{division_value} {division_word}"

    parts: list[str] = []
    if study_level and study_level.strip():
        parts.append(_level_display(study_level))
    parts.append(division_part)
    return " · ".join(parts)


async def find_or_create_term(
    db: AsyncSession,
    *,
    user_id,
    division_type: DivisionType,
    division_value: str,
    study_level: str | None = None,
) -> Term:
    """Resolve a user's term from components, reusing an identical one if present.

    Validates and composes, then dedupes on (user_id, label). Flushes so the row
    has an id; the caller owns the transaction.
    """
    validate_components(division_type, division_value)
    level = (study_level or "").strip() or None
    label = compose_label(division_type, division_value, level)

    existing = await db.scalar(
        select(Term).where(Term.user_id == user_id, Term.label == label)
    )
    if existing:
        return existing

    term = Term(
        user_id=user_id,
        division_type=division_type,
        division_value=division_value,
        study_level=level,
        label=label,
    )
    db.add(term)
    await db.flush()
    return term
