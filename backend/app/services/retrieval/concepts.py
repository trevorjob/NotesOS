"""
Concept extraction — turning synthesized knowledge into the measurable grain.

Synthesis (``knowledge_worker``) already emits a ``concepts`` list on
``TopicKnowledge`` (``[{term, definition}, ...]``). This elevates those into
first-class ``Concept`` rows so the retrieval engine can schedule and track them.

Idempotent by design: it upserts on (topic_id, text), so re-synthesis refreshes
definitions and adds new concepts **without** dropping existing rows — the
``ConceptState`` a user has built up against a concept must survive a re-synth.
"""

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval import Concept


async def sync_concepts(
    db: AsyncSession,
    *,
    topic_id,
    course_id,
    concepts: Optional[Iterable[dict]],
) -> list[Concept]:
    """Upsert the topic's Concept rows from a synthesized ``[{term, definition}]`` list.

    Returns the concepts in list order. Flushes so new rows get ids; the caller owns
    the transaction. Concepts not in the incoming list are left untouched (a re-synth
    that drops a term shouldn't silently delete a user's history against it).
    """
    if not concepts:
        return []

    existing = {
        c.text: c
        for c in (
            await db.execute(select(Concept).where(Concept.topic_id == topic_id))
        ).scalars().all()
    }

    result: list[Concept] = []
    seen: set[str] = set()
    order = 0
    for item in concepts:
        term = (item.get("term") or "").strip()
        if not term or term in seen:
            continue
        seen.add(term)
        definition = (item.get("definition") or None)

        concept = existing.get(term)
        if concept is None:
            concept = Concept(
                topic_id=topic_id,
                course_id=course_id,
                text=term,
                definition=definition,
                order_index=order,
                source_chunk_ids=[],
            )
            db.add(concept)
        else:
            concept.definition = definition
            concept.order_index = order
        result.append(concept)
        order += 1

    await db.flush()
    return result
