"""
NotesOS - Knowledge Worker
Polls the knowledge queue and synthesizes topic resources into
a TopicKnowledge record, then enqueues an audio generation job.
"""

import asyncio
import uuid

from sqlalchemy import select

from app.database import async_session_maker
from app.models.course import CourseEnrollment, Topic
from app.services.retrieval.concepts import sync_concepts
from app.models.notification import NotificationType
from app.services.cache import cache, topic_key
from app.services.knowledge_synthesizer import knowledge_synthesizer
from app.services.notifications import create_and_push_notification
from app.services.merge_gate import apply_merge_gate
from app.services.redis_client import redis_client
from app.services.websocket import connection_manager
from app.workers.base import run_worker_loop

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

            # Merge Agent gate: quarantine wildly off-topic uploads before synthesis so
            # they never reach the shared note. Non-fatal — a gate error must not block
            # synthesis. Invalidate the resource list so quarantine state is visible.
            try:
                gate_summary = await apply_merge_gate(db, topic_id)
                await db.commit()
                if gate_summary["quarantined"] or gate_summary["released"]:
                    await cache.delete_pattern(
                        f"notesos:v1:resources:topic:{topic_id}:"
                    )
            except Exception as gate_err:
                await db.rollback()
                print(f"⚠️ Merge gate failed for topic {topic_id}: {gate_err}")

            knowledge = await knowledge_synthesizer.synthesize(topic_id, db)

            if knowledge.status.value == "completed":
                print(f"✅ Knowledge synthesized for topic {topic_id}")

                # Invalidate topic cache so next GET reflects new knowledge_status
                await cache.delete(topic_key(topic_id))

                # Elevate synthesized concepts into first-class Concept rows so the
                # retrieval engine can schedule and track them. Non-fatal — a failure
                # here must not fail the synthesis that already succeeded.
                try:
                    concept_course_id = course_id
                    if concept_course_id is None:
                        topic_row = await db.scalar(
                            select(Topic).where(Topic.id == knowledge.topic_id)
                        )
                        concept_course_id = str(topic_row.course_id) if topic_row else None
                    if concept_course_id:
                        await sync_concepts(
                            db,
                            topic_id=knowledge.topic_id,
                            course_id=uuid.UUID(str(concept_course_id)),
                            concepts=knowledge.concepts,
                        )
                        await db.commit()
                except Exception as concept_err:
                    print(f"⚠️ Concept extraction failed for topic {topic_id}: {concept_err}")

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

                # Notify all enrolled users in the course
                if course_id:
                    try:
                        # Get topic title for the notification body
                        topic_result = await db.execute(
                            select(Topic).where(Topic.id == topic_id)
                        )
                        topic_obj = topic_result.scalar_one_or_none()
                        topic_title = topic_obj.title if topic_obj else "your topic"

                        # Get all enrolled users
                        enrollment_result = await db.execute(
                            select(CourseEnrollment).where(CourseEnrollment.course_id == course_id)
                        )
                        enrollments = enrollment_result.scalars().all()
                        for enrollment in enrollments:
                            await create_and_push_notification(
                                db=db,
                                user_id=enrollment.user_id,
                                notif_type=NotificationType.AI_SUMMARY_READY,
                                title="Learning materials ready",
                                body=f'Notes and key concepts for "{topic_title}" are ready.',
                                meta_data={"topic_id": topic_id, "course_id": course_id},
                            )
                    except Exception as notif_err:
                        print(f"[knowledge_worker] Failed to send notifications: {notif_err}")

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
    """Drain the knowledge queue via the shared reliable worker loop."""
    await run_worker_loop("knowledge", process_knowledge_job)


if __name__ == "__main__":
    asyncio.run(knowledge_worker())
