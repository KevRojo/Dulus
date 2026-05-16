"""Local HTTP server that serves the bundled sandbox/dist tree.

Why a dedicated server (vs file:// URLs):
  The sandbox's built index.html references its bundled JS as
  `/sandbox/assets/...` — absolute paths under a `/sandbox/` prefix.
  file:// URLs would either need rewriting (fragile) or would 404
  every asset. A trivial localhost HTTP server serving the right
  base path is the cheapest correct fix.

Why an ephemeral port:
  Avoids colliding with whatever the user already has on :5000 /
  :8080 / etc. The server picks port 0, the OS hands back a free
  one, and we expose `.url` for the caller to use.

The server runs in a daemon thread. Stop() shuts it down cleanly
when the GUI exits.
"""
from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path
from typing import Optional


def _resolve_sandbox_dist() -> Optional[Path]:
    """Find sandbox/dist whether running from source tree or installed wheel.

    Mirrors the resolution in sandbox_bootstrap.py so source-tree dev runs
    and pip-installed runs both work.
    """
    # 1) Walk up from this file looking for a sandbox/dist sibling
    here = Path(__file__).resolve()
    for parent in [here.parent.parent, here.parent.parent.parent, here.parent]:
        candidate = parent / "sandbox" / "dist"
        if (candidate / "index.html").exists():
            return candidate
    # 2) Installed wheel layout: sandbox is a top-level package
    try:
        from importlib.resources import files as _f
        pkg_dist = Path(str(_f("sandbox") / "dist"))
        if (pkg_dist / "index.html").exists():
            return pkg_dist
    except Exception:
        pass
    return None


class _SandboxRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the sandbox/dist tree under a /sandbox/ URL prefix.

    Strips a leading /sandbox/ from the path so the built index.html's
    `/sandbox/assets/...` references resolve relative to dist root.
    Falls back to serving / as index.html for convenience.
    """

    # Filled in by SandboxServer.start() before the server starts handling.
    sandbox_root: Path = Path(".")

    def translate_path(self, path: str) -> str:
        # Strip query string and fragment
        for sep in ("?", "#"):
            if sep in path:
                path = path.split(sep, 1)[0]
        # Drop the /sandbox/ prefix if present
        if path.startswith("/sandbox/"):
            path = path[len("/sandbox"):]   # keep leading slash
        elif path == "/sandbox":
            path = "/"
        # Root → index.html
        if path in ("", "/"):
            path = "/index.html"
        # Strip leading slash to make it relative
        rel = path.lstrip("/")
        return str(self.sandbox_root / rel)

    def log_message(self, format, *args):  # noqa: A002  (stdlib name)
        # Silence per-request logging in the GUI process — too noisy.
        return


class SandboxServer:
    """Singleton-ish local HTTP server for the sandbox UI.

    Usage:
        srv = SandboxServer()
        if srv.available:
            srv.start()             # idempotent
            url = srv.url           # "http://127.0.0.1:<port>/sandbox/"
            ...
            srv.stop()              # on GUI shutdown
    """

    def __init__(self) -> None:
        self._dist = _resolve_sandbox_dist()
        self._httpd: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._port: int = 0

    @property
    def available(self) -> bool:
        """True if the sandbox bundle was found on disk."""
        return self._dist is not None

    @property
    def url(self) -> str:
        """Full URL to the sandbox entry — empty string if not started."""
        if self._port:
            return f"http://127.0.0.1:{self._port}/sandbox/"
        return ""

    def start(self) -> str:
        """Start the server (idempotent). Returns the URL."""
        if self._httpd is not None:
            return self.url
        if not self._dist:
            return ""

        # Bind the dist root onto the handler class as a class attribute so
        # the inner Handler instances pick it up without a constructor hack.
        handler_cls = type(
            "BoundSandboxHandler",
            (_SandboxRequestHandler,),
            {"sandbox_root": self._dist},
        )

        # Port 0 → OS picks a free port; we read it back from sockname.
        self._httpd = socketserver.TCPServer(("127.0.0.1", 0), handler_cls)
        self._port = self._httpd.server_address[1]

        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="dulus-sandbox-server",
            daemon=True,
        )
        self._thread.start()
        return self.url

    def stop(self) -> None:
        """Stop the server and wait for the worker thread to exit."""
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._port = 0
