"""
NotesOS API - Global Invites Router
Manage class invites for enrolling users in all your courses at once.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.classmate import Class, Classmate
from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.api.auth import get_current_user


router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class ClassCreate(BaseModel):
    name: Optional[str] = None  # Optional friendly name


class ClassResponse(BaseModel):
    id: str
    name: Optional[str]
    invite_code: str
    is_active: bool
    classmate_count: int
    created_at: str


class ClassmateResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_email: str
    joined_at: str


class JoinClassRequest(BaseModel):
    invite_code: str


class JoinClassResponse(BaseModel):
    class_name: Optional[str]
    owner_name: str
    courses_joined: List[str]
    course_count: int


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/global", response_model=ClassResponse, status_code=status.HTTP_201_CREATED
)
async def create_class_invite(
    request: ClassCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a global invite link.

    Anyone who joins via this link will be enrolled in ALL courses
    you're currently enrolled in.
    """
    # Create class
    new_class = Class(
        owner_id=current_user.id,
        name=request.name,
    )

    db.add(new_class)
    await db.commit()
    await db.refresh(new_class)

    return ClassResponse(
        id=str(new_class.id),
        name=new_class.name,
        invite_code=new_class.invite_code,
        is_active=new_class.is_active,
        classmate_count=0,
        created_at=new_class.created_at.isoformat(),
    )


@router.get("/global", response_model=List[ClassResponse])
async def list_my_class_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all global invite links I've created."""
    query = select(Class).where(Class.owner_id == current_user.id)
    result = await db.execute(query)
    classes = result.scalars().all()

    responses = []
    for cls in classes:
        # Count classmates
        count_query = select(Classmate).where(Classmate.class_id == cls.id)
        count_result = await db.execute(count_query)
        classmate_count = len(count_result.scalars().all())

        responses.append(
            ClassResponse(
                id=str(cls.id),
                name=cls.name,
                invite_code=cls.invite_code,
                is_active=cls.is_active,
                classmate_count=classmate_count,
                created_at=cls.created_at.isoformat(),
            )
        )

    return responses


@router.get("/global/{class_id}/classmates", response_model=List[ClassmateResponse])
async def list_classmates(
    class_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all users who joined via a specific invite."""
    # Verify ownership
    class_query = select(Class).where(Class.id == uuid.UUID(class_id))
    class_result = await db.execute(class_query)
    cls = class_result.scalar_one_or_none()

    if not cls:
        raise HTTPException(status_code=404, detail="Class invite not found")

    if cls.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your class invite")

    # Get classmates with user info
    query = select(Classmate).where(Classmate.class_id == uuid.UUID(class_id))
    result = await db.execute(query)
    classmates = result.scalars().all()

    responses = []
    for cm in classmates:
        user_query = select(User).where(User.id == cm.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if user:
            responses.append(
                ClassmateResponse(
                    id=str(cm.id),
                    user_id=str(cm.user_id),
                    user_name=user.full_name,
                    user_email=user.email,
                    joined_at=cm.joined_at.isoformat(),
                )
            )

    return responses


@router.post("/global/join", response_model=JoinClassResponse)
async def join_class(
    request: JoinClassRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Join all courses via a global invite code.

    This enrolls you in every course the invite owner is enrolled in.
    """
    # Find class by invite code
    query = select(Class).where(
        Class.invite_code == request.invite_code.upper(), Class.is_active.is_(True)
    )
    result = await db.execute(query)
    cls = result.scalar_one_or_none()

    if not cls:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")

    # Can't join your own class
    if cls.owner_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="You can't join your own class invite"
        )

    # Check if already a classmate
    existing_query = select(Classmate).where(
        Classmate.class_id == cls.id, Classmate.user_id == current_user.id
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail="You've already joined via this invite"
        )

    # Get owner's enrolled courses
    owner_courses_query = select(CourseEnrollment).where(
        CourseEnrollment.user_id == cls.owner_id
    )
    owner_courses_result = await db.execute(owner_courses_query)
    owner_enrollments = owner_courses_result.scalars().all()

    # Enroll in each course (skip if already enrolled)
    courses_joined = []
    for enrollment in owner_enrollments:
        # Check if already enrolled
        existing_enrollment_query = select(CourseEnrollment).where(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == enrollment.course_id,
        )
        existing_enrollment_result = await db.execute(existing_enrollment_query)

        if not existing_enrollment_result.scalar_one_or_none():
            # Enroll in course
            new_enrollment = CourseEnrollment(
                user_id=current_user.id,
                course_id=enrollment.course_id,
            )
            db.add(new_enrollment)

            # Get course name
            course_query = select(Course).where(Course.id == enrollment.course_id)
            course_result = await db.execute(course_query)
            course = course_result.scalar_one_or_none()
            if course:
                courses_joined.append(course.name)

    # Add as classmate
    classmate = Classmate(
        class_id=cls.id,
        user_id=current_user.id,
    )
    db.add(classmate)

    await db.commit()

    # Get owner name
    owner_query = select(User).where(User.id == cls.owner_id)
    owner_result = await db.execute(owner_query)
    owner = owner_result.scalar_one_or_none()

    return JoinClassResponse(
        class_name=cls.name,
        owner_name=owner.full_name if owner else "Unknown",
        courses_joined=courses_joined,
        course_count=len(courses_joined),
    )


@router.delete("/global/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class_invite(
    class_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a global invite.

    Note: This doesn't remove classmates from courses they've already joined.
    """
    query = select(Class).where(Class.id == uuid.UUID(class_id))
    result = await db.execute(query)
    cls = result.scalar_one_or_none()

    if not cls:
        raise HTTPException(status_code=404, detail="Class invite not found")

    if cls.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your class invite")

    await db.delete(cls)
    await db.commit()

    return None


@router.patch("/global/{class_id}/deactivate", response_model=ClassResponse)
async def deactivate_class_invite(
    class_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate an invite (prevents new joins but keeps history)."""
    query = select(Class).where(Class.id == uuid.UUID(class_id))
    result = await db.execute(query)
    cls = result.scalar_one_or_none()

    if not cls:
        raise HTTPException(status_code=404, detail="Class invite not found")

    if cls.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your class invite")

    cls.is_active = False
    await db.commit()
    await db.refresh(cls)

    # Count classmates
    count_query = select(Classmate).where(Classmate.class_id == cls.id)
    count_result = await db.execute(count_query)
    classmate_count = len(count_result.scalars().all())

    return ClassResponse(
        id=str(cls.id),
        name=cls.name,
        invite_code=cls.invite_code,
        is_active=cls.is_active,
        classmate_count=classmate_count,
        created_at=cls.created_at.isoformat(),
    )
