"""
NotesOS - Knowledge Synthesizer Service
Synthesizes all topic resource chunks into a structured consolidated note
using the DeepSeek AI (primary) or Claude (upgrade).
"""

import json
import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge import KnowledgeStatus, TopicKnowledge
from app.models.resource import Resource, ResourceChunk


class KnowledgeSynthesizer:
    """Synthesize topic resources into structured knowledge."""

    def __init__(self):
        self.deepseek_api_key = settings.DEEPSEEK_API_KEY
        self.deepseek_base = "https://api.deepseek.com/v1"
        self.anthropic_api_key = settings.ANTHROPIC_API_KEY

    async def synthesize(self, topic_id: str, db: AsyncSession) -> TopicKnowledge:
        """
        Synthesize all resource chunks for a topic into a TopicKnowledge record.

        Creates or updates the record (upsert by topic_id).
        Returns the TopicKnowledge instance with status=completed or failed.
        """
        # Upsert: find existing or create new
        result = await db.execute(
            select(TopicKnowledge).where(TopicKnowledge.topic_id == topic_id)
        )
        knowledge = result.scalar_one_or_none()

        if knowledge is None:
            knowledge = TopicKnowledge(topic_id=topic_id)
            db.add(knowledge)

        knowledge.status = KnowledgeStatus.PROCESSING
        knowledge.error_message = None
        await db.commit()
        await db.refresh(knowledge)

        try:
            # Fetch all resource chunks for this topic via explicit join
            chunks_result = await db.execute(
                select(ResourceChunk)
                .join(Resource, ResourceChunk.resource_id == Resource.id)
                .where(Resource.topic_id == _uuid.UUID(topic_id))
                .order_by(ResourceChunk.resource_id, ResourceChunk.chunk_index)
            )
            chunks = chunks_result.scalars().all()

            if not chunks:
                knowledge.consolidated_note = "_No materials uploaded yet. Add notes or files to generate a consolidated summary._"
                knowledge.key_points = []
                knowledge.concepts = []
                knowledge.source_count = 0
                knowledge.status = KnowledgeStatus.COMPLETED
                knowledge.generated_at = datetime.utcnow()
                await db.commit()
                return knowledge

            # Group chunks by resource_id to count sources
            resource_ids = {str(chunk.resource_id) for chunk in chunks}
            source_count = len(resource_ids)

            # Build context from chunks (trim to avoid token limits)
            context = self._build_context(chunks)

            # Call AI to synthesize
            synthesis = await self._call_ai(context)

            knowledge.consolidated_note = synthesis.get("consolidated_note", "")
            knowledge.key_points = synthesis.get("key_points", [])
            knowledge.concepts = synthesis.get("concepts", [])
            knowledge.source_count = source_count
            knowledge.status = KnowledgeStatus.COMPLETED
            knowledge.generated_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            knowledge.status = KnowledgeStatus.FAILED
            knowledge.error_message = str(e)
            await db.commit()
            print(f"[KNOWLEDGE] Synthesis failed for topic {topic_id}: {e}")

        return knowledge

    def _build_context(self, chunks: List[ResourceChunk]) -> str:
        """Build a context string from resource chunks (max ~12k chars)."""
        MAX_CHARS = 12000
        parts = []
        total = 0

        for chunk in chunks:
            text = chunk.chunk_text.strip()
            if not text:
                continue
            if total + len(text) > MAX_CHARS:
                remaining = MAX_CHARS - total
                if remaining > 200:
                    parts.append(text[:remaining] + "…")
                break
            parts.append(text)
            total += len(text)

        return "\n\n---\n\n".join(parts)

    async def _call_ai(self, context: str) -> Dict[str, Any]:
        """Call the AI to synthesize knowledge from chunk context."""
        prompt = f"""You are an expert academic tutor. Synthesize the following study materials into a structured knowledge summary.

STUDY MATERIALS:
{context}

Create a comprehensive synthesis. Return JSON with this exact structure:
{{
  "consolidated_note": "Full markdown-formatted summary. Use ## headings, bullet points, bold for key terms. 300-600 words.",
  "key_points": ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5"],
  "concepts": [
    {{"term": "Term name", "definition": "Clear, concise definition"}},
    {{"term": "Another term", "definition": "Its definition"}}
  ]
}}

Rules:
- consolidated_note: markdown, well-structured, exam-focused
- key_points: 5-8 most important facts a student must know
- concepts: 4-8 key vocabulary terms with clear definitions
- Return ONLY valid JSON, no other text"""

        try:
            # Primary: DeepSeek (cost-optimised)
            if self.deepseek_api_key:
                return await self._call_deepseek(prompt)
            # Fallback: Claude
            return await self._call_claude(prompt)
        except Exception as e:
            print(f"[KNOWLEDGE] AI call failed: {e}")
            raise

    async def _call_deepseek(self, prompt: str) -> Dict[str, Any]:
        """Call DeepSeek API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.deepseek_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return self._parse_json(content)

    async def _call_claude(self, prompt: str) -> Dict[str, Any]:
        """Call Anthropic Claude API as fallback."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            content = response.json()["content"][0]["text"]
            return self._parse_json(content)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from AI response."""
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in AI response")
        return json.loads(text[start:end])


# Singleton instance
knowledge_synthesizer = KnowledgeSynthesizer()
