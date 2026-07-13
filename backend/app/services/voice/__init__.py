"""
Real-time voice lane (B5) — the premium conversational surface.

A NEW streaming pipeline, deliberately separate from the batch voice workers and from
the retrieval ``/attempt`` contract (which is LOCKED synchronous, text-only — build-guide
§134). Like recap, the lane is an *orchestration*, not a retrieval mode: it holds a live
spoken exchange (STT client-side → LLM reply streamed → TTS overlapped, with barge-in),
and **off-turn** grades what the user said by reusing the underlying mode's ``evaluate``,
recording the result append-only through ``engine.record_attempt``. It never touches
``/attempt`` or the mode Protocol.
"""

from app.services.voice.lane import VoiceLane, VOICE_MODES
from app.services.voice.protocol import OutboundEvent, SentenceBuffer

__all__ = ["VoiceLane", "VOICE_MODES", "OutboundEvent", "SentenceBuffer"]
