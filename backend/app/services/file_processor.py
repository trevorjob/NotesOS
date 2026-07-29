"""
NotesOS - File Processing Service
Extract text from various file formats (PDF, DOCX, images with OCR).
"""

import io
import re
from typing import Tuple, Optional
import httpx

# PDF processing — PyMuPDF for the text layer, poppler+tesseract for scanned OCR.
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

# DOCX processing
import mammoth

# A PDF that yields at least this many non-whitespace characters from its text layer
# is treated as text-native (skip OCR). Below it, assume a scanned/image PDF and OCR.
PDF_TEXT_LAYER_MIN_CHARS = 20

# Fonts that carry pictographs, not letters. ASCII-alphanumeric text drawn from
# them is the signature of a broken Unicode→PDF export: every Greek/math glyph
# collapsed onto one dingbat byte, unrecoverable by any extractor (the page
# renders a box too, so OCR can't save it either).
_PICTOGRAPH_FONTS = ("symbol", "zapfdingbats", "dingbats", "wingdings")
# Glyphs an extractor emits when a code point has no mapping at all.
_NOTDEF_CHARS = frozenset("�■□▯☐")
# Symbol corruption is unrecoverable however sparse — a handful of wrong glyphs
# still means every formula is wrong. Above this count, cap confidence so the
# resource is flagged for review instead of silently ingesting garbage.
_SYMBOL_CORRUPT_FLOOR = 3
_CORRUPT_CONFIDENCE_CAP = 0.4


class FileProcessor:
    """Process uploaded files and extract text content."""

    async def process_uploaded_file(
        self, file_url: str, file_format: str, is_handwritten: Optional[bool] = None
    ) -> dict:
        """
        Process a file by downloading from URL first.
        Prefer process_from_bytes() when raw bytes are already available.
        """
        file_bytes = await self._download_file(file_url)
        return await self.process_from_bytes(file_bytes, file_format, is_handwritten)

    async def process_from_bytes(
        self, file_bytes: bytes, file_format: str, is_handwritten: Optional[bool] = None
    ) -> dict:
        """
        Process raw file bytes and extract text content.
        Faster than process_uploaded_file() — skips the download step.

        Args:
            file_bytes: Raw file bytes
            file_format: File extension (pdf, docx, jpg, png, etc.)
            is_handwritten: For images only - whether content is handwritten

        Returns:
            dict with:
                - text: Extracted text content
                - source_type: 'pdf', 'docx', 'handwritten', or 'printed'
                - needs_cleaning: Whether OCR cleaning should be applied
        """
        # Process based on format
        if file_format.lower() == ".pdf":
            text, source_type, confidence = await self.extract_text_from_pdf(file_bytes)
            return {
                "text": text,
                "source_type": source_type,
                "needs_cleaning": False,
                "confidence": confidence,
            }

        elif file_format.lower() in [".doc", ".docx"]:
            text, source_type = await self.extract_text_from_docx(file_bytes)
            return {
                "text": text,
                "source_type": source_type,
                "needs_cleaning": False,
                "confidence": None,
            }

        elif file_format.lower() in [".md", ".txt"]:
            # Text-native formats — no extraction needed, just decode.
            return {
                "text": file_bytes.decode("utf-8", errors="replace"),
                "source_type": "text",
                "needs_cleaning": False,
                "confidence": None,
            }

        elif file_format.lower() in [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]:
            # Images are now processed via GPT-4o Vision, which requires a URL.
            # Call vision_transcribe.transcribe_images([url]) directly from the
            # upload handler (after Cloudinary upload provides the URL).
            raise NotImplementedError(
                "Image transcription requires a URL — use "
                "vision_transcribe.transcribe_images([url]) instead."
            )

        else:
            raise ValueError(f"Unsupported file format: {file_format}")

    async def _download_file(self, url: str) -> bytes:
        """Download file from URL."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.content

    async def extract_text_from_pdf(
        self, pdf_bytes: bytes
    ) -> Tuple[str, str, Optional[float]]:
        """
        Extract text from a PDF, text-layer first, OCR only as a fallback.

        Most PDFs students upload (slides, exported notes, papers) carry a real text
        layer — pull it with PyMuPDF: fast, high quality, block-aware (keeps
        paragraph structure for chunking), and **no poppler or tesseract required**.
        Only when the text layer is effectively empty (a scanned/image PDF) do we
        rasterise (poppler) and OCR (tesseract), so the common case works even where
        the OCR system binaries aren't installed.

        Returns:
            (text, source_type='pdf', confidence) where confidence in [0, 1] scores
            glyph fidelity of the text layer (None for the OCR fallback).
        """
        # 1. Text layer — the fast, dependency-free path.
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                text = _extract_pdf_text_layer(doc)
                if len(text.strip()) >= PDF_TEXT_LAYER_MIN_CHARS:
                    return text, "pdf", _pdf_text_confidence(doc)
        except Exception:
            pass  # unreadable text layer → try OCR below

        # 2. Scanned PDF → OCR each page. Needs poppler + tesseract.
        try:
            images = convert_from_bytes(pdf_bytes)
            text_parts = []
            for i, image in enumerate(images):
                page_text = pytesseract.image_to_string(image)
                text_parts.append(f"--- Page {i + 1} ---\n{page_text}")
            return _normalize_layout("\n\n".join(text_parts)), "pdf", None
        except Exception as e:
            raise Exception(
                "PDF text extraction failed: no readable text layer and OCR is "
                f"unavailable (install poppler + tesseract for scanned PDFs). {e}"
            )

    async def extract_text_from_docx(self, docx_bytes: bytes) -> Tuple[str, str]:
        """
        Extract text from DOCX file.

        Returns:
            (text, source_type='docx')
        """
        try:
            # Use mammoth to convert DOCX to plain text
            result = mammoth.extract_raw_text(io.BytesIO(docx_bytes))
            text = result.value

            return self.clean_text(text), "docx"

        except Exception as e:
            raise Exception(f"DOCX text extraction failed: {str(e)}")

    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """
        Extract text from image using OCR.

        Returns:
            Raw OCR text (not cleaned yet)
        """
        try:
            # Open image from bytes
            image = Image.open(io.BytesIO(image_bytes))

            # Perform OCR
            text = pytesseract.image_to_string(image)

            return self.clean_text(text)

        except Exception as e:
            raise Exception(f"Image OCR failed: {str(e)}")

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text (basic normalization).

        - Remove extra whitespace
        - Normalize line breaks
        - Trim
        """
        # Remove extra spaces
        text = " ".join(text.split())

        # Normalize line breaks (max 2 consecutive)
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        # Trim
        text = text.strip()

        return text


def _extract_pdf_text_layer(doc: "fitz.Document") -> str:
    """Text-block extraction that keeps paragraph breaks for chunking."""
    parts = [
        block[4].strip()
        for page in doc
        for block in page.get_text("blocks")
        if block[6] == 0 and block[4].strip()  # block_type 0 == text
    ]
    return _normalize_layout("\n\n".join(parts))


def _pdf_text_confidence(doc: "fitz.Document") -> Optional[float]:
    """Glyph-fidelity score of a PDF text layer in [0, 1], None if it has no text.

    Two independent corruption signals: notdef/replacement boxes (garbled text),
    and ASCII-alphanumeric glyphs drawn from a pictograph font (a broken export
    whose real letters are gone). The latter caps confidence regardless of how
    sparse it is, so a formula sheet with a wrong symbol per line is still flagged.
    """
    total = notdef = symbol_corrupt = 0
    for page in doc:
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    is_pictograph = any(
                        p in span["font"].lower() for p in _PICTOGRAPH_FONTS
                    )
                    for char in span["chars"]:
                        c = char["c"]
                        if c.isspace():
                            continue
                        total += 1
                        if c in _NOTDEF_CHARS:
                            notdef += 1
                        elif is_pictograph and c.isascii() and c.isalnum():
                            symbol_corrupt += 1
    if total == 0:
        return None
    confidence = 1.0 - notdef / total
    if symbol_corrupt >= _SYMBOL_CORRUPT_FLOOR:
        confidence = min(confidence, _CORRUPT_CONFIDENCE_CAP)
    return round(confidence, 3)


def _normalize_layout(text: str) -> str:
    """Collapse intra-line whitespace but keep paragraph breaks for chunking."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# Singleton instance
file_processor = FileProcessor()
