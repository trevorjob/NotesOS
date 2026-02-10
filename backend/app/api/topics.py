"""
NotesOS API - Topics Router
Manage topics within courses (organize notes by weeks/units).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.course import Topic
from app.api.auth import get_current_user, verify_course_enrollment
from app.models.user import User


router = APIRouter()


# Pydantic schemas
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


@router.get("/courses/{course_id}/topics", response_model=List[TopicResponse])
async def list_topics(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all topics for a course, ordered by order_index.
    Only accessible to enrolled students.
    """
    # Verify user is enrolled
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    # Fetch topics
    query = (
        select(Topic)
        .where(Topic.course_id == uuid.UUID(course_id))
        .order_by(Topic.order_index)
    )

    result = await db.execute(query)
    topics = result.scalars().all()

    return [
        TopicResponse(
            id=str(topic.id),
            course_id=str(topic.course_id),
            title=topic.title,
            description=topic.description,
            week_number=topic.week_number,
            order_index=topic.order_index,
            created_at=topic.created_at.isoformat(),
            updated_at=topic.updated_at.isoformat(),
        )
        for topic in topics
    ]


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
    """
    Create a new topic in a course.
    Only enrolled students can create topics.
    """
    # Verify enrollment
    await verify_course_enrollment(db, current_user.id, uuid.UUID(course_id))

    # Ensure course_id matches URL
    if topic_data.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course ID in URL and body must match",
        )

    # Create topic
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

    return TopicResponse(
        id=str(topic.id),
        course_id=str(topic.course_id),
        title=topic.title,
        description=topic.description,
        week_number=topic.week_number,
        order_index=topic.order_index,
        created_at=topic.created_at.isoformat(),
        updated_at=topic.updated_at.isoformat(),
    )


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single topic details."""
    # Fetch topic
    query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    # Verify enrollment
    await verify_course_enrollment(db, current_user.id, topic.course_id)

    return TopicResponse(
        id=str(topic.id),
        course_id=str(topic.course_id),
        title=topic.title,
        description=topic.description,
        week_number=topic.week_number,
        order_index=topic.order_index,
        created_at=topic.created_at.isoformat(),
        updated_at=topic.updated_at.isoformat(),
    )


@router.put("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    topic_data: TopicUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update topic details."""
    # Fetch topic
    query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    # Verify enrollment
    await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Update fields
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

    return TopicResponse(
        id=str(topic.id),
        course_id=str(topic.course_id),
        title=topic.title,
        description=topic.description,
        week_number=topic.week_number,
        order_index=topic.order_index,
        created_at=topic.created_at.isoformat(),
        updated_at=topic.updated_at.isoformat(),
    )


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a topic.
    This will cascade delete all notes in the topic.
    """
    # Fetch topic
    query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    # Verify enrollment
    await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Delete
    await db.delete(topic)
    await db.commit()

    return None
