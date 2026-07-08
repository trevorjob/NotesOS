"""
School canonicalisation service.

This is the first, simplest incarnation of the proximity check: before a school
row is created, look for one that already exists (exact key, alias, then fuzzy
trgm match) and reuse it. Unlike courses, schools auto-merge on a good match —
they're objective enough that a student typing "Unilag" should land on the
existing "University of Lagos" without being asked.

Requires the pg_trgm extension (enabled in the Phase 0.2 migration).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.schools import SCHOOL_MATCH_THRESHOLD, normalize_school_name
from app.models.school import School


async def find_school(db: AsyncSession, raw_name: str) -> School | None:
    """Return the best existing match for a typed name, or None.

    Order: exact normalized key -> alias containment -> fuzzy trgm above threshold.
    """
    norm = normalize_school_name(raw_name)
    if not norm:
        return None

    # 1. Exact canonical key (unique + indexed).
    exact = await db.scalar(select(School).where(School.normalized_name == norm))
    if exact:
        return exact

    # 2. Known alias (JSONB array containment: aliases @> ["norm"]).
    alias_hit = await db.scalar(
        select(School).where(School.aliases.contains([norm])).limit(1)
    )
    if alias_hit:
        return alias_hit

    # 3. Fuzzy match on the canonical key.
    sim = func.similarity(School.normalized_name, norm)
    row = (
        await db.execute(
            select(School, sim.label("sim"))
            .where(sim >= SCHOOL_MATCH_THRESHOLD)
            .order_by(sim.desc())
            .limit(1)
        )
    ).first()
    if row:
        return row[0]

    return None


async def find_or_create_school(
    db: AsyncSession, raw_name: str, *, country: str | None = None
) -> School | None:
    """Resolve a typed school name to a canonical row, creating one if needed.

    Returns None only for an empty/blank input. The caller is responsible for the
    surrounding transaction; this flushes so the row gets an id but does not commit.
    """
    norm = normalize_school_name(raw_name)
    if not norm:
        return None

    existing = await find_school(db, raw_name)
    if existing:
        return existing

    school = School(
        name=raw_name.strip(),
        normalized_name=norm,
        country=country,
        aliases=[],
    )
    db.add(school)
    await db.flush()
    return school
