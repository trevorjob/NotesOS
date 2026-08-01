"""Concept extraction: elevate synthesized concepts to rows, idempotently."""

import uuid

import pytest
from sqlalchemy import select

from app.models import Concept, Course, Resource, ResourceChunk, Topic, User
from app.services.retrieval import concepts as concepts_module
from app.services.retrieval.concepts import sync_concepts
from tests.conftest import unique_phone


@pytest.fixture(autouse=True)
def stub_embeddings(monkeypatch):
    """sync_concepts embeds for chunk provenance now — stub so tests stay fast/offline/free.

    Individual provenance tests override this stub where they need real vectors.
    """
    async def _fake_batch(texts, input_type="document"):
        return [[0.0] * 1536 for _ in texts]

    monkeypatch.setattr(concepts_module.embedding_service, "generate_embeddings_batch", _fake_batch)


def _vec(idx: int) -> list[float]:
    """A 1536-dim unit vector pointing along one axis (a distinct 'direction')."""
    v = [0.0] * 1536
    v[idx] = 1.0
    return v


async def _course_with_topic(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code="HIS101", name="History", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="WWI")
    db.add(topic)
    await db.flush()
    return user, course, topic


async def test_sync_creates_concept_rows(db_session):
    _user, course, topic = await _course_with_topic(db_session)
    concepts = await sync_concepts(
        db_session,
        topic_id=topic.id,
        course_id=course.id,
        concepts=[
            {"term": "Schlieffen Plan", "definition": "German war strategy"},
            {"term": "Trench warfare", "definition": "Static attrition"},
        ],
    )
    assert [c.text for c in concepts] == ["Schlieffen Plan", "Trench warfare"]
    assert [c.order_index for c in concepts] == [0, 1]

    rows = (await db_session.execute(select(Concept).where(Concept.topic_id == topic.id))).scalars().all()
    assert len(rows) == 2


async def test_sync_is_idempotent_and_preserves_rows(db_session):
    _user, course, topic = await _course_with_topic(db_session)
    first = await sync_concepts(
        db_session, topic_id=topic.id, course_id=course.id,
        concepts=[{"term": "Schlieffen Plan", "definition": "old def"}],
    )
    first_id = first[0].id

    # Re-synth: same term (updated definition) + a new one.
    await sync_concepts(
        db_session, topic_id=topic.id, course_id=course.id,
        concepts=[
            {"term": "Schlieffen Plan", "definition": "new def"},
            {"term": "Trench warfare", "definition": "Static attrition"},
        ],
    )
    rows = (await db_session.execute(select(Concept).where(Concept.topic_id == topic.id).order_by(Concept.order_index))).scalars().all()
    assert len(rows) == 2  # no duplicate for the repeated term
    assert rows[0].id == first_id  # same row survived (its ConceptStates would too)
    assert rows[0].definition == "new def"  # definition refreshed


async def test_blank_and_duplicate_terms_are_skipped(db_session):
    _user, course, topic = await _course_with_topic(db_session)
    concepts = await sync_concepts(
        db_session, topic_id=topic.id, course_id=course.id,
        concepts=[
            {"term": "  ", "definition": "blank"},
            {"term": "Alliances", "definition": "a"},
            {"term": "Alliances", "definition": "dup"},
        ],
    )
    assert [c.text for c in concepts] == ["Alliances"]


async def _resource_with_chunk(db, *, user, topic, chunk_text, direction, quarantined=False):
    resource = Resource(
        topic_id=topic.id, uploaded_by=user.id, content=chunk_text, quarantined=quarantined,
    )
    db.add(resource)
    await db.flush()
    db.add(ResourceChunk(resource_id=resource.id, chunk_text=chunk_text, chunk_index=0, embedding=_vec(direction)))
    await db.flush()
    return resource


async def test_provenance_links_concept_to_nearest_chunk(db_session, monkeypatch):
    """The exact-match chunk ranks first; the top-k cap holds when candidates overflow it."""
    user, course, topic = await _course_with_topic(db_session)
    near = await _resource_with_chunk(db_session, user=user, topic=topic, chunk_text="Schlieffen Plan details", direction=0)
    # 3 more candidates, each orthogonal to the query (worse than `near`'s exact match) —
    # with CHUNKS_PER_CONCEPT=3, near + these 3 overflows the cap by one.
    for i in range(1, 4):
        await _resource_with_chunk(db_session, user=user, topic=topic, chunk_text=f"unrelated {i}", direction=i)

    # The concept's own embedding points the same direction as `near`'s chunk (idx 0) —
    # an exact match, so it must always rank first regardless of the other candidates.
    async def _fake_batch(texts, input_type="document"):
        return [_vec(0) for _ in texts]
    monkeypatch.setattr(concepts_module.embedding_service, "generate_embeddings_batch", _fake_batch)

    concepts = await sync_concepts(
        db_session, topic_id=topic.id, course_id=course.id,
        concepts=[{"term": "Schlieffen Plan", "definition": "German war strategy"}],
    )
    concept = concepts[0]

    assert concept.embedding is not None
    near_rows = (await db_session.execute(
        select(ResourceChunk).where(ResourceChunk.resource_id == near.id)
    )).scalars().all()
    assert concept.source_chunk_ids[0] == str(near_rows[0].id)  # exact match ranks first
    assert len(concept.source_chunk_ids) == concepts_module.CHUNKS_PER_CONCEPT  # capped, not all 4


async def test_provenance_excludes_quarantined_resources(db_session, monkeypatch):
    user, course, topic = await _course_with_topic(db_session)
    quarantined = await _resource_with_chunk(
        db_session, user=user, topic=topic, chunk_text="off-topic", direction=0, quarantined=True,
    )

    async def _fake_batch(texts, input_type="document"):
        return [_vec(0) for _ in texts]
    monkeypatch.setattr(concepts_module.embedding_service, "generate_embeddings_batch", _fake_batch)

    concepts = await sync_concepts(
        db_session, topic_id=topic.id, course_id=course.id,
        concepts=[{"term": "Anything", "definition": "d"}],
    )
    quarantined_rows = (await db_session.execute(
        select(ResourceChunk).where(ResourceChunk.resource_id == quarantined.id)
    )).scalars().all()
    quarantined_chunk_ids = {str(c.id) for c in quarantined_rows}
    assert not (quarantined_chunk_ids & set(concepts[0].source_chunk_ids))
    assert concepts[0].source_chunk_ids == []  # nothing else in the topic to match


async def test_provenance_failure_does_not_break_concept_sync(db_session, monkeypatch):
    """Embedding/provenance is best-effort — a failure must not stop concepts being created."""
    _user, course, topic = await _course_with_topic(db_session)

    async def _boom(texts, input_type="document"):
        raise RuntimeError("embedding provider down")
    monkeypatch.setattr(concepts_module.embedding_service, "generate_embeddings_batch", _boom)

    concepts = await sync_concepts(
        db_session, topic_id=topic.id, course_id=course.id,
        concepts=[{"term": "Alliances", "definition": "a"}],
    )
    assert [c.text for c in concepts] == ["Alliances"]
    assert concepts[0].source_chunk_ids == []


async def _chunk_id(db, resource) -> str:
    row = (await db.execute(
        select(ResourceChunk).where(ResourceChunk.resource_id == resource.id)
    )).scalars().one()
    return str(row.id)


async def test_source_context_joins_chunks_in_provenance_order(db_session):
    """source_context spends the provenance: it resolves ids back to text, nearest-first."""
    user, course, topic = await _course_with_topic(db_session)
    concept = Concept(topic_id=topic.id, course_id=course.id, text="X")
    db_session.add(concept)
    await db_session.flush()

    res_a = await _resource_with_chunk(db_session, user=user, topic=topic, chunk_text="second chunk", direction=0)
    res_b = await _resource_with_chunk(db_session, user=user, topic=topic, chunk_text="first chunk", direction=1)
    id_a, id_b = await _chunk_id(db_session, res_a), await _chunk_id(db_session, res_b)
    # Deliberately out of insertion order — source_chunk_ids' own order must win (nearest-first).
    concept.source_chunk_ids = [id_b, id_a]

    result = await concepts_module.source_context(db_session, concept)
    assert result == "first chunk\n---\nsecond chunk"


async def test_source_context_empty_when_no_provenance(db_session):
    _user, course, topic = await _course_with_topic(db_session)
    concept = Concept(topic_id=topic.id, course_id=course.id, text="X", source_chunk_ids=[])
    db_session.add(concept)
    await db_session.flush()

    assert await concepts_module.source_context(db_session, concept) == ""


async def test_source_context_truncates_to_max_chars(db_session):
    user, course, topic = await _course_with_topic(db_session)
    concept = Concept(topic_id=topic.id, course_id=course.id, text="X")
    db_session.add(concept)
    await db_session.flush()

    res = await _resource_with_chunk(db_session, user=user, topic=topic, chunk_text="a" * 5000, direction=0)
    concept.source_chunk_ids = [await _chunk_id(db_session, res)]

    result = await concepts_module.source_context(db_session, concept, max_chars=100)
    assert len(result) == 100
