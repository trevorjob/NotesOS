"""
NotesOS - Vector Store Service
PostgreSQL pgvector operations for RAG similarity search.
"""

from typing import List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class VectorStore:
    """Manage vector embeddings in PostgreSQL with pgvector."""

    async def insert_chunks(
        self,
        db: AsyncSession,
        resource_id: str,
        chunks: List[Dict],
        embeddings: List[List[float]],
    ) -> int:
        """
        Insert resource chunks with embeddings into database.

        Args:
            db: Database session
            resource_id: Parent resource ID
            chunks: List of chunk metadata dicts
            embeddings: Corresponding embedding vectors (1536-dim)

        Returns:
            Number of chunks inserted
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        inserted = 0

        for chunk, embedding in zip(chunks, embeddings):
            query = text("""
                INSERT INTO resource_chunks (
                    id, resource_id, chunk_text, chunk_index, embedding, created_at
                )
                VALUES (
                    gen_random_uuid(), :resource_id, :chunk_text, :chunk_index, 
                    :embedding, NOW()
                )
            """)

            # Convert embedding list to pgvector format
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"

            await db.execute(
                query,
                {
                    "resource_id": resource_id,
                    "chunk_text": chunk["chunk_text"],
                    "chunk_index": chunk["chunk_index"],
                    "embedding": embedding_str,
                },
            )

            inserted += 1

        await db.commit()
        return inserted

    async def search_similar(
        self,
        db: AsyncSession,
        query_embedding: List[float],
        course_id: str,
        topic_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Find similar resource chunks using vector similarity search.

        Args:
            db: Database session
            query_embedding: Query vector (1536-dim)
            course_id: Filter by course
            topic_id: Optional filter by topic
            limit: Max results to return

        Returns:
            List of matching chunks with metadata
        """
        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

        # Build query with optional topic filter
        if topic_id:
            query = text("""
                SELECT 
                    rc.id,
                    rc.resource_id,
                    rc.chunk_text,
                    rc.chunk_index,
                    r.title as resource_title,
                    r.uploaded_by,
                    u.full_name as uploader_name,
                    1 - (rc.embedding <=> CAST(:embedding AS VECTOR)) as similarity
                FROM resource_chunks rc
                JOIN resources r ON r.id = rc.resource_id
                JOIN topics t ON t.id = r.topic_id
                JOIN users u ON u.id = r.uploaded_by
                WHERE t.course_id = :course_id 
                  AND r.topic_id = :topic_id
                ORDER BY rc.embedding <=> CAST(:embedding AS VECTOR)
                LIMIT :limit
            """)

            result = await db.execute(
                query,
                {
                    "embedding": embedding_str,
                    "course_id": course_id,
                    "topic_id": topic_id,
                    "limit": limit,
                },
            )
        else:
            query = text("""
                SELECT 
                    rc.id,
                    rc.resource_id,
                    rc.chunk_text,
                    rc.chunk_index,
                    r.title as resource_title,
                    r.uploaded_by,
                    u.full_name as uploader_name,
                    1 - (rc.embedding <=> CAST(:embedding AS VECTOR)) as similarity
                FROM resource_chunks rc
                JOIN resources r ON r.id = rc.resource_id
                JOIN topics t ON t.id = r.topic_id
                JOIN users u ON u.id = r.uploaded_by
                WHERE t.course_id = :course_id
                ORDER BY rc.embedding <=> CAST(:embedding AS VECTOR)
                LIMIT :limit
            """)

            result = await db.execute(
                query,
                {"embedding": embedding_str, "course_id": course_id, "limit": limit},
            )

        rows = result.all()

        return [
            {
                "id": str(row.id),
                "resource_id": str(row.resource_id),
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "resource_title": row.resource_title,
                "uploaded_by": str(row.uploaded_by),
                "uploader_name": row.uploader_name,
                "similarity": float(row.similarity),
            }
            for row in rows
        ]

    async def hybrid_search(
        self,
        db: AsyncSession,
        query: str,
        query_embedding: List[float],
        course_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Hybrid search combining full-text and vector similarity.

        Args:
            db: Database session
            query: Search query text
            query_embedding: Query vector
            course_id: Filter by course
            limit: Max results

        Returns:
            Ranked list of chunks
        """
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

        # Combine full-text search with vector search
        sql_query = text("""
            WITH vector_results AS (
                SELECT 
                    rc.id,
                    rc.resource_id,
                    rc.chunk_text,
                    rc.chunk_index,
                    r.title as resource_title,
                    1 - (rc.embedding <=> CAST(:embedding AS VECTOR)) as vector_score
                FROM resource_chunks rc
                JOIN resources r ON r.id = rc.resource_id
                JOIN topics t ON t.id = r.topic_id
                WHERE t.course_id = :course_id
            ),
            text_results AS (
                SELECT 
                    rc.id,
                    ts_rank(to_tsvector('english', rc.chunk_text), 
                            plainto_tsquery('english', :query)) as text_score
                FROM resource_chunks rc
                JOIN resources r ON r.id = rc.resource_id
                JOIN topics t ON t.id = r.topic_id
                WHERE t.course_id = :course_id
                  AND to_tsvector('english', rc.chunk_text) @@ 
                      plainto_tsquery('english', :query)
            )
            SELECT 
                vr.id,
                vr.resource_id,
                vr.chunk_text,
                vr.chunk_index,
                vr.resource_title,
                vr.vector_score,
                COALESCE(tr.text_score, 0) as text_score,
                (vr.vector_score * 0.7 + COALESCE(tr.text_score, 0) * 0.3) as combined_score
            FROM vector_results vr
            LEFT JOIN text_results tr ON tr.id = vr.id
            ORDER BY combined_score DESC
            LIMIT :limit
        """)

        result = await db.execute(
            sql_query,
            {
                "embedding": embedding_str,
                "query": query,
                "course_id": course_id,
                "limit": limit,
            },
        )

        rows = result.all()

        return [
            {
                "id": str(row.id),
                "resource_id": str(row.resource_id),
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "resource_title": row.resource_title,
                "vector_score": float(row.vector_score),
                "text_score": float(row.text_score),
                "combined_score": float(row.combined_score),
            }
            for row in rows
        ]

    async def delete_chunks(self, db: AsyncSession, resource_id: str) -> int:
        """
        Delete all chunks for a resource.

        Args:
            db: Database session
            resource_id: Resource ID

        Returns:
            Number of chunks deleted
        """
        query = text("""
            DELETE FROM resource_chunks
            WHERE resource_id = :resource_id
        """)

        result = await db.execute(query, {"resource_id": resource_id})
        await db.commit()

        return result.rowcount


# Singleton instance
vector_store = VectorStore()
