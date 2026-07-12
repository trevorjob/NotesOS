"""
NotesOS API - Capture Router (A2)

The two course-level capture surfaces:

- ``POST /api/courses/{course_id}/outline`` — the outline scaffold: paste or snap a
  syllabus → the semester's topics are created up front as empty, labeled buckets.
- ``POST /api/courses/{course_id}/capture`` — the dump: throw a whole pile of files
  in with **zero filing**. Returns 202 immediately ("capture is instant and dumb");
  a background worker transcribes, sorts the pile into topics (classify when an
  outline exists, cluster-and-propose when not), auto-files, and broadcasts
  ``capture_*`` events over the course WebSocket.

Topic-level (direct) adds stay on the resources router — navigating to a topic
already implies the destination, so those skip classification entirely.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import json

from app.api.auth import get_current_user, verify_course_enrollment
from app.models.course import Course, CourseOutline, Topic
from app.models.user import User
from app.database import get_db
from app.services import capture as capture_service
from app.services.capture_types import ext_of, kind_of
from app.services.cache import cache, topics_list_key
from app.services.redis_client import redis_client
from app.services.vision_transcribe import vision_transcribe

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────


class OutlineRequest(BaseModel):
    """Paste text and/or snap photos of the syllabus (either or both)."""

    text: Optional[str] = None
    image_urls: List[str] = []


class OutlineTopicOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    week_number: Optional[int] = None
    order_index: int


class OutlineResponse(BaseModel):
    created: List[OutlineTopicOut]
    skipped: List[str]  # titles that already existed (case-insensitive match)


class CaptureFileItem(BaseModel):
    url: str
    filename: Optional[str] = None
    file_order: int = 0


class CaptureRequest(BaseModel):
    files: List[CaptureFileItem]
    title: Optional[str] = None


class CaptureAccepted(BaseModel):
    batch_id: str
    status: str = "processing"
    file_count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/courses/{course_id}/outline",
    response_model=OutlineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def scaffold_outline(
    course_id: str,
    body: OutlineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parse a syllabus (pasted and/or photographed) into the topic scaffold.

    Idempotent-ish: topics whose title already exists in the course
    (case-insensitive) are skipped, so one classmate adding the outline after
    another causes no duplicates — the outline is a communal artifact.
    """
    course_uuid = uuid.UUID(course_id)
    course = await db.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    await verify_course_enrollment(db, current_user.id, course_uuid)

    raw_text = (body.text or "").strip()
    if body.image_urls:
        # Snapped syllabus — transcribe the photo(s) first, then parse as text.
        snapped = await vision_transcribe.transcribe_images(body.image_urls)
        raw_text = f"{raw_text}\n\n{snapped}".strip()

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide the outline as text and/or image_urls.",
        )

    parsed = await capture_service.parse_outline(raw_text)
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't find any topics in that outline.",
        )

    # Existing titles (case-insensitive) → skip; scaffold continues numbering after them.
    existing_res = await db.execute(select(Topic).where(Topic.course_id == course_uuid))
    existing = existing_res.scalars().all()
    existing_titles = {t.title.strip().lower() for t in existing}
    next_index_res = await db.execute(
        select(func.coalesce(func.max(Topic.order_index), -1)).where(
            Topic.course_id == course_uuid
        )
    )
    next_index = (next_index_res.scalar_one() or 0) + 1 if existing else 0

    created: list[Topic] = []
    skipped: list[str] = []
    seen_in_batch: set[str] = set()
    for entry in parsed:
        key = entry["title"].strip().lower()
        if key in existing_titles or key in seen_in_batch:
            skipped.append(entry["title"])
            continue
        seen_in_batch.add(key)
        topic = Topic(
            course_id=course_uuid,
            title=entry["title"],
            description=entry["description"],
            week_number=entry["week_number"],
            order_index=next_index,
        )
        next_index += 1
        db.add(topic)
        created.append(topic)

    # Keep the raw syllabus — the outline is a communal artifact (re-parse,
    # coverage tracking, and the class inherits one canonical skeleton).
    db.add(
        CourseOutline(
            course_id=course_uuid,
            uploaded_by=current_user.id,
            outline_content=raw_text,
            parsed_topics=json.dumps(parsed),
        )
    )

    await db.commit()
    for topic in created:
        await db.refresh(topic)

    await cache.delete(topics_list_key(course_id))

    return OutlineResponse(
        created=[
            OutlineTopicOut(
                id=str(t.id),
                title=t.title,
                description=t.description,
                week_number=t.week_number,
                order_index=t.order_index,
            )
            for t in created
        ],
        skipped=skipped,
    )


@router.post(
    "/courses/{course_id}/capture",
    response_model=CaptureAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def capture_dump(
    course_id: str,
    body: CaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk dump: files already uploaded to Cloudinary, zero filing required.

    Validates and returns 202 immediately; the capture worker transcribes,
    organizes (outline-classify or cluster-and-propose), auto-files into topics,
    and pushes ``capture_progress`` / ``capture_complete`` WebSocket events.
    """
    course_uuid = uuid.UUID(course_id)
    course = await db.get(Course, course_uuid)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    await verify_course_enrollment(db, current_user.id, course_uuid)

    if not body.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided."
        )
    for item in body.files:
        ext = ext_of(item.filename, item.url)
        if kind_of(ext) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {ext or '(none)'}",
            )

    batch_id = str(uuid.uuid4())
    await redis_client.enqueue_job(
        "capture",
        {
            "batch_id": batch_id,
            "course_id": course_id,
            "user_id": str(current_user.id),
            "uploader_name": current_user.full_name,
            "title": body.title,
            "files": [
                {"url": f.url, "filename": f.filename, "file_order": f.file_order}
                for f in sorted(body.files, key=lambda f: f.file_order)
            ],
        },
    )

    return CaptureAccepted(batch_id=batch_id, file_count=len(body.files))
