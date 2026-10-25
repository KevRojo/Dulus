"""Tool-call arguments that are not a JSON object must not crash the agent loop.

Open-weight models send "arguments": "null", double-encode the JSON or send
a list. Providers passed that straight through, and the permission gate and
the REPL's tool renderer call .get() on it.
"""
from __future__ import annotations

import pytest

import agent
from agent import AgentState, PermissionRequest, ToolEnd, _coerce_tool_input
from providers import AssistantTurn


@pytest.mark.parametrize("raw, expected", [
    ({"a": 1}, {"a": 1}),
    (None, {}),
    ('{"command": "ls"}', {"command": "ls"}),        # double-encoded
    ("not json", {"_raw": "not json"}),
    ('"a json string"', {"_raw": '"a json string"'}),
    ([1, 2], {"_raw": [1, 2]}),
])
def test_coerce_tool_input(raw, expected) -> None:
    assert _coerce_tool_input(raw) == expected


def test_agent_loop_survives_a_null_tool_input(monkeypatch) -> None:
    turns = iter([
        AssistantTurn("", [{"id": "c1", "name": "Bash", "input": None}], 1, 1),
        AssistantTurn("done", [], 1, 1),
    ])

    def scripted(**kwargs):
        yield next(turns)

    monkeypatch.setattr(agent, "stream", scripted)
    monkeypatch.setattr(agent, "maybe_compact", lambda state, config: False)
    state = AgentState()
    config = {"model": "openai/gpt-4o", "permission_mode": "auto"}

    events = []
    for ev in agent.run("go", state, config, "system"):
        if isinstance(ev, PermissionRequest):
            ev.granted = False
        events.append(ev)

    ends = [e for e in events if isinstance(e, ToolEnd)]
    assert ends and ends[0].result.startswith("Denied")
    assert state.messages[-1]["content"] == "done"
    assert state.messages[-3]["tool_calls"][0]["input"] == {}   # replayable history
