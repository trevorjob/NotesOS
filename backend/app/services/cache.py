"""
NotesOS - API Response Cache Service
Thin Redis wrapper for read-through caching of GET endpoints.
Separate from redis_client.py which handles job queues.
"""

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-backed cache for API responses."""

    def __init__(self) -> None:
        self._client: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = await redis.from_url(
                settings.REDIS_URL, encoding="utf-8", decode_responses=True
            )
        return self._client

    async def get(self, key: str) -> Any | None:
        """Return cached value or None if missing / cache disabled."""
        if not settings.CACHE_ENABLED:
            return None
        try:
            client = await self._get_client()
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache GET error for key %s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl_sec: int) -> None:
        """Store value in cache with TTL. Silently skips if cache disabled."""
        if not settings.CACHE_ENABLED:
            return
        try:
            client = await self._get_client()
            await client.set(key, json.dumps(value), ex=ttl_sec)
        except Exception as exc:
            logger.warning("Cache SET error for key %s: %s", key, exc)

    async def delete(self, key: str) -> None:
        """Delete a single cache key."""
        if not settings.CACHE_ENABLED:
            return
        try:
            client = await self._get_client()
            await client.delete(key)
        except Exception as exc:
            logger.warning("Cache DELETE error for key %s: %s", key, exc)

    async def delete_pattern(self, prefix: str) -> None:
        """
        Delete all keys matching prefix* using SCAN (safe for production).
        Never uses KEYS which blocks the Redis event loop.
        """
        if not settings.CACHE_ENABLED:
            return
        try:
            client = await self._get_client()
            cursor = 0
            pattern = f"{prefix}*"
            while True:
                cursor, keys = await client.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.warning("Cache DELETE_PATTERN error for prefix %s: %s", prefix, exc)


# ── Key builders ──────────────────────────────────────────────────────────────


def courses_list_key(user_id: str) -> str:
    return f"notesos:v1:courses:user:{user_id}:list"


def course_key(course_id: str) -> str:
    return f"notesos:v1:courses:course:{course_id}"


def topics_list_key(course_id: str) -> str:
    return f"notesos:v1:topics:course:{course_id}:list"


def topic_key(topic_id: str) -> str:
    return f"notesos:v1:topics:topic:{topic_id}"


def resources_list_key(topic_id: str, page: int, page_size: int) -> str:
    return f"notesos:v1:resources:topic:{topic_id}:page:{page}:size:{page_size}"


def resource_key(resource_id: str) -> str:
    return f"notesos:v1:resources:resource:{resource_id}"


# ── Singleton ─────────────────────────────────────────────────────────────────

cache = CacheService()
