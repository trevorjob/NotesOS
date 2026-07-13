"""
The B2 digest tick — a **periodic** worker, the deliberate exception to the reactive
queue loop (build-guide §2a). ``base.py`` drains a queue when an event arrives; the habit
digest must fire on a schedule regardless of events, so it runs on **APScheduler** instead
of a `sleep()` bolted onto the reactive loop.

All the digest *logic* lives in ``services/digest.py`` (apscheduler-free, unit-tested).
This module is just the glue: an ``AsyncIOScheduler`` firing ``run_digest_tick`` hourly.
Shaped like the other workers (a forever-awaitable) so ``run_workers.py`` can gather it.
APScheduler is an optional dependency — imported lazily so the rest of the app never needs
it; install it via ``requirements.txt`` before starting workers.
"""

import asyncio

from app.core.logging import get_logger
from app.database import worker_session
from app.services.digest import run_digest_tick

logger = get_logger(__name__)

# Tick hourly; the digest self-gates to one attempt per user per day, so a coarse tick is
# enough — it only needs to catch each user's preferred study hour.
DIGEST_TICK_MINUTES = 60


async def _tick() -> None:
    async with worker_session() as db:
        sent = await run_digest_tick(db)
    if sent:
        logger.info("digest tick delivered to %d user(s)", sent)


async def notification_scheduler() -> None:
    """Run the digest scheduler forever (cancel-safe), for ``run_workers.py`` to gather."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _tick,
        IntervalTrigger(minutes=DIGEST_TICK_MINUTES),
        id="digest_tick",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("🔔 notification digest scheduler started (every %d min)", DIGEST_TICK_MINUTES)
    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        scheduler.shutdown(wait=False)
        raise
