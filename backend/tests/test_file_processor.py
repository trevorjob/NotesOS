"""Unit tests for PDF text extraction and glyph-fidelity scoring.

No DB — synthetic PDFs are built in-memory with PyMuPDF.
"""

import fitz
import pytest

from app.services.file_processor import (
    file_processor,
    _normalize_layout,
    _pdf_text_confidence,
    _CORRUPT_CONFIDENCE_CAP,
)


def _pdf_bytes(build) -> bytes:
    """Build a PDF with `build(doc)` and return its bytes."""
    doc = fitz.open()
    build(doc)
    data = doc.tobytes()
    doc.close()
    return data


def _clean_pdf() -> bytes:
    def build(doc):
        page = doc.new_page()
        page.insert_text((72, 72), "Newton second law F equals m a.", fontsize=12)
        page.insert_text((72, 120), "Energy E equals m c squared.", fontsize=12)
        second = doc.new_page()
        second.insert_text((72, 72), "A second page with more prose here.", fontsize=12)

    return _pdf_bytes(build)


def _symbol_corrupt_pdf() -> bytes:
    """A PDF whose Greek glyphs are baked as ZapfDingbats — the broken-export shape."""

    def build(doc):
        page = doc.new_page()
        page.insert_text((72, 72), "Resistivity formula follows.", fontsize=12)
        for i, y in enumerate(range(110, 210, 12)):
            page.insert_text((72, y), "rho", fontsize=12, fontname="ZaDb")

    return _pdf_bytes(build)


def _normalize(text: str) -> str:
    return _normalize_layout(text)


class TestPdfConfidence:
    def test_clean_pdf_scores_full_confidence(self):
        with fitz.open(stream=_clean_pdf(), filetype="pdf") as doc:
            assert _pdf_text_confidence(doc) == 1.0

    def test_symbol_corruption_is_flagged_despite_sparsity(self):
        # ArrangeAct
        with fitz.open(stream=_symbol_corrupt_pdf(), filetype="pdf") as doc:
            confidence = _pdf_text_confidence(doc)

        # Assert — capped below the 0.7 needs-review threshold
        assert confidence is not None
        assert confidence <= _CORRUPT_CONFIDENCE_CAP

    def test_empty_pdf_returns_none(self):
        with fitz.open(stream=_pdf_bytes(lambda d: d.new_page()), filetype="pdf") as doc:
            assert _pdf_text_confidence(doc) is None


class TestNormalizeLayout:
    def test_collapses_intraline_whitespace(self):
        assert _normalize_layout("a    b\tc") == "a b c"

    def test_preserves_paragraph_breaks(self):
        assert _normalize_layout("one\n\n\n\ntwo") == "one\n\ntwo"


class TestExtractTextFromPdf:
    @pytest.mark.asyncio
    async def test_returns_text_source_and_confidence(self):
        text, source_type, confidence = await file_processor.extract_text_from_pdf(
            _clean_pdf()
        )
        assert source_type == "pdf"
        assert confidence == 1.0
        assert "Newton" in text

    @pytest.mark.asyncio
    async def test_keeps_paragraph_structure_across_blocks(self):
        text, _, _ = await file_processor.extract_text_from_pdf(_clean_pdf())
        assert "\n\n" in text  # blocks stay separated, not flattened to one line

    @pytest.mark.asyncio
    async def test_process_from_bytes_surfaces_confidence(self):
        result = await file_processor.process_from_bytes(_clean_pdf(), ".pdf")
        assert result["confidence"] == 1.0
        assert result["source_type"] == "pdf"
