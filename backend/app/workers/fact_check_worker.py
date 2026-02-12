"""
NotesOS - Fact Check Worker
Background worker for async fact-checking jobs.
"""

import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.resource import Resource, FactCheck, VerificationStatus
from app.services.fact_checker import fact_checker
from app.services.redis_client import redis_client


async def process_fact_check_job(job_data: dict):
    """
    Process a fact-check job from the Redis queue.

    Args:
        job_data: {"resource_id": "uuid"}
    """
    resource_id = job_data.get("resource_id")

    if not resource_id:
        print("[FACT CHECK WORKER] Error: No resource_id in job data")
        return

    print(f"[FACT CHECK WORKER] Starting fact check for resource {resource_id}")

    async for db in get_db():
        try:
            # Fetch resource with topic loaded (for course_id)
            resource_query = (
                select(Resource)
                .options(selectinload(Resource.topic))
                .where(Resource.id == uuid.UUID(resource_id))
            )
            result = await db.execute(resource_query)
            resource = result.scalar_one_or_none()

            if not resource:
                print(f"[FACT CHECK WORKER] Error: Resource {resource_id} not found")
                return

            if not resource.content or len(resource.content) < 50:
                print(f"[FACT CHECK WORKER] Error: Resource content too short")
                return

            # Run fact checker
            report = await fact_checker.check_facts(resource_id, resource.content)

            # Save verifications to database
            for verification in report.get("verifications", []):
                fact_check = FactCheck(
                    resource_id=resource.id,
                    claim_text=verification.get("claim_text", ""),
                    verification_status=VerificationStatus[
                        verification.get("status", "unverified").upper()
                    ],
                    sources=verification.get("sources", []),
                    confidence_score=verification.get("confidence", 0.0),
                    ai_explanation=verification.get("explanation", ""),
                )
                db.add(fact_check)

            # Update resource verification status
            resource.is_verified = True
            await db.commit()

            print(
                f"[FACT CHECK WORKER] Completed fact check for resource {resource_id}"
            )
            summary = report.get("summary", "")
            print(f"[FACT CHECK WORKER] Results: {summary}")

            # Send WebSocket notification to the course channel via Redis
            if resource.topic and resource.topic.course_id:
                await redis_client.publish(
                    channel="course_updates",
                    message={
                        "course_id": str(resource.topic.course_id),
                        "message": {
                            "type": "fact_check:complete",
                            "data": {
                                "resource_id": resource_id,
                                "topic_id": str(resource.topic_id),
                                "summary": report.get("summary"),
                                "stats": {
                                    "total": report.get("total_claims", 0),
                                    "verified": report.get("verified", 0),
                                    "disputed": report.get("disputed", 0),
                                    "unverified": report.get("unverified", 0),
                                },
                            },
                        },
                    },
                )

        except Exception as e:
            print(f"[FACT CHECK WORKER] Error processing job: {e}")
            await db.rollback()
            raise


async def start_fact_check_worker():
    """Start the fact check worker (listens to Redis queue)."""
    print("[FACT CHECK WORKER] Starting worker...")

    while True:
        try:
            # Poll for jobs from Redis
            job_data = await redis_client.dequeue_job("fact_check")

            if job_data:
                await process_fact_check_job(job_data)
            else:
                # No jobs, wait a bit
                await asyncio.sleep(1)

        except Exception as e:
            print(f"[FACT CHECK WORKER] Worker error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    """Run the worker."""
    asyncio.run(start_fact_check_worker())
