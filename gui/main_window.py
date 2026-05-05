"""Dulus Main Window — customtkinter desktop GUI.

Provides a professional dark-themed interface with sidebar, chat area,
input bar, and top controls. Designed to be wired to a backend bridge
by another agent.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

try:
    import customtkinter as ctk
except ImportError:
    raise ImportError("customtkinter is required. Install: pip install customtkinter")

from gui.chat_widget import ChatWidget
from gui.tasks_view import TasksView
from gui.themes import get_theme, set_theme, list_themes, CURATED_MODELS
from gui.sidebar import DulusSidebar

# ── Theme constants (loaded from active theme) ──────────────────────────────
_SIDEBAR_WIDTH = 260
_INPUT_HEIGHT = 60
_TOPBAR_HEIGHT = 50

_FONT_FAMILY = "Segoe UI"
_FONT_NORMAL = (_FONT_FAMILY, 13)
_FONT_BOLD = (_FONT_FAMILY, 13, "bold")
_FONT_SMALL = (_FONT_FAMILY, 11)
_FONT_TITLE = (_FONT_FAMILY, 18, "bold")
_FONT_LOGO = (_FONT_FAMILY, 22, "bold")

# Initial theme values (overridden by apply_theme)
t = get_theme()
BG_COLOR = t["bg"]
CARD_COLOR = t["card"]
ACCENT_COLOR = t["accent"]
ACCENT_HOVER = t["accent_hover"]
TEXT_COLOR = t["text"]
TEXT_DIM = t["dim"]
BORDER_COLOR = t["border"]
SIDEBAR_WIDTH = _SIDEBAR_WIDTH
INPUT_HEIGHT = _INPUT_HEIGHT
TOPBAR_HEIGHT = _TOPBAR_HEIGHT
FONT_FAMILY = _FONT_FAMILY
FONT_NORMAL = _FONT_NORMAL
FONT_BOLD = _FONT_BOLD
FONT_SMALL = _FONT_SMALL
FONT_TITLE = _FONT_TITLE
FONT_LOGO = _FONT_LOGO


class DulusMainWindow(ctk.CTk):
    """Main Dulus application window."""

    def __init__(self):
        super().__init__()

        # ── Window setup ─────────────────────────────────────────────────────
        self.title("Dulus")
        self.geometry("1100x750")
        self.minsize(900, 600)
        self.configure(fg_color=BG_COLOR)

        # Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self._theme_name = "midnight"  # Placeholder, will be sync'd by apply_theme

        # Grid layout: sidebar | main area
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Callback placeholders (inject from bridge) ───────────────────────
        self.on_send: Callable[[str], None] = lambda text: None
        self.on_new_chat: Callable[[], None] = lambda: None
        self.on_settings: Callable[[], None] = lambda: None
        self.on_model_change: Callable[[str], None] = lambda model: None
        self.on_voice_toggle: Callable[[], None] = lambda: None
        self.on_attach: Callable[[], None] = lambda: None
        self.on_session_select: Callable[[str], None] = lambda sid: None

        # ── Build UI ─────────────────────────────────────────────────────────
        self._build_sidebar()
        self._build_main_area()
        # Initialize with current global theme instead of a hardcoded string
        from gui.themes import get_theme, THEMES
        active = get_theme()
        current_theme_name = "midnight"
        for name, colors in THEMES.items():
            if colors["bg"] == active["bg"] and colors["accent"] == active["accent"]:
                current_theme_name = name
                break
        self.apply_theme(current_theme_name)

    # ═══════════════════════════════════════════════════════════════════════
    #  Sidebar
    # ═══════════════════════════════════════════════════════════════════════

    def _build_sidebar(self) -> None:
        self.sidebar = DulusSidebar(
            self,
            on_new_chat=lambda: self.on_new_chat(),
            on_command=lambda cmd: None,
            on_model_change=lambda model: self.on_model_change(model),
            on_session_select=lambda sid: self._on_sidebar_session_select(sid),
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._active_session_id: str | None = None

    # ═══════════════════════════════════════════════════════════════════════
    #  Main area
    # ═══════════════════════════════════════════════════════════════════════

    def _build_main_area(self) -> None:
        self.main_frame = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=0)

        # ── Top bar ──────────────────────────────────────────────────────────
        self.topbar = ctk.CTkFrame(
            self.main_frame,
            height=TOPBAR_HEIGHT,
            fg_color=CARD_COLOR,
            corner_radius=0,
        )
        self.topbar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.topbar.grid_propagate(False)
        self.topbar.grid_columnconfigure(1, weight=1)

        # Model selector
        self.model_label = ctk.CTkLabel(
            self.topbar,
            text="Modelo:",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        )
        self.model_label.grid(row=0, column=0, padx=(16, 4), pady=10)

        self.model_selector = ctk.CTkOptionMenu(
            self.topbar,
            values=CURATED_MODELS,
            font=FONT_NORMAL,
            dropdown_font=FONT_NORMAL,
            fg_color=BG_COLOR,
            button_color=BORDER_COLOR,
            button_hover_color=ACCENT_HOVER,
            text_color=TEXT_COLOR,
            dropdown_text_color=TEXT_COLOR,
            dropdown_fg_color=CARD_COLOR,
            corner_radius=8,
            width=180,
            command=self._on_model_change,
        )
        self.model_selector.grid(row=0, column=1, sticky="w", pady=10)
        self.model_selector.set(CURATED_MODELS[0])

        # Tasks toggle button
        self.tasks_btn = ctk.CTkButton(
            self.topbar,
            text="🗂️  Tareas",
            font=FONT_BOLD,
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            corner_radius=10,
            height=32,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self._toggle_tasks_view,
        )
        self.tasks_btn.grid(row=0, column=2, sticky="e", padx=(0, 8), pady=10)

        # Status indicators
        self.status_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.status_frame.grid(row=0, column=3, sticky="e", padx=16, pady=10)

        self.status_dot = ctk.CTkLabel(
            self.status_frame,
            text="●",
            font=(FONT_FAMILY, 14),
            text_color="#4caf50",
        )
        self.status_dot.pack(side="left", padx=(0, 4))

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Listo",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        )
        self.status_label.pack(side="left")

        # ── Chat widget ──────────────────────────────────────────────────────
        self.chat = ChatWidget(self.main_frame)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        # ── Tasks view (hidden by default) ───────────────────────────────────
        self.tasks_view = TasksView(self.main_frame)
        self.tasks_view.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.tasks_view.grid_remove()
        self._tasks_visible = False

        # ── Input bar ────────────────────────────────────────────────────────
        self.input_frame = ctk.CTkFrame(
            self.main_frame,
            height=INPUT_HEIGHT,
            fg_color=CARD_COLOR,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.input_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.input_frame.grid_propagate(False)
        self.input_frame.grid_columnconfigure(1, weight=1)

        # Attachment button
        self.attach_btn = ctk.CTkButton(
            self.input_frame,
            text="📎",
            font=(FONT_FAMILY, 16),
            width=36,
            height=36,
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            corner_radius=10,
            command=self._on_attach_click,
        )
        self.attach_btn.grid(row=0, column=0, padx=(10, 4), pady=10)

        # Text input
        self.input_box = ctk.CTkTextbox(
            self.input_frame,
            fg_color="transparent",
            text_color=TEXT_COLOR,
            font=FONT_NORMAL,
            wrap="word",
            activate_scrollbars=False,
            corner_radius=10,
            height=40,
        )
        self.input_box.grid(row=0, column=1, sticky="ew", padx=4, pady=10)
        self.input_box.bind("<KeyRelease-Return>", self._on_enter_key)
        self.input_box.bind("<Shift-Return>", self._on_shift_enter)
        self.input_box.bind("<KeyRelease-KP_Enter>", self._on_enter_key)

        # Voice button
        self.voice_btn = ctk.CTkButton(
            self.input_frame,
            text="🎙",
            font=(FONT_FAMILY, 16),
            width=36,
            height=36,
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            corner_radius=10,
            command=self._on_voice_click,
        )
        self.voice_btn.grid(row=0, column=2, padx=4, pady=10)

        # Send button
        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="➤",
            font=(FONT_FAMILY, 18),
            width=40,
            height=40,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=BG_COLOR,
            corner_radius=12,
            command=self._on_send_click,
        )
        self.send_btn.grid(row=0, column=3, padx=(4, 10), pady=10)

    # ═══════════════════════════════════════════════════════════════════════
    #  Event handlers
    # ═══════════════════════════════════════════════════════════════════════

    def _on_send_click(self) -> None:
        text = self.input_box.get("1.0", "end-1c").strip()
        if text:
            self.chat.add_user_message(text)
            self.input_box.delete("1.0", "end")
            self.on_send(text)

    def _on_enter_key(self, event=None) -> str:
        # Only send if Shift is NOT held
        if event and event.state & 0x1:
            return ""  # Shift held — let default newline happen
        self._on_send_click()
        return "break"

    def _on_shift_enter(self, event=None) -> str:
        self.input_box.insert("insert", "\n")
        return "break"

    def _on_new_chat_click(self) -> None:
        self.chat.clear_chat()
        self.on_new_chat()

    def _on_settings_click(self) -> None:
        self.on_settings()

    def _on_model_change(self, model: str) -> None:
        self.on_model_change(model)

    def _on_voice_click(self) -> None:
        self.on_voice_toggle()

    def _on_attach_click(self) -> None:
        self.on_attach()

    def _toggle_tasks_view(self) -> None:
        if self._tasks_visible:
            self._show_chat_view()
        else:
            self._show_tasks_view()

    def _show_tasks_view(self) -> None:
        self.chat.grid_remove()
        self.input_frame.grid_remove()
        self.tasks_view.grid()
        self.tasks_view.refresh()
        self.tasks_btn.configure(
            text="💬  Chat",
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=BG_COLOR,
            border_width=0,
        )
        self._tasks_visible = True

    def _show_chat_view(self) -> None:
        self.tasks_view.grid_remove()
        self.chat.grid()
        self.input_frame.grid()
        self.tasks_btn.configure(
            text="🗂️  Tareas",
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self._tasks_visible = False

    # ═══════════════════════════════════════════════════════════════════════
    #  Public API for bridge / external controllers
    # ═══════════════════════════════════════════════════════════════════════

    def set_status(self, text: str, color: str = TEXT_DIM) -> None:
        """Update the status label and dot color."""
        self.status_label.configure(text=text, text_color=color)
        self.status_dot.configure(text_color=color)

    def set_model(self, model: str) -> None:
        """Set the model selector value."""
        self.model_selector.set(model)

    def _on_sidebar_session_select(self, sid: str) -> None:
        self.set_active_session(sid)
        self.on_session_select(sid)

    def set_sessions(self, sessions: list[dict]) -> None:
        """Populate the sidebar session list."""
        self.sidebar.set_sessions(sessions)

    def set_active_session(self, session_id: str | None) -> None:
        """Mark a session as active in the sidebar."""
        self._active_session_id = session_id
        self.sidebar.set_active_session(session_id)

    def show_thinking(self) -> None:
        """Show assistant thinking indicator."""
        self.chat.show_thinking()
        self.set_status("Pensando…", ACCENT_COLOR)

    def hide_thinking(self) -> None:
        """Hide thinking indicator."""
        self.chat.hide_thinking()
        self.set_status("Listo", "#4caf50")

    def add_assistant_chunk(self, text: str) -> None:
        """Append streaming text to the current assistant message."""
        self.chat.append_to_last_message(text)

    def add_tool_call(self, name: str, status: str = "running") -> None:
        """Show a tool execution pill."""
        self.chat.add_tool_indicator(name, status)

    def focus_input(self) -> None:
        """Move focus to the input box."""
        self.input_box.focus_set()

    def apply_theme(self, theme_name: str) -> None:
        """Apply a color theme to the main window widgets."""
        t = set_theme(theme_name)
        if not t:
            return
        self._theme_name = theme_name
        global BG_COLOR, CARD_COLOR, ACCENT_COLOR, ACCENT_HOVER, TEXT_COLOR, TEXT_DIM, BORDER_COLOR
        BG_COLOR = t["bg"]
        CARD_COLOR = t["card"]
        ACCENT_COLOR = t["accent"]
        ACCENT_HOVER = t["accent_hover"]
        TEXT_COLOR = t["text"]
        TEXT_DIM = t["dim"]
        BORDER_COLOR = t["border"]

        # 1. Update main window backgrounds first (atomic visual shift)
        self.configure(fg_color=BG_COLOR)
        self.main_frame.configure(fg_color=BG_COLOR)
        self.update_idletasks() # Force redraw of main area before children

        # 2. Update top-level containers
        self.topbar.configure(fg_color=CARD_COLOR)
        self.input_frame.configure(fg_color=CARD_COLOR, border_color=BORDER_COLOR)
        
        # 3. Update widgets
        self.model_selector.configure(
            fg_color=BG_COLOR, button_color=BORDER_COLOR,
            button_hover_color=ACCENT_HOVER, text_color=TEXT_COLOR,
            dropdown_text_color=TEXT_COLOR, dropdown_fg_color=CARD_COLOR,
        )
        self.send_btn.configure(fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color=BG_COLOR)
        self.attach_btn.configure(hover_color=BORDER_COLOR, text_color=TEXT_DIM)
        self.voice_btn.configure(hover_color=BORDER_COLOR, text_color=TEXT_DIM)
        self.input_box.configure(text_color=TEXT_COLOR)
        self.tasks_btn.configure(
            hover_color=BORDER_COLOR, text_color=TEXT_DIM, border_color=BORDER_COLOR
        )
        self.status_label.configure(text_color=TEXT_DIM)
        self.status_dot.configure(text_color=t.get("success", "#4caf50"))
        self.model_label.configure(text_color=TEXT_DIM)
        
        # Redraw all frames to ensure consistency
        self.update()
        if self._tasks_visible:
            self.tasks_btn.configure(
                fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color=BG_COLOR, border_width=0
            )
        else:
            self.tasks_btn.configure(
                hover_color=BORDER_COLOR, text_color=TEXT_DIM, border_color=BORDER_COLOR, border_width=1
            )
            
        # 4. Propagate to children
        self.sidebar.apply_theme()
        
        import gui.chat_widget as _cw
        _cw.BG_COLOR = BG_COLOR
        _cw.CARD_COLOR = CARD_COLOR
        _cw.ACCENT_COLOR = ACCENT_COLOR
        _cw.ACCENT_HOVER = ACCENT_HOVER
        _cw.TEXT_COLOR = TEXT_COLOR
        _cw.TEXT_DIM = TEXT_DIM
        _cw.USER_BUBBLE = t["user_bubble"]
        _cw.ASSISTANT_BUBBLE = t["assistant_bubble"]
        _cw.CODE_BG = t["code_bg"]
        _cw.BORDER_COLOR = BORDER_COLOR
        self.chat.apply_theme()
        
        import gui.tasks_view as _tv
        _tv.BG_COLOR = BG_COLOR
        _tv.CARD_COLOR = CARD_COLOR
        _tv.ACCENT_COLOR = ACCENT_COLOR
        _tv.ACCENT_HOVER = ACCENT_HOVER
        _tv.TEXT_COLOR = TEXT_COLOR
        _tv.TEXT_DIM = TEXT_DIM
        _tv.BORDER_COLOR = BORDER_COLOR
        if hasattr(self.tasks_view, "apply_theme"):
            self.tasks_view.apply_theme()
        
        self.update_idletasks()

    def run(self) -> None:
        """Start the main loop."""
        self.mainloop()
