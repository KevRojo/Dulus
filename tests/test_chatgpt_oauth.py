"""ChatGPT / Codex OAuth provider — routing, translation, session helpers."""
from __future__ import annotations

import base64
import json
import time

import providers


def test_detect_provider_routes_chatgpt_models():
    assert providers.detect_provider("chatgpt/gpt-5.4") == "chatgpt-oauth"
    assert providers.detect_provider("chatgpt/gpt-5.5") == "chatgpt-oauth"
    assert providers.detect_provider("codex/gpt-5.1-codex") == "chatgpt-oauth"
    assert providers.detect_provider("gpt-5.5") == "chatgpt-oauth"
    assert providers.detect_provider("gpt-5.4-mini") == "chatgpt-oauth"
    assert providers.detect_provider("gpt-5.1-codex") == "chatgpt-oauth"
    assert providers.detect_provider("gpt-5.1-codex-mini") == "chatgpt-oauth"
    assert providers.detect_provider("codex-mini-latest") == "chatgpt-oauth"
    # API-key path must stay on openai
    assert providers.detect_provider("gpt-4o") == "openai"
    assert providers.detect_provider("gpt-4.1") == "openai"
    assert providers.detect_provider("o3-mini") == "openai"


def test_stream_dispatches_to_chatgpt_oauth(monkeypatch):
    seen = []

    def fake(model, system, messages, tool_schemas, config):
        seen.append(model)
        yield providers.TextChunk("ok")
        yield providers.AssistantTurn("ok", [], 0, 0)

    monkeypatch.setattr(providers, "stream_chatgpt_oauth", fake)
    list(providers.stream("chatgpt/gpt-5.4", "s", [{"role": "user", "content": "hi"}], [], {}))
    list(providers.stream("gpt-5.4", "s", [{"role": "user", "content": "hi"}], [], {}))
    assert seen == ["gpt-5.4", "gpt-5.4"]


def test_messages_to_responses_input_shape():
    instructions, items = providers._chatgpt_messages_to_responses_input(
        "You are helpful",
        [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "calling",
                "tool_calls": [{"id": "c1", "name": "Bash", "input": {"command": "ls"}}],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
        ],
    )
    assert "You are helpful" in instructions
    types = [i.get("type") for i in items]
    assert types == ["message", "message", "function_call", "function_call_output"]
    assert items[2]["call_id"] == "c1"
    assert items[2]["name"] == "Bash"
    assert items[3]["output"] == "ok"


def test_tools_to_responses_shape():
    tools = providers._chatgpt_tools_to_responses(
        [{
            "name": "Bash",
            "description": "run a command",
            "input_schema": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
            },
        }]
    )
    assert tools == [{
        "type": "function",
        "name": "Bash",
        "description": "run a command",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
        },
    }]


def test_reasoning_suffix_parser():
    assert providers._chatgpt_parse_reasoning_suffix("chatgpt/gpt-5.4-high") == ("gpt-5.4", "high")
    assert providers._chatgpt_parse_reasoning_suffix("gpt-5.5-xhigh") == ("gpt-5.5", "xhigh")
    assert providers._chatgpt_parse_reasoning_suffix("gpt-5.4") == ("gpt-5.4", None)


def test_extract_account_id_from_jwt():
    def _jwt(payload: dict) -> str:
        head = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        return f"{head}.{body}.sig"

    tok = _jwt({
        "https://api.openai.com/auth": {"chatgpt_account_id": "acc-123"},
        "exp": int(time.time()) + 3600,
    })
    assert providers._chatgpt_extract_account_id(id_token=tok) == "acc-123"
    assert providers._chatgpt_extract_account_id(access_token=tok) == "acc-123"


def test_stream_without_session_errors_cleanly(monkeypatch):
    monkeypatch.setattr(providers, "_chatgpt_oauth_get_session", lambda cfg=None: {})
    chunks = list(
        providers.stream_chatgpt_oauth(
            "gpt-5.4", "sys", [{"role": "user", "content": "x"}], [], {}
        )
    )
    assert any(isinstance(c, providers.TextChunk) for c in chunks)
    turn = next(c for c in chunks if isinstance(c, providers.AssistantTurn))
    assert turn.error is True
    assert "login chatgpt" in turn.text.lower() or "oauth" in turn.text.lower()


def test_provider_registry_entry():
    assert "chatgpt-oauth" in providers.PROVIDERS
    entry = providers.PROVIDERS["chatgpt-oauth"]
    assert entry["type"] == "chatgpt-oauth"
    assert entry.get("api_key_env") is None
    assert "chatgpt.com/backend-api/codex" in entry.get("base_url", "")
