"""
NotesOS API - Semesters Endpoints
"""

import secrets
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.database import get_db
from app.models import User, Course, CourseEnrollment
from app.models.semester import Semester, SemesterMember, SemesterRole
from app.api.auth import get_current_user

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class CreateSemesterRequest(BaseModel):
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class UpdateSemesterRequest(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class JoinSemesterRequest(BaseModel):
    invite_code: str


# =============================================================================
# Helpers
# =============================================================================


def _generate_semester_invite_code() -> str:
    """Generate an 8-char alphanumeric invite code (no ambiguous chars)."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(8))


async def _get_semester_as_member(
    semester_id: str,
    current_user: User,
    db: AsyncSession,
) -> tuple[Semester, SemesterMember]:
    """Load semester and verify current user is a member. Raises 404/403."""
    result = await db.execute(
        select(Semester).where(Semester.id == semester_id)
    )
    semester = result.scalar_one_or_none()
    if not semester:
        raise HTTPException(status_code=404, detail="Semester not found.")

    member_result = await db.execute(
        select(SemesterMember).where(
            SemesterMember.semester_id == semester.id,
            SemesterMember.user_id == current_user.id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this semester.")

    return semester, member


async def _require_owner(semester_id: str, current_user: User, db: AsyncSession) -> Semester:
    """Load semester and verify current user is the OWNER."""
    semester, member = await _get_semester_as_member(semester_id, current_user, db)
    if member.role != SemesterRole.OWNER:
        raise HTTPException(status_code=403, detail="Only the semester owner can do this.")
    return semester


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_semester(
    request: CreateSemesterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new semester and auto-assign creator as OWNER."""
    invite_code = _generate_semester_invite_code()
    # Retry on collision (extremely rare with 8-char code space)
    for _ in range(5):
        existing = await db.execute(
            select(Semester).where(Semester.invite_code == invite_code)
        )
        if not existing.scalar_one_or_none():
            break
        invite_code = _generate_semester_invite_code()

    semester = Semester(
        owner_id=current_user.id,
        name=request.name,
        start_date=request.start_date,
        end_date=request.end_date,
        invite_code=invite_code,
    )
    db.add(semester)
    await db.flush()

    owner_membership = SemesterMember(
        semester_id=semester.id,
        user_id=current_user.id,
        role=SemesterRole.OWNER,
    )
    db.add(owner_membership)
    await db.commit()
    await db.refresh(semester)

    return {
        "semester": {
            "id": str(semester.id),
            "name": semester.name,
            "start_date": semester.start_date.isoformat() if semester.start_date else None,
            "end_date": semester.end_date.isoformat() if semester.end_date else None,
            "invite_code": semester.invite_code,
            "created_at": semester.created_at.isoformat(),
        }
    }


@router.get("")
async def list_semesters(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all semesters the current user is a member of (owned + joined)."""
    membership_result = await db.execute(
        select(SemesterMember).where(SemesterMember.user_id == current_user.id)
    )
    memberships = membership_result.scalars().all()
    if not memberships:
        return {"semesters": []}

    semester_ids = [m.semester_id for m in memberships]
    membership_map = {m.semester_id: m for m in memberships}

    semesters_result = await db.execute(
        select(Semester).where(Semester.id.in_(semester_ids))
    )
    semesters = semesters_result.scalars().all()

    # Batch member counts
    member_counts_result = await db.execute(
        select(SemesterMember.semester_id, func.count().label("cnt"))
        .where(SemesterMember.semester_id.in_(semester_ids))
        .group_by(SemesterMember.semester_id)
    )
    member_counts = {row.semester_id: row.cnt for row in member_counts_result}

    # Batch course counts
    course_counts_result = await db.execute(
        select(Course.semester_id, func.count().label("cnt"))
        .where(Course.semester_id.in_(semester_ids))
        .group_by(Course.semester_id)
    )
    course_counts = {row.semester_id: row.cnt for row in course_counts_result}

    return {
        "semesters": [
            {
                "id": str(s.id),
                "name": s.name,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "role": membership_map[s.id].role.value,
                "member_count": member_counts.get(s.id, 0),
                "course_count": course_counts.get(s.id, 0),
                "created_at": s.created_at.isoformat(),
            }
            for s in semesters
        ]
    }


@router.get("/{semester_id}")
async def get_semester(
    semester_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get semester details. invite_code only visible to OWNER."""
    semester, member = await _get_semester_as_member(semester_id, current_user, db)

    # Members list
    members_result = await db.execute(
        select(SemesterMember, User)
        .join(User, User.id == SemesterMember.user_id)
        .where(SemesterMember.semester_id == semester.id)
    )
    members_rows = members_result.all()

    # Courses in this semester
    courses_result = await db.execute(
        select(Course).where(Course.semester_id == semester.id, Course.is_active)
    )
    courses = courses_result.scalars().all()

    is_owner = member.role == SemesterRole.OWNER

    return {
        "id": str(semester.id),
        "name": semester.name,
        "start_date": semester.start_date.isoformat() if semester.start_date else None,
        "end_date": semester.end_date.isoformat() if semester.end_date else None,
        "invite_code": semester.invite_code if is_owner else None,
        "role": member.role.value,
        "members": [
            {
                "user_id": str(m.user_id),
                "full_name": u.full_name,
                "role": m.role.value,
                "joined_at": m.joined_at.isoformat(),
            }
            for m, u in members_rows
        ],
        "courses": [
            {"id": str(c.id), "code": c.code, "name": c.name}
            for c in courses
        ],
    }


@router.patch("/{semester_id}")
async def update_semester(
    semester_id: str,
    request: UpdateSemesterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update semester metadata (owner only)."""
    semester = await _require_owner(semester_id, current_user, db)

    if request.name is not None:
        semester.name = request.name
    if request.start_date is not None:
        semester.start_date = request.start_date
    if request.end_date is not None:
        semester.end_date = request.end_date

    await db.commit()
    await db.refresh(semester)

    return {
        "id": str(semester.id),
        "name": semester.name,
        "start_date": semester.start_date.isoformat() if semester.start_date else None,
        "end_date": semester.end_date.isoformat() if semester.end_date else None,
    }


@router.delete("/{semester_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_semester(
    semester_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete semester (owner only).
    Courses become standalone (semester_id → NULL). Courses are NOT deleted.
    """
    semester = await _require_owner(semester_id, current_user, db)

    # Detach courses (SET NULL handled by FK, but do it explicitly for clarity)
    await db.execute(
        update(Course)
        .where(Course.semester_id == semester.id)
        .values(semester_id=None)
    )

    await db.delete(semester)
    await db.commit()


@router.post("/join")
async def join_semester(
    request: JoinSemesterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Join a semester via invite code.
    Auto-enrolls the user in all courses currently in the semester.
    """
    result = await db.execute(
        select(Semester).where(Semester.invite_code == request.invite_code)
    )
    semester = result.scalar_one_or_none()
    if not semester:
        raise HTTPException(status_code=404, detail="Invalid invite code.")

    # Check already a member
    existing_member = await db.execute(
        select(SemesterMember).where(
            SemesterMember.semester_id == semester.id,
            SemesterMember.user_id == current_user.id,
        )
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already a member of this semester.")

    membership = SemesterMember(
        semester_id=semester.id,
        user_id=current_user.id,
        role=SemesterRole.MEMBER,
    )
    db.add(membership)

    # Auto-enroll in all courses in this semester
    courses_result = await db.execute(
        select(Course).where(Course.semester_id == semester.id, Course.is_active)
    )
    courses = courses_result.scalars().all()

    joined_courses = []
    for course in courses:
        existing_enrollment = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.user_id == current_user.id,
                CourseEnrollment.course_id == course.id,
            )
        )
        if not existing_enrollment.scalar_one_or_none():
            enrollment = CourseEnrollment(
                user_id=current_user.id,
                course_id=course.id,
            )
            db.add(enrollment)
            joined_courses.append({"id": str(course.id), "code": course.code, "name": course.name})

    await db.commit()

    # Notify semester owner via notification service
    try:
        from app.services.notifications import create_and_push_notification
        from app.models.notification import NotificationType
        owner_result = await db.execute(
            select(User).where(User.id == semester.owner_id)
        )
        owner = owner_result.scalar_one_or_none()
        if owner:
            await create_and_push_notification(
                db=db,
                user_id=semester.owner_id,
                notif_type=NotificationType.INVITE_ACCEPTED,
                title="New member joined your semester",
                body=f"{current_user.full_name} joined {semester.name}.",
                metadata={"semester_id": str(semester.id), "user_id": str(current_user.id)},
            )
    except Exception:
        pass

    return {
        "semester": {
            "id": str(semester.id),
            "name": semester.name,
        },
        "courses_joined": joined_courses,
    }


@router.get("/{semester_id}/members")
async def list_semester_members(
    semester_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all members of a semester."""
    await _get_semester_as_member(semester_id, current_user, db)

    members_result = await db.execute(
        select(SemesterMember, User)
        .join(User, User.id == SemesterMember.user_id)
        .where(SemesterMember.semester_id == semester_id)
    )
    rows = members_result.all()

    return {
        "members": [
            {
                "user_id": str(m.user_id),
                "full_name": u.full_name,
                "role": m.role.value,
                "joined_at": m.joined_at.isoformat(),
            }
            for m, u in rows
        ]
    }


@router.post("/{semester_id}/courses/{course_id}", status_code=status.HTTP_200_OK)
async def add_course_to_semester(
    semester_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign an existing standalone course to a semester (owner only)."""
    semester = await _require_owner(semester_id, current_user, db)

    # Verify user is enrolled in the course
    enrollment_result = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id,
        )
    )
    if not enrollment_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enrolled in this course.")

    course_result = await db.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    course.semester_id = semester.id
    await db.commit()

    return {"message": f"Course assigned to semester '{semester.name}'."}


@router.delete("/{semester_id}/courses/{course_id}", status_code=status.HTTP_200_OK)
async def remove_course_from_semester(
    semester_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a course from a semester (owner only). Course becomes standalone."""
    semester = await _require_owner(semester_id, current_user, db)

    course_result = await db.execute(
        select(Course).where(
            Course.id == course_id,
            Course.semester_id == semester.id,
        )
    )
    course = course_result.scalar_one_or_none()
    if not course:
        raise HTTPException(
            status_code=404, detail="Course not found in this semester."
        )

    course.semester_id = None
    await db.commit()

    return {"message": "Course removed from semester (now standalone)."}
