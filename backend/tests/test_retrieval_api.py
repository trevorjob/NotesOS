"""
Retrieval HTTP surface — the two-request session (/next → /attempt), plus /modes.

The mode is stubbed (registered into the live registry) so the endpoints run without a
model. We pin: the sanitized handoff (answer key never leaves the server), the recorded
attempt + advanced schedule, the calibration delta, enrollment enforcement, and the
expired/unknown edges.
"""

import uuid

import pytest
import pytest_asyncio

from app.models import Concept, Course, Topic
from app.models.course import CourseEnrollment
from app.services.redis_client import redis_client
from app.services.retrieval import registry
from app.services.retrieval.modes import Challenge, Outcome, TurnResult, user_turns


@pytest_asyncio.fixture(autouse=True)
async def _fresh_redis():
    """The retrieval endpoints use ``redis_client`` for the challenge handoff. Its
    connection is a singleton, but every test runs on its own event loop (function-scoped
    engine + NullPool), so a cached connection from a prior test's loop blows up on reuse.
    Reset it per test and close within the test's own loop."""
    redis_client._client = None
    yield
    if redis_client._client is not None:
        await redis_client._client.aclose()
        redis_client._client = None


class StubApiMode:
    key = "stubapi"

    async def generate(self, concept, ctx) -> Challenge:
        return Challenge(
            concept_id=str(concept.id),
            prompt="Which is right?",
            payload={
                "question_type": "mcq",
                "answer_options": ["A", "B"],
                "correct_answer": "A",
                "explanation": "because A",
            },
        )

    async def evaluate(self, concept, challenge, response, ctx) -> Outcome:
        answer = response if isinstance(response, str) else ""
        ok = answer == (challenge.payload or {}).get("correct_answer")
        return Outcome(score=1.0 if ok else 0.0, grade="good" if ok else "again", feedback="fb")


@pytest.fixture
def stub_mode():
    registry.register(StubApiMode())
    yield
    registry._MODES.pop("stubapi", None)


@pytest_asyncio.fixture
async def seeded(db_session):
    """Factory: a course (optionally enrolling ``user_id``) with one topic + concept."""

    async def _make(user_id, *, enrolled=True):
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uuid.UUID(user_id))
        db_session.add(course)
        await db_session.flush()
        if enrolled:
            db_session.add(CourseEnrollment(user_id=uuid.UUID(user_id), course_id=course.id))
        topic = Topic(course_id=course.id, title="T")
        db_session.add(topic)
        await db_session.flush()
        concept = Concept(topic_id=topic.id, course_id=course.id, text="Photosynthesis")
        db_session.add(concept)
        await db_session.flush()
        await db_session.commit()
        return course, concept

    return _make


async def test_next_then_attempt_happy_path(client, register_user, seeded, stub_mode):
    user = await register_user()
    _, concept = await seeded(user["id"])

    nxt = await client.post(
        "/api/retrieval/next",
        headers=user["headers"],
        json={"mode": "stubapi", "concept_id": str(concept.id)},
    )
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["mode"] == "stubapi"
    assert body["concept_id"] == str(concept.id)
    assert body["concept_text"] == "Photosynthesis"  # labels a continuous session
    assert body["challenge_id"]
    # Answer key must not leak to the client.
    assert "correct_answer" not in body["payload"]
    assert "explanation" not in body["payload"]
    assert body["payload"]["answer_options"] == ["A", "B"]

    att = await client.post(
        "/api/retrieval/attempt",
        headers=user["headers"],
        json={"challenge_id": body["challenge_id"], "response": "A", "predicted_confidence": 0.4},
    )
    assert att.status_code == 200, att.text
    result = att.json()
    assert result["outcome"]["grade"] == "good"
    assert result["outcome"]["score"] == 1.0
    assert result["state"]["due"] is not None
    assert result["state"]["reps"] == 1
    # Predicted 0.4, actual 1.0 → underconfident by 0.6.
    assert result["calibration"]["delta"] == pytest.approx(0.6)
    assert result["calibration"]["label"] == "underconfident"


async def test_used_challenge_is_gone(client, register_user, seeded, stub_mode):
    user = await register_user()
    _, concept = await seeded(user["id"])
    nxt = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubapi", "concept_id": str(concept.id)},
    )
    cid = nxt.json()["challenge_id"]
    first = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "A"},
    )
    assert first.status_code == 200
    # Re-submitting the same challenge fails — it was dropped on use.
    again = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "A"},
    )
    assert again.status_code == 410


async def test_enrollment_enforced(client, register_user, seeded, stub_mode):
    user = await register_user()
    _, concept = await seeded(user["id"], enrolled=False)
    resp = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubapi", "concept_id": str(concept.id)},
    )
    assert resp.status_code == 403


async def test_unknown_mode_is_400(client, register_user, seeded, stub_mode):
    user = await register_user()
    _, concept = await seeded(user["id"])
    resp = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "does_not_exist", "concept_id": str(concept.id)},
    )
    assert resp.status_code == 400


async def test_stale_challenge_id_is_410(client, register_user, stub_mode):
    user = await register_user()
    resp = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": uuid.uuid4().hex, "response": "A"},
    )
    assert resp.status_code == 410


async def test_modes_lists_the_registered_modes(client, register_user):
    user = await register_user()
    resp = await client.get("/api/retrieval/modes", headers=user["headers"])
    assert resp.status_code == 200
    keys = {m["key"] for m in resp.json()}
    assert {"quiz", "ramble", "teach", "pretest"}.issubset(keys)
    # Every mode carries a subject affinity in [0, 1].
    assert all(0.0 <= m["affinity"] <= 1.0 for m in resp.json())


async def test_modes_affinity_shifts_with_subject_family(client, register_user):
    """The STEM family weights pretest above ramble; LANGUAGE flips it (Learning Science 12)."""
    user = await register_user()
    stem = {m["key"]: m["affinity"] for m in
            (await client.get("/api/retrieval/modes?family=STEM", headers=user["headers"])).json()}
    lang = {m["key"]: m["affinity"] for m in
            (await client.get("/api/retrieval/modes?family=LANGUAGE", headers=user["headers"])).json()}
    assert stem["pretest"] > stem["ramble"]
    assert lang["ramble"] > lang["pretest"]


async def test_topic_profile_defaults_to_general(client, register_user, seeded):
    user = await register_user()
    _, concept = await seeded(user["id"])
    resp = await client.get(
        f"/api/retrieval/topics/{concept.topic_id}/profile", headers=user["headers"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["subject_family"] == "GENERAL"
    assert body["overridden"] is False
    assert "quiz" in body["mode_mix"]      # the profile carries the full mode mix
    assert body["render"] and body["grading"]


async def test_topic_profile_override_locks_the_family(client, register_user, seeded):
    user = await register_user()
    _, concept = await seeded(user["id"])
    resp = await client.patch(
        f"/api/retrieval/topics/{concept.topic_id}/profile",
        headers=user["headers"],
        json={"subject_family": "STEM"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["subject_family"] == "STEM"
    assert body["overridden"] is True
    assert body["render"] == "math"        # STEM profile now in effect


async def test_topic_profile_requires_enrollment(client, register_user, seeded):
    owner = await register_user()
    _, concept = await seeded(owner["id"])
    intruder = await register_user()
    resp = await client.get(
        f"/api/retrieval/topics/{concept.topic_id}/profile", headers=intruder["headers"]
    )
    assert resp.status_code == 403


async def test_next_action_returns_new_for_enrolled_unattempted(client, register_user, seeded):
    """A fresh, enrolled user with concepts but no attempts → the 'new' action."""
    user = await register_user()
    await seeded(user["id"])
    resp = await client.get("/api/retrieval/next-action", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body is not None
    assert body["kind"] == "new"
    assert body["mode"] == "pretest"
    assert body["est_minutes"] >= 2
    assert body["reason"]


async def test_next_action_null_when_nothing_to_do(client, register_user):
    """No courses, no concepts → null (client routes to capture, not an empty study view)."""
    user = await register_user()
    resp = await client.get("/api/retrieval/next-action", headers=user["headers"])
    assert resp.status_code == 200
    assert resp.json() is None


async def test_next_action_enrollment_gate(client, register_user):
    """Scoping to a course the user isn't in is rejected."""
    user = await register_user()
    resp = await client.get(
        f"/api/retrieval/next-action?course_id={uuid.uuid4()}", headers=user["headers"]
    )
    assert resp.status_code == 403


async def test_session_summary_null_without_a_session(client, register_user, seeded):
    """No attempts yet → null (the client shows no warm close)."""
    user = await register_user()
    await seeded(user["id"])
    resp = await client.get("/api/retrieval/session-summary", headers=user["headers"])
    assert resp.status_code == 200
    assert resp.json() is None


async def test_session_summary_after_an_attempt(client, register_user, seeded, stub_mode):
    """A completed attempt surfaces in the warm close, with its calibration delta."""
    user = await register_user()
    _, concept = await seeded(user["id"])
    nxt = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubapi", "concept_id": str(concept.id)},
    )
    await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": nxt.json()["challenge_id"], "response": "A", "predicted_confidence": 0.3},
    )

    resp = await client.get("/api/retrieval/session-summary", headers=user["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["attempt_count"] == 1
    assert body["concept_count"] == 1
    assert [c["concept_id"] for c in body["firmed"]] == [str(concept.id)]
    assert body["firmed"][0]["concept_text"] == "Photosynthesis"
    # Predicted 0.3, scored 1.0 → underconfident.
    assert body["predicted_count"] == 1
    assert body["calibration_label"] == "underconfident"


async def test_session_summary_enrollment_gate(client, register_user):
    """Scoping to a course the user isn't in is rejected."""
    user = await register_user()
    resp = await client.get(
        f"/api/retrieval/session-summary?course_id={uuid.uuid4()}", headers=user["headers"]
    )
    assert resp.status_code == 403


# ── Conversational modes (/turn) ────────────────────────────────────────────────

class StubConvoMode:
    """A deterministic conversational mode: digs until ``close_after`` user turns."""

    key = "stubconvo"
    conversational = True
    close_after = 2

    async def generate(self, concept, ctx) -> Challenge:
        return Challenge(concept_id=str(concept.id), prompt="Explain it in your words.", payload={"teach": True})

    async def turn(self, concept, history, ctx) -> TurnResult:
        if len(user_turns(history)) >= self.close_after:
            return TurnResult(closed=True, close_reason="dug_enough")
        return TurnResult(closed=False, reply="Why does that happen?")

    async def close(self, concept, history, ctx) -> Outcome:
        return Outcome(score=0.75, grade="good", feedback="solid", detail={"turns": len(user_turns(history))})


@pytest.fixture
def convo_mode():
    mode = StubConvoMode()
    registry.register(mode)
    yield mode
    registry._MODES.pop("stubconvo", None)


async def test_next_flags_conversational(client, register_user, seeded, convo_mode):
    user = await register_user()
    _, concept = await seeded(user["id"])
    nxt = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubconvo", "concept_id": str(concept.id)},
    )
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["conversational"] is True
    assert body["challenge_id"] and body["prompt"]


async def test_turn_digs_then_closes_with_one_graded_attempt(client, register_user, seeded, convo_mode):
    user = await register_user()
    _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubconvo", "concept_id": str(concept.id)},
    )).json()["challenge_id"]

    # First turn digs; confidence is stamped here (captured at open).
    t1 = await client.post(
        "/api/retrieval/turn", headers=user["headers"],
        json={"challenge_id": cid, "message": "it spreads out", "predicted_confidence": 0.5},
    )
    assert t1.status_code == 200, t1.text
    b1 = t1.json()
    assert b1["closed"] is False
    assert b1["reply"] == "Why does that happen?"
    assert b1["turn_count"] == 1

    # Second turn closes: mode grades, one attempt lands, calibration surfaces.
    t2 = await client.post(
        "/api/retrieval/turn", headers=user["headers"],
        json={"challenge_id": cid, "message": "because of probability"},
    )
    assert t2.status_code == 200, t2.text
    b2 = t2.json()
    assert b2["closed"] is True
    assert b2["close_reason"] == "dug_enough"
    assert b2["outcome"]["grade"] == "good"
    assert b2["state"]["reps"] == 1  # exactly one graded attempt over the whole bout
    # Predicted 0.5, scored 0.75 → underconfident by 0.25.
    assert b2["calibration"]["delta"] == pytest.approx(0.25)
    assert b2["calibration"]["label"] == "underconfident"

    # The bout is consumed — replaying the challenge is gone.
    again = await client.post(
        "/api/retrieval/turn", headers=user["headers"], json={"challenge_id": cid, "message": "x"},
    )
    assert again.status_code == 410


async def test_turn_end_closes_immediately(client, register_user, seeded, convo_mode):
    user = await register_user()
    _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubconvo", "concept_id": str(concept.id)},
    )).json()["challenge_id"]
    t = await client.post(
        "/api/retrieval/turn", headers=user["headers"],
        json={"challenge_id": cid, "message": "a bit", "end": True},
    )
    assert t.status_code == 200, t.text
    assert t.json()["closed"] is True
    assert t.json()["close_reason"] == "user_ended"


async def test_turn_cap_closes_the_bout(client, register_user, seeded, convo_mode):
    # A mode that never volunteers to close still stops at MAX_CONVO_TURNS (7).
    convo_mode.close_after = 99
    user = await register_user()
    _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubconvo", "concept_id": str(concept.id)},
    )).json()["challenge_id"]

    last = None
    for i in range(7):
        last = await client.post(
            "/api/retrieval/turn", headers=user["headers"],
            json={"challenge_id": cid, "message": f"point {i}"},
        )
        assert last.status_code == 200, last.text
    body = last.json()
    assert body["closed"] is True
    assert body["close_reason"] == "turn_cap"
    assert body["turn_count"] == 7


async def test_turn_rejects_a_one_shot_challenge(client, register_user, seeded, stub_mode):
    user = await register_user()
    _, concept = await seeded(user["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubapi", "concept_id": str(concept.id)},
    )).json()["challenge_id"]
    resp = await client.post(
        "/api/retrieval/turn", headers=user["headers"], json={"challenge_id": cid, "message": "A"},
    )
    assert resp.status_code == 400


async def test_turn_not_your_conversation_is_403(client, register_user, seeded, convo_mode):
    owner = await register_user()
    intruder = await register_user()
    _, concept = await seeded(owner["id"])
    cid = (await client.post(
        "/api/retrieval/next", headers=owner["headers"],
        json={"mode": "stubconvo", "concept_id": str(concept.id)},
    )).json()["challenge_id"]
    resp = await client.post(
        "/api/retrieval/turn", headers=intruder["headers"], json={"challenge_id": cid, "message": "x"},
    )
    assert resp.status_code == 403


# ── Probe voice-out (server TTS) ─────────────────────────────────────────────

async def test_tts_streams_a_probe(client, register_user, monkeypatch):
    from app.services.audio_generator import audio_generator

    async def fake_stream(text, voice="nova"):
        for part in (b"ID3", b"fake", b"-mp3"):
            yield part

    monkeypatch.setattr(audio_generator, "stream_speech", fake_stream)
    user = await register_user()
    resp = await client.get(
        "/api/retrieval/tts", params={"text": "why does that happen?"}, headers=user["headers"]
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"ID3fake-mp3"


async def test_tts_rejects_blank_text(client, register_user):
    user = await register_user()
    resp = await client.get("/api/retrieval/tts", params={"text": "   "}, headers=user["headers"])
    assert resp.status_code == 400


async def test_tts_requires_auth(client):
    resp = await client.get("/api/retrieval/tts", params={"text": "hi"})
    assert resp.status_code == 401
