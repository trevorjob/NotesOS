"""
NotesOS - LLM Router
Single call site for all AI completions. Pick provider per task via env vars.

Usage:
    from app.services.llm import call_llm

    text = await call_llm(prompt, task="grading")
    text = await call_llm(prompt, task="study_chat", system=system_prompt, messages=history)
"""

import httpx
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# OpenAI-compatible base URLs
_OPENAI_BASE = "https://api.openai.com/v1"
_DEEPSEEK_BASE = "https://api.deepseek.com/v1"

# Default model per provider
_OPENAI_MODEL = "gpt-4o-mini"
_DEEPSEEK_MODEL = "deepseek-chat"

# Task → provider map. Override any task by setting e.g. LLM_GRADING=deepseek in .env.
# "openai"   → OpenAI API (gpt-4o-mini by default)
# "deepseek" → DeepSeek API (deepseek-chat)
_TASK_PROVIDER_MAP: dict[str, str] = {
    "question_gen":          "openai",
    "grading":               "openai",
    "study_chat":            "openai",
    "knowledge_synthesis":   "openai",
    "fact_check":            "openai",
    "research":              "openai",
    "audio_script":          "openai",
    "ocr_clean":             "deepseek",  # cheap + deterministic, no quality difference
}


def _provider_for(task: str) -> str:
    """Read task provider from env (LLM_<TASK>=openai|deepseek) with map fallback."""
    env_key = f"LLM_{task.upper()}"
    env_val = getattr(settings, env_key, None)
    if env_val:
        return env_val.lower()
    return _TASK_PROVIDER_MAP.get(task, "openai")


async def call_llm(
    prompt: str,
    *,
    task: str,
    system: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    temperature: float = 0.5,
    max_tokens: int = 2000,
    timeout: float = 120.0,
) -> str:
    """
    Call the appropriate LLM for the given task.

    Args:
        prompt:      User turn content (ignored when messages is provided).
        task:        Logical task name — determines which provider to use.
        system:      Optional system prompt (prepended as role=system).
        messages:    Full messages array (overrides prompt + system if provided).
                     Each entry: {"role": "user"|"assistant"|"system", "content": str}
        temperature: Sampling temperature.
        max_tokens:  Max completion tokens.
        timeout:     HTTP timeout in seconds.

    Returns:
        The assistant message content string.
    """
    provider = _provider_for(task)

    if provider == "deepseek":
        base_url = _DEEPSEEK_BASE
        model = _DEEPSEEK_MODEL
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not configured")
    else:
        base_url = _OPENAI_BASE
        model = _OPENAI_MODEL
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

    if messages is not None:
        payload_messages = messages
    else:
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.append({"role": "user", "content": prompt})

    logger.debug("[LLM] task=%s provider=%s model=%s tokens=%d", task, provider, model, max_tokens)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": payload_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
