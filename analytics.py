"""Dulus anonymous usage telemetry (opt-in, privacy-first).

Dulus asks ONCE on startup whether you want to share anonymous usage
statistics. Nothing is sent until you explicitly say yes.

What IS collected (when enabled):
  - Event names (session_start, message_sent, tool_used, model_selected)
  - Dulus version, OS name, Python version
  - Provider/model *names* (e.g. "gemini", "claude-sonnet")
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

Implementation notes: zero third-party dependencies — plain urllib POST to
the Mixpanel ingestion API in a fire-and-forget daemon thread. Failures are
silently ignored; telemetry must never slow down or break Dulus.
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
    return _enabled and not _env_disabled() and bool(MP_TOKEN)


CONSENT_NOTICE = """
  ── Ayuda a mejorar Dulus / Help improve Dulus ─────────────────────────
  Dulus can share ANONYMOUS usage statistics to help us understand
  which features matter (event counts only — sent to Mixpanel).

    Collected:  event names, Dulus version, OS, model/provider names,
                a random anonymous ID generated on this machine.
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
    _enabled = bool(config.get("telemetry")) and not _env_disabled()
    if _enabled:
        _distinct_id = config.get("telemetry_id") or uuid.uuid4().hex
        config.setdefault("telemetry_id", _distinct_id)


def track(event: str, properties: dict | None = None) -> None:
    """Fire-and-forget anonymous event. No-op unless telemetry is enabled."""
    if not is_enabled() or not _distinct_id:
        return

    payload = {
        "event": event,
        "properties": {
            "token": MP_TOKEN,
            "distinct_id": _distinct_id,
            "time": int(time.time()),
            "$ip": 0,  # disable Mixpanel geolocation
            "dulus_version": _dulus_version,
            "os": platform.system(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            **(properties or {}),
        },
    }

    def _send() -> None:
        try:
            from urllib.request import Request, urlopen
            from urllib.parse import urlencode

            data = urlencode(
                {"data": base64.b64encode(json.dumps([payload]).encode()).decode()}
            ).encode()
            req = Request(_MP_ENDPOINT, data=data, method="POST")
            urlopen(req, timeout=4).read()
        except Exception:
            pass  # telemetry must never break Dulus

    def _send_amplitude() -> None:
        if not AMP_KEY:
            return
        try:
            from urllib.request import Request, urlopen

            body = json.dumps({
                "api_key": AMP_KEY,
                "events": [{
                    "device_id": _distinct_id,  # same anonymous UUID, never PII
                    "event_type": event,
                    "event_properties": {
                        "dulus_version": _dulus_version,
                        "os": platform.system(),
                        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                        **(properties or {}),
                    },
                    "platform": platform.system(),
                }],
            }).encode()
            req = Request(
                _AMP_ENDPOINT, data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urlopen(req, timeout=4).read()
        except Exception:
            pass  # telemetry must never break Dulus

    threading.Thread(target=_send, daemon=True, name="telemetry").start()
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
