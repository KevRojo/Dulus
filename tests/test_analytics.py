"""Exercise the public CLI's telemetry without contacting analytics providers."""

import base64
import io
import json
import threading
import urllib.request
from urllib.parse import parse_qs, urlsplit

import pytest

import analytics


@pytest.fixture
def sent(monkeypatch):
    requests = []

    def capture(request, *, timeout):
        requests.append(request)
        return io.BytesIO(b"1")

    monkeypatch.setattr(urllib.request, "urlopen", capture)
    monkeypatch.setattr(threading.Thread, "start", threading.Thread.run)
    monkeypatch.delenv("DULUS_TELEMETRY", raising=False)
    monkeypatch.setattr(analytics, "MP_TOKEN", "mixpanel-test")
    monkeypatch.setattr(analytics, "AMP_KEY", "amplitude-test")
    monkeypatch.setattr(analytics, "_enabled", False)
    monkeypatch.setattr(analytics, "_distinct_id", None)
    monkeypatch.setattr(analytics, "_dulus_version", "")
    return requests


@pytest.mark.parametrize("choice", [False, None, "off", "false", "0", "disabled", "unknown"])
def test_only_explicit_consent_sends(choice, sent) -> None:
    config = {"telemetry": choice}
    analytics.init_telemetry(config)
    analytics.track_session_start(config)
    assert not analytics.is_enabled()
    assert "telemetry_id" not in config
    assert not sent


@pytest.mark.parametrize(
    "mixpanel,amplitude", [(True, True), (True, False), (False, True), (False, False)]
)
def test_each_configured_provider_receives_event(mixpanel, amplitude, sent, monkeypatch) -> None:
    if not mixpanel:
        monkeypatch.setattr(analytics, "MP_TOKEN", "")
    if not amplitude:
        monkeypatch.setattr(analytics, "AMP_KEY", "")
    config = {"telemetry": " ON ", "model": "test-model", "telemetry_id": "test-device"}
    analytics.init_telemetry(config)
    analytics.track_session_start(config)

    assert analytics.is_enabled() == (mixpanel or amplitude)
    requests = {urlsplit(request.full_url).hostname: request for request in sent}
    assert len(sent) == int(mixpanel) + int(amplitude)
    if mixpanel:
        form = parse_qs(requests["api.mixpanel.com"].data.decode())
        event, = json.loads(base64.b64decode(form["data"][0]))
        assert event["event"] == "session_start"
        assert event["properties"]["distinct_id"] == "test-device"
        assert event["properties"]["model"] == "test-model"
    if amplitude:
        body = json.loads(requests["api2.amplitude.com"].data)
        event, = body["events"]
        assert event["event_type"] == "session_start"
        assert event["device_id"] == "test-device"
        assert event["event_properties"]["model"] == "test-model"


def test_environment_opt_out_overrides_saved_consent(monkeypatch, sent) -> None:
    config = {"telemetry": True}
    analytics.init_telemetry(config)
    monkeypatch.setenv("DULUS_TELEMETRY", "0")
    analytics.track_session_start(config)
    assert not sent


@pytest.mark.parametrize(
    "next_config", [{"telemetry": False}, {"telemetry": True, "telemetry_id": "other-device"}]
)
def test_workers_recheck_consent_and_identity(next_config, monkeypatch, sent) -> None:
    pending = []
    monkeypatch.setattr(threading.Thread, "start", lambda worker: pending.append(worker))
    analytics.init_telemetry({"telemetry": True, "telemetry_id": "first-device"})
    analytics.track_message_sent("test-model")
    assert len(pending) == 2
    analytics.init_telemetry(next_config)
    for worker in pending:
        worker.run()
    assert not sent


def test_empty_saved_id_is_replaced_once(sent) -> None:
    config = {"telemetry": True, "telemetry_id": ""}
    analytics.init_telemetry(config)
    distinct_id = config["telemetry_id"]
    assert distinct_id
    analytics.init_telemetry(config)
    assert config["telemetry_id"] == distinct_id


def test_consent_prompt_names_both_destinations(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert analytics.ask_consent({}) == {"telemetry": False}
    notice = capsys.readouterr().out
    assert "Mixpanel" in notice and "Amplitude" in notice
