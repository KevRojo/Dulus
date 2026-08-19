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


def test_capacity_pushback_is_retryable():
    # These clear up on their own — the next request usually succeeds, which is
    # exactly the case worth absorbing instead of showing the user an error.
    for message in (
        'Error code: 529 - {"type":"overloaded_error"}',
        "The model is overloaded. Please try again.",
        "Service temporarily at capacity",
        "server is busy, retry later",
        "Model is currently loading",
    ):
        assert _ProviderRetry.is_retryable(Exception(message)), message


def test_credential_and_client_errors_are_never_retried():
    # Retrying these hammers the endpoint for an error that will never resolve.
    for message in (
        "401 invalid_authentication_error",
        "400 invalid_request_error: bad tool schema",
        "404 model_not_found",
    ):
        assert not _ProviderRetry.is_retryable(Exception(message)), message


def test_overloaded_stream_recovers_and_shows_why_it_waited(monkeypatch):
    # End to end: a 529 on the first attempts must not reach the transcript as
    # output text, but the backoff must be VISIBLE — a silent retry reads as a
    # frozen app, so each wait emits a transient StatusChunk instead.
    attempts = 0

    def overloaded_then_fine():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception('Error code: 529 - {"type":"overloaded_error"}')
        yield "the real answer"

    monkeypatch.setattr(providers.time, "sleep", lambda _seconds: None)
    out = list(_ProviderRetry.wrap_generator(overloaded_then_fine))

    statuses = [c for c in out if isinstance(c, providers.StatusChunk)]
    output = [c for c in out if not isinstance(c, providers.StatusChunk)]
    assert output == ["the real answer"]
    assert attempts == 3
    # One status per retry — none before the final (successful) attempt.
    assert len(statuses) == 2
    assert all("overloaded" in c.text for c in statuses)


def test_retry_status_never_enables_a_partial_stream_replay(monkeypatch):
    # StatusChunk comes from the wrapper, not the provider stream, so it must
    # NOT flip the emitted guard: once real output has streamed, a failure
    # still propagates instead of replaying the request (duplicate text).
    attempts = 0

    def fail_then_partial():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Exception('Error code: 529 - {"type":"overloaded_error"}')
        yield "partial answer"
        raise Exception('Error code: 529 - {"type":"overloaded_error"}')

    monkeypatch.setattr(providers.time, "sleep", lambda _seconds: None)
    out = []
    with pytest.raises(Exception, match="529"):
        for chunk in _ProviderRetry.wrap_generator(fail_then_partial):
            out.append(chunk)

    assert "partial answer" in out  # streamed once, never replayed
    assert attempts == 2  # no third attempt after partial output


def test_stream_handlers_reraise_transient_failures_for_the_retry_wrapper():
    # stream_anthropic and stream_openai_compat used to convert every exception
    # into an error TextChunk. That returns a well-behaved generator, so
    # _ProviderRetry never saw a failure and the retry silently did nothing.
    import inspect

    for fn in (providers.stream_anthropic, providers.stream_openai_compat):
        source = inspect.getsource(fn)
        assert "_ProviderRetry.is_retryable" in source, fn.__name__


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
