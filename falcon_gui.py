"""Falcon GUI Entry Point — professional desktop interface.

Usage:
    python falcon_gui.py
    python falcon.py --gui
"""
from __future__ import annotations

import datetime
import queue
import sys
import traceback
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))

try:
    import customtkinter as ctk
except ImportError:
    print("Error: customtkinter is required. Install: pip install customtkinter")
    sys.exit(1)

from config import load_config
from gui import FalconMainWindow, FalconBridge
from gui.themes import get_theme, set_theme
from gui.session_utils import scan_sessions

# Session directories
from config import SESSIONS_DIR, DAILY_DIR, MR_SESSION_DIR


# ── Helpers ───────────────────────────────────────────────────────────────────


def _center_on_parent(dialog: ctk.CTkToplevel, parent: ctk.CTk) -> None:
    """Center a Toplevel over its parent window."""
    dialog.update_idletasks()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_x(), parent.winfo_y()
    dw, dh = dialog.winfo_width(), dialog.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dialog.geometry(f"+{x}+{y}")


class _PermissionDialog(ctk.CTkToplevel):
    """Modal permission request dialog centered on the parent."""

    def __init__(self, parent: ctk.CTk, description: str, on_resolve: Callable[[bool], None]):
        super().__init__(parent)
        self._on_resolve = on_resolve
        self._create_ui(description)
        self._setup_window(parent)

    def _create_ui(self, description: str) -> None:
        t = get_theme()
        self.configure(fg_color=t["bg"])

        ctk.CTkLabel(
            self,
            text="🔒 Permission Required",
            font=("Segoe UI", 16, "bold"),
            text_color=t["accent"],
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            self,
            text=description,
            font=("Segoe UI", 12),
            text_color=t["text"],
            wraplength=450,
        ).pack(pady=10, padx=20)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(
            btn_frame,
            text="Deny",
            font=("Segoe UI", 12, "bold"),
            fg_color=t["border"],
            hover_color=t["error"],
            width=100,
            command=self._deny,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Allow",
            font=("Segoe UI", 12, "bold"),
            fg_color=t["accent"],
            hover_color=t["accent_hover"],
            width=100,
            command=self._allow,
        ).pack(side="left", padx=10)

    def _setup_window(self, parent: ctk.CTk) -> None:
        self.title("Permission Required")
        self.geometry("500x220")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        _center_on_parent(self, parent)

    def _allow(self) -> None:
        self.destroy()
        self._on_resolve(True)

    def _deny(self) -> None:
        self.destroy()
        self._on_resolve(False)


# ── Main launcher ─────────────────────────────────────────────────────────────


# _scan_sessions refactored to gui/session_utils.py


def launch_gui(config: dict | None = None, initial_prompt: str | None = None) -> None:
    """Launch the Falcon desktop GUI.

    Args:
        config: Falcon configuration dict (loaded from disk if None).
        initial_prompt: Optional initial user message to send on startup.
    """
    cfg = config or load_config()

    # Theme
    ctk.set_appearance_mode(cfg.get("appearance", "dark"))
    ctk.set_default_color_theme("dark-blue")
    set_theme(cfg.get("theme", "midnight"))
    t = get_theme()

    # Create GUI window FIRST so user sees something immediately
    app = FalconMainWindow()
    app.set_model(cfg.get("model", "default"))

    # Create bridge (but don't start yet)
    bridge = FalconBridge(config=cfg)

    # Wire bridge into sidebar so context bar / model list work
    app.sidebar.bridge = bridge

    # ── Wire callbacks ────────────────────────────────────────────────────────

    def _on_send(text: str) -> None:
        if text.strip():
            # NOTE: message bubble is already added by main_window._on_send_click
            app.show_thinking()
            bridge.send_message(text)

    def _on_new_chat() -> None:
        # Save current session if active (it will return a new ID if it was new)
        sid = bridge.save_current_session()
        if sid:
            # If a new session was created, refresh sidebar to show it
            app.set_sessions(scan_sessions())
            
        app.hide_thinking()
        app.chat.clear_chat()
        bridge.clear_session()
        app.set_active_session(None)
        app.sidebar.update_context_bar()
        app.set_status("Listo", t["success"])

    def _on_session_select(session_id: str) -> None:
        # Save current session before switching to ensure no loss
        sid = bridge.save_current_session()
        
        # If we were in a new chat that just got saved, refresh sidebar to show it
        if sid:
            app.set_sessions(scan_sessions())
            
        app.hide_thinking()
        
        # 1. Use cached data from sidebar for instant switching
        session_data = app.sidebar._session_cache.get(session_id)
        if not session_data:
            # Fallback to scanning if cache missed (rare)
            for s in scan_sessions():
                if s["id"] == session_id:
                    session_data = s
                    break
        
        if not session_data:
            return

        # 2. Update UI instantly (fluid)
        messages = session_data.get("messages", [])
        app.chat.load_messages(messages)
        
        # 3. Defer bridge loading until first message (user request)
        bridge.pending_history = messages
        bridge.session_id = session_id
        # Important: clear actual AI state so it's fresh until sync
        from agent import AgentState
        bridge.state = AgentState()
        
        app.set_active_session(session_id)
        app.sidebar.update_context_bar()
        app.set_status("Sesión lista (Contexto diferido)", t["success"])

    def _on_settings() -> None:
        from gui.settings_dialog import SettingsDialog
        SettingsDialog(app, cfg)

    def _on_model_change(model: str) -> None:
        bridge.set_model(model)
        app.set_model(model)

    app.on_send = _on_send
    app.on_new_chat = _on_new_chat
    app.sidebar.on_settings = _on_settings
    app.on_model_change = _on_model_change
    app.on_session_select = _on_session_select

    # Load existing sessions into sidebar
    app.set_sessions(scan_sessions())
    app.sidebar._refresh_model_list()
    app.sidebar.update_context_bar()

    # ── Permission dialog handling ────────────────────────────────────────────
    _perm_dialog: _PermissionDialog | None = None

    def _close_perm() -> None:
        nonlocal _perm_dialog
        if _perm_dialog is not None:
            _perm_dialog.destroy()
            _perm_dialog = None

    def _resolve_perm(granted: bool) -> None:
        _close_perm()
        bridge.grant_permission(granted)

    def _show_perm(description: str) -> None:
        nonlocal _perm_dialog
        _close_perm()
        _perm_dialog = _PermissionDialog(app, description, _resolve_perm)

    # ── Event polling loop ────────────────────────────────────────────────────
    def _poll_events() -> None:
        if not app.winfo_exists():
            return  # App destroyed, stop polling

        try:
            while True:
                event = bridge.event_queue.get_nowait()
                etype = event.get("type")

                if etype == "text":
                    app.add_assistant_chunk(event.get("text", ""))

                elif etype == "thinking":
                    app.show_thinking()

                elif etype == "tool_start":
                    app.add_tool_call(event.get("name", "tool"), "running")

                elif etype == "tool_end":
                    app.add_tool_call(event.get("name", ""), "done")

                elif etype == "turn_done":
                    app.hide_thinking()
                    itok = event.get("input_tokens", 0)
                    otok = event.get("output_tokens", 0)
                    app.set_status(f"Listo  (+{itok}/{otok} tok)", t["success"])
                    
                    # Refresh sessions list to show the newly saved session (with its title)
                    app.set_sessions(scan_sessions())
                    if event.get("session_id"):
                        app.set_active_session(event.get("session_id"))

                elif etype == "permission":
                    _show_perm(event.get("description", ""))

                elif etype == "error":
                    app.hide_thinking()
                    app.chat.add_assistant_message(
                        f"**Error:** {event.get('message', 'Unknown error')}"
                    )
                    app.set_status("Error", t["error"])

        except queue.Empty:
            pass
        except Exception as exc:
            # Log to file so we know what crashed the UI
            try:
                with open("gui_error.log", "a", encoding="utf-8") as f:
                    f.write(f"\n[{datetime.datetime.now()}] POLL ERROR: {exc}\n")
                    traceback.print_exc(file=f)
            except Exception:
                pass
        finally:
            # ALWAYS reschedule — if we don't, the GUI stops responding
            if app.winfo_exists():
                app.after(50, _poll_events)

    app.after(50, _poll_events)

    # ── Start bridge AFTER UI is ready ────────────────────────────────────────
    try:
        bridge.start()
    except Exception as exc:
        app.chat.add_assistant_message(f"**Fatal:** Could not start Falcon bridge: {exc}")
        app.set_status("Fatal error", t["error"])

    # ── Initial prompt ────────────────────────────────────────────────────────
    if initial_prompt:
        app.chat.add_user_message(initial_prompt)
        bridge.send_message(initial_prompt)
        app.show_thinking()

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def _on_close() -> None:
        bridge.stop()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", _on_close)
    app.run()


def main() -> None:
    """CLI entry point."""
    cfg = load_config()
    launch_gui(config=cfg)


if __name__ == "__main__":
    main()
