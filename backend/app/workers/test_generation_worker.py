"""
NotesOS - Test Generation Worker
Background worker that runs LangGraph question generation and streams
batch-ready events to the requesting user via WebSocket.
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import select, delete

from app.database import worker_session
from app.models.test import Test, TestQuestion, TestGenerationStatus, QuestionType
from app.services.redis_client import redis_client
from app.services.question_generator import question_generator
from app.core.logging import get_logger
from app.workers.base import run_worker_loop

logger = get_logger(__name__)


async def _emit(user_id: str, event_type: str, data: dict) -> None:
    """Publish a user-scoped WebSocket event."""
    await redis_client.publish("user_notifications", {
        "user_id": user_id,
        "raw": True,
        "notification": {"type": event_type, "data": data},
    })


async def process_test_generation_job(job_data: dict) -> None:
    test_id_str = job_data["test_id"]
    user_id = job_data["user_id"]
    test_uuid = uuid.UUID(test_id_str)

    async with worker_session() as db:
        result = await db.execute(select(Test).where(Test.id == test_uuid))
        test = result.scalar_one_or_none()

        if not test:
            logger.warning("Test not found, skipping", extra={"test_id": test_id_str})
            return

        # Idempotency: if already ready, nothing to do
        if test.generation_status == TestGenerationStatus.READY:
            logger.info("Test already ready, skipping", extra={"test_id": test_id_str})
            return

        # Risk 3: if a previous worker crashed mid-generation, wipe partial questions
        if test.generation_status == TestGenerationStatus.GENERATING:
            logger.info("Cleaning up partial questions from crashed run", extra={"test_id": test_id_str})
            await db.execute(delete(TestQuestion).where(TestQuestion.test_id == test_uuid))
            test.batches_done = 0
            await db.commit()

        # Mark as generating
        test.generation_status = TestGenerationStatus.GENERATING
        test.started_at = datetime.utcnow()
        await db.commit()

        await _emit(user_id, "test_generation_status", {
            "test_id": test_id_str,
            "status": "generating",
            "batches_done": 0,
            "batches_total": test.batches_total,
        })

    # Track the batch index sequence for per-batch DB commits.
    # We need a fresh session per batch because worker_session() auto-commits on exit.
    batch_counter = [0]

    async def on_batch_ready(batch_index: int, batches_total: int, questions: List[Dict[str, Any]]) -> None:
        async with worker_session() as db:
            result = await db.execute(select(Test).where(Test.id == test_uuid))
            test = result.scalar_one_or_none()
            if not test:
                return

            # Determine starting order_index for this batch
            from sqlalchemy import func
            count_result = await db.execute(
                select(func.count()).where(TestQuestion.test_id == test_uuid)
            )
            next_index = count_result.scalar() or 0

            for offset, q_data in enumerate(questions):
                db.add(TestQuestion(
                    test_id=test_uuid,
                    question_text=q_data["question_text"],
                    question_type=QuestionType[q_data["question_type"].upper()],
                    correct_answer=q_data.get("correct_answer"),
                    answer_options=q_data.get("answer_options"),
                    points=q_data.get("points", 1),
                    order_index=next_index + offset,
                ))

            test.batches_done = (test.batches_done or 0) + 1
            await db.commit()

        batch_counter[0] += 1

        # Emit batch event with question data for the frontend
        serialised = [
            {
                "question_text": q["question_text"],
                "question_type": q["question_type"],
                "answer_options": q.get("answer_options"),
                "points": q.get("points", 1),
                "order_index": (batch_index * 12) + i,  # approximate; DB is authoritative
            }
            for i, q in enumerate(questions)
        ]
        await _emit(user_id, "test_batch_ready", {
            "test_id": test_id_str,
            "batch_index": batch_counter[0] - 1,
            "batches_total": batches_total,
            "questions": serialised,
        })

    try:
        async with worker_session() as db:
            result = await db.execute(select(Test).where(Test.id == test_uuid))
            test = result.scalar_one_or_none()
            await question_generator.generate_for_test(db, test, on_batch_ready=on_batch_ready)
            test.generation_status = TestGenerationStatus.READY
            await db.commit()

        await _emit(user_id, "test_generation_complete", {
            "test_id": test_id_str,
            "question_count": test.question_count,
        })
        logger.info("Test generation complete", extra={"test_id": test_id_str})

    except Exception:
        logger.error("Test generation failed", exc_info=True, extra={"test_id": test_id_str})

        # Count how many questions made it
        async with worker_session() as db:
            from sqlalchemy import func
            count_result = await db.execute(
                select(func.count()).where(TestQuestion.test_id == test_uuid)
            )
            partial_count = count_result.scalar() or 0

            result = await db.execute(select(Test).where(Test.id == test_uuid))
            test = result.scalar_one_or_none()
            if test:
                test.generation_status = TestGenerationStatus.FAILED
                test.failure_reason = "Generation failed after max retries"
                await db.commit()

        await _emit(user_id, "test_generation_failed", {
            "test_id": test_id_str,
            "reason": "Generation failed after max retries",
            "partial_question_count": partial_count,
        })


async def test_generation_worker() -> None:
    """Drain the test-generation queue via the shared reliable worker loop."""
    await run_worker_loop("test_generation", process_test_generation_job)


if __name__ == "__main__":
    asyncio.run(test_generation_worker())
