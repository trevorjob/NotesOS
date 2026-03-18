"""
NotesOS - Audio Worker
Polls the audio queue, generates a spoken script from TopicKnowledge,
calls OpenAI TTS to produce MP3, and uploads it to Cloudinary.
"""

import asyncio
import json
from datetime import datetime

from sqlalchemy import select

from app.database import async_session_maker
from app.models.knowledge import AudioLesson, KnowledgeStatus, TopicKnowledge
from app.services.audio_generator import audio_generator
from app.services.redis_client import redis_client
from app.services.websocket import connection_manager

AsyncSessionLocal = async_session_maker


async def process_audio_job(job_data: dict):
    """
    Generate audio lesson for a topic.

    Job data:
        knowledge_id - UUID of the TopicKnowledge to generate audio from
        topic_id     - UUID of the topic
        course_id    - UUID of the course (for WebSocket broadcast)
    """
    knowledge_id = job_data["knowledge_id"]
    topic_id = job_data["topic_id"]
    course_id = job_data.get("course_id")

    async with AsyncSessionLocal() as db:
        lesson = None
        try:
            # Fetch knowledge record
            result = await db.execute(
                select(TopicKnowledge).where(TopicKnowledge.id == knowledge_id)
            )
            knowledge = result.scalar_one_or_none()

            if not knowledge or knowledge.status != KnowledgeStatus.COMPLETED:
                print(f"[AUDIO] Skipping: knowledge {knowledge_id} not ready")
                return

            # Create AudioLesson record in processing state
            lesson = AudioLesson(
                topic_id=topic_id,
                knowledge_id=knowledge_id,
                status=KnowledgeStatus.PROCESSING,
            )
            db.add(lesson)
            await db.commit()
            await db.refresh(lesson)

            # Step 1: Generate script
            script = await audio_generator.generate_script(knowledge)
            lesson.script = script

            # Step 2: Generate MP3 via OpenAI TTS
            audio_bytes = await audio_generator.generate_audio(script, voice=lesson.voice)

            # Step 3: Upload to Cloudinary
            audio_url, duration = await audio_generator.upload_audio(audio_bytes, topic_id)

            # Step 4: Persist result
            lesson.audio_url = audio_url
            lesson.duration_seconds = duration
            lesson.status = KnowledgeStatus.COMPLETED
            lesson.generated_at = datetime.utcnow()
            await db.commit()

            print(f"✅ Audio lesson generated for topic {topic_id} ({duration}s)")

            # Broadcast: audio ready
            if course_id:
                await connection_manager.broadcast_to_course(
                    course_id,
                    {
                        "type": "audio_ready",
                        "topic_id": topic_id,
                        "audio_lesson_id": str(lesson.id),
                        "audio_url": audio_url,
                        "duration_seconds": duration,
                    },
                )

        except Exception as e:
            print(f"❌ Audio worker error for topic {topic_id}: {e}")

            if lesson is not None:
                try:
                    lesson.status = KnowledgeStatus.FAILED
                    lesson.error_message = str(e)
                    await db.commit()
                except Exception:
                    pass

            if course_id:
                await connection_manager.broadcast_to_course(
                    course_id,
                    {"type": "audio_status", "topic_id": topic_id, "status": "failed"},
                )


async def audio_worker():
    """
    Main worker loop. Polls Redis queue:audio and processes jobs.
    """
    print("🚀 Audio worker started")

    client = await redis_client.get_client()

    while True:
        try:
            result = await client.brpop("queue:audio", timeout=5)

            if result:
                _, job_json = result
                job = json.loads(job_json)

                job_id = job["id"]
                job_data = job["data"]

                print(f"🎧 Processing audio job {job_id} for topic {job_data.get('topic_id')}")

                await redis_client.update_job_status(job_id, "processing")
                await process_audio_job(job_data)
                await redis_client.update_job_status(
                    job_id, "completed", result={"topic_id": job_data.get("topic_id")}
                )

        except asyncio.CancelledError:
            print("Audio worker shutting down")
            break
        except Exception as e:
            print(f"Audio worker error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(audio_worker())
