"""Bridge between the GUI and Dulus's core agent engine.

Handles AgentState, config, threaded execution, MemPalace injection,
skill injection, and permission requests. Based on Nayeli's design.
"""
from __future__ import annotations

import queue
import threading
from pathlib import Path

from agent import (
    AgentState,
    run,
    TextChunk,
    ThinkingChunk,
    ToolStart,
    ToolEnd,
    TurnDone,
    PermissionRequest,
)
from config import load_config
from context import build_system_prompt
from common import sanitize_text
from gui.session_utils import save_session

# Ensure all tool modules are loaded so registration side-effects run
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

try:
    from plugin.loader import register_plugin_tools
    register_plugin_tools()
except Exception:
    pass


class DulusBridge:
    """Thread-safe bridge between GUI and Dulus core.

    Runs the agent loop in a background thread and streams events
    back to the UI via an internal event queue (poll from GUI thread).
    """

    def __init__(self, config: dict | None = None):
        self.config = config or load_config()
        self.state = AgentState()
        self._cancelled = threading.Event()
        self._running = True
        self._worker_thread: threading.Thread | None = None
        self._input_queue: queue.Queue[str | None] = queue.Queue()
        self.event_queue: queue.Queue[dict] = queue.Queue()

        # Permission handling
        self._permission_queue: queue.Queue[bool] = queue.Queue()


        # Session ID tracking
        self.session_id: str | None = None
        self.pending_history: list[dict] = []

        # Skill injection buffer (one-shot, consumed on next message)
        self._skill_inject: str = ""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background worker thread."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._running = True
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()

    def stop(self) -> None:
        """Clean shutdown of the bridge worker thread."""
        self._running = False
        self._cancelled.set()
        self._input_queue.put(None)
        if self._worker_thread:
            self._worker_thread.join(timeout=3.0)

    # ── Public API ────────────────────────────────────────────────────────────

    def send_message(self, text: str) -> None:
        """Enqueue a user message. Pre-loads pending history if needed."""
        if self.pending_history:
            self.load_session(self.pending_history, self.session_id)
            self.pending_history = []
        self._input_queue.put(text)

    def stop_generation(self) -> None:
        """Signal the current generation to stop as soon as possible."""
        self._cancelled.set()

    def grant_permission(self, granted: bool) -> None:
        """Respond to a pending permission request."""
        self._permission_queue.put(granted)

    def get_context_usage(self) -> tuple[int, int]:
        """Return (tokens_used, token_limit)."""
        used = self.state.total_input_tokens + self.state.total_output_tokens
        limit = self.config.get("max_tokens", 250000)
        return used, limit

    def save_current_session(self) -> str | None:
        """Manually save the current active state to disk. Returns session_id."""
        if self.state and self.state.messages:
            self.session_id = save_session(self.state, self.config, self.session_id)
            return self.session_id
        return None

    def clear_session(self) -> None:
        """Reset the agent state (new conversation)."""
        self.state = AgentState()
        self.session_id = None
        self.pending_history = []

    def load_session(self, messages: list[dict], session_id: str | None = None) -> None:
        """Load a previous session's messages into the current state."""
        self.state = AgentState()
        self.session_id = session_id
        self.pending_history = []
        for m in messages:
            # Preserve all fields (role, content, tool_calls, tool_call_id, etc.)
            self.state.messages.append(m.copy())

    def inject_skill(self, skill_body: str) -> None:
        """Inject skill context into the next user message (one-shot)."""
        self._skill_inject = skill_body

    def set_model(self, model: str) -> None:
        """Change the active model."""
        self.config["model"] = model

    # ── Worker loop ───────────────────────────────────────────────────────────

    def _worker_loop(self) -> None:
        while self._running:
            try:
                user_message = self._input_queue.get(timeout=0.5)
                if user_message is None:
                    continue
                if not isinstance(user_message, str):
                    continue

                self._cancelled.clear()
                self._process_turn(user_message)

            except queue.Empty:
                continue
            except Exception as exc:
                self._emit("error", message=str(exc))

    def _process_turn(self, user_message: str) -> None:
        # Assign session_id immediately to prevent UI duplication during turn
        if not self.session_id:
            import uuid
            self.session_id = uuid.uuid4().hex[:8]

        # ── Skill inject (one-shot) ────────────────────────────────────────
        skill_body = self._skill_inject
        self._skill_inject = ""
        if skill_body:
            user_message = (
                "[SKILL CONTEXT — follow these instructions for this turn]\n\n"
                + skill_body
                + "\n\n---\n\n[USER MESSAGE]\n"
                + user_message
            )

        # ── MemPalace: per-turn memory injection ───────────────────────────
        user_message = self._apply_mempalace(user_message)

        # Sanitize input
        user_message = sanitize_text(user_message)

        # Rebuild system prompt each turn (picks up cwd changes, etc.)
        system_prompt = build_system_prompt(self.config)

        for event in run(
            user_message=user_message,
            state=self.state,
            config=self.config,
            system_prompt=system_prompt,
            cancel_check=lambda: self._cancelled.is_set(),
        ):
            if isinstance(event, TextChunk):
                self._emit("text", text=event.text)

            elif isinstance(event, ThinkingChunk):
                self._emit("thinking", text=event.text)

            elif isinstance(event, ToolStart):
                self._emit("tool_start", name=event.name, inputs=event.inputs)

            elif isinstance(event, ToolEnd):
                self._emit(
                    "tool_end",
                    name=event.name,
                    result=event.result,
                    permitted=event.permitted,
                )

            elif isinstance(event, TurnDone):
                # Auto-save session to disk
                sid = save_session(self.state, self.config, self.session_id)
                if sid: self.session_id = sid
                self._emit(
                    "turn_done",
                    input_tokens=event.input_tokens,
                    output_tokens=event.output_tokens,
                    session_id=self.session_id
                )

            elif isinstance(event, PermissionRequest):
                self._emit("permission", description=event.description)
                try:
                    granted = self._permission_queue.get(timeout=300.0)
                    event.granted = bool(granted)
                except queue.Empty:
                    event.granted = False

    def _apply_mempalace(self, user_input: str) -> str:
        """Copy of dulus.py MemPalace injection logic."""
        if not self.config.get("mem_palace", True):
            return user_input

        # Skip trivial messages so we don't burn tokens on "klk"
        if not user_input or len(user_input.strip()) < 12:
            return user_input

        _trivial = {
            "hola", "klk", "gracias", "ok", "si", "no", "dale",
            "exit", "quit", "help", "thanks", "bien",
        }
        _first = user_input.strip().lower().split()[0]
        if _first in _trivial:
            return user_input

        try:
            from memory import find_relevant_memories

            _q = user_input.strip()[:200]
            _raw_hits = find_relevant_memories(_q, max_results=3)
            if not _raw_hits:
                return user_input

            _parts = []
            for _i, _h in enumerate(_raw_hits, 1):
                _name = _h.get("name", f"hit_{_i}")
                _desc = _h.get("description", "")
                _body = _h.get("content", "").strip()
                _snip = _body[:300] + ("..." if len(_body) > 300 else "")
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
            return (
                _inject
                + "\n\n---\n\n[USER MESSAGE]\n"
                + user_input
            )
        except Exception:
            return user_input

    def _emit(self, event_type: str, **kwargs) -> None:
        """Put an event into the public event queue."""
        self.event_queue.put({"type": event_type, **kwargs})
