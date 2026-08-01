"""
Concept extraction — turning synthesized knowledge into the measurable grain.

Synthesis (``knowledge_worker``) already emits a ``concepts`` list on
``TopicKnowledge`` (``[{term, definition}, ...]``). This elevates those into
first-class ``Concept`` rows so the retrieval engine can schedule and track them.

Idempotent by design: it upserts on (topic_id, text), so re-synthesis refreshes
definitions and adds new concepts **without** dropping existing rows — the
``ConceptState`` a user has built up against a concept must survive a re-synth.

Provenance: each concept is extracted from the finished note, not straight from
chunks, so it has no chunk pointer for free. ``_attach_provenance`` recovers one by
embedding the concept and matching it back to the topic's nearest chunks — best
effort, never a gate on concept sync. ``source_context`` then spends that provenance:
it hands the retrieval modes the concept's original passages to ground question
generation and answer grading in what the material actually said, not just the
compressed one-line definition.
"""

from typing import Iterable, Optional

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.resource import ResourceChunk
from app.models.retrieval import Concept
from app.services.embeddings import embedding_service

logger = get_logger(__name__)

CHUNKS_PER_CONCEPT = 3  # top-k source chunks recorded as a concept's provenance
SOURCE_CONTEXT_MAX_CHARS = 1800  # bounds an LLM-only grounding block, not shown to students


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
    await _attach_provenance(db, topic_id=topic_id, concepts=result)
    return result


async def _attach_provenance(
    db: AsyncSession, *, topic_id, concepts: list[Concept]
) -> None:
    """Best-effort: link each concept to the chunks it was most likely drawn from.

    Embeds each concept's term+definition, then for each one finds its nearest
    chunks within the topic by cosine distance (pgvector). Failure here must never
    break concept sync — a concept with no provenance is still a valid concept.
    """
    if not concepts:
        return

    try:
        vectors = await embedding_service.generate_embeddings_batch(
            [f"{c.text}. {c.definition or ''}".strip() for c in concepts]
        )
    except Exception:
        logger.warning("concept embedding failed; skipping provenance", exc_info=True)
        return

    for concept, vector in zip(concepts, vectors):
        concept.embedding = vector
        embedding_str = "[" + ",".join(map(str, vector)) + "]"
        try:
            rows = await db.execute(
                sql_text(
                    """
                    SELECT rc.id
                    FROM resource_chunks rc
                    JOIN resources r ON r.id = rc.resource_id
                    WHERE r.topic_id = :topic_id
                      AND r.quarantined IS FALSE
                      AND rc.embedding IS NOT NULL
                    ORDER BY rc.embedding <=> CAST(:embedding AS VECTOR)
                    LIMIT :limit
                    """
                ),
                {
                    "topic_id": str(topic_id),
                    "embedding": embedding_str,
                    "limit": CHUNKS_PER_CONCEPT,
                },
            )
            concept.source_chunk_ids = [str(row[0]) for row in rows.all()]
        except Exception:
            logger.warning(
                "chunk provenance match failed for concept",
                exc_info=True,
                extra={"concept_id": str(concept.id)},
            )


async def source_context(
    db: AsyncSession, concept: Concept, *, max_chars: int = SOURCE_CONTEXT_MAX_CHARS
) -> str:
    """The concept's original source passages, for grounding an LLM-only prompt.

    NEVER use this to build a prompt shown raw to the student (a ramble/teach
    opener, an MCQ option) — it would leak the answer. Safe wherever the LLM only
    *writes a new question* or *judges a response the student already gave*, since
    the source text itself never reaches the student either way.

    Best-effort: concepts synced before provenance existed, or where embedding
    failed, have no ``source_chunk_ids`` — this degrades to "" and callers fall
    back to the definition alone, exactly like before this existed.
    """
    ids = concept.source_chunk_ids or []
    if not ids:
        return ""

    rows = (
        await db.execute(
            select(ResourceChunk.id, ResourceChunk.chunk_text).where(ResourceChunk.id.in_(ids))
        )
    ).all()
    by_id = {str(row.id): row.chunk_text for row in rows}
    # Preserve source_chunk_ids' own order (nearest-first from _attach_provenance).
    ordered = [by_id[i] for i in ids if i in by_id]
    if not ordered:
        return ""
    return "\n---\n".join(ordered)[:max_chars]
