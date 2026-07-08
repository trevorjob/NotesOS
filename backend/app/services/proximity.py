"""
Proximity check — course mode.

The core primitive of the emergent-set model: before a course is created, look
for one that already exists *nearby* and offer it, so two students in the same
class land on the same course instead of forking a private copy each.

Unlike schools (objective enough to auto-merge on a good match), courses only
ever produce an *offer*. The creator picks: join a match (merge) or make their
own (fork). Nothing is forced.

Shape of the check:
- **School is the hard filter.** Only courses at the creator's school are ever
  candidates. A creator with no school runs no check (nothing to scope against).
- **Text match** finds the candidates: exact/fuzzy on code or name (pg_trgm).
- **People signals rank them**, in the order the architecture doc fixes:
  program > entry_year > shared classmates. Two different "CHM 101" can coexist
  at a big school; the one your programme-mates already sit in is the one you
  mean. Text similarity is only the final tie-break.

The match threshold is deliberately loose to start (prompt more, fork less) and
is the single instrumentation knob — tighten it once real creation data shows
where accidental forks vs. prompt fatigue actually land.
"""

from dataclasses import dataclass

from sqlalchemy import false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, CourseEnrollment, User

# Loose on purpose — see module docstring. This is the knob to tune from data.
PROXIMITY_MATCH_THRESHOLD = 0.3
# Cap the offer list; more than a handful is noise, not a choice.
CANDIDATE_LIMIT = 8


@dataclass(frozen=True)
class CourseCandidate:
    """A near-match course offered to a would-be creator, with its ranking signals."""

    course_id: str
    code: str
    name: str
    member_count: int
    text_similarity: float
    program_overlap: int
    entry_year_overlap: int
    classmate_overlap: int

    def as_dict(self) -> dict:
        return {
            "course_id": self.course_id,
            "code": self.code,
            "name": self.name,
            "member_count": self.member_count,
            # Surfaced so the client can say *why* this is offered
            # ("3 of your classmates are here", "same programme").
            "signals": {
                "same_program": self.program_overlap,
                "same_entry_year": self.entry_year_overlap,
                "classmates_here": self.classmate_overlap,
            },
        }


async def find_course_candidates(
    db: AsyncSession,
    *,
    creator: User,
    code: str,
    name: str,
) -> list[CourseCandidate]:
    """Return existing courses the creator might mean instead, best match first.

    Empty when there is nothing to offer: no school on the creator, blank input,
    or no text match at the creator's school. The caller decides what an empty
    list means (proceed to create).
    """
    if creator.school_id is None:
        return []

    code = (code or "").strip()
    name = (name or "").strip()
    if not code and not name:
        return []

    code_sim = func.similarity(Course.code, code)
    name_sim = func.similarity(Course.name, name)
    text_sim = func.greatest(code_sim, name_sim).label("text_sim")

    # Candidates: same school (hard filter), active, and a text match on either
    # code or name — exact code always qualifies, fuzzy above the threshold.
    match_conds = []
    if code:
        match_conds.append(Course.code.ilike(code))
        match_conds.append(code_sim >= PROXIMITY_MATCH_THRESHOLD)
    if name:
        match_conds.append(name_sim >= PROXIMITY_MATCH_THRESHOLD)

    rows = (
        await db.execute(
            select(Course.id, Course.code, Course.name, text_sim)
            .where(Course.school_id == creator.school_id)
            .where(Course.is_active)
            .where(or_(*match_conds))
            .order_by(text_sim.desc())
            .limit(CANDIDATE_LIMIT)
        )
    ).all()
    if not rows:
        return []

    candidate_ids = [r.id for r in rows]

    member_counts = await _member_counts(db, candidate_ids)
    program_overlap, entry_year_overlap = await _people_overlap(db, creator, candidate_ids)
    classmate_overlap = await _classmate_overlap(db, creator, candidate_ids)

    candidates = [
        CourseCandidate(
            course_id=str(r.id),
            code=r.code,
            name=r.name,
            member_count=member_counts.get(r.id, 0),
            text_similarity=float(r.text_sim or 0.0),
            program_overlap=program_overlap.get(r.id, 0),
            entry_year_overlap=entry_year_overlap.get(r.id, 0),
            classmate_overlap=classmate_overlap.get(r.id, 0),
        )
        for r in rows
    ]

    # People proximity leads; text similarity only breaks ties. The order of the
    # first three keys is the doc's ranking contract: program > entry_year > shared.
    candidates.sort(
        key=lambda c: (
            c.program_overlap,
            c.entry_year_overlap,
            c.classmate_overlap,
            c.text_similarity,
        ),
        reverse=True,
    )
    return candidates


async def _member_counts(db: AsyncSession, candidate_ids: list) -> dict:
    rows = (
        await db.execute(
            select(CourseEnrollment.course_id, func.count())
            .where(CourseEnrollment.course_id.in_(candidate_ids))
            .group_by(CourseEnrollment.course_id)
        )
    ).all()
    return {course_id: count for course_id, count in rows}


async def _people_overlap(
    db: AsyncSession, creator: User, candidate_ids: list
) -> tuple[dict, dict]:
    """Per candidate: how many of its members share the creator's programme / entry year.

    A signal only counts when the creator actually has that value — an unknown
    programme should not match every other unknown. Excludes the creator.
    """
    # count(*) FILTER (WHERE member.program = creator.program), guarded so a NULL
    # creator value contributes nothing rather than matching NULLs.
    if creator.program:
        program_expr = func.count().filter(User.program == creator.program)
    else:
        program_expr = func.count().filter(false())
    if creator.entry_year is not None:
        year_expr = func.count().filter(User.entry_year == creator.entry_year)
    else:
        year_expr = func.count().filter(false())

    rows = (
        await db.execute(
            select(
                CourseEnrollment.course_id,
                program_expr.label("program_overlap"),
                year_expr.label("entry_year_overlap"),
            )
            .join(User, User.id == CourseEnrollment.user_id)
            .where(CourseEnrollment.course_id.in_(candidate_ids))
            .where(CourseEnrollment.user_id != creator.id)
            .group_by(CourseEnrollment.course_id)
        )
    ).all()
    program_map = {r.course_id: r.program_overlap for r in rows}
    year_map = {r.course_id: r.entry_year_overlap for r in rows}
    return program_map, year_map


async def _classmate_overlap(
    db: AsyncSession, creator: User, candidate_ids: list
) -> dict:
    """Per candidate: how many of its members are already the creator's classmates.

    A classmate is anyone the creator already shares at least one course with —
    the emergent graph. This is the "shared courses" ranking signal made concrete:
    a candidate full of people you already study with is almost certainly *your*
    section of the course.
    """
    my_courses = select(CourseEnrollment.course_id).where(
        CourseEnrollment.user_id == creator.id
    )
    classmate_ids = (
        select(CourseEnrollment.user_id)
        .where(CourseEnrollment.course_id.in_(my_courses))
        .where(CourseEnrollment.user_id != creator.id)
        .distinct()
    )

    rows = (
        await db.execute(
            select(
                CourseEnrollment.course_id,
                func.count(func.distinct(CourseEnrollment.user_id)),
            )
            .where(CourseEnrollment.course_id.in_(candidate_ids))
            .where(CourseEnrollment.user_id.in_(classmate_ids))
            .group_by(CourseEnrollment.course_id)
        )
    ).all()
    return {course_id: count for course_id, count in rows}
