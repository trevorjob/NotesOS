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
CLASSIFY_SAMPLE_CHARS = 4_000  # B10: family is only a *prior*, so classify cheaply off a sample
_EMPTY_NOTE = "_No materials uploaded yet. Add notes or files to generate a consolidated summary._"

# B10 — content picks form. Taught to EVERY synthesis prompt regardless of subject family:
# the family is only a prior (a one-line lean below), never a gate that swaps templates. The
# real bug this fixes is the prompt having no worked-example/math vocabulary at all ("prose
# for explanations" was humanities-tuned). Failure runs both ways — the rules guard both.
_FORM_RULES = """FORM FOLLOWS CONTENT (important):
- Let the material decide the shape. Definitions, theory, and intuition are prose.
  Problem-solving, derivations, and proofs are **worked examples** — keep every step,
  never compress a derivation into a paragraph. A single topic often mixes both freely.
- Render ALL mathematics as LaTeX: $…$ inline, $$…$$ for display equations. Never write
  math as plain text and never prose-flatten a formula or a derivation.
- Keep worked examples and derivations step-structured (numbered or line-by-line steps).
- Keep code in fenced ``` blocks and tabular data in Markdown tables — never prose-ify an
  algorithm or a comparison table.
- Do NOT invent structure the material lacks: don't inflate a two-line definition into a
  fake worked example, and don't add math to a topic that genuinely has none.

STRUCTURE BEFORE PROSE (this is how the note stays studiable, not a wall of text):
- Objective for every section: a student must be able to lift its core ideas AT A GLANCE,
  with no connective filler to read past. Prose is your fallback prior — and that fallback
  is exactly the failure to avoid. Do not default to paragraphs; derive each section's shape
  from what its material is actually *doing*. There is no default to fall back on.
- When a section covers several things of the same kind (sites, cases, categories, events,
  species, causes…), give each its own labelled entry that leads with its recallable core —
  itemised entries (e.g. *name · key attributes · why it matters*), a grouped or ordered
  list, or a genuine multi-axis comparison table. Lead every section with the idea a student
  must recall, never a warm-up sentence.
- Prose is still correct where an idea genuinely needs FLOW — an argument, a causal account,
  a narrative or a derivation that only makes sense read start-to-end. Do NOT shred those into
  disconnected bullets, and do NOT force a table onto ideas that aren't tabular. Over-
  structuring is the same bug as under-structuring, pointed the other way. (Tables read dense
  and high-level — reach for one only on real multi-axis comparison, so rarely.)
- Self-check before you finish: for each section, can its cores be pulled at a glance? Is any
  sentence pure connective tissue with nothing to recall? If so, restructure it."""

# The one-line lean per family — a bias on the default, not a command. Empty for GENERAL
# (let the content speak entirely). A wrong guess degrades gracefully to content-driven form.
_FAMILY_LEAN: dict[SubjectFamily, str] = {
    SubjectFamily.STEM: (
        "This topic is likely STEM — expect many worked examples, derivations, and formulas. "
        "Render those with math and keep the steps intact; still use prose for definitions and intuition."
    ),
    SubjectFamily.LANGUAGE: (
        "This topic is likely language-learning — expect vocabulary, example sentences, and grammar. "
        "Prose and lists lead; use math only if the material genuinely has it."
    ),
    SubjectFamily.HUMANITIES: (
        "This topic is likely reading/argument-heavy — expect mostly prose and structured explanation. "
        "Use worked examples or math only where the material actually contains them."
    ),
    SubjectFamily.SOCIAL_SCIENCE: (
        "This topic is likely social science — expect named theories, studies, and frameworks applied to "
        "evidence. Prose and labelled entries (theory · claim · evidence) lead; use tables for real "
        "multi-axis comparison and math only where the material genuinely has statistics."
    ),
    SubjectFamily.GENERAL: "",
}


def _family_lean_block(family: SubjectFamily) -> str:
    lean = _FAMILY_LEAN.get(family, "")
    return f"SUBJECT LEAN: {lean}\n\n" if lean else ""

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


def _extract_family_token(raw: Optional[str]) -> Optional[str]:
    """Pull the first family keyword out of a classification reply (tolerates chatty models)."""
    text = (raw or "").upper()
    for family in SubjectFamily:
        if family.value in text:
            return family.value
    return None


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

            # B10: classify the family *before* writing the note, so the prompt lean +
            # client render hint are available. It's a prior, not a gate — a wrong guess
            # degrades to content-driven form. User overrides win and skip the LLM.
            family = await self._classify_family(db, topic_id, sources, mode=mode)

            body = await self._generate_body(
                db, topic_id, topic_name, mode,
                base_note=knowledge.consolidated_note if mode == "incremental" else None,
                sources=sources,
                family=family,
                broadcast=broadcast,
            )
            meta = await self._extract_metadata(body, topic_name)

            knowledge.consolidated_note = body
            knowledge.key_points = meta.get("key_points", [])
            knowledge.concepts = meta.get("concepts", [])
            knowledge.source_count = len(resources)
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

    async def _classify_family(
        self, db: AsyncSession, topic_id: str, sources: List[Resource], *, mode: str
    ) -> SubjectFamily:
        """Pre-classify the topic's subject family from raw chunks, before the note is written.

        A user override wins and skips the LLM. On incremental merges an already-inferred
        family is kept (don't flip-flop off a partial new chunk); on a full build, or while
        the family is still the GENERAL default, (re)classify. Because the family is only a
        prior — a lean on the prompt + a render hint — a wrong guess degrades gracefully, so
        this stays deliberately cheap (a sample of the chunks, fast tier).
        """
        topic = await db.scalar(select(Topic).where(Topic.id == _uuid.UUID(str(topic_id))))
        if topic is None:
            return SubjectFamily.GENERAL
        if topic.subject_family_overridden:
            return topic.subject_family
        if mode == "incremental" and topic.subject_family != SubjectFamily.GENERAL:
            return topic.subject_family

        family = await self._infer_family(db, sources)
        topic.subject_family = family
        return family

    async def _infer_family(self, db: AsyncSession, sources: List[Resource]) -> SubjectFamily:
        """One cheap, fast-tier LLM classification off a sample of the material."""
        sample = (await self._context_for(db, sources))[:CLASSIFY_SAMPLE_CHARS]
        if not sample.strip():
            return SubjectFamily.GENERAL
        try:
            raw = await call_llm(
                self._classify_prompt(sample),
                task="subject_classify", temperature=0.0, max_tokens=16, timeout=30.0,
            )
        except Exception:
            logger.warning("subject pre-classification failed; defaulting to GENERAL", exc_info=True)
            return SubjectFamily.GENERAL
        return _coerce_family(_extract_family_token(raw))

    def _classify_prompt(self, sample: str) -> str:
        return f"""Classify the subject family of this study material. Reply with EXACTLY ONE word.

- STEM            — math, science, engineering: worked problems, formulas, derivations.
- LANGUAGE        — learning a language: vocabulary, grammar, producing/speaking output.
- HUMANITIES      — reading/argument-heavy: history, philosophy, literature, essays.
- SOCIAL_SCIENCE  — psychology, sociology, economics, political science: theories, studies, frameworks, evidence.
- GENERAL         — none of the above fits cleanly.

MATERIAL:
{sample}

One word only:"""

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
        family: SubjectFamily,
        broadcast: Optional[Broadcast],
    ) -> str:
        """Stream the note markdown, emitting deltas, and return the full body."""
        context = await self._context_for(db, sources)
        prompt = (
            self._incremental_prompt(topic_name, base_note or "", context, family)
            if mode == "incremental"
            else self._full_prompt(topic_name, context, family)
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

    def _full_prompt(self, topic_name: str, context: str, family: SubjectFamily) -> str:
        source_count = context.count("=== SOURCE ")
        reconcile = (
            "Where sources overlap or contradict, reconcile them — don't repeat each. "
            "Where they complement, merge them into a single complete picture."
            if source_count > 1 else ""
        )
        return f"""You are consolidating all class materials for a topic into one studiable note.

This is NOT a summary and NOT an exhaustive transcript. The raw uploads are kept verbatim as
the *source layer* — the complete archive a student can always re-read — so this note does not
have to hoard every sentence. Its job is the *studiable structure* on top: the shape a student
would actually study and practise from, with each idea pulled into a form they can recall at a
glance. Reconcile overlaps and merge complementary explanations across sources.

TOPIC: {topic_name}

{_family_lean_block(family)}SOURCE MATERIALS:
{context}

{reconcile}

Rules:
- Open with 1–2 plain-English sentences answering "what is this topic actually about?"
- Use ## subheadings organised by concept/theme (not by source).
- Bold the first mention of every important term.
- Lead each section with its recallable core; cut connective filler.
- Length matches the material's *ideas*, not its word count — rich material, rich structure.
  Don't pad, and don't flatten distinct ideas into a paragraph to save space.

{_FORM_RULES}

Output ONLY the finished markdown document. No preamble, no JSON, no commentary."""

    def _incremental_prompt(self, topic_name: str, base_note: str, context: str, family: SubjectFamily) -> str:
        return f"""You are UPDATING an existing consolidated study note by folding in new material.

TOPIC: {topic_name}

{_family_lean_block(family)}Return the COMPLETE updated note — the existing content PLUS the new material, merged in.
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
- Preserve the markdown conventions: plain-English opener, ## subheadings, bold first mention.
- Preserve existing worked examples and derivations intact — never dedupe, compress, or
  "tighten" a worked example or its steps out of existence when merging.

{_FORM_RULES}

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
- 4–12 terms (more if warranted); only ones a student might not know; one plain-English sentence each.
- For STEM material, a "concept" can be a **procedure or skill** ("differentiate a composite
  function", "balance a redox equation"), not just a term↔definition — name the procedure as the
  term and give a one-line method sketch as the definition. These become worked problems.

Return JSON:
{{
  "key_points": ["specific exam-ready fact", "..."],
  "concepts": [{{"term": "Term", "definition": "One clear sentence."}}]
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
