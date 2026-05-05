"""Left sidebar panel for Dulus GUI.

Provides session history, model selector, context-usage bar,
quick-command buttons, available-tools list, and version info.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    import tkinter as ctk
    from tkinter import ttk
    HAS_CTK = False

from config import CONFIG_DIR, SESSIONS_DIR, DAILY_DIR, MR_SESSION_DIR, load_config
from tool_registry import get_all_tools
from providers import PROVIDERS, list_ollama_models
from gui.themes import get_theme, CURATED_MODELS
from gui.session_utils import build_title, scan_sessions, delete_session

# ── Theme constants (mirror main_window.py when available) ──────────────────
BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
ACCENT_COLOR = "#00BCD4"
ACCENT_HOVER = "#00acc1"
MAGENTA_ACCENT = "#e91e63"
TEXT_COLOR = "#eaeaea"
TEXT_DIM = "#a0a0a0"
BORDER_COLOR = "#2a2a4a"
SIDEBAR_WIDTH = 260

FONT_FAMILY = "Segoe UI"
FONT_NORMAL = (FONT_FAMILY, 12)
FONT_BOLD = (FONT_FAMILY, 12, "bold")
FONT_SMALL = (FONT_FAMILY, 10)

# Dulus version
_VERSION = "unknown"
try:
    import dulus as _dulus_mod
    _VERSION = getattr(_dulus_mod, "VERSION", _VERSION)
except Exception:
    pass


class DulusSidebar(ctk.CTkFrame if HAS_CTK else ctk.Frame):
    """Left sidebar with session history, model selector, context bar, tools, and quick commands."""

    def __init__(
        self,
        master,
        bridge=None,
        on_new_chat: Callable[[], None] | None = None,
        on_command: Callable[[str], None] | None = None,
        on_model_change: Callable[[str], None] | None = None,
        on_session_select: Callable[[str], None] | None = None,
        **kwargs,
    ):
        if HAS_CTK:
            kwargs.setdefault("width", SIDEBAR_WIDTH)
            kwargs.setdefault("fg_color", CARD_COLOR)
            kwargs.setdefault("corner_radius", 0)
        else:
            kwargs.setdefault("width", SIDEBAR_WIDTH)
            kwargs.setdefault("bg", CARD_COLOR)

        super().__init__(master, **kwargs)
        self.bridge = bridge
        self.on_new_chat = on_new_chat
        self.on_command = on_command
        self.on_model_change = on_model_change
        self.on_session_select = on_session_select
        self.on_settings: Callable[[], None] | None = None

        self._model_var = ctk.StringVar(value="")
        self._sessions: list[str] = []
        self._session_buttons: dict[str, ctk.CTkButton] = {}
        self._quick_cmd_buttons: list = []
        self._tool_labels: list = []

        self._active_session_id: str | None = None
        self._session_cache: dict[str, dict] = {}

        self._build_ui()
        self._refresh_model_list()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Make the sidebar fixed-width and scrollable
        if HAS_CTK:
            self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        # Scrollable frame container
        if HAS_CTK:
            container = ctk.CTkScrollableFrame(self, fg_color="transparent", width=SIDEBAR_WIDTH - 20)
        else:
            container = ctk.Frame(self, bg=CARD_COLOR)
            # Simple scrollbar for tkinter fallback
            canvas = ctk.Canvas(container, bg=CARD_COLOR, highlightthickness=0)
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
            scroll_frame = ctk.Frame(canvas, bg=CARD_COLOR)
            scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            container = scroll_frame

        container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar_container = container

        # ── Header / Logo ────────────────────────────────────────────────────
        lbl_cls = ctk.CTkLabel if HAS_CTK else ctk.Label
        self._logo_label = lbl_cls(container, text="🦅  Dulus", font=(FONT_FAMILY, 18, "bold"),
             text_color=ACCENT_COLOR if HAS_CTK else ACCENT_COLOR)
        self._logo_label.pack(anchor="w", pady=(0, 2))
        self._subtitle_label = lbl_cls(container, text="AI Coding Assistant", font=FONT_SMALL,
             text_color=TEXT_DIM if HAS_CTK else TEXT_DIM)
        self._subtitle_label.pack(anchor="w", pady=(0, 10))

        # Accent separator
        sep = ctk.CTkFrame if HAS_CTK else ctk.Frame
        self._accent_sep = sep(container, height=2, fg_color=ACCENT_COLOR if HAS_CTK else ACCENT_COLOR,
            **({"bg": ACCENT_COLOR} if not HAS_CTK else {}))
        self._accent_sep.pack(fill="x", pady=(0, 12))

        # ── New Chat button ──────────────────────────────────────────────────
        btn_cls = ctk.CTkButton if HAS_CTK else ctk.Button
        self._new_chat_btn = btn_cls(
            container,
            text="+  Nueva conversación",
            font=FONT_BOLD,
            fg_color=ACCENT_COLOR if HAS_CTK else ACCENT_COLOR,
            hover_color=ACCENT_HOVER if HAS_CTK else ACCENT_HOVER,
            text_color=BG_COLOR if HAS_CTK else BG_COLOR,
            **({"bg": ACCENT_COLOR} if not HAS_CTK else {}),
            command=self._on_new_chat_click,
        )
        self._new_chat_btn.pack(fill="x", pady=(0, 12))

        # ── Session list ─────────────────────────────────────────────────────
        self._sess_label = lbl_cls(container, text="Historial", font=FONT_BOLD,
                 text_color=TEXT_COLOR if HAS_CTK else TEXT_COLOR)
        self._sess_label.pack(anchor="w", pady=(0, 6))

        frame_cls = ctk.CTkFrame if HAS_CTK else ctk.Frame
        self.session_frame = frame_cls(container, fg_color="transparent" if HAS_CTK else CARD_COLOR,
                                                **({"bg": CARD_COLOR} if not HAS_CTK else {}))
        self.session_frame.pack(fill="x", pady=(0, 12))

        # ── Model selector ───────────────────────────────────────────────────
        self._model_label = lbl_cls(container, text="Modelo activo", font=FONT_BOLD,
                  text_color=TEXT_COLOR if HAS_CTK else TEXT_COLOR)
        self._model_label.pack(anchor="w", pady=(0, 6))

        if HAS_CTK:
            self.model_combo = ctk.CTkOptionMenu(
                container,
                values=[],
                variable=self._model_var,
                command=self._on_model_change,
                font=FONT_NORMAL,
                dropdown_font=FONT_NORMAL,
            )
        else:
            self.model_combo = ttk.Combobox(container, textvariable=self._model_var, state="readonly")
            self.model_combo.bind("<<ComboboxSelected>>", lambda e: self._on_model_change(self._model_var.get()))

        self.model_combo.pack(fill="x", pady=(0, 12))

        # ── Context usage bar ────────────────────────────────────────────────
        self._ctx_label = lbl_cls(container, text="Uso de contexto", font=FONT_BOLD,
                text_color=TEXT_COLOR if HAS_CTK else TEXT_COLOR)
        self._ctx_label.pack(anchor="w", pady=(0, 6))

        self.context_label = lbl_cls(
            container, text="0 / 250000", font=FONT_SMALL,
            text_color=TEXT_DIM if HAS_CTK else TEXT_DIM,
        )
        self.context_label.pack(anchor="w")

        if HAS_CTK:
            self.context_bar = ctk.CTkProgressBar(
                container, height=8, corner_radius=4,
                progress_color=ACCENT_COLOR,
                fg_color=BORDER_COLOR,
            )
            self.context_bar.set(0.0)
        else:
            self.context_bar = ttk.Progressbar(container, length=SIDEBAR_WIDTH - 40, mode="determinate")
            self.context_bar["value"] = 0

        self.context_bar.pack(fill="x", pady=(4, 12))

        # ── Quick commands ───────────────────────────────────────────────────
        self._cmd_label = lbl_cls(container, text="Comandos rápidos", font=FONT_BOLD,
                text_color=TEXT_COLOR if HAS_CTK else TEXT_COLOR)
        self._cmd_label.pack(anchor="w", pady=(0, 6))

        self._cmd_frame = frame_cls(container, fg_color="transparent" if HAS_CTK else CARD_COLOR,
                              **({"bg": CARD_COLOR} if not HAS_CTK else {}))
        self._cmd_frame.pack(fill="x", pady=(0, 12))

        for col, (cmd, label) in enumerate([
            ("/clear", "/clear"),
            ("/context", "/context"),
            ("/cost", "/cost"),
            ("/verbose", "/verbose"),
        ]):
            btn = btn_cls(
                self._cmd_frame,
                text=label,
                font=FONT_SMALL,
                width=60,
                height=28,
                fg_color=BORDER_COLOR if HAS_CTK else BORDER_COLOR,
                hover_color=ACCENT_HOVER if HAS_CTK else ACCENT_HOVER,
                text_color=TEXT_COLOR if HAS_CTK else TEXT_COLOR,
                **({"bg": BORDER_COLOR} if not HAS_CTK else {}),
                command=lambda c=cmd: self._on_command_click(c),
            )
            btn.grid(row=0, column=col, padx=2, pady=2)
            self._quick_cmd_buttons.append(btn)

        # ── Bottom buttons (outside scroll area) ─────────────────────────────
        self._bottom_frame = frame_cls(self, fg_color="transparent" if HAS_CTK else CARD_COLOR,
                                       **({"bg": CARD_COLOR} if not HAS_CTK else {}))
        self._bottom_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self._bottom_frame.grid_columnconfigure(0, weight=1)

        self._settings_btn = btn_cls(
            self._bottom_frame,
            text="⚙  Ajustes",
            font=FONT_NORMAL,
            fg_color="transparent" if HAS_CTK else CARD_COLOR,
            hover_color=BORDER_COLOR if HAS_CTK else BORDER_COLOR,
            text_color=TEXT_COLOR if HAS_CTK else TEXT_COLOR,
            **({"bg": CARD_COLOR} if not HAS_CTK else {}),
            corner_radius=10,
            height=36,
            border_width=1 if HAS_CTK else 0,
            border_color=BORDER_COLOR if HAS_CTK else BORDER_COLOR,
            command=self._on_settings_click,
        )
        self._settings_btn.grid(row=0, column=0, sticky="ew")

    # ── Refresh helpers ───────────────────────────────────────────────────────

    def set_sessions(self, sessions: list[dict]) -> None:
        """Update the session history list in the sidebar."""
        # Clear existing buttons
        for widget in getattr(self.session_frame, "winfo_children", lambda: [])():
            widget.destroy()
        self._session_buttons.clear()
        self._sessions = []

        if not sessions:
            lbl = ctk.CTkLabel if HAS_CTK else ctk.Label
            lbl(self.session_frame, text="(sin sesiones)", font=FONT_SMALL,
                text_color=TEXT_DIM if HAS_CTK else TEXT_DIM).pack(anchor="w")
            return

        btn_cls = ctk.CTkButton if HAS_CTK else ctk.Button
        frm_cls = ctk.CTkFrame if HAS_CTK else ctk.Frame
        
        for sess in sessions:
            sid = sess.get("id", "")
            title = sess.get("title", "Untitled")
            self._sessions.append(sid)
            
            # Row container for button + delete
            row = frm_cls(self.session_frame, fg_color="transparent" if HAS_CTK else CARD_COLOR)
            row.pack(fill="x", pady=1)
            row.grid_columnconfigure(0, weight=1)
            
            # Main session button
            btn = btn_cls(
                row,
                text=title,
                font=FONT_SMALL,
                fg_color="transparent" if HAS_CTK else CARD_COLOR,
                hover_color=BORDER_COLOR if HAS_CTK else BORDER_COLOR,
                text_color=TEXT_DIM if HAS_CTK else TEXT_DIM,
                **({"bg": CARD_COLOR} if not HAS_CTK else {}),
                anchor="w",
                height=28,
                command=lambda s=sid: self._on_session_click(s),
            )
            btn.grid(row=0, column=0, sticky="ew")
            self._session_buttons[sid] = btn
            
            # Delete button (X)
            del_btn = btn_cls(
                row,
                text=" \u2715 ", # Unicode X
                width=24,
                height=24,
                font=(FONT_FAMILY, 10, "bold"),
                fg_color="transparent" if HAS_CTK else CARD_COLOR,
                hover_color="#aa3333", # Reddish on hover
                text_color=TEXT_DIM if HAS_CTK else TEXT_DIM,
                command=lambda s=sid: self._on_delete_click(s),
            )
            del_btn.grid(row=0, column=1, padx=(0, 2))
            
        self._highlight_active_session()

    def _on_delete_click(self, session_id: str) -> None:
        """Handle session deletion from the sidebar."""
        if delete_session(session_id):
            # Refresh the list
            self.refresh_sessions()
            # If the deleted session was active, reset chat
            if self._active_session_id == session_id:
                if self.on_new_chat:
                    self.on_new_chat()

    def set_active_session(self, session_id: str | None) -> None:
        """Mark a session as active in the sidebar."""
        self._active_session_id = session_id
        self._highlight_active_session()

    def _highlight_active_session(self) -> None:
        if not HAS_CTK:
            return
        for sid, btn in self._session_buttons.items():
            if sid == self._active_session_id:
                btn.configure(
                    fg_color=ACCENT_COLOR,
                    text_color=BG_COLOR,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=TEXT_DIM,
                )

    def refresh_sessions(self) -> None:
        """Load session history from all session directories (auto-scan)."""
        data = scan_sessions()
        self._session_cache = {s["id"]: s for s in data}
        self.set_sessions(data)
    def _on_settings_click(self) -> None:
        if self.on_settings:
            self.on_settings()

    def _on_session_click(self, sid: str) -> None:
        if self.on_session_select:
            self.on_session_select(sid)

    def _refresh_tools(self) -> None:
        """Populate the tools list from the registry."""
        for widget in getattr(self.tools_frame, "winfo_children", lambda: [])():
            widget.destroy()

        tools = get_all_tools()
        if not tools:
            lbl = ctk.CTkLabel if HAS_CTK else ctk.Label
            lbl(self.tools_frame, text="(ninguna tool cargada)", font=FONT_SMALL,
                text_color=TEXT_DIM if HAS_CTK else TEXT_DIM).pack(anchor="w")
            return

        lbl_cls = ctk.CTkLabel if HAS_CTK else ctk.Label
        for t in tools:
            name = t.name
            lbl_cls(
                self.tools_frame,
                text=f"• {name}",
                font=FONT_SMALL,
                text_color=TEXT_DIM if HAS_CTK else TEXT_DIM,
            ).pack(anchor="w")

    def _refresh_model_list(self) -> None:
        """Populate the model dropdown from curated list."""
        models = CURATED_MODELS
        
        current = self.bridge.config.get("model", models[0]) if self.bridge else models[0]
        self._model_var.set(current)

        if HAS_CTK:
            self.model_combo.configure(values=models)
        else:
            self.model_combo["values"] = models

    def update_context_bar(self) -> None:
        """Refresh the context usage progress bar (call from UI thread)."""
        if not self.bridge:
            return
        used, limit = self.bridge.get_context_usage()
        pct = min(used / limit, 1.0) if limit else 0.0

        self.context_label.configure(
            text=f"{used:,} / {limit:,}"
        ) if HAS_CTK else self.context_label.config(text=f"{used:,} / {limit:,}")

        if HAS_CTK:
            self.context_bar.set(pct)
            # Color coding: green -> yellow -> red
            if pct < 0.5:
                self.context_bar.configure(progress_color=ACCENT_COLOR)
            elif pct < 0.8:
                self.context_bar.configure(progress_color="#FFC107")
            else:
                self.context_bar.configure(progress_color="#F44336")
        else:
            self.context_bar["value"] = pct * 100

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_new_chat_click(self) -> None:
        if self.bridge:
            self.bridge.clear_session()
        if self.on_new_chat:
            self.on_new_chat()
        self.update_context_bar()

    def _on_command_click(self, cmd: str) -> None:
        if self.on_command:
            self.on_command(cmd)
        # Local handling for commands that affect bridge state directly
        if cmd == "/clear" and self.bridge:
            self.bridge.clear_session()
            self.update_context_bar()
        elif cmd == "/verbose" and self.bridge:
            current = self.bridge.config.get("verbose", False)
            self.bridge.config["verbose"] = not current

    def _on_model_change(self, model: str) -> None:
        if self.bridge:
            self.bridge.set_model(model)
        if self.on_model_change:
            self.on_model_change(model)

    def _on_session_click(self, path: str) -> None:
        if self.on_session_select:
            self.on_session_select(path)

    def apply_theme(self, t: dict | None = None) -> None:
        """Re-apply current theme colors to all sidebar widgets."""
        if t is None:
            t = get_theme()
        if not HAS_CTK:
            return
        # Update module-level globals so future widgets pick them up
        global BG_COLOR, CARD_COLOR, ACCENT_COLOR, ACCENT_HOVER, TEXT_COLOR, TEXT_DIM, BORDER_COLOR
        BG_COLOR = t["bg"]
        CARD_COLOR = t["card"]
        ACCENT_COLOR = t["accent"]
        ACCENT_HOVER = t["accent_hover"]
        TEXT_COLOR = t["text"]
        TEXT_DIM = t["dim"]
        BORDER_COLOR = t["border"]
        # Main frame
        self.configure(fg_color=t["card"])
        if hasattr(self, "_sidebar_container"):
            self._sidebar_container.configure(fg_color="transparent")
        
        # Internal frames
        if hasattr(self, "session_frame"):
            self.session_frame.configure(fg_color="transparent")
        if hasattr(self, "_cmd_frame"):
            self._cmd_frame.configure(fg_color="transparent")
        if hasattr(self, "_bottom_frame"):
            self._bottom_frame.configure(fg_color="transparent")

        self.update_idletasks()
        # Logo
        self._logo_label.configure(text_color=t["accent"])
        self._subtitle_label.configure(text_color=t["dim"])
        self._accent_sep.configure(fg_color=t["accent"])
        # New chat button
        self._new_chat_btn.configure(
            fg_color=t["accent"], hover_color=t["accent_hover"], text_color=t["bg"]
        )
        # Labels
        self._sess_label.configure(text_color=t["text"])
        self._model_label.configure(text_color=t["text"])
        self._ctx_label.configure(text_color=t["text"])
        self._cmd_label.configure(text_color=t["text"])
        # Separators
        # Model combo
        self.model_combo.configure(
            fg_color=t["card"], button_color=t["border"],
            button_hover_color=t["accent_hover"], text_color=t["text"],
            dropdown_text_color=t["text"], dropdown_fg_color=t["card"],
        )
        # Context bar
        self.context_label.configure(text_color=t["dim"])
        self.context_bar.configure(fg_color=t["border"], progress_color=t["accent"])
        # Quick cmd buttons
        for btn in self._quick_cmd_buttons:
            btn.configure(
                fg_color=t["border"], hover_color=t["accent_hover"], text_color=t["text"]
            )
        # Session buttons
        for btn in self._session_buttons.values():
            btn.configure(
                fg_color="transparent", hover_color=t["border"], text_color=t["text"]
            )
        # Tool labels
        for lbl in self._tool_labels:
            lbl.configure(text_color=t["dim"])
        # Settings button
        self._settings_btn.configure(
            hover_color=t["border"], text_color=t["text"], border_color=t["border"]
        )
