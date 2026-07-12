"""
NotesOS - Transcription Service
OpenAI Whisper API integration for speech-to-text.
"""

import httpx
from typing import Dict, Any
from io import BytesIO

from app.config import settings


class TranscriptionService:
    """OpenAI Whisper API for audio transcription."""

    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY
        self.whisper_base = "https://api.openai.com/v1/audio/transcriptions"

    async def transcribe_audio(self, audio_url: str, file_ext: str = "") -> Dict[str, Any]:
        """
        Transcribe audio using OpenAI Whisper API.

        Args:
            audio_url: URL to audio file (must be accessible)
            file_ext:  Original file extension (e.g. ".mp3") so Whisper sees the
                       real container format; defaults to .webm when unknown.

        Returns:
            dict with:
                - text: Transcribed text
                - language: Detected language code
                - duration: Audio duration in seconds (if available)
        """
        # 1. Download audio file from URL
        audio_data = await self._download_audio(audio_url)

        # 2. Send to Whisper API
        transcription = await self._call_whisper_api(audio_data, file_ext=file_ext)

        return {
            "text": transcription.get("text", ""),
            "language": transcription.get("language", "en"),
            "duration": transcription.get("duration"),
        }

    async def _download_audio(self, url: str) -> bytes:
        """Download audio file from URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.content

    async def _call_whisper_api(self, audio_data: bytes, file_ext: str = "") -> Dict[str, Any]:
        """
        Call OpenAI Whisper API with audio data.

        Args:
            audio_data: Raw audio bytes
            file_ext:   Original extension; Whisper sniffs the container from the
                        filename, so pass the real one where known.

        Returns:
            Transcription response from Whisper
        """
        ext = (file_ext or ".webm").lstrip(".").lower()
        # Prepare multipart form data
        files = {
            "file": (f"audio.{ext}", BytesIO(audio_data), f"audio/{ext}"),
        }
        data = {
            "model": "whisper-1",
            "language": "en",  # Can be auto-detected by removing this
            "response_format": "verbose_json",  # Get language + duration
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.whisper_base,
                headers={"Authorization": f"Bearer {self.openai_api_key}"},
                files=files,
                data=data,
                timeout=60.0,  # Transcription can take time
            )
            response.raise_for_status()
            return response.json()


# Singleton instance
transcription_service = TranscriptionService()
