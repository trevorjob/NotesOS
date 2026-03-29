"""
NotesOS - Chunking Worker
Background worker to chunk resources and generate embeddings.
"""

import asyncio
import json
from sqlalchemy import select
from app.database import async_session_maker

from app.models.resource import Resource
from app.services.redis_client import redis_client
from app.services.chunking import chunking_service
from app.services.embeddings import embedding_service
from app.services.vector_store import vector_store
from app.services.websocket import broadcast_processing_status
from app.models.course import Topic
from app.config import settings

# Use the centralized async engine and session maker
AsyncSessionLocal = async_session_maker


async def process_chunking_job(job_data: dict):
    """
    Process a chunking job: chunk text and generate embeddings.

    Job data:
        - resource_id: ID of resource to process
        - text: Text content to chunk
    """
    resource_id = job_data.get("resource_id") or job_data.get(
        "note_id"
    )  # backward compat
    text = job_data["text"]
    course_id = None

    async with AsyncSessionLocal() as db:
        try:
            # Fetch resource
            resource_query = select(Resource).where(Resource.id == resource_id)
            result = await db.execute(resource_query)
            resource = result.scalar_one_or_none()

            if not resource:
                print(f"Resource {resource_id} not found")
                return

            # Get course_id for WebSocket broadcast
            topic_query = select(Topic).where(Topic.id == resource.topic_id)
            topic_result = await db.execute(topic_query)
            topic = topic_result.scalar_one_or_none()
            course_id = str(topic.course_id) if topic else None

            # Broadcast processing started
            if course_id:
                await broadcast_processing_status(course_id, resource_id, "processing")

            # Step 1: Chunk the text
            chunks = chunking_service.chunk_text(text, resource_id=resource_id)

            if not chunks:
                print(f"No chunks generated for resource {resource_id}")
                resource.is_processed = True
                await db.commit()
                return

            # Step 2: Generate embeddings for all chunks (batch)
            chunk_texts = [chunk["chunk_text"] for chunk in chunks]
            embeddings = await embedding_service.generate_embeddings_batch(
                texts=chunk_texts, input_type="document"
            )

            # Step 3: Store in vector database
            chunks_inserted = await vector_store.insert_chunks(
                db=db, resource_id=resource_id, chunks=chunks, embeddings=embeddings
            )

            # Step 4: Mark resource as processed
            resource.is_processed = True
            await db.commit()

            print(
                f"✅ Processed resource {resource_id}: {chunks_inserted} chunks indexed"
            )

            # Broadcast completion
            if course_id:
                await broadcast_processing_status(course_id, resource_id, "completed")

            # Step 5: Enqueue knowledge synthesis for this topic
            if resource.topic_id and settings.ENABLE_KNOWLEDGE_SYNTHESIS:
                await redis_client.enqueue_job(
                    "knowledge",
                    {
                        "topic_id": str(resource.topic_id),
                        "course_id": course_id,
                    },
                )

        except Exception as e:
            print(f"❌ Error processing resource {resource_id}: {str(e)}")

            # Broadcast failure
            if course_id:
                await broadcast_processing_status(course_id, resource_id, "failed")

            # Mark as failed (keep is_processed=False for retry)
            try:
                resource_query = select(Resource).where(Resource.id == resource_id)
                result = await db.execute(resource_query)
                resource = result.scalar_one_or_none()
                if resource:
                    resource.is_processed = False
                    await db.commit()
            except Exception:
                pass


async def chunking_worker():
    """
    Main worker loop for chunking queue.
    Uses reliable BRPOPLPUSH so jobs survive worker restarts.
    """
    print("🚀 Chunking worker started")

    recovered = await redis_client.recover_orphaned_jobs("chunking")
    if recovered:
        print(f"🔄 Chunking worker recovered {recovered} orphaned job(s)")

    while True:
        job_json = None
        try:
            job_json = await redis_client.reliable_dequeue("chunking", timeout=5)

            if job_json:
                job = json.loads(job_json)

                job_id = job["id"]
                job_data = job["data"]

                print(f"📝 Processing chunking job {job_id}")

                await redis_client.update_job_status(job_id, "processing")
                await process_chunking_job(job_data)

                resource_id = job_data.get("resource_id") or job_data.get("note_id")
                await redis_client.update_job_status(
                    job_id, "completed", result={"resource_id": resource_id}
                )
                await redis_client.ack_job("chunking", job_json)

        except asyncio.CancelledError:
            print("Chunking worker shutting down")
            break
        except Exception as e:
            print(f"Worker error: {str(e)}")
            if job_json:
                await redis_client.ack_job("chunking", job_json)
            await asyncio.sleep(1)


if __name__ == "__main__":
    """Run the worker."""
    asyncio.run(chunking_worker())
