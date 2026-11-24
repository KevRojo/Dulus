"""Dulus anonymous usage telemetry (opt-in, privacy-first).

Dulus asks ONCE on startup whether you want to share anonymous usage
statistics. Nothing is sent until you explicitly say yes.

What IS collected (when enabled):
  - Event names (session_start, message_sent, tool_used, command_used, model_selected)
  - Dulus version, OS name, Python version
  - Provider, model, tool, and command names
  - A random anonymous ID (UUID generated locally — not tied to you)

What is NEVER collected:
  - Prompts, responses, or any conversation content
  - File paths, file contents, or code
  - Usernames, emails, hostnames, IPs (Mixpanel geo is disabled via $ip=0)
  - API keys or tokens

Where it goes: Mixpanel (https://mixpanel.com) and Amplitude
(https://amplitude.com) — event analytics only, same anonymous payload.

Opt out at any time (any of these):
  - Answer "n" at the first-run prompt
  - /config telemetry=off        (inside Dulus)
  - DULUS_TELEMETRY=0            (environment variable)

Each configured provider receives events through urllib in a background
thread. Delivery failures are ignored so the CLI can keep running.
"""
from __future__ import annotations

import base64
import json
import os
import platform
import sys
import threading
import time
import uuid

# Mixpanel PROJECT TOKEN for the public Dulus project.
# NOTE: Mixpanel ingestion tokens are write-only and designed to ship in
# client code (every website using Mixpanel exposes theirs). It cannot be
# used to read any data. Override with DULUS_MP_TOKEN.
MP_TOKEN = os.environ.get("DULUS_MP_TOKEN", "966ce8f5ccb32f06788f51be9f8bf8f5")

_MP_ENDPOINT = "https://api.mixpanel.com/track"

# Amplitude fan-out (same opt-in gate, same anonymous ID, same privacy rules).
# Ingestion keys are write-only by design — they cannot read any data.
AMP_KEY = os.environ.get("DULUS_AMP_KEY", "dbdb0e42b0fc29bfdb4061612c3c8a7e")

_AMP_ENDPOINT = "https://api2.amplitude.com/2/httpapi"

# Populated by init_telemetry(); None = not initialised / disabled.
_distinct_id: str | None = None
_enabled: bool = False
_dulus_version: str = ""


def _env_disabled() -> bool:
    return os.environ.get("DULUS_TELEMETRY", "").strip().lower() in ("0", "off", "false", "no")


def is_enabled() -> bool:
    return _enabled and not _env_disabled() and bool(MP_TOKEN or AMP_KEY)


CONSENT_NOTICE = """
  ── Ayuda a mejorar Dulus / Help improve Dulus ─────────────────────────
  Dulus can share anonymous usage statistics with Mixpanel and Amplitude
  to help us understand which features people use.

    Collected:  event names, Dulus and Python versions, OS, provider, model,
                tool and command names, and a random ID generated on this machine.
    NEVER:      prompts, responses, files, paths, keys, emails, IPs.

  Change your mind anytime:  /config telemetry=off   or  DULUS_TELEMETRY=0
  ────────────────────────────────────────────────────────────────────────
"""


def ask_consent(config: dict) -> dict:
    """One-time interactive consent prompt. Mutates + returns config.

    Only call when config['telemetry'] is unset and stdin is a TTY.
    """
    print(CONSENT_NOTICE)
    try:
        answer = input("  Share anonymous usage stats? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    config["telemetry"] = answer in ("y", "yes", "s", "si", "sí")
    if config["telemetry"] and not config.get("telemetry_id"):
        config["telemetry_id"] = uuid.uuid4().hex
    state = "enabled — thank you! 🦅" if config["telemetry"] else "disabled."
    print(f"  Telemetry {state}\n")
    return config


def init_telemetry(config: dict, version: str = "") -> None:
    """Initialise the module from config. Safe to call multiple times."""
    global _distinct_id, _enabled, _dulus_version
    _dulus_version = version or _dulus_version
    choice = str(config.get("telemetry", "")).strip().lower()
    _enabled = choice in ("true", "on", "1", "yes", "y", "enabled") and not _env_disabled()
    if _enabled:
        _distinct_id = config.get("telemetry_id") or uuid.uuid4().hex
        config["telemetry_id"] = _distinct_id
    else:
        _distinct_id = None


def track(event: str, properties: dict | None = None) -> None:
    """Fire-and-forget anonymous event. No-op unless telemetry is enabled."""
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

        # Consent or the active profile may change while the worker is waiting.
        if not is_enabled() or _distinct_id != distinct_id:
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
