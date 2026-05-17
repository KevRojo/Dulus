#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DULUS — Telegram Multi-User Dashboard Bridge                                ║
║  Autor: KevRojo + Dulus                                                      ║
║                                                                              ║
║  Extiende el bridge de Telegram para soportar múltiples usuarios con         ║
║  aprobación manual por un admin.                                             ║
║                                                                              ║
║  Flujo:                                                                      ║
║    1. Usuario nuevo escribe al bot → cola PENDING                            ║
║    2. Admin recibe notificación con datos del usuario                        ║
║    3. Admin aprueba/rechaza vía web dashboard o comandos Telegram            ║
║    4. Aprobados interactúan con Dulus normalmente                            ║
║    5. Rechazados son ignorados silenciosamente                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any

# ── Config paths ─────────────────────────────────────────────────────────────
DASHBOARD_DIR = Path.home() / ".dulus" / "telegram_dashboard"
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

USERS_FILE = DASHBOARD_DIR / "users.json"
MESSAGES_FILE = DASHBOARD_DIR / "messages.json"
LOG_FILE = DASHBOARD_DIR / "dashboard.log"

# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class UserRecord:
    chat_id: int
    username: str
    first_name: str
    last_name: str
    status: str  # "pending", "approved", "rejected", "banned"
    requested_at: str
    approved_at: Optional[str] = None
    approved_by: Optional[int] = None  # admin chat_id
    message_count: int = 0
    last_message_at: Optional[str] = None
    notes: str = ""  # admin notes

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> UserRecord:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def display_name(self) -> str:
        name = self.first_name or ""
        if self.last_name:
            name += f" {self.last_name}"
        if self.username:
            name += f" (@{self.username})"
        return name.strip() or f"User #{self.chat_id}"


@dataclass
class QueuedMessage:
    id: str
    chat_id: int
    text: str
    photo_base64: Optional[str] = None
    caption: Optional[str] = None
    received_at: str = ""
    processed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> QueuedMessage:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Storage ──────────────────────────────────────────────────────────────────

class DashboardStore:
    """Thread-safe JSON persistence for users and messages."""

    def __init__(self):
        self._users: Dict[int, UserRecord] = {}
        self._messages: Dict[str, QueuedMessage] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._users[int(k)] = UserRecord.from_dict(v)
            except Exception:
                pass
        if MESSAGES_FILE.exists():
            try:
                with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._messages[k] = QueuedMessage.from_dict(v)
            except Exception:
                pass

    def _save_users(self):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v.to_dict() for k, v in self._users.items()}, f, indent=2, ensure_ascii=False)

    def _save_messages(self):
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in self._messages.items()}, f, indent=2, ensure_ascii=False)

    # ── Users ─────────────────────────────────────────────────────────────────

    def get_user(self, chat_id: int) -> Optional[UserRecord]:
        with self._lock:
            return self._users.get(chat_id)

    def get_all_users(self) -> List[UserRecord]:
        with self._lock:
            return list(self._users.values())

    def get_pending(self) -> List[UserRecord]:
        with self._lock:
            return [u for u in self._users.values() if u.status == "pending"]

    def get_approved(self) -> List[UserRecord]:
        with self._lock:
            return [u for u in self._users.values() if u.status == "approved"]

    def add_or_update_user(self, user: UserRecord):
        with self._lock:
            self._users[user.chat_id] = user
            self._save_users()

    def approve_user(self, chat_id: int, admin_chat_id: int) -> bool:
        with self._lock:
            u = self._users.get(chat_id)
            if not u:
                return False
            u.status = "approved"
            u.approved_at = datetime.now().isoformat()
            u.approved_by = admin_chat_id
            self._save_users()
            return True

    def reject_user(self, chat_id: int, admin_chat_id: int) -> bool:
        with self._lock:
            u = self._users.get(chat_id)
            if not u:
                return False
            u.status = "rejected"
            u.approved_at = datetime.now().isoformat()
            u.approved_by = admin_chat_id
            self._save_users()
            return True

    def ban_user(self, chat_id: int) -> bool:
        with self._lock:
            u = self._users.get(chat_id)
            if not u:
                return False
            u.status = "banned"
            self._save_users()
            return True

    def increment_message_count(self, chat_id: int):
        with self._lock:
            u = self._users.get(chat_id)
            if u:
                u.message_count += 1
                u.last_message_at = datetime.now().isoformat()
                self._save_users()

    # ── Messages ──────────────────────────────────────────────────────────────

    def queue_message(self, msg: QueuedMessage):
        with self._lock:
            self._messages[msg.id] = msg
            self._save_messages()

    def get_pending_messages(self, chat_id: Optional[int] = None) -> List[QueuedMessage]:
        with self._lock:
            msgs = [m for m in self._messages.values() if not m.processed]
            if chat_id is not None:
                msgs = [m for m in msgs if m.chat_id == chat_id]
            return msgs

    def mark_processed(self, msg_id: str):
        with self._lock:
            m = self._messages.get(msg_id)
            if m:
                m.processed = True
                self._save_messages()

    def clear_processed(self):
        with self._lock:
            self._messages = {k: v for k, v in self._messages.items() if not v.processed}
            self._save_messages()


# ── Telegram API helpers ─────────────────────────────────────────────────────

def tg_api(token: str, method: str, params: dict = None) -> Optional[dict]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def tg_send(token: str, chat_id: int, text: str, parse_mode: str = "Markdown"):
    MAX = 4000
    chunks = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    for chunk in chunks:
        result = tg_api(token, "sendMessage", {"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode})
        if not result or not result.get("ok"):
            tg_api(token, "sendMessage", {"chat_id": chat_id, "text": chunk})


def tg_typing(token: str, chat_id: int):
    tg_api(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})


# ── Dashboard Web Server ─────────────────────────────────────────────────────

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🦅 Dulus Telegram Dashboard</title>
<style>
  :root{--bg:#1e1e2e;--surface:#313244;--text:#cdd6f4;--sub:#6c7086;--green:#a6e3a1;--red:#f38ba8;--yellow:#f9e2af;--blue:#89b4fa;--mauve:#cba6f7;}
  *{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',system-ui,sans-serif}
  body{background:var(--bg);color:var(--text);min-height:100vh;padding:20px}
  h1{text-align:center;margin-bottom:10px;font-size:2rem}
  .subtitle{text-align:center;color:var(--sub);margin-bottom:30px}
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:30px}
  .stat-card{background:var(--surface);padding:20px;border-radius:12px;text-align:center}
  .stat-num{font-size:2.5rem;font-weight:bold}
  .stat-label{color:var(--sub);font-size:.9rem;margin-top:5px}
  .pending{background:rgba(249,226,175,.1);border:1px solid var(--yellow)}
  .approved{background:rgba(166,227,161,.1);border:1px solid var(--green)}
  .rejected{background:rgba(243,139,168,.1);border:1px solid var(--red)}
  .section{margin-bottom:40px}
  .section h2{margin-bottom:15px;display:flex;align-items:center;gap:10px}
  table{width:100%;border-collapse:collapse;background:var(--surface);border-radius:12px;overflow:hidden}
  th,td{padding:12px 15px;text-align:left}
  th{background:rgba(0,0,0,.2);color:var(--sub);font-weight:600;font-size:.85rem;text-transform:uppercase}
  tr{border-bottom:1px solid rgba(255,255,255,.05)}
  tr:hover{background:rgba(255,255,255,.03)}
  .btn{padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:.85rem;font-weight:600;transition:.2s}
  .btn-green{background:var(--green);color:#1e1e2e}
  .btn-red{background:var(--red);color:#1e1e2e}
  .btn-blue{background:var(--blue);color:#1e1e2e}
  .btn:hover{opacity:.85;transform:translateY(-1px)}
  .badge{padding:4px 10px;border-radius:20px;font-size:.75rem;font-weight:600;text-transform:uppercase}
  .badge-pending{background:var(--yellow);color:#1e1e2e}
  .badge-approved{background:var(--green);color:#1e1e2e}
  .badge-rejected{background:var(--red);color:#1e1e2e}
  .badge-banned{background:#45475a;color:#cdd6f4}
  .empty{text-align:center;padding:40px;color:var(--sub)}
  .refresh{position:fixed;top:20px;right:20px;background:var(--mauve);color:#1e1e2e;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600}
  .message-preview{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--sub);font-size:.85rem}
  @media(max-width:768px){table{font-size:.8rem}th,td{padding:8px}
    .stats{grid-template-columns:repeat(2,1fr)}h1{font-size:1.5rem}}
</style>
</head>
<body>
<a href="/" class="refresh">🔄 Refresh</a>
<h1>🦅 Dulus Telegram Dashboard</h1>
<p class="subtitle">Admin Panel — Gestiona quién puede hablar con Dulus</p>

<div class="stats">
  <div class="stat-card pending">
    <div class="stat-num" style="color:var(--yellow)">{{pending_count}}</div>
    <div class="stat-label">Pendientes</div>
  </div>
  <div class="stat-card approved">
    <div class="stat-num" style="color:var(--green)">{{approved_count}}</div>
    <div class="stat-label">Aprobados</div>
  </div>
  <div class="stat-card rejected">
    <div class="stat-num" style="color:var(--red)">{{rejected_count}}</div>
    <div class="stat-label">Rechazados</div>
  </div>
  <div class="stat-card">
    <div class="stat-num" style="color:var(--blue)">{{total_messages}}</div>
    <div class="stat-label">Mensajes hoy</div>
  </div>
</div>

<div class="section">
  <h2>⏳ Solicitudes Pendientes</h2>
  {{pending_table}}
</div>

<div class="section">
  <h2>✅ Usuarios Aprobados</h2>
  {{approved_table}}
</div>

<div class="section">
  <h2>📜 Todos los Usuarios</h2>
  {{all_table}}
</div>

<script>
function approve(id){fetch('/api/approve/'+id,{method:'POST'}).then(()=>location.reload())}
function reject(id){fetch('/api/reject/'+id,{method:'POST'}).then(()=>location.reload())}
function ban(id){if(confirm('¿Seguro que quieres banear a este usuario?'))fetch('/api/ban/'+id,{method:'POST'}).then(()=>location.reload())}
</script>
</body>
</html>
"""


def build_table(users: List[UserRecord], actions: bool = False) -> str:
    if not users:
        return '<div class="empty">No hay usuarios en esta categoría.</div>'

    rows = ""
    for u in users:
        badge_class = f"badge-{u.status}"
        action_btns = ""
        if actions:
            if u.status == "pending":
                action_btns = f'''
                <button class="btn btn-green" onclick="approve({u.chat_id})">✓ Aprobar</button>
                <button class="btn btn-red" onclick="reject({u.chat_id})">✗ Rechazar</button>
                '''
            elif u.status == "approved":
                action_btns = f'<button class="btn btn-red" onclick="ban({u.chat_id})">🚫 Banear</button>'
            else:
                action_btns = f'<button class="btn btn-green" onclick="approve({u.chat_id})">↩ Re-aprobar</button>'

        rows += f"""
        <tr>
          <td>{u.chat_id}</td>
          <td><strong>{u.display_name}</strong></td>
          <td><span class="badge {badge_class}">{u.status}</span></td>
          <td>{u.requested_at[:16] if u.requested_at else '-'}</td>
          <td>{u.message_count}</td>
          <td>{action_btns}</td>
        </tr>
        """

    return f"""
    <table>
      <thead>
        <tr><th>Chat ID</th><th>Usuario</th><th>Estado</th><th>Solicitó</th><th>Mensajes</th><th>Acciones</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


class DashboardServer:
    """Minimal HTTP dashboard using only stdlib (no Flask/FastAPI dep)."""

    def __init__(self, store: DashboardStore, host: str = "127.0.0.1", port: int = 9876):
        self.store = store
        self.host = host
        self.port = port
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        # Ping ourselves to unblock accept()
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, self.port))
            s.close()
        except Exception:
            pass

    def _serve(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import urllib.parse

        store = self.store
        stop_evt = self._stop

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Silencio

            def _json(self, status: int, data: dict):
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _html(self, status: int, html: str):
                body = html.encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _redirect(self, path: str = "/"):
                self.send_response(302)
                self.send_header("Location", path)
                self.end_headers()

            def do_GET(self):
                if stop_evt.is_set():
                    self.send_error(503)
                    return

                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path

                if path == "/":
                    pending = store.get_pending()
                    approved = store.get_approved()
                    all_users = store.get_all_users()
                    total_msgs = sum(u.message_count for u in all_users)

                    html = HTML_DASHBOARD
                    html = html.replace("{{pending_count}}", str(len(pending)))
                    html = html.replace("{{approved_count}}", str(len(approved)))
                    html = html.replace("{{rejected_count}}", str(len([u for u in all_users if u.status == "rejected"])))
                    html = html.replace("{{total_messages}}", str(total_msgs))
                    html = html.replace("{{pending_table}}", build_table(pending, actions=True))
                    html = html.replace("{{approved_table}}", build_table(approved, actions=False))
                    html = html.replace("{{all_table}}", build_table(all_users, actions=True))
                    self._html(200, html)

                elif path == "/api/stats":
                    all_users = store.get_all_users()
                    self._json(200, {
                        "pending": len(store.get_pending()),
                        "approved": len(store.get_approved()),
                        "rejected": len([u for u in all_users if u.status == "rejected"]),
                        "banned": len([u for u in all_users if u.status == "banned"]),
                        "total_users": len(all_users),
                        "total_messages": sum(u.message_count for u in all_users),
                    })

                elif path == "/api/users":
                    self._json(200, {"users": [u.to_dict() for u in store.get_all_users()]})

                elif path == "/api/pending":
                    self._json(200, {"users": [u.to_dict() for u in store.get_pending()]})

                else:
                    self.send_error(404)

            def do_POST(self):
                if stop_evt.is_set():
                    self.send_error(503)
                    return

                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path

                # /api/approve/<chat_id>
                m = re.match(r"^/api/approve/(\d+)$", path)
                if m:
                    cid = int(m.group(1))
                    if store.approve_user(cid, 0):
                        self._json(200, {"ok": True, "chat_id": cid, "status": "approved"})
                    else:
                        self._json(404, {"ok": False, "error": "User not found"})
                    return

                # /api/reject/<chat_id>
                m = re.match(r"^/api/reject/(\d+)$", path)
                if m:
                    cid = int(m.group(1))
                    if store.reject_user(cid, 0):
                        self._json(200, {"ok": True, "chat_id": cid, "status": "rejected"})
                    else:
                        self._json(404, {"ok": False, "error": "User not found"})
                    return

                # /api/ban/<chat_id>
                m = re.match(r"^/api/ban/(\d+)$", path)
                if m:
                    cid = int(m.group(1))
                    if store.ban_user(cid):
                        self._json(200, {"ok": True, "chat_id": cid, "status": "banned"})
                    else:
                        self._json(404, {"ok": False, "error": "User not found"})
                    return

                self.send_error(404)

        server = HTTPServer((self.host, self.port), Handler)
        server.timeout = 1.0
        while not stop_evt.is_set():
            try:
                server.handle_request()
            except Exception:
                pass
        server.server_close()


# ── Main Bridge Class ────────────────────────────────────────────────────────

class TelegramDashboardBridge:
    """
    Drop-in replacement/extension for the standard Dulus Telegram bridge.

    Usage:
        bridge = TelegramDashboardBridge(token, admin_chat_id, config)
        bridge.start()          # starts polling + web dashboard
        bridge.stop()           # stops everything

    Admin commands (via Telegram):
        /pending        — lista usuarios pendientes
        /approve <id>   — aprueba un usuario
        /reject <id>    — rechaza un usuario
        /ban <id>       — banea un usuario
        /users          — lista todos los usuarios
        /stats          — estadísticas rápidas
    """

    def __init__(
        self,
        token: str,
        admin_chat_id: int,
        config: dict,
        dashboard_host: str = "127.0.0.1",
        dashboard_port: int = 9876,
        run_query_callback: Optional[Callable[[str, int, str], None]] = None,
    ):
        self.token = token
        self.admin_chat_id = admin_chat_id
        self.config = config
        self.store = DashboardStore()
        self.dashboard = DashboardServer(self.store, dashboard_host, dashboard_port)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._run_query = run_query_callback

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.dashboard.host}:{self.dashboard.port}"

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.dashboard.start()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.dashboard.stop()

    def _poll_loop(self):
        """Main long-polling loop with multi-user approval flow."""
        token = self.token
        admin_id = self.admin_chat_id
        store = self.store
        config = self.config

        # Flush old messages
        flush = tg_api(token, "getUpdates", {"offset": -1, "timeout": 0})
        offset = (flush["result"][-1]["update_id"] + 1) if (flush and flush.get("ok") and flush.get("result")) else 0

        # Notify admin that dashboard is live
        tg_send(token, admin_id,
            f"🦅 *Dulus Dashboard activo*\n\n"
            f"🔗 Panel: `{self.dashboard_url}`\n"
            f"📝 Comandos: /pending /approve /reject /ban /users /stats\n\n"
            f"Los usuarios nuevos quedarán en cola hasta que los apruebes."
        )

        while not self._stop.is_set():
            try:
                result = tg_api(token, "getUpdates", {
                    "offset": offset,
                    "timeout": 30,
                    "allowed_updates": ["message"]
                })
                if not result or not result.get("ok"):
                    self._stop.wait(5)
                    continue

                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    if not msg:
                        continue

                    chat = msg.get("chat", {})
                    chat_id = chat.get("id")
                    text = msg.get("text", "").strip()
                    from_user = msg.get("from", {})

                    # ── Admin commands ──────────────────────────────────────
                    if chat_id == admin_id:
                        handled = self._handle_admin_command(text, chat_id)
                        if handled:
                            continue

                    # ── Lookup user ─────────────────────────────────────────
                    user = store.get_user(chat_id)

                    # If never seen, register as pending
                    if user is None:
                        user = UserRecord(
                            chat_id=chat_id,
                            username=from_user.get("username", ""),
                            first_name=from_user.get("first_name", ""),
                            last_name=from_user.get("last_name", ""),
                            status="pending",
                            requested_at=datetime.now().isoformat(),
                        )
                        store.add_or_update_user(user)

                        # Notify admin about new request
                        name = user.display_name
                        tg_send(token, admin_id,
                            f"⏳ *Nueva solicitud de acceso*\n\n"
                            f"👤 {name}\n"
                            f"🆔 `{chat_id}`\n"
                            f"📝 Mensaje: `{text[:200]}`\n\n"
                            f"Usa `/approve {chat_id}` o el panel web."
                        )

                        # Tell user they're waiting
                        tg_send(token, chat_id,
                            "⏳ *Solicitud enviada*\n\n"
                            "Tu mensaje está pendiente de aprobación por el administrador. "
                            "Te notificaré cuando seas aprobado."
                        )
                        continue

                    # ── Handle by status ────────────────────────────────────
                    if user.status == "pending":
                        # Queue the message for later processing after approval
                        qmsg = QueuedMessage(
                            id=f"{chat_id}_{int(time.time()*1000)}",
                            chat_id=chat_id,
                            text=text,
                            received_at=datetime.now().isoformat(),
                        )
                        store.queue_message(qmsg)
                        tg_send(token, chat_id,
                            "⏳ Aún estás pendiente de aprobación. "
                            "Tu mensaje será procesado cuando el administrador te apruebe."
                        )
                        continue

                    if user.status in ("rejected", "banned"):
                        # Silently ignore
                        continue

                    # ── Approved user — process message ─────────────────────
                    if user.status == "approved":
                        store.increment_message_count(chat_id)
                        config["_active_tg_chat_id"] = chat_id
                        self._process_user_message(msg, chat_id)
                        continue

            except Exception as e:
                # Log error but keep loop alive
                try:
                    with open(LOG_FILE, "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now().isoformat()}] POLL ERROR: {e}\n")
                except Exception:
                    pass
                self._stop.wait(5)

    def _handle_admin_command(self, text: str, admin_chat_id: int) -> bool:
        """Returns True if the text was an admin command and was handled."""
        token = self.token
        store = self.store
        cmd = text.lower().split()
        if not cmd:
            return False

        if cmd[0] == "/pending":
            pending = store.get_pending()
            if not pending:
                tg_send(token, admin_chat_id, "✅ No hay solicitudes pendientes.")
            else:
                lines = ["⏳ *Solicitudes pendientes:*\n"]
                for u in pending:
                    lines.append(f"• `{u.chat_id}` — {u.display_name}")
                tg_send(token, admin_chat_id, "\n".join(lines))
            return True

        if cmd[0] == "/users":
            users = store.get_all_users()
            lines = [f"📋 *Total usuarios: {len(users)}*\n"]
            for u in users:
                lines.append(f"• `{u.chat_id}` — {u.display_name} — *{u.status}* — {u.message_count} msgs")
            tg_send(token, admin_chat_id, "\n".join(lines[:50]))  # truncate if huge
            return True

        if cmd[0] == "/stats":
            users = store.get_all_users()
            pending = len(store.get_pending())
            approved = len(store.get_approved())
            rejected = len([u for u in users if u.status == "rejected"])
            banned = len([u for u in users if u.status == "banned"])
            total_msgs = sum(u.message_count for u in users)
            tg_send(token, admin_chat_id,
                f"📊 *Estadísticas*\n\n"
                f"⏳ Pendientes: {pending}\n"
                f"✅ Aprobados: {approved}\n"
                f"✗ Rechazados: {rejected}\n"
                f"🚫 Baneados: {banned}\n"
                f"💬 Total mensajes: {total_msgs}\n\n"
                f"🔗 {self.dashboard_url}"
            )
            return True

        if cmd[0] in ("/approve", "/reject", "/ban") and len(cmd) >= 2:
            try:
                target_id = int(cmd[1])
            except ValueError:
                tg_send(token, admin_chat_id, "⚠️ Usa: `/approve <chat_id>`")
                return True

            if cmd[0] == "/approve":
                if store.approve_user(target_id, admin_chat_id):
                    tg_send(token, admin_chat_id, f"✅ Usuario `{target_id}` aprobado.")
                    tg_send(token, target_id,
                        "🎉 *¡Has sido aprobado!*\n\n"
                        "Ahora puedes hablar con Dulus. Escribe lo que necesites. 🦅"
                    )
                    # Process any queued messages
                    self._flush_queued_messages(target_id)
                else:
                    tg_send(token, admin_chat_id, f"⚠️ Usuario `{target_id}` no encontrado.")
                return True

            if cmd[0] == "/reject":
                if store.reject_user(target_id, admin_chat_id):
                    tg_send(token, admin_chat_id, f"✗ Usuario `{target_id}` rechazado.")
                    tg_send(token, target_id,
                        "❌ Tu solicitud de acceso ha sido rechazada."
                    )
                else:
                    tg_send(token, admin_chat_id, f"⚠️ Usuario `{target_id}` no encontrado.")
                return True

            if cmd[0] == "/ban":
                if store.ban_user(target_id):
                    tg_send(token, admin_chat_id, f"🚫 Usuario `{target_id}` baneado.")
                else:
                    tg_send(token, admin_chat_id, f"⚠️ Usuario `{target_id}` no encontrado.")
                return True

        return False

    def _process_user_message(self, msg: dict, chat_id: int):
        """Forward an approved user's message to Dulus for processing."""
        text = msg.get("text", "").strip()
        photo_list = msg.get("photo")

        # If there's a photo, download and base64 it
        if photo_list:
            caption = msg.get("caption", "").strip() or "What do you see in this image? Describe it in detail."
            file_id = photo_list[-1]["file_id"]
            try:
                file_info = tg_api(self.token, "getFile", {"file_id": file_id})
                if file_info and file_info.get("ok"):
                    file_path = file_info["result"]["file_path"]
                    url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                    with urllib.request.urlopen(url, timeout=60) as resp:
                        import base64
                        b64 = base64.b64encode(resp.read()).decode()
                    # Build image markdown for Dulus
                    ext = Path(file_path).suffix.lstrip(".") or "jpg"
                    text = f"![image](data:image/{ext};base64,{b64})\n\n{caption}"
            except Exception as e:
                tg_send(self.token, chat_id, f"⚠️ Error procesando imagen: {e}")
                return

        if not text:
            return

        # Invoke Dulus callback
        if self._run_query:
            # Typing indicator
            typing_stop = threading.Event()
            typing_thread = threading.Thread(
                target=self._typing_worker, args=(chat_id, typing_stop), daemon=True
            )
            typing_thread.start()

            def on_complete(response: str):
                typing_stop.set()
                typing_thread.join(timeout=1)
                if not response:
                    response = "⚠️ No response from Dulus."
                MAX_TG = 4000
                if len(response) > MAX_TG:
                    response = response[:MAX_TG] + "\n\n…truncated"
                tg_send(self.token, chat_id, response)

            self._run_query(text, chat_id, on_complete)
        else:
            # Fallback: just echo that we received it
            tg_send(self.token, chat_id, f"📨 Recibido: `{text[:100]}`\n\n(No hay callback configurado para procesar)")

    def _typing_worker(self, chat_id: int, stop_event: threading.Event):
        while not stop_event.is_set():
            tg_api(self.token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
            stop_event.wait(4)

    def _flush_queued_messages(self, chat_id: int):
        """Process any messages that were queued while user was pending."""
        pending_msgs = self.store.get_pending_messages(chat_id)
        if pending_msgs:
            tg_send(self.token, chat_id, f"📨 Procesando {len(pending_msgs)} mensaje(s) que enviaste mientras esperabas…")
            for msg in pending_msgs:
                self.store.mark_processed(msg.id)
                # Reconstruct a fake msg dict
                fake_msg = {"text": msg.text, "chat": {"id": chat_id}}
                self._process_user_message(fake_msg, chat_id)


# ── Integration helpers ──────────────────────────────────────────────────────

def start_dashboard_bridge(
    token: str,
    admin_chat_id: int,
    config: dict,
    dashboard_host: str = "127.0.0.1",
    dashboard_port: int = 9876,
    run_query_callback: Optional[Callable[[str, int, Callable[[str], None]], None]] = None,
) -> TelegramDashboardBridge:
    """
    Convenience factory. Starts the bridge and returns the instance.

    Example integration in dulus.py:

        from telegram_dashboard import start_dashboard_bridge

        # Replace the standard _tg_poll_loop with:
        bridge = start_dashboard_bridge(
            token=token,
            admin_chat_id=admin_chat_id,
            config=config,
            run_query_callback=lambda text, cid, cb: config["_run_query_callback"](text, cid, cb),
        )
    """
    bridge = TelegramDashboardBridge(
        token=token,
        admin_chat_id=admin_chat_id,
        config=config,
        dashboard_host=dashboard_host,
        dashboard_port=dashboard_port,
        run_query_callback=run_query_callback,
    )
    bridge.start()
    return bridge


# ── CLI standalone (for testing) ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Dulus Telegram Dashboard Bridge")
    parser.add_argument("--token", required=True, help="Telegram Bot API token")
    parser.add_argument("--admin", type=int, required=True, help="Admin chat ID")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard host")
    parser.add_argument("--port", type=int, default=9876, help="Dashboard port")
    args = parser.parse_args()

    print(f"🦅 Dulus Telegram Dashboard")
    print(f"   Token:   {args.token[:20]}...")
    print(f"   Admin:   {args.admin}")
    print(f"   Panel:   http://{args.host}:{args.port}")
    print(f"   Data:    {DASHBOARD_DIR}")
    print(f"\n   Ctrl+C para detener\n")

    # Dummy callback for testing
    def dummy_callback(text: str, chat_id: int, on_complete: Callable[[str], None]):
        print(f"   [DULUS] Message from {chat_id}: {text[:60]}...")
        import threading
        def respond():
            time.sleep(2)
            on_complete(f"🤖 Eco de Dulus: recibí tu mensaje: '{text[:100]}'")
        threading.Thread(target=respond, daemon=True).start()

    bridge = start_dashboard_bridge(
        token=args.token,
        admin_chat_id=args.admin,
        config={},
        dashboard_host=args.host,
        dashboard_port=args.port,
        run_query_callback=dummy_callback,
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n   Deteniendo…")
        bridge.stop()
