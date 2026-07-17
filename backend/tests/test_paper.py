"""
Paper substrate (B8) — handwriting photo → transcription → confirm → text /attempt.

Service tests pin the one seam (data-URL encoding into the existing vision transcriber,
validation limits, the uncertainty flags that drive the confirm beat). API tests pin the
endpoint shape (``requires_confirmation`` always true), the limit mapping, auth, and the
fairness contract end-to-end: the graded attempt records the **user-confirmed** text with
``challenge.origin == "paper"`` — on the single-concept flow and on a handwritten brain
dump (the paper-native pattern). The vision boundary is monkeypatched throughout.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Concept, Course, CourseEnrollment, Topic
from app.models.retrieval import RetrievalAttempt
from app.services import paper
from app.services.redis_client import redis_client
from app.services.retrieval import recap, registry
from app.services.retrieval.modes import Challenge, Outcome

PAGE = b"\xff\xd8\xff fake-jpeg-bytes"  # content is irrelevant; the boundary is stubbed


@pytest.fixture
def vision(monkeypatch):
    """Stub the vision seam; capture the data URLs it was handed."""
    seen: dict = {}

    def install(text="The Krebs cycle produces ATP."):
        async def fake(urls):
            seen["urls"] = urls
            return text
        monkeypatch.setattr(paper, "_vision_transcribe", fake)
        return seen

    return install


# ── the substrate ───────────────────────────────────────────────────────────────

async def test_transcribe_answer_encodes_pages_as_ephemeral_data_urls(vision):
    seen = vision("dumped everything...")

    result = await paper.transcribe_answer([("p1.jpg", PAGE), ("p2.png", PAGE)])

    assert result.text == "dumped everything..."
    assert result.page_count == 2
    assert seen["urls"][0].startswith("data:image/jpeg;base64,")
    assert seen["urls"][1].startswith("data:image/png;base64,")


async def test_uncertainty_flags_drive_the_confirm_beat(vision):
    vision("mitochondria [?] then [illegible section — approx 2 lines]")
    result = await paper.transcribe_answer([("p.jpg", PAGE)])
    assert result.has_uncertain and result.has_illegible

    vision("perfectly clear handwriting")
    result = await paper.transcribe_answer([("p.jpg", PAGE)])
    assert not result.has_uncertain and not result.has_illegible


async def test_rejects_unsupported_type_empty_and_oversize(vision, monkeypatch):
    vision()
    with pytest.raises(paper.PaperValidationError) as exc:
        await paper.transcribe_answer([("notes.pdf", PAGE)])   # a doc is capture's job
    assert exc.value.status == 415

    with pytest.raises(paper.PaperValidationError) as exc:
        await paper.transcribe_answer([("p.jpg", b"")])
    assert exc.value.status == 400

    monkeypatch.setattr(paper, "MAX_ANSWER_IMAGE_BYTES", 4)
    with pytest.raises(paper.PaperValidationError) as exc:
        await paper.transcribe_answer([("p.jpg", PAGE)])
    assert exc.value.status == 413


async def test_rejects_too_many_pages_and_no_pages(vision):
    vision()
    with pytest.raises(paper.PaperValidationError):
        await paper.transcribe_answer([])
    pages = [(f"p{i}.jpg", PAGE) for i in range(paper.MAX_ANSWER_PAGES + 1)]
    with pytest.raises(paper.PaperValidationError):
        await paper.transcribe_answer(pages)


# ── API: the endpoint + the fairness contract end-to-end ────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def _fresh_redis():
    """Reset the singleton Redis connection per test (function-scoped event loop)."""
    redis_client._client = None
    yield
    if redis_client._client is not None:
        await redis_client._client.aclose()
        redis_client._client = None


class StubPaperMode:
    """Echo-grader: records whatever text reached evaluate (the fairness probe)."""

    key = "stubpaper"

    async def generate(self, concept, ctx) -> Challenge:
        return Challenge(concept_id=str(concept.id), prompt="Explain it.", payload={})

    async def evaluate(self, concept, challenge, response, ctx) -> Outcome:
        return Outcome(score=0.8, grade="good", feedback="ok")


@pytest.fixture
def stub_mode():
    registry.register(StubPaperMode())
    yield
    registry._MODES.pop("stubpaper", None)


@pytest_asyncio.fixture
async def seeded(db_session):
    async def _make(user_id):
        uid = uuid.UUID(user_id)
        course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="C", created_by=uid)
        db_session.add(course)
        await db_session.flush()
        db_session.add(CourseEnrollment(user_id=uid, course_id=course.id))
        topic = Topic(course_id=course.id, title="Respiration", order_index=0)
        db_session.add(topic)
        await db_session.flush()
        concept = Concept(topic_id=topic.id, course_id=course.id, text="Krebs cycle", order_index=0)
        db_session.add(concept)
        await db_session.flush()
        await db_session.commit()
        return course, topic, concept

    return _make


async def test_transcribe_endpoint_returns_confirm_shape(client, register_user, vision):
    vision("what I wrote [?]")
    user = await register_user()

    resp = await client.post(
        "/api/retrieval/transcribe",
        headers=user["headers"],
        files=[("files", ("page1.jpg", PAGE, "image/jpeg"))],
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["transcription"] == "what I wrote [?]"
    assert body["requires_confirmation"] is True  # the confirm beat, in the contract
    assert body["has_uncertain"] is True and body["page_count"] == 1


async def test_transcribe_endpoint_maps_validation_to_http(client, register_user, vision):
    vision()
    user = await register_user()
    resp = await client.post(
        "/api/retrieval/transcribe",
        headers=user["headers"],
        files=[("files", ("essay.docx", PAGE, "application/octet-stream"))],
    )
    assert resp.status_code == 415


async def test_transcribe_requires_auth(client, vision):
    vision()
    resp = await client.post(
        "/api/retrieval/transcribe", files=[("files", ("p.jpg", PAGE, "image/jpeg"))]
    )
    assert resp.status_code in (401, 403)


async def test_confirmed_text_grades_with_paper_origin(client, register_user, seeded, stub_mode, db_session):
    """The full fairness loop: transcribe → user corrects → /attempt grades the confirmed text."""
    user = await register_user()
    _, _, concept = await seeded(user["id"])

    nxt = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubpaper", "concept_id": str(concept.id)},
    )
    assert nxt.status_code == 200, nxt.text

    confirmed = "the corrected text I actually wrote"  # user fixed OCR's guess
    att = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={
            "challenge_id": nxt.json()["challenge_id"],
            "response": confirmed,
            "answer_origin": "paper",
        },
    )
    assert att.status_code == 200, att.text

    attempt = await db_session.scalar(
        select(RetrievalAttempt).where(RetrievalAttempt.concept_id == concept.id)
    )
    assert attempt.mode == "stubpaper"                    # the real mode key
    assert attempt.challenge["origin"] == "paper"         # the paper marker
    assert attempt.response["raw"] == confirmed           # graded what the user confirmed


async def test_handwritten_dump_carries_paper_origin(client, register_user, seeded, db_session, monkeypatch):
    """A photographed brain dump — the paper-native pattern B8 exists for."""
    user = await register_user()
    _, topic, concept = await seeded(user["id"])

    async def fake_analyze(concepts, said):
        return [
            {"index": i + 1, "coverage": 1.0, "covered": ["ok"], "missed": [], "feedback": "nice"}
            for i in range(len(concepts))
        ]

    monkeypatch.setattr(recap, "_analyze_recall", fake_analyze)

    cid = (
        await client.post(
            "/api/retrieval/dump/next", headers=user["headers"], json={"topic_id": str(topic.id)}
        )
    ).json()["challenge_id"]
    att = await client.post(
        "/api/retrieval/dump/attempt", headers=user["headers"],
        json={"challenge_id": cid, "response": "everything, from paper", "answer_origin": "paper"},
    )
    assert att.status_code == 200, att.text

    attempt = await db_session.scalar(
        select(RetrievalAttempt).where(RetrievalAttempt.concept_id == concept.id)
    )
    assert attempt.mode == "brain_dump"
    assert attempt.challenge["origin"] == "paper"


async def test_answer_origin_rejects_unknown_values(client, register_user, seeded, stub_mode):
    user = await register_user()
    _, _, concept = await seeded(user["id"])
    nxt = await client.post(
        "/api/retrieval/next", headers=user["headers"],
        json={"mode": "stubpaper", "concept_id": str(concept.id)},
    )
    resp = await client.post(
        "/api/retrieval/attempt", headers=user["headers"],
        json={"challenge_id": nxt.json()["challenge_id"], "response": "x", "answer_origin": "carrier_pigeon"},
    )
    assert resp.status_code == 422  # closed vocabulary — a marker, not a free field
