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
from app.models.test import TestAnswer, TestAttempt, AnswerStatus
from app.services.redis_client import redis_client
from app.services.transcription import transcription_service
from app.services.grader import grader


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
        print("[GRADING WORKER] Missing answer_id in job data")
        return

    print(f"[GRADING WORKER] Processing grading job for answer {answer_id}")

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
                print(f"[GRADING WORKER] Answer {answer_id} not found")
                return

            question = answer.question
            student_answer_text = answer.answer_text or ""

            # 1. If voice answer, transcribe first
            if is_voice and answer.answer_audio_url:
                print(f"[GRADING WORKER] Transcribing audio for answer {answer_id}")
                transcription_result = await transcription_service.transcribe_audio(
                    answer.answer_audio_url
                )
                student_answer_text = transcription_result["text"]
                answer.transcription = student_answer_text
                print(f"[GRADING WORKER] Transcription: {student_answer_text[:100]}...")

            # 2. Grade the answer
            print(f"[GRADING WORKER] Grading answer {answer_id}")
            grading_result = await grader.grade_answer(
                question=question.question_text,
                expected_answer=question.correct_answer or "",
                student_answer=student_answer_text,
                is_voice=is_voice,
            )

            # 3. Save grading results
            answer.score = grading_result["score"]
            answer.ai_feedback = grading_result["feedback"]
            answer.encouragement = grading_result["encouragement"]
            answer.key_points_covered = grading_result.get("key_points_covered") or []
            answer.key_points_missed = grading_result.get("key_points_missed") or []

            # Derive answer status from normalized score (score is 0–10)
            normalized = float(grading_result["score"]) / 10.0
            if normalized >= 0.85:
                answer.status = AnswerStatus.CORRECT
            elif normalized >= 0.5:
                answer.status = AnswerStatus.PARTIAL
            else:
                answer.status = AnswerStatus.NEEDS_REVIEW

            await db.commit()

            print(f"[GRADING WORKER] Score: {grading_result['score']}/100")
            print(f"[GRADING WORKER] Encouragement: {grading_result['encouragement']}")

            # 4. Update test attempt total score; returns True if all answers are now graded
            all_done = False
            if answer.attempt:
                all_done = await _update_attempt_score(db, answer.attempt_id)

            # 5. Only broadcast + notify once the WHOLE test is graded (not per-answer)
            if all_done and answer.attempt:
                attempt = answer.attempt
                course_id = None
                if hasattr(attempt, "test") and attempt.test:
                    course_id = str(attempt.test.course_id)

                if course_id:
                    score_pct = round(
                        float(attempt.total_score or 0) / max(attempt.max_score, 1) * 100
                    )
                    await redis_client.publish(
                        channel="course_updates",
                        message={
                            "course_id": course_id,
                            "message": {
                                "type": "grading:complete",
                                "data": {
                                    "attempt_id": str(answer.attempt_id),
                                    "score_pct": score_pct,
                                },
                            },
                        },
                    )

                # Create TEST_GRADED notification once for this user
                try:
                    from app.services.notifications import create_and_push_notification
                    from app.models.notification import NotificationType

                    score_pct = round(
                        float(attempt.total_score or 0) / max(attempt.max_score, 1) * 100
                    )
                    await create_and_push_notification(
                        db=db,
                        user_id=attempt.user_id,
                        notif_type=NotificationType.TEST_GRADED,
                        title="Your test has been graded",
                        body=f"You scored {score_pct}% on your test.",
                        meta_data={
                            "attempt_id": str(answer.attempt_id),
                            "course_id": course_id,
                        },
                    )
                except Exception as notif_err:
                    print(f"[GRADING WORKER] Notification error: {notif_err}")

        except Exception as e:
            print(f"[GRADING WORKER] Error processing job: {e}")
            import traceback

            traceback.print_exc()
            await db.rollback()


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
        if not attempt.completed_at and all_graded:
            attempt.completed_at = datetime.utcnow()
        await db.commit()

        print(
            f"[GRADING WORKER] Updated attempt {attempt_id} total score: {total_score}"
        )

    return bool(all_graded and attempt and attempt.completed_at)


async def start_grading_worker():
    """Start the grading worker to process jobs from Redis."""
    print("[GRADING WORKER] Starting grading worker...")

    while True:
        try:
            # Dequeue job from Redis
            job_data = await redis_client.dequeue_job("voice_grade")

            if job_data:
                await process_grading_job(job_data)
            else:
                # No jobs available, wait before polling again
                await asyncio.sleep(1)

        except Exception as e:
            print(f"[GRADING WORKER] Worker error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    """Run the worker."""
    asyncio.run(start_grading_worker())
