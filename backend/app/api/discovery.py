"""
NotesOS API - Discovery

The emergent graph, exposed. Both endpoints are pure reads over course-enrollment
overlap — your classmates, and the courses they're in that you aren't. Discovery
never enrolls; it surfaces, and the join affordance is the existing
``POST /api/courses/join``.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.services.discovery import get_classmate_courses, get_classmates

router = APIRouter()


@router.get("/classmates")
async def list_classmates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """People you share at least one course with, closest (most-shared) first."""
    return {"classmates": await get_classmates(db, current_user.id)}


@router.get("/courses")
async def discover_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Courses your classmates are taking that you are not — activity-gated."""
    return {"courses": await get_classmate_courses(db, current_user.id)}
