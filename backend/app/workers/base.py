"""
Shared worker loop for all NotesOS background queues.

Every worker is the same machine: recover orphaned jobs on startup, then pull
one job at a time off a reliable (BRPOPLPUSH) queue, run a handler, and settle
the job. This module owns that machine so the individual workers are reduced to
a `process_*_job(job_data)` handler plus a one-line entrypoint.

Failure handling (the reason this exists):
- A handler that raises is retried up to `max_attempts` with exponential backoff,
  then parked in queue:<name>:dead. It is never ack'd-and-forgotten — the old
  per-worker loops removed a failed job from the processing list without
  re-enqueuing it, so any exception silently dropped the job.
- A job whose envelope can't even be parsed is dead-lettered immediately rather
  than requeued, so a corrupt payload can't loop forever.
"""

import asyncio
import json
from typing import Awaitable, Callable

from app.services.redis_client import redis_client
from app.core.logging import get_logger

Handler = Callable[[dict], Awaitable[None]]

DEFAULT_MAX_ATTEMPTS = 3
MAX_BACKOFF_SECONDS = 30


async def run_worker_loop(
    queue_name: str,
    handler: Handler,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    poll_timeout: int = 5,
) -> None:
    """Drain ``queue:<queue_name>`` forever, dispatching each job to ``handler``."""
    logger = get_logger(f"worker.{queue_name}")
    logger.info("%s worker started", queue_name)

    recovered = await redis_client.recover_orphaned_jobs(queue_name)
    if recovered:
        logger.info("recovered orphaned jobs", extra={"count": recovered})

    while True:
        job_json = None
        try:
            job_json = await redis_client.reliable_dequeue(queue_name, timeout=poll_timeout)
            if not job_json:
                continue

            try:
                job = json.loads(job_json)
            except (json.JSONDecodeError, TypeError):
                logger.error("undecodable job, dead-lettering", extra={"raw": str(job_json)[:500]})
                await redis_client.ack_job(queue_name, job_json)
                await redis_client.push_dead_letter(queue_name, job_json)
                continue

            job_id = job.get("id")
            job_data = job.get("data", {})
            attempt = int(job.get("attempts", 0)) + 1

            if job_id:
                await redis_client.update_job_status(job_id, "processing")

            try:
                await handler(job_data)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await _handle_failure(
                    logger, queue_name, job, job_json, job_id, attempt, max_attempts, exc
                )
                continue

            if job_id:
                await redis_client.update_job_status(job_id, "completed")
            await redis_client.ack_job(queue_name, job_json)

        except asyncio.CancelledError:
            logger.info("%s worker shutting down", queue_name)
            break
        except Exception:
            # Infrastructure-level error (Redis hiccup, etc.). Return the in-flight
            # job to the queue so it isn't stranded in the processing list, then
            # back off briefly before reconnecting.
            logger.error("worker loop error", exc_info=True)
            if job_json:
                await redis_client.ack_job(queue_name, job_json)
                await redis_client.requeue_job(queue_name, job_json)
            await asyncio.sleep(1)


async def _handle_failure(
    logger, queue_name, job, job_json, job_id, attempt, max_attempts, exc
) -> None:
    """Retry with backoff, or dead-letter once attempts are exhausted.

    The original job is left in the processing list until its replacement is
    safely enqueued, then ack'd last. This makes retries at-least-once: a crash
    mid-handling leaves the job recoverable on the next startup rather than lost.
    """
    job["attempts"] = attempt

    if attempt < max_attempts:
        backoff = min(2 ** attempt, MAX_BACKOFF_SECONDS)
        logger.warning(
            "job failed, retrying",
            exc_info=True,
            extra={"attempt": attempt, "max_attempts": max_attempts, "backoff_s": backoff},
        )
        if job_id:
            await redis_client.update_job_status(job_id, "pending", error=f"attempt {attempt}: {exc}")
        await asyncio.sleep(backoff)
        await redis_client.requeue_job(queue_name, json.dumps(job))
    else:
        logger.error(
            "job exhausted retries, dead-lettering",
            exc_info=True,
            extra={"attempt": attempt, "max_attempts": max_attempts},
        )
        if job_id:
            await redis_client.update_job_status(job_id, "failed", error=f"max attempts: {exc}")
        await redis_client.push_dead_letter(queue_name, json.dumps(job))

    # Replacement (retry copy or dead-letter entry) is now durably enqueued;
    # only now remove the in-flight original from the processing list.
    await redis_client.ack_job(queue_name, job_json)
