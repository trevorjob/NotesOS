"""
NotesOS - Audio Generator Service
Generates conversational audio lessons from TopicKnowledge using:
  1. DeepSeek/Claude → audio script
  2. OpenAI TTS → MP3 bytes
  3. Cloudinary → uploaded audio file
"""

import json
from typing import Any, Dict, Tuple

import httpx

from app.config import settings
from app.models.knowledge import TopicKnowledge
from app.services.storage import storage_service
from app.services.llm import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)


# Average MP3 bitrate bytes-per-second for duration estimation (128kbps)
_MP3_BYTES_PER_SECOND = 16_000


class AudioGenerator:
    """Generate TTS audio lessons from consolidated topic knowledge."""

    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY

    async def generate_script(self, knowledge: TopicKnowledge, topic_name: str) -> str:
        """
        Convert a consolidated note into a spoken, conversational audio script.

        Format follows the memory-loop pattern:
          concept → explanation → example → question → pause → answer
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
transition, a recall question asked out of habit? If so, rewrite that part.

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
        self, audio_bytes: bytes, topic_id: str
    ) -> Tuple[str, int]:
        """
        Upload MP3 bytes to Cloudinary.

        Returns:
            (audio_url, duration_seconds)
        """
        result = await storage_service.upload_file(
            file=audio_bytes,
            folder="audio_lessons",
            resource_type="raw",
            public_id=f"topic_{topic_id}.mp3",
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
