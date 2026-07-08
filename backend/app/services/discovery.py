"""
Discovery — the emergent graph made navigable.

Your classmates are the people you share a course with; "courses your classmates
are taking" is what those people are in that you are not. Both fall straight out
of `course_enrollments` overlap — no stored cohort, no public browse, no new join
primitive. This is why the old `join?search=` public course lookup could go: the
graph is the discovery surface.

Two rules from the architecture doc hold here:
- **Notify, don't enroll.** Discovery only ever *surfaces* a course with a join
  affordance; it never adds anyone to anything. Auto-enrolling turns every
  membership list into noise and has the app deciding for the user.
- **Activity gates visibility.** A course earns a place in a classmate's feed by
  having activity — an upload, or a second member. A solo, empty course is
  invisible weight and stays invisible; spam nobody sees isn't a moderation
  problem. `ACTIVITY_*` below are the gate, documented and tunable.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, CourseEnrollment, Resource, Topic, User

# A course surfaces in discovery once it clears *either* bar: someone uploaded to
# it, or a second person joined. Both are "a human did something here" signals.
ACTIVITY_MIN_RESOURCES = 1
ACTIVITY_MIN_MEMBERS = 2


async def get_classmates(db: AsyncSession, user_id) -> list[dict]:
    """The emergent set: everyone who shares at least one course with the user.

    Ranked by how many courses they share — your closest classmates first.
    """
    my_courses = select(CourseEnrollment.course_id).where(
        CourseEnrollment.user_id == user_id
    )
    shared = func.count(func.distinct(CourseEnrollment.course_id))

    rows = (
        await db.execute(
            select(
                User.id,
                User.full_name,
                User.avatar_url,
                shared.label("shared_courses"),
            )
            .join(CourseEnrollment, CourseEnrollment.user_id == User.id)
            .where(CourseEnrollment.course_id.in_(my_courses))
            .where(User.id != user_id)
            .group_by(User.id)
            .order_by(shared.desc(), User.full_name)
        )
    ).all()

    return [
        {
            "id": str(r.id),
            "full_name": r.full_name,
            "avatar_url": r.avatar_url,
            "shared_courses": r.shared_courses,
        }
        for r in rows
    ]


@dataclass(frozen=True)
class DiscoveredCourse:
    """A course a user's classmates are in that the user is not, with its why."""

    course_id: str
    code: str
    name: str
    classmate_count: int
    member_count: int
    resource_count: int

    def as_dict(self) -> dict:
        return {
            "course_id": self.course_id,
            "code": self.code,
            "name": self.name,
            "member_count": self.member_count,
            # Why it surfaced — lets the client say "4 of your classmates are here".
            "signals": {
                "classmates_here": self.classmate_count,
                "resource_count": self.resource_count,
            },
        }


async def get_classmate_courses(db: AsyncSession, user_id) -> list[dict]:
    """Courses your classmates are taking that you are not — activity-gated.

    Pull-only and ambient: this surfaces courses, it never enrolls. Ranked by how
    many of your classmates are in each, then by activity.
    """
    my_courses = select(CourseEnrollment.course_id).where(
        CourseEnrollment.user_id == user_id
    )
    classmate_ids = (
        select(CourseEnrollment.user_id)
        .where(CourseEnrollment.course_id.in_(my_courses))
        .where(CourseEnrollment.user_id != user_id)
        .distinct()
    )

    # Candidate courses: what my classmates are enrolled in that I'm not, plus how
    # many of them are in each (the primary ranking signal).
    classmate_count = func.count(func.distinct(CourseEnrollment.user_id))
    cand_rows = (
        await db.execute(
            select(CourseEnrollment.course_id, classmate_count.label("classmates"))
            .where(CourseEnrollment.user_id.in_(classmate_ids))
            .where(CourseEnrollment.course_id.not_in(my_courses))
            .group_by(CourseEnrollment.course_id)
        )
    ).all()
    if not cand_rows:
        return []

    candidate_ids = [r.course_id for r in cand_rows]
    classmate_by_course = {r.course_id: r.classmates for r in cand_rows}

    member_by_course = {
        course_id: count
        for course_id, count in (
            await db.execute(
                select(CourseEnrollment.course_id, func.count())
                .where(CourseEnrollment.course_id.in_(candidate_ids))
                .group_by(CourseEnrollment.course_id)
            )
        ).all()
    }
    resource_by_course = {
        course_id: count
        for course_id, count in (
            await db.execute(
                select(Topic.course_id, func.count(Resource.id))
                .join(Resource, Resource.topic_id == Topic.id)
                .where(Topic.course_id.in_(candidate_ids))
                .group_by(Topic.course_id)
            )
        ).all()
    }

    course_rows = (
        await db.execute(
            select(Course).where(Course.id.in_(candidate_ids), Course.is_active)
        )
    ).scalars().all()

    discovered: list[DiscoveredCourse] = []
    for course in course_rows:
        resource_count = resource_by_course.get(course.id, 0)
        member_count = member_by_course.get(course.id, 0)
        # Activity gate — a solo, empty course never surfaces.
        if resource_count < ACTIVITY_MIN_RESOURCES and member_count < ACTIVITY_MIN_MEMBERS:
            continue
        discovered.append(
            DiscoveredCourse(
                course_id=str(course.id),
                code=course.code,
                name=course.name,
                classmate_count=classmate_by_course.get(course.id, 0),
                member_count=member_count,
                resource_count=resource_count,
            )
        )

    discovered.sort(
        key=lambda d: (d.classmate_count, d.resource_count, d.member_count),
        reverse=True,
    )
    return [d.as_dict() for d in discovered]
