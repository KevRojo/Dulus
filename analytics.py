"""Always-on usage analytics for the public Dulus CLI.

The CLI sends session, message, tool, command, and model-selection events
to Mixpanel and Amplitude. Events contain a locally generated random ID,
Dulus and Python versions, the OS, and the relevant provider, model, tool,
or command name. Prompts, replies, tool arguments, and file contents are
excluded. Delivery runs in background threads and can fail offline.
"""
from __future__ import annotations

import base64
import json
import os
import platform
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

# Mixpanel PROJECT TOKEN for the public Dulus project.
# NOTE: Mixpanel ingestion tokens are write-only and designed to ship in
# client code (every website using Mixpanel exposes theirs). It cannot be
# used to read any data. Override with DULUS_MP_TOKEN.
_DEFAULT_MP_TOKEN = "966ce8f5ccb32f06788f51be9f8bf8f5"
MP_TOKEN = os.environ.get("DULUS_MP_TOKEN", _DEFAULT_MP_TOKEN).strip()

_MP_ENDPOINT = "https://api.mixpanel.com/track?ip=0"

# Amplitude receives the same usage events and random ID.
# Ingestion keys are write-only by design — they cannot read any data.
_DEFAULT_AMP_KEY = "dbdb0e42b0fc29bfdb4061612c3c8a7e"
AMP_KEY = os.environ.get("DULUS_AMP_KEY", _DEFAULT_AMP_KEY).strip()

# Allow routing to either provider alone. Empty overrides for both use the public projects.
if not (MP_TOKEN or AMP_KEY):
    MP_TOKEN, AMP_KEY = _DEFAULT_MP_TOKEN, _DEFAULT_AMP_KEY

_AMP_ENDPOINT = "https://api2.amplitude.com/2/httpapi"

# Populated by init_telemetry() at CLI startup.
_distinct_id: str | None = None
_dulus_version: str = ""


def is_enabled() -> bool:
    """Return whether the client is initialized and has a delivery destination."""
    return bool(_distinct_id and (MP_TOKEN or AMP_KEY))


def _anonymous_id(value: object) -> str | None:
    """Accept the random UUID format used by existing Dulus installations."""
    if isinstance(value, str):
        try:
            if uuid.UUID(value).version == 4:
                return value
        except ValueError:
            pass
    return None


def _installation_id() -> str:
    """Share one random ID across launches without creating the wizard's config.json."""
    from config import CONFIG_DIR, atomic_write_text

    path = CONFIG_DIR / "cli-analytics" / "id"
    new_id = uuid.uuid4().hex
    try:
        if not path.is_file():
            # A rename cannot replace another launch's nonempty directory on POSIX or Windows.
            with tempfile.TemporaryDirectory(dir=CONFIG_DIR) as staging:
                candidate = Path(staging) / "ready"
                candidate.mkdir(mode=0o700)
                (candidate / "id").write_text(new_id, encoding="ascii")
                try:
                    candidate.rename(path.parent)
                except OSError:
                    if not path.is_file():
                        raise
        stored = _anonymous_id(path.read_text(encoding="utf-8", errors="replace").strip())
        if stored:
            return stored
        atomic_write_text(path, new_id)
    except OSError:
        pass  # A read-only config directory can still use an ID for this session.
    return new_id


def init_telemetry(config: dict, version: str = "") -> None:
    """Initialize analytics for a CLI session, reusing its existing anonymous ID."""
    global _distinct_id, _dulus_version
    _dulus_version = version or _dulus_version
    distinct_id = _anonymous_id(config.get("telemetry_id")) or _installation_id()
    config["telemetry_id"] = distinct_id
    _distinct_id = distinct_id


def track(event: str, properties: dict | None = None) -> None:
    """Dispatch a usage event to each configured provider in the background."""
    distinct_id = _distinct_id
    if not is_enabled() or not distinct_id:
        return
    os_name = platform.system()
    event_properties = {
        "dulus_version": _dulus_version,
        "os": os_name,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        **(properties or {}),
    }
    payload = {
        "event": event,
        "properties": {
            "token": MP_TOKEN,
            "distinct_id": distinct_id,
            "time": int(time.time()),
            "$ip": 0,  # disable Mixpanel geolocation
            **event_properties,
        },
    }

    def _post(endpoint: str, data: bytes, content_type: str) -> None:
        from urllib.request import Request, urlopen

        # The active profile may change while the worker is waiting.
        if _distinct_id != distinct_id:
            return
        req = Request(endpoint, data=data, headers={"Content-Type": content_type}, method="POST")
        with urlopen(req, timeout=4) as response:
            response.read()

    def _send_mixpanel() -> None:
        try:
            from urllib.parse import urlencode

            data = urlencode(
                {"data": base64.b64encode(json.dumps([payload]).encode()).decode()}
            ).encode()
            _post(_MP_ENDPOINT, data, "application/x-www-form-urlencoded")
        except Exception:
            pass  # telemetry must never break Dulus

    def _send_amplitude() -> None:
        try:
            body = json.dumps({
                "api_key": AMP_KEY,
                "events": [{
                    "device_id": distinct_id,
                    "event_type": event,
                    "event_properties": event_properties,
                    "platform": os_name,
                }],
            }).encode()
            _post(_AMP_ENDPOINT, body, "application/json")
        except Exception:
            pass  # telemetry must never break Dulus

    if MP_TOKEN:
        threading.Thread(target=_send_mixpanel, daemon=True, name="telemetry").start()
    if AMP_KEY:
        threading.Thread(target=_send_amplitude, daemon=True, name="telemetry-amp").start()


def track_session_start(config: dict) -> None:
    """Convenience: one event per REPL boot (enough for DAU/MAU counts)."""
    track("session_start", {
        "provider": str(config.get("provider", "")),
        "model": str(config.get("model", "")),
    })


def track_message_sent(model: str = "") -> None:
    """One event per user prompt sent to the LLM (no content — count only)."""
    track("message_sent", {"model": model})


def track_tool_used(tool_name: str) -> None:
    """One event per tool invocation (tool NAME only — never inputs)."""
    track("tool_used", {"tool": tool_name})


def track_command_used(command: str) -> None:
    """One event per slash command (command NAME only — never args)."""
    track("command_used", {"command": command})


def track_model_selected(model: str, provider: str = "") -> None:
    """Fired when the user switches models via /model."""
    track("model_selected", {"model": model, "provider": provider})
