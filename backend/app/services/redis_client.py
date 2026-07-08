"""
NotesOS - Redis Client Service
Redis connection and job queue management.
"""

import json
import uuid
from typing import Dict, Any, Optional
import redis.asyncio as redis

from app.config import settings


class RedisClient:
    """Manage Redis connections and job queues."""

    def __init__(self):
        """Initialize Redis connection pool."""
        self.redis_url = settings.REDIS_URL
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        """Get or create Redis client (singleton pattern)."""
        if self._client is None:
            self._client = await redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._client

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def enqueue_job(self, queue_name: str, job_data: Dict[str, Any]) -> str:
        """
        Add job to queue.

        Args:
            queue_name: Queue name (e.g., 'chunking', 'embedding', 'fact_check')
            job_data: Job payload

        Returns:
            job_id
        """
        client = await self.get_client()

        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "data": job_data,
            "status": "pending",
            "created_at": None,  # Worker will set timestamp
        }

        # Push to queue (list)
        await client.lpush(f"queue:{queue_name}", json.dumps(job))

        # Store job status in hash
        await client.hset(
            f"job:{job_id}",
            mapping={
                "status": "pending",
                "queue": queue_name,
                "data": json.dumps(job_data),
            },
        )

        # Set expiration (job data expires after 24 hours)
        await client.expire(f"job:{job_id}", 86400)

        return job_id

    async def dequeue_job(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """
        Pop job from queue (FIFO).

        Args:
            queue_name: Queue name

        Returns:
            Job data dict or None
        """
        client = await self.get_client()

        # RPOP for FIFO (since we used LPUSH)
        job_json = await client.rpop(f"queue:{queue_name}")

        if job_json:
            job = json.loads(job_json)
            return job["data"]

        return None

    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Get job status and details.

        Returns:
            dict with status, result, error, etc. or None if not found
        """
        client = await self.get_client()

        job_data = await client.hgetall(f"job:{job_id}")

        if not job_data:
            return None

        return {
            "id": job_id,
            "status": job_data.get("status"),
            "queue": job_data.get("queue"),
            "result": json.loads(job_data.get("result", "null")),
            "error": job_data.get("error"),
        }

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ):
        """
        Update job status (called by workers).

        Args:
            job_id: Job ID
            status: 'processing', 'completed', 'failed'
            result: Job result data
            error: Error message if failed
        """
        client = await self.get_client()

        updates = {"status": status}

        if result is not None:
            updates["result"] = json.dumps(result)

        if error:
            updates["error"] = error

        await client.hset(f"job:{job_id}", mapping=updates)

    async def reliable_dequeue(self, queue_name: str, timeout: int = 5) -> Optional[str]:
        """
        Atomically pop from the main queue and push to a processing queue.

        Uses BRPOPLPUSH so that if the worker crashes mid-job, the job stays
        in queue:<name>:processing and is recovered on the next startup via
        recover_orphaned_jobs().

        Returns the raw job JSON string, or None on timeout.
        """
        client = await self.get_client()
        return await client.brpoplpush(
            f"queue:{queue_name}",
            f"queue:{queue_name}:processing",
            timeout=timeout,
        )

    async def ack_job(self, queue_name: str, job_json: str) -> None:
        """Remove a finished job from the processing queue."""
        client = await self.get_client()
        await client.lrem(f"queue:{queue_name}:processing", 1, job_json)

    async def requeue_job(self, queue_name: str, job_json: str) -> None:
        """
        Push a job back onto the tail of the main queue for a later retry.

        LPUSH places it behind jobs already waiting, so a repeatedly-failing job
        can't hot-loop and starve the queue.
        """
        client = await self.get_client()
        await client.lpush(f"queue:{queue_name}", job_json)

    async def push_dead_letter(self, queue_name: str, job_json: str) -> None:
        """
        Park a job that has exhausted its retries in a dead-letter list.

        Nothing consumes queue:<name>:dead automatically — it exists so failed
        work is inspectable and replayable instead of silently lost.
        """
        client = await self.get_client()
        await client.lpush(f"queue:{queue_name}:dead", job_json)

    async def recover_orphaned_jobs(self, queue_name: str) -> int:
        """
        On worker startup, move any jobs left in queue:<name>:processing back
        to the main queue. These are jobs that were in-flight when the previous
        worker process was killed.

        Returns the number of jobs recovered.
        """
        client = await self.get_client()
        count = 0
        while True:
            job_json = await client.rpoplpush(
                f"queue:{queue_name}:processing",
                f"queue:{queue_name}",
            )
            if job_json is None:
                break
            count += 1
        return count

    async def cache_embedding(self, text: str, embedding: list, ttl: int = 3600):
        """
        Cache embedding for frequently accessed text.

        Args:
            text: Source text
            embedding: Vector embedding
            ttl: Time to live in seconds (default 1 hour)
        """
        client = await self.get_client()

        # Use text hash as key
        key = f"embedding:{hash(text)}"
        await client.set(key, json.dumps(embedding), ex=ttl)

    async def get_cached_embedding(self, text: str) -> Optional[list]:
        """
        Retrieve cached embedding.

        Returns:
            Embedding vector or None if not cached
        """
        client = await self.get_client()

        key = f"embedding:{hash(text)}"
        cached = await client.get(key)

        if cached:
            return json.loads(cached)

        return None

    async def publish(self, channel: str, message: Dict[str, Any]):
        """
        Publish message to a channel.

        Args:
            channel: Channel name
            message: Message dict
        """
        client = await self.get_client()
        await client.publish(f"channel:{channel}", json.dumps(message))

    async def subscribe(self, channel: str):
        """
        Subscribe to a channel and yield messages.

        Args:
            channel: Channel name

        Yields:
            Message dict
        """
        client = await self.get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(f"channel:{channel}")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    yield json.loads(message["data"])
                except json.JSONDecodeError:
                    continue


# Singleton instance
redis_client = RedisClient()
