"""
NotesOS API - Course Endpoints
"""

import secrets
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Course, CourseEnrollment, Topic, User
from app.api.auth import get_current_user

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class CreateCourseRequest(BaseModel):
    code: str
    name: str
    semester: Optional[str] = None
    description: Optional[str] = None
    is_public: bool = True


class JoinCourseRequest(BaseModel):
    search: Optional[str] = None
    course_id: Optional[str] = None
    invite_code: Optional[str] = None


class TopicCreate(BaseModel):
    title: str
    description: Optional[str] = None
    week_number: Optional[int] = None
    order_index: int = 0


# =============================================================================
# Helpers
# =============================================================================


def generate_invite_code() -> str:
    """Generate a unique invite code like HIST-2F4K-9X1L"""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No confusing chars
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"{part1}-{part2}"


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_courses(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """List all courses the user is enrolled in."""
    result = await db.execute(
        select(Course, CourseEnrollment.joined_at)
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .where(CourseEnrollment.user_id == current_user.id)
        .where(Course.is_active == True)
    )

    courses = []
    for course, joined_at in result.all():
        # Get member count
        member_count = await db.scalar(
            select(func.count())
            .select_from(CourseEnrollment)
            .where(CourseEnrollment.course_id == course.id)
        )
        courses.append(
            {
                "id": str(course.id),
                "code": course.code,
                "name": course.name,
                "semester": course.semester,
                "member_count": member_count,
                "created_by": str(course.created_by),
                "joined_at": joined_at.isoformat(),
            }
        )

    return {"courses": courses}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_course(
    request: CreateCourseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new course."""
    # Generate invite code if private
    invite_code = None if request.is_public else generate_invite_code()

    course = Course(
        code=request.code,
        name=request.name,
        semester=request.semester,
        description=request.description,
        is_public=request.is_public,
        invite_code=invite_code,
        created_by=current_user.id,
    )
    db.add(course)
    await db.flush()

    # Auto-enroll creator
    enrollment = CourseEnrollment(user_id=current_user.id, course_id=course.id)
    db.add(enrollment)
    await db.commit()
    await db.refresh(course)

    return {
        "course": {
            "id": str(course.id),
            "code": course.code,
            "name": course.name,
            "invite_code": course.invite_code,
            "share_link": f"https://notesos.com/join/{course.invite_code}"
            if course.invite_code
            else None,
        }
    }


@router.post("/join")
async def join_course(
    request: JoinCourseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join an existing course."""
    course = None

    if request.invite_code:
        # Join by invite code
        result = await db.execute(
            select(Course).where(Course.invite_code == request.invite_code)
        )
        course = result.scalar_one_or_none()

    elif request.course_id:
        # Join by ID (for public courses)
        result = await db.execute(
            select(Course)
            .where(Course.id == request.course_id)
            .where(Course.is_public == True)
        )
        course = result.scalar_one_or_none()

    elif request.search:
        # Search by code or name
        result = await db.execute(
            select(Course)
            .where(Course.is_public == True)
            .where(
                Course.code.ilike(f"%{request.search}%")
                | Course.name.ilike(f"%{request.search}%")
            )
            .limit(10)
        )
        courses = result.scalars().all()
        return {
            "courses": [
                {"id": str(c.id), "code": c.code, "name": c.name} for c in courses
            ]
        }

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check if already enrolled
    existing = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.user_id == current_user.id)
        .where(CourseEnrollment.course_id == course.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already enrolled in this course")

    # Enroll
    enrollment = CourseEnrollment(user_id=current_user.id, course_id=course.id)
    db.add(enrollment)
    await db.commit()

    # Get classmate count
    member_count = await db.scalar(
        select(func.count())
        .select_from(CourseEnrollment)
        .where(CourseEnrollment.course_id == course.id)
    )

    return {
        "message": f"Welcome to {course.name}! 👋",
        "course": {"id": str(course.id), "code": course.code, "name": course.name},
        "classmates": member_count - 1,
    }


@router.get("/{course_id}")
async def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get course details with topics."""
    # Verify enrollment
    enrollment = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.user_id == current_user.id)
        .where(CourseEnrollment.course_id == course_id)
    )
    if not enrollment.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    # Get course with topics
    result = await db.execute(
        select(Course)
        .options(selectinload(Course.topics))
        .where(Course.id == course_id)
    )
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return {
        "course": {
            "id": str(course.id),
            "code": course.code,
            "name": course.name,
            "description": course.description,
            "semester": course.semester,
        },
        "topics": [
            {
                "id": str(t.id),
                "title": t.title,
                "description": t.description,
                "week_number": t.week_number,
                "order_index": t.order_index,
            }
            for t in sorted(course.topics, key=lambda x: x.order_index)
        ],
    }


@router.post("/{course_id}/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    course_id: str,
    request: TopicCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new topic in a course."""
    # Verify enrollment
    enrollment = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.user_id == current_user.id)
        .where(CourseEnrollment.course_id == course_id)
    )
    if not enrollment.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    topic = Topic(
        course_id=course_id,
        title=request.title,
        description=request.description,
        week_number=request.week_number,
        order_index=request.order_index,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)

    return {
        "topic": {
            "id": str(topic.id),
            "title": topic.title,
            "description": topic.description,
            "week_number": topic.week_number,
        }
    }
