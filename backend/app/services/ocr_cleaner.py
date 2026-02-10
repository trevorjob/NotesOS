"""
NotesOS - OCR Text Cleaner Service
Uses DeepSeek AI to clean OCR errors in handwritten notes.
"""

import json
import httpx
from typing import List, Dict

from app.config import settings


class OCRCleaner:
    """
    Intelligent OCR text cleaning using DeepSeek AI.

    Fixes common OCR errors in handwritten notes:
    - Mixed up words (e.g., "teh" → "the")
    - Unclear letters (e.g., "rn" misread as "m", "cl" as "d")
    - Missing/incorrect punctuation
    - Contextual corrections
    """

    def __init__(self):
        """Initialize DeepSeek API client."""
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_base = "https://api.deepseek.com/v1"
        self.model = "deepseek-chat"

    async def clean_ocr_text(
        self,
        raw_text: str,
        aggressive: bool = True,
        needs_aggressive_cleanup: bool = False,
    ) -> Dict[str, any]:
        """
        Clean OCR text using AI.

        Args:
            raw_text: Raw OCR output from handwritten notes
            aggressive: If True, apply more thorough corrections
            needs_aggressive_cleanup: If True (low OCR confidence), mark unclear sections

        Returns:
            dict with:
                - cleaned_text: Corrected text
                - corrections_made: List of corrections
                - confidence: Overall confidence score (0-1)
        """
        if not settings.ENABLE_OCR_CLEANING:
            return {
                "cleaned_text": raw_text,
                "corrections_made": [],
                "confidence": 1.0,
                "message": "OCR cleaning disabled",
            }

        if not raw_text or len(raw_text.strip()) < 10:
            # Too short to clean meaningfully
            return {
                "cleaned_text": raw_text,
                "corrections_made": [],
                "confidence": 1.0,
                "message": "Text too short for cleaning",
            }

        try:
            prompt = self._build_cleaning_prompt(raw_text, aggressive)
            response = await self._call_deepseek(prompt)
            result = self._parse_response(response)

            return {
                "cleaned_text": result.get("cleaned_text", raw_text),
                "corrections_made": result.get("corrections", []),
                "confidence": result.get("confidence", 0.8),
                "message": "OCR cleaning completed",
            }

        except Exception as e:
            # If cleaning fails, return original text
            return {
                "cleaned_text": raw_text,
                "corrections_made": [],
                "confidence": 0.0,
                "message": f"Cleaning failed: {str(e)}",
            }

    def _build_cleaning_prompt(self, text: str, aggressive: bool) -> str:
        """Build prompt for DeepSeek to clean OCR text."""

        correction_level = "thorough" if aggressive else "conservative"

        return f"""You are an OCR error correction system for handwritten student notes. 
Your job is to fix common OCR mistakes while preserving the original meaning.

Common OCR errors in handwriting:
- Letter confusion: "rn" → "m", "cl" → "d", "vv" → "w"
- Word mixups: "teh" → "the", "adn" → "and"
- Missing spaces: "inthe" → "in the"
- Extra spaces: "t he" → "the"
- Missing punctuation

IMPORTANT RULES:
1. Only fix OBVIOUS errors - don't change content or meaning
2. Preserve technical terms, names, and subject-specific vocabulary
3. Keep the student's voice and phrasing
4. {correction_level} corrections only

OCR TEXT TO CLEAN:
\"\"\"
{text}
\"\"\"

Return JSON in this format:
{{
  "cleaned_text": "the corrected text here",
  "corrections": [
    {{"original": "teh", "corrected": "the", "reason": "common typo"}},
    {{"original": "inthe", "corrected": "in the", "reason": "missing space"}}
  ],
  "confidence": 0.95
}}

RESPOND ONLY WITH VALID JSON, NO OTHER TEXT."""

    async def _call_deepseek(self, prompt: str) -> str:
        """Make API call to DeepSeek."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # Low temperature for consistent corrections
                    "max_tokens": 4000,
                    "stream": False,
                },
                timeout=30.0,
            )

            response.raise_for_status()
            data = response.json()

            return data["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> dict:
        """Parse DeepSeek JSON response."""
        try:
            # Try to find JSON in response (in case there's extra text)
            start = response.find("{")
            end = response.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")

            json_str = response[start:end]
            result = json.loads(json_str)

            return result

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse AI response as JSON: {str(e)}")

    async def suggest_corrections(
        self, text: str, max_suggestions: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get correction suggestions without applying them.
        Useful for showing user what would be changed.

        Returns:
            List of suggested corrections
        """
        result = await self.clean_ocr_text(text, aggressive=True)
        corrections = result.get("corrections_made", [])

        return corrections[:max_suggestions]


# Singleton instance
ocr_cleaner = OCRCleaner()
