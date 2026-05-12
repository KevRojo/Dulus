"""Dulus WebChat — in-process mirror of the terminal agent + Roundtable mode.
"""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
import webbrowser
import sys
from pathlib import Path
from typing import Generator

from backend.context import build_context, build_smart_context, get_compact_context
from backend.personas import create_persona, get_active_persona, get_all_personas, get_persona, load_personas, set_active_persona, update_persona
from backend.plugins import load_all_plugins, get_plugin_info, start_watcher, stop_watcher, watcher_status, reload_plugin, unload_plugin
from task import create_task as task_create, list_tasks as task_list, update_task as task_update, get_task as task_get, delete_task as task_delete
from backend.marketplace import load_registry, search_plugins, get_stats as marketplace_stats, install_plugin, uninstall_plugin
from gui.session_utils import scan_sessions, save_session, delete_session as _delete_session_disk

def _resolve_dashboard_dir() -> Path:
    """Find docs/dashboard whether running from source or installed package."""
    # 1. Try source layout (development)
    src = Path(__file__).parent / "docs" / "dashboard"
    if src.exists():
        return src
    # 2. Try installed package (docs is now a package)
    try:
        import docs as _docs_pkg
        pkg = Path(_docs_pkg.__file__).parent / "dashboard"
        if pkg.exists():
            return pkg
    except Exception:
        pass
    # 3. Fallback — will 404 gracefully
    return src

DASHBOARD_DIR = _resolve_dashboard_dir()

from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory

from agent import (
    run as agent_run,
    AgentState,
    TextChunk,
    ThinkingChunk,
    ToolStart,
    ToolEnd,
    TurnDone,
    PermissionRequest,
)
from context import build_system_prompt
from common import sanitize_text

# Ensure tools are registered
import tools as _tools_init
import memory.tools as _mem_tools_init
import multi_agent.tools as _ma_tools_init
import skill.tools as _sk_tools_init
import dulus_mcp.tools as _mcp_tools_init
import task.tools as _task_tools_init

try:
    import tmux_tools as _tmux_tools_init
except Exception:
    pass

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

# ── shared refs ────────────────────────────────────────────────────────────
STATE: AgentState | None = None
CONFIG: dict | None = None
_LOCK = threading.Lock()
_PENDING_PERMISSIONS: dict[str, tuple[PermissionRequest, threading.Event]] = {}

# Session context deferment
_PENDING_HISTORY: list[dict] = []
_PENDING_SESSION_ID: str | None = None

_SERVER_THREAD: threading.Thread | None = None
_SERVER_PORT: int = 5000
_WERKZEUG_SERVER = None

# ── roundtable state ───────────────────────────────────────────────────────
class RoundtableAgent:
    def __init__(self, agent_id: str, model: str):
        self.id = agent_id
        self.model = model
        self.state = AgentState()


ROUNDTABLE_AGENTS: list[RoundtableAgent] = []
ROUNDTABLE_HISTORY: list[tuple[str, str]] = []  # (author_id, text) global log
ROUNDTABLE_LOCK = threading.Lock()

# Per-agent cancellation tokens for roundtable
_AGENT_STOP_EVENTS: dict[str, threading.Event] = {}
_STOP_EVENTS_LOCK = threading.Lock()


def _ensure_plugin_tools() -> None:
    try:
        from plugin.loader import register_plugin_tools
        register_plugin_tools()
    except Exception:
        pass


_ANSI_RE = None


def _strip_ansi(text: str) -> str:
    global _ANSI_RE
    if _ANSI_RE is None:
        import re
        _ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
    return _ANSI_RE.sub('', text)


def _inject_mempalace(user_input: str, config: dict) -> str:
    """Inject relevant memories from MemPalace into the user message.
    Mirrors the logic in dulus.py REPL for consistent behavior.
    """
    if not config.get("mem_palace", True):
        return user_input
    if not user_input or len(user_input.strip()) < 12:
        return user_input
    _trivial = {"hola", "klk", "gracias", "ok", "si", "no", "dale",
                "exit", "quit", "help", "thanks", "bien"}
    _first = user_input.strip().lower().split()[0].strip(".,!?;:")
    if _first in _trivial:
        return user_input
    try:
        _q = user_input.strip()[:200]
        _raw_hits = []
        # Primary: query the real MemPalace (~/.mempalace/palace)
        try:
            from mempalace.searcher import search_memories as _mp_search
            from mempalace.config import MempalaceConfig as _MPCfg
            _palace = _MPCfg().palace_path
            _res = _mp_search(_q, _palace, n_results=3)
            for _hit in (_res or {}).get("results", []):
                _meta = _hit.get("metadata") or {}
                _src = _meta.get("source_file") or _meta.get("name") or "palace"
                _name = str(_src).rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
                _vec = max(0.0, 1.0 - float(_hit.get("distance", 1.0)))
                _bm = float(_hit.get("bm25_score", 0.0))
                _raw_hits.append({
                    "name": _name,
                    "description": _meta.get("wing") or _meta.get("room") or "",
                    "content": _hit.get("text", ""),
                    "keyword_score": max(_vec, _bm),
                })
        except Exception:
            pass
        # Fallback: Dulus's local memory dir
        if not _raw_hits:
            from memory import find_relevant_memories
            _raw_hits = find_relevant_memories(_q, max_results=3)
        _MIN_SCORE = 0.15
        _kept = [h for h in _raw_hits if float(h.get("keyword_score", 0.0)) >= _MIN_SCORE]
        # Dedup against session cache
        import hashlib as _hashlib
        def _mp_dedup_key(h):
            content = (h.get("content") or "").strip()[:240]
            return _hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()[:12]
        _seen = config.setdefault("_mp_injected_keys", set())
        _this_turn = set()
        _filtered = []
        for _h in _kept:
            _k = _mp_dedup_key(_h)
            if _k in _seen or _k in _this_turn:
                continue
            _this_turn.add(_k)
            _filtered.append(_h)
        _kept = _filtered
        if not _kept:
            return user_input
        _BODY_BUDGET = 1800
        _per_hit = max(300, _BODY_BUDGET // len(_kept))
        _parts = []
        for _i, _h in enumerate(_kept, 1):
            _name = _h.get("name", f"hit_{_i}")
            _desc = _h.get("description", "")
            _body = _h.get("content", "").strip()
            _snip = _body[:_per_hit] + ("..." if len(_body) > _per_hit else "")
            if _desc:
                _parts.append(f"### {_name}\n_{_desc}_\n{_snip}")
            else:
                _parts.append(f"### {_name}\n{_snip}")
        _hits_str = "\n\n".join(_parts)
        if len(_hits_str) > 2000:
            _hits_str = _hits_str[:2000] + "\n[...truncated]"
        _inject = (
            "[MemPalace — relevant memories pre-loaded for this turn. "
            "Do NOT re-query unless the user explicitly asks for more. "
            "The answer to the user's question is very likely already "
            "below — read it BEFORE reaching for any tool.]\n\n"
            + _hits_str
        )
        # Mark these as injected so we don't repeat them next turn
        for _h in _kept:
            _seen.add(_mp_dedup_key(_h))
        return _inject + "\n\n---\n\n[USER MESSAGE]\n" + user_input
    except Exception:
        return user_input


def _run_slash_command(cmd_line: str) -> tuple[str, str | None]:
    """Run a slash command through the REPL's registered handler,
    capturing stdout. Mirrors the Telegram bridge behavior
    (dulus.py:_handle_slash_from_telegram).

    Returns (output_text, assistant_reply_or_None).
    `assistant_reply` is set when the slash triggered a model query
    (cmd_type == "query") so the caller can stream it as a separate chunk.
    """
    import io
    if CONFIG is None:
        return ("[webchat] server not initialized", None)
    slash_cb = CONFIG.get("_handle_slash_callback")
    if not slash_cb:
        return (
            f"[webchat] slash commands unavailable — REPL not active.\n"
            f"Command was: {cmd_line}",
            None,
        )

    old_stdout = sys.stdout
    buf = io.StringIO()
    sys.stdout = buf
    try:
        try:
            cmd_type = slash_cb(cmd_line)
        except Exception as e:
            return (f"⚠ Error: {type(e).__name__}: {e}", None)
    finally:
        sys.stdout = old_stdout

    captured = _strip_ansi(buf.getvalue()).strip()
    if not captured and cmd_type == "simple":
        cmd_name = cmd_line.strip().split()[0]
        captured = f"✅ {cmd_name} executed."

    assistant_reply: str | None = None
    if cmd_type == "query" and STATE is not None and STATE.messages:
        for m in reversed(STATE.messages):
            if m.get("role") == "assistant":
                content = m.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block["text"])
                        elif isinstance(block, str):
                            parts.append(block)
                    content = "\n".join(parts)
                if content:
                    assistant_reply = content
                break

    return (captured, assistant_reply)


def _run_agent_mirror(user_message: str) -> Generator:
    """Run the agent loop with shared state/config, yielding all events."""
    _ensure_plugin_tools()
    if STATE is None or CONFIG is None:
        raise RuntimeError("webchat server not initialized")

    cfg = CONFIG
    state = STATE
    user_input = sanitize_text(user_message)

    _skill_body = cfg.pop("_skill_inject", "")
    if _skill_body:
        user_input = (
            "[SKILL CONTEXT — follow these instructions for this turn]\n\n"
            + _skill_body
            + "\n\n---\n\n[USER MESSAGE]\n"
            + user_input
        )

    user_input = _inject_mempalace(user_input, cfg)

    system_prompt = build_system_prompt(cfg)
    cfg.pop("_in_telegram_turn", None)
    cfg["_last_interaction_time"] = time.time()

    # ── Handle deferred loading ───────────────────────────────────────
    global _PENDING_HISTORY, _PENDING_SESSION_ID
    if _PENDING_HISTORY:
        with _LOCK:
            state.messages.clear()
            for m in _PENDING_HISTORY:
                state.messages.append(m)
            cfg["_session_id"] = _PENDING_SESSION_ID
            _PENDING_HISTORY = []
            _PENDING_SESSION_ID = None

    # track tool calls in this turn to group them if verbose is OFF
    _turn_tools = []
    _is_verbose = cfg.get("verbose", False)

    for event in agent_run(user_input, state, cfg, system_prompt):
        if not _is_verbose and isinstance(event, (ToolStart, ToolEnd)):
            _turn_tools.append(event)
            # If start, we might want to yield a minimal 'working' sign
            if isinstance(event, ToolStart):
                yield ToolStart(name="working...", inputs={})
            continue
        
        if isinstance(event, TurnDone) and not _is_verbose and _turn_tools:
            # Yield a summary of grouped tools before finishing
            names = list(dict.fromkeys(t.name for t in _turn_tools if isinstance(t, ToolStart)))
            summary = f"Used tools: {', '.join(names)}"
            yield ToolEnd(name="Summary", result=summary, permitted=True)
            _turn_tools = []

        yield event

    try:
        import checkpoint as ckpt
        session_id = cfg.get("_session_id", "default")
        tracked = ckpt.get_tracked_edits()
        last_snaps = ckpt.list_snapshots(session_id)
        skip = False
        if not tracked and last_snaps:
            if len(state.messages) == last_snaps[-1].get("message_index", -1):
                skip = True
        if not skip:
            ckpt.make_snapshot(session_id, state, cfg, user_input, tracked_edits=tracked)
        ckpt.reset_tracked()
    except Exception:
        pass


def _event_to_dict(event) -> dict | None:
    if isinstance(event, TextChunk):
        return {"type": "text", "text": event.text}
    elif isinstance(event, ThinkingChunk):
        return {"type": "thinking", "text": event.text}
    elif isinstance(event, ToolStart):
        return {"type": "tool_start", "name": event.name, "inputs": event.inputs}
    elif isinstance(event, ToolEnd):
        return {"type": "tool_end", "name": event.name, "result": event.result, "permitted": event.permitted}
    elif isinstance(event, TurnDone):
        return {
            "type":        "turn_done",
            "in":          event.input_tokens,
            "out":         event.output_tokens,
            "cache_read":  getattr(event, "cache_read_tokens", 0),
            "cache_write": getattr(event, "cache_creation_tokens", 0),
        }
    elif isinstance(event, PermissionRequest):
        pid = str(uuid.uuid4())
        evt = threading.Event()
        _PENDING_PERMISSIONS[pid] = (event, evt)
        payload = {"type": "permission", "id": pid, "description": event.description}
        return payload, evt
    return None


def _sanitize_for_api(text: str) -> str:
    """Aggressive sanitize: remove control chars (except \n\r\t), surrogates, and normalize."""
    if not isinstance(text, str):
        text = str(text)
    # Step 1: remove UTF-16 surrogates
    text = "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))
    # Step 2: remove control characters except newline, carriage return, tab
    text = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")
    # Step 3: normalize fancy quotes to plain quotes
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    # Step 4: strip leading/trailing whitespace per line but keep structure
    return text.strip()


def _build_roundtable_prompt(agent: RoundtableAgent, user_msg: str, history: list[dict]) -> str:
    """Build a lean prompt with ONLY the last text message per member.
    history items: {"agent": str, "text": str}
    """
    user_msg = _sanitize_for_api(user_msg)
    ctx_parts = []
    # history is already pruned to last-message-per-agent before calling this
    for item in history:
        author = item.get("agent", "")
        text = _sanitize_for_api(item.get("text", ""))
        if author and text:
            ctx_parts.append(f"[{author}]: {text}")

    if ctx_parts:
        ctx = "\n".join(ctx_parts)
        return (
            f"[Mesa Redonda]\n"
            f"Historial (ultimo mensaje de cada miembro):\n{ctx}\n\n"
            f"Usuario ahora: {user_msg}\n\n"
            f"Eres el miembro {agent.id}. Responde desde tu perspectiva."
        )
    return (
        f"[Mesa Redonda]\n"
        f"Eres parte de una mesa redonda con otros agentes.\n\n"
        f"Usuario ahora: {user_msg}\n\n"
        f"Eres el miembro {agent.id}. Responde desde tu perspectiva."
    )


def _run_agent_for_roundtable(agent: RoundtableAgent, user_msg: str, history: list[dict], q: queue.Queue):
    stop_evt = threading.Event()
    with _STOP_EVENTS_LOCK:
        _AGENT_STOP_EVENTS[agent.id] = stop_evt
    try:
        _ensure_plugin_tools()
        if CONFIG is None:
            q.put({"agent": agent.id, "type": "error", "message": "server not initialized"})
            return
        cfg = dict(CONFIG)
        cfg["model"] = agent.model
        prompt = _sanitize_for_api(_build_roundtable_prompt(agent, user_msg, history))
        system_prompt = build_system_prompt(cfg)
        cfg.pop("_in_telegram_turn", None)
        cfg["_last_interaction_time"] = time.time()

        # DO NOT clear agent.state.messages — we need prior turns for KV cache reuse.
        # The prompt itself is lean (only last msg per agent), so context stays small.
        # Agent SDK appends user+assistant to .messages automatically, giving cache hits.

        stopped = False
        for event in agent_run(prompt, agent.state, cfg, system_prompt):
            if stop_evt.is_set():
                stopped = True
                q.put({"agent": agent.id, "type": "agent_stopped"})
                break
            result = _event_to_dict(event)
            if result is None:
                continue
            if isinstance(result, tuple):
                payload, evt = result
                payload["agent"] = agent.id
                q.put(payload)
                evt.wait(timeout=300)
                _PENDING_PERMISSIONS.pop(payload["id"], None)
                continue
            payload = result
            payload["agent"] = agent.id
            q.put(payload)

        if not stopped:
            final_text = ""
            if agent.state.messages:
                for msg in reversed(agent.state.messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        final_text = msg["content"]
                        break
            q.put({"agent": agent.id, "type": "agent_done", "text": final_text})
    except Exception as exc:
        q.put({"agent": agent.id, "type": "error", "message": f"{type(exc).__name__}: {exc}"})
    finally:
        with _STOP_EVENTS_LOCK:
            _AGENT_STOP_EVENTS.pop(agent.id, None)


# ── Flask app ──────────────────────────────────────────────────────────────

def create_app() -> Flask:
    app = Flask(__name__)
    import logging as _logging
    _logging.getLogger("werkzeug").setLevel(_logging.ERROR)
    app.logger.disabled = True

    # ───────────────────────── Chat Normal HTML ─────────────────────────
    CHAT_PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dulus WebChat</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Archivo+Black&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0a0a;--bg2:#0f0f12;--bg3:#15151a;--bg4:#1a1a20;
  --ink:#f0e8df;--dim:#6a6470;--dim2:#3a3840;
  --accent:#ff6b1f;--accent2:#ffb347;
  --mono:'JetBrains Mono',monospace;
  --display:'Archivo Black','Impact',sans-serif;
  --radius:4px;
  --green:#7cffb5;--red:#ff5a6e;--yellow:#ffd166;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;font-size:16px}
body{background:var(--bg);color:var(--ink);font-family:var(--mono);height:100vh;display:flex;flex-direction:column;position:relative;overflow:hidden}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--accent);border-radius:3px}
.grid-bg{
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(rgba(255,107,31,.06) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,107,31,.06) 1px,transparent 1px);
  background-size:40px 40px;
  mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);
}
#app{display:flex;height:100vh;overflow:hidden;position:relative}

/* ===== Sidebar ===== */
#sidebar{
  width:260px;min-width:260px;background:var(--bg2);border-right:1px solid rgba(255,107,31,.12);
  display:flex;flex-direction:column;transition:width .25s ease,min-width .25s ease;margin-left:0;
  position:relative;z-index:200;height:100vh
}
#sidebar.collapsed{width:48px;min-width:48px}
#sidebar.collapsed .sidebar-expanded{display:none!important}
#sidebar:not(.collapsed) .sidebar-collapsed{display:none!important}
.sidebar-collapsed{display:flex;flex-direction:column;align-items:center;height:100%;padding:12px 0}
.sidebar-logo-btn{
  width:32px;height:32px;background:var(--accent);clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);
  display:grid;place-items:center;color:#000;font-size:16px;font-weight:800;cursor:pointer;border:none;flex-shrink:0
}
.sidebar-collapsed .sidebar-logo-btn{margin-bottom:auto}
.sidebar-collapsed .sidebar-bottom-btn{
  width:32px;height:32px;display:flex;align-items:center;justify-content:center;
  background:transparent;border:1px solid var(--dim2);border-radius:var(--radius);
  color:var(--dim);cursor:pointer;transition:all .2s;margin-top:6px;padding:0
}
.sidebar-collapsed .sidebar-bottom-btn:hover{border-color:var(--accent);color:var(--accent);background:rgba(255,107,31,.1)}
.sidebar-expanded{display:flex;flex-direction:column;height:100%}
.sidebar-header{
  display:flex;align-items:center;gap:10px;padding:16px;border-bottom:1px solid rgba(255,255,255,.05);flex-shrink:0
}
.sidebar-header h2{font-family:var(--display);font-size:14px;letter-spacing:-.01em;color:var(--ink)}
.sidebar-search{padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.05);flex-shrink:0}
.sidebar-search input{
  width:100%;background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:8px 12px;
  border-radius:var(--radius);font-family:var(--mono);font-size:12px;outline:none;transition:border-color .2s
}
.sidebar-search input:focus{border-color:var(--accent)}
.sidebar-search input::placeholder{color:var(--dim)}
#sessionList{flex:1;overflow-y:auto;padding:8px}
.session-item{
  display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--radius);
  cursor:pointer;transition:background .15s;border-left:3px solid transparent;margin-bottom:2px;
  position:relative;user-select:none
}
.session-item:hover{background:rgba(255,255,255,.03)}
.session-item.active{
  background:rgba(255,107,31,.08);border-left-color:var(--accent)
}
.session-icon{
  width:28px;height:28px;min-width:28px;border-radius:var(--radius);background:var(--bg3);
  display:grid;place-items:center;font-size:12px;color:var(--dim);border:1px solid var(--dim2)
}
.session-item.active .session-icon{border-color:var(--accent);color:var(--accent)}
.session-info{flex:1;min-width:0;overflow:hidden}
.session-title{
  font-size:12px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  font-weight:500;line-height:1.3
}
.session-time{font-size:10px;color:var(--dim);margin-top:2px}
.session-item.active .session-title{color:var(--accent2)}
.session-actions{
  display:flex;gap:2px;opacity:0;transition:opacity .15s
}
.session-item:hover .session-actions{opacity:1}
.session-actions button{
  width:24px;height:24px;display:flex;align-items:center;justify-content:center;
  background:transparent;border:none;color:var(--dim);cursor:pointer;border-radius:3px;transition:all .15s;
  padding:0
}
.session-actions button:hover{background:rgba(255,255,255,.08);color:var(--accent)}
.session-item.renaming .session-info{display:none}
.session-item.renaming .session-actions{display:none}
.session-rename-input{
  flex:1;background:var(--bg3);color:var(--ink);border:1px solid var(--accent);padding:6px 8px;
  border-radius:var(--radius);font-family:var(--mono);font-size:12px;outline:none
}
.sidebar-bottom{
  border-top:1px solid rgba(255,255,255,.05);padding:10px 16px;display:flex;gap:6px;flex-shrink:0
}
.sidebar-bottom button{
  flex:1;display:flex;align-items:center;justify-content:center;gap:6px;
  background:var(--bg3);color:var(--dim);border:1px solid var(--dim2);padding:8px 0;
  border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:700;
  letter-spacing:.05em;text-transform:uppercase;transition:all .2s
}
.sidebar-bottom button:hover{background:rgba(255,107,31,.1);border-color:var(--accent);color:var(--accent)}
.sidebar-bottom button svg{width:14px;height:14px}

/* ===== Main ===== */
#main{flex:1;display:flex;flex-direction:column;min-width:0;position:relative}

/* ===== Header ===== */
header{
  padding:0 24px;height:56px;background:rgba(10,10,10,.7);backdrop-filter:blur(16px);
  border-bottom:1px solid rgba(255,107,31,.12);display:flex;justify-content:space-between;
  align-items:center;gap:10px;position:relative;z-index:100
}
header .header-left{display:flex;align-items:center;gap:12px}
header h1{
  font-family:var(--display);font-size:18px;letter-spacing:-.02em;color:var(--ink);
  display:flex;align-items:center;gap:12px
}
header h1::before{
  content:"\25b2";font-size:18px;color:#000;background:var(--accent);width:32px;height:32px;
  display:grid;place-items:center;clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%)
}
header .model{font-size:11px;color:var(--dim)}
header a,header button{
  background:var(--bg2);color:var(--dim);border:1px solid var(--dim2);padding:6px 12px;
  border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;text-decoration:none;transition:background .2s,border-color .2s,color .2s
}
header a:hover,header button:hover{background:rgba(255,107,31,.1);border-color:var(--accent);color:var(--accent)}
#sidebarToggle{
  display:none;width:36px;height:36px;align-items:center;justify-content:center;
  background:transparent;border:1px solid var(--dim2);border-radius:var(--radius);
  color:var(--dim);cursor:pointer;transition:all .2s;padding:0
}
#sidebarToggle:hover{border-color:var(--accent);color:var(--accent)}

/* ===== Log ===== */
#log{flex:1;overflow-y:auto;padding:24px 40px;display:flex;flex-direction:column;gap:16px;position:relative;z-index:1}
.msg{max-width:780px;padding:12px 16px;border-radius:6px;white-space:pre-wrap;word-wrap:break-word;font-size:14px}
.user{align-self:flex-end;background:rgba(255,107,31,.1);border:1px solid rgba(255,107,31,.25)}
.assistant{align-self:flex-start;background:var(--bg3);border:1px solid var(--dim2)}
.meta{font-size:10px;color:var(--dim);margin-top:6px}
.err{color:#ff5a6e;border-color:rgba(255,90,110,.4)!important}

/* ===== Input ===== */
#inputArea{
  display:flex;gap:10px;padding:16px 40px;background:var(--bg2);border-top:1px solid var(--dim2);
  position:relative;z-index:100
}
textarea{
  flex:1;background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:12px;
  border-radius:var(--radius);font-family:var(--mono);font-size:14px;resize:none;height:64px;
  outline:none;transition:border-color .2s
}
textarea:focus{border-color:var(--accent)}
textarea::placeholder{color:var(--dim)}
button.send{
  background:var(--accent);color:#000;border:none;padding:0 24px;border-radius:var(--radius);
  font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  cursor:pointer;transition:background .2s
}
button.send:hover{background:var(--accent2)}
button.send:disabled{opacity:.4;cursor:not-allowed}

/* ===== Extras ===== */
.think{
  font-size:11px;color:var(--dim);margin-top:8px;padding:8px 12px;border-left:2px solid var(--dim2);
  background:rgba(0,0,0,.2);white-space:pre-wrap
}
.tool{
  font-size:11px;color:#a39ca8;margin-top:8px;padding:8px 12px;border-left:2px solid var(--accent);
  background:rgba(255,107,31,.04);white-space:pre-wrap
}
.tool-result{
  font-size:11px;color:var(--dim);margin-top:4px;padding:8px 12px;border-left:2px solid var(--dim2);
  background:rgba(0,0,0,.2);white-space:pre-wrap;max-height:200px;overflow-y:auto
}
.perm{
  font-size:12px;color:#ffd166;margin-top:8px;padding:12px;border:1px solid rgba(255,209,102,.25);
  background:rgba(255,209,102,.1);display:flex;gap:10px;align-items:center;flex-wrap:wrap
}
.perm button{background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:6px 14px;border-radius:3px;cursor:pointer;font-weight:700}
.perm button.approve{background:var(--accent);color:#000;border:none}

/* ===== Context Menu ===== */
#ctxMenu{
  position:fixed;background:var(--bg4);border:1px solid var(--dim2);border-radius:var(--radius);
  padding:4px;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,.5);display:none;min-width:140px
}
#ctxMenu .ctx-item{
  display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:3px;
  cursor:pointer;font-size:12px;color:var(--ink);transition:background .15s;border:none;background:transparent;
  width:100%;font-family:var(--mono)
}
#ctxMenu .ctx-item:hover{background:rgba(255,107,31,.15);color:var(--accent2)}
#ctxMenu .ctx-item svg{width:14px;height:14px;color:var(--dim);flex-shrink:0}
#ctxMenu .ctx-item:hover svg{color:var(--accent)}
#ctxMenu .ctx-separator{height:1px;background:var(--dim2);margin:4px 0}

/* ===== Toast ===== */
#toastContainer{
  position:fixed;top:16px;right:16px;z-index:10000;display:flex;flex-direction:column;gap:8px;pointer-events:none
}
.toast{
  background:var(--bg4);border:1px solid var(--dim2);border-radius:var(--radius);padding:12px 16px;
  font-size:12px;color:var(--ink);box-shadow:0 4px 16px rgba(0,0,0,.5);
  display:flex;align-items:center;gap:10px;min-width:240px;max-width:340px;
  animation:toastIn .25s ease;pointer-events:auto;position:relative;overflow:hidden
}
.toast::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--dim)}
.toast.success::before{background:var(--green)}
.toast.error::before{background:var(--red)}
.toast.info::before{background:var(--accent)}
@keyframes toastIn{from{opacity:0;transform:translateX(40px)}to{opacity:1;transform:translateX(0)}}
@keyframes toastOut{from{opacity:1;transform:translateX(0)}to{opacity:0;transform:translateX(40px)}}
.toast svg{width:16px;height:16px;flex-shrink:0}
.toast.success svg{color:var(--green)}
.toast.error svg{color:var(--red)}
.toast.info svg{color:var(--accent)}

/* ===== Mobile ===== */
@media(max-width:768px){
  #sidebar{position:fixed;left:0;top:0;bottom:0;z-index:500;transform:translateX(-100%);transition:transform .3s ease;box-shadow:none}
  #sidebar.open{transform:translateX(0);box-shadow:4px 0 24px rgba(0,0,0,.5)}
  #sidebarOverlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:400;backdrop-filter:blur(2px)}
  #sidebarOverlay.open{display:block}
  #sidebarToggle{display:flex}
  #log{padding:16px 20px}
  .msg{max-width:92%}
  #inputArea{padding:16px 20px}
  header{padding:0 16px;height:52px}
}
@media(max-width:600px){
  header{height:auto;min-height:52px;padding:8px 16px;flex-wrap:wrap}
  header h1{font-size:15px}
  header h1::before{width:26px;height:26px;font-size:14px}
  header a,header button{font-size:10px;padding:5px 8px}
}
</style><style id="dynamic-theme"></style></head><body>
<div class="grid-bg"></div>
<div id="sidebarOverlay"></div>
<div id="app">
<!-- ===== SIDEBAR ===== -->
<nav id="sidebar">
  <div class="sidebar-collapsed">
    <button class="sidebar-logo-btn" onclick="toggleSidebar()" title="Expand">&#9650;</button>
    <button class="sidebar-bottom-btn" onclick="newChat()" title="New Chat">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
    </button>
    <button class="sidebar-bottom-btn" onclick="refreshSessions()" title="Refresh">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
    </button>
    <button class="sidebar-bottom-btn" onclick="toggleSidebar()" title="Expand" style="margin-top:auto">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 5l7 7-7 7"/><path d="M5 5l7 7-7 7"/></svg>
    </button>
  </div>
  <div class="sidebar-expanded">
    <div class="sidebar-header">
      <div class="sidebar-logo-btn" style="cursor:default">&#9650;</div>
      <h2>DULUS</h2>
    </div>
    <div class="sidebar-search">
      <input type="text" id="searchInput" placeholder="Search chats..." oninput="filterSessions()">
    </div>
    <div id="sessionList"></div>
    <div class="sidebar-bottom">
      <button onclick="newChat()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>New</span>
      </button>
      <button onclick="refreshSessions()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
      </button>
      <button onclick="toggleSidebar()" title="Collapse">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 17l-5-5 5-5"/><path d="M18 17l-5-5 5-5"/></svg>
      </button>
    </div>
  </div>
</nav>
<!-- ===== MAIN ===== -->
<div id="main">
<header>
  <div class="header-left">
    <button id="sidebarToggle" onclick="toggleSidebar()">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <h1>DULUS WEBCHAT</h1>
  </div>
  <select id="personaSelect" style="background:var(--bg3);color:var(--dim);border:1px solid var(--dim2);padding:4px 10px;border-radius:var(--radius);font-family:var(--mono);font-size:12px;outline:none;cursor:pointer;flex:1;max-width:250px;margin:0 15px;text-align:center"></select>
  <div>
    <a href="/roundtable">Mesa Redonda</a>
    <a href="/dashboard">Task Manager</a>
    <button onclick="clearChat()">clear</button>
  </div>
</header>
<div id="log"></div>
<div id="inputArea">
  <textarea id="inp" placeholder="Mensaje a Dulus... (Enter envia, Shift+Enter nueva linea)" autofocus></textarea>
  <button class="send" id="sendBtn">SEND</button>
</div>
</div>
</div>

<!-- Context Menu -->
<div id="ctxMenu">
  <button class="ctx-item" onclick="ctxRename()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
    Rename
  </button>
  <div class="ctx-separator"></div>
  <button class="ctx-item" onclick="ctxDelete()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
    Delete
  </button>
</div>

<!-- Toast Container -->
<div id="toastContainer"></div>
<script>
// ===== THEME SYNC =====
(function(){
  function ensureThemeStyle(){
    var el = document.getElementById('dynamic-theme');
    if(!el){
      el = document.createElement('style');
      el.id = 'dynamic-theme';
      document.head.appendChild(el);
    }
    return el;
  }
  async function applyTheme(name){
    name = name || localStorage.getItem('dulus-theme') || 'dulus';
    try{
      var res = await fetch('/api/themes/' + encodeURIComponent(name) + '/css');
      var css = await res.text();
      if(css){
        ensureThemeStyle().textContent = css;
        localStorage.setItem('dulus-theme', name);
      }
    }catch(e){}
  }
  applyTheme();
})();

// ===== STATE =====
const ACTIVE_KEY = 'dulus_active_session';
const SIDEBAR_COLLAPSED_KEY = 'dulus_sidebar_collapsed';
const DEFAULT_SESSION_ID = 'default';

let sessions = [];
let activeSessionId = DEFAULT_SESSION_ID;
let ctxTargetId = null;
let isMobile = window.innerWidth < 768;
let renamingId = null;

// ===== TOAST =====
function showToast(message, type){
  var c = document.getElementById('toastContainer');
  var t = document.createElement('div');
  t.className = 'toast ' + (type || 'info');
  var icon = '';
  if(type === 'success'){
    icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
  }else if(type === 'error'){
    icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
  }else{
    icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
  }
  t.innerHTML = icon + '<span>' + escapeHtml(message) + '</span>';
  c.appendChild(t);
  setTimeout(function(){ t.classList.add('exit'); setTimeout(function(){ t.remove(); }, 250); }, 3000);
}

// ===== UTILS =====
function escapeHtml(t){
  var d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}
function genId(){ return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
function formatTime(ts){
  var d = new Date(ts);
  var now = new Date();
  if(d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  var yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1);
  if(d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], {month: 'short', day: 'numeric'});
}

// ===== SESSION STORAGE =====
function loadSessions(){
  // Server is the source of truth; localStorage no longer caches session data
  fetch('/api/sessions')
    .then(function(r){ return r.json(); })
    .then(function(data){
      if(data && data.length){
        sessions = data.map(function(s){
          return {
            id: s.id,
            title: s.title,
            timestamp: s.saved_at ? new Date(s.saved_at).getTime() : Date.now(),
            messages: s.messages || []
          };
        });
        var savedActive = localStorage.getItem(ACTIVE_KEY);
        if(savedActive && sessions.some(function(s){ return s.id === savedActive; })){
          activeSessionId = savedActive;
        }else{
          activeSessionId = sessions[0].id;
        }
        renderSessions();
        selectSession(activeSessionId);
        return;
      }
      // Server empty — create a default session
      sessions = [{id: DEFAULT_SESSION_ID, title: 'Chat', timestamp: Date.now(), messages: []}];
      activeSessionId = DEFAULT_SESSION_ID;
      renderSessions();
      selectSession(activeSessionId);
    })
    .catch(function(e){
      // Network down — start with a blank default session
      sessions = [{id: DEFAULT_SESSION_ID, title: 'Chat', timestamp: Date.now(), messages: []}];
      activeSessionId = DEFAULT_SESSION_ID;
      renderSessions();
    });
}
function saveActive(){ localStorage.setItem(ACTIVE_KEY, activeSessionId); }
function getActiveSession(){
  return sessions.find(function(s){ return s.id === activeSessionId; }) || sessions[0];
}
function updateActiveMessages(msgs){
  var s = getActiveSession();
  if(s){ s.messages = msgs; s.timestamp = Date.now(); }
}
function updateSessionTitleFromMessages(){
  var s = getActiveSession();
  if(!s) return;
  var firstUser = s.messages.find(function(m){ return m.role === 'user'; });
  if(firstUser && s.title === 'Chat'){
    var txt = (typeof firstUser.content === 'string' ? firstUser.content : '').slice(0, 40);
    if(txt) s.title = txt;
    renderSessions();
  }
}

// ===== SIDEBAR UI =====
function renderSessions(){
  var list = document.getElementById('sessionList');
  var q = document.getElementById('searchInput').value.toLowerCase();
  var filtered = sessions.filter(function(s){ return !q || s.title.toLowerCase().indexOf(q) >= 0; });
  if(!filtered.length){
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--dim);font-size:11px">No chats found</div>';
    return;
  }
  var html = '';
  for(var i = 0; i < filtered.length; i++){
    var s = filtered[i];
    var isActive = s.id === activeSessionId;
    var isRenaming = s.id === renamingId;
    if(isRenaming){
      html += '<div class="session-item active renaming" data-id="' + s.id + '">' +
        '<div class="session-icon">&#9650;</div>' +
        '<input class="session-rename-input" value="' + escapeHtml(s.title) + '" ' +
        'onkeydown="renameKey(event,\'' + s.id + '\')" onblur="finishRename(\'' + s.id + '\')" id="rename-' + s.id + '">' +
        '</div>';
      continue;
    }
    html += '<div class="session-item ' + (isActive ? 'active' : '') + '" data-id="' + s.id + '" ' +
      'onclick="selectSession(\'' + s.id + '\')" oncontextmenu="showCtx(event,\'' + s.id + '\')">' +
      '<div class="session-icon">&#9650;</div>' +
      '<div class="session-info">' +
        '<div class="session-title">' + escapeHtml(s.title) + '</div>' +
        '<div class="session-time">' + formatTime(s.timestamp) + '</div>' +
      '</div>' +
      '<div class="session-actions" onclick="event.stopPropagation()">' +
        '<button onclick="startRename(\'' + s.id + '\')" title="Rename">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>' +
        '</button>' +
        '<button onclick="deleteSession(\'' + s.id + '\')" title="Delete">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
        '</button>' +
      '</div>' +
    '</div>';
  }
  list.innerHTML = html;
  if(renamingId){
    var inp = document.getElementById('rename-' + renamingId);
    if(inp){ inp.focus(); inp.select(); }
  }
}

function startRename(id){
  renamingId = id; renderSessions();
}
function finishRename(id){
  var inp = document.getElementById('rename-' + id);
  if(inp){
    var v = inp.value.trim();
    if(v){
      var s = sessions.find(function(x){ return x.id === id; });
      if(s){ s.title = v; }
    }
  }
  renamingId = null; renderSessions();
}
function renameKey(e, id){
  if(e.key === 'Enter'){ e.preventDefault(); finishRename(id); }
  else if(e.key === 'Escape'){ renamingId = null; renderSessions(); }
}
function filterSessions(){ renderSessions(); }

async function selectSession(id){
  activeSessionId = id; saveActive();
  renderSessions();
  var s = getActiveSession();
  if(s && s.messages){
    log.innerHTML = '';
    currentAssistant = null;
    currentText = '';
    for(var i = 0; i < s.messages.length; i++){
      var m = s.messages[i];
      if(m.role === 'user') add('user', m.content);
      else if(m.role === 'assistant'){
        var text = typeof m.content === 'string' ? m.content : '';
        if(Array.isArray(m.content)){
          var tc = m.content.find(function(c){ return c.type === 'text'; });
          if(tc) text = tc.text;
        }
        if(text) add('assistant', text);
      }
    }
  }
  closeMobileSidebar();
  // Sync server state with this session so the backend talks to the right conversation
  try{
    await fetch('/api/session/load', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({messages: s ? s.messages : []})
    });
  }catch(_){}
}

function newChat(){
  fetch('/clear', {method: 'POST'}).then(function(){
    var newS = {id: genId(), title: 'Chat', timestamp: Date.now(), messages: []};
    sessions.unshift(newS); activeSessionId = newS.id;
    saveActive();
    log.innerHTML = '';
    currentAssistant = null;
    currentText = '';
    renderSessions();
    closeMobileSidebar();
    showToast('New chat started', 'success');
  });
}

function deleteSession(id){
  var s = sessions.find(function(x){ return x.id === id; });
  if(!s) return;
  if(!confirm('Delete "' + s.title + '"?')) return;
  fetch('/api/sessions/' + encodeURIComponent(id), {method: 'DELETE'}).catch(function(){});
  sessions = sessions.filter(function(x){ return x.id !== id; });
  if(sessions.length === 0){
    var ns = {id: genId(), title: 'Chat', timestamp: Date.now(), messages: []};
    sessions.push(ns); activeSessionId = ns.id;
  }else if(activeSessionId === id){
    activeSessionId = sessions[0].id;
  }
  saveActive();
  selectSession(activeSessionId);
  renderSessions();
  showToast('Chat deleted', 'info');
}

function refreshSessions(){
  syncWithServer(function(){
    showToast('Chats refreshed', 'success');
  });
}

// ===== CONTEXT MENU =====
function showCtx(e, id){
  e.preventDefault();
  ctxTargetId = id;
  var menu = document.getElementById('ctxMenu');
  menu.style.display = 'block';
  var x = e.clientX, y = e.clientY;
  if(x + 160 > window.innerWidth) x = window.innerWidth - 170;
  if(y + 80 > window.innerHeight) y = window.innerHeight - 90;
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
}
function hideCtx(){ document.getElementById('ctxMenu').style.display = 'none'; ctxTargetId = null; }
function ctxRename(){ if(ctxTargetId) startRename(ctxTargetId); hideCtx(); }
function ctxDelete(){ if(ctxTargetId) deleteSession(ctxTargetId); hideCtx(); }
document.addEventListener('click', function(e){
  if(!e.target.closest('#ctxMenu')) hideCtx();
});

// ===== SIDEBAR TOGGLE =====
function toggleSidebar(){
  if(window.innerWidth < 768){
    var sb = document.getElementById('sidebar');
    if(sb.classList.contains('open')) closeMobileSidebar();
    else openMobileSidebar();
  }else{
    var sb = document.getElementById('sidebar');
    sb.classList.toggle('collapsed');
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sb.classList.contains('collapsed') ? '1' : '0');
  }
}
function initSidebar(){
  var collapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
  if(collapsed === '1') document.getElementById('sidebar').classList.add('collapsed');
}

// ===== MOBILE SIDEBAR =====
function openMobileSidebar(){
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebarOverlay').classList.add('open');
}
function closeMobileSidebar(){
  if(window.innerWidth >= 768) return;
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');
}
document.getElementById('sidebarOverlay').addEventListener('click', closeMobileSidebar);

// ===== CHAT FUNCTIONS =====
var log = document.getElementById('log');
var inp = document.getElementById('inp');
var btn = document.getElementById('sendBtn');
var currentAssistant = null;
var currentText = '';

function add(role, text, extra){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  if(extra){
    var m = document.createElement('div');
    m.className = 'meta';
    m.textContent = extra;
    d.appendChild(m);
  }
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function ensureAssistant(){
  if(!currentAssistant){
    currentAssistant = add('assistant', '');
  }
  return currentAssistant;
}

function appendText(text){
  ensureAssistant();
  currentText += text;
  currentAssistant.textContent = currentText;
  log.scrollTop = log.scrollHeight;
}

function appendThinking(text){
  ensureAssistant();
  var th = currentAssistant.querySelector('.think');
  if(!th){
    th = document.createElement('div');
    th.className = 'think';
    th.textContent = '[thinking]';
    currentAssistant.appendChild(th);
  }
  th.textContent += text;
  log.scrollTop = log.scrollHeight;
}

function startTool(name, inputs){
  ensureAssistant();
  var t = document.createElement('div');
  t.className = 'tool';
  t.textContent = '\ud83d\udd27 ' + name + '\n' + JSON.stringify(inputs, null, 2);
  currentAssistant.appendChild(t);
  log.scrollTop = log.scrollHeight;
}

function endTool(name, result, permitted){
  ensureAssistant();
  var r = document.createElement('div');
  r.className = 'tool-result';
  r.textContent = (permitted ? '\u2705' : '\u274c') + ' ' + result;
  currentAssistant.appendChild(r);
  log.scrollTop = log.scrollHeight;
}

function showPermission(id, desc){
  ensureAssistant();
  var p = document.createElement('div');
  p.className = 'perm';
  p.innerHTML = '<span>\u26d4 ' + desc + '</span>';
  var yes = document.createElement('button');
  yes.textContent = 'Approve';
  yes.className = 'approve';
  yes.onclick = function(){ sendPermission(id, true); p.remove(); };
  var no = document.createElement('button');
  no.textContent = 'Deny';
  no.onclick = function(){ sendPermission(id, false); p.remove(); };
  p.appendChild(yes);
  p.appendChild(no);
  currentAssistant.appendChild(p);
  log.scrollTop = log.scrollHeight;
}

async function sendPermission(id, granted){
  await fetch('/permission', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id: id, granted: granted})
  });
}

async function sendMessage(){
  var t = inp.value.trim();
  if(!t) return;
  add('user', t);
  inp.value = '';
  btn.disabled = true;
  currentAssistant = null;
  currentText = '';
  try{
    var resp = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: t})
    });
    var reader = resp.body.getReader();
    var decoder = new TextDecoder();
    var buf = '';
    while(true){
      var chunk = await reader.read();
      if(chunk.done) break;
      buf += decoder.decode(chunk.value, {stream: true});
      var lines = buf.split('\n');
      buf = lines.pop();
      for(var i = 0; i < lines.length; i++){
        var line = lines[i];
        if(!line.startsWith('data: ')) continue;
        var d;
        try{ d = JSON.parse(line.slice(6)); }catch(_){ continue; }
        if(d.type === 'text') appendText(d.text);
        else if(d.type === 'thinking') appendThinking(d.text);
        else if(d.type === 'tool_start') startTool(d.name, d.inputs);
        else if(d.type === 'tool_end') endTool(d.name, d.result, d.permitted);
        else if(d.type === 'permission') showPermission(d.id, d.description);
        else if(d.type === 'turn_done'){
          var meta = document.createElement('div');
          meta.className = 'meta';
          var txt = 'in:' + d.in + ' out:' + d.out;
          if(d.cache_read) txt += ' [cache hit: ' + d.cache_read + ']';
          if(d.cache_write) txt += ' [cache new: ' + d.cache_write + ']';
          meta.textContent = txt;
          ensureAssistant().appendChild(meta);
        }
        else if(d.type === 'error') appendText('\n[error] ' + d.message);
      }
    }
  }catch(err){
    add('assistant', '[network] ' + err, '').classList.add('err');
  }finally{
    btn.disabled = false;
    inp.focus();
    syncWithServer();
  }
}

async function clearChat(){
  await fetch('/clear', {method: 'POST'});
  log.innerHTML = '';
  currentAssistant = null;
  currentText = '';
  var s = getActiveSession();
  if(s){ s.messages = []; s.timestamp = Date.now(); }
  showToast('Chat cleared', 'info');
}

async function syncWithServer(cb){
  if(btn.disabled) return;
  try{
    var rh = await fetch('/api/chat/history');
    if(rh.ok){
      var ht = await rh.json();
      var s = getActiveSession();
      var localCount = s ? s.messages.length : 0;
      // Only overwrite local session if server has more messages (new turn completed)
      if(ht.messages.length > localCount){
        updateActiveMessages(ht.messages);
        updateSessionTitleFromMessages();
        var wasNearBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 50;
        log.innerHTML = '';
        currentAssistant = null;
        currentText = '';
        for(var i = 0; i < ht.messages.length; i++){
          var m = ht.messages[i];
          if(m.role === 'user') add('user', m.content);
          else if(m.role === 'assistant'){
            var text = typeof m.content === 'string' ? m.content : '';
            if(Array.isArray(m.content)){
              var tc = m.content.find(function(c){ return c.type === 'text'; });
              if(tc) text = tc.text;
            }
            if(text) add('assistant', text);
          }
        }
        if(wasNearBottom) log.scrollTop = log.scrollHeight;
        renderSessions();
      }
    }
    var rp = await fetch('/api/personas');
    if(rp.ok){
      var jp = await rp.json();
      var sel = document.getElementById('personaSelect');
      var activeKeys = Object.keys(jp.active || {});
      sel.innerHTML = jp.personas.map(function(p){
        var isSelected = activeKeys.indexOf(p.name) >= 0 ? 'selected' : '';
        return '<option value="' + p.name + '" ' + isSelected + '>' + p.name + ' (' + p.role + ')</option>';
      }).join('');
      sel.onchange = async function(e){
        await fetch('/api/personas/activate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id: e.target.value})
        });
      };
    }
  }catch(_){}
  // Persist current session to server disk
  fetch('/api/sessions/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: activeSessionId})
  }).catch(function(){});
  if(cb) cb();
}

async function loadHist(){ return syncWithServer(); }

inp.addEventListener('keydown', function(e){
  if(e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    sendMessage();
  }
});
btn.addEventListener('click', sendMessage);

// ===== MOBILE =====
window.addEventListener('resize', function(){
  var nowMobile = window.innerWidth < 768;
  if(nowMobile !== isMobile){
    isMobile = nowMobile;
    if(!isMobile) closeMobileSidebar();
  }
});

// ===== INIT =====
loadSessions();
initSidebar();
renderSessions();
loadHist();
// Ensure server state matches the active session on startup
(function(){
  var s = getActiveSession();
  if(s){
    fetch('/api/session/load', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({messages: s.messages || []})
    }).catch(function(){});
  }
})();
setInterval(function(){ syncWithServer(); }, 5000);
</script>
</body></html>"""

    # ─────────────────────── Mesa Redonda HTML ──────────────────────────
    RT_PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dulus Mesa Redonda</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Archivo+Black&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0a0a;
  --bg2:#0f0f12;
  --bg3:#15151a;
  --ink:#f0e8df;
  --dim:#6a6470;
  --dim2:#3a3840;
  --accent:#ff6b1f;
  --accent2:#ffb347;
  --mono:'JetBrains Mono',monospace;
  --display:'Archivo Black','Impact',sans-serif;
  --radius:4px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;font-size:16px}
body{background:var(--bg);color:var(--ink);font-family:var(--mono);height:100vh;display:flex;flex-direction:column;position:relative}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--accent);border-radius:3px}

.grid-bg{
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(rgba(255,107,31,.06) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,107,31,.06) 1px,transparent 1px);
  background-size:40px 40px;
  mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);
}

header{padding:0 40px;height:64px;background:rgba(10,10,10,.7);backdrop-filter:blur(16px);border-bottom:1px solid rgba(255,107,31,.12);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;position:relative;z-index:100}
header h1{font-family:var(--display);font-size:18px;letter-spacing:-.02em;color:var(--ink);display:flex;align-items:center;gap:12px}
header h1::before{content:"▲";font-size:18px;color:#000;background:var(--accent);width:32px;height:32px;display:grid;place-items:center;clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);}

header a,header button{background:var(--bg2);color:var(--dim);border:1px solid var(--dim2);padding:6px 12px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;text-decoration:none;transition:background .2s,border-color .2s,color .2s}
header a:hover,header button:hover{background:rgba(255,107,31,.1);border-color:var(--accent);color:var(--accent)}

#setup{padding:30px;display:flex;flex-direction:column;gap:16px;align-items:center;justify-content:center;flex:1;position:relative;z-index:1}
#setup h2{color:var(--accent);font-family:var(--display);font-size:32px;letter-spacing:-.02em}
#setup p{color:var(--dim);font-size:13px;letter-spacing:.1em;text-transform:uppercase}
#setup textarea{width:400px;max-width:90vw;height:120px;background:var(--bg3);border:1px solid var(--dim2);color:var(--ink);padding:12px;border-radius:var(--radius);font-family:var(--mono);font-size:13px;resize:none;outline:none;transition:border-color .2s}
#setup textarea:focus{border-color:var(--accent)}
#setup button{background:var(--accent);color:#000;border:none;padding:12px 32px;border-radius:var(--radius);font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:background .2s}
#setup button:hover{background:var(--accent2)}
#grid{display:none;flex:1;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;padding:24px 40px;overflow-y:auto;position:relative;z-index:1}
.col{background:var(--bg2);border:1px solid var(--dim2);border-radius:6px;display:flex;flex-direction:column;overflow:hidden}
.col-head{padding:12px 16px;background:var(--bg3);border-bottom:1px solid var(--dim2);font-size:12px;font-weight:700;color:var(--accent);letter-spacing:.1em;text-transform:uppercase;display:flex;justify-content:space-between;align-items:center}
.col-head .stop-btn{background:#2a0a0a;color:#ff5a6e;border:1px solid rgba(255,90,110,.4);padding:3px 10px;border-radius:3px;cursor:pointer;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;transition:background .2s,border-color .2s}
.col-head .stop-btn:hover{background:rgba(255,90,110,.15);border-color:#ff5a6e}
.col-head .stop-btn:disabled{opacity:.4;cursor:not-allowed}
.col.stopped{border-color:rgba(255,90,110,.4)}
.col.stopped .col-head{color:#ff5a6e}
.col-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.user-bubble{align-self:flex-end;background:rgba(255,107,31,.1);border:1px solid rgba(255,107,31,.25);padding:10px 14px;border-radius:6px;white-space:pre-wrap;word-wrap:break-word;font-size:13px}
.agent-bubble{align-self:flex-start;background:var(--bg3);border:1px solid var(--dim2);padding:10px 14px;border-radius:6px;white-space:pre-wrap;word-wrap:break-word;font-size:13px}
.think{font-size:11px;color:var(--dim);margin-top:6px;padding:6px 10px;border-left:2px solid var(--dim2);background:rgba(0,0,0,.2);white-space:pre-wrap}
.tool{font-size:11px;color:#a39ca8;margin-top:6px;padding:6px 10px;border-left:2px solid var(--accent);background:rgba(255,107,31,.04);white-space:pre-wrap}
.meta{font-size:10px;color:var(--dim);margin-top:6px}
.err{color:#ff5a6e}
.perm{font-size:12px;color:#ffd166;margin-top:8px;padding:12px;border:1px solid rgba(255,209,102,.25);background:rgba(255,209,102,.1);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.perm button{background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:6px 14px;border-radius:3px;cursor:pointer;font-weight:700}
.perm button.approve{background:var(--accent);color:#000;border:none}
#inputArea{display:flex;gap:10px;padding:16px 40px;background:var(--bg2);border-top:1px solid var(--dim2);position:relative;z-index:100}
textarea{flex:1;background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:12px;border-radius:var(--radius);font-family:var(--mono);font-size:14px;resize:none;height:64px;outline:none;transition:border-color .2s}
textarea:focus{border-color:var(--accent)}
button.send{background:var(--accent);color:#000;border:none;padding:0 24px;border-radius:var(--radius);font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:background .2s}
button.send:disabled{opacity:.4;cursor:not-allowed}
@media(max-width:600px){
header{padding:10px 20px;height:auto}
#grid{padding:16px 20px}
#inputArea{padding:16px 20px}
}
</style><style id="dynamic-theme"></style></head><body>
<div class="grid-bg"></div>
<header>
  <h1>DULUS MESA REDONDA</h1>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:12px;color:var(--dim)">
      <input type="checkbox" id="proactiveToggle" style="accent-color:var(--accent);cursor:pointer">
      <span id="proactiveLabel">Auto-turno</span>
    </label>
    <a href="/">Chat</a>
    <a href="/dashboard">Task Manager</a>
    <button onclick="location.reload()">Reiniciar</button>
  </div>
</header>
<div id="setup">
  <h2>Setup</h2>
  <p>Introduce 3 a 5 modelos (uno por linea)</p>
  <textarea id="modelsInput" placeholder="kimi-code/kimi-for-coding&#10;kimi-code2/kimi-for-coding&#10;kimi-code3/kimi-for-coding"></textarea>
  <button onclick="startRt()">Iniciar</button>
</div>
<div id="grid"></div>
<div id="inputArea" style="display:none">
  <textarea id="inp" placeholder="Mensaje a la mesa... (Enter envia)" autofocus></textarea>
  <button class="send" id="sendBtn" onclick="sendTurn()">SEND</button>
</div>
<script>
// ===== THEME SYNC =====
(function(){
  function ensureThemeStyle(){
    var el = document.getElementById('dynamic-theme');
    if(!el){
      el = document.createElement('style');
      el.id = 'dynamic-theme';
      document.head.appendChild(el);
    }
    return el;
  }
  async function applyTheme(name){
    name = name || localStorage.getItem('dulus-theme') || 'dulus';
    try{
      var res = await fetch('/api/themes/' + encodeURIComponent(name) + '/css');
      var css = await res.text();
      if(css){
        ensureThemeStyle().textContent = css;
        localStorage.setItem('dulus-theme', name);
      }
    }catch(e){}
  }
  applyTheme();
})();

let agents=[];
let active=false;
let proactiveMode=false;
let autoRoundsLeft=0;

const proactiveToggle=document.getElementById('proactiveToggle');
proactiveToggle.addEventListener('change',function(){
  proactiveMode=this.checked;
  const lbl=document.getElementById('proactiveLabel');
  lbl.textContent=proactiveMode?'Auto-turno (ON)':'Auto-turno';
  lbl.style.color=proactiveMode?'#00ffa3':'#888';
});

function startRt(){
  const raw=document.getElementById('modelsInput').value.trim().split('\n').filter(function(x){return x.trim();});
  if(raw.length<3||raw.length>5){alert('Necesitas 3 a 5 modelos');return;}
  fetch('/roundtable/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({models:raw})})
    .then(function(r){return r.json();})
    .then(function(j){
      if(!j.ok){alert(j.error);return;}
      agents=j.agents;
      active=true;
      document.getElementById('setup').style.display='none';
      document.getElementById('grid').style.display='grid';
      document.getElementById('inputArea').style.display='flex';
      const grid=document.getElementById('grid');
      grid.innerHTML='';
      agents.forEach(function(a){
        const col=document.createElement('div');
        col.className='col';
        col.id='col-'+a;
        col.innerHTML='<div class="col-head"><span>'+a+'</span><button class="stop-btn" id="stop-'+a+'" onclick="stopAgent(\''+a+'\')">Stop</button></div><div class="col-body"></div>';
        grid.appendChild(col);
      });
    });
}

function addUserToAll(msg){
  agents.forEach(function(a){
    const body=document.querySelector('#col-'+a+' .col-body');
    const d=document.createElement('div');
    d.className='user-bubble';
    d.textContent=msg;
    body.appendChild(d);
    body.scrollTop=body.scrollHeight;
  });
}

function addUserToAgent(agentId,msg){
  const body=document.querySelector('#col-'+agentId+' .col-body');
  if(!body) return;
  const d=document.createElement('div');
  d.className='user-bubble';
  d.style.borderStyle='dashed';
  d.textContent=msg;
  body.appendChild(d);
  body.scrollTop=body.scrollHeight;
}

function parseDirectMessage(text){
  const m=text.match(/^\/([a-zA-Z0-9_-]+)\s+(.+)$/);
  if(!m) return null;
  return {agent:m[1], message:m[2].trim()};
}

function stopAgent(id){
  const btn=document.getElementById('stop-'+id);
  if(btn) btn.disabled=true;
  fetch('/roundtable/stop-agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:id})})
    .then(function(r){return r.json();})
    .then(function(j){
      if(!j.ok && btn) btn.disabled=false;
    })
    .catch(function(){
      if(btn) btn.disabled=false;
    });
}

async function sendPermission(id,granted){
  await fetch('/permission',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id,granted:granted})
  });
}

function appendToAgent(agent,type,data){
  const col=document.getElementById('col-'+agent);
  if(!col) return;
  const body=col.querySelector('.col-body');
  if(type==='agent_stopped'){
    col.classList.add('stopped');
    const s=document.createElement('div');
    s.className='meta';
    s.style.color='#ff5a6e';
    s.textContent='[detenido por usuario]';
    body.appendChild(s);
    body.scrollTop=body.scrollHeight;
    const btn=document.getElementById('stop-'+agent);
    if(btn) btn.disabled=true;
    if(col._lastBubble) col._lastBubble.dataset.done='1';
    return;
  }
  if(type==='agent_done'){
    const btn=document.getElementById('stop-'+agent);
    if(btn) btn.disabled=true;
  }
  if(type==='text'){
    let bubble=col._lastBubble;
    if(!bubble||bubble.dataset.done==='1'){
      bubble=document.createElement('div');
      bubble.className='agent-bubble';
      bubble.dataset.done='0';
      body.appendChild(bubble);
      col._lastBubble=bubble;
    }
    bubble.textContent=(bubble.textContent||'')+data.text;
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='thinking'){
    let th=body.querySelector('.think:last-child');
    if(!th||th.dataset.type!=='thinking'){
      th=document.createElement('div');
      th.className='think';
      th.dataset.type='thinking';
      th.textContent='[thinking]\n';
      body.appendChild(th);
    }
    th.textContent+=data.text;
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='tool_start'){
    const t=document.createElement('div');
    t.className='tool';
    t.textContent='🔧 '+data.name+'\n'+JSON.stringify(data.inputs,null,2);
    body.appendChild(t);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='tool_end'){
    const r=document.createElement('div');
    r.className='tool';
    r.style.borderLeftColor='#444';
    r.style.background='#111';
    r.textContent=(data.permitted?'✅':'❌')+' '+data.result;
    body.appendChild(r);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='permission'){
    const p=document.createElement('div');
    p.className='perm';
    p.innerHTML='<span>⛔ '+data.description+'</span>';
    const yes=document.createElement('button');
    yes.textContent='Approve';
    yes.className='approve';
    yes.onclick=function(){sendPermission(data.id,true);p.remove();};
    const no=document.createElement('button');
    no.textContent='Deny';
    no.onclick=function(){sendPermission(data.id,false);p.remove();};
    p.appendChild(yes);
    p.appendChild(no);
    body.appendChild(p);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='turn_done'){
    const m=document.createElement('div');
    m.className='meta';
    m.textContent='in:'+data.in+' out:'+data.out;
    body.appendChild(m);
    if(col._lastBubble) col._lastBubble.dataset.done='1';
  }
  else if(type==='error'){
    const e=document.createElement('div');
    e.className='agent-bubble';
    e.style.color='#ff6b6b';
    e.textContent='[error] '+data.message;
    body.appendChild(e);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='agent_done'){
    const btn=document.getElementById('stop-'+agent);
    if(btn) btn.disabled=true;
    if(col._lastBubble) col._lastBubble.dataset.done='1';
  }
}

async function sendTurnWithMessage(t){
  const inp=document.getElementById('inp');
  const btn=document.getElementById('sendBtn');
  if(!t) return;
  const direct=parseDirectMessage(t);
  if(direct){
    const targetAgent=agents.find(function(a){ return a.toLowerCase()===direct.agent.toLowerCase(); });
    if(!targetAgent){
      alert('Agente no encontrado: '+direct.agent);
      return;
    }
    inp.value='';
    btn.disabled=true;
    const stopBtnDirect=document.getElementById('stop-'+targetAgent);
    if(stopBtnDirect) stopBtnDirect.disabled=false;
    const colDirect=document.getElementById('col-'+targetAgent);
    if(colDirect) colDirect.classList.remove('stopped');
    addUserToAgent(targetAgent,'[→ '+targetAgent+'] '+direct.message);
    try{
      const resp=await fetch('/roundtable/direct',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({agent_id:targetAgent, message:direct.message})
      });
      const reader=resp.body.getReader();
      const decoder=new TextDecoder();
      let buf='';
      while(true){
        const chunk=await reader.read();
        if(chunk.done) break;
        buf+=decoder.decode(chunk.value,{stream:true});
        const lines=buf.split('\n');
        buf=lines.pop();
        for(let i=0;i<lines.length;i++){
          const line=lines[i];
          if(!line.startsWith('data: ')) continue;
          let d;
          try{d=JSON.parse(line.slice(6));}catch(_){continue;}
          if(d.agent) appendToAgent(d.agent,d.type,d);
        }
      }
    }catch(err){
      alert('[network] '+err);
    }finally{
      btn.disabled=false;
      inp.focus();
    }
    return;
  }
  inp.value='';
  btn.disabled=true;
  agents.forEach(function(a){
    const stopBtn=document.getElementById('stop-'+a);
    if(stopBtn) stopBtn.disabled=false;
    const col=document.getElementById('col-'+a);
    if(col) col.classList.remove('stopped');
  });
  addUserToAll(t);
  try{
    const resp=await fetch('/roundtable/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:t})
    });
    const reader=resp.body.getReader();
    const decoder=new TextDecoder();
    let buf='';
    let gotDone=false;
    while(true){
      const chunk=await reader.read();
      if(chunk.done) break;
      buf+=decoder.decode(chunk.value,{stream:true});
      const lines=buf.split('\n');
      buf=lines.pop();
      for(let i=0;i<lines.length;i++){
        const line=lines[i];
        if(!line.startsWith('data: ')) continue;
        let d;
        try{d=JSON.parse(line.slice(6));}catch(_){continue;}
        if(d.type==='done'){gotDone=true;}
        if(d.agent) appendToAgent(d.agent,d.type,d);
      }
    }
    // if proactive is on and we got a clean done, auto-fire next round
    if(gotDone && proactiveMode && autoRoundsLeft>0){
      autoRoundsLeft--;
      setTimeout(function(){
        sendTurnWithMessage('Proactive mode active keep working');
      },800);
    }
  }catch(err){
    alert('[network] '+err);
  }finally{
    btn.disabled=false;
    inp.focus();
  }
}

async function sendTurn(){
  const t=document.getElementById('inp').value.trim();
  if(!t) return;
  if(proactiveMode){
    autoRoundsLeft=10; // max 10 auto rounds when user manually triggers
  }
  await sendTurnWithMessage(t);
}

async function restoreRt(){
  try{
    const r = await fetch('/roundtable/status');
    const j = await r.json();
    if(j.active && j.agents && j.agents.length){
      agents = j.agents;
      active = true;
      document.getElementById('setup').style.display='none';
      document.getElementById('grid').style.display='grid';
      document.getElementById('inputArea').style.display='flex';
      const grid = document.getElementById('grid');
      grid.innerHTML = '';
      agents.forEach(function(a){
        const col = document.createElement('div');
        col.className = 'col';
        col.id = 'col-' + a;
        col.innerHTML = '<div class="col-head"><span>' + a + '</span><button class="stop-btn" id="stop-' + a + '" onclick="stopAgent(\'' + a + '\')">Stop</button></div><div class="col-body"></div>';
        grid.appendChild(col);
      });
      if(j.history && j.history.length){
        j.history.forEach(function(h){
          if(h.agent === 'Usuario'){
            addUserToAll(h.text);
          } else {
            appendToAgent(h.agent, 'text', {text: h.text});
            const col = document.getElementById('col-' + h.agent);
            if(col && col._lastBubble){
              col._lastBubble.dataset.done = '1';
            }
          }
        });
      }
    }
  }catch(_){}
}

document.getElementById('inp').addEventListener('keydown',function(e){
  if(e.key==='Enter' && !e.shiftKey){
    e.preventDefault();
    sendTurn();
  }
});

restoreRt();
</script>
</body></html>"""

    RT_PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dulus WebChat</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Archivo+Black&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0a0a;--bg2:#0f0f12;--bg3:#15151a;--bg4:#1a1a20;
  --ink:#f0e8df;--dim:#6a6470;--dim2:#3a3840;
  --accent:#ff6b1f;--accent2:#ffb347;
  --mono:'JetBrains Mono',monospace;
  --display:'Archivo Black','Impact',sans-serif;
  --radius:4px;
  --green:#7cffb5;--red:#ff5a6e;--yellow:#ffd166;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;font-size:16px}
body{background:var(--bg);color:var(--ink);font-family:var(--mono);height:100vh;display:flex;flex-direction:column;position:relative;overflow:hidden}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--accent);border-radius:3px}
.grid-bg{
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(rgba(255,107,31,.06) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,107,31,.06) 1px,transparent 1px);
  background-size:40px 40px;
  mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);
}
#app{display:flex;height:100vh;overflow:hidden;position:relative}

/* ===== Sidebar ===== */
#sidebar{
  width:260px;min-width:260px;background:var(--bg2);border-right:1px solid rgba(255,107,31,.12);
  display:flex;flex-direction:column;transition:width .25s ease,min-width .25s ease;margin-left:0;
  position:relative;z-index:200;height:100vh
}
#sidebar.collapsed{width:48px;min-width:48px}
#sidebar.collapsed .sidebar-expanded{display:none!important}
#sidebar:not(.collapsed) .sidebar-collapsed{display:none!important}
.sidebar-collapsed{display:flex;flex-direction:column;align-items:center;height:100%;padding:12px 0}
.sidebar-logo-btn{
  width:32px;height:32px;background:var(--accent);clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);
  display:grid;place-items:center;color:#000;font-size:16px;font-weight:800;cursor:pointer;border:none;flex-shrink:0
}
.sidebar-collapsed .sidebar-logo-btn{margin-bottom:auto}
.sidebar-collapsed .sidebar-bottom-btn{
  width:32px;height:32px;display:flex;align-items:center;justify-content:center;
  background:transparent;border:1px solid var(--dim2);border-radius:var(--radius);
  color:var(--dim);cursor:pointer;transition:all .2s;margin-top:6px;padding:0
}
.sidebar-collapsed .sidebar-bottom-btn:hover{border-color:var(--accent);color:var(--accent);background:rgba(255,107,31,.1)}
.sidebar-expanded{display:flex;flex-direction:column;height:100%}
.sidebar-header{
  display:flex;align-items:center;gap:10px;padding:16px;border-bottom:1px solid rgba(255,255,255,.05);flex-shrink:0
}
.sidebar-header h2{font-family:var(--display);font-size:14px;letter-spacing:-.01em;color:var(--ink)}
.sidebar-search{padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.05);flex-shrink:0}
.sidebar-search input{
  width:100%;background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:8px 12px;
  border-radius:var(--radius);font-family:var(--mono);font-size:12px;outline:none;transition:border-color .2s
}
.sidebar-search input:focus{border-color:var(--accent)}
.sidebar-search input::placeholder{color:var(--dim)}
#sessionList{flex:1;overflow-y:auto;padding:8px}
.session-item{
  display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--radius);
  cursor:pointer;transition:background .15s;border-left:3px solid transparent;margin-bottom:2px;
  position:relative;user-select:none
}
.session-item:hover{background:rgba(255,255,255,.03)}
.session-item.active{
  background:rgba(255,107,31,.08);border-left-color:var(--accent)
}
.session-icon{
  width:28px;height:28px;min-width:28px;border-radius:var(--radius);background:var(--bg3);
  display:grid;place-items:center;font-size:12px;color:var(--dim);border:1px solid var(--dim2)
}
.session-item.active .session-icon{border-color:var(--accent);color:var(--accent)}
.session-info{flex:1;min-width:0;overflow:hidden}
.session-title{
  font-size:12px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  font-weight:500;line-height:1.3
}
.session-time{font-size:10px;color:var(--dim);margin-top:2px}
.session-item.active .session-title{color:var(--accent2)}
.session-actions{
  display:flex;gap:2px;opacity:0;transition:opacity .15s
}
.session-item:hover .session-actions{opacity:1}
.session-actions button{
  width:24px;height:24px;display:flex;align-items:center;justify-content:center;
  background:transparent;border:none;color:var(--dim);cursor:pointer;border-radius:3px;transition:all .15s;
  padding:0
}
.session-actions button:hover{background:rgba(255,255,255,.08);color:var(--accent)}
.session-item.renaming .session-info{display:none}
.session-item.renaming .session-actions{display:none}
.session-rename-input{
  flex:1;background:var(--bg3);color:var(--ink);border:1px solid var(--accent);padding:6px 8px;
  border-radius:var(--radius);font-family:var(--mono);font-size:12px;outline:none
}
.sidebar-bottom{
  border-top:1px solid rgba(255,255,255,.05);padding:10px 16px;display:flex;gap:6px;flex-shrink:0
}
.sidebar-bottom button{
  flex:1;display:flex;align-items:center;justify-content:center;gap:6px;
  background:var(--bg3);color:var(--dim);border:1px solid var(--dim2);padding:8px 0;
  border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:700;
  letter-spacing:.05em;text-transform:uppercase;transition:all .2s
}
.sidebar-bottom button:hover{background:rgba(255,107,31,.1);border-color:var(--accent);color:var(--accent)}
.sidebar-bottom button svg{width:14px;height:14px}

/* ===== Main ===== */
#main{flex:1;display:flex;flex-direction:column;min-width:0;position:relative}

/* ===== Header ===== */
header{
  padding:0 24px;height:56px;background:rgba(10,10,10,.7);backdrop-filter:blur(16px);
  border-bottom:1px solid rgba(255,107,31,.12);display:flex;justify-content:space-between;
  align-items:center;gap:10px;position:relative;z-index:100
}
header .header-left{display:flex;align-items:center;gap:12px}
header h1{
  font-family:var(--display);font-size:18px;letter-spacing:-.02em;color:var(--ink);
  display:flex;align-items:center;gap:12px
}
header h1::before{
  content:"\25b2";font-size:18px;color:#000;background:var(--accent);width:32px;height:32px;
  display:grid;place-items:center;clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%)
}
header .model{font-size:11px;color:var(--dim)}
header a,header button{
  background:var(--bg2);color:var(--dim);border:1px solid var(--dim2);padding:6px 12px;
  border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;text-decoration:none;transition:background .2s,border-color .2s,color .2s
}
header a:hover,header button:hover{background:rgba(255,107,31,.1);border-color:var(--accent);color:var(--accent)}
#sidebarToggle{
  display:none;width:36px;height:36px;align-items:center;justify-content:center;
  background:transparent;border:1px solid var(--dim2);border-radius:var(--radius);
  color:var(--dim);cursor:pointer;transition:all .2s;padding:0
}
#sidebarToggle:hover{border-color:var(--accent);color:var(--accent)}

/* ===== Log ===== */
#log{flex:1;overflow-y:auto;padding:24px 40px;display:flex;flex-direction:column;gap:16px;position:relative;z-index:1}
.msg{max-width:780px;padding:12px 16px;border-radius:6px;white-space:pre-wrap;word-wrap:break-word;font-size:14px}
.user{align-self:flex-end;background:rgba(255,107,31,.1);border:1px solid rgba(255,107,31,.25)}
.assistant{align-self:flex-start;background:var(--bg3);border:1px solid var(--dim2)}
.meta{font-size:10px;color:var(--dim);margin-top:6px}
.err{color:#ff5a6e;border-color:rgba(255,90,110,.4)!important}

/* ===== Input ===== */
#inputArea{
  display:flex;gap:10px;padding:16px 40px;background:var(--bg2);border-top:1px solid var(--dim2);
  position:relative;z-index:100
}
textarea{
  flex:1;background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:12px;
  border-radius:var(--radius);font-family:var(--mono);font-size:14px;resize:none;height:64px;
  outline:none;transition:border-color .2s
}
textarea:focus{border-color:var(--accent)}
textarea::placeholder{color:var(--dim)}
button.send{
  background:var(--accent);color:#000;border:none;padding:0 24px;border-radius:var(--radius);
  font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  cursor:pointer;transition:background .2s
}
button.send:hover{background:var(--accent2)}
button.send:disabled{opacity:.4;cursor:not-allowed}

/* ===== Extras ===== */
.think{
  font-size:11px;color:var(--dim);margin-top:8px;padding:8px 12px;border-left:2px solid var(--dim2);
  background:rgba(0,0,0,.2);white-space:pre-wrap
}
.tool{
  font-size:11px;color:#a39ca8;margin-top:8px;padding:8px 12px;border-left:2px solid var(--accent);
  background:rgba(255,107,31,.04);white-space:pre-wrap
}
.tool-result{
  font-size:11px;color:var(--dim);margin-top:4px;padding:8px 12px;border-left:2px solid var(--dim2);
  background:rgba(0,0,0,.2);white-space:pre-wrap;max-height:200px;overflow-y:auto
}
.perm{
  font-size:12px;color:#ffd166;margin-top:8px;padding:12px;border:1px solid rgba(255,209,102,.25);
  background:rgba(255,209,102,.1);display:flex;gap:10px;align-items:center;flex-wrap:wrap
}
.perm button{background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:6px 14px;border-radius:3px;cursor:pointer;font-weight:700}
.perm button.approve{background:var(--accent);color:#000;border:none}

/* ===== Context Menu ===== */
#ctxMenu{
  position:fixed;background:var(--bg4);border:1px solid var(--dim2);border-radius:var(--radius);
  padding:4px;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,.5);display:none;min-width:140px
}
#ctxMenu .ctx-item{
  display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:3px;
  cursor:pointer;font-size:12px;color:var(--ink);transition:background .15s;border:none;background:transparent;
  width:100%;font-family:var(--mono)
}
#ctxMenu .ctx-item:hover{background:rgba(255,107,31,.15);color:var(--accent2)}
#ctxMenu .ctx-item svg{width:14px;height:14px;color:var(--dim);flex-shrink:0}
#ctxMenu .ctx-item:hover svg{color:var(--accent)}
#ctxMenu .ctx-separator{height:1px;background:var(--dim2);margin:4px 0}

/* ===== Toast ===== */
#toastContainer{
  position:fixed;top:16px;right:16px;z-index:10000;display:flex;flex-direction:column;gap:8px;pointer-events:none
}
.toast{
  background:var(--bg4);border:1px solid var(--dim2);border-radius:var(--radius);padding:12px 16px;
  font-size:12px;color:var(--ink);box-shadow:0 4px 16px rgba(0,0,0,.5);
  display:flex;align-items:center;gap:10px;min-width:240px;max-width:340px;
  animation:toastIn .25s ease;pointer-events:auto;position:relative;overflow:hidden
}
.toast::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--dim)}
.toast.success::before{background:var(--green)}
.toast.error::before{background:var(--red)}
.toast.info::before{background:var(--accent)}
@keyframes toastIn{from{opacity:0;transform:translateX(40px)}to{opacity:1;transform:translateX(0)}}
@keyframes toastOut{from{opacity:1;transform:translateX(0)}to{opacity:0;transform:translateX(40px)}}
.toast svg{width:16px;height:16px;flex-shrink:0}
.toast.success svg{color:var(--green)}
.toast.error svg{color:var(--red)}
.toast.info svg{color:var(--accent)}

/* ===== Mobile ===== */
@media(max-width:768px){
  #sidebar{position:fixed;left:0;top:0;bottom:0;z-index:500;transform:translateX(-100%);transition:transform .3s ease;box-shadow:none}
  #sidebar.open{transform:translateX(0);box-shadow:4px 0 24px rgba(0,0,0,.5)}
  #sidebarOverlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:400;backdrop-filter:blur(2px)}
  #sidebarOverlay.open{display:block}
  #sidebarToggle{display:flex}
  #log{padding:16px 20px}
  .msg{max-width:92%}
  #inputArea{padding:16px 20px}
  header{padding:0 16px;height:52px}
}
@media(max-width:600px){
  header{height:auto;min-height:52px;padding:8px 16px;flex-wrap:wrap}
  header h1{font-size:15px}
  header h1::before{width:26px;height:26px;font-size:14px}
  header a,header button{font-size:10px;padding:5px 8px}
}
</style><style id="dynamic-theme"></style></head><body>
<div class="grid-bg"></div>
<div id="sidebarOverlay"></div>
<div id="app">
<!-- ===== SIDEBAR ===== -->
<nav id="sidebar">
  <div class="sidebar-collapsed">
    <button class="sidebar-logo-btn" onclick="toggleSidebar()" title="Expand">&#9650;</button>
    <button class="sidebar-bottom-btn" onclick="newChat()" title="New Chat">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
    </button>
    <button class="sidebar-bottom-btn" onclick="refreshSessions()" title="Refresh">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
    </button>
    <button class="sidebar-bottom-btn" onclick="toggleSidebar()" title="Expand" style="margin-top:auto">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 5l7 7-7 7"/><path d="M5 5l7 7-7 7"/></svg>
    </button>
  </div>
  <div class="sidebar-expanded">
    <div class="sidebar-header">
      <div class="sidebar-logo-btn" style="cursor:default">&#9650;</div>
      <h2>DULUS</h2>
    </div>
    <div class="sidebar-search">
      <input type="text" id="searchInput" placeholder="Search chats..." oninput="filterSessions()">
    </div>
    <div id="sessionList"></div>
    <div class="sidebar-bottom">
      <button onclick="newChat()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>New</span>
      </button>
      <button onclick="refreshSessions()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
      </button>
      <button onclick="toggleSidebar()" title="Collapse">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 17l-5-5 5-5"/><path d="M18 17l-5-5 5-5"/></svg>
      </button>
    </div>
  </div>
</nav>
<!-- ===== MAIN ===== -->
<div id="main">
<header>
  <div class="header-left">
    <button id="sidebarToggle" onclick="toggleSidebar()">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <h1>DULUS WEBCHAT</h1>
  </div>
  <select id="personaSelect" style="background:var(--bg3);color:var(--dim);border:1px solid var(--dim2);padding:4px 10px;border-radius:var(--radius);font-family:var(--mono);font-size:12px;outline:none;cursor:pointer;flex:1;max-width:250px;margin:0 15px;text-align:center"></select>
  <div>
    <a href="/roundtable">Mesa Redonda</a>
    <a href="/dashboard">Task Manager</a>
    <button onclick="clearChat()">clear</button>
  </div>
</header>
<div id="log"></div>
<div id="inputArea">
  <textarea id="inp" placeholder="Mensaje a Dulus... (Enter envia, Shift+Enter nueva linea)" autofocus></textarea>
  <button class="send" id="sendBtn">SEND</button>
</div>
</div>
</div>

<!-- Context Menu -->
<div id="ctxMenu">
  <button class="ctx-item" onclick="ctxRename()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
    Rename
  </button>
  <div class="ctx-separator"></div>
  <button class="ctx-item" onclick="ctxDelete()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
    Delete
  </button>
</div>

<!-- Toast Container -->
<div id="toastContainer"></div>
<script>
// ===== THEME SYNC =====
(function(){
  function ensureThemeStyle(){
    var el = document.getElementById('dynamic-theme');
    if(!el){
      el = document.createElement('style');
      el.id = 'dynamic-theme';
      document.head.appendChild(el);
    }
    return el;
  }
  async function applyTheme(name){
    name = name || localStorage.getItem('dulus-theme') || 'dulus';
    try{
      var res = await fetch('/api/themes/' + encodeURIComponent(name) + '/css');
      var css = await res.text();
      if(css){
        ensureThemeStyle().textContent = css;
        localStorage.setItem('dulus-theme', name);
      }
    }catch(e){}
  }
  applyTheme();
})();

// ===== STATE =====
const ACTIVE_KEY = 'dulus_active_session';
const SIDEBAR_COLLAPSED_KEY = 'dulus_sidebar_collapsed';
const DEFAULT_SESSION_ID = 'default';

let sessions = [];
let activeSessionId = DEFAULT_SESSION_ID;
let ctxTargetId = null;
let isMobile = window.innerWidth < 768;
let renamingId = null;

// ===== TOAST =====
function showToast(message, type){
  var c = document.getElementById('toastContainer');
  var t = document.createElement('div');
  t.className = 'toast ' + (type || 'info');
  var icon = '';
  if(type === 'success'){
    icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
  }else if(type === 'error'){
    icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
  }else{
    icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
  }
  t.innerHTML = icon + '<span>' + escapeHtml(message) + '</span>';
  c.appendChild(t);
  setTimeout(function(){ t.classList.add('exit'); setTimeout(function(){ t.remove(); }, 250); }, 3000);
}

// ===== UTILS =====
function escapeHtml(t){
  var d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}
function genId(){ return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
function formatTime(ts){
  var d = new Date(ts);
  var now = new Date();
  if(d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  var yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1);
  if(d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], {month: 'short', day: 'numeric'});
}

// ===== SESSION STORAGE =====
function loadSessions(){
  // Server is the source of truth; localStorage no longer dictates startup session
  fetch('/api/sessions')
    .then(function(r){ return r.json(); })
    .then(function(data){
      if(data && data.length){
        sessions = data.map(function(s){
          return {
            id: s.id,
            title: s.title,
            timestamp: s.saved_at ? new Date(s.saved_at).getTime() : Date.now(),
            messages: s.messages || []
          };
        });
        renderSessions();
        // Removed selectSession(activeSessionId) so it does not override server on init!
        return;
      }
      // Server fully empty — create a default session structure silently
      sessions = [{id: DEFAULT_SESSION_ID, title: 'Chat', timestamp: Date.now(), messages: []}];
      renderSessions();
    })
    .catch(function(e){
      // Network down — start with a blank default session silently
      sessions = [{id: DEFAULT_SESSION_ID, title: 'Chat', timestamp: Date.now(), messages: []}];
      renderSessions();
    });
}
function saveActive(){ localStorage.setItem(ACTIVE_KEY, activeSessionId); }
function getActiveSession(){
  return sessions.find(function(s){ return s.id === activeSessionId; }) || sessions[0];
}
function updateActiveMessages(msgs){
  var s = getActiveSession();
  if(s){ s.messages = msgs; s.timestamp = Date.now(); }
}
function updateSessionTitleFromMessages(){
  var s = getActiveSession();
  if(!s) return;
  var firstUser = s.messages.find(function(m){ return m.role === 'user'; });
  if(firstUser && s.title === 'Chat'){
    var txt = (typeof firstUser.content === 'string' ? firstUser.content : '').slice(0, 40);
    if(txt) s.title = txt;
    renderSessions();
  }
}

// ===== SIDEBAR UI =====
function renderSessions(){
  var list = document.getElementById('sessionList');
  var q = document.getElementById('searchInput').value.toLowerCase();
  var filtered = sessions.filter(function(s){ return !q || s.title.toLowerCase().indexOf(q) >= 0; });
  if(!filtered.length){
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--dim);font-size:11px">No chats found</div>';
    return;
  }
  var html = '';
  for(var i = 0; i < filtered.length; i++){
    var s = filtered[i];
    var isActive = s.id === activeSessionId;
    var isRenaming = s.id === renamingId;
    if(isRenaming){
      html += '<div class="session-item active renaming" data-id="' + s.id + '">' +
        '<div class="session-icon">&#9650;</div>' +
        '<input class="session-rename-input" value="' + escapeHtml(s.title) + '" ' +
        'onkeydown="renameKey(event,\'' + s.id + '\')" onblur="finishRename(\'' + s.id + '\')" id="rename-' + s.id + '">' +
        '</div>';
      continue;
    }
    html += '<div class="session-item ' + (isActive ? 'active' : '') + '" data-id="' + s.id + '" ' +
      'onclick="selectSession(\'' + s.id + '\')" oncontextmenu="showCtx(event,\'' + s.id + '\')">' +
      '<div class="session-icon">&#9650;</div>' +
      '<div class="session-info">' +
        '<div class="session-title">' + escapeHtml(s.title) + '</div>' +
        '<div class="session-time">' + formatTime(s.timestamp) + '</div>' +
      '</div>' +
      '<div class="session-actions" onclick="event.stopPropagation()">' +
        '<button onclick="startRename(\'' + s.id + '\')" title="Rename">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>' +
        '</button>' +
        '<button onclick="deleteSession(\'' + s.id + '\')" title="Delete">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
        '</button>' +
      '</div>' +
    '</div>';
  }
  list.innerHTML = html;
  if(renamingId){
    var inp = document.getElementById('rename-' + renamingId);
    if(inp){ inp.focus(); inp.select(); }
  }
}

function startRename(id){
  renamingId = id; renderSessions();
}
function finishRename(id){
  var inp = document.getElementById('rename-' + id);
  if(inp){
    var v = inp.value.trim();
    if(v){
      var s = sessions.find(function(x){ return x.id === id; });
      if(s){ s.title = v; }
    }
  }
  renamingId = null; renderSessions();
}
function renameKey(e, id){
  if(e.key === 'Enter'){ e.preventDefault(); finishRename(id); }
  else if(e.key === 'Escape'){ renamingId = null; renderSessions(); }
}
function filterSessions(){ renderSessions(); }

async function selectSession(id){
  activeSessionId = id; saveActive();
  renderSessions();
  var s = getActiveSession();
  if(s && s.messages){
    log.innerHTML = '';
    currentAssistant = null;
    currentText = '';
    for(var i = 0; i < s.messages.length; i++){
      var m = s.messages[i];
      if(m.role === 'user') add('user', m.content);
      else if(m.role === 'assistant'){
        var msgDiv = ensureAssistant();
        if(m.thinking){
          var th = document.createElement('div');
          th.className = 'think';
          th.textContent = m.thinking;
          msgDiv.appendChild(th);
        }
        var text = typeof m.content === 'string' ? m.content : '';
        if(Array.isArray(m.content)){
          var tc = m.content.find(function(c){ return c.type === 'text'; });
          if(tc) text = tc.text;
        }
        if(text){
          var tn = document.createTextNode(text);
          msgDiv.appendChild(tn);
        }
        if(m.tool_calls && m.tool_calls.length){
          m.tool_calls.forEach(function(tc){
            var tDiv = document.createElement('div');
            tDiv.className = 'tool';
            var fn = tc.function || tc;
            tDiv.textContent = '\ud83d\udd27 ' + (fn.name || 'tool') + '\n' + JSON.stringify(fn.arguments || {}, null, 2);
            msgDiv.appendChild(tDiv);
          });
        }
        currentAssistant = null; // reset for next message
      } else if(m.role === 'tool'){
        var msgDiv = ensureAssistant();
        var rDiv = document.createElement('div');
        rDiv.className = 'tool-result';
        rDiv.textContent = '\u2705 ' + m.content;
        msgDiv.appendChild(rDiv);
        currentAssistant = null;
      }
    }
  }
  closeMobileSidebar();
  // Sync server state with this session so the backend talks to the right conversation
  try{
    await fetch('/api/session/load', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({messages: s ? s.messages : [], session_id: id})
    });
  }catch(_){}
}

function newChat(){
  fetch('/clear', {method: 'POST'}).then(function(){
    var newS = {id: genId(), title: 'Chat', timestamp: Date.now(), messages: []};
    sessions.unshift(newS); activeSessionId = newS.id;
    saveActive();
    log.innerHTML = '';
    currentAssistant = null;
    currentText = '';
    renderSessions();
    closeMobileSidebar();
    showToast('New chat started', 'success');
  });
}

function deleteSession(id){
  var s = sessions.find(function(x){ return x.id === id; });
  if(!s) return;
  if(!confirm('Delete "' + s.title + '"?')) return;
  fetch('/api/sessions/' + encodeURIComponent(id), {method: 'DELETE'}).catch(function(){});
  sessions = sessions.filter(function(x){ return x.id !== id; });
  if(sessions.length === 0){
    var ns = {id: genId(), title: 'Chat', timestamp: Date.now(), messages: []};
    sessions.push(ns); activeSessionId = ns.id;
  }else if(activeSessionId === id){
    activeSessionId = sessions[0].id;
  }
  saveActive();
  selectSession(activeSessionId);
  renderSessions();
  showToast('Chat deleted', 'info');
}

function refreshSessions(){
  syncWithServer(function(){
    showToast('Chats refreshed', 'success');
  });
}

// ===== CONTEXT MENU =====
function showCtx(e, id){
  e.preventDefault();
  ctxTargetId = id;
  var menu = document.getElementById('ctxMenu');
  menu.style.display = 'block';
  var x = e.clientX, y = e.clientY;
  if(x + 160 > window.innerWidth) x = window.innerWidth - 170;
  if(y + 80 > window.innerHeight) y = window.innerHeight - 90;
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
}
function hideCtx(){ document.getElementById('ctxMenu').style.display = 'none'; ctxTargetId = null; }
function ctxRename(){ if(ctxTargetId) startRename(ctxTargetId); hideCtx(); }
function ctxDelete(){ if(ctxTargetId) deleteSession(ctxTargetId); hideCtx(); }
document.addEventListener('click', function(e){
  if(!e.target.closest('#ctxMenu')) hideCtx();
});

// ===== SIDEBAR TOGGLE =====
function toggleSidebar(){
  if(window.innerWidth < 768){
    var sb = document.getElementById('sidebar');
    if(sb.classList.contains('open')) closeMobileSidebar();
    else openMobileSidebar();
  }else{
    var sb = document.getElementById('sidebar');
    sb.classList.toggle('collapsed');
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sb.classList.contains('collapsed') ? '1' : '0');
  }
}
function initSidebar(){
  var collapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
  if(collapsed === '1') document.getElementById('sidebar').classList.add('collapsed');
}

// ===== MOBILE SIDEBAR =====
function openMobileSidebar(){
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebarOverlay').classList.add('open');
}
function closeMobileSidebar(){
  if(window.innerWidth >= 768) return;
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('open');
}
document.getElementById('sidebarOverlay').addEventListener('click', closeMobileSidebar);

// ===== CHAT FUNCTIONS =====
var log = document.getElementById('log');
var inp = document.getElementById('inp');
var btn = document.getElementById('sendBtn');
var currentAssistant = null;
var currentText = '';

function add(role, text, extra){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  if(extra){
    var m = document.createElement('div');
    m.className = 'meta';
    m.textContent = extra;
    d.appendChild(m);
  }
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function ensureAssistant(){
  if(!currentAssistant){
    currentAssistant = add('assistant', '');
  }
  return currentAssistant;
}

function appendText(text){
  ensureAssistant();
  currentText += text;
  currentAssistant.textContent = currentText;
  log.scrollTop = log.scrollHeight;
}

function appendThinking(text){
  ensureAssistant();
  var th = currentAssistant.querySelector('.think');
  if(!th){
    th = document.createElement('div');
    th.className = 'think';
    th.textContent = '[thinking]';
    currentAssistant.appendChild(th);
  }
  th.textContent += text;
  log.scrollTop = log.scrollHeight;
}

function startTool(name, inputs){
  ensureAssistant();
  if(name === 'working...') {
    var t = currentAssistant.querySelector('.tool.working');
    if(!t){
        t = document.createElement('div');
        t.className = 'tool working';
        t.textContent = '\ud83d\udce6 consolidando herramientas...';
        currentAssistant.appendChild(t);
    }
    return;
  }
  var t = document.createElement('div');
  t.className = 'tool';
  t.textContent = '\ud83d\udd27 ' + name + '\n' + JSON.stringify(inputs, null, 2);
  currentAssistant.appendChild(t);
  log.scrollTop = log.scrollHeight;
}

function endTool(name, result, permitted){
  ensureAssistant();
  var work = currentAssistant.querySelector('.tool.working');
  if(work) work.remove();
  
  var r = document.createElement('div');
  r.className = 'tool-result';
  r.textContent = (permitted ? '\u2705' : '\u274c') + ' ' + result;
  currentAssistant.appendChild(r);
  log.scrollTop = log.scrollHeight;
}

function showPermission(id, desc){
  ensureAssistant();
  var p = document.createElement('div');
  p.className = 'perm';
  p.innerHTML = '<span>\u26d4 ' + desc + '</span>';
  var yes = document.createElement('button');
  yes.textContent = 'Approve';
  yes.className = 'approve';
  yes.onclick = function(){ sendPermission(id, true); p.remove(); };
  var no = document.createElement('button');
  no.textContent = 'Deny';
  no.onclick = function(){ sendPermission(id, false); p.remove(); };
  p.appendChild(yes);
  p.appendChild(no);
  currentAssistant.appendChild(p);
  log.scrollTop = log.scrollHeight;
}

async function sendPermission(id, granted){
  await fetch('/permission', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id: id, granted: granted})
  });
}

async function sendMessage(){
  var t = inp.value.trim();
  if(!t) return;
  add('user', t);
  inp.value = '';
  btn.disabled = true;
  currentAssistant = null;
  currentText = '';
  try{
    var resp = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: t})
    });
    var reader = resp.body.getReader();
    var decoder = new TextDecoder();
    var buf = '';
    while(true){
      var chunk = await reader.read();
      if(chunk.done) break;
      buf += decoder.decode(chunk.value, {stream: true});
      var lines = buf.split('\n');
      buf = lines.pop();
      for(var i = 0; i < lines.length; i++){
        var line = lines[i];
        if(!line.startsWith('data: ')) continue;
        var d;
        try{ d = JSON.parse(line.slice(6)); }catch(_){ continue; }
        if(d.type === 'text') appendText(d.text);
        else if(d.type === 'thinking') appendThinking(d.text);
        else if(d.type === 'tool_start') startTool(d.name, d.inputs);
        else if(d.type === 'tool_end') endTool(d.name, d.result, d.permitted);
        else if(d.type === 'permission') showPermission(d.id, d.description);
        else if(d.type === 'turn_done'){
          var meta = document.createElement('div');
          meta.className = 'meta';
          var txt = 'in:' + d.in + ' out:' + d.out;
          if(d.cache_read) txt += ' [cache hit: ' + d.cache_read + ']';
          if(d.cache_write) txt += ' [cache new: ' + d.cache_write + ']';
          meta.textContent = txt;
          ensureAssistant().appendChild(meta);
        }
        else if(d.type === 'error') appendText('\n[error] ' + d.message);
      }
    }
  }catch(err){
    add('assistant', '[network] ' + err, '').classList.add('err');
  }finally{
    btn.disabled = false;
    inp.focus();
    syncWithServer();
  }
}

async function clearChat(){
  await fetch('/clear', {method: 'POST'});
  log.innerHTML = '';
  currentAssistant = null;
  currentText = '';
  var s = getActiveSession();
  if(s){ s.messages = []; s.timestamp = Date.now(); }
  showToast('Chat cleared', 'info');
}

async function syncWithServer(cb){
  if(btn.disabled) return;
  try{
    var rh = await fetch('/api/chat/history');
    if(rh.ok){
      var ht = await rh.json();
      
      var switched = false;
      // ADOPT SERVER'S ACTIVE SESSION TO PREVENT DESYNC
      if(ht.session_id && activeSessionId !== ht.session_id) {
          activeSessionId = ht.session_id;
          saveActive();
          switched = true;
          if(!sessions.find(function(x){ return x.id === activeSessionId; })){
              sessions.unshift({id: activeSessionId, title: 'Chat', timestamp: Date.now(), messages: ht.messages});
          }
          // Full render when we jump to a completely different session internally
          renderSessions();
      }
      
      var s = getActiveSession();
      var localCount = s ? s.messages.length : -1;
      // Overwrite local session if server has a different message count OR we just adopted a new session
      if(switched || ht.messages.length !== localCount){
        updateActiveMessages(ht.messages);
        updateSessionTitleFromMessages();
        var wasNearBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 50;
        log.innerHTML = '';
        currentAssistant = null;
        currentText = '';
        for(var i = 0; i < ht.messages.length; i++){
          var m = ht.messages[i];
          if(m.role === 'user') add('user', m.content);
          else if(m.role === 'assistant' || m.role === 'system'){
            var text = typeof m.content === 'string' ? m.content : '';
            if(Array.isArray(m.content)){
              var tc = m.content.find(function(c){ return c.type === 'text'; });
              if(tc) text = tc.text;
            }
            if(text) add(m.role, text);
          }
        }
        if(wasNearBottom) log.scrollTop = log.scrollHeight;
        renderSessions();
      }
    }
    var rp = await fetch('/api/personas');
    if(rp.ok){
      var jp = await rp.json();
      var sel = document.getElementById('personaSelect');
      var activeKeys = Object.keys(jp.active || {});
      sel.innerHTML = jp.personas.map(function(p){
        var isSelected = activeKeys.indexOf(p.name) >= 0 ? 'selected' : '';
        return '<option value="' + p.name + '" ' + isSelected + '>' + p.name + ' (' + p.role + ')</option>';
      }).join('');
      sel.onchange = async function(e){
        await fetch('/api/personas/activate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id: e.target.value})
        });
      };
    }
  }catch(_){}
  // Persist current session to server disk
  fetch('/api/sessions/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: activeSessionId})
  }).catch(function(){});
  if(cb) cb();
}

async function loadHist(){ return syncWithServer(); }

inp.addEventListener('keydown', function(e){
  if(e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    sendMessage();
  }
});
btn.addEventListener('click', sendMessage);

// ===== MOBILE =====
window.addEventListener('resize', function(){
  var nowMobile = window.innerWidth < 768;
  if(nowMobile !== isMobile){
    isMobile = nowMobile;
    if(!isMobile) closeMobileSidebar();
  }
});

// ===== INIT =====
(function(){
  // Prune legacy/bloated localStorage keys from older versions
  try {
    const keysToRemove = [];
    for(let i=0; i<localStorage.length; i++){
      const k = localStorage.key(i);
      // Remove keys that are not our standard ones if they are large or match legacy patterns
      if(k !== ACTIVE_KEY && k !== SIDEBAR_COLLAPSED_KEY && k !== 'dulus-theme' && k.startsWith('dulus_')){
          const val = localStorage.getItem(k);
          if(val && val.length > 5000) keysToRemove.push(k); // Likely old bulky session data
      }
    }
    keysToRemove.forEach(k => localStorage.removeItem(k));
  } catch(e) {}

  // Restore active session ID
  var savedId = localStorage.getItem(ACTIVE_KEY);
  if(savedId && savedId !== 'null') activeSessionId = savedId;
})();

loadSessions();
initSidebar();
renderSessions();
loadHist();
setInterval(function(){ syncWithServer(); }, 5000);
</script>
</body></html>"""

    # ─────────────────────── Mesa Redonda HTML ──────────────────────────
    RT_PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dulus Mesa Redonda</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Archivo+Black&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0a0a;
  --bg2:#0f0f12;
  --bg3:#15151a;
  --ink:#f0e8df;
  --dim:#6a6470;
  --dim2:#3a3840;
  --accent:#ff6b1f;
  --accent2:#ffb347;
  --mono:'JetBrains Mono',monospace;
  --display:'Archivo Black','Impact',sans-serif;
  --radius:4px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;font-size:16px}
body{background:var(--bg);color:var(--ink);font-family:var(--mono);height:100vh;display:flex;flex-direction:column;position:relative}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--accent);border-radius:3px}

.grid-bg{
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(rgba(255,107,31,.06) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,107,31,.06) 1px,transparent 1px);
  background-size:40px 40px;
  mask-image:radial-gradient(ellipse at center,black 30%,transparent 80%);
}

header{padding:0 40px;height:64px;background:rgba(10,10,10,.7);backdrop-filter:blur(16px);border-bottom:1px solid rgba(255,107,31,.12);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;position:relative;z-index:100}
header h1{font-family:var(--display);font-size:18px;letter-spacing:-.02em;color:var(--ink);display:flex;align-items:center;gap:12px}
header h1::before{content:"▲";font-size:18px;color:#000;background:var(--accent);width:32px;height:32px;display:grid;place-items:center;clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);}

header a,header button{background:var(--bg2);color:var(--dim);border:1px solid var(--dim2);padding:6px 12px;border-radius:var(--radius);cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;text-decoration:none;transition:background .2s,border-color .2s,color .2s}
header a:hover,header button:hover{background:rgba(255,107,31,.1);border-color:var(--accent);color:var(--accent)}

#setup{padding:30px;display:flex;flex-direction:column;gap:16px;align-items:center;justify-content:center;flex:1;position:relative;z-index:1}
#setup h2{color:var(--accent);font-family:var(--display);font-size:32px;letter-spacing:-.02em}
#setup p{color:var(--dim);font-size:13px;letter-spacing:.1em;text-transform:uppercase}
#setup textarea{width:400px;max-width:90vw;height:120px;background:var(--bg3);border:1px solid var(--dim2);color:var(--ink);padding:12px;border-radius:var(--radius);font-family:var(--mono);font-size:13px;resize:none;outline:none;transition:border-color .2s}
#setup textarea:focus{border-color:var(--accent)}
#setup button{background:var(--accent);color:#000;border:none;padding:12px 32px;border-radius:var(--radius);font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:background .2s}
#setup button:hover{background:var(--accent2)}
#grid{display:none;flex:1;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;padding:24px 40px;overflow-y:auto;position:relative;z-index:1}
.col{background:var(--bg2);border:1px solid var(--dim2);border-radius:6px;display:flex;flex-direction:column;overflow:hidden}
.col-head{padding:12px 16px;background:var(--bg3);border-bottom:1px solid var(--dim2);font-size:12px;font-weight:700;color:var(--accent);letter-spacing:.1em;text-transform:uppercase;display:flex;justify-content:space-between;align-items:center}
.col-head .stop-btn{background:#2a0a0a;color:#ff5a6e;border:1px solid rgba(255,90,110,.4);padding:3px 10px;border-radius:3px;cursor:pointer;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;transition:background .2s,border-color .2s}
.col-head .stop-btn:hover{background:rgba(255,90,110,.15);border-color:#ff5a6e}
.col-head .stop-btn:disabled{opacity:.4;cursor:not-allowed}
.col.stopped{border-color:rgba(255,90,110,.4)}
.col.stopped .col-head{color:#ff5a6e}
.col-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.user-bubble{align-self:flex-end;background:rgba(255,107,31,.1);border:1px solid rgba(255,107,31,.25);padding:10px 14px;border-radius:6px;white-space:pre-wrap;word-wrap:break-word;font-size:13px}
.agent-bubble{align-self:flex-start;background:var(--bg3);border:1px solid var(--dim2);padding:10px 14px;border-radius:6px;white-space:pre-wrap;word-wrap:break-word;font-size:13px}
.think{font-size:11px;color:var(--dim);margin-top:6px;padding:6px 10px;border-left:2px solid var(--dim2);background:rgba(0,0,0,.2);white-space:pre-wrap}
.tool{font-size:11px;color:#a39ca8;margin-top:6px;padding:6px 10px;border-left:2px solid var(--accent);background:rgba(255,107,31,.04);white-space:pre-wrap}
.meta{font-size:10px;color:var(--dim);margin-top:6px}
.err{color:#ff5a6e}
.perm{font-size:12px;color:#ffd166;margin-top:8px;padding:12px;border:1px solid rgba(255,209,102,.25);background:rgba(255,209,102,.1);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.perm button{background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:6px 14px;border-radius:3px;cursor:pointer;font-weight:700}
.perm button.approve{background:var(--accent);color:#000;border:none}
#inputArea{display:flex;gap:10px;padding:16px 40px;background:var(--bg2);border-top:1px solid var(--dim2);position:relative;z-index:100}
textarea{flex:1;background:var(--bg3);color:var(--ink);border:1px solid var(--dim2);padding:12px;border-radius:var(--radius);font-family:var(--mono);font-size:14px;resize:none;height:64px;outline:none;transition:border-color .2s}
textarea:focus{border-color:var(--accent)}
button.send{background:var(--accent);color:#000;border:none;padding:0 24px;border-radius:var(--radius);font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:background .2s}
button.send:disabled{opacity:.4;cursor:not-allowed}
@media(max-width:600px){
header{padding:10px 20px;height:auto}
#grid{padding:16px 20px}
#inputArea{padding:16px 20px}
}
</style><style id="dynamic-theme"></style></head><body>
<div class="grid-bg"></div>
<header>
  <h1>DULUS MESA REDONDA</h1>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:12px;color:var(--dim)">
      <input type="checkbox" id="proactiveToggle" style="accent-color:var(--accent);cursor:pointer">
      <span id="proactiveLabel">Auto-turno</span>
    </label>
    <a href="/">Chat</a>
    <a href="/dashboard">Task Manager</a>
    <button onclick="location.reload()">Reiniciar</button>
  </div>
</header>
<div id="setup">
  <h2>Setup</h2>
  <p>Introduce 3 a 5 modelos (uno por linea)</p>
  <textarea id="modelsInput" placeholder="kimi-code/kimi-for-coding&#10;kimi-code2/kimi-for-coding&#10;kimi-code3/kimi-for-coding"></textarea>
  <button onclick="startRt()">Iniciar</button>
</div>
<div id="grid"></div>
<div id="inputArea" style="display:none">
  <textarea id="inp" placeholder="Mensaje a la mesa... (Enter envia)" autofocus></textarea>
  <button class="send" id="sendBtn" onclick="sendTurn()">SEND</button>
</div>
<script>
// ===== THEME SYNC =====
(function(){
  function ensureThemeStyle(){
    var el = document.getElementById('dynamic-theme');
    if(!el){
      el = document.createElement('style');
      el.id = 'dynamic-theme';
      document.head.appendChild(el);
    }
    return el;
  }
  async function applyTheme(name){
    name = name || localStorage.getItem('dulus-theme') || 'dulus';
    try{
      var res = await fetch('/api/themes/' + encodeURIComponent(name) + '/css');
      var css = await res.text();
      if(css){
        ensureThemeStyle().textContent = css;
        localStorage.setItem('dulus-theme', name);
      }
    }catch(e){}
  }
  applyTheme();
})();

let agents=[];
let active=false;
let proactiveMode=false;
let autoRoundsLeft=0;

const proactiveToggle=document.getElementById('proactiveToggle');
proactiveToggle.addEventListener('change',function(){
  proactiveMode=this.checked;
  const lbl=document.getElementById('proactiveLabel');
  lbl.textContent=proactiveMode?'Auto-turno (ON)':'Auto-turno';
  lbl.style.color=proactiveMode?'#00ffa3':'#888';
});

function startRt(){
  const raw=document.getElementById('modelsInput').value.trim().split('\n').filter(function(x){return x.trim();});
  if(raw.length<3||raw.length>5){alert('Necesitas 3 a 5 modelos');return;}
  fetch('/roundtable/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({models:raw})})
    .then(function(r){return r.json();})
    .then(function(j){
      if(!j.ok){alert(j.error);return;}
      agents=j.agents;
      active=true;
      document.getElementById('setup').style.display='none';
      document.getElementById('grid').style.display='grid';
      document.getElementById('inputArea').style.display='flex';
      const grid=document.getElementById('grid');
      grid.innerHTML='';
      agents.forEach(function(a){
        const col=document.createElement('div');
        col.className='col';
        col.id='col-'+a;
        col.innerHTML='<div class="col-head"><span>'+a+'</span><button class="stop-btn" id="stop-'+a+'" onclick="stopAgent(\''+a+'\')">Stop</button></div><div class="col-body"></div>';
        grid.appendChild(col);
      });
    });
}

function addUserToAll(msg){
  agents.forEach(function(a){
    const body=document.querySelector('#col-'+a+' .col-body');
    const d=document.createElement('div');
    d.className='user-bubble';
    d.textContent=msg;
    body.appendChild(d);
    body.scrollTop=body.scrollHeight;
  });
}

function addUserToAgent(agentId,msg){
  const body=document.querySelector('#col-'+agentId+' .col-body');
  if(!body) return;
  const d=document.createElement('div');
  d.className='user-bubble';
  d.style.borderStyle='dashed';
  d.textContent=msg;
  body.appendChild(d);
  body.scrollTop=body.scrollHeight;
}

function parseDirectMessage(text){
  const m=text.match(/^\/([a-zA-Z0-9_-]+)\s+(.+)$/);
  if(!m) return null;
  return {agent:m[1], message:m[2].trim()};
}

function stopAgent(id){
  const btn=document.getElementById('stop-'+id);
  if(btn) btn.disabled=true;
  fetch('/roundtable/stop-agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:id})})
    .then(function(r){return r.json();})
    .then(function(j){
      if(!j.ok && btn) btn.disabled=false;
    })
    .catch(function(){
      if(btn) btn.disabled=false;
    });
}

async function sendPermission(id,granted){
  await fetch('/permission',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id,granted:granted})
  });
}

function appendToAgent(agent,type,data){
  const col=document.getElementById('col-'+agent);
  if(!col) return;
  const body=col.querySelector('.col-body');
  if(type==='agent_stopped'){
    col.classList.add('stopped');
    const s=document.createElement('div');
    s.className='meta';
    s.style.color='#ff5a6e';
    s.textContent='[detenido por usuario]';
    body.appendChild(s);
    body.scrollTop=body.scrollHeight;
    const btn=document.getElementById('stop-'+agent);
    if(btn) btn.disabled=true;
    if(col._lastBubble) col._lastBubble.dataset.done='1';
    return;
  }
  if(type==='agent_done'){
    const btn=document.getElementById('stop-'+agent);
    if(btn) btn.disabled=true;
  }
  if(type==='text'){
    let bubble=col._lastBubble;
    if(!bubble||bubble.dataset.done==='1'){
      bubble=document.createElement('div');
      bubble.className='agent-bubble';
      bubble.dataset.done='0';
      body.appendChild(bubble);
      col._lastBubble=bubble;
    }
    bubble.textContent=(bubble.textContent||'')+data.text;
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='thinking'){
    let th=body.querySelector('.think:last-child');
    if(!th||th.dataset.type!=='thinking'){
      th=document.createElement('div');
      th.className='think';
      th.dataset.type='thinking';
      th.textContent='[thinking]\n';
      body.appendChild(th);
    }
    th.textContent+=data.text;
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='tool_start'){
    const t=document.createElement('div');
    t.className='tool';
    t.textContent='🔧 '+data.name+'\n'+JSON.stringify(data.inputs,null,2);
    body.appendChild(t);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='tool_end'){
    const r=document.createElement('div');
    r.className='tool';
    r.style.borderLeftColor='#444';
    r.style.background='#111';
    r.textContent=(data.permitted?'✅':'❌')+' '+data.result;
    body.appendChild(r);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='permission'){
    const p=document.createElement('div');
    p.className='perm';
    p.innerHTML='<span>⛔ '+data.description+'</span>';
    const yes=document.createElement('button');
    yes.textContent='Approve';
    yes.className='approve';
    yes.onclick=function(){sendPermission(data.id,true);p.remove();};
    const no=document.createElement('button');
    no.textContent='Deny';
    no.onclick=function(){sendPermission(data.id,false);p.remove();};
    p.appendChild(yes);
    p.appendChild(no);
    body.appendChild(p);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='turn_done'){
    const m=document.createElement('div');
    m.className='meta';
    m.textContent='in:'+data.in+' out:'+data.out;
    body.appendChild(m);
    if(col._lastBubble) col._lastBubble.dataset.done='1';
  }
  else if(type==='error'){
    const e=document.createElement('div');
    e.className='agent-bubble';
    e.style.color='#ff6b6b';
    e.textContent='[error] '+data.message;
    body.appendChild(e);
    body.scrollTop=body.scrollHeight;
  }
  else if(type==='agent_done'){
    const btn=document.getElementById('stop-'+agent);
    if(btn) btn.disabled=true;
    if(col._lastBubble) col._lastBubble.dataset.done='1';
  }
}

async function sendTurnWithMessage(t){
  const inp=document.getElementById('inp');
  const btn=document.getElementById('sendBtn');
  if(!t) return;
  const direct=parseDirectMessage(t);
  if(direct){
    const targetAgent=agents.find(function(a){ return a.toLowerCase()===direct.agent.toLowerCase(); });
    if(!targetAgent){
      alert('Agente no encontrado: '+direct.agent);
      return;
    }
    inp.value='';
    btn.disabled=true;
    const stopBtnDirect=document.getElementById('stop-'+targetAgent);
    if(stopBtnDirect) stopBtnDirect.disabled=false;
    const colDirect=document.getElementById('col-'+targetAgent);
    if(colDirect) colDirect.classList.remove('stopped');
    addUserToAgent(targetAgent,'[→ '+targetAgent+'] '+direct.message);
    try{
      const resp=await fetch('/roundtable/direct',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({agent_id:targetAgent, message:direct.message})
      });
      const reader=resp.body.getReader();
      const decoder=new TextDecoder();
      let buf='';
      while(true){
        const chunk=await reader.read();
        if(chunk.done) break;
        buf+=decoder.decode(chunk.value,{stream:true});
        const lines=buf.split('\n');
        buf=lines.pop();
        for(let i=0;i<lines.length;i++){
          const line=lines[i];
          if(!line.startsWith('data: ')) continue;
          let d;
          try{d=JSON.parse(line.slice(6));}catch(_){continue;}
          if(d.agent) appendToAgent(d.agent,d.type,d);
        }
      }
    }catch(err){
      alert('[network] '+err);
    }finally{
      btn.disabled=false;
      inp.focus();
    }
    return;
  }
  inp.value='';
  btn.disabled=true;
  agents.forEach(function(a){
    const stopBtn=document.getElementById('stop-'+a);
    if(stopBtn) stopBtn.disabled=false;
    const col=document.getElementById('col-'+a);
    if(col) col.classList.remove('stopped');
  });
  addUserToAll(t);
  try{
    const resp=await fetch('/roundtable/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:t})
    });
    const reader=resp.body.getReader();
    const decoder=new TextDecoder();
    let buf='';
    let gotDone=false;
    while(true){
      const chunk=await reader.read();
      if(chunk.done) break;
      buf+=decoder.decode(chunk.value,{stream:true});
      const lines=buf.split('\n');
      buf=lines.pop();
      for(let i=0;i<lines.length;i++){
        const line=lines[i];
        if(!line.startsWith('data: ')) continue;
        let d;
        try{d=JSON.parse(line.slice(6));}catch(_){continue;}
        if(d.type==='done'){gotDone=true;}
        if(d.agent) appendToAgent(d.agent,d.type,d);
      }
    }
    // if proactive is on and we got a clean done, auto-fire next round
    if(gotDone && proactiveMode && autoRoundsLeft>0){
      autoRoundsLeft--;
      setTimeout(function(){
        sendTurnWithMessage('Proactive mode active keep working');
      },800);
    }
  }catch(err){
    alert('[network] '+err);
  }finally{
    btn.disabled=false;
    inp.focus();
  }
}

async function sendTurn(){
  const t=document.getElementById('inp').value.trim();
  if(!t) return;
  if(proactiveMode){
    autoRoundsLeft=10; // max 10 auto rounds when user manually triggers
  }
  await sendTurnWithMessage(t);
}

async function restoreRt(){
  try{
    const r = await fetch('/roundtable/status');
    const j = await r.json();
    if(j.active && j.agents && j.agents.length){
      agents = j.agents;
      active = true;
      document.getElementById('setup').style.display='none';
      document.getElementById('grid').style.display='grid';
      document.getElementById('inputArea').style.display='flex';
      const grid = document.getElementById('grid');
      grid.innerHTML = '';
      agents.forEach(function(a){
        const col = document.createElement('div');
        col.className = 'col';
        col.id = 'col-' + a;
        col.innerHTML = '<div class="col-head"><span>' + a + '</span><button class="stop-btn" id="stop-' + a + '" onclick="stopAgent(\'' + a + '\')">Stop</button></div><div class="col-body"></div>';
        grid.appendChild(col);
      });
      if(j.history && j.history.length){
        j.history.forEach(function(h){
          if(h.agent === 'Usuario'){
            addUserToAll(h.text);
          } else {
            appendToAgent(h.agent, 'text', {text: h.text});
            const col = document.getElementById('col-' + h.agent);
            if(col && col._lastBubble){
              col._lastBubble.dataset.done = '1';
            }
          }
        });
      }
    }
  }catch(_){}
}

document.getElementById('inp').addEventListener('keydown',function(e){
  if(e.key==='Enter' && !e.shiftKey){
    e.preventDefault();
    sendTurn();
  }
});

restoreRt();
</script>
</body></html>"""

    @app.route("/")
    def home() -> Response:
        return Response(CHAT_PAGE, mimetype="text/html")

    @app.route("/roundtable")
    def roundtable_page() -> Response:
        return Response(RT_PAGE, mimetype="text/html")

    # ── Sandbox (Mini OS) ─────────────────────────────────────────────────────
    _SANDBOX_DIST = Path(__file__).parent / "sandbox" / "dist"

    @app.route("/sandbox")
    @app.route("/sandbox/")
    def sandbox_index() -> Response:
        return send_from_directory(_SANDBOX_DIST, "index.html")

    @app.route("/sandbox/<path:path>")
    def sandbox_static(path) -> Response:
        return send_from_directory(_SANDBOX_DIST, path)

    # ── Sandbox Filesystem API ────────────────────────────────────────────────
    import os as _os

    @app.route("/api/sandbox/fs/list", methods=["GET"])
    def sandbox_fs_list():
        """List directory contents. ?path= relative to project root."""
        rel = request.args.get("path", "/")
        base = Path(__file__).parent
        target = (base / rel.lstrip("/")).resolve()
        # Safety: must stay within project root
        try:
            target.relative_to(base)
        except ValueError:
            return jsonify(error="Access denied"), 403
        if not target.exists():
            return jsonify(error="Not found"), 404
        if target.is_file():
            return jsonify([{"name": target.name, "type": "file", "size": target.stat().st_size}])
        entries = []
        for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "type": "folder" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else 0,
                    "modified": stat.st_mtime,
                })
            except OSError:
                pass
        return jsonify(entries)

    @app.route("/api/sandbox/fs/read", methods=["GET"])
    def sandbox_fs_read():
        """Read a file. ?path= relative to project root."""
        rel = request.args.get("path", "")
        if not rel:
            return jsonify(error="path required"), 400
        base = Path(__file__).parent
        target = (base / rel.lstrip("/")).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return jsonify(error="Access denied"), 403
        if not target.exists() or not target.is_file():
            return jsonify(error="Not found"), 404
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            return jsonify({"path": rel, "content": content})
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/sandbox/fs/write", methods=["POST"])
    def sandbox_fs_write():
        """Write a file. Body: {path, content}."""
        body = request.get_json(silent=True) or {}
        rel = body.get("path", "")
        content = body.get("content", "")
        if not rel:
            return jsonify(error="path required"), 400
        base = Path(__file__).parent
        target = (base / rel.lstrip("/")).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return jsonify(error="Access denied"), 403
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return jsonify(ok=True, path=rel)
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/api/sandbox/exec", methods=["POST"])
    def sandbox_exec():
        """Execute a command string through the Dulus agent (streaming SSE)."""
        body = request.get_json(silent=True) or {}
        cmd = (body.get("command") or "").strip()
        if not cmd:
            return jsonify(error="command required"), 400
        # Run via agent mirror so it has full tool access
        def generate():
            q: queue.Queue = queue.Queue(maxsize=512)
            exc_holder = [None]
            def producer():
                try:
                    for ev in _run_agent_mirror(cmd):
                        result = _event_to_dict(ev)
                        if result is None:
                            continue
                        if isinstance(result, tuple):
                            payload, evt = result
                            # auto-approve in exec mode
                            perm_req = _PENDING_PERMISSIONS.get(payload["id"])
                            if perm_req:
                                perm_req[0].granted = True
                            evt.set()
                            continue
                        q.put(result)
                except Exception as e:
                    exc_holder[0] = e
                finally:
                    q.put(None)
            t = threading.Thread(target=producer, daemon=True)
            t.start()
            yield 'data: {"type":"start"}\n\n'
            while True:
                item = q.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
            if exc_holder[0]:
                err = exc_holder[0]
                yield f'data: {json.dumps({"type":"error","message":str(err)})}\n\n'
            yield 'data: {"type":"done"}\n\n'
        return Response(stream_with_context(generate()), mimetype="text/event-stream")


    @app.route("/state")
    def state_endpoint() -> Response:
        with _LOCK:
            hist = [dict(m) for m in (STATE.messages if STATE else [])]
            model = CONFIG.get("model", "?") if CONFIG else "?"
        return jsonify(model=model, history=hist)

    @app.route("/clear", methods=["POST"])
    def clear() -> Response:
        with _LOCK:
            if STATE:
                STATE.messages.clear()
        return jsonify(ok=True)

    @app.route("/shutdown", methods=["POST"])
    def shutdown() -> Response:
        return jsonify(ok=True)

    @app.route("/permission", methods=["POST"])
    def permission() -> Response:
        body = request.get_json(silent=True) or {}
        pid = body.get("id")
        granted = body.get("granted", False)
        with _LOCK:
            item = _PENDING_PERMISSIONS.get(pid)
        if item is None:
            return jsonify(error="not found"), 404
        req, evt = item
        req.granted = bool(granted)
        evt.set()
        return jsonify(ok=True)

    @app.route("/chat", methods=["POST"])
    def chat() -> Response:
        body = request.get_json(silent=True) or {}
        msg = (body.get("message") or "").strip()
        if not msg:
            return jsonify(error="empty message"), 400

        # Slash commands: same behavior as the Telegram bridge —
        # run via REPL's _handle_slash_callback, capture stdout,
        # stream output back as text events.
        if msg.startswith("/") and len(msg) > 1:
            def generate_slash():
                yield 'data: {"type":"start"}\n\n'
                try:
                    output, assistant_reply = _run_slash_command(msg)
                    if output:
                        yield f"data: {json.dumps({'type':'text','text':output})}\n\n"
                    if assistant_reply:
                        sep = "\n\n" if output else ""
                        yield f"data: {json.dumps({'type':'text','text':sep + assistant_reply})}\n\n"
                except Exception as e:
                    yield f'data: {json.dumps({"type":"error","message":f"{type(e).__name__}: {e}"})}\n\n'
                yield 'data: {"type":"done"}\n\n'
            return Response(
                stream_with_context(generate_slash()),
                mimetype="text/event-stream",
            )

        def generate():
            q: queue.Queue = queue.Queue(maxsize=512)
            exc_holder = [None]

            def producer():
                try:
                    for ev in _run_agent_mirror(msg):
                        result = _event_to_dict(ev)
                        if result is None:
                            continue
                        if isinstance(result, tuple):
                            payload, evt = result
                            q.put(payload)
                            evt.wait(timeout=300)
                            _PENDING_PERMISSIONS.pop(payload.get("id"), None)
                            continue
                        q.put(result)
                except Exception as e:
                    exc_holder[0] = e
                finally:
                    q.put(None)

            t = threading.Thread(target=producer, daemon=True)
            t.start()

            yield 'data: {"type":"start"}\n\n'

            while True:
                item = q.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"

            if exc_holder[0]:
                err = exc_holder[0]
                yield f'data: {json.dumps({"type":"error","message":f"{type(err).__name__}: {err}"})}\n\n'

            yield 'data: {"type":"done"}\n\n'

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
        )

    # ── Roundtable endpoints ─────────────────────────────────────────────

    @app.route("/roundtable/start", methods=["POST"])
    def roundtable_start() -> Response:
        body = request.get_json(silent=True) or {}
        models = body.get("models", [])
        if not (3 <= len(models) <= 5):
            return jsonify(ok=False, error="Necesitas 3 a 5 modelos"), 400

        with ROUNDTABLE_LOCK:
            ROUNDTABLE_AGENTS.clear()
            ROUNDTABLE_HISTORY.clear()
            for i, model in enumerate(models):
                letter = chr(65 + i)
                ROUNDTABLE_AGENTS.append(RoundtableAgent(letter, model.strip()))

        return jsonify(ok=True, agents=[a.id for a in ROUNDTABLE_AGENTS])

    @app.route("/roundtable/chat", methods=["POST"])
    def roundtable_chat() -> Response:
        body = request.get_json(silent=True) or {}
        msg = (body.get("message") or "").strip()
        if not msg:
            return jsonify(error="empty message"), 400

        with ROUNDTABLE_LOCK:
            agents = list(ROUNDTABLE_AGENTS)
        if not agents:
            return jsonify(error="no roundtable active"), 400

        # Slash commands: run once via REPL handler, broadcast the
        # output to every agent column. Same pattern as Telegram bridge.
        if msg.startswith("/") and len(msg) > 1:
            def generate_slash_rt():
                yield 'data: {"type":"start"}\n\n'
                try:
                    output, assistant_reply = _run_slash_command(msg)
                    chunks = []
                    if output:
                        chunks.append(output)
                    if assistant_reply:
                        chunks.append(assistant_reply)
                    full = "\n\n".join(chunks) if chunks else f"✅ {msg.split()[0]} executed."
                    with ROUNDTABLE_LOCK:
                        for ag in agents:
                            evt = {"type": "text", "text": full, "agent": ag.id}
                            ROUNDTABLE_HISTORY.append(evt)
                            yield f"data: {json.dumps(evt)}\n\n"
                            yield f"data: {json.dumps({'type':'agent_done','agent':ag.id,'text':full})}\n\n"
                except Exception as e:
                    err = f"{type(e).__name__}: {e}"
                    for ag in agents:
                        yield f"data: {json.dumps({'type':'error','agent':ag.id,'message':err})}\n\n"
                yield 'data: {"type":"done"}\n\n'
            return Response(
                stream_with_context(generate_slash_rt()),
                mimetype="text/event-stream",
            )

        # Build lean history: only last text message per agent (for prompt building)
        msg = _sanitize_for_api(msg)
        with ROUNDTABLE_LOCK:
            # Build last-msg-per-agent snapshot for prompt
            last_per_agent: dict[str, str] = {}
            for item in ROUNDTABLE_HISTORY:
                a = item.get("agent", "")
                t = item.get("text", "")
                if a and t:
                    last_per_agent[a] = t
            history_snapshot = [{"agent": a, "text": t} for a, t in last_per_agent.items()]
            # Store user message in history (lean)
            ROUNDTABLE_HISTORY.append({"agent": "Usuario", "text": msg, "type": "text"})

        def generate():
            q: queue.Queue = queue.Queue(maxsize=1024)
            active_flags = [True] * len(agents)
            agent_results: dict[str, str] = {}

            def run_one(idx: int):
                try:
                    _run_agent_for_roundtable(agents[idx], msg, history_snapshot, q)
                finally:
                    active_flags[idx] = False

            threads = [
                threading.Thread(target=run_one, args=(i,), daemon=True)
                for i in range(len(agents))
            ]
            for t in threads:
                t.start()

            yield 'data: {"type":"start"}\n\n'

            while any(active_flags) or not q.empty():
                try:
                    item = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if item:
                    # Stream event to frontend but do NOT store every event
                    yield f"data: {json.dumps(item)}\n\n"
                    # Only persist final text per agent to keep history lean
                    if item.get("type") == "agent_done":
                        agent_results[item["agent"]] = item.get("text", "")

            # Save only final text per agent to shared history
            with ROUNDTABLE_LOCK:
                for agent in agents:
                    text = _sanitize_for_api(agent_results.get(agent.id, ""))
                    if text:
                        ROUNDTABLE_HISTORY.append({"agent": agent.id, "text": text, "type": "text"})

            yield 'data: {"type":"done"}\n\n'

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
        )

    @app.route("/roundtable/stop", methods=["POST"])
    def roundtable_stop() -> Response:
        with ROUNDTABLE_LOCK:
            ROUNDTABLE_AGENTS.clear()
        return jsonify(ok=True)

    @app.route("/roundtable/stop-agent", methods=["POST"])
    def roundtable_stop_agent() -> Response:
        body = request.get_json(silent=True) or {}
        agent_id = body.get("agent_id", "").strip()
        if not agent_id:
            return jsonify(ok=False, error="missing agent_id"), 400
        with _STOP_EVENTS_LOCK:
            evt = _AGENT_STOP_EVENTS.get(agent_id)
        if evt is None:
            return jsonify(ok=False, error="agent not running"), 404
        evt.set()
        return jsonify(ok=True)

    @app.route("/roundtable/status", methods=["GET"])
    def roundtable_status() -> Response:
        with ROUNDTABLE_LOCK:
            active = len(ROUNDTABLE_AGENTS) > 0
            agents = [a.id for a in ROUNDTABLE_AGENTS]
            history = list(ROUNDTABLE_HISTORY)
        return jsonify(active=active, agents=agents, history=history)

    @app.route("/roundtable/direct", methods=["POST"])
    def roundtable_direct() -> Response:
        body = request.get_json(silent=True) or {}
        agent_id = (body.get("agent_id") or "").strip()
        msg = (body.get("message") or "").strip()
        if not agent_id or not msg:
            return jsonify(error="agent_id and message required"), 400

        with ROUNDTABLE_LOCK:
            target = None
            for a in ROUNDTABLE_AGENTS:
                if a.id.lower() == agent_id.lower():
                    target = a
                    break
        if target is None:
            return jsonify(error="agent not found"), 404

        msg = _sanitize_for_api(msg)
        with ROUNDTABLE_LOCK:
            # Lean history for prompts
            last_per_agent: dict[str, str] = {}
            for item in ROUNDTABLE_HISTORY:
                a = item.get("agent", "")
                t = item.get("text", "")
                if a and t:
                    last_per_agent[a] = t
            history_snapshot = [{"agent": a, "text": t} for a, t in last_per_agent.items()]
            
            # Store user direct message
            ROUNDTABLE_HISTORY.append({"agent": "Usuario", "text": f"[→ {target.id}] {msg}", "type": "text"})

        def generate():
            q: queue.Queue = queue.Queue(maxsize=1024)
            final_text = [""]

            def run_one():
                try:
                    _run_agent_for_roundtable(target, msg, history_snapshot, q)
                finally:
                    q.put(None)

            t = threading.Thread(target=run_one, daemon=True)
            t.start()

            yield 'data: {"type":"start"}\n\n'

            while True:
                try:
                    item = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                
                # Stream to frontend
                yield f"data: {json.dumps(item)}\n\n"
                
                # Capture result
                if item.get("type") == "agent_done":
                    final_text[0] = item.get("text", "")

            # Persist final result only
            with ROUNDTABLE_LOCK:
                text = _sanitize_for_api(final_text[0])
                if text:
                    ROUNDTABLE_HISTORY.append({"agent": target.id, "text": text, "type": "text"})

            yield 'data: {"type":"done"}\n\n'

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
        )

    # ── DULUS 2 UNIFIED ENDPOINTS ──

    @app.route("/api/events")
    def api_events():
        def generate():
            q = queue.Queue(maxsize=100)
            _add_sse_client(q)
            yield f"event: connected\ndata: {json.dumps({'message':'Dulus SSE active'})}\n\n"
            try:
                while True:
                    try:
                        msg = q.get(timeout=30)
                        yield msg
                    except queue.Empty:
                        yield ":\n\n"
            finally:
                _remove_sse_client(q)
        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "agent": "Dulus", "mode": "proactive", "version": "2026.04.26"})

    @app.route("/api/tasks", methods=["GET"])
    def get_api_tasks():
        tasks = task_list()
        return jsonify([t.to_dict() for t in tasks])

    @app.route("/api/context", methods=["GET"])
    def api_context():
        return jsonify(build_context())

    @app.route("/api/context/compact", methods=["GET"])
    def api_context_compact():
        return Response(get_compact_context(), mimetype="text/plain")

    @app.route("/api/chat/history", methods=["GET"])
    def api_chat_history():
        msgs = []
        if STATE and hasattr(STATE, "messages"):
            for m in STATE.messages:
                msgs.append({
                    "role": m.get("role", ""),
                    "content": m.get("content", ""),
                    "thinking": m.get("thinking", ""),
                    "tool_calls": m.get("tool_calls", []),
                    "name": m.get("name", ""),
                    "tool_call_id": m.get("tool_call_id", ""),
                })
        sid = CONFIG.get("_session_id", "default") if CONFIG else "default"
        return jsonify({"messages": msgs, "session_id": sid})

    @app.route("/api/session/load", methods=["POST"])
    def api_session_load():
        body = request.get_json(silent=True) or {}
        msgs = body.get("messages", [])
        sid = body.get("session_id")
        global _PENDING_HISTORY, _PENDING_SESSION_ID
        with _LOCK:
            active_sid = CONFIG.get("_session_id") if CONFIG else None
            if sid and active_sid and sid == active_sid:
                pass  # Do not overwrite live memory with stale disk/frontend data
            else:
                _PENDING_HISTORY = msgs
                _PENDING_SESSION_ID = sid
                if CONFIG and sid:
                    CONFIG["_session_id"] = sid
                if STATE:
                    STATE.messages.clear()
                    for m in msgs:
                        STATE.messages.append(m)
        return jsonify(ok=True)

    @app.route("/api/sessions", methods=["GET"])
    def api_sessions_list():
        return jsonify(scan_sessions())

    @app.route("/api/sessions/save", methods=["POST"])
    def api_sessions_save():
        body = request.get_json(silent=True) or {}
        sid = body.get("session_id", "default")
        with _LOCK:
            if STATE and CONFIG:
                save_session(STATE, CONFIG, sid)
        return jsonify(ok=True)

    @app.route("/api/sessions/<sid>", methods=["DELETE"])
    def api_sessions_delete(sid):
        _delete_session_disk(sid)
        return jsonify(ok=True)

    @app.route("/api/smart-context", methods=["GET"])
    def api_smart_context():
        return jsonify(build_smart_context())

    @app.route("/api/smart-context/compact", methods=["POST"])
    def api_smart_context_compact():
        from backend.context import force_compaction
        return jsonify(force_compaction())

    @app.route("/api/quick-message", methods=["POST"])
    def api_quick_message():
        body = request.get_json(silent=True) or {}
        msg = (body.get("message") or "").strip()
        if not msg:
            return jsonify(error="empty message"), 400
        
        def run_blind():
            try:
                for event in _run_agent_mirror(msg):
                    from agent import PermissionRequest
                    if isinstance(event, PermissionRequest):
                        # Auto-approve silently for background quick messages
                        event.granted = True
            except Exception as e:
                import traceback
                traceback.print_exc()

        threading.Thread(target=run_blind, daemon=True).start()
        return jsonify(ok=True)

    @app.route("/api/agents", methods=["GET"])
    def api_agents():
        return jsonify(build_context().get("agents", []))

    @app.route("/api/personas", methods=["GET"])
    def api_get_personas():
        return jsonify({"personas": get_all_personas(), "active": get_active_persona()})

    @app.route("/api/personas/active", methods=["GET"])
    def api_personas_active():
        return jsonify(get_active_persona())

    @app.route("/api/personas/<pid>", methods=["GET"])
    def api_get_persona_id(pid):
        p = get_persona(pid)
        if p: return jsonify(p)
        return jsonify(error="Not found"), 404

    @app.route("/api/personas", methods=["POST"])
    def api_create_persona():
        data = request.get_json(silent=True) or {}
        r = create_persona(data)
        broadcast_event("persona_created", r)
        return jsonify(r), 201

    @app.route("/api/tasks", methods=["POST"])
    def api_create_task():
        data = request.get_json(silent=True) or {}
        t = task_create(
            subject=data.get("subject", "New Task"),
            description=data.get("description", data.get("metadata", {}).get("description", "")),
            metadata=data.get("metadata", {}),
        )
        result = t.to_dict()
        broadcast_event("task_created", result)
        return jsonify(result), 201

    @app.route("/api/tasks/<tid>", methods=["POST"])
    def api_update_task(tid):
        data = request.get_json(silent=True) or {}
        t, fields = task_update(
            task_id=tid,
            subject=data.get("subject"),
            description=data.get("description"),
            status=data.get("status"),
            owner=data.get("owner"),
            metadata=data.get("metadata"),
        )
        if t:
            result = t.to_dict()
            broadcast_event("task_updated", result)
            return jsonify(result)
        return jsonify(error="Not found"), 404

    @app.route("/api/plugins", methods=["GET"])
    def api_get_plugins():
        import os
        user_plugins_dir = Path(os.path.expanduser("~")) / ".dulus" / "plugins"
        plugins = []
        if user_plugins_dir.exists():
            for d in sorted(user_plugins_dir.iterdir()):
                if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("__"):
                    plugins.append({
                        "name": d.name,
                        "status": "enabled",
                        "source": "user",
                        "path": str(d),
                    })
        # Also include any from dulus2's hot-reload system
        try:
            load_all_plugins()
            for p in get_plugin_info():
                if not any(ep["name"] == p["name"] for ep in plugins):
                    plugins.append(p)
        except Exception:
            pass
        return jsonify({"plugins": plugins, "count": len(plugins)})

    @app.route("/api/plugins/status", methods=["GET"])
    def api_plugins_status():
        return jsonify(watcher_status())

    @app.route("/api/plugins/reload", methods=["POST"])
    def api_plugins_reload():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if name:
            from backend.plugins import PLUGINS_DIR
            r = reload_plugin(PLUGINS_DIR / f"{name}.py")
            dr = {"name": r.get("name", name), "version": r.get("version", "?"), "status": r.get("status", "?")}
            broadcast_event("plugin_reloaded", dr)
            return jsonify(dr)
        else:
            load_all_plugins()
            inf = get_plugin_info()
            broadcast_event("plugins_reloaded", {"count": len(inf)})
            return jsonify({"plugins": inf})

    # ── Personas activate ──
    @app.route("/api/personas/activate", methods=["POST"])
    def api_personas_activate():
        data = request.get_json(silent=True) or {}
        pid = data.get("id")
        if not pid:
            return jsonify(error="Missing persona id"), 400
        result = set_active_persona(pid)
        if result:
            broadcast_event("persona_activated", result)
            return jsonify({"activated": True, "persona": result})
        return jsonify(error="Persona not found"), 404

    # ── Marketplace ──
    @app.route("/api/marketplace", methods=["GET"])
    def api_marketplace():
        q = request.args.get("q", "")
        tag = request.args.get("tag", "")
        return jsonify({"plugins": search_plugins(q, tag)})

    @app.route("/api/marketplace/stats", methods=["GET"])
    def api_marketplace_stats():
        return jsonify(marketplace_stats())

    @app.route("/api/marketplace/install", methods=["POST"])
    def api_marketplace_install():
        data = request.get_json(silent=True) or {}
        plugin_id = data.get("id")
        if not plugin_id:
            return jsonify(error="Missing plugin id"), 400
        result = install_plugin(plugin_id)
        if result:
            broadcast_event("marketplace_install", result)
            return jsonify({"installed": True, "plugin": result})
        return jsonify(error="Plugin not found"), 404

    @app.route("/api/marketplace/uninstall", methods=["POST"])
    def api_marketplace_uninstall():
        data = request.get_json(silent=True) or {}
        plugin_id = data.get("id")
        if not plugin_id:
            return jsonify(error="Missing plugin id"), 400
        result = uninstall_plugin(plugin_id)
        if result:
            broadcast_event("marketplace_uninstall", result)
            return jsonify({"uninstalled": True, "plugin": result})
        return jsonify(error="Plugin not found"), 404

    # ── MemPalace ──
    @app.route("/api/mempalace", methods=["GET"])
    def api_mempalace():
        try:
            from backend.mempalace_bridge import load_cache, get_mempalace_compact_text
            data = load_cache()
            data["compact_text"] = get_mempalace_compact_text()
            return jsonify(data)
        except Exception as e:
            return jsonify(error=f"MemPalace error: {e}"), 500

    # ── Themes ──
    @app.route("/api/themes", methods=["GET"])
    def api_themes():
        try:
            from gui.themes import THEMES
            theme_list = {name: f"{t['accent']} accent, {t['bg']} bg" for name, t in THEMES.items()}
            return jsonify({"themes": theme_list})
        except Exception:
            return jsonify({"themes": {}})

    @app.route("/api/themes/<theme_name>/css", methods=["GET"])
    def api_theme_css(theme_name):
        try:
            from gui.themes import THEMES
            t = THEMES.get(theme_name)
            if not t:
                return Response("", mimetype="text/css")
            css = ":root{\n"
            css += f"  --bg:{t['bg']};\n"
            css += f"  --bg2:{t['card']};\n"
            css += f"  --bg3:{t.get('code_bg', t['card'])};\n"
            css += f"  --ink:{t['text']};\n"
            css += f"  --dim:{t['dim']};\n"
            css += f"  --dim2:{t['border']};\n"
            css += f"  --accent:{t['accent']};\n"
            css += f"  --accent2:{t.get('accent_hover', t['accent'])};\n"
            css += f"  --green:{t.get('success', '#4caf50')};\n"
            css += f"  --red:{t.get('error', '#ff6b6b')};\n"
            css += f"  --yellow:{t.get('warning', '#FFC107')};\n"
            css += f"  --blue:{t['accent']};\n"
            css += "}\n"
            return Response(css, mimetype="text/css")
        except Exception:
            return Response("", mimetype="text/css")

    # ── Dashboard static serving ──
    @app.route("/dashboard")
    @app.route("/dashboard/")
    def dashboard_page():
        target = DASHBOARD_DIR / "index.html"
        if target.exists():
            return Response(target.read_bytes(), mimetype="text/html")
        return "Dashboard not found", 404

    @app.route("/dashboard/<path:filepath>")
    def dashboard_static(filepath):
        target = DASHBOARD_DIR / filepath
        if target.exists() and target.is_file():
            ctype = "text/html"
            if filepath.endswith(".css"): ctype = "text/css"
            elif filepath.endswith(".js"): ctype = "application/javascript"
            elif filepath.endswith(".json"): ctype = "application/json"
            elif filepath.endswith(".png"): ctype = "image/png"
            elif filepath.endswith(".svg"): ctype = "image/svg+xml"
            return Response(target.read_bytes(), mimetype=ctype)
        return "Not found", 404

    return app


def start(state: AgentState, config: dict, port: int = 5000, open_browser: bool = False) -> bool:
    global STATE, CONFIG, _SERVER_THREAD, _SERVER_PORT, _WERKZEUG_SERVER
    if _SERVER_THREAD and _SERVER_THREAD.is_alive():
        return False
    STATE = state
    CONFIG = config
    _SERVER_PORT = port
    app = create_app()
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()

    from werkzeug.serving import make_server

    # Default to loopback-only — exposing to the LAN by accident is a real
    # safety footgun (anyone on the wifi can poke the agent). Opt-in via
    # config["webchat_lan"] = true (or /webchat lan on).
    bind_host = "0.0.0.0" if config.get("webchat_lan") else "127.0.0.1"
    _WERKZEUG_SERVER = make_server(bind_host, port, app, threaded=True)
    _SERVER_THREAD = threading.Thread(target=_WERKZEUG_SERVER.serve_forever, daemon=True)
    _SERVER_THREAD.start()
    return True


def stop() -> None:
    global _SERVER_THREAD, _WERKZEUG_SERVER
    srv = _WERKZEUG_SERVER
    if srv is not None:
        srv.shutdown()
    _SERVER_THREAD = None
    _WERKZEUG_SERVER = None


def is_running() -> bool:
    return _SERVER_THREAD is not None and _SERVER_THREAD.is_alive()
