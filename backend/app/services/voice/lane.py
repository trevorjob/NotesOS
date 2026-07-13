"""
The voice-lane turn orchestration — where STT, LLM, and TTS overlap and the grade
falls out off-turn.

One ``VoiceLane`` backs one live session over one concept. A turn is: the user's
(client-transcribed) text arrives, and the lane simultaneously
  1. **streams a spoken reply** — LLM prose token-by-token, with TTS synthesized and
     emitted *per sentence* so audio starts before the reply finishes (the overlap), and
  2. **grades the turn off-turn** — reusing the underlying mode's ``evaluate`` (ramble /
     teach), recorded append-only via ``engine.record_attempt`` exactly like recap.

The grade is about what the *user* said, so it survives **barge-in**: interrupting the
reply stops the speech, never the grade. This is why voice can be a delivery lane over an
existing AI-graded mode without touching ``/attempt`` or the mode Protocol (build-guide
§134): the conversational reply is prose (streamable), the grade is structured and parsed
whole, off the spoken turn.

Every external boundary — reply stream, TTS, grade — is injectable so the whole lane is
testable without a live model or audio backend (the same discipline every mode follows).
"""

import asyncio
import base64
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm import call_llm_stream
from app.services.retrieval import engine, recognition, registry
from app.services.retrieval.modes import Challenge, ModeContext, Outcome
from app.services.voice.protocol import (
    EVT_AUDIO,
    EVT_ERROR,
    EVT_GRADED,
    EVT_STATE,
    EVT_TOKEN,
    EVT_TURN_DONE,
    STATE_INTERRUPTED,
    STATE_SPEAKING,
    STATE_THINKING,
    OutboundEvent,
    SentenceBuffer,
)

# Voice is a *conversation*, so only the free-response AI-graded modes belong here.
# Quiz / pretest are objective and offline-capable — they have no place in a spoken lane.
VOICE_MODES = frozenset({"ramble", "teach"})

# The spoken tutor persona — brand voice (§Design): warm, brief, a sharp study partner.
# Kept short on purpose: this is speech, not an essay.
_VOICE_SYSTEM = (
    "You are a warm, sharp study partner talking with a student out loud about one "
    "concept. Keep replies short and conversational — a sentence or two, the way a "
    "person actually speaks. React to what they just said: affirm what they got, nudge "
    "gently at what they missed, and keep them talking. Never lecture. Never list."
)

# Type aliases for the injectable boundaries.
_StreamReply = Callable[[str], AsyncIterator[str]]
_Synthesize = Callable[[str], Awaitable[bytes]]
_Grade = Callable[[str], Awaitable[Outcome]]


class VoiceLane:
    """A live spoken exchange over one concept, grading each turn off-turn."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        user_id: Any,
        concept: Any,
        mode_key: str,
        stream_reply: Optional[_StreamReply] = None,
        synthesize: Optional[_Synthesize] = None,
        grade: Optional[_Grade] = None,
    ) -> None:
        if mode_key not in VOICE_MODES:
            raise ValueError(
                f"voice lane supports {sorted(VOICE_MODES)}, not {mode_key!r} "
                "(objective modes are offline/synchronous, not conversational)"
            )
        self.db = db
        self.user_id = user_id
        self.concept = concept
        self.mode_key = mode_key
        self._stream_reply_fn = stream_reply
        self._synthesize_fn = synthesize
        self._grade_fn = grade
        # Rolling conversation so replies stay coherent across turns in one session.
        self._history: list[dict[str, str]] = []

    # ── the turn ────────────────────────────────────────────────────────────────

    async def run_turn(
        self,
        user_text: str,
        *,
        cancel: Optional[asyncio.Event] = None,
        now=None,
    ) -> AsyncIterator[OutboundEvent]:
        """Run one turn: stream the spoken reply while grading off-turn.

        Grading starts immediately in the background so it overlaps the speech and
        completes even if the user barges in. ``cancel`` (set by the endpoint on a
        ``barge_in`` frame) stops the reply between tokens; the grade is unaffected.
        Yields ``state`` → ``token``/``audio`` … → ``turn_done`` → ``graded``.
        """
        cancel = cancel or asyncio.Event()
        grade_task = asyncio.create_task(self._grade_and_record(user_text, now))

        try:
            async for event in self._speak(user_text, cancel):
                yield event
        except Exception as exc:  # a reply/TTS failure must not lose the graded attempt
            yield OutboundEvent(EVT_ERROR, {"message": f"reply failed: {exc}"})

        yield OutboundEvent(EVT_TURN_DONE, {"interrupted": cancel.is_set()})

        try:
            yield OutboundEvent(EVT_GRADED, await grade_task)
        except Exception as exc:  # pragma: no cover - defensive; grading is best-effort
            yield OutboundEvent(EVT_ERROR, {"message": f"grade failed: {exc}"})

    async def _speak(
        self, user_text: str, cancel: asyncio.Event
    ) -> AsyncIterator[OutboundEvent]:
        """Stream the reply prose, synthesizing + emitting audio per sentence."""
        yield OutboundEvent(EVT_STATE, {"state": STATE_THINKING})

        buffer = SentenceBuffer()
        reply_parts: list[str] = []
        seq = 0
        speaking = False

        async for token in self._reply_stream(user_text):
            if cancel.is_set():
                break
            if not speaking:
                speaking = True
                yield OutboundEvent(EVT_STATE, {"state": STATE_SPEAKING})
            reply_parts.append(token)
            yield OutboundEvent(EVT_TOKEN, {"text": token})
            for sentence in buffer.feed(token):
                if cancel.is_set():
                    break
                yield await self._audio_event(sentence, seq)
                seq += 1

        if not cancel.is_set():
            tail = buffer.flush()
            if tail:
                yield await self._audio_event(tail, seq)

        if cancel.is_set():
            yield OutboundEvent(EVT_STATE, {"state": STATE_INTERRUPTED})

        # Record the exchange so multi-turn stays coherent (barge-in still "said" it).
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": "".join(reply_parts)})

    async def _audio_event(self, sentence: str, seq: int) -> OutboundEvent:
        audio = await self._synthesize(sentence)
        return OutboundEvent(
            EVT_AUDIO, {"seq": seq, "b64": base64.b64encode(audio).decode("ascii")}
        )

    # ── off-turn grade (the recap pattern: append-only via the engine) ────────────

    async def _grade_and_record(self, user_text: str, now) -> dict:
        """Grade the user's turn and record it append-only — never through /attempt."""
        outcome = await self._grade(user_text)
        result = await engine.record_attempt(
            self.db,
            user_id=self.user_id,
            concept_id=self.concept.id,
            mode=self.mode_key,
            outcome=outcome,
            challenge={"lane": "voice", "mode": self.mode_key},
            response={"raw": user_text},
            now=now,
            created_at=now,  # log the turn at its review time (None → real now, online)
        )
        # Same seam recap/‌/attempt fire — beneficiary resolution, no per-attempt delivery.
        await recognition.on_attempt(
            self.db, attempt=result.attempt, concept=self.concept, learner_id=self.user_id
        )
        return {
            "concept_id": str(self.concept.id),
            "score": outcome.score,
            "grade": outcome.grade,
            "feedback": outcome.feedback,
        }

    # ── injectable boundaries (defaults wire the real backends) ───────────────────

    async def _reply_stream(self, user_text: str) -> AsyncIterator[str]:
        if self._stream_reply_fn is not None:
            async for token in self._stream_reply_fn(user_text):
                yield token
            return
        messages = [
            {"role": "system", "content": self._reply_system()},
            *self._history,
            {"role": "user", "content": user_text},
        ]
        async for delta in call_llm_stream(
            "", task="voice_chat", messages=messages, temperature=0.6, max_tokens=400, timeout=45.0
        ):
            yield delta

    def _reply_system(self) -> str:
        concept = self.concept
        defn = f" ({concept.definition})" if getattr(concept, "definition", None) else ""
        return f"{_VOICE_SYSTEM}\n\nThe concept in focus: {concept.text}{defn}."

    async def _synthesize(self, sentence: str) -> bytes:
        if self._synthesize_fn is not None:
            return await self._synthesize_fn(sentence)
        # Lazy import: the TTS backend is only needed on the live path, never in tests.
        from app.services.audio_generator import AudioGenerator

        return await AudioGenerator().generate_audio(sentence)

    async def _grade(self, user_text: str) -> Outcome:
        if self._grade_fn is not None:
            return await self._grade_fn(user_text)
        mode = registry.get_mode(self.mode_key)
        challenge = Challenge(concept_id=str(self.concept.id), prompt="(voice)", payload={"lane": "voice"})
        ctx = ModeContext(db=self.db, user_id=self.user_id, extra={"lane": "voice"})
        return await mode.evaluate(self.concept, challenge, user_text, ctx)
