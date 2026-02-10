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
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.resource import Resource, ResourceFile, ResourceKind, SourceType
from app.models.course import Topic
from app.api.auth import get_current_user, verify_course_enrollment
from app.models.user import User
from app.services.storage import storage_service
from app.services.file_processor import file_processor
from app.services.ocr_cleaner import ocr_cleaner
from app.services.redis_client import redis_client


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

    # Total count
    count_query = select(Resource).where(Resource.topic_id == uuid.UUID(topic_id))
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Build responses with uploader names
    from app.models.user import User as UserModel

    resource_responses = []
    for resource in resources:
        uploader_query = select(UserModel).where(UserModel.id == resource.uploaded_by)
        uploader_result = await db.execute(uploader_query)
        uploader = uploader_result.scalar_one_or_none()
        uploader_name = uploader.full_name if uploader else "Unknown"
        resource_responses.append(build_resource_response(resource, uploader_name))

    return ResourceListResponse(
        resources=resource_responses, total=total, page=page, page_size=page_size
    )


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
    await db.refresh(resource)

    # Enqueue for RAG chunking
    await redis_client.enqueue_job(
        "chunking", {"resource_id": str(resource.id), "text": resource.content}
    )

    return build_resource_response(resource, current_user.full_name)


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
    if image_files:
        image_resource = await _create_image_resource(
            db=db,
            topic=topic,
            user=current_user,
            title=title,
            is_handwritten=is_handwritten,
            image_files=image_files,
        )
        created_resources.append(image_resource)

    # ── Process documents → 1 Resource per file ──
    for file in doc_files:
        doc_resource = await _create_document_resource(
            db=db,
            topic=topic,
            user=current_user,
            title=title,
            file=file,
        )
        created_resources.append(doc_resource)

    await db.commit()

    # Refresh and enqueue RAG for each resource
    responses = []
    for resource in created_resources:
        await db.refresh(resource)

        await redis_client.enqueue_job(
            "chunking", {"resource_id": str(resource.id), "text": resource.content}
        )

        responses.append(build_resource_response(resource, current_user.full_name))

    return responses


async def _create_image_resource(
    db: AsyncSession,
    topic: Topic,
    user: User,
    title: Optional[str],
    is_handwritten: Optional[bool],
    image_files: List[UploadFile],
) -> Resource:
    """Create a single image Resource with multiple ResourceFile pages."""
    combined_text = []
    total_confidence = 0.0
    confidence_count = 0
    primary_provider = None
    primary_source = SourceType.PRINTED
    any_cleaned = False

    # Auto-generate title
    if not title:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"{topic.title} - {timestamp}"

    resource = Resource(
        topic_id=topic.id,
        uploaded_by=user.id,
        title=title,
        content="",  # Will be filled after processing
        resource_type=ResourceKind.IMAGE,
        source_type=SourceType.PRINTED,  # Updated below
        is_processed=False,
    )
    db.add(resource)
    await db.flush()  # Get resource.id

    for idx, file in enumerate(image_files):
        file_content = await file.read()
        ext = os.path.splitext(file.filename or "")[1].lower()

        # Upload to Cloudinary
        upload_result = await storage_service.upload_file(
            file=file_content,
            folder=f"notesos/{topic.course_id}/{topic.id}",
        )
        file_url = upload_result["url"]

        # OCR / extract text
        processing_result = await file_processor.process_uploaded_file(
            file_url=file_url, file_format=ext, is_handwritten=is_handwritten
        )

        extracted_text = processing_result["text"]
        source_type_str = processing_result["source_type"]
        needs_cleaning = processing_result["needs_cleaning"]
        ocr_confidence = processing_result.get("ocr_confidence")
        ocr_provider = processing_result.get("ocr_provider")
        needs_aggressive = processing_result.get("needs_aggressive_cleanup", False)

        # Track source type priority: HANDWRITTEN > PRINTED
        current_source = SourceType[source_type_str.upper()]
        if current_source == SourceType.HANDWRITTEN:
            primary_source = SourceType.HANDWRITTEN

        if ocr_provider:
            primary_provider = ocr_provider
        if ocr_confidence is not None:
            total_confidence += float(ocr_confidence)
            confidence_count += 1

        # Clean OCR if needed
        page_ocr_text = extracted_text if needs_cleaning else None
        final_text = extracted_text

        if needs_cleaning:
            any_cleaned = True
            cleaning_result = await ocr_cleaner.clean_ocr_text(
                extracted_text,
                aggressive=True,
                needs_aggressive_cleanup=needs_aggressive,
            )
            final_text = cleaning_result["cleaned_text"]

        combined_text.append(final_text)

        # Create ResourceFile for this page
        resource_file = ResourceFile(
            resource_id=resource.id,
            file_url=file_url,
            file_name=file.filename,
            file_order=idx,
            ocr_text=page_ocr_text,
            ocr_confidence=ocr_confidence,
            ocr_provider=ocr_provider,
        )
        db.add(resource_file)

    # Update resource with combined data
    resource.content = "\n\n---\n\n".join(combined_text)
    resource.source_type = primary_source
    resource.ocr_cleaned = any_cleaned
    resource.ocr_confidence = (
        total_confidence / confidence_count if confidence_count > 0 else None
    )
    resource.ocr_provider = primary_provider

    return resource


async def _create_document_resource(
    db: AsyncSession,
    topic: Topic,
    user: User,
    title: Optional[str],
    file: UploadFile,
) -> Resource:
    """Create a single Resource for a PDF or DOCX file."""
    file_content = await file.read()
    ext = os.path.splitext(file.filename or "")[1].lower()

    # Upload to Cloudinary
    upload_result = await storage_service.upload_file(
        file=file_content,
        folder=f"notesos/{topic.course_id}/{topic.id}",
    )
    file_url = upload_result["url"]

    # Extract text
    processing_result = await file_processor.process_uploaded_file(
        file_url=file_url, file_format=ext, is_handwritten=False
    )

    extracted_text = processing_result["text"]
    source_type_str = processing_result["source_type"]

    # Determine resource type
    resource_type = ResourceKind.PDF if ext == ".pdf" else ResourceKind.DOCX

    # Auto-generate title
    if not title:
        # Use filename without extension
        base_name = os.path.splitext(file.filename or "document")[0]
        title = base_name

    resource = Resource(
        topic_id=topic.id,
        uploaded_by=user.id,
        title=title,
        content=extracted_text,
        resource_type=resource_type,
        file_url=file_url,
        file_name=file.filename,
        source_type=SourceType[source_type_str.upper()],
        is_processed=False,
    )
    db.add(resource)

    return resource


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
    resource_query = select(Resource).where(Resource.id == uuid.UUID(resource_id))
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
    await db.refresh(resource)

    if content_changed:
        await redis_client.enqueue_job(
            "chunking", {"resource_id": str(resource.id), "text": resource.content}
        )

    return build_resource_response(resource, current_user.full_name)


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a resource. Only uploader can delete. Also deletes files from storage."""
    resource_query = select(Resource).where(Resource.id == uuid.UUID(resource_id))
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

    return None


@router.post("/resources/{resource_id}/reprocess-ocr", response_model=ResourceResponse)
async def reprocess_resource_ocr(
    resource_id: str,
    use_premium_ocr: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reprocess OCR for an image resource using improved transcription."""
    from app.config import settings

    if not settings.ALLOW_USER_REQUESTED_REPROCESS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OCR reprocessing is not enabled",
        )

    resource_query = select(Resource).where(Resource.id == uuid.UUID(resource_id))
    resource_result = await db.execute(resource_query)
    resource = resource_result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
        )

    if resource.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader can reprocess this resource",
        )

    if resource.resource_type != ResourceKind.IMAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image resources can be reprocessed",
        )

    if not resource.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image files available for reprocessing",
        )

    try:
        import httpx
        from app.services.hybrid_ocr import hybrid_ocr

        combined_text = []
        total_confidence = 0.0
        confidence_count = 0
        primary_provider = None

        for rf in sorted(resource.files, key=lambda x: x.file_order):
            async with httpx.AsyncClient() as client:
                response = await client.get(rf.file_url, timeout=30.0)
                response.raise_for_status()
                image_bytes = response.content

            ocr_result = await hybrid_ocr.process_handwritten_note(
                image_bytes,
                is_premium_user=use_premium_ocr,
            )

            new_raw_text = ocr_result["text"]
            cleaning_result = await ocr_cleaner.clean_ocr_text(
                new_raw_text,
                aggressive=True,
                needs_aggressive_cleanup=ocr_result.get(
                    "needs_aggressive_cleanup", False
                ),
            )
            new_cleaned_text = cleaning_result["cleaned_text"]

            # Update ResourceFile
            rf.ocr_text = new_raw_text
            rf.ocr_confidence = ocr_result["confidence"]
            rf.ocr_provider = ocr_result["provider"]

            combined_text.append(new_cleaned_text)

            if ocr_result["confidence"] is not None:
                total_confidence += float(ocr_result["confidence"])
                confidence_count += 1
            primary_provider = ocr_result["provider"]

        # Update Resource
        resource.content = "\n\n---\n\n".join(combined_text)
        resource.ocr_cleaned = True
        resource.ocr_confidence = (
            total_confidence / confidence_count if confidence_count > 0 else None
        )
        resource.ocr_provider = primary_provider
        resource.is_processed = False

        await db.commit()
        await db.refresh(resource)

        await redis_client.enqueue_job(
            "chunking", {"resource_id": str(resource.id), "text": resource.content}
        )

        return build_resource_response(resource, current_user.full_name)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR reprocessing failed: {str(e)}",
        )
