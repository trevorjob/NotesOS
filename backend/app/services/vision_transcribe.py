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

    SYSTEM_PROMPT = """You are transcribing student study materials — handwritten notes, 
printed slides, whiteboard photos, and lecture documents. Your output feeds 
directly into an AI that will generate study summaries and quizzes, so 
completeness and accuracy matter more than polish.

CORE RULES:
- Transcribe exactly what is written. Do not paraphrase, summarise, 
  correct grammar, or reword anything.
- Preserve the author's abbreviations and shorthand as-is 
  (e.g. "w/" stays "w/", "bc" stays "bc").
- Do not add explanations, preamble, or commentary. Output only the transcript.

STRUCTURE:
- Reproduce the visual hierarchy using markdown: # for main headings, 
  ## for subheadings, bullet points and numbered lists where they appear.
- If there are no clear headings but content is clearly grouped into 
  sections, infer a simple structure — add a ## heading that describes 
  the section rather than outputting a flat wall of text.
- Preserve underlines and circled/boxed text by bolding them: **like this**
- Preserve arrows and connectors as → or ←

SPECIAL CONTENT:
- Mathematical equations: use LaTeX inline notation where possible 
  ($E = mc^2$), or write them out plainly if LaTeX is ambiguous.
- Chemical formulas: use standard notation (H₂O, CO₂).
- Tables: reproduce using markdown table syntax.
- Diagrams and drawings: describe briefly in italics on their own line: 
  *[Diagram: arrow showing X flowing into Y]*
- Graphs: note axes and key data points: 
  *[Graph: X-axis = time, Y-axis = concentration, curve peaks at t=3]*

HANDWRITING HANDLING:
- If a word is unclear but you can make a reasonable inference from context, 
  transcribe your best guess followed by [?]: "mitochondria [?]"
- If a word or phrase is completely illegible, write [illegible] in its place.
- If an entire section is too unclear to transcribe, write 
  [illegible section — approx N lines]
- Never silently skip content. A flagged gap is more useful than a clean 
  transcript with missing information.

MULTIPLE IMAGES:
- Treat all images as pages of a single continuous document.
- Maintain reading order (assume left-to-right, top-to-bottom unless 
  the layout clearly indicates otherwise).
- If a sentence or bullet clearly continues from one image to the next, 
  join them naturally — do not add a page break marker.
- If the page order is ambiguous, note it once at the top: 
  *[Note: page order uncertain — transcribed in order provided]*

Output only the transcript. Start immediately with the content."""
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
