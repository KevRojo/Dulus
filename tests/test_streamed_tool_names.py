"""A streamed tool call keeps the name the model gave it.

OpenAI sends a tool call's name once, on its first delta. Plenty of
OpenAI-compatible servers resend the full name on every delta instead, and
three stream loops appended each copy: the model called ``Bash`` and Dulus
looked up ``BashBashBash`` — "tool not found", and a wasted turn. These drive
the real loops behind providers.stream() with every shape a server sends the
name in.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import providers
from providers import AssistantTurn

openai = pytest.importorskip("openai")
requests = pytest.importorskip("requests")

MSGS = [{"role": "user", "content": "list the files"}]

# One (index, id, name, arguments) tuple per streamed delta.
RESENT = [  # the full name on every delta — the bug
    (0, "call_1", "Bash", '{"command":'),
    (0, None, "Bash", ' "ls -la"'),
    (0, None, "Bash", "}"),
]
ONCE = [  # OpenAI: the name on the first delta only
    (0, "call_1", "Bash", ""),
    (0, None, None, '{"command": "ls -la"}'),
]
SPLIT = [  # the name itself streamed in fragments
    (0, "call_1", "Ba", ""),
    (0, None, "sh", '{"command": "ls -la"}'),
]
PARALLEL = [  # two calls in one turn, each resending its own name
    (0, "call_1", "Read", '{"file_path": "a.py"}'),
    (1, "call_2", "Bash", '{"command":'),
    (0, None, "Read", ""),
    (1, None, "Bash", ' "ls -la"}'),
]
BASH = [("Bash", {"command": "ls -la"})]


def _openai_compat(deltas: list, monkeypatch) -> tuple[str, dict]:
    def _chunk(idx, tc_id, name, args):
        tc = SimpleNamespace(index=idx, id=tc_id,
                             function=SimpleNamespace(name=name, arguments=args))
        delta = SimpleNamespace(content=None, tool_calls=[tc])
        return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)

    chunks = [_chunk(*d) for d in deltas]

    class _Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kw: iter(chunks)))

    monkeypatch.setattr(openai, "OpenAI", _Client)
    return "openai/gpt-4o", {"openai_api_key": "k"}


def _sse(deltas: list) -> list:
    lines = []
    for idx, tc_id, name, args in deltas:
        fn = {k: v for k, v in (("name", name), ("arguments", args)) if v is not None}
        tc = {"index": idx, "function": fn, **({"id": tc_id} if tc_id else {})}
        payload = {"choices": [{"delta": {"tool_calls": [tc]}}]}
        lines.append(f"data: {json.dumps(payload)}\n".encode())
    return lines + [b"data: [DONE]\n"]


def _kimi(deltas: list, monkeypatch) -> tuple[str, dict]:
    monkeypatch.setattr(providers.urllib.request, "urlopen",
                        lambda *a, **k: iter(_sse(deltas)))
    return "kimi/kimi-k2.5", {}


def _grok(deltas: list, monkeypatch) -> tuple[str, dict]:
    class _Resp:
        status_code = 200

        def iter_lines(self):
            return iter(_sse(deltas))

    monkeypatch.setattr(providers, "_xai_oauth_get_token", lambda config: "tok")
    monkeypatch.setattr(requests, "Session",
                        lambda: SimpleNamespace(post=lambda *a, **k: _Resp()))
    return "grok-4", {}


ADAPTERS = pytest.mark.parametrize(
    "adapter", [_openai_compat, _kimi, _grok], ids=["openai-compat", "kimi", "grok"])


def _calls(adapter, deltas: list, monkeypatch) -> list:
    model, config = adapter(deltas, monkeypatch)
    events = list(providers.stream(model=model, system="s", messages=MSGS,
                                   tool_schemas=[], config=config))
    last = events[-1]
    assert isinstance(last, AssistantTurn) and last.error is False
    return [(c["name"], c["input"]) for c in last.tool_calls]


@ADAPTERS
def test_a_name_resent_on_every_delta_is_not_repeated(adapter, monkeypatch) -> None:
    assert _calls(adapter, RESENT, monkeypatch) == BASH


@ADAPTERS
def test_a_name_sent_once_is_kept(adapter, monkeypatch) -> None:
    assert _calls(adapter, ONCE, monkeypatch) == BASH


@ADAPTERS
def test_a_name_streamed_in_fragments_is_joined(adapter, monkeypatch) -> None:
    assert _calls(adapter, SPLIT, monkeypatch) == BASH


@ADAPTERS
def test_parallel_calls_each_keep_their_own_name(adapter, monkeypatch) -> None:
    assert _calls(adapter, PARALLEL, monkeypatch) == [
        ("Read", {"file_path": "a.py"}),
        ("Bash", {"command": "ls -la"}),
    ]
