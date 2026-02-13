"""
NotesOS - Grading Worker
Background worker for async voice answer grading.
"""

import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database import get_db
from app.models.test import TestAnswer, TestAttempt
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

    async for db in get_db():
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
            await db.commit()

            print(f"[GRADING WORKER] Score: {grading_result['score']}/100")
            print(f"[GRADING WORKER] Encouragement: {grading_result['encouragement']}")

            # 4. Update test attempt total score
            if answer.attempt:
                await _update_attempt_score(db, answer.attempt_id)

            # 5. Send WebSocket notification via Redis
            if answer.attempt:
                attempt = answer.attempt
                # Get course_id from test
                course_id = None
                if hasattr(attempt, "test") and attempt.test:
                    course_id = str(attempt.test.course_id)

                if course_id:
                    await redis_client.publish(
                        channel="course_updates",
                        message={
                            "course_id": course_id,
                            "message": {
                                "type": "grading:complete",
                                "data": {
                                    "answer_id": answer_id,
                                    "attempt_id": str(answer.attempt_id),
                                    "score": grading_result["score"],
                                    "encouragement": grading_result["encouragement"],
                                },
                            },
                        },
                    )

        except Exception as e:
            print(f"[GRADING WORKER] Error processing job: {e}")
            import traceback

            traceback.print_exc()
            await db.rollback()
        finally:
            break  # Exit async for loop after first iteration


async def _update_attempt_score(db, attempt_id):
    """Recalculate and update test attempt total score."""
    # Get all answers for this attempt
    answers_query = select(TestAnswer).where(TestAnswer.attempt_id == attempt_id)
    result = await db.execute(answers_query)
    answers = result.scalars().all()

    # Calculate total score
    total_score = sum(float(ans.score or 0) for ans in answers)

    # Update attempt
    attempt_query = select(TestAttempt).where(TestAttempt.id == attempt_id)
    attempt_result = await db.execute(attempt_query)
    attempt = attempt_result.scalar_one_or_none()

    if attempt:
        attempt.total_score = total_score
        if not attempt.completed_at and all(ans.score is not None for ans in answers):
            # All answers graded, mark as completed
            attempt.completed_at = datetime.utcnow()
        await db.commit()

        print(
            f"[GRADING WORKER] Updated attempt {attempt_id} total score: {total_score}"
        )


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
