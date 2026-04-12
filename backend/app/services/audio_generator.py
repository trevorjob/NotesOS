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
from app.core.logging import get_logger

logger = get_logger(__name__)


# Average MP3 bitrate bytes-per-second for duration estimation (128kbps)
_MP3_BYTES_PER_SECOND = 16_000


class AudioGenerator:
    """Generate TTS audio lessons from consolidated topic knowledge."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"
        self.anthropic_api_key = settings.ANTHROPIC_API_KEY
        self.openai_api_key = settings.OPENAI_API_KEY

    async def generate_script(self, knowledge: TopicKnowledge, topic_name: str) -> str:
        """
        Convert a consolidated note into a spoken, conversational audio script.

        Format follows the memory-loop pattern:
          concept → explanation → example → question → pause → answer
        """
        prompt = f"""You are writing a spoken audio script that a student will listen to 
while walking, commuting, or doing something else with their hands. 
This is the only thing they're doing with their ears right now.

Your voice is a sharp, unhurried person who knows this topic cold and 
genuinely finds it interesting. Not a lecturer. Not a tutor. 
The kind of person who, if you asked them to explain something at a 
coffee shop, would make you feel like you finally got it.

TOPIC: {topic_name}

CONSOLIDATED NOTES:
{knowledge.consolidated_note}

KEY POINTS:
{json.dumps(knowledge.key_points or [], indent=2)}

CONCEPTS:
{json.dumps(knowledge.concepts or [], indent=2)}

═══════════════════════════════════════
STRUCTURE — follow this arc:
═══════════════════════════════════════

HOOK (30–45 seconds)
Don't announce the topic. Don't say "in this lesson we'll cover."
Open with something that makes the listener lean in — a surprising fact, 
a question they can't immediately answer, a contradiction, a real-world 
consequence of this topic. Make them want to know the answer before 
you've explained anything.

CORE CONTENT
Work through the material using the memory-loop format — but vary the 
execution so it doesn't feel like a template repeating itself:

  The loop per concept:
  1. State what the concept is — plainly, no jargon first
  2. Explain it like you're thinking through it out loud
  3. Ground it in something concrete: an analogy, an example, 
     a real-world application, a comparison to something familiar
  4. Ask a recall question — make it feel conversational, 
     not like a quiz ("So here's something to sit with — ...")
  5. [PAUSE]
  6. Give the answer, then add one more thing they didn't know to ask

  Vary the loop:
  - Simple concepts: compress it — don't over-explain the obvious
  - Hard concepts: slow down, use two examples, come back to it later
  - Closely related concepts: contrast them against each other 
    instead of explaining them separately
  - The most important concept in the material: explain it twice — 
    once near the start, once near the end, with different framing

TRANSITIONS
Never use structural transitions like "moving on to" or "next up" or 
"now let's look at." Instead, connect concepts to each other:
  - "This is why X matters — because without it, Y can't happen."
  - "Here's where it gets interesting."
  - "That was the setup. Here's the payoff."
  - "Hold that thought — we'll come back to it."
  - "If you got that, the next part will make a lot of sense."

CLOSING (30–45 seconds)
Don't say "to summarise" or "in conclusion."
Land on the one thing — the single most important idea from everything 
you just covered. Then give a final recall moment: ask a question that 
ties together 2–3 concepts at once. [PAUSE]. Answer it. 
End with something that makes the topic feel alive outside the classroom.

═══════════════════════════════════════
WRITING RULES:
═══════════════════════════════════════

Voice and rhythm:
- Write exactly as it will be spoken — no markdown, no bullet symbols, 
  no headers. Pure prose.
- Vary sentence length deliberately. Short sentences hit hard. 
  Longer sentences carry you through an explanation. Mix them.
- Read every line aloud in your head before writing the next one. 
  If it trips you up, rewrite it.
- Never use a word you wouldn't say naturally in conversation.

Pauses:
- [PAUSE] after every recall question — give the listener time to 
  actually think, not just hear the question.
- [PAUSE] before introducing a genuinely complex idea — 
  let the previous one settle.
- [PAUSE] is a breath, not a quiz buzzer. Use it like one.

Emphasis:
- Use [EMPHASIS] before a word or phrase that must land: 
  "The key word here is [EMPHASIS] gradient."
- Use it sparingly — 2–4 times maximum. If everything is emphasised, 
  nothing is.

Length:
- Target 900–1300 words. That's roughly 6–8 minutes at a natural 
  speaking pace — long enough to cover material properly, 
  short enough to finish on a commute.
- If the material is genuinely simple, stop at 900. 
  Do not pad to hit a word count.
- If the material is complex and rich, go to 1300. 
  Do not compress important ideas to hit a word count.

What this script is NOT:
- Not a podcast with two hosts
- Not a lecture with slides
- Not a summary of the notes read aloud
- Not a quiz with answers
- A single, clear voice working through material in a way that 
  makes it stick

Return ONLY the script. Start immediately with the hook. 
No title, no label, no "here is the script." Just the words."""

        try:
            if self.deepseek_api_key:
                return await self._script_via_deepseek(prompt)
            return await self._script_via_claude(prompt)
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

    async def _script_via_deepseek(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.deepseek_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 1500,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

    async def _script_via_claude(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"].strip()


# Singleton instance
audio_generator = AudioGenerator()
