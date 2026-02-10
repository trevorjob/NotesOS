"""
NotesOS - OpenAI Embeddings Service
Generate vector embeddings for RAG using OpenAI's text-embedding-3-small.
Cost-optimized: ~$0.02 per 1M tokens (50x cheaper than Voyage AI).
"""

from typing import List
from openai import AsyncOpenAI

from app.config import settings


class EmbeddingService:
    """Generate embeddings using OpenAI text-embedding-3-small."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSIONS

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            1536-dimensional embedding vector
        """
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0]

    async def generate_embeddings_batch(
        self, texts: List[str], input_type: str = "document"
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).

        Args:
            texts: List of texts to embed
            input_type: "document" for notes, "query" for search queries

        Returns:
            List of embedding vectors

        Cost: ~$0.02 per 1M tokens
        For 1000 notes (500 words each): ~$0.01
        """
        if not texts:
            return []

        try:
            response = await self.client.embeddings.create(
                model=self.model, input=texts, dimensions=self.dimensions
            )

            # Extract embeddings from response
            embeddings = [item.embedding for item in response.data]

            return embeddings

        except Exception as e:
            raise Exception(f"Embedding generation failed: {str(e)}")

    async def embed_query(self, query: str) -> List[float]:
        """
        Convenience method for embedding search queries.

        Args:
            query: Search query text

        Returns:
            Embedding vector optimized for search
        """
        return await self.generate_embedding(query)


# Singleton instance
embedding_service = EmbeddingService()
