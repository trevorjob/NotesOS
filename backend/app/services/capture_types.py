"""
Accepted capture file types — the single allow-list every ingestion surface shares.

Used by the topic-level upload endpoints, the course-level capture (dump) endpoint,
and the capture worker. Add a format here and every entry point accepts it.
"""

import os

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
# Text-native formats ride the doc path — file_processor just decodes them.
DOC_EXTS = {".pdf", ".doc", ".docx", ".md", ".txt"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".webm", ".ogg", ".aac", ".flac"}

ALL_ACCEPTED_EXTS = IMAGE_EXTS | DOC_EXTS | AUDIO_EXTS


def ext_of(filename: str | None, url: str = "") -> str:
    """Lowercase extension of a filename, falling back to the URL path."""
    name = filename or url.split("?")[0]
    return os.path.splitext(name)[1].lower()


def kind_of(ext: str) -> str | None:
    """Coarse kind for an extension: image | doc | audio | None (unsupported)."""
    if ext in IMAGE_EXTS:
        return "image"
    if ext in DOC_EXTS:
        return "doc"
    if ext in AUDIO_EXTS:
        return "audio"
    return None


def doc_resource_kinds(ext: str):
    """(ResourceKind, SourceType) for a doc-path extension."""
    from app.models.resource import ResourceKind, SourceType

    if ext == ".pdf":
        return ResourceKind.PDF, SourceType.PDF
    if ext in (".md", ".txt"):
        return ResourceKind.TEXT, SourceType.TEXT
    return ResourceKind.DOCX, SourceType.DOCX
