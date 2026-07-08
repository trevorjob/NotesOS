"""Concept extraction: elevate synthesized concepts to rows, idempotently."""

import uuid

from sqlalchemy import select

from app.models import Concept, Course, Topic, User
from app.services.retrieval.concepts import sync_concepts


async def _course_with_topic(db):
    user = User(email=f"u_{uuid.uuid4().hex[:8]}@t.dev", full_name="U", password_hash="x")
    db.add(user)
    await db.flush()
    course = Course(code="HIS101", name="History", created_by=user.id)
    db.add(course)
    await db.flush()
    topic = Topic(course_id=course.id, title="WWI")
    db.add(topic)
    await db.flush()
    return course, topic


async def test_sync_creates_concept_rows(db_session):
    course, topic = await _course_with_topic(db_session)
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
    course, topic = await _course_with_topic(db_session)
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
    course, topic = await _course_with_topic(db_session)
    concepts = await sync_concepts(
        db_session, topic_id=topic.id, course_id=course.id,
        concepts=[
            {"term": "  ", "definition": "blank"},
            {"term": "Alliances", "definition": "a"},
            {"term": "Alliances", "definition": "dup"},
        ],
    )
    assert [c.text for c in concepts] == ["Alliances"]
