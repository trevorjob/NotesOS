"""
NotesOS - Transcription Worker
Background worker that handles AI text extraction for uploaded files.

Offloads GPT-4o Vision (images), Tesseract/mammoth (PDFs/DOCX), and Whisper
(audio) from the HTTP request cycle so uploads return immediately with 201.

Job shape:
  Image:    {"type": "image",    "resource_id": str, "image_urls": [str], "course_id": str}
  Document: {"type": "document", "resource_id": str, "file_url": str,     "file_ext": str, "course_id": str}
  Audio:    {"type": "audio",    "resource_id": str, "file_url": str,     "file_ext": str, "course_id": str}
"""

import asyncio
import uuid
from sqlalchemy import select

from app.database import worker_session
from app.models.resource import Resource
from app.services.redis_client import redis_client
from app.services.vision_transcribe import vision_transcribe
from app.services.file_processor import file_processor
from app.workers.base import run_worker_loop


async def _broadcast(course_id: str, resource_id: str, status: str) -> None:
    """Publish a processing_status event via Redis pub-sub → WebSocket."""
    await redis_client.publish(
        channel="course_updates",
        message={
            "course_id": course_id,
            "message": {
                "type": "processing_status",
                "resource_id": resource_id,
                "status": status,
            },
        },
    )


async def process_transcription_job(job_data: dict) -> None:
    """
    Run transcription for one job and persist the result.

    On success: sets resource.content, resource.is_processed=False (chunking handles True),
                broadcasts 'transcription_completed', then re-enqueues chunking.
    On failure: broadcasts 'failed' and logs the error.
    """
    job_type = job_data.get("type")
    resource_id = job_data.get("resource_id")
    course_id = job_data.get("course_id", "")

    if not resource_id or job_type not in ("image", "document", "audio"):
        print(f"[TRANSCRIPTION WORKER] Invalid job data: {job_data}")
        return

    print(
        f"[TRANSCRIPTION WORKER] Starting {job_type} transcription for resource {resource_id}"
    )

    if course_id:
        await _broadcast(course_id, resource_id, "processing")

    async with worker_session() as db:
        try:
            resource_query = select(Resource).where(
                Resource.id == uuid.UUID(resource_id)
            )
            result = await db.execute(resource_query)
            resource = result.scalar_one_or_none()

            if not resource:
                print(
                    f"[TRANSCRIPTION WORKER] Resource {resource_id} not found — skipping"
                )
                return

            # ── Transcribe ─────────────────────────────────────────────────────
            if job_type == "image":
                image_urls = job_data.get("image_urls", [])
                if not image_urls:
                    print(
                        f"[TRANSCRIPTION WORKER] No image_urls for resource {resource_id}"
                    )
                    return
                transcript = await vision_transcribe.transcribe_images(image_urls)
                resource.content = transcript
                resource.ocr_provider = "gpt-vision"
                resource.ocr_cleaned = False
                # Honesty seam: score the transcript's own uncertainty markers so a
                # blurry scan is flagged for review, never silently accepted.
                from app.services.capture import estimate_confidence

                resource.ocr_confidence = estimate_confidence(transcript)

            elif job_type == "audio":
                file_url = job_data.get("file_url", "")
                if not file_url:
                    print(
                        f"[TRANSCRIPTION WORKER] Missing file_url for audio resource {resource_id}"
                    )
                    return
                from app.services.transcription import transcription_service

                whisper_result = await transcription_service.transcribe_audio(
                    file_url, file_ext=job_data.get("file_ext", "")
                )
                resource.content = whisper_result["text"]

            else:  # document
                file_url = job_data.get("file_url", "")
                file_ext = job_data.get("file_ext", "")
                if not file_url or not file_ext:
                    print(
                        f"[TRANSCRIPTION WORKER] Missing file_url/file_ext for resource {resource_id}"
                    )
                    return
                processing_result = await file_processor.process_uploaded_file(
                    file_url=file_url,
                    file_format=file_ext,
                    is_handwritten=False,
                )
                resource.content = processing_result["text"]

            await db.commit()
            print(
                f"[TRANSCRIPTION WORKER] ✅ Transcription done for resource {resource_id}"
            )

            # ── Hand off to chunking worker ────────────────────────────────────
            await redis_client.enqueue_job(
                "chunking",
                {"resource_id": resource_id, "text": resource.content},
            )

        except Exception as exc:
            print(f"[TRANSCRIPTION WORKER] ❌ Error for resource {resource_id}: {exc}")
            await db.rollback()
            if course_id:
                await _broadcast(course_id, resource_id, "failed")


async def transcription_worker() -> None:
    """Drain the transcription queue via the shared reliable worker loop."""
    await run_worker_loop("transcription", process_transcription_job)


if __name__ == "__main__":
    asyncio.run(transcription_worker())
