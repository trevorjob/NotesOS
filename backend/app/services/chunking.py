"""
NotesOS - Text Chunking Service
Split text into chunks for RAG processing with semantic awareness.
"""

from typing import List, Dict
import re


class ChunkingService:
    """Chunk text while preserving semantic boundaries."""

    def __init__(
        self, chunk_size: int = 800, chunk_overlap: int = 100, min_chunk_size: int = 100
    ):
        """
        Initialize chunking parameters.

        Args:
            chunk_size: Target size for each chunk (characters)
            chunk_overlap: Overlap between chunks for context continuity
            min_chunk_size: Minimum acceptable chunk size
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(self, text: str, resource_id: str = None) -> List[Dict]:
        """
        Split text into chunks with metadata.

        Args:
            text: Full text to chunk
            resource_id: Optional resource ID for metadata

        Returns:
            List of chunk dicts with:
                - chunk_text: The chunk content
                - chunk_index: Position in sequence
                - char_start: Starting character position
                - char_end: Ending character position
        """
        if not text or len(text) < self.min_chunk_size:
            # Text too short, return as single chunk
            return [
                {
                    "chunk_text": text,
                    "chunk_index": 0,
                    "char_start": 0,
                    "char_end": len(text),
                }
            ]

        # Split into paragraphs first (semantic boundaries)
        paragraphs = self._split_into_paragraphs(text)

        # Combine paragraphs into chunks
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0

        for para_text, para_start in paragraphs:
            # Check if adding this paragraph exceeds chunk size
            potential_chunk = (
                current_chunk + ("\n\n" if current_chunk else "") + para_text
            )

            if len(potential_chunk) <= self.chunk_size:
                # Add paragraph to current chunk
                current_chunk = potential_chunk
            else:
                # Current chunk is full, save it
                if current_chunk:
                    chunks.append(
                        {
                            "chunk_text": current_chunk.strip(),
                            "chunk_index": chunk_index,
                            "char_start": current_start,
                            "char_end": current_start + len(current_chunk),
                        }
                    )
                    chunk_index += 1

                # Start new chunk with this paragraph
                # Add overlap from previous chunk if exists
                if current_chunk and self.chunk_overlap > 0:
                    overlap_text = current_chunk[-self.chunk_overlap :]
                    current_chunk = overlap_text + "\n\n" + para_text
                    current_start = (
                        current_start
                        + len(current_chunk)
                        - self.chunk_overlap
                        - len(para_text)
                    )
                else:
                    current_chunk = para_text
                    current_start = para_start

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(
                {
                    "chunk_text": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "char_start": current_start,
                    "char_end": current_start + len(current_chunk),
                }
            )

        return chunks

    def _split_into_paragraphs(self, text: str) -> List[tuple]:
        """
        Split text into paragraphs with their start positions.

        Returns:
            List of (paragraph_text, start_position) tuples
        """
        paragraphs = []

        # Split by double newlines or period + newline
        para_pattern = r"\n\n+|\.\n"
        parts = re.split(para_pattern, text)

        current_pos = 0
        for part in parts:
            if part.strip():
                paragraphs.append((part.strip(), current_pos))
                current_pos += len(part)

        return paragraphs

    def chunk_with_sentences(self, text: str) -> List[Dict]:
        """
        Alternative chunking method that respects sentence boundaries.
        More precise but potentially slower.
        """
        sentences = self._split_into_sentences(text)

        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0

        for sent_text, sent_start in sentences:
            potential_chunk = current_chunk + " " + sent_text

            if len(potential_chunk) <= self.chunk_size:
                current_chunk = potential_chunk.strip()
            else:
                if current_chunk:
                    chunks.append(
                        {
                            "chunk_text": current_chunk,
                            "chunk_index": chunk_index,
                            "char_start": current_start,
                            "char_end": current_start + len(current_chunk),
                        }
                    )
                    chunk_index += 1

                current_chunk = sent_text
                current_start = sent_start

        if current_chunk:
            chunks.append(
                {
                    "chunk_text": current_chunk,
                    "chunk_index": chunk_index,
                    "char_start": current_start,
                    "char_end": current_start + len(current_chunk),
                }
            )

        return chunks

    def _split_into_sentences(self, text: str) -> List[tuple]:
        """Split text into sentences."""
        # Simple sentence splitter (can be improved)
        sentence_pattern = r"(?<=[.!?])\s+"
        sentences = re.split(sentence_pattern, text)

        result = []
        current_pos = 0
        for sent in sentences:
            if sent.strip():
                result.append((sent.strip(), current_pos))
                current_pos += len(sent)

        return result


# Singleton with default config
chunking_service = ChunkingService(
    chunk_size=800, chunk_overlap=100, min_chunk_size=100
)
