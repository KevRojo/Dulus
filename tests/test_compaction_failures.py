"""A failed summary must never cost the conversation its history.

When the summarizer timed out or the provider was down, compaction replaced
everything older than the recent turns with a "(summary skipped …)" card. An
adapter's error turn was even taken as the summary itself.
"""
from __future__ import annotations

from types import SimpleNamespace

import compaction
import providers

CONFIG = {"model": "openai/gpt-4o"}


def _conversation(pairs: int) -> list:
    msgs = []
    for i in range(pairs):
        msgs.append({"role": "user", "content": f"question {i} " + "q" * 400})
        msgs.append({"role": "assistant", "content": f"answer {i} " + "a" * 400})
    return msgs


def test_error_turn_is_not_taken_as_the_summary(monkeypatch) -> None:
    def down(**kwargs):
        yield providers.TextChunk("Network problem reaching the API.")
        yield providers.AssistantTurn("Network problem reaching the API.", [], 0, 0, error=True)

    monkeypatch.setattr(providers, "stream", down)
    messages = _conversation(30)

    assert compaction.compact_messages(messages, CONFIG) is messages


def test_timed_out_summary_keeps_the_history(monkeypatch) -> None:
    monkeypatch.setattr(compaction, "_run_summarizer", lambda *a, **k: ("", True))
    messages = _conversation(30)
    before = list(messages)

    out = compaction.compact_messages(messages, CONFIG)

    assert out is messages
    assert out == before


def test_a_real_summary_still_compacts(monkeypatch) -> None:
    def summarize(**kwargs):
        yield providers.TextChunk("dense summary")
        yield providers.AssistantTurn("dense summary", [], 0, 0)

    monkeypatch.setattr(providers, "stream", summarize)
    messages = _conversation(30)

    out = compaction.compact_messages(messages, CONFIG)

    assert len(out) < len(messages)
    assert any("dense summary" in str(m.get("content")) for m in out)


def test_auto_compact_backs_off_instead_of_retrying_every_tool_call(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(compaction, "_run_summarizer",
                        lambda *a, **k: calls.append(1) or ("", True))
    monkeypatch.setattr(compaction, "get_context_limit", lambda model, config=None: 1000)
    state = SimpleNamespace(messages=_conversation(30))
    before = list(state.messages)
    config = dict(CONFIG)

    assert compaction.maybe_compact(state, config) is False
    assert state.messages == before
    compaction.maybe_compact(state, config)
    assert len(calls) == 1, "summarizer retried on the very next tool call"

    state.messages.extend(_conversation(5))
    compaction.maybe_compact(state, config)
    assert len(calls) == 2, "never retried after the history grew"

    state.messages = _conversation(20)   # /clear, then a new long chat
    compaction.maybe_compact(state, config)
    assert len(calls) == 3, "a stale backoff blocked compaction of a new history"


def test_null_tool_calls_do_not_break_token_estimates() -> None:
    # OpenAI-style sessions store "tool_calls": null on plain replies.
    msgs = [{"role": "assistant", "content": "hi", "tool_calls": None}]
    assert compaction.estimate_tokens(msgs) > 0
