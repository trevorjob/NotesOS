"""
Voice lane (B5) — the live spoken turn: reply streaming, LLM↔TTS overlap, barge-in,
and the off-turn grade recorded append-only.

The lane's three boundaries (reply stream, TTS, grade) are injected so no live model or
audio backend is touched — the same discipline every retrieval mode follows. The default
grade path is exercised by monkeypatching the underlying mode's single LLM method, proving
voice reuses the mode's ``evaluate`` rather than inventing a new grade path.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.models import Concept, Course, CourseEnrollment, Topic, User
from app.models.retrieval import ConceptState, RetrievalAttempt
from app.services.retrieval.modes import Outcome
from app.services.retrieval.ramble_mode import RambleMode
from app.services.voice.lane import VOICE_MODES, VoiceLane
from app.services.voice.protocol import (
    EVT_AUDIO,
    EVT_GRADED,
    EVT_STATE,
    EVT_TOKEN,
    EVT_TURN_DONE,
    STATE_INTERRUPTED,
    STATE_SPEAKING,
    STATE_THINKING,
)
from tests.conftest import unique_phone

NOW = __import__("datetime").datetime(2026, 7, 13, 12, 0, 0)


# ── seeding ─────────────────────────────────────────────────────────────────────

async def _seed_concept(db):
    user = User(email=f"v_{uuid.uuid4().hex[:8]}@t.dev", full_name="V", password_hash="x", phone=unique_phone())
    db.add(user)
    await db.flush()
    course = Course(code=f"C{uuid.uuid4().hex[:5]}", name="Course", created_by=user.id)
    db.add(course)
    await db.flush()
    db.add(CourseEnrollment(user_id=user.id, course_id=course.id))
    topic = Topic(course_id=course.id, title="Krebs Cycle", order_index=0)
    db.add(topic)
    await db.flush()
    concept = Concept(topic_id=topic.id, course_id=course.id, text="citrate synthase", definition="first step", order_index=0)
    db.add(concept)
    await db.flush()
    return user.id, course, concept


def _reply(*tokens):
    async def stream(_text):
        for t in tokens:
            yield t
    return stream


async def _tts(sentence):
    return b"AUDIO:" + sentence.encode()


async def _grade_good(_text):
    return Outcome(score=0.8, grade="good", feedback="Nice — you had the core of it.")


async def _drain(agen):
    return [e async for e in agen]


# ── turn shape: states, tokens, overlapped audio ────────────────────────────────

async def test_turn_emits_states_tokens_audio_then_grade(db_session):
    user_id, _course, concept = await _seed_concept(db_session)
    lane = VoiceLane(
        db_session, user_id=user_id, concept=concept, mode_key="ramble",
        stream_reply=_reply("Nice ", "point. ", "Now ", "consider ", "this."),
        synthesize=_tts, grade=_grade_good,
    )

    events = await _drain(lane.run_turn("citrate is the first intermediate", now=NOW))
    types = [e.type for e in events]

    # thinking before any speech, speaking once the first token lands
    assert types[0] == EVT_STATE and events[0].data["state"] == STATE_THINKING
    assert any(e.type == EVT_STATE and e.data["state"] == STATE_SPEAKING for e in events)
    assert [e.type for e in events if e.type == EVT_TOKEN]  # tokens streamed
    # graded is the terminal event; turn_done precedes it
    assert types[-1] == EVT_GRADED
    assert EVT_TURN_DONE in types and types.index(EVT_TURN_DONE) < types.index(EVT_GRADED)


async def test_audio_is_synthesized_per_sentence_not_per_token(db_session):
    user_id, _course, concept = await _seed_concept(db_session)
    lane = VoiceLane(
        db_session, user_id=user_id, concept=concept, mode_key="ramble",
        stream_reply=_reply("Nice ", "point. ", "Now ", "consider ", "this."),
        synthesize=_tts, grade=_grade_good,
    )
    events = await _drain(lane.run_turn("...", now=NOW))
    audio = [e for e in events if e.type == EVT_AUDIO]
    # Two sentences ("Nice point." / "Now consider this.") → two audio chunks, in order.
    assert len(audio) == 2
    assert [a.data["seq"] for a in audio] == [0, 1]
    assert audio[0].data["b64"]  # base64 payload present


# ── the off-turn grade: append-only, via the engine (recap pattern) ─────────────

async def test_off_turn_grade_records_append_only_attempt(db_session):
    user_id, _course, concept = await _seed_concept(db_session)
    lane = VoiceLane(
        db_session, user_id=user_id, concept=concept, mode_key="ramble",
        stream_reply=_reply("Right. "), synthesize=_tts, grade=_grade_good,
    )
    events = await _drain(lane.run_turn("my recall", now=NOW))

    graded = next(e for e in events if e.type == EVT_GRADED)
    assert graded.data["grade"] == "good" and graded.data["concept_id"] == str(concept.id)

    attempt = await db_session.scalar(select(RetrievalAttempt).where(RetrievalAttempt.concept_id == concept.id))
    assert attempt.mode == "ramble"                       # logged under the real mode key
    assert attempt.challenge["lane"] == "voice"           # marked as coming via the lane
    assert attempt.created_at == NOW
    # ConceptState was derived by the engine, exactly as /attempt would.
    state = await db_session.scalar(select(ConceptState).where(ConceptState.concept_id == concept.id))
    assert state.reps == 1 and state.last_grade == "good"


# ── barge-in: speech stops, the grade still lands ───────────────────────────────

async def test_barge_in_stops_speech_but_still_grades(db_session):
    user_id, _course, concept = await _seed_concept(db_session)
    cancel = asyncio.Event()
    cancel.set()  # user is already talking over the reply before it starts
    lane = VoiceLane(
        db_session, user_id=user_id, concept=concept, mode_key="ramble",
        stream_reply=_reply("This ", "should ", "not ", "be ", "spoken."),
        synthesize=_tts, grade=_grade_good,
    )
    events = await _drain(lane.run_turn("what I said", cancel=cancel, now=NOW))
    types = [e.type for e in events]

    assert not [e for e in events if e.type == EVT_AUDIO]  # nothing was synthesized
    assert any(e.type == EVT_STATE and e.data["state"] == STATE_INTERRUPTED for e in events)
    assert EVT_GRADED in types  # the grade survives the interruption
    count = await db_session.scalar(
        select(func.count(RetrievalAttempt.id)).where(RetrievalAttempt.concept_id == concept.id)
    )
    assert count == 1  # the user's turn was still recorded


# ── the default grade path reuses the mode's evaluate ───────────────────────────

async def test_default_grade_path_reuses_the_mode(db_session, monkeypatch):
    user_id, _course, concept = await _seed_concept(db_session)

    async def fake_analyze(self, _concept, _said, _ctx):
        return {"coverage": 0.95, "covered": ["core"], "missed": [], "feedback": "Solid."}

    monkeypatch.setattr(RambleMode, "_analyze", fake_analyze)

    lane = VoiceLane(  # no grade injected → falls through to registry.get_mode("ramble")
        db_session, user_id=user_id, concept=concept, mode_key="ramble",
        stream_reply=_reply("Yes. "), synthesize=_tts,
    )
    events = await _drain(lane.run_turn("a strong free recall", now=NOW))

    graded = next(e for e in events if e.type == EVT_GRADED)
    assert graded.data["grade"] == "easy"  # score_to_grade(0.95)
    attempt = await db_session.scalar(select(RetrievalAttempt).where(RetrievalAttempt.concept_id == concept.id))
    assert attempt.mode == "ramble"


# ── guardrail: only conversational modes ────────────────────────────────────────

async def test_lane_rejects_objective_modes(db_session):
    user_id, _course, concept = await _seed_concept(db_session)
    assert "quiz" not in VOICE_MODES
    with pytest.raises(ValueError):
        VoiceLane(db_session, user_id=user_id, concept=concept, mode_key="quiz")
