"""
NotesOS - Knowledge Worker
Polls the knowledge queue and synthesizes topic resources into
a TopicKnowledge record, then enqueues an audio generation job.
"""

import asyncio
import json

from app.database import async_session_maker
from app.services.cache import cache, topic_key
from app.services.knowledge_synthesizer import knowledge_synthesizer
from app.services.redis_client import redis_client
from app.services.websocket import connection_manager

AsyncSessionLocal = async_session_maker


async def process_knowledge_job(job_data: dict):
    """
    Synthesize topic knowledge from all its resource chunks.

    Job data:
        topic_id  - UUID of the topic to synthesize
        course_id - UUID of the course (for WebSocket broadcast)
    """
    topic_id = job_data["topic_id"]
    course_id = job_data.get("course_id")

    async with AsyncSessionLocal() as db:
        try:
            # Broadcast: synthesis started
            if course_id:
                await connection_manager.broadcast_to_course(
                    course_id,
                    {"type": "knowledge_status", "topic_id": topic_id, "status": "processing"},
                )

            knowledge = await knowledge_synthesizer.synthesize(topic_id, db)

            if knowledge.status.value == "completed":
                print(f"✅ Knowledge synthesized for topic {topic_id}")

                # Invalidate topic cache so next GET reflects new knowledge_status
                await cache.delete(topic_key(topic_id))

                # Broadcast: knowledge ready
                if course_id:
                    await connection_manager.broadcast_to_course(
                        course_id,
                        {
                            "type": "knowledge_updated",
                            "topic_id": topic_id,
                            "knowledge_id": str(knowledge.id),
                        },
                    )

                # Enqueue audio generation
                await redis_client.enqueue_job(
                    "audio",
                    {
                        "knowledge_id": str(knowledge.id),
                        "topic_id": topic_id,
                        "course_id": course_id,
                    },
                )
            else:
                print(f"❌ Knowledge synthesis failed for topic {topic_id}: {knowledge.error_message}")
                if course_id:
                    await connection_manager.broadcast_to_course(
                        course_id,
                        {"type": "knowledge_status", "topic_id": topic_id, "status": "failed"},
                    )

        except Exception as e:
            print(f"❌ Knowledge worker error for topic {topic_id}: {e}")
            if course_id:
                await connection_manager.broadcast_to_course(
                    course_id,
                    {"type": "knowledge_status", "topic_id": topic_id, "status": "failed"},
                )


async def knowledge_worker():
    """
    Main worker loop. Polls Redis queue:knowledge and processes jobs.
    """
    print("🚀 Knowledge worker started")

    client = await redis_client.get_client()

    while True:
        try:
            result = await client.brpop("queue:knowledge", timeout=5)

            if result:
                _, job_json = result
                job = json.loads(job_json)

                job_id = job["id"]
                job_data = job["data"]

                print(f"🧠 Processing knowledge job {job_id} for topic {job_data.get('topic_id')}")

                await redis_client.update_job_status(job_id, "processing")
                await process_knowledge_job(job_data)
                await redis_client.update_job_status(
                    job_id, "completed", result={"topic_id": job_data.get("topic_id")}
                )

        except asyncio.CancelledError:
            print("Knowledge worker shutting down")
            break
        except Exception as e:
            print(f"Knowledge worker error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(knowledge_worker())
