"""
NotesOS - Grading Worker
Background worker for async voice answer grading.
"""

import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database import worker_session
from app.models.course import Topic
from app.models.test import TestAnswer, TestAttempt, AnswerStatus
from app.services.redis_client import redis_client
from app.services.transcription import transcription_service
from app.services.grader import grader
from app.core.logging import get_logger
from app.workers.base import run_worker_loop

logger = get_logger(__name__)


async def process_grading_job(job_data: dict):
    """
    Process a voice grading job from Redis queue.

    Job data:
        - answer_id: TestAnswer ID
        - is_voice: True if audio answer
    """
    answer_id = job_data.get("answer_id")
    is_voice = job_data.get("is_voice", False)

    if not answer_id:
        logger.warning("Missing answer_id in grading job")
        return

    logger.info("Processing grading job", extra={"answer_id": answer_id})

    async with worker_session() as db:
        try:
            # Fetch answer with question loaded
            answer_query = (
                select(TestAnswer)
                .options(selectinload(TestAnswer.question))
                .options(
                    selectinload(TestAnswer.attempt).selectinload(TestAttempt.test)
                )
                .where(TestAnswer.id == uuid.UUID(answer_id))
            )
            result = await db.execute(answer_query)
            answer = result.scalar_one_or_none()

            if not answer:
                logger.warning("Answer not found", extra={"answer_id": answer_id})
                return

            # Save scalars before any commit (relationships expire after commit)
            attempt_id = answer.attempt_id
            course_id = str(answer.attempt.test.course_id) if answer.attempt and answer.attempt.test else None
            user_id = answer.attempt.user_id if answer.attempt else None

            question = answer.question
            student_answer_text = answer.answer_text or ""

            # 1. If voice answer, transcribe first
            if is_voice and answer.answer_audio_url:
                logger.info("Transcribing audio", extra={"answer_id": answer_id})
                transcription_result = await transcription_service.transcribe_audio(
                    answer.answer_audio_url
                )
                student_answer_text = transcription_result["text"]
                answer.transcription = student_answer_text
                logger.info("Transcription complete", extra={"answer_id": answer_id, "preview": student_answer_text[:100]})

            # 1b. Skip AI grading for blank/skipped answers — score 0 immediately
            if not student_answer_text.strip():
                answer.score = 0.0
                answer.ai_feedback = "No answer provided."
                answer.encouragement = ""
                answer.key_points_covered = []
                answer.key_points_missed = []
                answer.status = AnswerStatus.NEEDS_REVIEW
                await db.commit()
                all_done = await _update_attempt_score(db, attempt_id)
                logger.info("Blank answer scored 0", extra={"answer_id": answer_id})
                if all_done:
                    await _broadcast_and_notify(db, attempt_id, course_id, user_id)
                return

            # 2. Fetch topic name for grading context
            topic_name = ""
            test_topics = answer.attempt.test.topics if answer.attempt and answer.attempt.test else []
            if test_topics:
                topic_result = await db.execute(
                    select(Topic).where(Topic.id == uuid.UUID(str(test_topics[0])))
                )
                topic_obj = topic_result.scalar_one_or_none()
                topic_name = topic_obj.title if topic_obj else ""

            # 3. Grade the answer
            logger.info("Grading answer", extra={"answer_id": answer_id})
            grading_result = await grader.grade_answer(
                question=question.question_text,
                expected_answer=question.correct_answer or "",
                student_answer=student_answer_text,
                is_voice=is_voice,
                question_type=question.question_type.value,
                topic_name=topic_name,
            )

            # 3. Save grading results (grader returns 0–10, matching MCQ scale)
            answer.score = grading_result["score"]
            answer.ai_feedback = grading_result["feedback"]
            answer.encouragement = grading_result["encouragement"]
            answer.key_points_covered = grading_result.get("key_points_covered") or []
            answer.key_points_missed = grading_result.get("key_points_missed") or []

            # Derive answer status from normalized score (normalize 0–10 → 0–1 for threshold check)
            normalized = float(grading_result["score"]) / 10.0
            if normalized >= 0.85:
                answer.status = AnswerStatus.CORRECT
            elif normalized >= 0.5:
                answer.status = AnswerStatus.PARTIAL
            else:
                answer.status = AnswerStatus.NEEDS_REVIEW

            await db.commit()

            logger.info("Answer graded", extra={"answer_id": answer_id, "score": grading_result["score"]})

            # 4. Update test attempt total score; returns True if all answers are now graded
            all_done = await _update_attempt_score(db, attempt_id)

            # 5. Only broadcast + notify once the WHOLE test is graded (not per-answer)
            if all_done:
                await _broadcast_and_notify(db, attempt_id, course_id, user_id)

        except Exception:
            logger.error("Grading job failed", exc_info=True, extra={"answer_id": answer_id})
            await db.rollback()


async def _broadcast_and_notify(db, attempt_id, course_id, user_id) -> None:
    """Broadcast grading:complete and send notification. Uses fresh DB query — safe after commit."""
    from app.models.test import TestAttempt as _TA
    attempt_result = await db.execute(select(_TA).where(_TA.id == attempt_id))
    attempt = attempt_result.scalar_one_or_none()
    if not attempt:
        return

    score_pct = round(float(attempt.total_score or 0) / max(attempt.max_score, 1) * 100)

    if course_id:
        await redis_client.publish(
            channel="course_updates",
            message={
                "course_id": course_id,
                "message": {
                    "type": "grading:complete",
                    "data": {
                        "attempt_id": str(attempt_id),
                        "score_pct": score_pct,
                    },
                },
            },
        )

    if user_id:
        try:
            from app.services.notifications import create_and_push_notification
            from app.models.notification import NotificationType
            await create_and_push_notification(
                db=db,
                user_id=user_id,
                notif_type=NotificationType.TEST_GRADED,
                title="Your test has been graded",
                body=f"You scored {score_pct}% on your test.",
                meta_data={"attempt_id": str(attempt_id), "course_id": course_id or ""},
            )
        except Exception:
            logger.error("Failed to send grading notification", exc_info=True)


async def _update_attempt_score(db, attempt_id) -> bool:
    """Recalculate and update test attempt total score. Returns True when all answers are graded."""
    # Get all answers for this attempt
    answers_query = select(TestAnswer).where(TestAnswer.attempt_id == attempt_id)
    result = await db.execute(answers_query)
    answers = result.scalars().all()

    # Calculate total score
    total_score = sum(float(ans.score or 0) for ans in answers)
    all_graded = all(ans.score is not None for ans in answers)

    # Update attempt
    attempt_query = select(TestAttempt).where(TestAttempt.id == attempt_id)
    attempt_result = await db.execute(attempt_query)
    attempt = attempt_result.scalar_one_or_none()

    if attempt:
        attempt.total_score = total_score
        now_completed = not attempt.completed_at and all_graded
        if now_completed:
            attempt.completed_at = datetime.utcnow()
        await db.commit()

        logger.info("Attempt score updated", extra={"attempt_id": str(attempt_id), "total_score": total_score})

    return bool(all_graded and attempt and (attempt.completed_at or now_completed))


async def start_grading_worker():
    """Drain the voice-grading queue via the shared reliable worker loop.

    Previously used a plain RPOP with no processing queue, so a crash mid-job
    dropped the work entirely. Now reliable + retried + dead-lettered.
    """
    await run_worker_loop("voice_grade", process_grading_job)


if __name__ == "__main__":
    asyncio.run(start_grading_worker())
