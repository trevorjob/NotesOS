"""
NotesOS - Hybrid OCR Service
Implements cost-optimized handwritten note transcription:
- Tesseract OCR (free) → Google Vision (fallback when confidence < 65%)
- DeepSeek LLM cleanup (always)
"""

import io
from typing import Dict, Tuple, List
from PIL import Image
import pytesseract

from app.config import settings


class HybridOCR:
    """
    Hybrid OCR pipeline for handwritten notes.

    Flow:
    1. Image preprocessing (grayscale, contrast)
    2. Tesseract OCR (free) with confidence scoring
    3. If confidence < threshold: fallback to Google Vision
    4. DeepSeek LLM cleanup (always)
    """

    # Confidence thresholds
    GOOGLE_VISION_THRESHOLD = 0.65  # Below this → use Google Vision
    LOW_CONFIDENCE_THRESHOLD = 0.40  # Below this → mark as [unclear]

    def __init__(self):
        """Initialize OCR services."""
        self.google_vision_client = None
        self._init_google_vision()

    def _init_google_vision(self):
        """Initialize Google Vision client if credentials are available."""
        if settings.GOOGLE_VISION_ENABLED:
            try:
                from google.cloud import vision

                self.google_vision_client = vision.ImageAnnotatorClient()
            except Exception:
                # Google Vision not available, will use Tesseract only
                self.google_vision_client = None

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR results.

        Steps:
        - Convert to grayscale
        - Enhance contrast
        - Apply threshold (binarization)
        """
        from PIL import ImageEnhance, ImageFilter

        # Convert to grayscale
        if image.mode != "L":
            image = image.convert("L")

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Slight sharpening
        image = image.filter(ImageFilter.SHARPEN)

        return image

    async def extract_text_with_confidence(self, image_bytes: bytes) -> Dict[str, any]:
        """
        Extract text from image with confidence scoring.
        Uses hybrid OCR approach.

        Returns:
            dict with:
                - text: Extracted text
                - confidence: Average confidence score (0-1)
                - provider: 'tesseract' or 'google_vision'
                - word_confidences: List of (word, confidence) tuples
        """
        # Open and preprocess image
        image = Image.open(io.BytesIO(image_bytes))
        processed_image = self.preprocess_image(image)

        # Step 1: Try Tesseract OCR with confidence data
        tesseract_result = self._tesseract_ocr_with_confidence(processed_image)

        # Step 2: Check if we should fallback to Google Vision
        if (
            tesseract_result["confidence"] < self.GOOGLE_VISION_THRESHOLD
            and self.google_vision_client is not None
            and settings.GOOGLE_VISION_ENABLED
        ):
            # Fallback to Google Vision
            google_result = await self._google_vision_ocr(image_bytes)

            if google_result["confidence"] > tesseract_result["confidence"]:
                return google_result

        return tesseract_result

    def _tesseract_ocr_with_confidence(self, image: Image.Image) -> Dict[str, any]:
        """
        Run Tesseract OCR and get word-level confidence scores.

        Returns:
            dict with text, confidence, provider, word_confidences
        """
        # Get detailed data including confidence
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            config="--psm 6",  # Uniform block of text
        )

        # Extract words and confidences
        word_confidences: List[Tuple[str, float]] = []
        words = []

        for i, conf in enumerate(data["conf"]):
            word = data["text"][i].strip()
            if word and conf != -1:  # -1 means no confidence (not a word)
                # Tesseract confidence is 0-100, convert to 0-1
                confidence = conf / 100.0
                word_confidences.append((word, confidence))
                words.append(word)

        # Calculate weighted average confidence
        overall_confidence = self._calculate_weighted_confidence(word_confidences)

        # Reconstruct text with proper spacing
        full_text = self._reconstruct_text(data)

        return {
            "text": full_text,
            "confidence": overall_confidence,
            "provider": "tesseract",
            "word_confidences": word_confidences,
        }

    def _calculate_weighted_confidence(
        self, word_confidences: List[Tuple[str, float]]
    ) -> float:
        """
        Calculate weighted average of word confidences.
        Longer words are weighted more (harder to OCR correctly).
        """
        if not word_confidences:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for word, conf in word_confidences:
            # Weight by word length (min 1, max based on length/3)
            weight = max(1, len(word) / 3)
            weighted_sum += conf * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _reconstruct_text(self, tesseract_data: dict) -> str:
        """Reconstruct text from Tesseract data with proper formatting."""
        lines = {}

        for i, text in enumerate(tesseract_data["text"]):
            if text.strip():
                line_num = tesseract_data["line_num"][i]
                block_num = tesseract_data["block_num"][i]
                key = (block_num, line_num)

                if key not in lines:
                    lines[key] = []
                lines[key].append(text)

        # Sort by block then line number and join
        sorted_keys = sorted(lines.keys())
        text_lines = [" ".join(lines[key]) for key in sorted_keys]

        return "\n".join(text_lines)

    async def _google_vision_ocr(self, image_bytes: bytes) -> Dict[str, any]:
        """
        Extract text using Google Vision API (handwriting-aware).
        Cost: $1.50 per 1000 images

        Returns:
            dict with text, confidence, provider, word_confidences
        """
        if not self.google_vision_client:
            return {
                "text": "",
                "confidence": 0.0,
                "provider": "google_vision",
                "word_confidences": [],
                "error": "Google Vision client not initialized",
            }

        try:
            from google.cloud import vision

            image = vision.Image(content=image_bytes)

            # Use DOCUMENT_TEXT_DETECTION for handwritten text
            response = self.google_vision_client.document_text_detection(image=image)

            if response.error.message:
                raise Exception(response.error.message)

            # Get full text
            full_text = (
                response.full_text_annotation.text
                if response.full_text_annotation
                else ""
            )

            # Calculate confidence from symbol confidences
            word_confidences = []
            confidences = []

            if response.full_text_annotation:
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = "".join(
                                    [symbol.text for symbol in word.symbols]
                                )
                                word_conf = (
                                    sum(s.confidence for s in word.symbols)
                                    / len(word.symbols)
                                    if word.symbols
                                    else 0
                                )

                                word_confidences.append((word_text, word_conf))
                                confidences.append(word_conf)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return {
                "text": full_text,
                "confidence": avg_confidence,
                "provider": "google_vision",
                "word_confidences": word_confidences,
            }

        except Exception as e:
            return {
                "text": "",
                "confidence": 0.0,
                "provider": "google_vision",
                "word_confidences": [],
                "error": str(e),
            }

    async def process_handwritten_note(
        self, image_bytes: bytes, is_premium_user: bool = False
    ) -> Dict[str, any]:
        """
        Full processing pipeline for handwritten notes.

        Args:
            image_bytes: Raw image bytes
            is_premium_user: If True, always use Google Vision

        Returns:
            dict with:
                - text: Raw OCR text
                - confidence: OCR confidence score
                - provider: Which OCR was used
                - needs_aggressive_cleanup: If True, LLM should mark [unclear] sections
        """
        # Check if premium users always get Google Vision
        if (
            is_premium_user
            and settings.PREMIUM_ALWAYS_USE_GOOGLE_VISION
            and self.google_vision_client is not None
        ):
            result = await self._google_vision_ocr(image_bytes)
        else:
            result = await self.extract_text_with_confidence(image_bytes)

        # Add flag for aggressive cleanup if confidence is low
        result["needs_aggressive_cleanup"] = (
            result["confidence"] < self.LOW_CONFIDENCE_THRESHOLD
        )

        return result


# Singleton instance
hybrid_ocr = HybridOCR()
