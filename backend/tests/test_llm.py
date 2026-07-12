"""LLM router — model tiering (A1) and streaming completions."""

import pytest

from app.services import llm
from app.services.llm import _resolve_task_model, _extract_delta, call_llm_stream
from app.services.study_agent import study_agent


# --------------------------------------------------------------------------- #
# Model tiering / task→provider resolution
# --------------------------------------------------------------------------- #

def test_task_defaults_resolve_to_mapped_model():
    assert _resolve_task_model("study_chat") == ("openai", "gpt-4o-mini")
    # Quality-critical task rides the heavy tier.
    assert _resolve_task_model("knowledge_synthesis") == ("openai", "gpt-4o")
    # Deterministic/cheap task keeps its deepseek routing.
    assert _resolve_task_model("ocr_clean") == ("deepseek", "deepseek-chat")


def test_unknown_task_falls_back_to_standard():
    assert _resolve_task_model("something_new") == llm._TIER_SPEC["standard"]


def test_env_override_by_tier(monkeypatch):
    # LLM_<TASK> naming a tier retargets that task's model.
    monkeypatch.setattr(llm.settings, "LLM_GRADING", "heavy", raising=False)
    assert _resolve_task_model("grading") == ("openai", "gpt-4o")


def test_env_override_by_provider_is_backcompat(monkeypatch):
    # LLM_<TASK> naming a provider keeps the legacy behaviour (provider default model).
    monkeypatch.setattr(llm.settings, "LLM_GRADING", "deepseek", raising=False)
    assert _resolve_task_model("grading") == ("deepseek", "deepseek-chat")


# --------------------------------------------------------------------------- #
# SSE delta parsing
# --------------------------------------------------------------------------- #

def test_extract_delta_parses_content():
    line = 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    assert _extract_delta(line) == "Hello"


@pytest.mark.parametrize(
    "line",
    [
        "",
        ": keep-alive",
        "data: [DONE]",
        'data: {"choices":[{"delta":{}}]}',   # role frame, no content
        "data: not-json",
    ],
)
def test_extract_delta_ignores_non_content(line):
    assert _extract_delta(line) is None


# --------------------------------------------------------------------------- #
# Streaming generator (faked transport — never hits a real model)
# --------------------------------------------------------------------------- #

class _FakeStream:
    def __init__(self, lines):
        self._lines = lines
        self.status_code = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    async def aread(self):
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeClient:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, **kwargs):
        return _FakeStream(self._lines)


async def test_call_llm_stream_yields_deltas(monkeypatch):
    lines = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr(llm.settings, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: _FakeClient(lines))

    out = [d async for d in call_llm_stream("hi", task="study_chat")]
    assert out == ["Hel", "lo"]
    assert "".join(out) == "Hello"


# --------------------------------------------------------------------------- #
# SSE endpoint wiring (study_agent stubbed — no RAG / real LLM)
# --------------------------------------------------------------------------- #

async def test_study_ask_stream_emits_sse(client, register_user, monkeypatch):
    user = await register_user()
    created = await client.post(
        "/api/courses", headers=user["headers"], json={"code": "BIO101", "name": "Biology 101"}
    )
    assert created.status_code == 201, created.text
    course_id = created.json()["course"]["id"]

    async def fake_stream(**kwargs):
        yield {"type": "meta", "conversation_id": "c1", "sources": []}
        yield {"type": "token", "text": "Hi"}
        yield {"type": "done", "conversation_id": "c1"}

    monkeypatch.setattr(study_agent, "ask_question_stream", fake_stream)

    resp = await client.post(
        f"/api/study/ask/stream?course_id={course_id}",
        headers=user["headers"],
        json={"question": "what is a cell?"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert '"type": "meta"' in body
    assert '"text": "Hi"' in body
    assert '"type": "done"' in body


async def test_study_ask_stream_requires_enrollment(client, register_user):
    """A non-enrolled user can't stream another course's tutor."""
    owner = await register_user()
    created = await client.post(
        "/api/courses", headers=owner["headers"], json={"code": "CHE101", "name": "Chem 101"}
    )
    course_id = created.json()["course"]["id"]

    outsider = await register_user()
    resp = await client.post(
        f"/api/study/ask/stream?course_id={course_id}",
        headers=outsider["headers"],
        json={"question": "hello?"},
    )
    assert resp.status_code == 403
