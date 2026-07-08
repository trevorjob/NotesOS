"""
The Merge Agent gate — governance without a moderator.

The moment someone can approve or reject uploads, they're an owner with a different
job title, and ownerless is load-bearing for the shared-resource model. So the gate
is a *worker*, not a person: it already runs embedding similarity to synthesize, so
give it one job more — hold back an upload that is wildly off-topic.

The rule (from the architecture doc): an upload coherent with the topic is merged; one
whose embedding sits far from *everything else* in the topic is quarantined — kept out
of the shared note, visible only to its uploader, **until it corroborates with
something**. Corroboration is the release valve: if later material makes a
quarantined upload coherent, the same gate lets it back in.

Cold start is respected: with too few uploads there's no topic signal yet to call
anything an outlier, so everything passes (``MIN_CORPUS``). ``COHERENCE_THRESHOLD`` is
the single tuning knob — start loose (quarantine only the clearly-off) and tighten
from data.
"""

import math
import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource, ResourceChunk

# Cosine similarity below this to *every* other resource → off-topic. Loose on purpose.
COHERENCE_THRESHOLD = 0.30
# Need at least this many resources before the topic has a shape to be an outlier from.
MIN_CORPUS = 3


@dataclass(frozen=True)
class GateDecision:
    """Per-resource verdict. ``coherence`` is None when the corpus is too small to judge."""

    coherence: Optional[float]
    quarantine: bool


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def centroid(vectors: Sequence[Sequence[float]]) -> list[float]:
    """Mean vector of a resource's chunk embeddings."""
    n = len(vectors)
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / n for i in range(dim)]


def decide_quarantine(
    centroids: dict,
    *,
    threshold: float = COHERENCE_THRESHOLD,
    min_corpus: int = MIN_CORPUS,
) -> dict:
    """Judge each resource by its best coherence with any *other* resource in the topic.

    ``centroids`` maps resource id → its mean embedding. A resource is quarantined
    when it corroborates with nothing (max cosine to any peer < threshold). Below
    ``min_corpus`` resources, nothing is judged — everything passes.
    """
    ids = list(centroids)
    if len(ids) < min_corpus:
        return {i: GateDecision(coherence=None, quarantine=False) for i in ids}

    decisions: dict = {}
    for i in ids:
        peers = [cosine(centroids[i], centroids[j]) for j in ids if j != i]
        best = max(peers) if peers else 1.0
        decisions[i] = GateDecision(coherence=best, quarantine=best < threshold)
    return decisions


async def apply_merge_gate(
    db: AsyncSession,
    topic_id,
    *,
    threshold: float = COHERENCE_THRESHOLD,
    min_corpus: int = MIN_CORPUS,
) -> dict:
    """Evaluate a topic's resources and set/clear quarantine flags accordingly.

    Runs before synthesis. Resources with no embeddings yet are skipped (they can't be
    judged; a later run will catch them). Flushes; the caller owns the transaction.
    Returns a summary: which resources were newly quarantined vs. released.
    """
    tid = topic_id if isinstance(topic_id, _uuid.UUID) else _uuid.UUID(str(topic_id))

    rows = (
        await db.execute(
            select(ResourceChunk.resource_id, ResourceChunk.embedding)
            .join(Resource, ResourceChunk.resource_id == Resource.id)
            .where(Resource.topic_id == tid)
        )
    ).all()

    by_resource: dict = {}
    for resource_id, embedding in rows:
        if embedding is None:
            continue
        by_resource.setdefault(resource_id, []).append(list(embedding))

    centroids = {rid: centroid(vecs) for rid, vecs in by_resource.items() if vecs}
    decisions = decide_quarantine(centroids, threshold=threshold, min_corpus=min_corpus)

    if not centroids:
        return {"evaluated": 0, "quarantined": [], "released": []}

    resources = (
        await db.execute(select(Resource).where(Resource.id.in_(list(centroids))))
    ).scalars().all()

    newly_quarantined: list[str] = []
    released: list[str] = []
    now = datetime.utcnow()

    for resource in resources:
        decision = decisions.get(resource.id)
        if decision is None:
            continue
        if decision.quarantine and not resource.quarantined:
            resource.quarantined = True
            resource.quarantine_reason = (
                f"Off-topic: best coherence {decision.coherence:.2f} < {threshold:.2f}"
            )
            resource.quarantined_at = now
            newly_quarantined.append(str(resource.id))
        elif not decision.quarantine and resource.quarantined:
            # It now corroborates with something — release it back into the note.
            resource.quarantined = False
            resource.quarantine_reason = None
            resource.quarantined_at = None
            released.append(str(resource.id))

    await db.flush()
    return {
        "evaluated": len(centroids),
        "quarantined": newly_quarantined,
        "released": released,
    }
