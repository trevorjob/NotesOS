"""
Synthesis debounce — coalesce bursty synthesis triggers into one pass.

A bulk upload (A2 capture) can finish chunking a dozen files within seconds, each
wanting to re-synthesize the same topic. Firing one synthesis per file is the
write-amplification we're killing. This module gates the enqueue: at most one
knowledge job per topic per debounce window. Stragglers that arrive mid-window
don't enqueue — the already-scheduled job merges whatever is pending when it runs,
and the worker re-schedules a trailing pass if anything is still unmerged (the DB's
``synthesized_at`` is the source of truth for "what's left", not this window).

Two escape hatches bypass the window and always enqueue:
  * ``force_full``      — a manual regenerate / post-move rebuild.
  * ``bypass_debounce`` — the worker's own trailing re-schedule for stragglers.
"""

from typing import Optional

from app.services.redis_client import redis_client

# One synth per topic per window. Long enough to swallow a chunking burst, short
# enough that a lone upload's note appears promptly.
SYNTH_DEBOUNCE_WINDOW_SEC = 10

_COOLDOWN_KEY = "synth:cooldown:{}"


async def schedule_synthesis(
    topic_id,
    course_id: Optional[str] = None,
    *,
    force_full: bool = False,
    bypass_debounce: bool = False,
) -> bool:
    """
    Request synthesis for a topic, coalescing bursts.

    Returns True if a knowledge job was enqueued, False if it was coalesced into an
    already-scheduled run within the debounce window.
    """
    client = await redis_client.get_client()
    key = _COOLDOWN_KEY.format(str(topic_id))
    payload = {
        "topic_id": str(topic_id),
        "course_id": str(course_id) if course_id is not None else None,
        "force_full": force_full,
    }

    if force_full or bypass_debounce:
        # Always run; (re)arm the window so followups coalesce onto this run.
        await client.set(key, "1", ex=SYNTH_DEBOUNCE_WINDOW_SEC)
        await redis_client.enqueue_job("knowledge", payload)
        return True

    acquired = await client.set(key, "1", nx=True, ex=SYNTH_DEBOUNCE_WINDOW_SEC)
    if not acquired:
        return False
    await redis_client.enqueue_job("knowledge", payload)
    return True
