"""
NotesOS API - Terms

The user's personal, reusable study-period labels, composed from controlled
components. `GET /vocab` feeds the pickers; create/list/update/delete manage the
user's own terms. Terms are filed onto enrollments via the courses API.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.course import CourseEnrollment
from app.models.term import DivisionType, Term
from app.models.user import User
from app.services.terms import (
    DIVISION_VALUES,
    SUGGESTED_LEVELS,
    TermValidationError,
    compose_label,
    find_or_create_term,
    validate_components,
)

router = APIRouter()


class TermCreate(BaseModel):
    division_type: DivisionType
    division_value: str
    study_level: Optional[str] = None


def _serialize(term: Term, course_count: int | None = None) -> dict:
    data = {
        "id": str(term.id),
        "label": term.label,
        "division_type": term.division_type.value,
        "division_value": term.division_value,
        "study_level": term.study_level,
    }
    if course_count is not None:
        data["course_count"] = course_count
    return data


@router.get("/vocab")
async def term_vocab():
    """Controlled vocabularies for the term pickers."""
    return {
        "division_types": [t.value for t in DivisionType],
        "division_values": {t.value: vals for t, vals in DIVISION_VALUES.items()},
        "suggested_levels": SUGGESTED_LEVELS,
    }


@router.get("")
async def list_terms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's terms with how many courses are filed under each."""
    terms = (
        await db.execute(
            select(Term)
            .where(Term.user_id == current_user.id)
            .order_by(Term.label)
        )
    ).scalars().all()

    counts = dict(
        (
            await db.execute(
                select(CourseEnrollment.term_id, func.count())
                .where(CourseEnrollment.user_id == current_user.id)
                .where(CourseEnrollment.term_id.isnot(None))
                .group_by(CourseEnrollment.term_id)
            )
        ).all()
    )
    return {"terms": [_serialize(t, counts.get(t.id, 0)) for t in terms]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_term(
    request: TermCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create (or reuse) a term from components."""
    try:
        term = await find_or_create_term(
            db,
            user_id=current_user.id,
            division_type=request.division_type,
            division_value=request.division_value,
            study_level=request.study_level,
        )
    except TermValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"term": _serialize(term)}


@router.patch("/{term_id}")
async def update_term(
    term_id: str,
    request: TermCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit a term's components and recompose its label (applies to every course
    filed under it — rename once)."""
    term = await db.scalar(
        select(Term).where(Term.id == term_id, Term.user_id == current_user.id)
    )
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    try:
        validate_components(request.division_type, request.division_value)
    except TermValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    level = (request.study_level or "").strip() or None
    new_label = compose_label(request.division_type, request.division_value, level)
    # Guard the (user_id, label) uniqueness against another existing term.
    clash = await db.scalar(
        select(Term).where(
            Term.user_id == current_user.id,
            Term.label == new_label,
            Term.id != term.id,
        )
    )
    if clash:
        raise HTTPException(status_code=400, detail="You already have a term with these settings.")

    term.division_type = request.division_type
    term.division_value = request.division_value
    term.study_level = level
    term.label = new_label
    await db.commit()
    return {"term": _serialize(term)}


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_term(
    term_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a term. Courses filed under it become unfiled (term_id → NULL)."""
    term = await db.scalar(
        select(Term).where(Term.id == term_id, Term.user_id == current_user.id)
    )
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    await db.delete(term)
    await db.commit()
