"""
NotesOS API - Course Endpoints
"""

import secrets
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Course, CourseEnrollment, Topic, User
from app.models.progress import UserProgress
from app.models.term import Term
from app.api.auth import get_current_user, verify_course_enrollment
from app.services.cache import (
    cache,
    courses_list_key,
    course_key,
    topics_list_key,
)
from app.services.proximity import find_course_candidates
from app.config import settings

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class CreateCourseRequest(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    # Optional: file the new course under one of the user's own terms.
    term_id: Optional[str] = None
    # Set true to skip the proximity check and fork a new course even when
    # near-matches exist ("make my own"). The client sends this on the second
    # call, after the user has seen the offered matches and declined them.
    force: bool = False


class JoinCourseRequest(BaseModel):
    course_id: Optional[str] = None
    invite_code: Optional[str] = None
    term_id: Optional[str] = None


class TopicCreate(BaseModel):
    title: str
    week_number: Optional[int] = None
    order_index: int = 0


class BatchCourseCreate(BaseModel):
    """Create multiple courses at once."""

    courses: List[CreateCourseRequest]  # Max 10


class BatchTopicCreate(BaseModel):
    """Create multiple topics at once."""

    topics: List[TopicCreate]  # Max 20


# =============================================================================
# Helpers
# =============================================================================


def generate_invite_code() -> str:
    """Generate a unique invite code like HIST-2F4K-9X1L"""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No confusing chars
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"{part1}-{part2}"


async def resolve_owned_term_id(term_id: Optional[str], user: User, db: AsyncSession):
    """Validate that term_id (if given) belongs to the user. Returns it or None."""
    if not term_id:
        return None
    owned = await db.scalar(
        select(Term.id).where(Term.id == term_id, Term.user_id == user.id)
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Term not found")
    return term_id


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_courses(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """List all courses the user is enrolled in, with completion and last-studied data."""
    user_id = str(current_user.id)
    cache_key = courses_list_key(user_id)

    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    result = await db.execute(
        select(
            Course,
            CourseEnrollment.joined_at,
            CourseEnrollment.term_id,
            Term.label,
        )
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .outerjoin(Term, Term.id == CourseEnrollment.term_id)
        .where(CourseEnrollment.user_id == current_user.id)
        .where(Course.is_active)
    )
    rows = result.all()

    course_ids = [course.id for course, _, _, _ in rows]
    if not course_ids:
        payload = {"courses": []}
        await cache.set(cache_key, payload, settings.CACHE_TTL_COURSES)
        return payload

    # Batch member counts
    counts_result = await db.execute(
        select(CourseEnrollment.course_id, func.count().label("cnt"))
        .where(CourseEnrollment.course_id.in_(course_ids))
        .group_by(CourseEnrollment.course_id)
    )
    member_counts = {str(row.course_id): row.cnt for row in counts_result}

    # Batch completion percentages — average mastery_level per course for this user
    progress_result = await db.execute(
        select(
            UserProgress.course_id,
            func.avg(UserProgress.mastery_level).label("avg_mastery"),
        )
        .where(
            UserProgress.user_id == current_user.id,
            UserProgress.course_id.in_(course_ids),
        )
        .group_by(UserProgress.course_id)
    )
    completion_map = {
        str(row.course_id): round(float(row.avg_mastery or 0) * 100, 1)
        for row in progress_result
    }

    # Batch last-studied per course — most recent UserProgress.last_activity
    last_studied_result = await db.execute(
        select(
            UserProgress.course_id,
            UserProgress.topic_id,
            Topic.title,
            UserProgress.last_activity,
        )
        .join(Topic, Topic.id == UserProgress.topic_id)
        .where(
            UserProgress.user_id == current_user.id,
            UserProgress.course_id.in_(course_ids),
        )
        .order_by(UserProgress.last_activity.desc())
    )
    last_studied_map: dict = {}
    for row in last_studied_result:
        cid = str(row.course_id)
        if cid not in last_studied_map:
            last_studied_map[cid] = {
                "topic_id": str(row.topic_id),
                "topic_name": row.title,
                "studied_at": row.last_activity.isoformat(),
            }

    # Batch topics for all courses — avoids N+1 and lets the frontend render
    # the sidebar and home page without a separate selectCourse call per course.
    topics_result = await db.execute(
        select(Topic)
        .where(Topic.course_id.in_(course_ids))
        .order_by(Topic.order_index)
    )
    topics_by_course: dict = {}
    for topic in topics_result.scalars().all():
        cid = str(topic.course_id)
        if cid not in topics_by_course:
            topics_by_course[cid] = []
        topics_by_course[cid].append({
            "id": str(topic.id),
            "title": topic.title,
            "order_index": topic.order_index,
            "week_number": topic.week_number,
        })

    courses = [
        {
            "id": str(course.id),
            "code": course.code,
            "name": course.name,
            "term_id": str(term_id) if term_id else None,
            "term_label": term_label,
            "member_count": member_counts.get(str(course.id), 1),
            "created_by": str(course.created_by),
            "joined_at": joined_at.isoformat(),
            "completion_percentage": completion_map.get(str(course.id), 0.0),
            "last_studied": last_studied_map.get(str(course.id)),
            "topics": topics_by_course.get(str(course.id), []),
        }
        for course, joined_at, term_id, term_label in rows
    ]

    payload = {"courses": courses}
    await cache.set(cache_key, payload, settings.CACHE_TTL_COURSES)
    return payload


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_course(
    request: CreateCourseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new course.

    Runs the proximity check first: if near-matches exist at the creator's school,
    return them as an offer (HTTP 200, nothing created) instead of forking a copy.
    The client re-POSTs with ``force=true`` to create anyway.
    """
    term_id = await resolve_owned_term_id(request.term_id, current_user, db)

    if not request.force:
        candidates = await find_course_candidates(
            db, creator=current_user, code=request.code, name=request.name
        )
        if candidates:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "proximity_check": True,
                    "message": "This might already exist. Join one of these, or make your own.",
                    "matches": [c.as_dict() for c in candidates],
                },
            )

    course = Course(
        code=request.code,
        name=request.name,
        description=request.description,
        invite_code=generate_invite_code(),
        created_by=current_user.id,
        # A course inherits the creator's school — the proximity-check hard filter.
        school_id=current_user.school_id,
    )
    db.add(course)
    await db.flush()

    # Auto-enroll creator, filing the course under their chosen term (if any).
    enrollment = CourseEnrollment(
        user_id=current_user.id,
        course_id=course.id,
        term_id=term_id,
    )
    db.add(enrollment)

    await db.commit()
    await db.refresh(course)

    # Invalidate user's course list cache
    await cache.delete(courses_list_key(str(current_user.id)))

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
        result = await db.execute(
            select(Course).where(Course.invite_code == request.invite_code)
        )
        course = result.scalar_one_or_none()

    elif request.course_id:
        result = await db.execute(
            select(Course).where(Course.id == request.course_id)
        )
        course = result.scalar_one_or_none()

    # No public search branch: a course is reached by invite code, a direct
    # course_id from the classmate-graph discovery feed, or creation. Public
    # browse is exactly what the emergent-set model rules out.

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

    term_id = await resolve_owned_term_id(request.term_id, current_user, db)
    enrollment = CourseEnrollment(
        user_id=current_user.id,
        course_id=course.id,
        term_id=term_id,
    )
    db.add(enrollment)
    await db.commit()

    member_count = await db.scalar(
        select(func.count())
        .select_from(CourseEnrollment)
        .where(CourseEnrollment.course_id == course.id)
    )

    # Invalidate caches
    await cache.delete(courses_list_key(str(current_user.id)))
    await cache.delete(course_key(str(course.id)))

    # Notify the course owner that someone joined
    if course.created_by and course.created_by != current_user.id:
        try:
            from app.services.notifications import create_and_push_notification
            from app.models.notification import NotificationType
            await create_and_push_notification(
                db=db,
                user_id=course.created_by,
                notif_type=NotificationType.CLASSMATE_JOINED,
                title=f"{current_user.full_name} joined {course.name}",
                body=f"Your course now has {member_count} member{'s' if member_count != 1 else ''}.",
                meta_data={"course_id": str(course.id)},
            )
        except Exception:
            pass  # Non-fatal

    return {
        "message": f"Welcome to {course.name}! 👋",
        "course": {"id": str(course.id), "code": course.code, "name": course.name},
        "classmates": member_count - 1,
    }


class SetCourseTermRequest(BaseModel):
    term_id: Optional[str] = None  # null unfiles the course


@router.patch("/{course_id}/term")
async def set_course_term(
    course_id: str,
    request: SetCourseTermRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """File (or refile / unfile) the current user's enrollment under one of their terms."""
    enrollment = await db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.user_id == current_user.id,
            CourseEnrollment.course_id == course_id,
        )
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")

    enrollment.term_id = await resolve_owned_term_id(request.term_id, current_user, db)
    await db.commit()
    await cache.delete(courses_list_key(str(current_user.id)))
    return {"course_id": course_id, "term_id": str(enrollment.term_id) if enrollment.term_id else None}


@router.get("/{course_id}")
async def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get course details with topics."""
    cache_key = course_key(course_id)
    cached = await cache.get(cache_key)
    if cached is not None:
        # Still verify enrollment — enrollment check is not cached
        enrollment = await db.execute(
            select(CourseEnrollment)
            .where(CourseEnrollment.user_id == current_user.id)
            .where(CourseEnrollment.course_id == course_id)
        )
        if not enrollment.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not enrolled in this course")
        return cached

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

    payload = {
        "course": {
            "id": str(course.id),
            "code": course.code,
            "name": course.name,
            "description": course.description,
            "school_id": str(course.school_id) if course.school_id else None,
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

    await cache.set(cache_key, payload, settings.CACHE_TTL_COURSES)
    return payload


# NOTE: single-topic creation lives on the topics router
# (POST /api/courses/{course_id}/topics in api/topics.py). A duplicate route here
# used to shadow it — registration order made this router win — while dropping
# `description` and skipping classmates' cache invalidation. Removed 2026-07-12;
# only the batch endpoint below is courses-router territory.


@router.get("/{course_id}/summary")
async def get_course_summary(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get completion percentage and last studied topic for a course."""
    import uuid as _uuid
    await verify_course_enrollment(db, current_user.id, _uuid.UUID(course_id))

    # Completion percentage
    progress_result = await db.execute(
        select(func.avg(UserProgress.mastery_level).label("avg_mastery"))
        .where(
            UserProgress.user_id == current_user.id,
            UserProgress.course_id == course_id,
        )
    )
    avg_mastery = progress_result.scalar_one_or_none() or 0
    completion_percentage = round(float(avg_mastery) * 100, 1)

    # Last studied topic
    last_studied_result = await db.execute(
        select(UserProgress, Topic)
        .join(Topic, Topic.id == UserProgress.topic_id)
        .where(
            UserProgress.user_id == current_user.id,
            UserProgress.course_id == course_id,
        )
        .order_by(UserProgress.last_activity.desc())
        .limit(1)
    )
    row = last_studied_result.first()
    last_studied_topic = None
    if row:
        progress, topic = row
        last_studied_topic = {
            "id": str(topic.id),
            "name": topic.title,
            "studied_at": progress.last_activity.isoformat(),
        }

    return {
        "completion_percentage": completion_percentage,
        "last_studied_topic": last_studied_topic,
    }


# =============================================================================
# Batch Creation Endpoints
# =============================================================================


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def batch_create_courses(
    request: BatchCourseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create multiple courses at once.
    Max 10 courses per request. All succeed or all fail.
    """
    if len(request.courses) > 10:
        raise HTTPException(
            status_code=400, detail="Maximum 10 courses per batch request"
        )

    created_courses = []

    for course_req in request.courses:
        course = Course(
            code=course_req.code,
            name=course_req.name,
            description=course_req.description,
            invite_code=generate_invite_code(),
            created_by=current_user.id,
            school_id=current_user.school_id,
        )
        db.add(course)
        await db.flush()

        enrollment = CourseEnrollment(
            user_id=current_user.id,
            course_id=course.id,
            term_id=await resolve_owned_term_id(course_req.term_id, current_user, db),
        )
        db.add(enrollment)

        created_courses.append(
            {
                "id": str(course.id),
                "code": course.code,
                "name": course.name,
                "invite_code": course.invite_code,
            }
        )

    await db.commit()

    # Invalidate user's course list cache
    await cache.delete(courses_list_key(str(current_user.id)))

    return {
        "message": f"Created {len(created_courses)} courses",
        "courses": created_courses,
    }


@router.post("/{course_id}/topics/batch", status_code=status.HTTP_201_CREATED)
async def batch_create_topics(
    course_id: str,
    request: BatchTopicCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create multiple topics at once.
    Max 20 topics per request. All succeed or all fail.
    """
    if len(request.topics) > 20:
        raise HTTPException(
            status_code=400, detail="Maximum 20 topics per batch request"
        )

    enrollment = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.user_id == current_user.id)
        .where(CourseEnrollment.course_id == course_id)
    )
    if not enrollment.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    created_topics = []

    for topic_req in request.topics:
        topic = Topic(
            course_id=course_id,
            title=topic_req.title,
            week_number=topic_req.week_number,
            order_index=topic_req.order_index,
        )
        db.add(topic)
        await db.flush()

        created_topics.append(
            {
                "id": str(topic.id),
                "title": topic.title,
                "week_number": topic.week_number,
            }
        )

    await db.commit()

    # Invalidate course detail + topic list caches
    await cache.delete(course_key(course_id))
    await cache.delete(topics_list_key(course_id))

    return {
        "message": f"Created {len(created_topics)} topics",
        "topics": created_topics,
    }
