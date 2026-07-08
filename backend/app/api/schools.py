"""
NotesOS API - Schools

Typeahead for the curated school catalogue used at signup. Public (no auth):
school selection happens before an account exists. Actual canonicalisation /
creation runs server-side during registration via app.services.school.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import bindparam, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.schools import normalize_school_name
from app.database import get_db
from app.models.school import School

router = APIRouter()


def _serialize(school: School) -> dict:
    return {"id": str(school.id), "name": school.name, "country": school.country}


@router.get("/search")
async def search_schools(
    q: str = Query("", description="Partial school name"),
    limit: int = Query(10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
):
    """Return curated schools matching `q` for typeahead. Empty `q` lists A–Z."""
    q = q.strip()
    if not q:
        rows = await db.execute(select(School).order_by(School.name).limit(limit))
        return {"schools": [_serialize(s) for s in rows.scalars().all()]}

    norm = normalize_school_name(q)
    pattern = f"%{norm}%"
    sim = func.similarity(School.normalized_name, norm)
    # Also match aliases ("unil" -> "unilag" -> University of Lagos), which the
    # name alone would miss.
    alias_match = text(
        "EXISTS (SELECT 1 FROM jsonb_array_elements_text(schools.aliases) elem "
        "WHERE elem ILIKE :alias_pattern)"
    ).bindparams(bindparam("alias_pattern", value=pattern))
    rows = await db.execute(
        select(School)
        .where(or_(School.normalized_name.ilike(pattern), sim >= 0.2, alias_match))
        .order_by(sim.desc())
        .limit(limit)
    )
    return {"schools": [_serialize(s) for s in rows.scalars().all()]}
