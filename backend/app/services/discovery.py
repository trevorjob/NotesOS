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
from app.services.membership import active_member_counts, active_user_ids

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
            .where(User.is_active)  # soft-deleted classmates are invisible to peers
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


# Bound the contact upload — a phone book can be huge, and the match query is an
# `IN (...)` over the set. More than this is truncated (best-effort, not an error).
MAX_CONTACT_HASHES = 2000


async def match_contacts(db: AsyncSession, user, phone_hashes: list[str]) -> list[dict]:
    """Which of the caller's contacts are on NotesOS, with the courses they're in.

    Contacts arrive as SHA-256 hashes of canonical phones (the raw numbers never
    leave the device). We match them against stored ``phone_hash`` values and, for
    each matched person, surface the **active** courses at the caller's school that
    they're in and the caller is not — the join targets. Same activity gate and
    notify-don't-enroll rule as the rest of discovery.

    Ranked: same-school contacts first, then by how many joinable courses they bring.
    """
    hashes = [h for h in dict.fromkeys(phone_hashes) if isinstance(h, str) and len(h) == 64]
    hashes = hashes[:MAX_CONTACT_HASHES]
    if not hashes:
        return []

    matched = (
        await db.execute(
            select(User)
            .where(User.phone_hash.in_(hashes))
            .where(User.id != user.id)
            .where(User.is_active)
        )
    ).scalars().all()
    if not matched:
        return []

    matched_ids = [m.id for m in matched]
    my_courses = select(CourseEnrollment.course_id).where(
        CourseEnrollment.user_id == user.id
    )

    # Every (matched contact → course) enrollment that the caller isn't already in.
    enroll_rows = (
        await db.execute(
            select(CourseEnrollment.user_id, CourseEnrollment.course_id)
            .where(CourseEnrollment.user_id.in_(matched_ids))
            .where(CourseEnrollment.course_id.not_in(my_courses))
        )
    ).all()

    candidate_ids = list({course_id for _, course_id in enroll_rows})
    joinable_by_course: dict = {}
    if candidate_ids:
        member_by_course = await active_member_counts(db, candidate_ids)
        resource_by_course = await _resource_counts(db, candidate_ids)
        # Keep it scoped to the caller's school (when they have one) and active +
        # past the activity gate — a contact's private, empty course stays hidden.
        course_query = select(Course).where(
            Course.id.in_(candidate_ids), Course.is_active
        )
        if user.school_id is not None:
            course_query = course_query.where(Course.school_id == user.school_id)
        for course in (await db.execute(course_query)).scalars().all():
            resource_count = resource_by_course.get(course.id, 0)
            member_count = member_by_course.get(course.id, 0)
            if resource_count < ACTIVITY_MIN_RESOURCES and member_count < ACTIVITY_MIN_MEMBERS:
                continue
            joinable_by_course[course.id] = {
                "course_id": str(course.id),
                "code": course.code,
                "name": course.name,
                "member_count": member_count,
                "signals": {"resource_count": resource_count},
            }

    courses_by_contact: dict = {}
    for uid, course_id in enroll_rows:
        course = joinable_by_course.get(course_id)
        if course:
            courses_by_contact.setdefault(uid, []).append(course)

    contacts = [
        {
            "id": str(m.id),
            "full_name": m.full_name,
            "avatar_url": m.avatar_url,
            "same_school": bool(
                user.school_id is not None and m.school_id == user.school_id
            ),
            "courses": courses_by_contact.get(m.id, []),
        }
        for m in matched
    ]
    contacts.sort(
        key=lambda ct: (ct["same_school"], len(ct["courses"]), ct["full_name"] or ""),
        reverse=True,
    )
    return contacts


async def get_cohort_courses(db: AsyncSession, user) -> list[dict]:
    """Active courses your *cohort* is in that you are not — enrollment-independent.

    Cohort = people at your school who also share your program and entry_year. Each
    of program/entry_year is a hard filter only when you actually have it (an unknown
    signal must not match every other unknown). School is always required — with no
    school there is nothing to scope against.

    Unlike ``get_classmate_courses`` (seeded from shared enrollment), this is seeded
    from profile signals, so it returns results for a brand-new user who has joined
    nothing yet — the onboarding surface. Same activity gate; pull-only, never enrolls.
    """
    if user.school_id is None:
        return []

    peer_conds = [User.school_id == user.school_id, User.id != user.id, User.is_active]
    if user.program:
        peer_conds.append(User.program == user.program)
    if user.entry_year is not None:
        peer_conds.append(User.entry_year == user.entry_year)
    peer_ids = select(User.id).where(*peer_conds)

    my_courses = select(CourseEnrollment.course_id).where(
        CourseEnrollment.user_id == user.id
    )

    # Candidate courses: what my cohort peers are enrolled in that I'm not, plus how
    # many of them are in each (the primary ranking signal).
    peer_count = func.count(func.distinct(CourseEnrollment.user_id))
    cand_rows = (
        await db.execute(
            select(CourseEnrollment.course_id, peer_count.label("peers"))
            .where(CourseEnrollment.user_id.in_(peer_ids))
            .where(CourseEnrollment.course_id.not_in(my_courses))
            .group_by(CourseEnrollment.course_id)
        )
    ).all()
    if not cand_rows:
        return []

    candidate_ids = [r.course_id for r in cand_rows]
    peer_by_course = {r.course_id: r.peers for r in cand_rows}

    member_by_course = await active_member_counts(db, candidate_ids)
    resource_by_course = await _resource_counts(db, candidate_ids)

    # Belt-and-suspenders: a cohort peer could (rarely) be in an off-school course;
    # keep the surface scoped to the caller's own school, active only.
    course_rows = (
        await db.execute(
            select(Course).where(
                Course.id.in_(candidate_ids),
                Course.is_active,
                Course.school_id == user.school_id,
            )
        )
    ).scalars().all()

    discovered: list[dict] = []
    for course in course_rows:
        resource_count = resource_by_course.get(course.id, 0)
        member_count = member_by_course.get(course.id, 0)
        # Activity gate — a solo, empty course never surfaces.
        if resource_count < ACTIVITY_MIN_RESOURCES and member_count < ACTIVITY_MIN_MEMBERS:
            continue
        discovered.append(
            {
                "course_id": str(course.id),
                "code": course.code,
                "name": course.name,
                "member_count": member_count,
                "signals": {
                    "cohort_peers_here": peer_by_course.get(course.id, 0),
                    "resource_count": resource_count,
                },
            }
        )

    discovered.sort(
        key=lambda d: (
            d["signals"]["cohort_peers_here"],
            d["signals"]["resource_count"],
            d["member_count"],
        ),
        reverse=True,
    )
    return discovered


async def _resource_counts(db: AsyncSession, course_ids: list) -> dict:
    rows = (
        await db.execute(
            select(Topic.course_id, func.count(Resource.id))
            .join(Resource, Resource.topic_id == Topic.id)
            .where(Topic.course_id.in_(course_ids))
            .group_by(Topic.course_id)
        )
    ).all()
    return {course_id: count for course_id, count in rows}


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
        .where(CourseEnrollment.user_id.in_(active_user_ids()))  # drop soft-deleted
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

    member_by_course = await active_member_counts(db, candidate_ids)
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
