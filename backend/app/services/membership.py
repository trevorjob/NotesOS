"""
Membership visibility — one rule, applied everywhere peers see or count each other.

**Soft-deleted users are invisible to other users.** A deactivated account
(`is_active = False`, see the account-deletion flow) keeps its row and its uploaded
resources (so shared notes don't break), but must never appear in a classmate list,
a discovery/cohort signal, a proximity offer, or a "N members" count. Every
enrollment-based aggregation that another user can see routes through here so the
rule lives in one place instead of being re-derived (and forgotten) per query.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CourseEnrollment, User


def active_user_ids():
    """Subquery of user ids that are active — the set visible to peers.

    Use as ``CourseEnrollment.user_id.in_(active_user_ids())`` to drop soft-deleted
    users from an enrollment-derived list of people.
    """
    return select(User.id).where(User.is_active)


async def active_member_counts(db: AsyncSession, course_ids: list) -> dict:
    """Per-course count of **active** members only (soft-deleted users excluded)."""
    if not course_ids:
        return {}
    rows = (
        await db.execute(
            select(CourseEnrollment.course_id, func.count())
            .join(User, User.id == CourseEnrollment.user_id)
            .where(CourseEnrollment.course_id.in_(course_ids))
            .where(User.is_active)
            .group_by(CourseEnrollment.course_id)
        )
    ).all()
    return {course_id: count for course_id, count in rows}
