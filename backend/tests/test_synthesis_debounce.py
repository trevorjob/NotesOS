"""
Synthesis debounce — a bursty topic coalesces to one knowledge job per window.

Runs against the real Redis the app uses. Each test uses a fresh (uuid) topic id so
the per-topic cooldown key never collides with another test's window.
"""

import json
import uuid

import pytest
import pytest_asyncio

from app.services.redis_client import redis_client
from app.services.synthesis_debounce import schedule_synthesis


@pytest_asyncio.fixture(autouse=True)
async def _fresh_redis():
    redis_client._client = None
    yield
    if redis_client._client is not None:
        await redis_client._client.aclose()
        redis_client._client = None


async def _drain_knowledge_queue():
    client = await redis_client.get_client()
    await client.delete("queue:knowledge")


async def _knowledge_jobs() -> list[dict]:
    """Every job currently queued on ``queue:knowledge`` (newest first)."""
    client = await redis_client.get_client()
    raw = await client.lrange("queue:knowledge", 0, -1)
    return [json.loads(r)["data"] for r in raw]


async def test_burst_coalesces_to_one_job():
    await _drain_knowledge_queue()
    topic = str(uuid.uuid4())

    results = [await schedule_synthesis(topic, "course-1") for _ in range(5)]

    assert results[0] is True                 # first arms the window + enqueues
    assert results[1:] == [False] * 4         # the rest coalesce
    jobs = await _knowledge_jobs()
    assert len(jobs) == 1
    assert jobs[0]["topic_id"] == topic


async def test_distinct_topics_are_independent():
    await _drain_knowledge_queue()
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())

    assert await schedule_synthesis(t1, "c") is True
    assert await schedule_synthesis(t2, "c") is True  # different key, own window

    assert len(await _knowledge_jobs()) == 2


async def test_force_full_bypasses_the_window():
    await _drain_knowledge_queue()
    topic = str(uuid.uuid4())

    await schedule_synthesis(topic, "c")                       # enqueues, arms window
    assert await schedule_synthesis(topic, "c") is False       # coalesced
    assert await schedule_synthesis(topic, "c", force_full=True) is True  # always runs

    jobs = await _knowledge_jobs()
    assert len(jobs) == 2
    assert any(j["force_full"] for j in jobs)


async def test_bypass_debounce_always_enqueues():
    await _drain_knowledge_queue()
    topic = str(uuid.uuid4())

    await schedule_synthesis(topic, "c")                            # arms window
    r = await schedule_synthesis(topic, "c", bypass_debounce=True)  # trailing pass
    assert r is True

    jobs = await _knowledge_jobs()
    assert len(jobs) == 2
    assert all(j["force_full"] is False for j in jobs)  # trailing is incremental
