"""
NotesOS - Capture Worker (A2: dump → auto-organize)

Consumes course-level bulk dumps. The endpoint accepted the pile instantly; this
worker does the deferred-smart half:

  1. transcribe every file (vision / doc extraction / Whisper), per-file error
     isolation so one bad scan never sinks the batch;
  2. sort the pile into topics — **classify** into the known topics when the course
     has an outline/topics, **cluster + name** when it doesn't;
  3. auto-file: create the topics and resources and hand each resource to the
     normal pipeline (chunking → merge gate → synthesis). The merge gate still
     guards the shared note, exactly as for a direct upload;
  4. broadcast ``capture_progress`` / ``capture_complete`` (or ``capture_failed``)
     over the course WebSocket so the client can show "here's how I filed it".

Auto-file is deliberate (LOCKED capture design: review-and-adjust is *opt-out*) —
if the user never confirms, the material still lands. Tweaks are ordinary edits
(move / rename), not a staging approval.

Job shape:
  {"batch_id": str, "course_id": str, "user_id": str, "uploader_name": str,
   "title": str|None, "files": [{"url": str, "filename": str|None, "file_order": int}]}
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import func, select

from app.database import worker_session
from app.models.resource import Resource, ResourceFile, ResourceKind, SourceType
from app.models.course import Topic
from app.services import capture as capture_service
from app.services.capture_types import doc_resource_kinds, ext_of, kind_of
from app.services.cache import cache, topics_list_key
from app.services.embeddings import EmbeddingService
from app.services.file_processor import file_processor
from app.services.redis_client import redis_client
from app.services.transcription import transcription_service
from app.services.vision_transcribe import vision_transcribe
from app.workers.base import run_worker_loop

# How many files transcribe concurrently inside one batch.
TRANSCRIBE_CONCURRENCY = 3

_KIND_TO_RESOURCE = {
    "image": (ResourceKind.IMAGE, SourceType.PRINTED),
    "audio": (ResourceKind.AUDIO, SourceType.AUDIO),
}


async def _broadcast(course_id: str, message: dict) -> None:
    await redis_client.publish(
        channel="course_updates",
        message={"course_id": course_id, "message": message},
    )


async def _transcribe_one(item: dict) -> dict:
    """Transcribe a single dumped file. Returns the item + transcript or error."""
    ext = ext_of(item.get("filename"), item.get("url", ""))
    kind = kind_of(ext) or "image"
    out = {**item, "ext": ext, "kind": kind}
    try:
        if kind == "image":
            out["transcript"] = await vision_transcribe.transcribe_images([item["url"]])
        elif kind == "audio":
            result = await transcription_service.transcribe_audio(
                item["url"], file_ext=ext
            )
            out["transcript"] = result["text"]
        else:  # doc
            result = await file_processor.process_uploaded_file(
                file_url=item["url"], file_format=ext, is_handwritten=False
            )
            out["transcript"] = result["text"]
    except Exception as exc:  # per-file isolation — the batch survives
        out["error"] = str(exc)
    return out


async def _transcribe_all(files: list[dict]) -> list[dict]:
    semaphore = asyncio.Semaphore(TRANSCRIBE_CONCURRENCY)

    async def bounded(item: dict) -> dict:
        async with semaphore:
            return await _transcribe_one(item)

    return list(await asyncio.gather(*(bounded(f) for f in files)))


def _excerpt_items(items: list[dict]) -> list[dict]:
    return [
        {
            "name": item.get("filename") or item.get("url", "")[-40:],
            "excerpt": (item.get("transcript") or "")[: capture_service.EXCERPT_CHARS],
        }
        for item in items
    ]


async def _organize(db, course_uuid, items: list[dict]) -> tuple[list[dict], list[Topic]]:
    """Decide a topic per item.

    Returns (assignments, existing_topics): one assignment per item —
    {"topic_index": int} into existing_topics, or {"new_topic": str}. Outline path
    when the course already has topics (classification against labeled buckets);
    cluster-and-propose otherwise.
    """
    topics_res = await db.execute(
        select(Topic).where(Topic.course_id == course_uuid).order_by(Topic.order_index)
    )
    existing_topics = list(topics_res.scalars().all())

    if existing_topics:
        titles = [t.title for t in existing_topics]
        assignments = await capture_service.classify_items(_excerpt_items(items), titles)
        return assignments, existing_topics

    # No outline — embed, cluster, and let the LLM name the proposed buckets.
    excerpts = [e["excerpt"] or e["name"] for e in _excerpt_items(items)]
    embeddings = await EmbeddingService().generate_embeddings_batch(excerpts)
    labels = capture_service.cluster_items(embeddings)
    n_clusters = max(labels) + 1 if labels else 0
    members: list[list[dict]] = [[] for _ in range(n_clusters)]
    for item, label in zip(_excerpt_items(items), labels):
        members[label].append(item)
    names = await capture_service.name_clusters(members)
    return (
        [{"new_topic": names[label]["title"]} for label in labels],
        existing_topics,
    )


async def process_capture_job(job_data: dict) -> None:
    batch_id = job_data.get("batch_id", "")
    course_id = job_data.get("course_id", "")
    user_id = job_data.get("user_id", "")
    files = job_data.get("files") or []
    if not (batch_id and course_id and user_id and files):
        print(f"[CAPTURE WORKER] Invalid job data: {job_data}")
        return

    course_uuid = uuid.UUID(course_id)
    uploader_uuid = uuid.UUID(user_id)

    await _broadcast(
        course_id,
        {"type": "capture_progress", "batch_id": batch_id, "stage": "transcribing",
         "file_count": len(files)},
    )

    # ── 1. Transcribe the pile ────────────────────────────────────────────────
    transcribed = await _transcribe_all(files)
    ok_items = [t for t in transcribed if not t.get("error") and (t.get("transcript") or "").strip()]
    failed = [
        {"url": t.get("url"), "filename": t.get("filename"), "error": t.get("error", "empty transcript")}
        for t in transcribed
        if t.get("error") or not (t.get("transcript") or "").strip()
    ]

    if not ok_items:
        await _broadcast(
            course_id,
            {"type": "capture_failed", "batch_id": batch_id, "failed": failed},
        )
        return

    await _broadcast(
        course_id,
        {"type": "capture_progress", "batch_id": batch_id, "stage": "organizing",
         "file_count": len(ok_items)},
    )

    async with worker_session() as db:
        try:
            # ── 2. Sort the pile into topics ──────────────────────────────────
            assignments, existing_topics = await _organize(db, course_uuid, ok_items)

            # ── 3. Materialise new topics (dedupe by lowercase title) ─────────
            next_index_res = await db.execute(
                select(func.coalesce(func.max(Topic.order_index), -1)).where(
                    Topic.course_id == course_uuid
                )
            )
            next_index = next_index_res.scalar_one() + 1
            by_title: dict[str, Topic] = {t.title.strip().lower(): t for t in existing_topics}
            for assignment in assignments:
                label = assignment.get("new_topic")
                if not label or label.strip().lower() in by_title:
                    continue
                topic = Topic(
                    course_id=course_uuid,
                    title=label,
                    order_index=next_index,
                )
                next_index += 1
                db.add(topic)
                by_title[label.strip().lower()] = topic
            await db.flush()

            # ── 4. Auto-file: create the resources ────────────────────────────
            created: list[tuple[Resource, dict]] = []
            for item, assignment in zip(ok_items, assignments):
                if "topic_index" in assignment:
                    topic = existing_topics[assignment["topic_index"]]
                else:
                    topic = by_title[assignment["new_topic"].strip().lower()]

                kind = item["kind"]
                resource_kind, source_type = _KIND_TO_RESOURCE.get(
                    kind, doc_resource_kinds(item["ext"])
                )
                base_name = item.get("filename") or ""
                title = (
                    base_name.rsplit(".", 1)[0]
                    if base_name
                    else f"{topic.title} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                resource = Resource(
                    topic_id=topic.id,
                    uploaded_by=uploader_uuid,
                    title=title[:255],
                    content=item["transcript"],
                    resource_type=resource_kind,
                    file_url=None if kind == "image" else item["url"],
                    file_name=item.get("filename"),
                    source_type=source_type,
                    is_processed=False,
                    ocr_provider="gpt-vision" if kind == "image" else None,
                    ocr_confidence=(
                        capture_service.estimate_confidence(item["transcript"])
                        if kind == "image"
                        else None
                    ),
                )
                db.add(resource)
                await db.flush()
                if kind == "image":
                    # Keep the figure attached — the image stays referenced.
                    db.add(
                        ResourceFile(
                            resource_id=resource.id,
                            file_url=item["url"],
                            file_name=item.get("filename"),
                            file_order=0,
                            ocr_provider="gpt-vision",
                        )
                    )
                created.append((resource, item))

            await db.commit()

            # ── 5. Hand off to the normal pipeline + tell the room ────────────
            structure: dict[str, dict] = {}
            for resource, item in created:
                await redis_client.enqueue_job(
                    "chunking",
                    {"resource_id": str(resource.id), "text": resource.content},
                )
                topic_id = str(resource.topic_id)
                entry = structure.setdefault(topic_id, {"topic_id": topic_id, "resources": []})
                entry["resources"].append(
                    {
                        "resource_id": str(resource.id),
                        "title": resource.title,
                        "needs_review": capture_service.needs_review(resource.ocr_confidence),
                    }
                )
                await cache.delete_pattern(f"notesos:v1:resources:topic:{topic_id}:")
            await cache.delete(topics_list_key(course_id))

            # Attach topic titles for the client.
            topic_ids = [uuid.UUID(tid) for tid in structure]
            if topic_ids:
                titles_res = await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))
                for topic in titles_res.scalars().all():
                    structure[str(topic.id)]["title"] = topic.title

            await _broadcast(
                course_id,
                {
                    "type": "capture_complete",
                    "batch_id": batch_id,
                    "topics": list(structure.values()),
                    "failed": failed,
                },
            )
            print(f"[CAPTURE WORKER] ✅ Batch {batch_id}: filed {len(created)} file(s) "
                  f"into {len(structure)} topic(s), {len(failed)} failed")

        except Exception:
            await db.rollback()
            await _broadcast(
                course_id,
                {"type": "capture_failed", "batch_id": batch_id, "failed": failed},
            )
            raise  # let run_worker_loop retry / dead-letter


async def capture_worker() -> None:
    """Drain the capture queue via the shared reliable worker loop."""
    await run_worker_loop("capture", process_capture_job)


if __name__ == "__main__":
    asyncio.run(capture_worker())
