"""
NotesOS - RAG (Retrieval-Augmented Generation) Service
Orchestrate the full RAG pipeline for question answering.
"""

from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embeddings import embedding_service
from app.services.vector_store import vector_store


class RAGService:
    """RAG pipeline orchestration for context retrieval."""

    async def query_notes(
        self,
        db: AsyncSession,
        question: str,
        course_id: str,
        topic_id: Optional[str] = None,
        max_chunks: int = 5,
    ) -> Dict:
        """
                Execute full RAG pipeline to retrieve relevant context for a question.

                Args:
                    db: Database session
                    question: User's question
                    course_id: Filter by course
                    topic_id: Optional filter by topic
                    max_chunks: Maximum chunks to retrieve


        Returns:
                    dict with:
                        - context: Combined text from relevant notes
                        - sources: List of source metadata
                        - chunks: Retrieved chunks with similarity scores
        """
        # 1. Generate embedding for the question
        query_embedding = await embedding_service.embed_query(question)

        # 2. Vector similarity search
        similar_chunks = await vector_store.search_similar(
            db=db,
            query_embedding=query_embedding,
            course_id=course_id,
            topic_id=topic_id,
            limit=max_chunks,
        )

        # 3. Build context string from retrieved chunks
        context = self._build_context(similar_chunks)

        # 4. Extract unique sources
        sources = self._extract_sources(similar_chunks)

        return {
            "context": context,
            "sources": sources,
            "chunks": similar_chunks,
            "chunk_count": len(similar_chunks),
        }

    async def hybrid_query_notes(
        self, db: AsyncSession, question: str, course_id: str, max_chunks: int = 10
    ) -> Dict:
        """
        Execute hybrid search combining vector and full-text search.
        Better for specific keyword-based queries.
        """
        # Generate embedding
        query_embedding = await embedding_service.embed_query(question)

        # Hybrid search
        results = await vector_store.hybrid_search(
            db=db,
            query=question,
            query_embedding=query_embedding,
            course_id=course_id,
            limit=max_chunks,
        )

        # Take top results by combined score
        top_results = sorted(
            results, key=lambda x: x.get("combined_score", 0), reverse=True
        )[:max_chunks]

        context = self._build_context(top_results)
        sources = self._extract_sources(top_results)

        return {
            "context": context,
            "sources": sources,
            "chunks": top_results,
            "chunk_count": len(top_results),
        }

    def _build_context(self, chunks: List[Dict]) -> str:
        """
        Build formatted context string from chunks.

        Format:
        From [Uploader]'s resource ([Resource Title]):
        [chunk text]

        ---

        From [Uploader]'s resource ([Resource Title]):
        [chunk text]
        """
        if not chunks:
            return ""

        context_parts = []

        for chunk in chunks:
            uploader = chunk.get("uploader_name", "Unknown")
            resource_title = chunk.get("resource_title", "Untitled")
            text = chunk.get("chunk_text", "")

            part = f"From {uploader}'s resource ({resource_title}):\n{text}"
            context_parts.append(part)

        return "\n\n---\n\n".join(context_parts)

    def _extract_sources(self, chunks: List[Dict]) -> List[Dict]:
        """
        Extract unique sources from chunks.

        Returns list of unique resources referenced.
        """
        seen_resources = set()
        sources = []

        for chunk in chunks:
            resource_id = chunk.get("resource_id")

            if resource_id and resource_id not in seen_resources:
                seen_resources.add(resource_id)
                sources.append(
                    {
                        "resource_id": resource_id,
                        "title": chunk.get("resource_title"),
                        "uploader": chunk.get("uploader_name"),
                        "uploaded_by": chunk.get("uploaded_by"),
                    }
                )

        return sources


# Singleton instance
rag_service = RAGService()
