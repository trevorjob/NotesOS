"""
The voice-lane wire protocol + the sentence segmenter that enables LLM↔TTS overlap.

The lane speaks a small, JSON-friendly event vocabulary. **Inbound** (client → server)
frames are plain dicts the WS endpoint parses; **outbound** frames are ``OutboundEvent``s
the lane yields, which the endpoint serialises to JSON. Transcription is client-side
(build-guide §134), so inbound audio never reaches the server — only text + turn signals.

``SentenceBuffer`` is the overlap mechanism: as reply tokens stream in, it emits each
sentence the instant its terminator arrives, so TTS can start on sentence one while the
LLM is still generating sentence two.
"""

import re
from dataclasses import dataclass, field

# ── outbound event types (server → client) ──────────────────────────────────────
EVT_STATE = "state"          # a lifecycle transition (see STATE_*)
EVT_TOKEN = "token"          # a reply prose delta (streamed, spoken)
EVT_AUDIO = "audio"          # one synthesized TTS chunk (a sentence), base64 mp3
EVT_TURN_DONE = "turn_done"  # the spoken reply finished (or was interrupted)
EVT_GRADED = "graded"        # the off-turn grade, after the append-only attempt is recorded
EVT_ERROR = "error"          # something failed mid-turn (best-effort; never fatal)

# ── lifecycle states (system-spec §14.5) ────────────────────────────────────────
STATE_LISTENING = "listening"      # user is speaking
STATE_THINKING = "thinking"        # reply is being generated, nothing spoken yet
STATE_SPEAKING = "speaking"        # reply is streaming out as audio
STATE_INTERRUPTED = "interrupted"  # user barged in — speech stopped, back to listening
STATE_DONE = "done"                # the session ended

# ── inbound event types (client → server) ───────────────────────────────────────
IN_START = "start"              # open the session: {concept_id, mode}
IN_SPEECH_FINAL = "speech_final"  # the user's turn ended (client VAD endpoint): {text}
IN_BARGE_IN = "barge_in"        # the user started talking over the reply → cancel it
IN_END = "end"                  # close the session


@dataclass(frozen=True)
class OutboundEvent:
    """One frame the lane emits toward the client. ``data`` is JSON-serialisable."""

    type: str
    data: dict = field(default_factory=dict)


# Sentence terminators — end of a clause worth speaking as one TTS unit.
_TERMINATOR = re.compile(r"[.!?\n]")


class SentenceBuffer:
    """Accumulates streamed tokens, emitting complete sentences as they close.

    ``feed`` returns the sentences that completed on this token (usually zero or one);
    ``flush`` returns whatever tail is left when the stream ends. This is what lets the
    lane synthesize and emit audio for sentence *n* while the LLM is still producing
    sentence *n+1* — the overlap the spec calls for.
    """

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, token: str) -> list[str]:
        self._buf += token
        out: list[str] = []
        while True:
            match = _TERMINATOR.search(self._buf)
            if not match:
                break
            cut = match.end()
            sentence = self._buf[:cut].strip()
            self._buf = self._buf[cut:]
            if sentence:
                out.append(sentence)
        return out

    def flush(self) -> str:
        """Return and clear any trailing partial sentence (no terminator seen)."""
        tail = self._buf.strip()
        self._buf = ""
        return tail
