"""
NotesOS - Audio Worker
Polls the audio queue, generates a spoken script from TopicKnowledge (or a single
concept within it), calls OpenAI TTS to produce MP3, and uploads it to Cloudinary.

Two job shapes land on the same queue (docs/listen-audio-plan.md):
  - Legacy/global: {knowledge_id, topic_id, course_id} — enqueued by knowledge_worker
    after synthesis. Creates the shared global (owner=None), default-lens artifact.
  - Personal/lens request: {artifact_id, course_id} — enqueued by POST /audio/request.
    The row already exists (PENDING); this just generates and fills it in.
Both converge on the same generation + save path once an artifact row exists.
"""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.course import Topic
from app.models.knowledge import AudioArtifact, AudioLens, AudioScopeType, KnowledgeStatus, TopicKnowledge
from app.models.retrieval import Concept
from app.services.audio_generator import audio_generator
from app.services.redis_client import redis_client
from app.services.retrieval.remediation import recent_wrong_answers
from app.services.retrieval.subject_profiles import is_audio_suitable
from app.services.websocket import connection_manager
from app.core.logging import get_logger
from app.workers.base import run_worker_loop

logger = get_logger(__name__)

AsyncSessionLocal = async_session_maker


async def _create_global_default(job_data: dict):
    """Legacy job shape: create the global, topic-scoped, default-lens artifact and
    return its id — or None if the topic's knowledge isn't ready to narrate yet."""
    knowledge_id = job_data["knowledge_id"]
    topic_id = job_data["topic_id"]

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(TopicKnowledge).where(TopicKnowledge.id == knowledge_id))
            knowledge = result.scalar_one_or_none()
            if not knowledge or knowledge.status != KnowledgeStatus.COMPLETED:
                logger.warning("Skipping audio job: knowledge not ready", extra={"knowledge_id": str(knowledge_id)})
                return None

            topic_result = await db.execute(select(Topic).where(Topic.id == topic_id))
            topic = topic_result.scalar_one_or_none()
            if topic and not is_audio_suitable(topic.subject_family):
                logger.info(
                    "Skipping global audio: family unsuited to plain narration",
                    extra={"topic_id": str(topic_id), "subject_family": topic.subject_family.value},
                )
                return None

            artifact = AudioArtifact(
                scope_type=AudioScopeType.TOPIC,
                scope_ref=topic_id,
                knowledge_id=knowledge_id,
                lens=AudioLens.DEFAULT,
                owner_id=None,
                status=KnowledgeStatus.PROCESSING,
            )
            db.add(artifact)
            await db.commit()
            await db.refresh(artifact)
            return artifact.id
    except Exception:
        logger.error("Audio worker setup failed", exc_info=True, extra={"topic_id": str(topic_id)})
        return None


async def _mark_processing(artifact_id: str):
    """Personal/lens request: the row already exists (PENDING) — flip it to PROCESSING."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AudioArtifact).where(AudioArtifact.id == artifact_id))
            artifact = result.scalar_one_or_none()
            if not artifact:
                logger.warning("Skipping audio job: artifact not found", extra={"artifact_id": str(artifact_id)})
                return None
            artifact.status = KnowledgeStatus.PROCESSING
            await db.commit()
            return artifact.id
    except Exception:
        logger.error("Audio worker setup failed", exc_info=True, extra={"artifact_id": str(artifact_id)})
        return None


async def _load_generation_context(db: AsyncSession, artifact: AudioArtifact):
    """Resolve (knowledge, topic_name, concept_focus) for an artifact's scope.

    Concept-scoped requests narrow the lesson to one concept (§3) but still draw on
    the concept's own topic knowledge for surrounding context.
    """
    concept_focus = None
    if artifact.scope_type == AudioScopeType.CONCEPT:
        result = await db.execute(select(Concept).where(Concept.id == artifact.scope_ref))
        concept = result.scalar_one_or_none()
        if not concept:
            return None, "", None
        topic_id = concept.topic_id
        concept_focus = {"term": concept.text, "definition": concept.definition}
    else:
        topic_id = artifact.scope_ref

    topic_result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = topic_result.scalar_one_or_none()

    knowledge = None
    if artifact.knowledge_id:
        knowledge_result = await db.execute(select(TopicKnowledge).where(TopicKnowledge.id == artifact.knowledge_id))
        knowledge = knowledge_result.scalar_one_or_none()

    return knowledge, (topic.title if topic else ""), concept_focus


async def _generate_and_save(artifact_id, course_id):
    # Setup: load the artifact + resolve its scope's generation context — short session
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AudioArtifact).where(AudioArtifact.id == artifact_id))
            artifact = result.scalar_one_or_none()
            if not artifact:
                return

            knowledge, topic_name, concept_focus = await _load_generation_context(db, artifact)
            if not knowledge or knowledge.status != KnowledgeStatus.COMPLETED:
                logger.warning("Skipping audio job: knowledge not ready", extra={"artifact_id": str(artifact_id)})
                return

            wrong_answers = None
            if artifact.lens == AudioLens.REMEDIATION and artifact.scope_type == AudioScopeType.CONCEPT:
                wrong_answers = await recent_wrong_answers(
                    db, user_id=artifact.owner_id, concept_id=artifact.scope_ref
                )

            artifact_voice = artifact.voice
            artifact_lens = artifact.lens
            artifact_instruction = artifact.instruction
            scope_type = artifact.scope_type
            scope_ref = artifact.scope_ref
            knowledge_content = knowledge  # still in-memory after session closes
    except Exception:
        logger.error("Audio worker context load failed", exc_info=True, extra={"artifact_id": str(artifact_id)})
        return

    # Heavy external work — no DB session held open
    script = None
    audio_url = None
    duration = None
    error = None
    try:
        script = await audio_generator.generate_script(
            knowledge_content,
            topic_name=topic_name,
            lens=artifact_lens,
            concept_focus=concept_focus,
            instruction=artifact_instruction,
            wrong_answers=wrong_answers,
        )
        audio_bytes = await audio_generator.generate_audio(script, voice=artifact_voice)
        audio_url, duration = await audio_generator.upload_audio(audio_bytes, str(artifact_id))
    except Exception as e:
        error = e
        logger.error("Audio generation failed", exc_info=True, extra={"artifact_id": str(artifact_id)})

    # Persist result — fresh session
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AudioArtifact).where(AudioArtifact.id == artifact_id))
            artifact = result.scalar_one_or_none()
            if not artifact:
                return

            if error:
                artifact.status = KnowledgeStatus.FAILED
                artifact.error_message = str(error)
            else:
                artifact.script = script
                artifact.audio_url = audio_url
                artifact.duration_seconds = duration
                artifact.status = KnowledgeStatus.COMPLETED
                artifact.generated_at = datetime.utcnow()

            await db.commit()
    except Exception:
        logger.error("Audio worker save failed", exc_info=True, extra={"artifact_id": str(artifact_id)})

    # The topic room to broadcast to — only meaningful for topic-scoped artifacts today.
    topic_id = str(scope_ref) if scope_type == AudioScopeType.TOPIC else None

    if error:
        if course_id and topic_id:
            await connection_manager.broadcast_to_course(
                course_id,
                {"type": "audio_status", "topic_id": topic_id, "status": "failed"},
            )
        return

    logger.info("Audio artifact generated", extra={"artifact_id": str(artifact_id), "duration_seconds": duration})

    if course_id and topic_id:
        await connection_manager.broadcast_to_course(
            course_id,
            {
                "type": "audio_ready",
                "topic_id": topic_id,
                "audio_artifact_id": str(artifact_id),
                "audio_url": audio_url,
                "duration_seconds": duration,
            },
        )


async def process_audio_job(job_data: dict):
    """
    Generate audio for an artifact.

    Job data (one of):
        artifact_id                       - an existing AudioArtifact (personal/lens
                                             requests, already PENDING)
        knowledge_id, topic_id, course_id - creates the global default artifact, then
                                             generates it (legacy shape)
    """
    course_id = job_data.get("course_id")

    if "artifact_id" in job_data:
        artifact_id = await _mark_processing(job_data["artifact_id"])
    else:
        artifact_id = await _create_global_default(job_data)

    if artifact_id is None:
        return

    await _generate_and_save(artifact_id, course_id)


async def audio_worker():
    """Drain the audio queue via the shared reliable worker loop."""
    await run_worker_loop("audio", process_audio_job)


if __name__ == "__main__":
    asyncio.run(audio_worker())
