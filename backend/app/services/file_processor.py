"""
NotesOS - File Processing Service
Extract text from various file formats (PDF, DOCX, images with OCR).
"""

import io
from typing import Tuple, Optional
import httpx

# PDF processing
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

# DOCX processing
import mammoth


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
            text, source_type = await self.extract_text_from_pdf(file_bytes)
            return {
                "text": text,
                "source_type": source_type,
                "needs_cleaning": False,
            }

        elif file_format.lower() in [".doc", ".docx"]:
            text, source_type = await self.extract_text_from_docx(file_bytes)
            return {
                "text": text,
                "source_type": source_type,
                "needs_cleaning": False,
            }

        elif file_format.lower() in [".md", ".txt"]:
            # Text-native formats — no extraction needed, just decode.
            return {
                "text": file_bytes.decode("utf-8", errors="replace"),
                "source_type": "text",
                "needs_cleaning": False,
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

    async def extract_text_from_pdf(self, pdf_bytes: bytes) -> Tuple[str, str]:
        """
        Extract text from PDF using OCR.

        Returns:
            (text, source_type='pdf')
        """
        try:
            # Convert PDF pages to images
            images = convert_from_bytes(pdf_bytes)

            # OCR each page
            text_parts = []
            for i, image in enumerate(images):
                page_text = pytesseract.image_to_string(image)
                text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

            full_text = "\n\n".join(text_parts)
            return self.clean_text(full_text), "pdf"

        except Exception as e:
            raise Exception(f"PDF text extraction failed: {str(e)}")

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


# Singleton instance
file_processor = FileProcessor()
