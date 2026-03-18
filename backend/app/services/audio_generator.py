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


# Average MP3 bitrate bytes-per-second for duration estimation (128kbps)
_MP3_BYTES_PER_SECOND = 16_000


class AudioGenerator:
    """Generate TTS audio lessons from consolidated topic knowledge."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"
        self.anthropic_api_key = settings.ANTHROPIC_API_KEY
        self.openai_api_key = settings.OPENAI_API_KEY

    async def generate_script(self, knowledge: TopicKnowledge) -> str:
        """
        Convert a consolidated note into a spoken, conversational audio script.

        Format follows the memory-loop pattern:
          concept → explanation → example → question → pause → answer
        """
        prompt = f"""You are creating an audio study lesson for a student. Convert the following study notes into a natural, spoken audio script.

CONSOLIDATED NOTES:
{knowledge.consolidated_note}

KEY POINTS:
{json.dumps(knowledge.key_points or [], indent=2)}

CONCEPTS:
{json.dumps(knowledge.concepts or [], indent=2)}

Write a spoken audio script that:
1. Opens with a brief intro ("In this lesson, we'll cover...")
2. Covers each key concept using this memory-loop format:
   - State the concept
   - Give a clear explanation
   - Give a simple example
   - Ask a recall question ("Quick question: ...")
   - Pause cue: "[PAUSE 3 SECONDS]"
   - Give the answer
3. Closes with a summary of the 3 most important points

Rules:
- Write exactly as it would be spoken aloud (no markdown, no bullet symbols)
- Use natural transitions ("Now let's look at...", "Moving on to...")
- Keep it between 400-700 words total
- Use [PAUSE 3 SECONDS] for recall pauses
- Return ONLY the script text, no JSON, no extra formatting"""

        try:
            if self.deepseek_api_key:
                return await self._script_via_deepseek(prompt)
            return await self._script_via_claude(prompt)
        except Exception as e:
            print(f"[AUDIO] Script generation failed: {e}")
            raise

    async def generate_audio(self, script: str, voice: str = "nova") -> bytes:
        """
        Convert script text to MP3 audio using OpenAI TTS.

        Args:
            script: Spoken script text
            voice: OpenAI TTS voice (alloy, echo, fable, onyx, nova, shimmer)

        Returns:
            MP3 audio bytes
        """
        # Strip pause cues before sending to TTS
        clean_script = script.replace("[PAUSE 3 SECONDS]", "...").strip()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "tts-1",
                    "input": clean_script,
                    "voice": voice,
                    "response_format": "mp3",
                },
                timeout=120.0,
            )
            response.raise_for_status()
            return response.content

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
