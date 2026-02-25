"""
NotesOS - Vision Transcription Service
Uses OpenAI GPT-4o Vision to transcribe images directly to clean text/markdown.
Replaces the Tesseract + Google Vision + DeepSeek OCR cleaning pipeline for images.
"""

from typing import List
from openai import AsyncOpenAI

from app.config import settings


class VisionTranscribeService:
    """
    Transcribe one or more images using GPT-4o Vision.

    Handles handwritten notes, printed text, diagrams, and mixed content.
    Returns a single combined transcript (markdown-formatted where structure exists).
    """

    SYSTEM_PROMPT = (
        "You are a precise transcription assistant for student study notes. "
        "Extract all text and meaningful content visible in the image(s). "
        "Preserve document structure: use markdown headings, bullet lists, "
        "and numbered lists where they appear in the source. "
        "For handwritten content, transcribe accurately — do not paraphrase or summarise. "
        "If multiple images are provided they form a single document; output one coherent transcript. "
        "Output only the transcript, no preamble or commentary."
    )

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.VISION_MODEL

    async def transcribe_images(self, image_urls: List[str]) -> str:
        """
        Transcribe one or more images to text using GPT-4o Vision.

        Args:
            image_urls: List of publicly accessible image URLs (e.g. Cloudinary).

        Returns:
            Combined transcript string (markdown where applicable).

        Raises:
            ValueError: If no URLs are provided.
            Exception:  Propagates OpenAI API errors.
        """
        if not image_urls:
            raise ValueError("At least one image URL is required")

        # Build content parts: one image_url block per image
        image_parts = [
            {
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "high",  # high fidelity for handwritten notes
                },
            }
            for url in image_urls
        ]

        # Add a trailing text instruction so the model knows what to do
        content_parts = image_parts + [
            {
                "type": "text",
                "text": "Transcribe all text and content from the above image(s).",
            }
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": content_parts},
            ],
            max_tokens=4096,
            temperature=0,  # deterministic transcription
        )

        transcript = response.choices[0].message.content or ""
        return transcript.strip()


# Singleton instance
vision_transcribe = VisionTranscribeService()
