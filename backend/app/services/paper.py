"""
Paper substrate (B8) — handwriting in, every retrieval mode at once.

The written twin of the voice substrate (product-map, LOCKED 2026-07-17): any written
answer, in any mode, can arrive as a **photo of handwriting**. This is ONE transcription
pre-step in front of the unchanged text ``/attempt`` flow — modes only ever consume text,
which is exactly why all of them (quiz/ramble/teach/pretest/recap/brain dump) get photo
answers from this single seam. Nothing here touches a mode, the engine, or the LOCKED
synchronous ``/attempt`` contract.

**The fairness rule is the whole design: grade what the user confirms they wrote, never
what OCR guessed.** The transcription goes back to the client for confirm/correct; only
the confirmed text ever reaches an ``evaluate``. Answer photos are **ephemeral** — passed
to the vision model as data URLs, never stored (the attempt log records confirmed text).

Unlike voice (client-side STT, LOCKED), handwriting is transcribed **server-side**: the
existing vision seam (``vision_transcribe``, ``VISION_MODEL``) reads handwriting and
emits LaTeX for equations (B4's ``render=math`` displays them) — on-device handwriting
OCR can't. Reuses that seam; adds no new OCR path.
"""

import base64
import os
from dataclasses import dataclass

from app.services.vision_transcribe import vision_transcribe

# Answer photos are tighter than the capture allow-list: the vision API accepts these
# as inline data URLs (capture's .tiff/.bmp ride Cloudinary transforms instead — an
# ephemeral answer photo never goes to storage). Phones emit jpeg/png/webp natively;
# the client converts HEIC before upload (standard practice).
ANSWER_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_MIME_BY_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

MAX_ANSWER_IMAGE_BYTES = 10 * 1024 * 1024  # per page — same posture as capture uploads
MAX_ANSWER_PAGES = 5                       # a handwritten dump spans pages; an essay doesn't need 20

# The transcription prompt flags what it couldn't read — surfaced so the client can
# draw the user's eye to exactly the spots that need correcting (the confirm beat).
_UNCERTAIN_MARK = "[?]"
_ILLEGIBLE_MARK = "[illegible"


class PaperValidationError(Exception):
    """A rejected answer photo. ``status`` maps to the HTTP code the endpoint returns."""

    def __init__(self, message: str, *, status: int) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class PaperTranscription:
    """What the vision model read off the page — pending the user's confirmation."""

    text: str
    page_count: int
    has_uncertain: bool   # contains best-guess words flagged "[?]"
    has_illegible: bool   # contains sections the model couldn't read at all


async def transcribe_answer(images: list[tuple[str, bytes]]) -> PaperTranscription:
    """Transcribe handwritten answer page(s) into text for the user to confirm.

    ``images`` is ``[(filename, bytes), ...]`` in page order. Validates count, type, and
    size, then hands the pages to the existing vision seam as ephemeral data URLs.
    Raises :class:`PaperValidationError` on any rejected upload.
    """
    if not images:
        raise PaperValidationError("no image provided", status=400)
    if len(images) > MAX_ANSWER_PAGES:
        raise PaperValidationError(
            f"too many pages — at most {MAX_ANSWER_PAGES} per answer", status=400
        )

    urls = [_as_data_url(filename, data) for filename, data in images]
    text = (await _vision_transcribe(urls)).strip()

    return PaperTranscription(
        text=text,
        page_count=len(images),
        has_uncertain=_UNCERTAIN_MARK in text,
        has_illegible=_ILLEGIBLE_MARK in text,
    )


def _as_data_url(filename: str, data: bytes) -> str:
    """Validate one page and encode it as an inline data URL (never stored)."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ANSWER_IMAGE_EXTS:
        raise PaperValidationError(
            f"unsupported answer-photo type {ext or '(none)'} — use one of "
            f"{sorted(ANSWER_IMAGE_EXTS)}",
            status=415,
        )
    if not data:
        raise PaperValidationError(f"{filename}: empty file", status=400)
    if len(data) > MAX_ANSWER_IMAGE_BYTES:
        raise PaperValidationError(
            f"{filename}: too large — each page must be under "
            f"{MAX_ANSWER_IMAGE_BYTES // (1024 * 1024)}MB",
            status=413,
        )
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{_MIME_BY_EXT[ext]};base64,{encoded}"


# ── vision boundary (monkeypatched in tests) ────────────────────────────────────

async def _vision_transcribe(urls: list[str]) -> str:
    """The one call to the vision seam — reuses the capture pipeline's transcriber."""
    return await vision_transcribe.transcribe_images(urls)
