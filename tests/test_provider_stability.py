"""Every provider turn must end in an AssistantTurn, never a raw exception.

The REPL, webchat, the daemon, sub-agents and compaction all consume
providers.stream() and only handle API errors. A dropped connection, a chunk
without a delta or a missing endpoint used to escape as a raw httpx/OSError/
ValueError and kill the turn — or, for Anthropic, end it as a "success" that
saved a cut-off reply as the final answer.
"""
from __future__ import annotations

import io
import unittest.mock as mock
from types import SimpleNamespace

import pytest

import providers
from providers import AssistantTurn, TextChunk

httpx = pytest.importorskip("httpx")
openai = pytest.importorskip("openai")
anthropic = pytest.importorskip("anthropic")

MSGS = [{"role": "user", "content": "hi"}]


def _run(model: str, config: dict | None = None) -> list:
    return list(providers.stream(model=model, system="s", messages=MSGS,
                                 tool_schemas=[], config=config or {}))


def _text(events: list) -> str:
    return "".join(e.text for e in events if isinstance(e, TextChunk))


def _chunk(content: str):
    delta = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=None)


def _fake_openai(script: list):
    """An OpenAI client whose stream replays `script`, raising any exception in it."""
    def _replay():
        for item in script:
            if isinstance(item, BaseException):
                raise item
            yield item

    class _Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kw: _replay()))
    return _Client


# ── OpenAI-compatible adapters ────────────────────────────────────────────────


def test_connection_drop_mid_reply_ends_the_turn_with_an_error() -> None:
    drop = httpx.RemoteProtocolError("peer closed connection without sending complete message body")
    with mock.patch.object(openai, "OpenAI", _fake_openai([_chunk("The answer is"), drop])):
        events = _run("openai/gpt-4o", {"openai_api_key": "k"})

    last = events[-1]
    assert isinstance(last, AssistantTurn) and last.error is True
    assert "The answer is" in _text(events)


def test_read_timeout_before_any_output_is_a_network_error() -> None:
    timeout = httpx.ReadTimeout("The read operation timed out")
    with mock.patch.object(openai, "OpenAI", _fake_openai([timeout])):
        events = _run("openai/gpt-4o", {"openai_api_key": "k"})

    last = events[-1]
    assert isinstance(last, AssistantTurn) and last.error is True
    assert "network" in last.text.lower()


def test_chunk_without_a_delta_is_skipped() -> None:
    filtered = SimpleNamespace(choices=[SimpleNamespace(delta=None)], usage=None)
    with mock.patch.object(openai, "OpenAI", _fake_openai([filtered, _chunk("ok")])):
        events = _run("openai/gpt-4o", {"openai_api_key": "k"})

    last = events[-1]
    assert isinstance(last, AssistantTurn) and last.error is False
    assert last.text == "ok"


# ── stream(): the last line of defence ───────────────────────────────────────


def test_transport_error_escaping_an_adapter_becomes_an_error_turn(monkeypatch) -> None:
    def reset(*args, **kwargs):
        yield TextChunk("partial")
        raise ConnectionResetError(104, "Connection reset by peer")

    monkeypatch.setattr(providers, "stream_ollama", reset)
    events = _run("ollama/llama3")

    last = events[-1]
    assert isinstance(last, AssistantTurn) and last.error is True


@pytest.mark.parametrize("model, env", [
    ("azure/gpt-4o", "AZURE_OPENAI_ENDPOINT"),
    ("amd/Qwen2.5-72B-Instruct", "AMD_BASE_URL"),
    ("custom/my-model", "CUSTOM_BASE_URL"),
])
def test_missing_endpoint_is_an_error_turn_not_a_crash(monkeypatch, model, env) -> None:
    monkeypatch.delenv(env, raising=False)
    events = _run(model)
    last = events[-1]
    assert isinstance(last, AssistantTurn) and last.error is True
    assert env in last.text


def test_custom_models_go_to_the_configured_server(monkeypatch) -> None:
    seen: list = []

    def capture(api_key, base_url, model, *args, **kwargs):
        seen.append((base_url, model))
        yield AssistantTurn("ok", [], 0, 0)

    monkeypatch.setattr(providers, "stream_openai_compat", capture)
    _run("custom/my-model", {"custom_base_url": "http://gpu-box:8000/v1"})

    assert providers.detect_provider("custom/my-model") == "custom"
    assert seen == [("http://gpu-box:8000/v1", "my-model")]


# ── Anthropic ────────────────────────────────────────────────────────────────


def test_anthropic_drop_mid_reply_is_not_saved_as_the_answer() -> None:
    class _Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __iter__(self):
            delta = SimpleNamespace(type="text_delta", text="The answer is")
            yield SimpleNamespace(type="content_block_delta", delta=delta)
            raise httpx.ReadError("connection reset")

    class _Client:
        def __init__(self, **kwargs):
            self.messages = SimpleNamespace(stream=lambda **kw: _Stream())

    with mock.patch.object(anthropic, "Anthropic", _Client):
        events = _run("anthropic/claude-sonnet-4-6", {"anthropic_api_key": "k"})

    last = events[-1]
    assert isinstance(last, AssistantTurn)
    assert last.error is True, "a cut-off reply was recorded as a finished answer"


# ── Ollama ───────────────────────────────────────────────────────────────────


def test_ollama_error_line_is_reported(monkeypatch) -> None:
    body = (b'{"message": {"content": "Hi"}}\n'
            b'{"error": "model runner has unexpectedly stopped"}\n')

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()
            return False

    monkeypatch.setattr(providers.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    events = _run("ollama/llama3")

    last = events[-1]
    assert isinstance(last, AssistantTurn) and last.error is True
    assert "runner has unexpectedly stopped" in last.text
