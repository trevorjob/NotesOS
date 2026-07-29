"""
The note's attribution layer — GET /api/topics/{id}/contributions.

Aggregates the non-quarantined resources behind a note into: who built it (distinct
uploaders), what was added recently, and how many resources are new since the caller's
previous read (NOTE_VIEW, current session excluded by a grace window).
"""

import uuid
from datetime import datetime, timedelta

import pytest_asyncio

from app.models import Concept, Course, Topic, User  # noqa: F401  (Course/Topic/User used)
from app.models.course import CourseEnrollment
from app.models.resource import Resource
from app.models.consume import ConsumeEvent, ConsumeKind
from tests.conftest import unique_phone


def _user(name: str) -> User:
    return User(email=f"{name.lower()}_{uuid.uuid4().hex[:6]}@t.dev", full_name=name, password_hash="x", phone=unique_phone())


@pytest_asyncio.fixture
async def topic_ctx(db_session):
    """Factory: course + topic enrolling ``caller_id``. Returns (topic, add_resource, add_view)."""

    async def _make(caller_id, *, enrolled=True):
        uid = uuid.UUID(caller_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        if enrolled:
            db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topic = Topic(course_id=course.id, title="T")
        db_session.add(topic)
        await db_session.flush()

        async def add_resource(uploader: User, *, title, created_at, quarantined=False):
            if uploader.id is None:
                db_session.add(uploader)
                await db_session.flush()
            r = Resource(
                topic_id=topic.id, uploaded_by=uploader.id, content="x",
                title=title, quarantined=quarantined, created_at=created_at,
            )
            db_session.add(r)
            await db_session.flush()
            return r

        async def add_view(actor_id, *, created_at):
            db_session.add(ConsumeEvent(
                actor_id=uuid.UUID(actor_id), topic_id=topic.id,
                kind=ConsumeKind.NOTE_VIEW, created_at=created_at,
            ))
            await db_session.flush()

        return topic, add_resource, add_view

    return _make


async def _commit(db_session):
    await db_session.commit()


async def test_contributors_distinct_recent_ordered(client, register_user, topic_ctx, db_session):
    caller = await register_user()
    topic, add_resource, _ = await topic_ctx(caller["id"])
    ada, kofi = _user("Ada"), _user("Kofi")
    now = datetime.utcnow()
    await add_resource(ada, title="Lecture 1", created_at=now - timedelta(days=5))
    await add_resource(kofi, title="Lecture 2", created_at=now - timedelta(days=2))
    await add_resource(ada, title="Lecture 3", created_at=now - timedelta(hours=1))
    await _commit(db_session)

    resp = await client.get(f"/api/topics/{topic.id}/contributions", headers=caller["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["contributor_count"] == 2
    assert {c["name"] for c in data["contributors"]} == {"Ada", "Kofi"}
    # recent = newest first
    assert [r["title"] for r in data["recent"]] == ["Lecture 3", "Lecture 2", "Lecture 1"]
    assert data["recent"][0]["uploader_name"] == "Ada"


async def test_quarantined_excluded(client, register_user, topic_ctx, db_session):
    caller = await register_user()
    topic, add_resource, _ = await topic_ctx(caller["id"])
    ada, mallory = _user("Ada"), _user("Mallory")
    now = datetime.utcnow()
    await add_resource(ada, title="Real", created_at=now - timedelta(days=1))
    await add_resource(mallory, title="Held", created_at=now, quarantined=True)
    await _commit(db_session)

    data = (await client.get(f"/api/topics/{topic.id}/contributions", headers=caller["headers"])).json()
    assert data["contributor_count"] == 1
    assert {c["name"] for c in data["contributors"]} == {"Ada"}
    assert [r["title"] for r in data["recent"]] == ["Real"]


async def test_recent_capped_at_three(client, register_user, topic_ctx, db_session):
    caller = await register_user()
    topic, add_resource, _ = await topic_ctx(caller["id"])
    ada = _user("Ada")
    now = datetime.utcnow()
    for i in range(5):
        await add_resource(ada, title=f"R{i}", created_at=now - timedelta(days=i))
    await _commit(db_session)

    data = (await client.get(f"/api/topics/{topic.id}/contributions", headers=caller["headers"])).json()
    assert len(data["recent"]) == 3
    assert [r["title"] for r in data["recent"]] == ["R0", "R1", "R2"]  # newest


async def test_new_since_last_read_counts_after_prior_view(client, register_user, topic_ctx, db_session):
    caller = await register_user()
    topic, add_resource, add_view = await topic_ctx(caller["id"])
    ada = _user("Ada")
    now = datetime.utcnow()
    await add_resource(ada, title="Old", created_at=now - timedelta(days=5))
    await add_view(caller["id"], created_at=now - timedelta(days=3))  # prior read
    await add_resource(ada, title="New1", created_at=now - timedelta(days=2))
    await add_resource(ada, title="New2", created_at=now - timedelta(days=1))
    await _commit(db_session)

    data = (await client.get(f"/api/topics/{topic.id}/contributions", headers=caller["headers"])).json()
    assert data["new_since_last_read"] == 2


async def test_new_since_null_when_never_read(client, register_user, topic_ctx, db_session):
    caller = await register_user()
    topic, add_resource, _ = await topic_ctx(caller["id"])
    await add_resource(_user("Ada"), title="R", created_at=datetime.utcnow() - timedelta(days=1))
    await _commit(db_session)

    data = (await client.get(f"/api/topics/{topic.id}/contributions", headers=caller["headers"])).json()
    assert data["new_since_last_read"] is None


async def test_current_session_view_excluded_by_grace(client, register_user, topic_ctx, db_session):
    caller = await register_user()
    topic, add_resource, add_view = await topic_ctx(caller["id"])
    await add_resource(_user("Ada"), title="R", created_at=datetime.utcnow() - timedelta(days=1))
    await add_view(caller["id"], created_at=datetime.utcnow())  # this-session view, within grace
    await _commit(db_session)

    data = (await client.get(f"/api/topics/{topic.id}/contributions", headers=caller["headers"])).json()
    assert data["new_since_last_read"] is None  # only view is inside the grace window


async def test_contributions_requires_enrollment(client, register_user, topic_ctx, db_session):
    owner = await register_user()
    topic, _, _ = await topic_ctx(owner["id"], enrolled=False)
    await _commit(db_session)
    outsider = await register_user()
    resp = await client.get(f"/api/topics/{topic.id}/contributions", headers=outsider["headers"])
    assert resp.status_code == 403


async def test_contributions_unknown_topic_404(client, register_user):
    caller = await register_user()
    resp = await client.get(f"/api/topics/{uuid.uuid4()}/contributions", headers=caller["headers"])
    assert resp.status_code == 404
