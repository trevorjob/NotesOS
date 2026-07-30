"""
Conversational modes (teach · ramble) — the open/turn/close dialogue layer.

Pure, DB-free: the turn LLM (``conversation.call_llm``) and the close judge
(``_judge`` / ``_analyze``) are stubbed. We pin the dig-vs-close decision, the
never-send-an-empty-probe guard, grading over the *whole* transcript, the blank
short-circuit, and that both modes still expose the one-shot contract unchanged.
"""

import json
import uuid

from app.models import Concept
from app.services.retrieval import conversation
from app.services.retrieval.modes import (
    ROLE_AI,
    ROLE_USER,
    ConversationTurn,
    ModeContext,
    is_conversational,
    join_user_turns,
    user_turns,
)
from app.services.retrieval.ramble_mode import RambleMode
from app.services.retrieval.teach_mode import TeachMode

CTX = ModeContext(db=None, user_id=None)


def _concept():
    c = Concept(text="Entropy", definition="a measure of disorder")
    c.id = uuid.uuid4()
    return c


def _stub_turn_llm(monkeypatch, payload: dict):
    async def fake_call(prompt, **kwargs):
        return json.dumps(payload)

    monkeypatch.setattr(conversation, "call_llm", fake_call)


def test_teach_and_ramble_are_conversational():
    assert is_conversational(TeachMode())
    assert is_conversational(RambleMode())


def test_join_user_turns_takes_only_the_user_side():
    history = [
        ConversationTurn(ROLE_AI, "explain it"),
        ConversationTurn(ROLE_USER, "it spreads out"),
        ConversationTurn(ROLE_AI, "why?"),
        ConversationTurn(ROLE_USER, "because of probability"),
    ]
    assert len(user_turns(history)) == 2
    assert join_user_turns(history) == "it spreads out\nbecause of probability"


async def test_turn_digs_when_there_is_more_to_pull(monkeypatch):
    _stub_turn_llm(monkeypatch, {"done": False, "reply": "But why does that happen?"})
    history = [ConversationTurn(ROLE_AI, "explain"), ConversationTurn(ROLE_USER, "it just does")]
    result = await TeachMode().turn(_concept(), history, CTX)
    assert result.closed is False
    assert result.reply == "But why does that happen?"


async def test_turn_closes_when_model_is_done(monkeypatch):
    _stub_turn_llm(monkeypatch, {"done": True, "reply": ""})
    result = await RambleMode().turn(_concept(), [ConversationTurn(ROLE_USER, "all of it")], CTX)
    assert result.closed is True
    assert result.close_reason == "ran_dry"


async def test_turn_closes_when_reply_is_blank(monkeypatch):
    # done:false but an empty reply must still close — never send an empty probe.
    _stub_turn_llm(monkeypatch, {"done": False, "reply": "   "})
    result = await TeachMode().turn(_concept(), [ConversationTurn(ROLE_USER, "x")], CTX)
    assert result.closed is True


async def test_close_grades_over_the_whole_transcript():
    seen = {}

    class StubTeach(TeachMode):
        async def _judge(self, concept, explanation, ctx):
            seen["explanation"] = explanation
            return {"correctness": 0.8, "completeness": 0.8, "clarity": 0.8, "feedback": "clear"}

    history = [
        ConversationTurn(ROLE_AI, "explain"),
        ConversationTurn(ROLE_USER, "it spreads out"),
        ConversationTurn(ROLE_AI, "why?"),
        ConversationTurn(ROLE_USER, "because of probability"),
    ]
    outcome = await StubTeach().close(_concept(), history, CTX)
    assert "because of probability" in seen["explanation"]  # both user turns graded
    assert outcome.grade == "good"


async def test_close_on_a_blank_transcript_is_a_lapse():
    class Boom(RambleMode):
        async def _analyze(self, *args, **kwargs):
            raise AssertionError("should not grade a blank")

    outcome = await Boom().close(_concept(), [ConversationTurn(ROLE_AI, "go")], CTX)
    assert (outcome.grade, outcome.score) == ("again", 0.0)


async def test_one_shot_contract_still_works():
    # generate/evaluate are untouched — run_once / offline / tests still drive these.
    class StubRamble(RambleMode):
        async def _analyze(self, concept, said, ctx):
            return {"coverage": 0.9, "covered": ["a"], "missed": []}

    mode = StubRamble()
    ctx = CTX
    challenge = await mode.generate(_concept(), ctx)
    assert challenge.payload["free_recall"] is True
    outcome = await mode.evaluate(_concept(), challenge, "a full dump", ctx)
    assert outcome.score == 0.9
