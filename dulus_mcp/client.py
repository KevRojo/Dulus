"""MCP client: stdio and HTTP/SSE transports, JSON-RPC 2.0 protocol."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from .types import (
    MCPServerConfig, MCPServerState, MCPTool, MCPTransport,
    INIT_PARAMS, make_notification, make_request,
)

try:
    from process_utils import windows_no_window_kwargs as _windows_no_window_kwargs
except Exception:  # pragma: no cover - fallback keeps MCP usable if helper moves
    def _windows_no_window_kwargs() -> dict:
        if os.name != "nt":
            return {}
        flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"creationflags": flags} if flags else {}


# ── Stdio transport ───────────────────────────────────────────────────────────

# Launcher names that should be mapped to the current Python interpreter
# when they are not found on PATH. This removes friction from stdio MCP
# configs that use bare "python" or "py".
_PYTHON_LAUNCHERS = {"python", "python3", "py", "py.exe", "python.exe", "python3.exe"}


def _resolve_launcher(launcher: str) -> str:
    """Resolve a stdio launcher to an absolute path when possible.

    - Uses shutil.which() first.
    - Falls back to sys.executable for known Python launchers.
    - Falls back to local/venv/cargo/homebrew paths for uv / uvx.
    - Falls back to common Node / npx paths on macOS, Linux, and Windows.
    - Returns the original launcher if nothing else works.
    """
    launcher = (launcher or "").strip()
    if not launcher:
        return launcher

    resolved = shutil.which(launcher)
    if resolved:
        return resolved

    base = os.path.basename(launcher).lower()
    if base in _PYTHON_LAUNCHERS:
        return sys.executable

    # ── uv / uvx discovery ────────────────────────────────────────────────
    if base in {"uvx", "uv", "uvx.exe", "uv.exe"}:
        py_dir = os.path.dirname(sys.executable)
        candidates = [
            os.path.join(py_dir, base),
            os.path.join(py_dir, "Scripts", base),
            os.path.join(py_dir, base + ".exe"),
            os.path.join(py_dir, "Scripts", base + ".exe"),
            os.path.expanduser(f"~/.local/bin/{base}"),
            os.path.expanduser(f"~/.cargo/bin/{base}"),
            f"/opt/homebrew/bin/{base}",
            f"/usr/local/bin/{base}",
            f"/usr/bin/{base}",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        # If uv module is present in Python, we can route through sys.executable
        try:
            import uv  # noqa: F401
            return sys.executable
        except ImportError:
            pass

    # ── Node.js / npx discovery ───────────────────────────────────────────
    if base in {"node", "node.exe", "npx", "npx.cmd", "npx.exe"}:
        import glob
        is_npx = "npx" in base
        candidates = [
            f"/opt/homebrew/bin/{'npx' if is_npx else 'node'}",
            f"/usr/local/bin/{'npx' if is_npx else 'node'}",
            f"/usr/bin/{'npx' if is_npx else 'node'}",
            os.path.expanduser(f"~/.nvm/versions/node/*/bin/{'npx' if is_npx else 'node'}"),
            os.path.expanduser(f"~/.fnm/current/bin/{'npx' if is_npx else 'node'}"),
            os.path.expanduser(f"~/.volta/bin/{'npx' if is_npx else 'node'}"),
            os.path.expanduser(f"~/.asdf/shims/{'npx' if is_npx else 'node'}"),
            os.path.expandvars(r"%ProgramFiles%\nodejs\npx.cmd" if is_npx else r"%ProgramFiles%\nodejs\node.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\nodejs\npx.cmd" if is_npx else r"%ProgramFiles(x86)%\nodejs\node.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs\npx.cmd" if is_npx else r"%LOCALAPPDATA%\Programs\nodejs\node.exe"),
            os.path.expandvars(r"%APPDATA%\npm\npx.cmd" if is_npx else r"%APPDATA%\npm\node.exe"),
        ]
        for pattern in candidates:
            for candidate in glob.glob(pattern):
                if os.path.exists(candidate):
                    return candidate

    return launcher


# Env vars that are safe to forward to an untrusted MCP stdio server.
# We do NOT forward the full os.environ because the server could read Dulus's
# own API keys, tokens, and other secrets. Only pass what is needed for the
# launcher/runtime to work (PATH, user profile, temp dirs) plus the env block
# explicitly configured for this server.
_ALLOWED_ENV_VARS = {
    # Launcher/runtime basics
    "PATH", "PATHEXT",
    # Windows profile/temp
    "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH",
    "TEMP", "TMP", "TMPDIR",
    "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "USERNAME", "COMPUTERNAME", "USERDOMAIN", "USERDOMAIN_ROAMINGPROFILE",
    # Locale/terminal
    "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "TERM",
    # Node tooling
    "NODE_PATH", "NPM_CONFIG_PREFIX", "NPM_CONFIG_CACHE", "NPM_CONFIG_TMP",
    # Python runtime (so uv/uvx can find Python if needed)
    "PYTHONPATH", "PYTHONHOME", "PY_PYTHON",
    # Docker/cli basics
    "DOCKER_HOST", "DOCKER_CONFIG",
}


def _minimal_subprocess_env() -> dict:
    """Return a scrubbed environment dict safe to pass to MCP stdio servers."""
    return {k: v for k, v in os.environ.items() if k.upper() in _ALLOWED_ENV_VARS}


# Tokens / secrets that may appear in MCP stderr or error messages.
_SENSITIVE_PATTERNS = ("token", "secret", "password", "api_key", "apikey",
                       "authorization", "bearer", "private_key", "credentials")


def _sanitize_for_display(text: str) -> str:
    """Redact lines that look like they contain secrets."""
    lines: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if any(p in lower for p in _SENSITIVE_PATTERNS):
            lines.append("[REDACTED: potential secret]")
        else:
            lines.append(line)
    return "\n".join(lines)


class StdioTransport:
    """Bidirectional JSON-RPC over a subprocess's stdin/stdout.

    Messages are newline-delimited JSON objects (one per line).
    Responses are matched to requests by 'id'.
    """

    def __init__(self, config: MCPServerConfig):
        self._config = config
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._pending: Dict[int, dict] = {}   # id → {"event": Event, "result": ...}
        self._reader: Optional[threading.Thread] = None
        self._stderr_reader: Optional[threading.Thread] = None
        self._running = False
        self._stderr_lines: List[str] = []

    def start(self) -> None:
        env = {**_minimal_subprocess_env(), **(self._config.env or {})}
        # ── Guard: empty/blank command ────────────────────────────────────
        if not (self._config.command or "").strip():
            raise RuntimeError(
                f"MCP server '{self._config.name}' has no command configured "
                f"(empty 'command' field in mcp.json). Fix or remove this entry."
            )
        # ── Launcher resolution ────────────────────────────────────────────
        # Resolve bare Python/Node launchers to absolute paths so subprocess
        # works even when the MCP server's environment has a different PATH.
        _launcher = _resolve_launcher(self._config.command)
        if self._config.command in ("uvx", "uv") and _launcher == sys.executable:
            cmd = [sys.executable, "-m", "uv", "tool", "run"] + list(self._config.args or [])
        else:
            if not os.path.exists(_launcher) and not shutil.which(_launcher):
                # Fallback: check if uv package is importable
                if self._config.command in ("uvx", "uv"):
                    try:
                        import uv  # noqa: F401
                        _launcher = sys.executable
                        cmd = [sys.executable, "-m", "uv", "tool", "run"] + list(self._config.args or [])
                    except ImportError:
                        pass
                if not os.path.exists(_launcher) and not shutil.which(_launcher):
                    raise RuntimeError(
                        f"MCP server '{self._config.name}': launcher '{self._config.command}' "
                        f"could not be resolved. Install the runtime or fix the 'command' field."
                    )
            cmd = [_launcher] + list(self._config.args or [])
        # On Windows, .cmd/.bat shims must run through the shell layer.
        _use_shell = os.name == "nt" and str(_launcher).lower().endswith((".cmd", ".bat"))
        # On Windows, stdio MCP servers are console programs (node/npx/python).
        # Launched from the windowed .exe (console=False) they would each spawn
        # a visible cmd window that lingers for the server's whole lifetime.
        # CREATE_NO_WINDOW + hidden STARTUPINFO keeps them invisible.
        _no_window = _windows_no_window_kwargs()
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            shell=_use_shell,
            **_no_window,
        )
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(target=self._stderr_loop, daemon=True)
        self._stderr_reader.start()

    def _read_loop(self) -> None:
        while self._running and self._process:
            try:
                _stdout = self._process.stdout
                if _stdout is None:
                    break
                raw = _stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                msg = json.loads(line)
            except Exception:
                continue
            # Dispatch: response (has "id") vs notification (no "id")
            msg_id = msg.get("id")
            if msg_id is not None and msg_id in self._pending:
                holder = self._pending[msg_id]
                holder["result"] = msg
                holder["event"].set()

    def _stderr_loop(self) -> None:
        while self._running and self._process:
            try:
                _stderr = self._process.stderr
                if _stderr is None:
                    break
                raw = _stderr.readline()
                if not raw:
                    break
                self._stderr_lines.append(raw.decode("utf-8", errors="replace").rstrip())
            except Exception:
                break

    def _send_raw(self, msg: dict) -> None:
        line = (json.dumps(msg) + "\n").encode("utf-8")
        with self._lock:
            if self._process is None or self._process.stdin is None:
                raise RuntimeError("MCP stdio process is not running")
            self._process.stdin.write(line)
            self._process.stdin.flush()

    def request(self, method: str, params: Optional[dict] = None, timeout: Optional[int] = None) -> dict:
        """Send a JSON-RPC request and wait for the response."""
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
        event = threading.Event()
        holder: dict = {"event": event, "result": None}
        self._pending[req_id] = holder
        msg = make_request(method, params, req_id)
        self._send_raw(msg)
        wait_secs = timeout or self._config.timeout
        event.wait(timeout=wait_secs)
        self._pending.pop(req_id, None)
        result = holder["result"]
        if result is None:
            stderr_tail = self.stderr_output
            detail = f"MCP server '{self._config.name}' timed out on '{method}'"
            if stderr_tail:
                detail += f". Server stderr:\n{stderr_tail}"
            else:
                detail += ". The server may have hung or failed to start."
            raise TimeoutError(detail)
        if "error" in result:
            err = result["error"]
            msg = f"MCP error {err.get('code')}: {err.get('message')}"
            stderr_tail = self.stderr_output
            if stderr_tail:
                msg += f"\nServer stderr:\n{stderr_tail}"
            raise RuntimeError(msg)
        return result.get("result", {})

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        self._send_raw(make_notification(method, params))

    def stop(self) -> None:
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                pass
            self._process = None

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def stderr_output(self) -> str:
        return _sanitize_for_display("\n".join(self._stderr_lines[-20:]))


# ── HTTP / SSE transport ──────────────────────────────────────────────────────

class HttpTransport:
    """HTTP-based MCP transport (POST-based streamable HTTP or SSE endpoint).

    For SSE servers: sends messages via POST to the SSE session endpoint.
    For HTTP servers: sends messages via POST and reads response directly.
    """

    def __init__(self, config: MCPServerConfig):
        self._config = config
        self._session_url: Optional[str] = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._client = None   # httpx.Client, loaded lazily
        self._sse_thread: Optional[threading.Thread] = None
        self._sse_pending: Dict[int, dict] = {}
        self._running = False
        self._mcp_session_id: Optional[str] = None
        self._composio_style: bool = False  # for servers like Composio that use direct POST + Mcp-Session-Id header

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
                # Base headers: always accept both JSON and SSE
                headers = {
                    **self._config.headers,
                    "Accept": "application/json, text/event-stream",
                }
                self._client = httpx.Client(
                    headers=headers,
                    timeout=self._config.timeout,
                    follow_redirects=True,
                )
            except ImportError:
                raise RuntimeError("httpx is required for HTTP/SSE MCP transport: pip install httpx")
        return self._client

    def _inject_session_header(self, extra_headers: dict | None = None) -> dict:
        """Add Mcp-Session-Id if we have one (for Composio-style and modern MCP)."""
        h = {}
        if extra_headers:
            h.update(extra_headers)
        if self._mcp_session_id:
            h["Mcp-Session-Id"] = self._mcp_session_id
        return h

    def start(self) -> None:
        """For SSE transport: connect to the /sse endpoint and get session URL.

        Supports two styles:
        - Traditional SSE: GET /sse → receives 'endpoint' event with session URL
        - Modern / Composio-style: POST directly to the URL. Server returns
          Mcp-Session-Id header on first response (often text/event-stream).
          The initial GET will fail with 400 "Mcp-Session-Id header is required".
        """
        if self._config.transport == MCPTransport.SSE:
            # Special case for Composio (and similar modern MCP servers over HTTP):
            # They do NOT support the traditional GET /sse for endpoint.
            # First POST to the URL returns 200 + text/event-stream + "mcp-session-id" header.
            # All future calls must include "Mcp-Session-Id".
            if self._config.name.lower() == "composio":
                self._session_url = self._config.url
                self._composio_style = True
                return

            try:
                self._start_sse()
            except RuntimeError as e:
                msg = str(e).lower()
                if "mcp-session-id" in msg or "session" in msg or "400" in msg:
                    self._session_url = self._config.url
                    self._composio_style = True
                else:
                    raise
        else:
            self._session_url = self._config.url
            self._composio_style = True

    def _start_sse(self) -> None:
        """Open SSE stream to get session endpoint, then start background reader."""
        import httpx
        client = self._get_client()
        self._running = True

        # Initial SSE connect — first event should be 'endpoint' with session URL
        endpoint_event = threading.Event()
        endpoint_holder: dict = {"url": None, "error": None}

        def _sse_reader():
            try:
                with client.stream("GET", self._config.url, headers={"Accept": "text/event-stream"}) as resp:
                    resp.raise_for_status()
                    event_type = None
                    for line in resp.iter_lines():
                        if not self._running:
                            break
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data = line[5:].strip()
                            if event_type == "endpoint":
                                # Session URL may be relative or absolute
                                base = self._config.url.rsplit("/sse", 1)[0]
                                session_url = data if data.startswith("http") else base + data
                                endpoint_holder["url"] = session_url
                                self._session_url = session_url
                                endpoint_event.set()
                            elif event_type == "message":
                                try:
                                    msg = json.loads(data)
                                    msg_id = msg.get("id")
                                    if msg_id is not None and msg_id in self._sse_pending:
                                        holder = self._sse_pending[msg_id]
                                        holder["result"] = msg
                                        holder["event"].set()
                                except Exception:
                                    pass
            except Exception as e:
                endpoint_holder["error"] = str(e)
                endpoint_event.set()

        self._sse_thread = threading.Thread(target=_sse_reader, daemon=True)
        self._sse_thread.start()
        endpoint_event.wait(timeout=10)
        if endpoint_holder.get("error"):
            raise RuntimeError(f"SSE connect failed: {endpoint_holder['error']}")
        if not self._session_url:
            raise RuntimeError("SSE server did not send 'endpoint' event")

    def request(self, method: str, params: Optional[dict] = None, timeout: Optional[int] = None) -> dict:
        with self._lock:
            req_id = self._next_id
            self._next_id += 1

        msg = make_request(method, params, req_id)
        client = self._get_client()
        wait_secs = timeout or self._config.timeout
        target_url = self._session_url or self._config.url

        # Inject Mcp-Session-Id if we already have one (Composio + modern MCP require it after first response)
        post_headers = self._inject_session_header()

        if self._composio_style or self._config.transport == MCPTransport.HTTP:
            # Composio-style / modern streamable HTTP:
            # Direct POST, server returns text/event-stream with the response + Mcp-Session-Id header.
            # We capture the session id from the first response and use it in future headers.
            resp = client.post(target_url, json=msg, headers=post_headers if post_headers else None, timeout=wait_secs)
            resp.raise_for_status()

            # Capture Mcp-Session-Id (header name is case-insensitive in practice, but we check common variants)
            session_hdr = (
                resp.headers.get("mcp-session-id")
                or resp.headers.get("Mcp-Session-Id")
                or resp.headers.get("MCP-Session-Id")
            )
            if session_hdr and not self._mcp_session_id:
                self._mcp_session_id = session_hdr

            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type.lower():
                result = self._parse_sse_for_id(resp.text, req_id)
            else:
                result = resp.json()

        elif self._config.transport == MCPTransport.SSE:
            # Traditional SSE: persistent GET stream + POST requests, responses come on the stream
            event = threading.Event()
            holder: dict = {"event": event, "result": None}
            self._sse_pending[req_id] = holder
            client.post(target_url, json=msg, headers=post_headers if post_headers else None)
            event.wait(timeout=wait_secs)
            self._sse_pending.pop(req_id, None)
            result = holder["result"]
        else:
            # Fallback pure HTTP
            resp = client.post(target_url, json=msg, headers=post_headers if post_headers else None, timeout=wait_secs)
            resp.raise_for_status()
            result = resp.json()

        if result is None:
            raise TimeoutError(f"MCP server '{self._config.name}' timed out on '{method}'")
        if "error" in result:
            err = result["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
        return result.get("result", {})

    def notify(self, method: str, params: Optional[dict] = None) -> None:
        client = self._get_client()
        msg = make_notification(method, params)
        url = self._session_url or self._config.url
        post_headers = self._inject_session_header()
        try:
            client.post(url, json=msg, headers=post_headers if post_headers else None)
        except Exception:
            pass

    def _parse_sse_for_id(self, sse_text: str, target_id: int) -> dict:
        """Parse a text/event-stream body and return the JSON-RPC response with matching id."""
        current_event = None
        for line in sse_text.splitlines():
            line = line.strip()
            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
                if current_event in (None, "message") and data:
                    try:
                        obj = json.loads(data)
                        if obj.get("id") == target_id:
                            return obj
                    except Exception:
                        pass
        return {}

    def stop(self) -> None:
        self._running = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    @property
    def alive(self) -> bool:
        return self._session_url is not None or self._config.transport == MCPTransport.HTTP


# ── High-level MCP client ─────────────────────────────────────────────────────

class MCPClient:
    """Manages the lifecycle of one MCP server connection.

    Protocol flow:
        connect() → initialize handshake → notifications/initialized
        list_tools() → tools/list
        call_tool()  → tools/call
        disconnect() → cleanup
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.state = MCPServerState.DISCONNECTED
        self._transport: Optional[Any] = None
        self._server_info: dict = {}
        self._capabilities: dict = {}
        self._tools: List[MCPTool] = []
        self._error: str = ""

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        if self.state == MCPServerState.CONNECTED:
            return
        self.state = MCPServerState.CONNECTING
        self._error = ""
        try:
            self._transport = self._make_transport()
            self._transport.start()
            self._handshake()
            self.state = MCPServerState.CONNECTED
        except Exception as e:
            self.state = MCPServerState.ERROR
            error_msg = str(e)
            # Include captured stderr for stdio servers to aid diagnosis.
            if self._transport and hasattr(self._transport, "stderr_output"):
                stderr_tail = self._transport.stderr_output
                if stderr_tail:
                    error_msg += f"\nServer stderr:\n{stderr_tail}"
            self._error = error_msg
            raise RuntimeError(error_msg) from e

    def _make_transport(self):
        t = self.config.transport
        if t == MCPTransport.STDIO:
            return StdioTransport(self.config)
        if t in (MCPTransport.SSE, MCPTransport.HTTP):
            return HttpTransport(self.config)
        raise ValueError(f"Unsupported MCP transport: {t}")

    def _handshake(self) -> None:
        if self._transport is None:
            raise RuntimeError("MCP transport not started")
        result = self._transport.request("initialize", INIT_PARAMS, timeout=15)
        self._server_info = result.get("serverInfo", {})
        self._capabilities = result.get("capabilities", {})
        self._transport.notify("notifications/initialized")

    def disconnect(self) -> None:
        if self._transport:
            self._transport.stop()
            self._transport = None
        self.state = MCPServerState.DISCONNECTED

    def reconnect(self) -> None:
        self.disconnect()
        self.connect()

    @property
    def alive(self) -> bool:
        return (
            self.state == MCPServerState.CONNECTED
            and self._transport is not None
            and self._transport.alive
        )

    # ── Tool discovery ────────────────────────────────────────────────────────

    def list_tools(self) -> List[MCPTool]:
        """Fetch tool list from server and cache as MCPTool objects."""
        if self.state != MCPServerState.CONNECTED:
            raise RuntimeError(f"MCP server '{self.config.name}' is not connected")
        if self._transport is None:
            raise RuntimeError(f"MCP server '{self.config.name}' has no transport")

        if "tools" not in self._capabilities:
            self._tools = []
            return self._tools

        result = self._transport.request("tools/list", timeout=15)
        raw_tools = result.get("tools", [])
        self._tools = [self._parse_tool(t) for t in raw_tools]
        return self._tools

    def _parse_tool(self, raw: dict) -> MCPTool:
        tool_name = raw.get("name", "")
        qualified = f"mcp__{self.config.name}__{tool_name}"
        # Sanitize: replace non-alphanumeric with _ for API compatibility
        qualified = "".join(c if c.isalnum() or c == "_" else "_" for c in qualified)

        annotations = raw.get("annotations", {})
        read_only = bool(annotations.get("readOnlyHint", False))

        schema = raw.get("inputSchema", {"type": "object", "properties": {}})
        # Ensure minimum valid JSON schema
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}

        return MCPTool(
            server_name=self.config.name,
            tool_name=tool_name,
            qualified_name=qualified,
            description=raw.get("description", ""),
            input_schema=schema,
            read_only=read_only,
        )

    # ── Tool invocation ───────────────────────────────────────────────────────

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool by its original (non-qualified) name.

        Returns the text content from the response, or an error string.
        """
        if self.state != MCPServerState.CONNECTED:
            raise RuntimeError(f"MCP server '{self.config.name}' is not connected")
        if self._transport is None:
            raise RuntimeError(f"MCP server '{self.config.name}' has no transport")

        params = {"name": tool_name, "arguments": arguments}
        result = self._transport.request("tools/call", params, timeout=self.config.timeout)

        is_error = result.get("isError", False)
        content = result.get("content", [])

        # Collect text content blocks
        parts: List[str] = []
        for block in content:
            btype = block.get("type", "")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "image":
                parts.append(f"[image: {block.get('mimeType', 'unknown')}]")
            elif btype == "resource":
                res = block.get("resource", {})
                parts.append(f"[resource: {res.get('uri', '')}]")

        text = "\n".join(parts) if parts else str(result)
        if is_error:
            return f"[MCP tool error]\n{text}"
        return text

    # ── Status ────────────────────────────────────────────────────────────────

    def status_line(self) -> str:
        icon = {"connected": "✓", "connecting": "…", "disconnected": "○", "error": "✗"}.get(
            self.state.value, "?"
        )
        server = self._server_info.get("name", self.config.name)
        version = self._server_info.get("version", "")
        tool_count = len(self._tools)
        line = f"{icon} {self.config.name}"
        if server and server != self.config.name:
            line += f" ({server}"
            if version:
                line += f" v{version}"
            line += ")"
        if self.state == MCPServerState.CONNECTED:
            line += f"  [{tool_count} tool(s)]"
        if self.state == MCPServerState.ERROR:
            line += f"  error: {self._error}"
        return line


# ── Manager ───────────────────────────────────────────────────────────────────

class MCPManager:
    """Singleton that manages all configured MCP server connections."""

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}

    def add_server(self, config: MCPServerConfig) -> MCPClient:
        """Register a server. Replaces any existing client with the same name."""
        if config.name in self._clients:
            try:
                self._clients[config.name].disconnect()
            except Exception:
                pass
        client = MCPClient(config)
        self._clients[config.name] = client
        return client

    def connect_all(self) -> Dict[str, Optional[str]]:
        """Connect to all registered servers. Returns {name: error_or_None}."""
        errors: Dict[str, Optional[str]] = {}
        for name, client in self._clients.items():
            if client.config.disabled:
                errors[name] = "disabled"
                continue
            try:
                client.connect()
                client.list_tools()
                errors[name] = None
            except Exception as e:
                errors[name] = str(e)
        return errors

    def connect_server(self, name: str) -> MCPClient:
        """Connect (or reconnect) a single server by name."""
        client = self._clients.get(name)
        if client is None:
            raise KeyError(f"MCP server '{name}' not configured")
        if client.state != MCPServerState.CONNECTED:
            client.connect()
            client.list_tools()
        return client

    def all_tools(self) -> List[MCPTool]:
        """Return all tools from all connected servers."""
        tools: List[MCPTool] = []
        for client in self._clients.values():
            if client.state == MCPServerState.CONNECTED:
                tools.extend(client._tools)
        return tools

    def call_tool(self, qualified_name: str, arguments: dict) -> str:
        """Dispatch a tool call by qualified name (mcp__server__tool)."""
        # Parse server and tool name from qualified name
        parts = qualified_name.split("__", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            raise ValueError(f"Invalid MCP tool name: {qualified_name}")
        server_name = parts[1]
        tool_name = parts[2]

        client = self._clients.get(server_name)
        if client is None:
            raise RuntimeError(f"MCP server '{server_name}' not configured")

        # Auto-reconnect if dropped
        if not client.alive:
            client.reconnect()
            client.list_tools()

        # Find the original tool name (un-sanitized)
        original_name = tool_name
        for t in client._tools:
            if t.qualified_name == qualified_name:
                original_name = t.tool_name
                break

        return client.call_tool(original_name, arguments)

    def list_servers(self) -> List[MCPClient]:
        return list(self._clients.values())

    def disconnect_all(self) -> None:
        for client in self._clients.values():
            try:
                client.disconnect()
            except Exception:
                pass

    def reload_server(self, name: str) -> None:
        client = self._clients.get(name)
        if client:
            client.reconnect()
            client.list_tools()


# ── Module-level singleton ────────────────────────────────────────────────────

_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    global _manager
    if _manager is None:
        _manager = MCPManager()
    return _manager
