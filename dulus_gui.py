"""Dulus GUI Entry Point -- Your feathered companion's desktop home.

A warm, professional desktop interface with bird-themed personality:
  - Cigua Palmera avatar and branding
  - Orange (#ff6b1f) and dark (#07070a) color scheme
  - Animated typing indicator with bird flair
  - Friendly status messages ("Dulus is ready", "Dulus is thinking...")
  - Toast notifications with bird icons
  - Motivational empty states
  - Smooth hover effects and transitions

Usage:
    python dulus_gui.py
    python dulus.py --gui
"""
from __future__ import annotations

import datetime
import json
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))

try:
    import customtkinter as ctk
    from PIL import Image, ImageTk
except ImportError:
    print("Error: customtkinter and Pillow are required.")
    print("Install: pip install customtkinter Pillow")
    sys.exit(1)

from config import load_config
from gui import DulusMainWindow, DulusBridge
from gui.themes import get_theme, set_theme
from gui.session_utils import scan_sessions
from personality_config import PersonalityConfig

# Session directories
from config import SESSIONS_DIR, DAILY_DIR


# ---------------------------------------------------------------------------
# Color constants -- Dulus brand palette
# ---------------------------------------------------------------------------

DULUS_ORANGE = "#ff6b1f"
DULUS_ORANGE_LIGHT = "#ffb347"
DULUS_DARK = "#07070a"
DULUS_DARK_SECONDARY = "#0f0f12"
DULUS_DARK_TERTIARY = "#1a1a2e"
DULUS_TEXT = "#f0e8df"
DULUS_DIM = "#6a6470"
DULUS_SUCCESS = "#7cffb5"
DULUS_ERROR = "#ff5a6e"
DULUS_WARNING = "#ffd166"


# ---------------------------------------------------------------------------
# Friendly status messages with bird personality
# ---------------------------------------------------------------------------

_STATUS_READY = [
    "🦅 Dulus is ready to fly!",
    "🦅 Your feathered friend is here!",
    "🪶 Tallons sharp and ready!",
    "🦅 Dulus is perched and ready!",
]

_STATUS_THINKING = [
    "🦅 Dulus is thinking...",
    "🪶 Ruffling feathers, processing...",
    "🦅 Scanning the horizon...",
    "🪶 Sharpening talons on your request...",
    "🦅 Diving deep into the code...",
    "🪶 Hatching a solution...",
]

_STATUS_WORKING = [
    "🦅 Dulus is working...",
    "🪶 Flapping through the data...",
    "🦅 Preying on bugs...",
    "🔥 Cooking up a response...",
]

_STATUS_SUCCESS = [
    "🦅 All done! That was smooth!",
    "🎉 Crushed it! High wing!",
    "✨ Nailed the landing!",
    "🚀 Another win for the nest!",
]

_STATUS_ERROR = [
    "🦅 Hmm, hit some turbulence...",
    "🛡️ Don't worry, we got this!",
    "🦅 Let's regroup and try again!",
]

_EMPTY_STATE_MESSAGES = [
    "🦅 **Welcome!** I'm Dulus, your AI companion.\n\nWhat would you like to build today?",
    "🪶 **Hey there!** Your feathered friend is ready.\n\nAsk me anything -- coding, debugging, brainstorming!",
    "🦅 **The nest is ready!**\n\nLet's turn your ideas into reality. What's on your mind?",
    "🔥 **Dulus is in the house!**\n\nReady to code, create, and ship. What are we working on?",
]


# ---------------------------------------------------------------------------
# Helper: Get random status message
# ---------------------------------------------------------------------------

def _random_status(options: list[str]) -> str:
    """Pick a random status message."""
    import random
    return random.choice(options)


# ---------------------------------------------------------------------------
# Bird Avatar Loader
# ---------------------------------------------------------------------------

class BirdAvatar:
    """Loads and caches the Cigua Palmera avatar images for the GUI.

    Tries multiple image sources in order:
    1. brand-assets/cigua-icon-256.png (best quality icon)
    2. brand-assets/cigua-OFFICIAL-256.png (official logo)
    3. dulus-bird.png (fallback)

    Attributes:
        icon: Small icon for sidebar/buttons (32x32)
        avatar: Medium avatar for chat bubbles (48x48)
        logo: Large logo for header (64x64)
    """

    def __init__(self) -> None:
        self.icon: ctk.CTkImage | None = None
        self.avatar: ctk.CTkImage | None = None
        self.logo: ctk.CTkImage | None = None
        self._load_images()

    def _load_images(self) -> None:
        """Attempt to load bird images from available assets."""
        base_dir = Path(__file__).parent

        # Possible image sources in priority order
        candidates = [
            base_dir / "brand-assets" / "cigua-icon-256.png",
            base_dir / "brand-assets" / "cigua-OFFICIAL-256.png",
            base_dir / "dulus-bird.png",
        ]

        img_path: Path | None = None
        for candidate in candidates:
            if candidate.exists():
                img_path = candidate
                break

        if img_path is None:
            return  # No images available, UI will fall back to text/emoji

        try:
            pil_img = Image.open(img_path).convert("RGBA")

            # Create different sizes
            self.icon = ctk.CTkImage(pil_img, size=(32, 32))
            self.avatar = ctk.CTkImage(pil_img, size=(48, 48))
            self.logo = ctk.CTkImage(pil_img, size=(64, 64))
        except Exception:
            pass  # Graceful fallback


# ---------------------------------------------------------------------------
# Animated Typing Indicator
# ---------------------------------------------------------------------------

class TypingIndicator(ctk.CTkFrame):
    """A bird-themed typing indicator with subtle animation.

    Shows an animated bird emoji sequence to indicate Dulus is thinking.
    Much friendlier than a generic spinner.
    """

    _FRAMES = ["🦅", "🪶", "✨", "🪶"]

    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent, fg_color="transparent")
        self._frame_idx = 0
        self._label = ctk.CTkLabel(
            self,
            text="🦅 Dulus is thinking...",
            font=("Segoe UI", 12, "italic"),
            text_color=DULUS_DIM,
        )
        self._label.pack(padx=16, pady=8, anchor="w")
        self._after_id: str | None = None
        self._hide()

    def show(self, message: str | None = None) -> None:
        """Show the typing indicator with optional custom message."""
        self._frame_idx = 0
        self._update_text(message)
        self.pack(fill="x", padx=0, pady=(0, 8), before=self.master.winfo_children()[0] if self.master.winfo_children() else None)
        self._schedule_animation()

    def hide(self) -> None:
        """Hide the typing indicator."""
        self._cancel_animation()
        self.pack_forget()

    def _hide(self) -> None:
        """Initial hidden state."""
        self.pack_forget()

    def _update_text(self, message: str | None = None) -> None:
        """Update the label text with current frame."""
        frame = self._FRAMES[self._frame_idx % len(self._FRAMES)]
        text = message or _random_status(_STATUS_THINKING)
        self._label.configure(text=f"{frame} {text}")

    def _schedule_animation(self) -> None:
        """Schedule the next animation frame."""
        self._cancel_animation()
        self._after_id = self.after(400, self._animate)

    def _animate(self) -> None:
        """Advance to next animation frame."""
        self._frame_idx += 1
        self._update_text()
        self._schedule_animation()

    def _cancel_animation(self) -> None:
        """Cancel pending animation."""
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None


# ---------------------------------------------------------------------------
# Bird Toast Notification
# ---------------------------------------------------------------------------

class BirdToast(ctk.CTkFrame):
    """A toast notification with bird-themed styling.

    Slides in from the right with a colored accent bar and bird icon.
    Auto-dismisses after a timeout.
    """

    _ICONS = {
        "success": "🦅",
        "error": "🪶",
        "info": "✨",
        "warning": "🔥",
    }

    _COLORS = {
        "success": DULUS_SUCCESS,
        "error": DULUS_ERROR,
        "info": DULUS_ORANGE,
        "warning": DULUS_WARNING,
    }

    def __init__(
        self,
        parent: ctk.CTk,
        message: str,
        toast_type: str = "info",
        duration_ms: int = 3000,
    ) -> None:
        super().__init__(
            parent,
            fg_color=DULUS_DARK_TERTIARY,
            corner_radius=8,
            border_width=1,
            border_color=DULUS_DIM,
        )
        self._duration = duration_ms
        self._create_ui(message, toast_type)

    def _create_ui(self, message: str, toast_type: str) -> None:
        """Build the toast UI."""
        icon = self._ICONS.get(toast_type, "✨")
        color = self._COLORS.get(toast_type, DULUS_ORANGE)

        # Accent bar
        accent = ctk.CTkFrame(self, fg_color=color, width=4, corner_radius=2)
        accent.pack(side="left", fill="y", padx=(0, 0))

        # Content frame
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        # Icon + message
        ctk.CTkLabel(
            content,
            text=f"{icon}  {message}",
            font=("Segoe UI", 12),
            text_color=DULUS_TEXT,
            wraplength=280,
        ).pack(anchor="w")

    def show(self) -> None:
        """Show the toast and schedule dismissal."""
        self.place(relx=1.0, rely=0.02, anchor="ne", x=-16)
        self.after(self._duration, self.destroy)


# ---------------------------------------------------------------------------
# Empty State Widget
# ---------------------------------------------------------------------------

class EmptyState(ctk.CTkFrame):
    """A warm, motivational empty state for new chats.

    Shows the bird avatar, a welcome message, and a motivational quote
    when the chat area is empty.
    """

    def __init__(self, parent: ctk.CTkFrame, avatar: BirdAvatar, on_action: Callable | None = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self._on_action = on_action
        self._create_ui(avatar)

    def _create_ui(self, avatar: BirdAvatar) -> None:
        """Build the empty state UI."""
        import random

        # Center content
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.4, anchor="center")

        # Bird avatar or emoji
        if avatar.logo:
            ctk.CTkLabel(container, image=avatar.logo, text="").pack(pady=(0, 16))
        else:
            ctk.CTkLabel(
                container,
                text="🦅",
                font=("Segoe UI", 64),
            ).pack(pady=(0, 16))

        # Welcome message
        welcome_text = random.choice(_EMPTY_STATE_MESSAGES)
        ctk.CTkLabel(
            container,
            text=welcome_text,
            font=("Segoe UI", 14),
            text_color=DULUS_TEXT,
            wraplength=450,
            justify="center",
        ).pack(pady=(0, 20))

        # Motivational quote
        from soul import get_motivational_phrase
        quote = get_motivational_phrase("general")
        ctk.CTkLabel(
            container,
            text=f"_{quote}_",
            font=("Segoe UI", 11, "italic"),
            text_color=DULUS_DIM,
            wraplength=400,
            justify="center",
        ).pack(pady=(0, 20))

        # Quick action hint
        ctk.CTkLabel(
            container,
            text="💡 Type a message below to get started!",
            font=("Segoe UI", 11),
            text_color=DULUS_ORANGE,
        ).pack()

    def show(self) -> None:
        """Show the empty state as an overlay (place is independent of the
        parent's grid/pack geometry manager, avoiding TclError conflicts)."""
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

    def hide(self) -> None:
        """Hide the empty state."""
        self.place_forget()


# ---------------------------------------------------------------------------
# Permission Dialog
# ---------------------------------------------------------------------------

class _PermissionDialog(ctk.CTkToplevel):
    """Modal permission request dialog with bird branding."""

    def __init__(self, parent: ctk.CTk, description: str, on_resolve: Callable[[bool], None]):
        super().__init__(parent)
        self._on_resolve = on_resolve
        self._create_ui(description)
        self._setup_window(parent)

    def _create_ui(self, description: str) -> None:
        t = get_theme()
        self.configure(fg_color=t["bg"])

        # Bird icon
        ctk.CTkLabel(
            self,
            text="🦅",
            font=("Segoe UI", 32),
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            self,
            text="Permission Required",
            font=("Segoe UI", 16, "bold"),
            text_color=DULUS_ORANGE,
        ).pack(pady=(4, 10))

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
            hover_color=DULUS_ERROR,
            width=100,
            command=self._deny,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Allow",
            font=("Segoe UI", 12, "bold"),
            fg_color=DULUS_ORANGE,
            hover_color=DULUS_ORANGE_LIGHT,
            width=100,
            command=self._allow,
        ).pack(side="left", padx=10)

    def _setup_window(self, parent: ctk.CTk) -> None:
        self.title("Permission Required")
        self.geometry("500x250")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self._center_on_parent(parent)

    def _center_on_parent(self, parent: ctk.CTk) -> None:
        """Center the dialog over its parent."""
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        dw, dh = self.winfo_width(), self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        self.geometry(f"+{x}+{y}")

    def _allow(self) -> None:
        self.destroy()
        self._on_resolve(True)

    def _deny(self) -> None:
        self.destroy()
        self._on_resolve(False)


# ---------------------------------------------------------------------------
# Main launcher
# ---------------------------------------------------------------------------


def launch_gui(config: dict | None = None, initial_prompt: str | None = None) -> None:
    """Launch the Dulus desktop GUI with bird-themed personality.

    Creates a warm, branded experience with the Cigua Palmera as
    the visual identity. Features smooth animations, friendly status
    messages, and motivational empty states.

    Args:
        config: Dulus configuration dict (loaded from disk if None).
        initial_prompt: Optional initial user message to send on startup.
    """
    cfg = config or load_config()

    # Load personality configuration
    personality = PersonalityConfig.load()

    # Ensure MemPalace is initialized for fresh installs
    try:
        from pathlib import Path as _Path
        import subprocess as _sp, sys as _sys, os as _os
        _mp_cfg = _Path.home() / ".mempalace" / "config.json"
        if not _mp_cfg.exists():
            _mem_dir = _Path.home() / ".dulus" / "memory"
            _mem_dir.mkdir(parents=True, exist_ok=True)
            _env = {**_os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            _sp.run(
                [_sys.executable, "-X", "utf8", "-m", "mempalace", "init",
                 str(_mem_dir), "--yes", "--no-llm"],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                env=_env,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
                check=False,
            )
    except Exception:
        pass  # Best-effort; don't block GUI startup

    # Theme
    ctk.set_appearance_mode(cfg.get("appearance", "dark"))
    ctk.set_default_color_theme("dark-blue")
    set_theme(cfg.get("theme", "midnight"))
    t = get_theme()

    # Load bird avatar
    bird_avatar = BirdAvatar()

    # Create GUI window FIRST so user sees something immediately
    app = DulusMainWindow()
    app.set_model(cfg.get("model", "default"))

    # Create bridge (but don't start yet)
    bridge = DulusBridge(config=cfg)

    # Wire bridge into sidebar so context bar / model list work
    app.sidebar.bridge = bridge

    # Track empty state
    _empty_state_visible = True
    _empty_state_widget: EmptyState | None = None

    def _show_empty_state() -> None:
        """Show the motivational empty state."""
        nonlocal _empty_state_visible, _empty_state_widget
        if _empty_state_widget is None:
            # Find the chat frame to attach empty state to
            chat_frame = getattr(app.chat, "frame", app.chat)
            _empty_state_widget = EmptyState(chat_frame, bird_avatar)
        _empty_state_widget.show()
        _empty_state_visible = True

    def _hide_empty_state() -> None:
        """Hide the empty state when messages appear."""
        nonlocal _empty_state_visible
        if _empty_state_widget:
            _empty_state_widget.hide()
        _empty_state_visible = False

    # ------------------------------------------------------------------
    # Sidebar refresh (non-blocking)
    # ------------------------------------------------------------------

    _sidebar_refresh_pending = False

    def _refresh_sidebar_async() -> None:
        """Run scan_sessions in a background thread so the UI never freezes."""
        nonlocal _sidebar_refresh_pending
        if _sidebar_refresh_pending:
            return
        _sidebar_refresh_pending = True

        def _do_scan():
            try:
                data = scan_sessions()
                app.after(0, lambda: app.set_sessions(data))
            finally:
                nonlocal _sidebar_refresh_pending
                _sidebar_refresh_pending = False

        threading.Thread(target=_do_scan, daemon=True).start()

    def _load_session_messages(path: str) -> list[dict]:
        """Load messages directly from a session file."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
            return data.get("messages", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Wire callbacks
    # ------------------------------------------------------------------

    def _on_send(text: str) -> None:
        if text.strip():
            _hide_empty_state()
            app.show_thinking()
            bridge.send_message(text)

    def _on_new_chat() -> None:
        # Save current session if active
        sid = bridge.save_current_session()
        if sid:
            _refresh_sidebar_async()

        app.hide_thinking()
        app.chat.clear_chat()
        bridge.clear_session()
        app.set_active_session(None)
        app.sidebar.update_context_bar()
        app.set_status(_random_status(_STATUS_READY), t["success"])

        # Show empty state for fresh chat
        _show_empty_state()

    def _on_session_select(session_id: str) -> None:
        # Save current session before switching
        sid = bridge.save_current_session()

        if sid:
            _refresh_sidebar_async()

        app.hide_thinking()

        # Find the session file path
        session_path = None
        cached = app.sidebar._session_cache.get(session_id)
        if cached:
            session_path = cached.get("path")
        if not session_path:
            for s in scan_sessions():
                if s["id"] == session_id:
                    session_path = s.get("path")
                    break

        if not session_path:
            return

        # Load messages
        messages = _load_session_messages(session_path)
        if messages:
            _hide_empty_state()
        else:
            _show_empty_state()

        app.chat.load_messages(messages)

        # Defer bridge loading until first message
        bridge.pending_history = messages
        bridge.session_id = session_id
        from agent import AgentState
        bridge.state = AgentState()

        app.set_active_session(session_id)
        app.sidebar.update_context_bar()
        app.set_status("🦅 Session ready (context deferred)", t["success"])

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

    # Load existing sessions into sidebar (async so GUI shows immediately)
    _refresh_sidebar_async()
    app.sidebar._refresh_model_list()
    app.sidebar.update_context_bar()

    # Show empty state initially
    _show_empty_state()

    # ------------------------------------------------------------------
    # Permission dialog handling
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Event polling loop
    # ------------------------------------------------------------------

    def _poll_events() -> None:
        if not app.winfo_exists():
            return

        try:
            while True:
                event = bridge.event_queue.get_nowait()
                etype = event.get("type")

                if etype == "text":
                    _hide_empty_state()
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

                    # Bird-themed success status
                    import random
                    status_msg = random.choice(_STATUS_SUCCESS)
                    app.set_status(f"{status_msg}  (+{itok}/{otok} tok)", t["success"])

                    # Rebuild sidebar if new session
                    sid = event.get("session_id")
                    if sid and sid not in app.sidebar._session_buttons:
                        _refresh_sidebar_async()
                    if sid:
                        app.set_active_session(sid)

                elif etype == "permission":
                    _show_perm(event.get("description", ""))

                elif etype == "error":
                    app.hide_thinking()
                    import random
                    error_msg = random.choice(_STATUS_ERROR)
                    app.chat.add_assistant_message(
                        f"**{error_msg}**\n\nError: {event.get('message', 'Unknown error')}"
                    )
                    app.set_status("🦅 Turbulence detected", t["error"])

        except queue.Empty:
            pass
        except Exception as exc:
            # Log to file
            try:
                with open("gui_error.log", "a", encoding="utf-8") as f:
                    f.write(f"\n[{datetime.datetime.now()}] POLL ERROR: {exc}\n")
                    traceback.print_exc(file=f)
            except Exception:
                pass
        finally:
            # ALWAYS reschedule
            if app.winfo_exists():
                app.after(50, _poll_events)

    app.after(50, _poll_events)

    # ------------------------------------------------------------------
    # Start bridge AFTER UI is ready
    # ------------------------------------------------------------------

    try:
        bridge.start()
        app.set_status(_random_status(_STATUS_READY), t["success"])
    except Exception as exc:
        app.chat.add_assistant_message(
            f"**🦅 Oh no!** I couldn't start my engine...\n\n"
            f"Could not start Dulus bridge: {exc}\n\n"
            f"Try running `/doctor` to diagnose the issue!"
        )
        app.set_status("🦅 Engine trouble", t["error"])

    # ------------------------------------------------------------------
    # Initial prompt
    # ------------------------------------------------------------------

    if initial_prompt:
        _hide_empty_state()
        app.chat.add_user_message(initial_prompt)
        bridge.send_message(initial_prompt)
        app.show_thinking()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

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
