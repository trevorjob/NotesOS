"""
NotesOS API - Topics Router
Manage topics within courses (organize notes by weeks/units).
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.course import Topic, CourseEnrollment
from app.api.auth import get_current_user
from app.models.user import User
from app.services.cache import cache, topics_list_key, topic_key, course_key
from app.config import settings

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class TopicCreate(BaseModel):
    course_id: str
    title: str
    description: Optional[str] = None
    week_number: Optional[int] = None
    order_index: int


class TopicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    week_number: Optional[int] = None
    order_index: Optional[int] = None


class TopicResponse(BaseModel):
    id: str
    course_id: str
    title: str
    description: Optional[str]
    week_number: Optional[int]
    order_index: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# =============================================================================
# Helpers
# =============================================================================


def _topic_to_dict(topic: Topic) -> dict:
    return {
        "id": str(topic.id),
        "course_id": str(topic.course_id),
        "title": topic.title,
        "description": topic.description,
        "week_number": topic.week_number,
        "order_index": topic.order_index,
        "created_at": topic.created_at.isoformat(),
        "updated_at": topic.updated_at.isoformat(),
    }


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/courses/{course_id}/topics", response_model=List[TopicResponse])
async def list_topics(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all topics for a course, ordered by order_index. Enrolled users only."""
    cache_key = topics_list_key(course_id)
    cached = await cache.get(cache_key)
    if cached is not None:
        # Enrollment still checked on every request — never cached
        await _assert_enrolled(db, current_user.id, course_id)
        return cached

    await _assert_enrolled(db, current_user.id, course_id)

    query = (
        select(Topic)
        .where(Topic.course_id == uuid.UUID(course_id))
        .order_by(Topic.order_index)
    )
    result = await db.execute(query)
    topics = result.scalars().all()
    payload = [_topic_to_dict(t) for t in topics]

    await cache.set(cache_key, payload, settings.CACHE_TTL_TOPICS)
    return payload


@router.post(
    "/courses/{course_id}/topics",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    course_id: str,
    topic_data: TopicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new topic in a course. Only enrolled students can create topics."""
    await _assert_enrolled(db, current_user.id, course_id)

    if topic_data.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course ID in URL and body must match",
        )

    topic = Topic(
        course_id=uuid.UUID(course_id),
        title=topic_data.title,
        description=topic_data.description,
        week_number=topic_data.week_number,
        order_index=topic_data.order_index,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)

    await _invalidate_topic_caches(course_id)

    return _topic_to_dict(topic)


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single topic details."""
    cache_key = topic_key(topic_id)
    cached = await cache.get(cache_key)
    if cached is not None:
        # Enrollment check against the cached course_id
        await _assert_enrolled(db, current_user.id, cached["course_id"])
        return cached

    query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await _assert_enrolled(db, current_user.id, str(topic.course_id))

    payload = _topic_to_dict(topic)
    await cache.set(cache_key, payload, settings.CACHE_TTL_TOPICS)
    return payload


@router.put("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    topic_data: TopicUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update topic details."""
    query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await _assert_enrolled(db, current_user.id, str(topic.course_id))

    if topic_data.title is not None:
        topic.title = topic_data.title
    if topic_data.description is not None:
        topic.description = topic_data.description
    if topic_data.week_number is not None:
        topic.week_number = topic_data.week_number
    if topic_data.order_index is not None:
        topic.order_index = topic_data.order_index

    await db.commit()
    await db.refresh(topic)

    await _invalidate_topic_caches(str(topic.course_id), topic_id)

    return _topic_to_dict(topic)


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a topic. Cascades to all resources."""
    query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    course_id = str(topic.course_id)
    await _assert_enrolled(db, current_user.id, course_id)

    await db.delete(topic)
    await db.commit()

    await _invalidate_topic_caches(course_id, topic_id)

    return None


# =============================================================================
# Private helpers
# =============================================================================


async def _assert_enrolled(db: AsyncSession, user_id, course_id: str) -> None:
    query = select(CourseEnrollment).where(
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.course_id == uuid.UUID(course_id),
    )
    result = await db.execute(query)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this course"
        )


async def _invalidate_topic_caches(course_id: str, topic_id: str | None = None) -> None:
    """Invalidate list + course detail + optionally individual topic cache."""
    await cache.delete(topics_list_key(course_id))
    await cache.delete(course_key(course_id))
    if topic_id:
        await cache.delete(topic_key(topic_id))
