"""
NotesOS API - Discovery

The emergent graph, exposed. Both endpoints are pure reads over course-enrollment
overlap — your classmates, and the courses they're in that you aren't. Discovery
never enrolls; it surfaces, and the join affordance is the existing
``POST /api/courses/join``.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models import User
from app.services.discovery import (
    get_classmate_courses,
    get_classmates,
    get_cohort_courses,
    match_contacts,
)

router = APIRouter()


class ContactMatchRequest(BaseModel):
    # SHA-256 hex hashes of the caller's canonical contact phone numbers. Raw
    # numbers never leave the device — see docs/mobile-integration-plan.md §6.3-A.
    phone_hashes: list[str]


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


@router.get("/cohort")
async def discover_cohort(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Active courses your cohort (same school + program + entry_year) is in that you
    are not — the enrollment-independent surface a brand-new user sees at onboarding."""
    return {"courses": await get_cohort_courses(db, current_user)}


@router.post("/contacts")
async def match_contacts_endpoint(
    request: ContactMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Which of your phone contacts are on NotesOS, with the courses they're in that
    you can join. Contacts are uploaded as hashes only — raw numbers never leave the
    device. The final onboarding beat (see §6)."""
    return {"contacts": await match_contacts(db, current_user, request.phone_hashes)}
