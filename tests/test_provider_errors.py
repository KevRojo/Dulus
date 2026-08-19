"""Regression tests for issue #18: unhandled ResourceExhausted crash.

When the NVIDIA free-tier quota is exhausted, the OpenAI-compatible client
raises ``openai.APIError: ResourceExhausted ...`` on the first *read* of the
SSE stream — after ``create()`` already returned. The stream adapter must
convert that into a friendly error turn instead of killing the REPL.
"""
import sys
import unittest.mock as mock
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import providers
from providers import friendly_api_error, _ProviderRetry, AssistantTurn

openai = pytest.importorskip("openai")

QUOTA_MSG = "ResourceExhausted: Worker local total request limit reached (606/48)"


class _QuotaStream:
    """Stream whose first read raises, like the real SSE client does."""
    def __iter__(self):
        return self

    def __next__(self):
        raise openai.APIError(QUOTA_MSG, request=None, body=None)


class _FakeClient:
    def __init__(self, **kwargs):
        pass

    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                return _QuotaStream()


def test_quota_error_is_not_retryable():
    exc = Exception(QUOTA_MSG)
    assert _ProviderRetry.is_retryable(exc) is False


def test_friendly_message_mentions_quota():
    msg = friendly_api_error(Exception(QUOTA_MSG))
    assert "quota" in msg.lower()
    assert "/model" in msg


def test_mid_stream_quota_error_yields_error_turn():
    with mock.patch.object(openai, "OpenAI", _FakeClient):
        events = list(providers.stream_openai_compat(
            "key", "https://example.com/v1", "gpt-x",
            "sys", [{"role": "user", "content": "hi"}], [], {},
        ))
    assert events, "adapter must yield something, not raise"
    last = events[-1]
    assert isinstance(last, AssistantTurn)
    assert last.error is True
    assert "quota" in last.text.lower()


def test_nvidia_mid_stream_quota_falls_back_to_error_turn():
    # Empty fallback chain -> no model to switch to -> friendly error turn.
    with mock.patch.object(openai, "OpenAI", _FakeClient), \
         mock.patch.object(providers, "_get_nvidia_fallback_chain", lambda cfg: []):
        events = list(providers.stream_openai_compat(
            "key", "https://integrate.api.nvidia.com/v1",
            "nvidia-web/deepseek-ai/deepseek-v4-flash",
            "sys", [{"role": "user", "content": "hi"}], [], {},
        ))
    last = events[-1]
    assert isinstance(last, AssistantTurn)
    assert last.error is True


def test_stream_entry_point_survives_quota_error():
    # Through stream() + _ProviderRetry: must not retry forever nor raise.
    with mock.patch.object(openai, "OpenAI", _FakeClient):
        events = list(providers.stream(
            model="openai/gpt-4o", system="s",
            messages=[{"role": "user", "content": "hi"}],
            tool_schemas=[], config={"openai_api_key": "k"},
        ))
    last = events[-1]
    assert isinstance(last, AssistantTurn)
    assert last.error is True
