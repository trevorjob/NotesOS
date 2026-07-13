"""
NotesOS - LLM Router
Single call site for all AI completions. Pick provider + model tier per task.

Usage:
    from app.services.llm import call_llm, call_llm_stream

    text = await call_llm(prompt, task="grading")
    text = await call_llm(prompt, task="study_chat", system=system_prompt, messages=history)

    async for delta in call_llm_stream(prompt, task="study_chat", messages=history):
        ...  # stream text deltas to the client (SSE)

Model tiering
-------------
Every task resolves to a (provider, model) pair. "Fast" is a cheap/low-latency
model for interactive or high-frequency work; "heavy" is a stronger model reserved
for quality-critical output (the consolidated note). Override any task with the
env var ``LLM_<TASK>`` — set it to a provider name (``openai``/``deepseek``, kept
for back-compat) OR a tier name (``fast``/``standard``/``heavy``).
"""

import json
import httpx
import logging
from typing import Any, AsyncIterator

from app.config import settings

logger = logging.getLogger(__name__)

# OpenAI-compatible base URLs (both providers speak /chat/completions)
_OPENAI_BASE = "https://api.openai.com/v1"
_DEEPSEEK_BASE = "https://api.deepseek.com/v1"

# Default model per provider
_OPENAI_MODEL = "gpt-4o-mini"
_DEEPSEEK_MODEL = "deepseek-chat"

_PROVIDER_DEFAULT_MODEL: dict[str, str] = {
    "openai": _OPENAI_MODEL,
    "deepseek": _DEEPSEEK_MODEL,
}

# A tier names a (provider, model). Tasks map to these so intent ("this is a
# fast/interactive task", "this one needs quality") is expressed once and tuned
# in one place. cost == speed: fast tier is simultaneously cheaper and quicker.
_TIER_SPEC: dict[str, tuple[str, str]] = {
    "fast":     ("openai", "gpt-4o-mini"),
    "standard": ("openai", "gpt-4o-mini"),
    "heavy":    ("openai", "gpt-4o"),
}

# Task → default (provider, model). Trailing comment marks the intended tier.
# Override any task via env: LLM_<TASK>=<provider|tier>.
_TASK_MODEL_MAP: dict[str, tuple[str, str]] = {
    "question_gen":        ("openai",   "gpt-4o-mini"),   # standard
    "grading":             ("openai",   "gpt-4o-mini"),   # standard
    "study_chat":          ("openai",   "gpt-4o-mini"),   # fast — interactive tutor
    "knowledge_synthesis": ("openai",   "gpt-4o"),        # heavy — the consolidated note (streamed body)
    "knowledge_metadata":  ("openai",   "gpt-4o-mini"),   # fast — extract key_points/concepts from the finished note
    "fact_check":          ("openai",   "gpt-4o-mini"),   # standard
    "research":            ("openai",   "gpt-4o-mini"),   # standard
    "audio_script":        ("openai",   "gpt-4o-mini"),   # fast
    "ocr_clean":           ("deepseek", "deepseek-chat"), # fast — cheap, deterministic
    "outline_parse":       ("openai",   "gpt-4o-mini"),   # fast — syllabus → topic list
    "capture_organize":    ("openai",   "gpt-4o-mini"),   # fast — classify/name a dump
    "recap_eval":          ("openai",   "gpt-4o"),         # heavy — grades a monologue over many concepts
    "voice_chat":          ("openai",   "gpt-4o-mini"),    # fast — the spoken tutor reply (streamed, low-latency)
}


def _resolve_task_model(task: str) -> tuple[str, str]:
    """Resolve a task to a concrete (provider, model).

    Precedence: per-task env override ``LLM_<TASK>`` (provider name for back-compat,
    or a tier name) > the task's mapped default > the ``standard`` tier.
    """
    override = (getattr(settings, f"LLM_{task.upper()}", "") or "").strip().lower()
    if override in _TIER_SPEC:
        return _TIER_SPEC[override]
    if override in _PROVIDER_DEFAULT_MODEL:
        return override, _PROVIDER_DEFAULT_MODEL[override]
    if task in _TASK_MODEL_MAP:
        return _TASK_MODEL_MAP[task]
    return _TIER_SPEC["standard"]


def _provider_conn(provider: str) -> tuple[str, str]:
    """Return (base_url, api_key) for a provider, raising if the key is missing."""
    if provider == "deepseek":
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not configured")
        return _DEEPSEEK_BASE, api_key
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return _OPENAI_BASE, api_key


def _build_messages(
    prompt: str,
    system: str | None,
    messages: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Assemble the messages array, or pass through an explicit one."""
    if messages is not None:
        return messages
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    out.append({"role": "user", "content": prompt})
    return out


def _completion_body(
    model: str,
    payload_messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    response_format: dict[str, Any] | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": payload_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        body["response_format"] = response_format
    if stream:
        body["stream"] = True
    return body


async def call_llm(
    prompt: str,
    *,
    task: str,
    system: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    temperature: float = 0.5,
    max_tokens: int = 2000,
    timeout: float = 120.0,
    response_format: dict[str, Any] | None = None,
) -> str:
    """
    Call the appropriate LLM for the given task and return the full completion.

    Args:
        prompt:      User turn content (ignored when messages is provided).
        task:        Logical task name — determines provider + model tier.
        system:      Optional system prompt (prepended as role=system).
        messages:    Full messages array (overrides prompt + system if provided).
        temperature: Sampling temperature.
        max_tokens:  Max completion tokens.
        timeout:     HTTP timeout in seconds.
        response_format: Optional OpenAI-compatible response_format, e.g.
                     {"type": "json_object"} to force syntactically valid JSON.

    Returns:
        The assistant message content string.
    """
    provider, model = _resolve_task_model(task)
    base_url, api_key = _provider_conn(provider)
    payload_messages = _build_messages(prompt, system, messages)

    logger.debug("[LLM] task=%s provider=%s model=%s tokens=%d", task, provider, model, max_tokens)

    body = _completion_body(model, payload_messages, temperature, max_tokens, response_format)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _extract_delta(line: str) -> str | None:
    """Parse one SSE line from an OpenAI-compatible stream into a text delta.

    Returns the incremental content, or None for keep-alives, ``[DONE]``, and any
    line without a content delta.
    """
    if not line or not line.startswith("data:"):
        return None
    data = line[len("data:"):].strip()
    if not data or data == "[DONE]":
        return None
    try:
        obj = json.loads(data)
        return obj["choices"][0]["delta"].get("content")
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


async def call_llm_stream(
    prompt: str,
    *,
    task: str,
    system: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    temperature: float = 0.5,
    max_tokens: int = 2000,
    timeout: float = 120.0,
) -> AsyncIterator[str]:
    """
    Stream a completion for the given task, yielding text deltas as they arrive.

    Same routing/tiering as ``call_llm``. Callers accumulate the deltas (e.g. to
    persist the full answer) while forwarding each one to the client over SSE.
    """
    provider, model = _resolve_task_model(task)
    base_url, api_key = _provider_conn(provider)
    payload_messages = _build_messages(prompt, system, messages)

    logger.debug("[LLM stream] task=%s provider=%s model=%s tokens=%d", task, provider, model, max_tokens)

    body = _completion_body(model, payload_messages, temperature, max_tokens, stream=True)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        ) as response:
            if response.status_code >= 400:
                # Body isn't read yet on a streamed response — read it so the
                # raised error carries the provider's message.
                await response.aread()
                response.raise_for_status()
            async for line in response.aiter_lines():
                delta = _extract_delta(line)
                if delta:
                    yield delta
