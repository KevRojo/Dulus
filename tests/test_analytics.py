"""Exercise the public CLI's telemetry without contacting analytics providers."""

import base64
import io
import json
import runpy
import sys
import threading
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import pytest

import analytics
import config as cfgmod


@pytest.fixture(autouse=True)
def isolate_client(monkeypatch, tmp_path):
    monkeypatch.setattr(cfgmod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(analytics, "_distinct_id", None)
    monkeypatch.setattr(analytics, "_dulus_version", "")


@pytest.fixture
def sent(monkeypatch):
    requests = []

    def capture(request, *, timeout):
        requests.append(request)
        return io.BytesIO(b"1")

    monkeypatch.setattr(urllib.request, "urlopen", capture)
    monkeypatch.setattr(threading.Thread, "start", threading.Thread.run)
    monkeypatch.setattr(analytics, "MP_TOKEN", "mixpanel-test")
    monkeypatch.setattr(analytics, "AMP_KEY", "amplitude-test")
    return requests


@pytest.mark.parametrize("settings", [{}, {"telemetry": False}, {"telemetry": "off"}])
def test_every_session_sends_with_legacy_opt_outs(settings, monkeypatch, sent) -> None:
    monkeypatch.setenv("DULUS_TELEMETRY", "0")
    analytics.init_telemetry(settings)
    analytics.track_session_start(settings)
    assert analytics.is_enabled()
    assert uuid.UUID(settings["telemetry_id"]).version == 4
    assert {urlsplit(req.full_url).hostname for req in sent} == {
        "api.mixpanel.com", "api2.amplitude.com",
    }


@pytest.mark.parametrize("interactive", [True, False])
def test_cli_startup_sends_without_a_consent_prompt(interactive, sent, monkeypatch, capsys) -> None:
    import dulus
    import welcome

    settings = {"model": "ollama/test-model"}
    if not interactive:
        settings["telemetry"] = False
    monkeypatch.setenv("DULUS_TELEMETRY", "0")
    monkeypatch.setenv("DULUS_NO_IPC", "1")
    monkeypatch.setattr(sys, "argv", ["dulus"] if interactive else ["dulus", "-p", "test"])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: interactive)
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("unexpected prompt"))
    monkeypatch.setattr(welcome, "is_first_run", lambda: False)
    monkeypatch.setattr(cfgmod, "load_config", lambda: settings)
    monkeypatch.setattr(cfgmod, "has_api_key", lambda config: True)
    monkeypatch.setattr(dulus, "_require_dulus_login", lambda args: None)
    monkeypatch.setattr(dulus, "repl", lambda *args, **kwargs: None)
    dulus.main()
    assert len(sent) == 2
    assert ("usage analytics are always on" in capsys.readouterr().err) == interactive


@pytest.mark.parametrize(
    "mixpanel,amplitude", [(True, True), (True, False), (False, True), (False, False)]
)
def test_each_configured_provider_receives_event(mixpanel, amplitude, sent, monkeypatch) -> None:
    if not mixpanel:
        monkeypatch.setattr(analytics, "MP_TOKEN", "")
    if not amplitude:
        monkeypatch.setattr(analytics, "AMP_KEY", "")
    saved_id = uuid.uuid4().hex
    config = {
        "model": "test-model", "provider": "test-provider", "telemetry_id": saved_id,
        "user_name": "private-name", "openai_api_key": "private-key", "prompt": "private-prompt",
    }
    analytics.init_telemetry(config)
    analytics.track_session_start(config)

    assert analytics.is_enabled() == (mixpanel or amplitude)
    requests = {urlsplit(request.full_url).hostname: request for request in sent}
    assert len(sent) == int(mixpanel) + int(amplitude)
    if mixpanel:
        form = parse_qs(requests["api.mixpanel.com"].data.decode())
        event, = json.loads(base64.b64decode(form["data"][0]))
        assert event["event"] == "session_start"
        assert event["properties"]["distinct_id"] == saved_id
        assert event["properties"]["model"] == "test-model"
        assert "private-" not in json.dumps(event)
        assert parse_qs(urlsplit(requests["api.mixpanel.com"].full_url).query)["ip"] == ["0"]
    if amplitude:
        body = json.loads(requests["api2.amplitude.com"].data)
        event, = body["events"]
        assert event["event_type"] == "session_start"
        assert event["device_id"] == saved_id
        assert event["event_properties"]["model"] == "test-model"
        assert "private-" not in json.dumps(event)


def test_empty_provider_overrides_use_public_projects(monkeypatch, sent) -> None:
    monkeypatch.setenv("DULUS_MP_TOKEN", "")
    monkeypatch.setenv("DULUS_AMP_KEY", "")
    client = runpy.run_path(analytics.__file__)
    client["init_telemetry"]({})
    client["track_message_sent"]("test-model")
    assert {urlsplit(req.full_url).hostname for req in sent} == {
        "api.mixpanel.com", "api2.amplitude.com",
    }


def test_workers_recheck_identity(monkeypatch, sent) -> None:
    pending = []
    monkeypatch.setattr(threading.Thread, "start", lambda worker: pending.append(worker))
    analytics.init_telemetry({"telemetry_id": uuid.uuid4().hex})
    analytics.track_message_sent("test-model")
    assert len(pending) == 2
    analytics.init_telemetry({"telemetry_id": uuid.uuid4().hex})
    for worker in pending:
        worker.run()
    assert not sent


def test_concurrent_fresh_launches_share_an_id_without_completing_setup(tmp_path) -> None:
    def start(_):
        config = {"telemetry_id": ""}
        analytics.init_telemetry(config)
        return config["telemetry_id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(start, range(16)))
    assert len(set(ids)) == 1
    assert uuid.UUID(ids[0]).version == 4
    assert (tmp_path / "cli-analytics" / "id").read_text(encoding="ascii") == ids[0]
    assert not (tmp_path / "config.json").exists()


def test_invalid_legacy_id_is_replaced_with_a_random_id(sent) -> None:
    config = {"telemetry_id": "person@example.test"}
    analytics.init_telemetry(config)
    analytics.track_session_start(config)
    assert uuid.UUID(config["telemetry_id"]).version == 4
    assert len(sent) == 2


def test_config_reports_effective_status_without_saving_a_preference(monkeypatch, capsys) -> None:
    import dulus

    def unexpected_save(settings):
        pytest.fail("a read-only telemetry setting must not save the config")

    monkeypatch.setattr(cfgmod, "save_config", unexpected_save)
    config = {"telemetry": False}
    for args in ("telemetry", "telemetry=off", "telemetry=on"):
        assert dulus.cmd_config(args, None, config)
        assert "always on" in capsys.readouterr().out
    assert dulus.cmd_config("", None, config)
    assert json.loads(capsys.readouterr().out)["telemetry"] is True


def test_offline_providers_do_not_interrupt_the_cli(monkeypatch, sent) -> None:
    def offline(request, *, timeout):
        sent.append(request)
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    analytics.init_telemetry({})
    analytics.track_tool_used("Read")
    assert len(sent) == 2
