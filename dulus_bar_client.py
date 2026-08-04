"""Native Dulus Bar (Dynamic Island) client — optional, non-invasive.

Streams Dulus's live status to the Dulus Bar island over
``ws://127.0.0.1:17372`` and receives Allow/Deny decisions back. This is the
"native bridge" path: because Dulus talks to the island directly, it keeps its
own real terminal (a TTY) and renders full emoji + animations — unlike the
generic stdout-scraping wrapper, which pipes stdout and forces plain mode.

Entirely optional and defensive by design:
  * Off unless ``DULUS_BAR=1`` (set by the island when it launches Dulus) or
    ``/config dulus_bar=1``.
  * If ``websockets`` is missing or the island isn't running, every call is a
    silent no-op. Nothing here may ever raise into Dulus's main loop.

Wire protocol (agent -> bar):
    {"agent": "Dulus", "type": <event>, "session_id": "ab12cd34",
     "payload": {"text": "...", "model": "kimi/kimi-k2.5", "ctx": "38%"}}
  events: session_started, message, tool_request, tool_approved, tool_denied,
          completed, error
Bar -> agent (decision):
    {"type": "decision", "session_id": "ab12cd34", "payload": {"approved": true}}
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import uuid
from typing import Callable, Dict, List, Optional

AGENT_NAME = "Dulus"
BAR_URL = os.environ.get("DULUS_BAR_URL", "ws://127.0.0.1:17372")
_MAX_CONNECT_ATTEMPTS = 8   # give up quietly if the island never appears
_RECONNECT_DELAY = 2.0


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _gui_available() -> bool:
    """A GUI can only pop up where there's a display."""
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _installed() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("dulus_bar") is not None
    except Exception:
        return False


def enabled(config: Optional[Dict] = None) -> bool:
    """True when the Dulus Bar integration should run this session.

    Default: ON whenever the `dulus_bar` package is installed (``pip install
    dulus-bar``) and a GUI is available — so Dulus opens with the island out of
    the box. Explicit switches win: ``DULUS_BAR`` / ``/config dulus_bar`` set to
    a truthy value forces it on, a falsey value ('0', 'off', 'no') forces it off.
    """
    env = os.environ.get("DULUS_BAR", "")
    if env.strip():
        return _truthy(env)
    if config is not None:
        try:
            cv = config.get("dulus_bar", None)
            if cv is not None and str(cv).strip() != "":
                return _truthy(cv)
        except Exception:
            pass
    # Default: on when installed + GUI-capable.
    return _gui_available() and _installed()


def _bar_host_port() -> tuple[str, int]:
    try:
        rest = BAR_URL.split("://", 1)[-1]
        hostport = rest.split("/", 1)[0]
        host, _, port = hostport.partition(":")
        return host or "127.0.0.1", int(port or 17372)
    except Exception:
        return "127.0.0.1", 17372


def _port_open(timeout: float = 0.4) -> bool:
    import socket
    host, port = _bar_host_port()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _launch_island() -> None:
    """Spawn the Dulus Bar island detached — only if installed, GUI-capable, and
    not already running. Best-effort: any failure is swallowed."""
    if _port_open() or not _gui_available() or not _installed():
        return
    import subprocess
    argv = [sys.executable, "-m", "dulus_bar"]
    try:
        if os.name == "nt":
            _DETACHED, _NO_WINDOW = 0x00000008, 0x08000000
            subprocess.Popen(argv, creationflags=_DETACHED | _NO_WINDOW, close_fds=True)
        else:
            subprocess.Popen(
                argv, start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


class DulusBarClient:
    """Fire-and-forget websocket client running on its own asyncio thread."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ws: object = None
        self._session_id = uuid.uuid4().hex[:8]
        self._model = ""
        self._decision_cbs: List[Callable[[bool, Optional[str]], None]] = []
        self._started = False
        self._stopping = False
        self._last_status: Optional[tuple] = None

    # -- lifecycle -------------------------------------------------------
    def start(self, model: str = "", session_id: Optional[str] = None) -> bool:
        """Begin connecting in the background. Returns False if unavailable."""
        if self._started:
            return True
        if session_id:
            self._session_id = session_id
        if model:
            self._model = model
        try:
            import websockets  # noqa: F401
        except Exception:
            return False  # dependency absent -> stay a no-op
        # Open the island for the user if it isn't already up — this is what
        # makes "run Dulus, the island appears" work out of the box.
        try:
            _launch_island()
        except Exception:
            pass
        self._started = True
        self._thread = threading.Thread(
            target=self._run, name="dulus-bar-client", daemon=True
        )
        self._thread.start()
        try:
            import atexit

            atexit.register(self._atexit)
        except Exception:
            pass
        return True

    def _atexit(self) -> None:
        try:
            self.completed()
        except Exception:
            pass
        self.stop()

    def stop(self) -> None:
        self._stopping = True
        loop = self._loop
        if loop is not None:
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass

    def on_decision(self, cb: Callable[[bool, Optional[str]], None]) -> None:
        """Register a callback fired when the island answers a tool_request."""
        self._decision_cbs.append(cb)

    # -- emit helpers (all non-blocking, all safe) -----------------------
    def session_started(self, model: str = "") -> None:
        if model:
            self._model = model
        self._send("session_started", {"model": self._model})

    def message(self, text: str = "", model: str = "", ctx: str = "") -> None:
        if model:
            self._model = model
        self._send(
            "message",
            {"text": (text or "")[:200], "model": self._model, "ctx": ctx},
        )

    def status(self, model: str = "", ctx: str = "") -> None:
        """Refresh just the model/ctx on the island. De-duplicated so it's cheap
        to call on every prompt/keystroke cycle — only a real change is sent."""
        key = (model or self._model, ctx)
        if key == self._last_status:
            return
        self._last_status = key
        self.message("", model=model, ctx=ctx)

    def tool_request(self, tool: str, args: str = "") -> None:
        self._send("tool_request", {"tool": tool, "args": str(args)[:300]})

    def tool_result(self, approved: bool) -> None:
        self._send("tool_approved" if approved else "tool_denied", {})

    def completed(self) -> None:
        self._send("completed", {})

    def error(self, text: str = "") -> None:
        self._send("error", {"text": (text or "")[:200]})

    # -- internals -------------------------------------------------------
    def _send(self, event_type: str, payload: Dict) -> None:
        if not self._started or self._loop is None or self._ws is None:
            return
        msg = {
            "agent": AGENT_NAME,
            "type": event_type,
            "session_id": self._session_id,
            "payload": payload,
        }
        try:
            asyncio.run_coroutine_threadsafe(self._async_send(msg), self._loop)
        except Exception:
            pass

    async def _async_send(self, msg: Dict) -> None:
        ws = self._ws
        if ws is None:
            return
        try:
            await ws.send(json.dumps(msg))
        except Exception:
            pass

    def _run(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._connect_loop())
        except Exception:
            pass

    async def _connect_loop(self) -> None:
        import websockets

        attempts = 0
        while not self._stopping and attempts < _MAX_CONNECT_ATTEMPTS:
            attempts += 1
            try:
                async with websockets.connect(
                    BAR_URL, ping_interval=20, open_timeout=3
                ) as ws:
                    self._ws = ws
                    attempts = 0  # reset once we're in
                    await ws.send(
                        json.dumps(
                            {
                                "agent": AGENT_NAME,
                                "type": "session_started",
                                "session_id": self._session_id,
                                "payload": {"model": self._model},
                            }
                        )
                    )
                    async for raw in ws:
                        self._on_incoming(raw)
            except Exception:
                self._ws = None
                if self._stopping:
                    break
                await asyncio.sleep(_RECONNECT_DELAY)
        self._ws = None

    def _on_incoming(self, raw: object) -> None:
        try:
            data = json.loads(raw)
        except Exception:
            return
        if not isinstance(data, dict) or data.get("type") != "decision":
            return
        approved = bool((data.get("payload") or {}).get("approved"))
        session_id = data.get("session_id")
        for cb in list(self._decision_cbs):
            try:
                cb(approved, session_id)
            except Exception:
                pass


# -- module-level singleton -------------------------------------------------
_client: Optional[DulusBarClient] = None


def get() -> DulusBarClient:
    global _client
    if _client is None:
        _client = DulusBarClient()
    return _client
