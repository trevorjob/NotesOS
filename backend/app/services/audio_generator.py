"""
NotesOS - Audio Generator Service
Generates conversational audio lessons from TopicKnowledge using:
  1. DeepSeek/Claude → audio script
  2. OpenAI TTS → MP3 bytes
  3. Cloudinary → uploaded audio file
"""

import json
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import settings
from app.models.knowledge import AudioLens, TopicKnowledge
from app.services.storage import storage_service
from app.services.llm import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)


# Average MP3 bitrate bytes-per-second for duration estimation (128kbps)
_MP3_BYTES_PER_SECOND = 16_000


def _concept_focus_directive(concept_focus: Optional[Dict[str, Any]]) -> str:
    """A personal concept-scoped request narrows the lesson to one concept (docs/
    listen-audio-plan.md §3) — empty string (no-op) when the request is topic-scoped."""
    if not concept_focus:
        return ""
    term = concept_focus.get("term", "")
    definition = concept_focus.get("definition") or ""
    focus = f"{term} — {definition}" if definition else term
    return f"""

SCOPE — ONE CONCEPT, NOT THE WHOLE TOPIC:
The listener asked specifically about {focus}. Use the rest of the note only as supporting
context; don't survey the whole topic. Stay on this concept until it's genuinely landed, then
stop — don't pad outward to cover more ground."""


# Lens directives (docs/listen-audio-plan.md §1/§3) — guidance, not a rigid script, per the
# generative-prompt principle (B13): each nudges judgment in a direction, it doesn't hand the
# model a template to fill in. DEFAULT has no directive — it's today's prompt, untouched.
_LENS_DIRECTIVES: Dict[AudioLens, str] = {
    AudioLens.EXAM_FOCUSED: """

LENS — EXAM-FOCUSED:
The listener is reviewing for an exam, not meeting this material for the first time. Lead with
what's actually testable: the distinctions examiners like to probe, the definitions that get
confused with each other, the edge cases. Skip color and motivation the exam won't ask about.""",
    AudioLens.SLOWER: """

LENS — SLOWER PACE:
The listener wants this to actually sink in, not move fast. Take longer per idea: more restating
in different words, more worked-through reasoning, longer [PAUSE] recall gaps. Simpler sentences.
Cover less ground overall rather than rushing to fit everything in.""",
    AudioLens.WORKED_EXAMPLE: """

LENS — WORKED EXAMPLE:
Narrate an actual worked example from the material step by step — the reasoning at each step, not
just the answer — rather than describing the concept in the abstract. If the material has a
concrete problem or calculation, walk through solving it out loud; this is the version built for
material that doesn't land as pure prose.""",
}


def _instruction_directive(instruction: Optional[str]) -> str:
    """The user's own free-text ask for a personal request — empty when there isn't one."""
    if not instruction:
        return ""
    return f"""

WHAT THE LISTENER SPECIFICALLY ASKED FOR:
"{instruction}"
Shape the lesson around this ask while staying accurate to the material above — don't ignore it,
and don't invent material the notes don't support."""


def _remediation_directive(wrong_answers: Optional[list]) -> str:
    """Remediation (docs/listen-audio-plan.md §6) grounds itself in the listener's actual
    misses rather than re-explaining the concept generically. Falls back to a softer
    directive if the attempt log somehow has nothing usable (still better than silence)."""
    if not wrong_answers:
        return """

LENS — REMEDIATION:
The listener has struggled with this concept before. Don't generically re-explain it — lead
with the misconception that's easy to fall into here and why, then rebuild from there."""

    lines = "\n".join(
        f'- Asked: "{qa["question"]}" — they answered: "{qa["your_answer"]}"' for qa in wrong_answers
    )
    return f"""

LENS — REMEDIATION:
The listener has specifically gotten this wrong before:
{lines}
Don't generically re-explain the concept from scratch — start from what they actually got
wrong and why that answer is wrong, then rebuild the correct understanding from there. This is
a targeted fix for a specific misunderstanding, not a survey of the topic."""


class AudioGenerator:
    """Generate TTS audio lessons from consolidated topic knowledge."""

    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY

    async def generate_script(
        self,
        knowledge: TopicKnowledge,
        topic_name: str,
        *,
        lens: AudioLens = AudioLens.DEFAULT,
        concept_focus: Optional[Dict[str, Any]] = None,
        instruction: Optional[str] = None,
        wrong_answers: Optional[list] = None,
    ) -> str:
        """
        Convert a consolidated note into a spoken, conversational audio script.

        Format follows the memory-loop pattern:
          concept → explanation → example → question → pause → answer

        ``lens``/``concept_focus``/``instruction`` are personal-request additions
        (docs/listen-audio-plan.md Phase 1) layered onto the base prompt as directives,
        never templates — the default lens with no concept/instruction produces the
        exact same prompt this always has.
        """
        prompt = f"""You are writing a spoken audio lesson a student listens to while walking or
commuting — ears only, nothing on screen. Your job is to make THIS material actually stick in
their memory by the time the audio ends. Not "cover" it — make it land.

Your voice is one sharp, unhurried person who knows this topic cold and genuinely finds it
interesting — the person who explains a thing at a coffee shop and you finally get it.
Not a lecturer, not a podcast duo, not the notes read aloud.

TOPIC: {topic_name}

CONSOLIDATED NOTES:
{knowledge.consolidated_note}

KEY POINTS:
{json.dumps(knowledge.key_points or [], indent=2)}

CONCEPTS:
{json.dumps(knowledge.concepts or [], indent=2)}

HOW TO MAKE IT STICK (judgment, not a formula):
- Let THIS material decide the shape. There is no fixed arc to fill in and no per-concept loop
  to repeat — a rhythm the listener can predict is a rhythm they stop hearing. Work through the
  ideas the way they actually connect, spending time in proportion to difficulty: compress the
  obvious, slow down and re-approach the hard thing, contrast ideas that are easy to confuse
  rather than explaining each in isolation.
- Memory is built by retrieval, not exposure. Land an idea, then genuinely make the listener
  reach for it — a real question they have to answer in their head, [PAUSE], then the answer.
  Do this where recall actually matters, never on a schedule.
- Connect ideas by meaning, never by structural filler. "This is why X matters — without it Y
  can't happen" carries the listener; "moving on to", "next up", "now let's look at", "to
  summarise", "in conclusion" are dead air. Never announce the topic or say "in this lesson".

OPEN FROM THIS MATERIAL, NOT FROM A TEMPLATE:
- This is one of many lessons the student will hear. If every lesson opens the same way — a
  generic surprising fact, a rhetorical question — they all blur into one. Find the entry point
  that only THIS topic has: the specific tension, consequence, or surprise inside this material.
  Don't reach for a stock opening move, and don't open two different topics the same way.
- Close on the single most important idea from what you covered, then one last real recall
  moment tying a couple of ideas together. [PAUSE], answer it, and leave the topic feeling alive
  outside the classroom — without ever saying "to summarise".

SPOKEN-WORD RULES (real constraints, not style):
- Write exactly as spoken: pure prose, no markdown, no headings, no bullet symbols. If a line
  trips the tongue read aloud, rewrite it. Vary sentence length deliberately — short lines hit,
  long lines carry. Never use a word you wouldn't say out loud.
- [PAUSE] is the ONLY control token. Put it after a recall question (real thinking time) and
  before a genuinely hard idea (let the last one settle). It's a breath, not a buzzer. Do not
  write any other bracketed markers.
- Length follows the material: 900–1300 words (~6–8 min). Stop at 900 if it's genuinely simple;
  go to 1300 if it's rich. Never pad to a count, never compress an important idea to hit one.

Before you finish, check your own script: does the opening come from THIS topic specifically, or
could it head any lesson? Is any stretch running on autopilot — a predictable loop, a filler
transition, a recall question asked out of habit? If so, rewrite that part."""

        prompt += _concept_focus_directive(concept_focus)
        if lens == AudioLens.REMEDIATION:
            prompt += _remediation_directive(wrong_answers)
        else:
            prompt += _LENS_DIRECTIVES.get(lens, "")
        prompt += _instruction_directive(instruction)
        prompt += """

Return ONLY the script — start straight in with the first line, no title, no label."""

        try:
            # Higher temperature than the default: spoken lessons need variety between topics,
            # and a low temperature is part of why every script used to open the same way.
            return await call_llm(prompt, task="audio_script", temperature=0.8, max_tokens=4000, timeout=60.0)
        except Exception:
            logger.error("Audio script generation failed", exc_info=True)
            raise

    async def generate_audio(self, script: str, voice: str = "nova") -> bytes:
        """
        Convert script text to MP3 audio using OpenAI TTS.
        Splits into ≤4096-char chunks at sentence boundaries to stay within the API limit.

        Args:
            script: Spoken script text
            voice: OpenAI TTS voice (alloy, echo, fable, onyx, nova, shimmer)

        Returns:
            MP3 audio bytes (chunks concatenated)
        """
        clean_script = script.replace("[PAUSE 3 SECONDS]", "...").replace("[PAUSE]", "...").strip()
        chunks = self._chunk_script(clean_script)

        async with httpx.AsyncClient() as client:
            parts = []
            for chunk in chunks:
                response = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "tts-1",
                        "input": chunk,
                        "voice": voice,
                        "response_format": "mp3",
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                parts.append(response.content)
            return b"".join(parts)

    async def stream_speech(self, text: str, voice: str = "nova"):
        """Stream MP3 audio for a short text — yields bytes as OpenAI produces them.

        For the real-time probe voice-out (conversational modes): playback can start before
        the whole clip is done, no server-side buffering. Single-shot (no sentence chunking) —
        callers bound the length.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": "tts-1", "input": text, "voice": voice, "response_format": "mp3"},
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    @staticmethod
    def _chunk_script(text: str, limit: int = 4000) -> list[str]:
        """Split text into chunks ≤ limit chars, breaking at sentence boundaries."""
        sentences = []
        for sentence in text.replace("\n", " ").split(". "):
            sentence = sentence.strip()
            if sentence:
                sentences.append(sentence if sentence.endswith(".") else sentence + ".")

        chunks = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 > limit:
                if current:
                    chunks.append(current.strip())
                current = sentence
            else:
                current = (current + " " + sentence).strip() if current else sentence

        if current:
            chunks.append(current.strip())
        return chunks

    async def upload_audio(
        self, audio_bytes: bytes, artifact_id: str
    ) -> Tuple[str, int]:
        """
        Upload MP3 bytes to Cloudinary.

        Keyed by ``artifact_id`` (not scope_ref/topic_id) — a topic can now have several
        artifacts (global default + personal lens requests), and keying by topic would
        make concurrent generations overwrite each other's file at the same public_id.

        Returns:
            (audio_url, duration_seconds)
        """
        result = await storage_service.upload_file(
            file=audio_bytes,
            folder="audio_lessons",
            resource_type="raw",
            public_id=f"audio_{artifact_id}.mp3",
        )
        url = result["url"]
        # Estimate duration from file size
        duration = max(1, len(audio_bytes) // _MP3_BYTES_PER_SECOND)
        return url, duration

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------



# Singleton instance
audio_generator = AudioGenerator()
