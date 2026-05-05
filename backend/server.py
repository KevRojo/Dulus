"""Zero-dependency HTTP server for Dulus Dashboard + API + SSE Live Updates."""
import json
import os
import queue
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend.context import build_context, build_smart_context, get_compact_context
from backend.personas import create_persona, get_active_persona, get_all_personas, get_persona, load_personas, set_active_persona, update_persona
from backend.plugins import load_all_plugins, get_plugin_info, start_watcher, stop_watcher, watcher_status, reload_plugin, unload_plugin
from backend.tasks import create_task, load_tasks, update_task

DASHBOARD_DIR = Path(__file__).parent.parent / "docs" / "dashboard"

# ─────────── SSE Broadcast System ───────────
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def _add_sse_client(q: queue.Queue):
    with _sse_lock:
        _sse_clients.append(q)


def _remove_sse_client(q: queue.Queue):
    with _sse_lock:
        if q in _sse_clients:
            _sse_clients.remove(q)


def broadcast_event(event_type: str, payload: dict):
    """Broadcast JSON event to all connected SSE clients."""
    data = json.dumps({"type": event_type, "data": payload, "ts": time.time()})
    msg = f"event: {event_type}\ndata: {data}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


def _sse_heartbeat():
    """Send periodic ping to keep connections alive."""
    while True:
        time.sleep(15)
        broadcast_event("ping", {"status": "ok"})


threading.Thread(target=_sse_heartbeat, daemon=True, name="sse-heartbeat").start()


class DulusHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Suppress default logging
        pass

    def _safe_handle(self, handler_fn):
        """Wrap request handlers so unhandled exceptions return 500 instead of killing the server thread."""
        try:
            handler_fn()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self._error(f"Internal server error: {e}", 500)
            except Exception:
                pass

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _text_response(self, text, status=200, content_type="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _error(self, msg, status=400):
        self._json_response({"error": msg}, status)

    def _parse_query(self):
        return parse_qs(urlparse(self.path).query)

    def _sse_stream(self, client_q: queue.Queue):
        """Send SSE headers and stream from queue until client disconnects."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        self.wfile.write(f"event: connected\ndata: {json.dumps({'message':'Dulus SSE active'})}\n\n".encode("utf-8"))
        self.wfile.flush()

        try:
            while True:
                try:
                    msg = client_q.get(timeout=30)
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b":\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            _remove_sse_client(client_q)

    def _do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # ── SSE Live Events ──
        if path == "/api/events":
            q = queue.Queue(maxsize=100)
            _add_sse_client(q)
            self._sse_stream(q)
            return

        # ── Health ──
        if path == "/api/health":
            self._json_response({
                "status": "ok",
                "agent": "Dulus",
                "mode": "proactive",
                "version": "2026.04.26"
            })
            return

        # ── Tasks ──
        if path == "/api/tasks":
            self._json_response(load_tasks())
            return

        # ── Context ──
        if path == "/api/context":
            self._json_response(build_context())
            return
        if path == "/api/context/compact":
            self._text_response(get_compact_context())
            return
        if path == "/api/smart-context":
            self._json_response(build_smart_context())
            return

        # ── Agents ──
        if path == "/api/agents":
            ctx = build_context()
            self._json_response(ctx.get("agents", []))
            return

        # ── Personas ──
        if path == "/api/personas":
            try:
                self._json_response({
                    "personas": get_all_personas(),
                    "active": get_active_persona(),
                })
            except Exception as e:
                self._error(f"Personas error: {e}", 500)
            return
        if path == "/api/personas/active":
            self._json_response(get_active_persona())
            return
        if path.startswith("/api/personas/") and len(path.split("/")) == 4:
            pid = path.split("/")[-1]
            try:
                p = get_persona(pid)
                if p:
                    self._json_response(p)
                else:
                    self._error("Persona not found", 404)
            except Exception as e:
                self._error(f"Personas error: {e}", 500)
            return

        # ── MemPalace ──
        if path == "/api/mempalace":
            try:
                from backend.mempalace_bridge import load_cache, get_mempalace_compact_text
                data = load_cache()
                data["compact_text"] = get_mempalace_compact_text()
                self._json_response(data)
            except Exception as e:
                self._error(f"MemPalace error: {e}", 500)
            return

        # ── Themes ──
        if path == "/api/themes":
            try:
                from gui.theme_pack import list_themes
                self._json_response({"themes": list_themes()})
            except Exception as e:
                self._error(f"Theme pack unavailable: {e}", 500)
            return
        if path.startswith("/api/themes/") and path.endswith("/css"):
            theme_name = path.split("/")[-2]
            try:
                from gui.theme_pack import generate_css_variables
                css = generate_css_variables(theme_name)
                self._text_response(css, content_type="text/css; charset=utf-8")
            except Exception as e:
                self._error(f"Theme error: {e}", 500)
            return

        # ── Plugins ──
        if path == "/api/plugins":
            try:
                load_all_plugins()
                self._json_response({"plugins": get_plugin_info()})
            except Exception as e:
                self._error(f"Plugin error: {e}", 500)
            return
        if path == "/api/plugins/status":
            try:
                self._json_response(watcher_status())
            except Exception as e:
                self._error(f"Plugin status error: {e}", 500)
            return

        # ── Marketplace ──
        if path == "/api/marketplace":
            try:
                from backend.marketplace import load_registry, search_plugins
                q = query.get("q", [""])[0]
                tag = query.get("tag", [""])[0]
                self._json_response({"plugins": search_plugins(q, tag)})
            except Exception as e:
                self._error(f"Marketplace error: {e}", 500)
            return
        if path == "/api/marketplace/stats":
            try:
                from backend.marketplace import get_stats
                self._json_response(get_stats())
            except Exception as e:
                self._error(f"Marketplace error: {e}", 500)
            return

        # ── Static files from dashboard ──
        if path == "/" or path == "/index.html":
            target = DASHBOARD_DIR / "index.html"
        else:
            target = DASHBOARD_DIR / path.lstrip("/")

        if target.exists() and target.is_file():
            self.send_response(200)
            ctype = "text/html"
            if path.endswith(".css"):
                ctype = "text/css"
            elif path.endswith(".js"):
                ctype = "application/javascript"
            elif path.endswith(".json"):
                ctype = "application/json"
            self.send_header("Content-Type", ctype)
            self.end_headers()
            with open(target, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(404)

    def _do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except Exception:
            return self._error("Invalid JSON")

        # ── Tasks ──
            task = create_task(data)
            broadcast_event("task_created", task)
            return self._json_response(task, 201)
        if path.startswith("/api/tasks/"):
            tid = path.split("/")[-1]
            task = update_task(tid, data)
            if task:
                broadcast_event("task_updated", task)
                return self._json_response(task)
            return self._error("Task not found", 404)

        # ── Marketplace Install / Uninstall ──
        if path == "/api/marketplace/install":
            plugin_id = data.get("id")
            if not plugin_id:
                return self._error("Missing plugin id")
            try:
                from backend.marketplace import install_plugin
                result = install_plugin(plugin_id)
                if result:
                    broadcast_event("marketplace_install", result)
                    return self._json_response({"installed": True, "plugin": result})
                return self._error("Plugin not found", 404)
            except Exception as e:
                return self._error(str(e), 500)
        if path == "/api/marketplace/uninstall":
            plugin_id = data.get("id")
            if not plugin_id:
                return self._error("Missing plugin id")
            try:
                from backend.marketplace import uninstall_plugin
                result = uninstall_plugin(plugin_id)
                if result:
                    broadcast_event("marketplace_uninstall", result)
                    return self._json_response({"uninstalled": True, "plugin": result})
                return self._error("Plugin not found", 404)
            except Exception as e:
                return self._error(str(e), 500)

        # ── Plugins ──
        if path == "/api/plugins/reload":
            name = data.get("name")
            try:
                if name:
                    from backend.plugins import PLUGINS_DIR
                    result = reload_plugin(PLUGINS_DIR / f"{name}.py")
                    clean_result = {"name": result.get("name", name), "version": result.get("version", "?"), "status": result.get("status", "?")}
                    broadcast_event("plugin_reloaded", clean_result)
                    return self._json_response(clean_result)
                else:
                    load_all_plugins()
                    info = get_plugin_info()
                    broadcast_event("plugins_reloaded", {"count": len(info)})
                    return self._json_response({"plugins": info})
            except Exception as e:
                return self._error(str(e), 500)

        # ── Personas ──
        if path == "/api/personas/activate":
            pid = data.get("id")
            if not pid:
                return self._error("Missing persona id")
            try:
                result = set_active_persona(pid)
                if result:
                    broadcast_event("persona_activated", result)
                    return self._json_response({"activated": True, "persona": result})
                return self._error("Persona not found", 404)
            except Exception as e:
                return self._error(str(e), 500)
        if path == "/api/personas":
            try:
                result = create_persona(data)
                broadcast_event("persona_created", result)
                return self._json_response(result, 201)
            except Exception as e:
                return self._error(str(e), 500)

        self._error("Not found", 404)

    def do_GET(self):
        self._safe_handle(self._do_GET)

    def do_POST(self):
        self._safe_handle(self._do_POST)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(port: int = 8000):
    # Start plugin hot-reload watcher with SSE broadcast
    started = start_watcher(broadcast_event)
    if started:
        print("[DULUS] Plugin hot-reload watcher started")
    server = HTTPServer(("", port), DulusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[DULUS] Server running at http://localhost:{port}")
    print(f"   Dashboard:   http://localhost:{port}/")
    print(f"   API Tasks:   http://localhost:{port}/api/tasks")
    print(f"   Context:     http://localhost:{port}/api/context")
    print(f"   Smart Ctx:   http://localhost:{port}/api/smart-context")
    print(f"   Agents:      http://localhost:{port}/api/agents")
    print(f"   Personas:    http://localhost:{port}/api/personas")
    print(f"   Themes:      http://localhost:{port}/api/themes")
    print(f"   Plugins:     http://localhost:{port}/api/plugins")
    print(f"   Marketplace: http://localhost:{port}/api/marketplace")
    print(f"   MemPalace:   http://localhost:{port}/api/mempalace")
    print(f"   SSE Events:  http://localhost:{port}/api/events")
    print("   Press Ctrl+C to stop")
    try:
        thread.join()
    except KeyboardInterrupt:
        print("\n[DULUS] Shutting down...")
        stop_watcher()
        server.shutdown()


if __name__ == "__main__":
    run_server()
