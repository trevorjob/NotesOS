"""
Per-concept mastery for a topic — the note's heat-map data.

GET /api/topics/{id}/concept-states joins the topic's shared Concept rows against the
caller's own ConceptState and collapses each into one heat-map label (new/solid/fading/
shaky). Covers the derivation edges, ordering, the summary counts, and enrollment.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from app.models import Concept, Course, Topic
from app.models.course import CourseEnrollment
from app.models.retrieval import ConceptState
from app.services.retrieval.scheduler import derive_mastery


@pytest_asyncio.fixture
async def topic_with_concepts(db_session):
    """Factory: a course (optionally enrolling ``user_id``) + topic + ordered concepts.

    ``concepts`` is a list of (term, state_kwargs|None); a None entry leaves the concept
    with no ConceptState for the user (an untouched concept). Commits so the client's
    own sessions see it.
    """

    async def _make(user_id, concepts, *, enrolled=True):
        uid = uuid.UUID(user_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        if enrolled:
            db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topic = Topic(course_id=course.id, title="T")
        db_session.add(topic)
        await db_session.flush()

        for i, (term, state_kwargs) in enumerate(concepts):
            concept = Concept(topic_id=topic.id, course_id=course.id, text=term, order_index=i)
            db_session.add(concept)
            await db_session.flush()
            if state_kwargs is not None:
                db_session.add(ConceptState(user_id=uid, concept_id=concept.id, **state_kwargs))
        await db_session.commit()
        return course, topic

    return _make


# ── derive_mastery (pure) ──────────────────────────────────────────────────

def test_derive_new_when_never_reviewed():
    assert derive_mastery(reps=0, last_grade=None, fsrs_state=None, due=None) == "new"


def test_derive_shaky_on_recent_lapse():
    future = datetime.utcnow() + timedelta(days=3)
    # A future due doesn't override a just-missed grade — shaky wins.
    assert derive_mastery(reps=2, last_grade="again", fsrs_state=2, due=future) == "shaky"


def test_derive_shaky_when_relearning():
    assert derive_mastery(reps=2, last_grade="good", fsrs_state=3, due=None) == "shaky"


def test_derive_fading_when_overdue():
    past = datetime.utcnow() - timedelta(days=1)
    assert derive_mastery(reps=2, last_grade="good", fsrs_state=2, due=past) == "fading"


def test_derive_solid_when_due_in_future():
    future = datetime.utcnow() + timedelta(days=5)
    assert derive_mastery(reps=3, last_grade="good", fsrs_state=2, due=future) == "solid"


# ── endpoint ───────────────────────────────────────────────────────────────

async def test_concept_states_labels_each_concept(client, register_user, topic_with_concepts):
    user = await register_user()
    future = datetime.utcnow() + timedelta(days=5)
    past = datetime.utcnow() - timedelta(days=1)
    _, topic = await topic_with_concepts(
        user["id"],
        [
            ("Glycolysis", {"reps": 3, "last_grade": "good", "fsrs_state": 2, "due": future}),
            ("Krebs cycle", {"reps": 2, "last_grade": "good", "fsrs_state": 2, "due": past}),
            ("Electron transport", {"reps": 1, "last_grade": "again", "fsrs_state": 2, "due": future}),
            ("Fermentation", None),
        ],
    )

    resp = await client.get(f"/api/topics/{topic.id}/concept-states", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Ordering preserved (order_index), and each term carries its derived state.
    by_term = {c["term"]: c["state"] for c in data["concepts"]}
    assert [c["term"] for c in data["concepts"]] == [
        "Glycolysis", "Krebs cycle", "Electron transport", "Fermentation",
    ]
    assert by_term == {
        "Glycolysis": "solid",
        "Krebs cycle": "fading",
        "Electron transport": "shaky",
        "Fermentation": "new",
    }
    assert data["summary"] == {"new": 1, "solid": 1, "fading": 1, "shaky": 1}


async def test_concept_states_are_per_user(client, register_user, topic_with_concepts, db_session):
    owner = await register_user()
    future = datetime.utcnow() + timedelta(days=5)
    course, topic = await topic_with_concepts(
        owner["id"],
        [("Glycolysis", {"reps": 3, "last_grade": "good", "fsrs_state": 2, "due": future})],
    )

    # Enroll a second user in the same course; they have no ConceptState of their own.
    other = await register_user()
    db_session.add(CourseEnrollment(user_id=uuid.UUID(other["id"]), course_id=course.id))
    await db_session.commit()

    owner_state = (await client.get(
        f"/api/topics/{topic.id}/concept-states", headers=owner["headers"]
    )).json()["concepts"][0]["state"]
    other_state = (await client.get(
        f"/api/topics/{topic.id}/concept-states", headers=other["headers"]
    )).json()["concepts"][0]["state"]

    assert owner_state == "solid"   # the owner drilled it
    assert other_state == "new"     # same concept, untouched for this user


async def test_concept_states_requires_enrollment(client, register_user, topic_with_concepts):
    owner = await register_user()
    _, topic = await topic_with_concepts(owner["id"], [("Glycolysis", None)], enrolled=False)

    outsider = await register_user()
    resp = await client.get(f"/api/topics/{topic.id}/concept-states", headers=outsider["headers"])
    assert resp.status_code == 403


async def test_concept_states_unknown_topic_404(client, register_user):
    user = await register_user()
    resp = await client.get(f"/api/topics/{uuid.uuid4()}/concept-states", headers=user["headers"])
    assert resp.status_code == 404


async def test_concept_states_empty_topic(client, register_user, topic_with_concepts):
    user = await register_user()
    _, topic = await topic_with_concepts(user["id"], [])
    resp = await client.get(f"/api/topics/{topic.id}/concept-states", headers=user["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["concepts"] == []
    assert data["summary"] == {"new": 0, "solid": 0, "fading": 0, "shaky": 0}
