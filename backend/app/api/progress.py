"""
NotesOS API - Progress Router
Track sessions, get progress, streaks, and recommendations.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.api.auth import get_current_user, verify_course_enrollment
from app.models.user import User
from app.models.progress import UserProgress
from app.services.progress import progress_service


router = APIRouter(prefix="/api/progress", tags=["Progress"])


# ── Pydantic Models ────────────────────────────────────────────────────────


class StartSessionRequest(BaseModel):
    topic_id: str
    session_type: str = "reading"  # reading, quiz, practice


class StartSessionResponse(BaseModel):
    session_id: str
    started_at: str


class EndSessionRequest(BaseModel):
    session_id: str


class EndSessionResponse(BaseModel):
    session_id: str
    duration_seconds: int


class TopicProgressResponse(BaseModel):
    topic_id: str
    mastery_level: float
    total_study_time: int  # Seconds
    avg_score: float | None
    streak_days: int
    last_activity: str


class CourseProgressResponse(BaseModel):
    course_id: str
    overall_mastery: float
    total_study_time: int
    current_streak: int
    topics_count: int
    topics_mastered: int  # mastery >= 0.7


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int  # Not implemented yet, just current for now
    last_activity: str


class RecommendationResponse(BaseModel):
    topic_id: str
    reason: str
    priority: str  # high, medium, low
    type: str  # weak_topic, inactive_topic, next_topic


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/sessions/start", response_model=StartSessionResponse)
async def start_study_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a study session for a topic."""
    # Verify topic exists and user has access (via course enrollment)
    from app.models.course import Topic

    topic_query = select(Topic).where(Topic.id == uuid.UUID(request.topic_id))
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Start session
    session = await progress_service.start_session(
        db, str(current_user.id), request.topic_id, request.session_type
    )

    return StartSessionResponse(
        session_id=str(session.id),
        started_at=session.started_at.isoformat(),
    )


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_study_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """End a study session and update progress."""
    # End session
    session = await progress_service.end_session(db, session_id)

    # Verify ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your session",
        )

    return EndSessionResponse(
        session_id=str(session.id),
        duration_seconds=session.duration_seconds,
    )


@router.get("/{course_id}", response_model=CourseProgressResponse)
async def get_course_progress(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get overall progress for a course."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    # Get all progress records for this course
    query = select(UserProgress).where(
        UserProgress.user_id == current_user.id,
        UserProgress.course_id == uuid.UUID(course_id),
    )
    result = await db.execute(query)
    progress_records = result.scalars().all()

    if not progress_records:
        # No progress yet
        return CourseProgressResponse(
            course_id=course_id,
            overall_mastery=0.0,
            total_study_time=0,
            current_streak=0,
            topics_count=0,
            topics_mastered=0,
        )

    # Calculate aggregates
    overall_mastery = sum(p.mastery_level for p in progress_records) / len(
        progress_records
    )
    total_study_time = sum(p.total_study_time for p in progress_records)
    current_streak = max(p.streak_days for p in progress_records)
    topics_mastered = sum(1 for p in progress_records if p.mastery_level >= 0.7)

    return CourseProgressResponse(
        course_id=course_id,
        overall_mastery=round(float(overall_mastery), 2),
        total_study_time=total_study_time,
        current_streak=current_streak,
        topics_count=len(progress_records),
        topics_mastered=topics_mastered,
    )


@router.get("/{course_id}/topics", response_model=List[TopicProgressResponse])
async def get_topics_progress(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get per-topic progress breakdown for a course."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    # Get all progress records
    query = select(UserProgress).where(
        UserProgress.user_id == current_user.id,
        UserProgress.course_id == uuid.UUID(course_id),
    )
    result = await db.execute(query)
    progress_records = result.scalars().all()

    return [
        TopicProgressResponse(
            topic_id=str(p.topic_id),
            mastery_level=float(p.mastery_level),
            total_study_time=p.total_study_time,
            avg_score=float(p.avg_score) if p.avg_score else None,
            streak_days=p.streak_days,
            last_activity=p.last_activity.isoformat(),
        )
        for p in progress_records
    ]


@router.get("/{course_id}/streak", response_model=StreakResponse)
async def get_streak(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get study streak information for a course."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    # Update streak (checks if needs reset)
    current_streak = await progress_service.update_streak(
        db, str(current_user.id), course_id
    )

    # Get last activity
    query = select(UserProgress).where(
        UserProgress.user_id == current_user.id,
        UserProgress.course_id == uuid.UUID(course_id),
    )
    result = await db.execute(query)
    progress_records = result.scalars().all()

    if not progress_records:
        last_activity = None
    else:
        last_activity = max(p.last_activity for p in progress_records).isoformat()

    return StreakResponse(
        current_streak=current_streak,
        longest_streak=current_streak,  # TODO: track longest separately
        last_activity=last_activity or "",
    )


@router.get("/{course_id}/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get personalized study recommendations for a course."""
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    recommendations = await progress_service.get_recommendations(
        db, str(current_user.id), course_id
    )

    return [RecommendationResponse(**rec) for rec in recommendations]
