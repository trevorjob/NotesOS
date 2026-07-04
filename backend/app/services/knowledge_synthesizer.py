"""
NotesOS - Knowledge Synthesizer Service
Synthesizes all topic resource chunks into a structured consolidated note
using the DeepSeek AI (primary) or Claude (upgrade).
"""

import json
import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Topic
from app.models.knowledge import KnowledgeStatus, TopicKnowledge
from app.models.resource import Resource, ResourceChunk
from app.services.llm import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)


class KnowledgeSynthesizer:
    """Synthesize topic resources into structured knowledge."""

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
            # Fetch topic name for AI prompt
            topic_result = await db.execute(
                select(Topic).where(Topic.id == _uuid.UUID(topic_id))
            )
            topic_obj = topic_result.scalar_one_or_none()
            topic_name = topic_obj.title if topic_obj else "this topic"

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
            synthesis = await self._call_ai(context, topic_name)

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
            logger.error("Knowledge synthesis failed", exc_info=True, extra={"topic_id": str(topic_id)})

        return knowledge

    def _build_context(self, chunks: List[ResourceChunk]) -> str:
        """Build a context string from resource chunks, grouped by source.

        Raises the cap to 80k chars (~20k tokens input) so that multi-source
        topics aren't silently truncated. gpt-4o-mini supports 128k context.
        We group chunks by resource so the AI can see which source each came from.
        """
        MAX_CHARS = 80_000

        # Group chunks by resource_id preserving insertion order
        by_resource: dict[str, list[str]] = {}
        for chunk in chunks:
            rid = str(chunk.resource_id)
            if rid not in by_resource:
                by_resource[rid] = []
            text = chunk.chunk_text.strip()
            if text:
                by_resource[rid].append(text)

        parts = []
        total = 0
        for i, (rid, texts) in enumerate(by_resource.items(), 1):
            source_header = f"=== SOURCE {i} ==="
            body = "\n\n".join(texts)
            block = f"{source_header}\n{body}"
            if total + len(block) > MAX_CHARS:
                remaining = MAX_CHARS - total
                if remaining > 500:
                    parts.append(block[:remaining] + "\n[truncated — source too long]")
                break
            parts.append(block)
            total += len(block)

        return "\n\n".join(parts)

    async def _call_ai(self, context: str, topic_name: str) -> Dict[str, Any]:
        """Call the AI to consolidate all source material into one authoritative document."""
        source_count = context.count("=== SOURCE ")
        source_note = (
            f"There are {source_count} source(s) above. "
            "Where sources overlap or contradict each other, reconcile them — "
            "don't just repeat each one. Where they complement each other, merge "
            "their explanations into a single complete picture."
            if source_count > 1 else ""
        )

        prompt = f"""You are consolidating all class materials for a topic into one definitive knowledge document.

This is NOT a summary. A summary compresses. This consolidates — it takes everything
across all sources and produces a single document that covers the topic completely,
resolving overlaps and merging complementary explanations. A student should be able to
study ONLY this document and have everything they need.

TOPIC: {topic_name}

SOURCE MATERIALS:
{context}

{source_note}

Your job:
1. Read everything across all sources.
2. Identify every distinct concept, mechanism, definition, example, and relationship covered.
3. Write a consolidated document that covers ALL of it — organised by idea, not by source.
4. Do not omit material just because it appears in only one source.
5. Do not pad — every sentence must earn its place. But do not compress either.

CONSOLIDATED_NOTE format rules:
- Open with 1–2 sentences that answer: "What is this topic actually about, in plain English?"
- Use ## subheadings to organise by concept/theme (not by source)
- Bold the first mention of every important term
- Use bullet points for lists; use prose for explanations that need flow
- Include examples if the sources give them — they help
- Length must match the material. A topic with 3 dense sources should produce a long document.
  Do not artificially shorten. If the material is rich, the output should be rich.

KEY_POINTS: The facts a student must know cold to pass an exam.
- 5–10 items (more if the material warrants it)
- Each point is one specific, self-contained sentence — no vague generalisations
- Cover different aspects — don't cluster on one sub-topic

CONCEPTS: Terms that need defining.
- 4–12 terms depending on the material
- Only include terms a student might not already know
- One clear sentence per definition, plain English

Return JSON:
{{
  "consolidated_note": "full markdown document — complete, not compressed",
  "key_points": ["specific exam-ready fact", "..."],
  "concepts": [
    {{"term": "Term", "definition": "One clear sentence."}}
  ]
}}

Return ONLY valid JSON. No preamble. No text outside the JSON."""

        try:
            content = await call_llm(
                prompt,
                task="knowledge_synthesis",
                temperature=0.3,
                max_tokens=16000,
                timeout=120.0,
                response_format={"type": "json_object"},
            )
            return self._parse_json(content)
        except Exception:
            logger.error("Knowledge AI call failed", exc_info=True)
            raise

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from AI response.

        With response_format=json_object the API returns syntactically valid
        JSON, but we still slice to the outer braces (defensive) and parse with
        strict=False so stray control characters inside string values (raw
        newlines/tabs from source material) don't break parsing.
        """
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in AI response")
        return json.loads(text[start:end], strict=False)


# Singleton instance
knowledge_synthesizer = KnowledgeSynthesizer()
