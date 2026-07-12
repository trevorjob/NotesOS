"""
NotesOS - Capture service: the "organization is deferred and smart" half.

Capture's governing rule (product-map, LOCKED): capture is instant and dumb;
organization is deferred and smart. This module is the smart half:

- ``parse_outline``       — syllabus text → an ordered topic list (the scaffold).
- ``classify_items``      — outline path: assign each dumped file to a known topic
                            (reliable — matching against labeled buckets).
- ``cluster_items``       — no-outline path: embed + greedy-cluster the pile.
- ``name_clusters``       — LLM names each proposed cluster.
- ``estimate_confidence`` — honesty seam: a cheap transcript-quality score so a
                            blurry scan is flagged, never laundered into the note.

Every LLM call goes through ``call_llm`` (single-call-site rule) and is isolated
behind one module-level function so tests stub exactly one seam per behaviour.
"""

import json
import math
from typing import Any, Optional

from app.services.llm import call_llm

# ── Tuning knobs ──────────────────────────────────────────────────────────────
# Cosine similarity for two files to share a proposed topic (no-outline path).
CLUSTER_THRESHOLD = 0.55
# Transcript excerpt fed to classify/cluster — enough signal, bounded cost.
EXCERPT_CHARS = 1200
# Below this ocr_confidence a resource is surfaced as needs-review.
NEEDS_REVIEW_THRESHOLD = 0.7


# ── Outline scaffold ─────────────────────────────────────────────────────────


async def parse_outline(raw_text: str) -> list[dict[str, Any]]:
    """Parse a pasted/snapped syllabus into an ordered topic list.

    Returns ``[{"title": str, "description": str|None, "week_number": int|None}]``.
    Order in = order out (the syllabus order is the canonical order).
    """
    prompt = f"""Below is a course outline/syllabus a student pasted or photographed.
Extract the ordered list of TOPICS the course covers.

Rules:
- One entry per real topic/unit/week of content. Skip admin noise (grading policy,
  office hours, textbook lists, exam dates without content).
- Keep the original order.
- "title" is required, short, and specific (e.g. "Aromaticity", not "Week 4").
- "description" is optional — only when the outline gives one.
- "week_number" only when the outline explicitly numbers weeks.

Return JSON: {{"topics": [{{"title": "...", "description": null, "week_number": null}}]}}

OUTLINE:
{raw_text}"""

    raw = await call_llm(
        prompt,
        task="outline_parse",
        temperature=0.1,
        max_tokens=3000,
        timeout=60.0,
        response_format={"type": "json_object"},
    )
    data = _parse_json(raw)
    topics = data.get("topics") or []
    # Validate at the boundary — never trust model output shape.
    cleaned: list[dict[str, Any]] = []
    for entry in topics:
        title = (entry.get("title") or "").strip() if isinstance(entry, dict) else ""
        if not title:
            continue
        cleaned.append(
            {
                "title": title[:255],
                "description": (entry.get("description") or None),
                "week_number": entry.get("week_number")
                if isinstance(entry.get("week_number"), int)
                else None,
            }
        )
    return cleaned


# ── Outline path: classification ─────────────────────────────────────────────


async def classify_items(
    items: list[dict[str, Any]], topic_titles: list[str]
) -> list[dict[str, Any]]:
    """Assign each dumped item to one of the known topics (one LLM call).

    ``items``: ``[{"name": str, "excerpt": str}]``.
    Returns one entry per item, same order:
    ``{"topic_index": int}`` (index into topic_titles) or
    ``{"new_topic": str}`` when nothing fits (worst case is a one-drag fix —
    misfiling into a wrong bucket is worse than proposing a new one).
    """
    if not items:
        return []

    topics_block = "\n".join(f"{i}. {t}" for i, t in enumerate(topic_titles))
    files_block = "\n\n".join(
        f"FILE {i} ({item['name']}):\n{item['excerpt'][:EXCERPT_CHARS]}"
        for i, item in enumerate(items)
    )
    prompt = f"""A student bulk-uploaded study files into a course. File each one into
the course's existing topics.

TOPICS (index. title):
{topics_block}

For each file return either:
- {{"file": <i>, "topic_index": <topic index>}} — when it clearly belongs there, or
- {{"file": <i>, "new_topic": "<short title>"}} — when it fits NO existing topic.
Prefer an existing topic when it's a reasonable fit; propose new only when clearly none fit.

Return JSON: {{"assignments": [ ... one per file ... ]}}

FILES:
{files_block}"""

    raw = await call_llm(
        prompt,
        task="capture_organize",
        temperature=0.1,
        max_tokens=2000,
        timeout=90.0,
        response_format={"type": "json_object"},
    )
    data = _parse_json(raw)
    by_file: dict[int, dict[str, Any]] = {}
    for entry in data.get("assignments") or []:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("file")
        if not isinstance(idx, int):
            continue
        topic_index = entry.get("topic_index")
        if isinstance(topic_index, int) and 0 <= topic_index < len(topic_titles):
            by_file[idx] = {"topic_index": topic_index}
        elif (entry.get("new_topic") or "").strip():
            by_file[idx] = {"new_topic": entry["new_topic"].strip()[:255]}

    # Anything the model skipped/malformed falls back to a new "Unsorted" bucket —
    # never drop a file on the floor.
    return [
        by_file.get(i, {"new_topic": "Unsorted"})
        for i in range(len(items))
    ]


# ── No-outline path: cluster + name ──────────────────────────────────────────


def cluster_items(embeddings: list[list[float]]) -> list[int]:
    """Greedy centroid clustering — returns a cluster id per item.

    Each item joins the first cluster whose centroid cosine ≥ CLUSTER_THRESHOLD,
    else starts a new one. Simple and dependency-free; the confirm/tweak step is
    the accuracy backstop.
    """
    centroids: list[list[float]] = []
    counts: list[int] = []
    labels: list[int] = []

    for vec in embeddings:
        best_idx, best_sim = -1, -1.0
        for i, centroid in enumerate(centroids):
            sim = _cosine(vec, centroid)
            if sim > best_sim:
                best_idx, best_sim = i, sim
        if best_idx >= 0 and best_sim >= CLUSTER_THRESHOLD:
            labels.append(best_idx)
            # Update the running centroid (new mean; new list — no mutation).
            n = counts[best_idx]
            centroids[best_idx] = [
                (c * n + v) / (n + 1) for c, v in zip(centroids[best_idx], vec)
            ]
            counts[best_idx] = n + 1
        else:
            centroids.append(list(vec))
            counts.append(1)
            labels.append(len(centroids) - 1)

    return labels


async def name_clusters(clusters: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """LLM names each proposed cluster from its members' excerpts (one call).

    ``clusters``: list of member-item lists (``{"name", "excerpt"}``).
    Returns ``[{"title": str, "description": str|None}]``, one per cluster.
    """
    if not clusters:
        return []

    blocks = []
    for i, members in enumerate(clusters):
        sample = "\n---\n".join(
            f"({m['name']}) {m['excerpt'][:400]}" for m in members[:5]
        )
        blocks.append(f"CLUSTER {i} ({len(members)} files):\n{sample}")
    prompt = f"""A student's bulk-uploaded study files were grouped by content similarity.
Give each cluster a short, specific topic title a student would recognise from their
course (e.g. "Chemical Bonding", not "Cluster 1" or "Miscellaneous Notes").

Return JSON: {{"clusters": [{{"index": <i>, "title": "...", "description": null}}]}}

{chr(10).join(blocks)}"""

    raw = await call_llm(
        prompt,
        task="capture_organize",
        temperature=0.3,
        max_tokens=1500,
        timeout=60.0,
        response_format={"type": "json_object"},
    )
    data = _parse_json(raw)
    by_index: dict[int, dict[str, Any]] = {}
    for entry in data.get("clusters") or []:
        if isinstance(entry, dict) and isinstance(entry.get("index"), int):
            title = (entry.get("title") or "").strip()
            if title:
                by_index[entry["index"]] = {
                    "title": title[:255],
                    "description": entry.get("description") or None,
                }
    return [
        by_index.get(i, {"title": f"Topic {i + 1}", "description": None})
        for i in range(len(clusters))
    ]


# ── Honesty seam: low-confidence extraction ──────────────────────────────────


def estimate_confidence(transcript: str) -> Optional[float]:
    """Cheap transcript-quality score in [0, 1] from the vision prompt's own
    uncertainty markers (``[?]``, ``[illegible ...]``).

    The transcriber is instructed to flag gaps rather than skip them, so marker
    density is an honest proxy for extraction quality. Returns None for empty text.
    """
    if not transcript or not transcript.strip():
        return None
    words = max(len(transcript.split()), 1)
    markers = transcript.count("[?]") + transcript.count("[illegible")
    # Each marker wounds confidence in proportion to how much text it shadows;
    # 25 words per marker → 0.0 keeps short-but-clean notes at 1.0.
    penalty = min(markers * 25.0 / words, 1.0)
    return round(1.0 - penalty, 3)


def needs_review(ocr_confidence: Optional[float]) -> bool:
    """Whether a resource should carry the "hard to read — check it?" flag."""
    return ocr_confidence is not None and float(ocr_confidence) < NEEDS_REVIEW_THRESHOLD


# ── Internals ────────────────────────────────────────────────────────────────


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _parse_json(text: str) -> dict[str, Any]:
    """Slice to the outer braces (defensive) and parse leniently."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end], strict=False)
    except json.JSONDecodeError:
        return {}
