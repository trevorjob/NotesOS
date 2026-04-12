"""
NotesOS API - Resources Router
Manage resources within topics - CRUD, file uploads, OCR processing, RAG.

Resource = one logical piece of study material:
- Text typed by user
- PDF or DOCX upload (single file)
- Image upload (multi-page, stored as ResourceFiles)
"""

from typing import List, Optional
from datetime import datetime
import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.resource import Resource, ResourceFile, ResourceKind, SourceType
from app.models.course import Topic
from app.api.auth import get_current_user, verify_course_enrollment
from app.models.user import User
from app.services.storage import storage_service
from app.services.vision_transcribe import vision_transcribe
from app.services.redis_client import redis_client
from app.services.cache import cache, resources_list_key, resource_key
from app.config import settings
from app.models.course import CourseEnrollment


router = APIRouter()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────


class ResourceCreate(BaseModel):
    topic_id: str
    title: Optional[str] = None
    content: str


class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class ResourceFileResponse(BaseModel):
    id: str
    file_url: str
    file_name: Optional[str]
    file_order: int
    ocr_confidence: Optional[float] = None
    ocr_provider: Optional[str] = None


class ResourceResponse(BaseModel):
    id: str
    topic_id: str
    uploaded_by: str
    uploader_name: str
    title: Optional[str]
    content: str
    resource_type: str
    file_url: Optional[str]
    file_name: Optional[str]
    source_type: str
    is_processed: bool
    ocr_cleaned: bool
    is_verified: bool
    ocr_confidence: Optional[float] = None
    ocr_provider: Optional[str] = None
    files: List[ResourceFileResponse] = []
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ResourceListResponse(BaseModel):
    resources: List[ResourceResponse]
    total: int
    page: int
    page_size: int


# ── Helper ────────────────────────────────────────────────────────────────────


def build_resource_response(resource: Resource, uploader_name: str) -> ResourceResponse:
    """Build a ResourceResponse from a Resource model instance."""
    files = []
    if resource.files:
        for f in sorted(resource.files, key=lambda x: x.file_order):
            files.append(
                ResourceFileResponse(
                    id=str(f.id),
                    file_url=f.file_url,
                    file_name=f.file_name,
                    file_order=f.file_order,
                    ocr_confidence=float(f.ocr_confidence)
                    if f.ocr_confidence
                    else None,
                    ocr_provider=f.ocr_provider,
                )
            )

    return ResourceResponse(
        id=str(resource.id),
        topic_id=str(resource.topic_id),
        uploaded_by=str(resource.uploaded_by),
        uploader_name=uploader_name,
        title=resource.title,
        content=resource.content,
        resource_type=resource.resource_type.value,
        file_url=resource.file_url,
        file_name=resource.file_name,
        source_type=resource.source_type.value,
        is_processed=resource.is_processed,
        ocr_cleaned=resource.ocr_cleaned,
        is_verified=resource.is_verified,
        ocr_confidence=float(resource.ocr_confidence)
        if resource.ocr_confidence
        else None,
        ocr_provider=resource.ocr_provider,
        files=files,
        created_at=resource.created_at.isoformat(),
        updated_at=resource.updated_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/topics/{topic_id}/resources", response_model=ResourceListResponse)
async def list_resources(
    topic_id: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all resources for a topic with pagination."""
    topic_query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await verify_course_enrollment(db, current_user.id, topic.course_id)

    # ── Cache read-through ────────────────────────────────────────────────────
    cache_key = resources_list_key(topic_id, page, page_size)
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached
    # ─────────────────────────────────────────────────────────────────────────

    offset = (page - 1) * page_size
    resources_query = (
        select(Resource)
        .options(selectinload(Resource.files))
        .where(Resource.topic_id == uuid.UUID(topic_id))
        .order_by(Resource.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    resources_result = await db.execute(resources_query)
    resources = resources_result.scalars().all()

    # Total count — single scalar query, no row fetching
    total = await db.scalar(
        select(func.count()).where(Resource.topic_id == uuid.UUID(topic_id))
    )

    # Batch-load uploader names in one query
    from app.models.user import User as UserModel

    uploader_ids = list({r.uploaded_by for r in resources})
    uploader_map: dict = {}
    if uploader_ids:
        uploader_result = await db.execute(
            select(UserModel.id, UserModel.full_name).where(
                UserModel.id.in_(uploader_ids)
            )
        )
        uploader_map = {row.id: row.full_name for row in uploader_result}

    resource_responses = [
        build_resource_response(r, uploader_map.get(r.uploaded_by, "Unknown"))
        for r in resources
    ]

    result_payload = ResourceListResponse(
        resources=resource_responses, total=total, page=page, page_size=page_size
    )
    await cache.set(
        cache_key, result_payload.model_dump(), ttl_sec=settings.CACHE_TTL_RESOURCES
    )
    return result_payload


@router.post(
    "/topics/{topic_id}/resources/text",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_text_resource(
    topic_id: str,
    resource_data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new text resource (no file upload)."""
    topic_query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Auto-generate title if missing
    title = resource_data.title
    if not title:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"{topic.title} - {timestamp}"

    resource = Resource(
        topic_id=uuid.UUID(topic_id),
        uploaded_by=current_user.id,
        title=title,
        content=resource_data.content,
        resource_type=ResourceKind.TEXT,
        source_type=SourceType.TEXT,
        is_processed=False,
    )

    db.add(resource)
    await db.commit()
    # Re-fetch with eager loading for files
    resource_query = (
        select(Resource)
        .options(selectinload(Resource.files))
        .where(Resource.id == resource.id)
    )
    result = await db.execute(resource_query)
    resource = result.scalar_one()

    # Enqueue for RAG chunking
    await redis_client.enqueue_job(
        "chunking", {"resource_id": str(resource.id), "text": resource.content}
    )

    # Notify other course members about the new resource
    await _notify_course_members_resource_uploaded(
        db, topic.course_id, current_user.id, current_user.full_name, title, topic_id
    )

    # Invalidate resource list cache for this topic
    await cache.delete_pattern(f"notesos:v1:resources:topic:{topic_id}:")

    return build_resource_response(resource, current_user.full_name)


# ── Pydantic schema for direct-upload endpoint ────────────────────────────────


class UploadedFileItem(BaseModel):
    url: str
    public_id: Optional[str] = None
    filename: Optional[str] = None
    file_order: int = 0


class UploadUrlsRequest(BaseModel):
    topic_id: str
    title: Optional[str] = None
    is_handwritten: Optional[bool] = None
    files: List[UploadedFileItem]


@router.post(
    "/resources/upload-urls",
    response_model=List[ResourceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_resources_from_urls(
    body: UploadUrlsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create resources from files already uploaded directly to Cloudinary.

    The frontend uploads files directly to Cloudinary (bypassing the VPS),
    then sends the resulting URLs here. This endpoint only creates DB records
    and enqueues transcription — no file bytes cross the VPS.

    Image files are grouped into one Resource (multi-page); docs are separate.
    file_order from the client is preserved as the ResourceFile page order.
    """
    # Validate topic
    topic_query = select(Topic).where(Topic.id == uuid.UUID(body.topic_id))
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await verify_course_enrollment(db, current_user.id, topic.course_id)

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
    DOC_EXTS = {".pdf", ".doc", ".docx"}

    image_files = []
    doc_files = []

    for item in body.files:
        ext = os.path.splitext(item.filename or item.url.split("?")[0])[1].lower()
        if ext in IMAGE_EXTS:
            image_files.append(item)
        elif ext in DOC_EXTS:
            doc_files.append(item)
        else:
            # Unknown ext — treat as image (Cloudinary accepted it)
            image_files.append(item)

    created_resources = []
    image_urls_for_job: list[str] = []

    # ── Images → 1 Resource, multiple ResourceFiles ────────────────────────────
    if image_files:
        title = body.title
        if not title:
            from datetime import datetime as _dt

            title = f"{topic.title} - {_dt.now().strftime('%Y-%m-%d %H:%M')}"

        image_resource = Resource(
            topic_id=topic.id,
            uploaded_by=current_user.id,
            title=title,
            content="",  # Filled by transcription worker
            resource_type=ResourceKind.IMAGE,
            source_type=SourceType.PRINTED,
            is_processed=False,
            ocr_provider="gpt-vision",
        )
        db.add(image_resource)
        await db.flush()

        # Sort by provided file_order to guarantee page sequence
        for item in sorted(image_files, key=lambda x: x.file_order):
            rf = ResourceFile(
                resource_id=image_resource.id,
                file_url=item.url,
                file_name=item.filename,
                file_order=item.file_order,
                ocr_provider="gpt-vision",
            )
            db.add(rf)
            image_urls_for_job.append(item.url)

        created_resources.append(image_resource)

    # ── Documents → 1 Resource each ────────────────────────────────────────────
    doc_meta: list[tuple] = []
    for item in doc_files:
        ext = os.path.splitext(item.filename or "")[1].lower()
        resource_type = ResourceKind.PDF if ext == ".pdf" else ResourceKind.DOCX
        source_type = SourceType.PDF if ext == ".pdf" else SourceType.DOCX

        doc_title = body.title or os.path.splitext(item.filename or "document")[0]
        doc_resource = Resource(
            topic_id=topic.id,
            uploaded_by=current_user.id,
            title=doc_title,
            content="",  # Filled by transcription worker
            resource_type=resource_type,
            file_url=item.url,
            file_name=item.filename,
            source_type=source_type,
            is_processed=False,
        )
        db.add(doc_resource)
        created_resources.append(doc_resource)
        doc_meta.append((doc_resource, item.url, ext))

    await db.commit()

    # Build responses
    responses = []
    for resource in created_resources:
        rq = (
            select(Resource)
            .options(selectinload(Resource.files))
            .where(Resource.id == resource.id)
        )
        result = await db.execute(rq)
        refreshed = result.scalar_one()
        responses.append(build_resource_response(refreshed, current_user.full_name))

    # ── Enqueue transcription jobs ──────────────────────────────────────────────
    course_id_str = str(topic.course_id)

    if image_files and image_urls_for_job:
        await redis_client.enqueue_job(
            "transcription",
            {
                "type": "image",
                "resource_id": str(image_resource.id),
                "image_urls": image_urls_for_job,
                "course_id": course_id_str,
            },
        )

    for doc_resource, file_url, file_ext in doc_meta:
        await redis_client.enqueue_job(
            "transcription",
            {
                "type": "document",
                "resource_id": str(doc_resource.id),
                "file_url": file_url,
                "file_ext": file_ext,
                "course_id": course_id_str,
            },
        )

    await cache.delete_pattern(f"notesos:v1:resources:topic:{body.topic_id}:")

    # Notify other course members about the new upload
    upload_title = body.title or f"{len(responses)} file(s)"
    await _notify_course_members_resource_uploaded(
        db, topic.course_id, current_user.id, current_user.full_name, upload_title, body.topic_id
    )

    return responses


@router.post(
    "/resources/upload",
    response_model=List[ResourceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_resources(
    topic_id: str = Form(...),
    title: Optional[str] = Form(None),
    is_handwritten: Optional[bool] = Form(None),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload file(s) as resources.

    Behavior:
    - Images (.jpg, .png, etc.) → grouped into 1 Resource with multiple pages
    - PDFs (.pdf) → 1 Resource each
    - DOCX (.docx) → 1 Resource each

    Mixed uploads create multiple Resources (images grouped, docs separate).
    """
    # Validate topic
    topic_query = select(Topic).where(Topic.id == uuid.UUID(topic_id))
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )

    await verify_course_enrollment(db, current_user.id, topic.course_id)

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
    DOC_EXTS = {".pdf", ".doc", ".docx"}
    ALLOWED = IMAGE_EXTS | DOC_EXTS

    # Separate files by type
    image_files = []
    doc_files = []

    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {ext}",
            )
        if ext in IMAGE_EXTS:
            image_files.append(file)
        else:
            doc_files.append(file)

    created_resources = []

    # ── Process images → 1 Resource with multiple ResourceFiles ──
    image_urls_for_job: list[str] = []
    if image_files:
        image_resource, image_urls_for_job = await _create_image_resource(
            db=db,
            topic=topic,
            user=current_user,
            title=title,
            is_handwritten=is_handwritten,
            image_files=image_files,
        )
        created_resources.append(image_resource)

    # ── Process documents → 1 Resource per file ──
    doc_meta: list[tuple] = []  # (resource, file_url, file_ext)
    for file in doc_files:
        doc_resource, file_url, file_ext = await _create_document_resource(
            db=db,
            topic=topic,
            user=current_user,
            title=title,
            file=file,
        )
        created_resources.append(doc_resource)
        doc_meta.append((doc_resource, file_url, file_ext))

    await db.commit()

    # Refresh all resources and build responses
    responses = []
    for resource in created_resources:
        resource_query = (
            select(Resource)
            .options(selectinload(Resource.files))
            .where(Resource.id == resource.id)
        )
        result = await db.execute(resource_query)
        refreshed_resource = result.scalar_one()
        responses.append(
            build_resource_response(refreshed_resource, current_user.full_name)
        )

    # ── Enqueue transcription jobs (non-blocking AI work) ────────────────────
    course_id_str = str(topic.course_id)

    if image_files and image_urls_for_job:
        await redis_client.enqueue_job(
            "transcription",
            {
                "type": "image",
                "resource_id": str(image_resource.id),
                "image_urls": image_urls_for_job,
                "course_id": course_id_str,
            },
        )

    for doc_resource, file_url, file_ext in doc_meta:
        await redis_client.enqueue_job(
            "transcription",
            {
                "type": "document",
                "resource_id": str(doc_resource.id),
                "file_url": file_url,
                "file_ext": file_ext,
                "course_id": course_id_str,
            },
        )

    # Invalidate resource list cache for this topic (uploads change the list)
    await cache.delete_pattern(f"notesos:v1:resources:topic:{topic_id}:")

    return responses


async def _create_image_resource(
    db: AsyncSession,
    topic: Topic,
    user: User,
    title: Optional[str],
    is_handwritten: Optional[bool],
    image_files: List[UploadFile],
) -> tuple:
    """
    Create a single image Resource with multiple ResourceFile pages.

    Flow:
    1. Upload all images to Cloudinary concurrently.
    2. Create ResourceFile records.
    3. Return resource + image_urls (AI transcription is enqueued separately).

    Returns:
        (Resource, list[image_url])
    """
    # Auto-generate title
    if not title:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"{topic.title} - {timestamp}"

    resource = Resource(
        topic_id=topic.id,
        uploaded_by=user.id,
        title=title,
        content="",  # Filled by transcription worker
        resource_type=ResourceKind.IMAGE,
        source_type=SourceType.PRINTED,
        is_processed=False,
        ocr_provider="gpt-vision",
    )
    db.add(resource)
    await db.flush()  # Get resource.id

    # ── Upload all images to Cloudinary concurrently ────────────────────────
    file_contents: list[bytes] = []
    for file in image_files:
        file_contents.append(await file.read())

    upload_tasks = [
        storage_service.upload_file(
            file=content,
            folder=f"notesos/{topic.course_id}/{topic.id}",
        )
        for content in file_contents
    ]
    upload_results = await asyncio.gather(*upload_tasks)
    image_urls = [r["url"] for r in upload_results]

    # ── Create ResourceFile records ──────────────────────────────────────────
    for idx, (file, file_url) in enumerate(zip(image_files, image_urls)):
        resource_file = ResourceFile(
            resource_id=resource.id,
            file_url=file_url,
            file_name=file.filename,
            file_order=idx,
            ocr_text=None,
            ocr_confidence=None,
            ocr_provider="gpt-vision",
        )
        db.add(resource_file)

    # Transcription is enqueued by the caller after db.commit()
    return resource, image_urls


async def _create_document_resource(
    db: AsyncSession,
    topic: Topic,
    user: User,
    title: Optional[str],
    file: UploadFile,
) -> tuple:
    """
    Create a single Resource for a PDF or DOCX file.

    Uploads the file to Cloudinary and saves the record immediately.
    Text extraction is enqueued to the transcription worker by the caller.

    Returns:
        (Resource, file_url, file_ext)
    """
    file_content = await file.read()
    ext = os.path.splitext(file.filename or "")[1].lower()

    # Upload to Cloudinary only — extraction happens in background worker
    upload_result = await storage_service.upload_file(
        file=file_content,
        folder=f"notesos/{topic.course_id}/{topic.id}",
    )
    file_url = upload_result["url"]

    # Determine resource type and default source_type
    resource_type = ResourceKind.PDF if ext == ".pdf" else ResourceKind.DOCX
    source_type = SourceType.PDF if ext == ".pdf" else SourceType.DOCX

    # Auto-generate title from filename if not provided
    if not title:
        base_name = os.path.splitext(file.filename or "document")[0]
        title = base_name

    resource = Resource(
        topic_id=topic.id,
        uploaded_by=user.id,
        title=title,
        content="",  # Filled by transcription worker
        resource_type=resource_type,
        file_url=file_url,
        file_name=file.filename,
        source_type=source_type,
        is_processed=False,
    )
    db.add(resource)

    return resource, file_url, ext


@router.get("/resources/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single resource details (includes ResourceFiles if image type)."""
    resource_query = (
        select(Resource)
        .options(selectinload(Resource.files))
        .where(Resource.id == uuid.UUID(resource_id))
    )
    resource_result = await db.execute(resource_query)
    resource = resource_result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    # Verify enrollment via topic
    topic_query = select(Topic).where(Topic.id == resource.topic_id)
    topic_result = await db.execute(topic_query)
    topic = topic_result.scalar_one_or_none()

    if topic:
        await verify_course_enrollment(db, current_user.id, topic.course_id)

    # Fetch uploader
    from app.models.user import User as UserModel

    uploader_query = select(UserModel).where(UserModel.id == resource.uploaded_by)
    uploader_result = await db.execute(uploader_query)
    uploader = uploader_result.scalar_one_or_none()

    return build_resource_response(
        resource, uploader.full_name if uploader else "Unknown"
    )


@router.put("/resources/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: str,
    resource_data: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update resource content/title. Only the uploader can edit."""
    resource_query = (
        select(Resource)
        .options(selectinload(Resource.files))
        .where(Resource.id == uuid.UUID(resource_id))
    )
    resource_result = await db.execute(resource_query)
    resource = resource_result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    if resource.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader can edit this resource",
        )

    content_changed = False

    if resource_data.title is not None:
        resource.title = resource_data.title

    if resource_data.content is not None:
        resource.content = resource_data.content
        content_changed = True
        resource.is_processed = False

    await db.commit()

    # Re-fetch with eager loading for files to avoid MissingGreenlet
    resource_query = (
        select(Resource)
        .options(selectinload(Resource.files))
        .where(Resource.id == resource.id)
    )
    result = await db.execute(resource_query)
    resource = result.scalar_one()

    if content_changed:
        await redis_client.enqueue_job(
            "chunking", {"resource_id": str(resource.id), "text": resource.content}
        )

    # Invalidate list cache and single resource cache
    await cache.delete_pattern(f"notesos:v1:resources:topic:{resource.topic_id}:")
    await cache.delete(resource_key(resource_id))

    return build_resource_response(resource, current_user.full_name)


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a resource. Only uploader can delete. Also deletes files from storage."""
    resource_query = (
        select(Resource)
        .options(selectinload(Resource.files))
        .where(Resource.id == uuid.UUID(resource_id))
    )
    resource_result = await db.execute(resource_query)
    resource = resource_result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    if resource.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader can delete this resource",
        )

    # Delete files from storage
    if resource.file_url:
        try:
            await storage_service.delete_file(resource.file_url)
        except Exception:
            pass

    # Delete ResourceFile files from storage
    if resource.files:
        for rf in resource.files:
            try:
                await storage_service.delete_file(rf.file_url)
            except Exception:
                pass

    await db.delete(resource)
    await db.commit()

    # Invalidate list cache and single resource cache
    await cache.delete_pattern(f"notesos:v1:resources:topic:{resource.topic_id}:")
    await cache.delete(resource_key(resource_id))

    return None


@router.post("/resources/{resource_id}/retranscribe", response_model=ResourceResponse)
async def retranscribe_resource(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-transcribe an image resource using GPT-4o Vision.

    Replaces resource.content with a fresh AI transcript and re-enqueues chunking.
    Only the original uploader can trigger this.
    """
    resource_query = (
        select(Resource)
        .options(selectinload(Resource.files))
        .where(Resource.id == uuid.UUID(resource_id))
    )
    resource_result = await db.execute(resource_query)
    resource = resource_result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    if resource.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader can re-transcribe this resource",
        )

    if resource.resource_type != ResourceKind.IMAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image resources can be re-transcribed",
        )

    if not resource.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image files available for transcription",
        )

    try:
        # Collect image URLs in page order
        image_urls = [
            rf.file_url for rf in sorted(resource.files, key=lambda x: x.file_order)
        ]

        # Single Vision API call for all pages
        transcript = await vision_transcribe.transcribe_images(image_urls)

        # Update provider tag on each ResourceFile
        for rf in resource.files:
            rf.ocr_provider = "gpt-vision"
            rf.ocr_confidence = None

        # Update Resource
        resource.content = transcript
        resource.ocr_cleaned = False
        resource.ocr_confidence = None
        resource.ocr_provider = "gpt-vision"
        resource.is_processed = False

        await db.commit()

        # Re-fetch with eager loading
        resource_query = (
            select(Resource)
            .options(selectinload(Resource.files))
            .where(Resource.id == resource.id)
        )
        result = await db.execute(resource_query)
        resource = result.scalar_one()

        await redis_client.enqueue_job(
            "chunking", {"resource_id": str(resource.id), "text": resource.content}
        )

        return build_resource_response(resource, current_user.full_name)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Re-transcription failed: {str(e)}",
        )


async def _notify_course_members_resource_uploaded(
    db,
    course_id,
    uploader_id,
    uploader_name: str,
    resource_title: str,
    topic_id: str,
) -> None:
    """Notify all enrolled course members (except the uploader) about a new resource."""
    from app.services.notifications import create_and_push_notification
    from app.models.notification import NotificationType

    result = await db.execute(
        select(CourseEnrollment.user_id).where(CourseEnrollment.course_id == course_id)
    )
    member_ids = [row[0] for row in result.fetchall() if row[0] != uploader_id]

    for member_id in member_ids:
        try:
            await create_and_push_notification(
                db=db,
                user_id=member_id,
                notif_type=NotificationType.RESOURCE_UPLOADED,
                title=f"{uploader_name} added a resource",
                body=resource_title,
                meta_data={"topic_id": str(topic_id), "course_id": str(course_id)},
            )
        except Exception:
            pass  # Non-fatal — don't fail the upload if a notification errors
