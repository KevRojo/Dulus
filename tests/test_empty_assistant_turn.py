"""A reasoning-only stall leaves an empty assistant turn in history.

agent.run keeps {"role": "assistant", "content": "", "tool_calls": []} after
the model spends its whole budget on reasoning. Both converters must turn it
into something the API accepts, or every later prompt in the session 400s.
"""
from __future__ import annotations

import providers

STALL = [
    {"role": "user", "content": "Prove the theorem."},
    {"role": "assistant", "content": "", "thinking": "", "tool_calls": []},
    {"role": "user", "content": "Try again, shorter."},
]


def test_openai_empty_assistant_gets_string_content():
    out = providers.messages_to_openai(STALL)
    assert out[1] == {"role": "assistant", "content": ""}


def test_openai_tool_call_turn_keeps_null_content():
    msgs = [
        {"role": "user", "content": "ls"},
        {"role": "assistant", "content": "",
         "tool_calls": [{"id": "c1", "name": "Bash", "input": {"command": "ls"}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "Bash", "content": "a.txt"},
    ]
    out = providers.messages_to_openai(msgs)
    assert out[1]["content"] is None
    assert out[1]["tool_calls"][0]["id"] == "c1"


def test_anthropic_empty_assistant_is_dropped():
    out = providers.messages_to_anthropic(STALL)
    assert all(m["content"] for m in out)
    assert [m["role"] for m in out] == ["user", "user"]
