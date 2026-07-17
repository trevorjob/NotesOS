"""
Brain dump — uncued, whole-topic free recall (B7).

Brain dump and recap are **two surfaces of one free-recall machine** (product-map,
LOCKED 2026-07-17), distinguished only by the set selector:

- **Recap** — the *last session's* concepts ("blurt everything from last time").
- **Brain dump** — the topic's **full** concept set ("everything you know about this
  topic"). The purest retrieval act on the platform: no concept cue at all; one
  monologue graded against everything, and a concept that never surfaces is a genuine
  lapse — exactly the forgetting the dump exists to expose.

No new machinery: the opener lives here, the grading is ``recap.grade_recap`` with the
mode key swapped to ``brain_dump`` (*not* ``dump`` — capture owns that word). Like recap
it's an **orchestration, not a registry mode**, driving its own two-request HTTP flow.
The read→dump→wait→dump *protocol* is a schedule, not a feature — spacing is FSRS/decay,
and dump-after-reading is a next-action case (see ``next_action``).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Topic
from app.models.retrieval import Concept
from app.services.retrieval.recap import RecapChallenge

DUMP_MODE = "brain_dump"


class NoDumpAvailable(Exception):
    """Raised when the topic has no concepts to dump against (nothing synthesized yet)."""


async def build_dump(db: AsyncSession, *, topic_id) -> RecapChallenge:
    """Open a brain dump: the topic's full concept set behind one uncued prompt.

    Raises ``NoDumpAvailable`` when the topic has no concepts yet. The prompt names the
    topic but **never lists the concepts** — free recall is uncued on purpose (listing
    them would hand back the answer). Same challenge shape as recap: one machine.
    """
    rows = (
        await db.execute(
            select(Concept.id)
            .where(Concept.topic_id == topic_id)
            .order_by(Concept.order_index)
        )
    ).scalars().all()
    if not rows:
        raise NoDumpAvailable("this topic has no concepts to dump against yet")

    topic = await db.get(Topic, topic_id)
    topic_title = topic.title if topic is not None else "this topic"

    prompt = (
        f"Brain dump: without looking at anything, tell me **everything you know about "
        f"{topic_title}** — in your own words, in any order. Don't stop to check; "
        "getting it out of your head is the whole exercise."
    )
    return RecapChallenge(
        prompt=prompt, topic_title=topic_title, concept_ids=[str(cid) for cid in rows]
    )
