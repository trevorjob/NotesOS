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
from app.models.course import Topic
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

    lesson_id = None
    lesson_voice = "alloy"
    topic_name = ""
    error = None

    # Phase 1: fetch knowledge and create lesson record — short-lived session
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TopicKnowledge).where(TopicKnowledge.id == knowledge_id)
            )
            knowledge = result.scalar_one_or_none()

            if not knowledge or knowledge.status != KnowledgeStatus.COMPLETED:
                print(f"[AUDIO] Skipping: knowledge {knowledge_id} not ready")
                return

            topic_result = await db.execute(
                select(Topic).where(Topic.id == topic_id)
            )
            topic_obj = topic_result.scalar_one_or_none()
            topic_name = topic_obj.title if topic_obj else ""

            lesson = AudioLesson(
                topic_id=topic_id,
                knowledge_id=knowledge_id,
                status=KnowledgeStatus.PROCESSING,
            )
            db.add(lesson)
            await db.commit()
            await db.refresh(lesson)
            lesson_id = lesson.id
            lesson_voice = lesson.voice
            knowledge_content = knowledge  # still in-memory after session closes

    except Exception as e:
        print(f"❌ Audio worker error (setup) for topic {topic_id}: {e}")
        return

    # Phase 2: heavy external work — no DB session held open
    script = None
    audio_url = None
    duration = None
    try:
        script = await audio_generator.generate_script(knowledge_content, topic_name=topic_name)
        audio_bytes = await audio_generator.generate_audio(script, voice=lesson_voice)
        audio_url, duration = await audio_generator.upload_audio(audio_bytes, topic_id)
    except Exception as e:
        error = e
        print(f"❌ Audio worker error (generation) for topic {topic_id}: {e}")

    # Phase 3: persist result — fresh session
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AudioLesson).where(AudioLesson.id == lesson_id)
            )
            lesson = result.scalar_one_or_none()
            if not lesson:
                return

            if error:
                lesson.status = KnowledgeStatus.FAILED
                lesson.error_message = str(error)
            else:
                lesson.script = script
                lesson.audio_url = audio_url
                lesson.duration_seconds = duration
                lesson.status = KnowledgeStatus.COMPLETED
                lesson.generated_at = datetime.utcnow()

            await db.commit()

    except Exception as e:
        print(f"❌ Audio worker error (save) for topic {topic_id}: {e}")

    if error:
        if course_id:
            await connection_manager.broadcast_to_course(
                course_id,
                {"type": "audio_status", "topic_id": topic_id, "status": "failed"},
            )
        return

    print(f"✅ Audio lesson generated for topic {topic_id} ({duration}s)")

    if course_id:
        await connection_manager.broadcast_to_course(
            course_id,
            {
                "type": "audio_ready",
                "topic_id": topic_id,
                "audio_lesson_id": str(lesson_id),
                "audio_url": audio_url,
                "duration_seconds": duration,
            },
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
