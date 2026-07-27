"""
NotesOS — Practice-test generation worker (B14).

Builds an authored, shareable question set **on the retrieval atom**. The builder
endpoint persisted the ``PracticeTest`` shell (status=generating) and enqueued a job;
this worker fills in the frozen, concept-anchored questions and flips the status.

It is the "bounded, concept-anchored pre-gen" §2a's retire-note points at — **not** the
retired v1 ``test_generation`` worker (which bypassed the engine and graded through the
dead path). Here every question is one ``mode.generate`` over one concept, and *taking*
the test later records per-concept attempts through ``engine.record_attempt`` — the same
review-loop path. Cost==speed (build-guide §5) actively favours pre-generating a shared,
reused test.

Job shape: ``{"test_id": str}``.
"""

import asyncio
import uuid

from sqlalchemy import delete, select

from app.database import worker_session
from app.models.practice_test import (
    GEN_FAILED,
    GEN_READY,
    PracticeTest,
    PracticeTestQuestion,
)
from app.services.redis_client import redis_client
from app.services.retrieval import engine, registry
from app.services.retrieval.modes import ModeContext
from app.workers.base import run_worker_loop


async def _broadcast(course_id: str, message: dict) -> None:
    await redis_client.publish(
        channel="course_updates",
        message={"course_id": course_id, "message": message},
    )


async def _select_concepts(db, test: PracticeTest):
    """The concept pool for the test — its chosen scope (multi-topic or whole course)."""
    topic_ids = [uuid.UUID(t) for t in (test.scope_topic_ids or [])]
    if topic_ids:
        return await engine.select_concepts(
            db,
            user_id=test.created_by,
            scope=engine.SCOPE_TOPIC,
            topic_ids=topic_ids,
            limit=test.question_count,
        )
    return await engine.select_concepts(
        db,
        user_id=test.created_by,
        scope=engine.SCOPE_COURSE,
        course_id=test.course_id,
        limit=test.question_count,
    )


async def process_practice_test_job(job_data: dict) -> None:
    test_id = job_data.get("test_id", "")
    if not test_id:
        print(f"[PRACTICE TEST WORKER] Invalid job data: {job_data}")
        return

    async with worker_session() as db:
        test = await db.get(PracticeTest, uuid.UUID(test_id))
        if test is None:
            print(f"[PRACTICE TEST WORKER] test {test_id} gone")
            return
        course_id = str(test.course_id)

        try:
            # Fresh rebuild on retry: clear any partial questions from a prior attempt.
            await db.execute(
                delete(PracticeTestQuestion).where(PracticeTestQuestion.test_id == test.id)
            )
            test.questions_done = 0
            await db.flush()

            concepts = await _select_concepts(db, test)
            if not concepts:
                test.generation_status = GEN_FAILED
                test.failure_reason = "no concepts in the selected scope yet"
                await db.commit()
                await _broadcast(
                    course_id,
                    {"type": "practice_test_failed", "test_id": test_id,
                     "reason": test.failure_reason},
                )
                return

            mode = registry.get_mode(test.mode)
            # Deliberately NOT passing a grading directive: authored tests use the plain
            # question path (mcq/short/essay), never the STEM worked-problem reveal flow.
            ctx = ModeContext(
                db=db, user_id=test.created_by,
                extra={"question_type": test.question_type},
            )

            total = min(test.question_count, len(concepts))
            for i, concept in enumerate(concepts[:total]):
                challenge = await mode.generate(concept, ctx)
                db.add(
                    PracticeTestQuestion(
                        test_id=test.id,
                        concept_id=concept.id,
                        order_index=i,
                        prompt=challenge.prompt,
                        payload=dict(challenge.payload or {}),
                    )
                )
                test.questions_done = i + 1
                await db.commit()
                await _broadcast(
                    course_id,
                    {"type": "practice_test_progress", "test_id": test_id,
                     "done": i + 1, "total": total},
                )

            test.question_count = total
            test.generation_status = GEN_READY
            await db.commit()
            await _broadcast(
                course_id,
                {"type": "practice_test_complete", "test_id": test_id, "total": total},
            )
            print(f"[PRACTICE TEST WORKER] ✅ test {test_id}: {total} question(s)")

        except Exception:
            await db.rollback()
            test = await db.get(PracticeTest, uuid.UUID(test_id))
            if test is not None:
                test.generation_status = GEN_FAILED
                test.failure_reason = "generation error"
                await db.commit()
            await _broadcast(
                course_id,
                {"type": "practice_test_failed", "test_id": test_id, "reason": "generation error"},
            )
            raise  # let run_worker_loop retry / dead-letter


async def practice_test_worker() -> None:
    """Drain the practice-test generation queue via the shared reliable worker loop."""
    await run_worker_loop("practice_test", process_practice_test_job)


if __name__ == "__main__":
    asyncio.run(practice_test_worker())
