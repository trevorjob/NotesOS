"""
NotesOS - Knowledge Synthesizer Service

Produces the consolidated note for a topic. **Incremental (A4):** instead of
re-reading the whole corpus on every upload (the write-amplification cost bomb),
it folds only the *new* material into the existing note. Per-resource
``synthesized_at`` marks what's already merged — NULL means "not in the note yet"
(a fresh upload, a quarantine release, or a moved-in resource, uniformly).

Three synthesis modes, decided per run:
  * **full**   — no usable existing note (first synthesis, or a forced rebuild):
                 read every non-quarantined chunk, write the note from scratch.
  * **incremental** — an existing note plus pending resources: merge the new
                 material into the note, reconciling and deduping.
  * **noop**   — nothing pending: the note is already current, so skip the LLM
                 entirely (the cost win).

The note **body is streamed** as markdown prose (`call_llm_stream`) so the client
can watch it write itself over the course WebSocket; the structured metadata
(`key_points`, `concepts`) is extracted from the finished body in a second, cheap,
whole-parsed call. Prose streams, JSON arrives whole — never a half-parsed blob.
"""

import json
import uuid as _uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Topic
from app.models.subject import SubjectFamily
from app.models.knowledge import KnowledgeStatus, TopicKnowledge
from app.models.resource import Resource, ResourceChunk
from app.services.llm import call_llm, call_llm_stream
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_CONTEXT_CHARS = 80_000
_EMPTY_NOTE = "_No materials uploaded yet. Add notes or files to generate a consolidated summary._"

# A note is "usable as a base to merge into" only if it's real prose — not absent
# and not the empty-state placeholder. Otherwise we do a full build.
Broadcast = Callable[[dict], Awaitable[None]]


def _is_usable_note(note: Optional[str]) -> bool:
    return bool(note) and note.strip() != _EMPTY_NOTE.strip()


def _coerce_family(raw: Optional[str]) -> SubjectFamily:
    """Map an LLM-emitted family string to the enum; anything unrecognised → GENERAL."""
    try:
        return SubjectFamily(str(raw).strip().upper())
    except (ValueError, AttributeError):
        return SubjectFamily.GENERAL


class KnowledgeSynthesizer:
    """Synthesize topic resources into structured knowledge, incrementally."""

    async def synthesize(
        self,
        topic_id: str,
        db: AsyncSession,
        *,
        force_full: bool = False,
        broadcast: Optional[Broadcast] = None,
    ) -> TopicKnowledge:
        """
        (Re)synthesize the consolidated note for a topic.

        Merges only *new* (non-quarantined, unmerged) material into the existing
        note unless there's no usable note yet or ``force_full`` is set, in which
        case it rebuilds from the whole corpus. Upserts the ``TopicKnowledge`` row.

        Args:
            topic_id:   Topic to synthesize.
            db:         Async session (worker-owned).
            force_full: Rebuild from scratch, re-merging every resource. Used by a
                        manual regenerate and after a move removes material.
            broadcast:  Optional async sink for streaming events
                        (``knowledge_stream_start`` / ``knowledge_delta`` /
                        ``knowledge_stream_end``). Decoupled from the transport.

        Returns the ``TopicKnowledge`` with status completed or failed.
        """
        knowledge = await self._upsert(db, topic_id)
        knowledge.status = KnowledgeStatus.PROCESSING
        knowledge.error_message = None
        await db.commit()
        await db.refresh(knowledge)

        try:
            topic_name = await self._topic_name(db, topic_id)
            resources = await self._live_resources(db, topic_id)

            if force_full:
                for r in resources:
                    r.synthesized_at = None

            # Only chunked resources can be merged — an uploaded-but-not-yet-chunked
            # resource has no content to fold in, and must not be stamped as merged.
            has_chunks = await self._has_chunks(db, resources)
            chunked = [r for r, ok in zip(resources, has_chunks) if ok]

            if not chunked:
                return await self._finish_empty(db, knowledge)

            merged_any = any(r.synthesized_at is not None for r in chunked)
            has_base = _is_usable_note(knowledge.consolidated_note) and merged_any
            pending = [r for r in chunked if r.synthesized_at is None]

            if has_base:
                mode, sources = "incremental", pending
            else:
                mode, sources = "full", chunked

            if not sources:
                # Nothing new to fold in — the note is already current. Skip the LLM.
                return await self._finish_unchanged(db, knowledge, len(resources))

            body = await self._generate_body(
                db, topic_id, topic_name, mode,
                base_note=knowledge.consolidated_note if mode == "incremental" else None,
                sources=sources,
                broadcast=broadcast,
            )
            meta = await self._extract_metadata(body, topic_name)

            knowledge.consolidated_note = body
            knowledge.key_points = meta.get("key_points", [])
            knowledge.concepts = meta.get("concepts", [])
            knowledge.source_count = len(resources)

            # Infer the subject family from the note (drives the retrieval profile).
            # Never overrides a user's manual choice.
            await self._apply_subject_family(db, topic_id, meta.get("subject_family"))
            knowledge.status = KnowledgeStatus.COMPLETED
            knowledge.generated_at = datetime.utcnow()

            # Stamp exactly the resources we just merged.
            stamped_at = datetime.utcnow()
            for r in sources:
                r.synthesized_at = stamped_at

            await db.commit()

        except Exception as e:
            await db.rollback()
            knowledge = await self._upsert(db, topic_id)
            knowledge.status = KnowledgeStatus.FAILED
            knowledge.error_message = str(e)
            await db.commit()
            logger.error("Knowledge synthesis failed", exc_info=True, extra={"topic_id": str(topic_id)})

        return knowledge

    # ── record + scope helpers ──────────────────────────────────────────────

    async def _upsert(self, db: AsyncSession, topic_id: str) -> TopicKnowledge:
        result = await db.execute(
            select(TopicKnowledge).where(TopicKnowledge.topic_id == _uuid.UUID(str(topic_id)))
        )
        knowledge = result.scalar_one_or_none()
        if knowledge is None:
            knowledge = TopicKnowledge(topic_id=_uuid.UUID(str(topic_id)))
            db.add(knowledge)
        return knowledge

    async def _topic_name(self, db: AsyncSession, topic_id: str) -> str:
        topic = await db.scalar(select(Topic).where(Topic.id == _uuid.UUID(str(topic_id))))
        return topic.title if topic else "this topic"

    async def _apply_subject_family(
        self, db: AsyncSession, topic_id: str, raw_family: Optional[str]
    ) -> None:
        """Set the topic's inferred subject family — unless a user has overridden it."""
        topic = await db.scalar(select(Topic).where(Topic.id == _uuid.UUID(str(topic_id))))
        if topic is None or topic.subject_family_overridden:
            return
        topic.subject_family = _coerce_family(raw_family)

    async def _live_resources(self, db: AsyncSession, topic_id: str) -> List[Resource]:
        """Non-quarantined resources for the topic — never merges a quarantined upload."""
        result = await db.execute(
            select(Resource)
            .where(Resource.topic_id == _uuid.UUID(str(topic_id)))
            .where(Resource.quarantined.is_(False))
            .order_by(Resource.created_at)
        )
        return list(result.scalars().all())

    async def _has_chunks(self, db: AsyncSession, resources: List[Resource]) -> List[bool]:
        """Whether each resource has at least one chunk (unchunked ones can't merge yet)."""
        ids = [r.id for r in resources]
        if not ids:
            return []
        rows = await db.execute(
            select(ResourceChunk.resource_id).where(ResourceChunk.resource_id.in_(ids)).distinct()
        )
        with_chunks = {row[0] for row in rows.all()}
        return [r.id in with_chunks for r in resources]

    async def _finish_empty(self, db: AsyncSession, knowledge: TopicKnowledge) -> TopicKnowledge:
        knowledge.consolidated_note = _EMPTY_NOTE
        knowledge.key_points = []
        knowledge.concepts = []
        knowledge.source_count = 0
        knowledge.status = KnowledgeStatus.COMPLETED
        knowledge.generated_at = datetime.utcnow()
        await db.commit()
        return knowledge

    async def _finish_unchanged(
        self, db: AsyncSession, knowledge: TopicKnowledge, source_count: int
    ) -> TopicKnowledge:
        knowledge.source_count = source_count
        knowledge.status = KnowledgeStatus.COMPLETED
        # generated_at is left as-is: the note didn't change.
        await db.commit()
        return knowledge

    # ── context building ────────────────────────────────────────────────────

    async def _context_for(self, db: AsyncSession, resources: List[Resource]) -> str:
        """Chunk text for the given resources, grouped by source, capped at the limit."""
        ids = [r.id for r in resources]
        if not ids:
            return ""
        result = await db.execute(
            select(ResourceChunk)
            .where(ResourceChunk.resource_id.in_(ids))
            .order_by(ResourceChunk.resource_id, ResourceChunk.chunk_index)
        )
        chunks = result.scalars().all()

        by_resource: dict[str, list[str]] = {}
        for chunk in chunks:
            text = (chunk.chunk_text or "").strip()
            if text:
                by_resource.setdefault(str(chunk.resource_id), []).append(text)

        parts, total = [], 0
        for i, (_rid, texts) in enumerate(by_resource.items(), 1):
            block = f"=== SOURCE {i} ===\n" + "\n\n".join(texts)
            if total + len(block) > MAX_CONTEXT_CHARS:
                remaining = MAX_CONTEXT_CHARS - total
                if remaining > 500:
                    parts.append(block[:remaining] + "\n[truncated — source too long]")
                break
            parts.append(block)
            total += len(block)
        return "\n\n".join(parts)

    # ── body generation (streamed) ──────────────────────────────────────────

    async def _generate_body(
        self,
        db: AsyncSession,
        topic_id: str,
        topic_name: str,
        mode: str,
        *,
        base_note: Optional[str],
        sources: List[Resource],
        broadcast: Optional[Broadcast],
    ) -> str:
        """Stream the note markdown, emitting deltas, and return the full body."""
        context = await self._context_for(db, sources)
        prompt = (
            self._incremental_prompt(topic_name, base_note or "", context)
            if mode == "incremental"
            else self._full_prompt(topic_name, context)
        )

        await self._emit(broadcast, {"type": "knowledge_stream_start", "topic_id": str(topic_id), "mode": mode})
        buf: list[str] = []
        async for delta in call_llm_stream(
            prompt, task="knowledge_synthesis", temperature=0.3, max_tokens=16000, timeout=120.0
        ):
            buf.append(delta)
            await self._emit(broadcast, {"type": "knowledge_delta", "topic_id": str(topic_id), "delta": delta})
        await self._emit(broadcast, {"type": "knowledge_stream_end", "topic_id": str(topic_id)})

        return "".join(buf).strip()

    async def _emit(self, broadcast: Optional[Broadcast], event: dict) -> None:
        """Fire a streaming event — best-effort, a broadcast failure never fails synthesis."""
        if broadcast is None:
            return
        try:
            await broadcast(event)
        except Exception:
            logger.warning("knowledge stream broadcast failed", exc_info=True)

    def _full_prompt(self, topic_name: str, context: str) -> str:
        source_count = context.count("=== SOURCE ")
        reconcile = (
            "Where sources overlap or contradict, reconcile them — don't repeat each. "
            "Where they complement, merge them into a single complete picture."
            if source_count > 1 else ""
        )
        return f"""You are consolidating all class materials for a topic into one definitive document.

This is NOT a summary. It takes everything across all sources and produces a single
document that covers the topic completely, resolving overlaps and merging complementary
explanations. A student should be able to study ONLY this document and have everything.

TOPIC: {topic_name}

SOURCE MATERIALS:
{context}

{reconcile}

Rules:
- Open with 1–2 plain-English sentences answering "what is this topic actually about?"
- Use ## subheadings organised by concept/theme (not by source).
- Bold the first mention of every important term.
- Bullets for lists; prose for explanations that need flow. Keep examples the sources give.
- Length matches the material — rich material, rich document. Don't pad, don't compress.

Output ONLY the finished markdown document. No preamble, no JSON, no commentary."""

    def _incremental_prompt(self, topic_name: str, base_note: str, context: str) -> str:
        return f"""You are UPDATING an existing consolidated study note by folding in new material.

TOPIC: {topic_name}

Return the COMPLETE updated note — the existing content PLUS the new material, merged in.
This is an incremental update, not a rewrite: preserve the existing note's structure and
content, and weave the new material into the right sections.

EXISTING NOTE:
{base_note}

NEW MATERIAL TO FOLD IN:
{context}

Rules:
- Keep everything already covered — do not drop or shorten existing content without reason.
- Where the new material repeats what's already there, DEDUPE — don't add a second copy.
- Where it contradicts the existing note, reconcile and note the more reliable version.
- Where it adds something genuinely new, add it under the right ## subheading (or a new one).
- Preserve the markdown conventions: plain-English opener, ## subheadings, bold first
  mention of terms, bullets for lists, prose for explanations.

Output ONLY the finished markdown document — the whole updated note. No preamble, no JSON."""

    # ── metadata extraction (whole-parsed) ──────────────────────────────────

    async def _extract_metadata(self, note_body: str, topic_name: str) -> Dict[str, Any]:
        """Pull key_points + concepts out of the finished note (structured, parsed whole)."""
        if not note_body.strip():
            return {"key_points": [], "concepts": []}

        prompt = f"""From this consolidated study note, extract exam-ready metadata.

TOPIC: {topic_name}

NOTE:
{note_body[:MAX_CONTEXT_CHARS]}

KEY_POINTS: the facts a student must know cold to pass an exam.
- 5–10 items (more if warranted); each one specific and self-contained; cover different aspects.

CONCEPTS: terms that need defining.
- 4–12 terms; only ones a student might not know; one plain-English sentence each.

SUBJECT_FAMILY: the single best fit for how this material is best practised. One of:
- "STEM"        — math, science, engineering: worked problems, formulas, derivations.
- "LANGUAGE"    — learning a language: vocabulary, grammar, producing/speaking output.
- "HUMANITIES"  — reading/argument-heavy: history, philosophy, literature, essays.
- "GENERAL"     — none of the above fits cleanly.

Return JSON:
{{
  "key_points": ["specific exam-ready fact", "..."],
  "concepts": [{{"term": "Term", "definition": "One clear sentence."}}],
  "subject_family": "STEM" | "LANGUAGE" | "HUMANITIES" | "GENERAL"
}}

Return ONLY valid JSON. No preamble, no text outside the JSON."""
        content = await call_llm(
            prompt,
            task="knowledge_metadata",
            temperature=0.2,
            max_tokens=4000,
            timeout=60.0,
            response_format={"type": "json_object"},
        )
        return self._parse_json(content)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in AI response")
        return json.loads(text[start:end], strict=False)


# Singleton instance
knowledge_synthesizer = KnowledgeSynthesizer()
