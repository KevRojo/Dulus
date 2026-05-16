"""Dulus Main Window — customtkinter desktop GUI.

Provides a professional dark-themed interface with sidebar, chat area,
input bar, and top controls. Designed to be wired to a backend bridge
by another agent.
"""
from __future__ import annotations

import math
import threading
import time
import tkinter as tk
from typing import Callable

# NOTE: pywebview is intentionally NOT imported here. Embedding it inside
# the tkinter event loop crashes on macOS / some Linux setups with
# "pywebview must be created on the main thread", and even when it
# works the embedded surface is fragile across themes/DPI. The webapp
# loader below opens URLs in the user's default browser instead — always
# works, no platform hacks, no thread-safety landmines, and the user
# already has their chosen browser configured.
import webbrowser as _webbrowser_lib

try:
    import customtkinter as ctk
except ImportError:
    raise ImportError("customtkinter is required. Install: pip install customtkinter")

from gui.chat_widget import ChatWidget
from gui.tasks_view import TasksView
from gui.themes import get_theme, set_theme, list_themes, CURATED_MODELS, get_quality_color, get_quality_label
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


# ═══════════════════════════════════════════════════════════════════════════
#  Quality Monitor — tracks health metrics and computes a 0-100 score
# ═══════════════════════════════════════════════════════════════════════════

class QualityMonitor:
    """Monitors backend health and computes an overall quality score (0-100)."""

    # Weight factors
    WEIGHT_CONNECTION = 0.30
    WEIGHT_MODEL = 0.30
    WEIGHT_RESPONSE_TIME = 0.20
    WEIGHT_FEATURES = 0.20

    def __init__(self):
        self.is_connected = False
        self.last_ping_time: float | None = None
        self.model_loaded = False
        self.model_name: str = ""
        self.response_times_ms: list[float] = []
        self.error_count = 0
        self.feature_flags: dict[str, bool] = {}
        self._lock = threading.Lock()

    # ── Setters (called from bridge / polling) ────────────────────────────

    def set_connected(self, connected: bool) -> None:
        with self._lock:
            self.is_connected = connected
            if connected:
                self.last_ping_time = time.time()

    def set_model_status(self, loaded: bool, name: str = "") -> None:
        with self._lock:
            self.model_loaded = loaded
            self.model_name = name

    def record_response_time(self, ms: float) -> None:
        """Record a model response time in milliseconds."""
        with self._lock:
            self.response_times_ms.append(ms)
            # Keep last 20 samples
            if len(self.response_times_ms) > 20:
                self.response_times_ms = self.response_times_ms[-20:]

    def record_error(self) -> None:
        with self._lock:
            self.error_count += 1

    def set_feature(self, name: str, available: bool) -> None:
        with self._lock:
            self.feature_flags[name] = available

    # ── Score computation ─────────────────────────────────────────────────

    def compute_score(self) -> dict:
        """Compute overall quality score and return breakdown dict."""
        with self._lock:
            # Connection score (0 or 100, with decay if no recent ping)
            if self.is_connected and self.last_ping_time:
                elapsed = time.time() - self.last_ping_time
                if elapsed < 30:
                    conn_score = 100
                elif elapsed < 60:
                    conn_score = 70
                elif elapsed < 120:
                    conn_score = 40
                else:
                    conn_score = 0
            else:
                conn_score = 0

            # Model availability score
            model_score = 100 if self.model_loaded else 0

            # Response time score (ideal: <500ms, poor: >5000ms)
            if self.response_times_ms:
                avg_rt = sum(self.response_times_ms) / len(self.response_times_ms)
                if avg_rt < 500:
                    rt_score = 100
                elif avg_rt < 1000:
                    rt_score = 80
                elif avg_rt < 2000:
                    rt_score = 60
                elif avg_rt < 5000:
                    rt_score = 40
                else:
                    rt_score = 20
            else:
                # No data yet — neutral score
                rt_score = 50

            # Feature availability score
            if self.feature_flags:
                feat_score = sum(1 for v in self.feature_flags.values() if v) / len(self.feature_flags) * 100
            else:
                feat_score = 100  # Assume all good if no flags set

            # Weighted total
            total = (
                conn_score * self.WEIGHT_CONNECTION +
                model_score * self.WEIGHT_MODEL +
                rt_score * self.WEIGHT_RESPONSE_TIME +
                feat_score * self.WEIGHT_FEATURES
            )

            return {
                "total": int(total),
                "connection": conn_score,
                "model": model_score,
                "response_time": rt_score,
                "features": feat_score,
                "avg_response_ms": sum(self.response_times_ms) / len(self.response_times_ms) if self.response_times_ms else 0,
                "error_count": self.error_count,
                "is_connected": self.is_connected,
                "model_loaded": self.model_loaded,
                "model_name": self.model_name,
            }


# ═══════════════════════════════════════════════════════════════════════════
#  Circular Progress Indicator (Canvas-based)
# ═══════════════════════════════════════════════════════════════════════════

class CircularProgress(ctk.CTkFrame):
    """A circular progress indicator showing a 0-100 score with color coding."""

    def __init__(self, master, size: int = 36, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.size = size
        self._score = 0
        self._color = "#555555"
        self._pulse_phase = 0.0

        self._canvas = tk.Canvas(
            self,
            width=size,
            height=size,
            bg=self._get_parent_bg(),
            highlightthickness=0,
        )
        self._canvas.pack()

        self._draw_progress()

    def _get_parent_bg(self) -> str:
        """Get the parent's background color for the canvas.
        
        tk.Canvas is a native tkinter widget and cannot use customtkinter's
        "transparent" fg_color, so we map it to a real hex color.
        """
        try:
            color = self.master.cget("fg_color")
            if color == "transparent":
                return BG_COLOR
            return color
        except Exception:
            return BG_COLOR

    def _draw_progress(self) -> None:
        """Draw the circular progress arc and score text."""
        self._canvas.delete("all")
        s = self.size
        padding = 3
        r = (s - padding * 2) // 2
        cx, cy = s // 2, s // 2

        # Background circle (track)
        self._canvas.create_oval(
            padding, padding, s - padding, s - padding,
            outline=BORDER_COLOR, width=2, fill=""
        )

        if self._score > 0:
            # Progress arc
            extent = (self._score / 100) * 360
            start = 90  # Start from top
            self._canvas.create_arc(
                padding, padding, s - padding, s - padding,
                start=start, extent=-extent,
                outline=self._color, width=3, style="arc"
            )

        # Score text
        font_size = max(8, s // 3)
        self._canvas.create_text(
            cx, cy,
            text=str(self._score),
            fill=self._color,
            font=(FONT_FAMILY, font_size, "bold")
        )

    def set_score(self, score: int, color: str | None = None) -> None:
        """Update the displayed score and optionally the color."""
        self._score = max(0, min(100, score))
        if color:
            self._color = color
        self._draw_progress()

    def set_pulse(self, active: bool, color: str = "#4caf50") -> None:
        """Set the pulsing animation state for the connection dot."""
        self._pulse_active = active
        self._pulse_color = color
        if active:
            self._animate_pulse()

    def _animate_pulse(self) -> None:
        """Animate the pulse effect."""
        if not getattr(self, '_pulse_active', False):
            return
        self._pulse_phase = (self._pulse_phase + 0.15) % (2 * math.pi)
        intensity = int(127 + 128 * abs(math.sin(self._pulse_phase)))
        hex_val = f"{intensity:02x}"
        # Parse base color to get R,G,B and apply intensity to alpha channel
        pulse_color = self._pulse_color
        self._color = pulse_color
        self._draw_progress()
        self.after(100, self._animate_pulse)

    def apply_theme(self) -> None:
        """Update canvas background to match current theme."""
        self._canvas.configure(bg=self._get_parent_bg())
        self._draw_progress()


# ═══════════════════════════════════════════════════════════════════════════
#  Webapp Loader Frame — embeds web content with navigation
# ═══════════════════════════════════════════════════════════════════════════

class WebappLoader(ctk.CTkFrame):
    """A frame that loads and displays a web dashboard with navigation controls."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_COLOR, corner_radius=0, **kwargs)

        self._current_url = ""
        self._history: list[str] = []
        self._history_pos = -1

        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Navigation bar ──────────────────────────────────────────────────
        self.nav_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=0, height=36)
        self.nav_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.nav_frame.grid_propagate(False)

        # Back button
        self.back_btn = ctk.CTkButton(
            self.nav_frame, text="◀", font=(FONT_FAMILY, 12),
            width=30, height=28, fg_color="transparent",
            hover_color=BORDER_COLOR, text_color=TEXT_DIM,
            corner_radius=6, command=self._nav_back,
        )
        self.back_btn.pack(side="left", padx=(8, 2), pady=4)

        # Forward button
        self.fwd_btn = ctk.CTkButton(
            self.nav_frame, text="▶", font=(FONT_FAMILY, 12),
            width=30, height=28, fg_color="transparent",
            hover_color=BORDER_COLOR, text_color=TEXT_DIM,
            corner_radius=6, command=self._nav_forward,
        )
        self.fwd_btn.pack(side="left", padx=2, pady=4)

        # Refresh button
        self.refresh_btn = ctk.CTkButton(
            self.nav_frame, text="↻", font=(FONT_FAMILY, 12),
            width=30, height=28, fg_color="transparent",
            hover_color=BORDER_COLOR, text_color=TEXT_DIM,
            corner_radius=6, command=self._nav_refresh,
        )
        self.refresh_btn.pack(side="left", padx=2, pady=4)

        # URL entry
        self.url_entry = ctk.CTkEntry(
            self.nav_frame,
            font=(FONT_FAMILY, 11),
            fg_color=BG_COLOR,
            text_color=TEXT_COLOR,
            border_color=BORDER_COLOR,
            corner_radius=6,
            height=28,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=6, pady=4)
        self.url_entry.bind("<Return>", self._on_url_enter)

        # Go button
        self.go_btn = ctk.CTkButton(
            self.nav_frame, text="Ir", font=(FONT_FAMILY, 11, "bold"),
            width=40, height=28, fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER, text_color=BG_COLOR,
            corner_radius=6, command=self._nav_go,
        )
        self.go_btn.pack(side="left", padx=(2, 8), pady=4)

        # ── Content area ────────────────────────────────────────────────────
        self.content_frame = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Placeholder label — we open URLs in the user's browser, not inside
        # this frame. See the module-level comment for why pywebview is out.
        self._placeholder = ctk.CTkLabel(
            self.content_frame,
            text=(
                "🌐  Dulus Web Dashboard\n\n"
                "Ingresa una URL y pulsa Ir — se abrirá en tu navegador.\n"
                "Atajos comunes:\n"
                "  http://127.0.0.1:5000/         (webchat)\n"
                "  http://127.0.0.1:5000/dashboard (task dashboard)\n"
                "  http://127.0.0.1:5000/sandbox/  (sandbox OS)"
            ),
            font=FONT_NORMAL,
            text_color=TEXT_DIM,
            justify="center",
        )
        self._placeholder.grid(row=0, column=0, sticky="nsew")

    # ── Navigation ──────────────────────────────────────────────────────────

    def _nav_back(self) -> None:
        if self._history_pos > 0:
            self._history_pos -= 1
            url = self._history[self._history_pos]
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self._load_url(url)

    def _nav_forward(self) -> None:
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            url = self._history[self._history_pos]
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
            self._load_url(url)

    def _nav_refresh(self) -> None:
        url = self.url_entry.get().strip()
        if url:
            self._load_url(url)

    def _nav_go(self) -> None:
        url = self.url_entry.get().strip()
        if url:
            self._push_history(url)
            self._load_url(url)

    def _on_url_enter(self, event=None) -> None:
        self._nav_go()

    def _push_history(self, url: str) -> None:
        """Add URL to history, trimming forward history."""
        if self._history_pos < len(self._history) - 1:
            self._history = self._history[:self._history_pos + 1]
        self._history.append(url)
        self._history_pos = len(self._history) - 1

    def _load_url(self, url: str) -> None:
        """Open URL in the user's default browser.

        Embedding webview crashed on too many setups (the "must be created
        on main thread" error) and tk has no native browser widget. So we
        delegate to the OS's default browser via the stdlib `webbrowser`
        module — always works, no extra deps, no threading landmines.
        """
        self._current_url = url
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)

        try:
            _webbrowser_lib.open_new_tab(url)
            self._placeholder.configure(
                text=f"🌐  Abierto en tu navegador:\n\n{url}",
                text_color=TEXT_DIM,
            )
        except Exception as e:
            self._placeholder.configure(
                text=f"❌  No pude abrir el navegador:\n{e}\n\nURL: {url}",
                text_color="#ff5555",
            )

    def load_dashboard(self, endpoint: str = "http://127.0.0.1:5000/dashboard") -> None:
        """Load the Dulus dashboard endpoint (default = local webchat on :5000)."""
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, endpoint)
        self._push_history(endpoint)
        self._load_url(endpoint)

    def apply_theme(self) -> None:
        """Re-apply current theme colors."""
        t = get_theme()
        self.configure(fg_color=t["bg"])
        self.nav_frame.configure(fg_color=t["card"])
        self.content_frame.configure(fg_color=t["bg"])
        self.url_entry.configure(
            fg_color=t["bg"], text_color=t["text"], border_color=t["border"]
        )
        self.back_btn.configure(hover_color=t["border"], text_color=t["dim"])
        self.fwd_btn.configure(hover_color=t["border"], text_color=t["dim"])
        self.refresh_btn.configure(hover_color=t["border"], text_color=t["dim"])
        self.go_btn.configure(
            fg_color=t["accent"], hover_color=t["accent_hover"], text_color=t["bg"]
        )
        self._placeholder.configure(text_color=t["dim"])


# ═══════════════════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════════════════

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

        # Quality monitor
        self.quality = QualityMonitor()
        self._quality_tooltip: tk.Toplevel | None = None

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

        # Start periodic quality update
        self._schedule_quality_update()

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

        # ── Quality score indicator ──────────────────────────────────────────
        self.quality_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.quality_frame.grid(row=0, column=3, sticky="e", padx=(8, 4), pady=10)

        self.quality_circle = CircularProgress(self.quality_frame, size=36)
        self.quality_circle.pack(side="left", padx=(0, 6))
        self.quality_circle.set_score(0, TEXT_DIM)

        # Quality label (clickable for tooltip)
        self.quality_label_btn = ctk.CTkButton(
            self.quality_frame,
            text="Quality",
            font=(FONT_FAMILY, 10),
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            corner_radius=6,
            width=50,
            height=28,
            command=self._show_quality_tooltip,
        )
        self.quality_label_btn.pack(side="left", padx=(0, 4))

        # ── Connection status (pulsing dot) ─────────────────────────────────
        self.status_frame = ctk.CTkFrame(self.topbar, fg_color="transparent")
        self.status_frame.grid(row=0, column=4, sticky="e", padx=(4, 4), pady=10)

        self.status_dot_canvas = tk.Canvas(
            self.status_frame,
            width=14,
            height=14,
            bg=CARD_COLOR,
            highlightthickness=0,
        )
        self.status_dot_canvas.pack(side="left", padx=(0, 4))
        self._status_dot_id = self.status_dot_canvas.create_oval(
            2, 2, 12, 12, fill="#4caf50", outline=""
        )
        self._pulse_after_id: str | None = None
        self._pulse_active = False

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Listo",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        )
        self.status_label.pack(side="left")

        # Response time label
        self.response_time_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=(FONT_FAMILY, 10),
            text_color=TEXT_DIM,
        )
        self.response_time_label.pack(side="left", padx=(8, 0))

        # Error count badge
        self.error_badge = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=(FONT_FAMILY, 10, "bold"),
            text_color="#ff5555",
        )
        self.error_badge.pack(side="left", padx=(8, 0))

        # ── Webapp toggle button ─────────────────────────────────────────────
        self.webapp_btn = ctk.CTkButton(
            self.topbar,
            text="🌐  Web",
            font=FONT_BOLD,
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            corner_radius=10,
            height=32,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self._toggle_webapp_view,
        )
        self.webapp_btn.grid(row=0, column=5, sticky="e", padx=(0, 16), pady=10)

        # ── Chat widget ──────────────────────────────────────────────────────
        self.chat = ChatWidget(self.main_frame)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        # ── Tasks view (hidden by default) ───────────────────────────────────
        self.tasks_view = TasksView(self.main_frame)
        self.tasks_view.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.tasks_view.grid_remove()
        self._tasks_visible = False

        # ── Webapp loader (hidden by default) ────────────────────────────────
        self.webapp_loader = WebappLoader(self.main_frame)
        self.webapp_loader.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.webapp_loader.grid_remove()
        self._webapp_visible = False

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
    #  Quality Score & Status
    # ═══════════════════════════════════════════════════════════════════════

    def _schedule_quality_update(self) -> None:
        """Schedule the next quality score update (every 5 seconds)."""
        self._update_quality_display()
        self.after(5000, self._schedule_quality_update)

    def _update_quality_display(self) -> None:
        """Read quality metrics and update the circular indicator."""
        result = self.quality.compute_score()
        score = result["total"]
        color = get_quality_color(score)
        label = get_quality_label(score)

        self.quality_circle.set_score(score, color)
        self.quality_label_btn.configure(text=f"{label}")

        # Update status dot with pulse when connected
        if result["is_connected"]:
            self._start_pulse()
            self.status_dot_canvas.itemconfigure(self._status_dot_id, fill="#4caf50")
        else:
            self._stop_pulse()
            self.status_dot_canvas.itemconfigure(self._status_dot_id, fill="#ff5555")

        # Update response time label
        avg_rt = result["avg_response_ms"]
        if avg_rt > 0:
            self.response_time_label.configure(text=f"{avg_rt:.0f}ms")
        else:
            self.response_time_label.configure(text="")

        # Update error badge
        err_count = result["error_count"]
        if err_count > 0:
            self.error_badge.configure(text=f"⚠ {err_count} errs")
        else:
            self.error_badge.configure(text="")

        # Store latest result for tooltip
        self._last_quality_result = result

    def _start_pulse(self) -> None:
        """Start the pulsing animation on the status dot."""
        if self._pulse_active:
            return
        self._pulse_active = True
        self._animate_pulse()

    def _stop_pulse(self) -> None:
        """Stop the pulsing animation."""
        self._pulse_active = False
        if self._pulse_after_id:
            self.after_cancel(self._pulse_after_id)
            self._pulse_after_id = None

    def _animate_pulse(self) -> None:
        """Animate the status dot with a pulse effect."""
        if not self._pulse_active:
            return
        # Simple alpha oscillation using color intensity
        phase = (time.time() * 3) % (2 * math.pi)
        intensity = 0.5 + 0.5 * math.sin(phase)
        # Green with varying brightness
        g = int(150 + 105 * intensity)
        color = f"#00{g:02x}00"
        self.status_dot_canvas.itemconfigure(self._status_dot_id, fill=color)
        self._pulse_after_id = self.after(100, self._animate_pulse)

    def _show_quality_tooltip(self) -> None:
        """Show a tooltip window with quality score breakdown."""
        if self._quality_tooltip is not None and self._quality_tooltip.winfo_exists():
            self._quality_tooltip.destroy()
            self._quality_tooltip = None
            return

        result = getattr(self, '_last_quality_result', self.quality.compute_score())

        tooltip = tk.Toplevel(self)
        tooltip.overrideredirect(True)
        tooltip.configure(bg=CARD_COLOR)
        tooltip.attributes("-topmost", True)

        # Content frame
        frame = ctk.CTkFrame(tooltip, fg_color=CARD_COLOR, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        frame.pack(padx=0, pady=0)

        # Title
        ctk.CTkLabel(
            frame,
            text=f"📊 Quality Score: {result['total']}/100",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=get_quality_color(result['total']),
        ).pack(padx=12, pady=(10, 4))

        # Breakdown rows
        items = [
            ("🔗  Conexión", result['connection'], 30),
            ("🤖  Modelo", result['model'], 30),
            ("⏱️  Tiempo resp.", result['response_time'], 20),
            ("⚡  Features", result['features'], 20),
        ]
        for label, val, weight in items:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=label, font=(FONT_FAMILY, 10), text_color=TEXT_DIM).pack(side="left")
            bar_color = get_quality_color(val)
            bar_width = int((val / 100) * 80)
            bar = ctk.CTkFrame(row, fg_color=bar_color, corner_radius=3, width=max(bar_width, 4), height=8)
            bar.pack(side="right", padx=(8, 0))
            ctk.CTkLabel(row, text=f"{val}", font=(FONT_FAMILY, 10, "bold"), text_color=TEXT_COLOR, width=28).pack(side="right")

        # Extra info
        info_text = f"Modelo: {result['model_name'] or 'N/A'}  |  Errores: {result['error_count']}"
        ctk.CTkLabel(
            frame,
            text=info_text,
            font=(FONT_FAMILY, 9),
            text_color=TEXT_DIM,
        ).pack(padx=12, pady=(6, 10))

        # Position near the quality indicator
        self.update_idletasks()
        qx = self.quality_frame.winfo_rootx()
        qy = self.quality_frame.winfo_rooty()
        tooltip.geometry(f"+{qx - 20}+{qy + 45}")

        self._quality_tooltip = tooltip

        # Auto-close after 8 seconds
        self.after(8000, lambda: tooltip.destroy() if tooltip.winfo_exists() else None)

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
        self._hide_all_views()
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
        self._hide_all_views()
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

    def _toggle_webapp_view(self) -> None:
        if self._webapp_visible:
            self._show_chat_view()
        else:
            self._show_webapp_view()

    def _show_webapp_view(self) -> None:
        """Show the webapp loader, hiding chat and input."""
        self._hide_all_views()
        self.webapp_loader.grid()
        self.webapp_loader.load_dashboard()
        self.webapp_btn.configure(
            text="💬  Chat",
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=BG_COLOR,
            border_width=0,
        )
        self._webapp_visible = True

    def _hide_all_views(self) -> None:
        """Hide all main content views (chat, tasks, webapp)."""
        self.chat.grid_remove()
        self.input_frame.grid_remove()
        self.tasks_view.grid_remove()
        self.webapp_loader.grid_remove()

        # Reset all toggle button styles
        self.tasks_btn.configure(
            text="🗂️  Tareas",
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.webapp_btn.configure(
            text="🌐  Web",
            fg_color="transparent",
            hover_color=BORDER_COLOR,
            text_color=TEXT_DIM,
            border_width=1,
            border_color=BORDER_COLOR,
        )

        self._tasks_visible = False
        self._webapp_visible = False

    # ═══════════════════════════════════════════════════════════════════════
    #  Public API for bridge / external controllers
    # ═══════════════════════════════════════════════════════════════════════

    def set_status(self, text: str, color: str = TEXT_DIM) -> None:
        """Update the status label and dot color."""
        self.status_label.configure(text=text, text_color=color)
        # Also update dot color based on status
        if "Listo" in text or "listo" in text.lower():
            self.status_dot_canvas.itemconfigure(self._status_dot_id, fill="#4caf50")
            self.quality.set_connected(True)
        elif "Error" in text or "error" in text.lower() or "Fatal" in text:
            self.status_dot_canvas.itemconfigure(self._status_dot_id, fill="#ff5555")
            self.quality.record_error()
            self.quality.set_connected(False)
        else:
            self.status_dot_canvas.itemconfigure(self._status_dot_id, fill=ACCENT_COLOR)

    def set_model(self, model: str) -> None:
        """Set the model selector value."""
        self.model_selector.set(model)
        self.quality.set_model_status(True, model)

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
        self.webapp_btn.configure(
            hover_color=BORDER_COLOR, text_color=TEXT_DIM, border_color=BORDER_COLOR
        )
        self.status_label.configure(text_color=TEXT_DIM)
        self.model_label.configure(text_color=TEXT_DIM)
        self.response_time_label.configure(text_color=TEXT_DIM)
        self.error_badge.configure(text_color=t.get("error", "#ff5555"))
        
        # Update status dot canvas background
        self.status_dot_canvas.configure(bg=CARD_COLOR)
        
        # Update quality indicator
        self.quality_circle.apply_theme()
        self.quality_label_btn.configure(hover_color=BORDER_COLOR, text_color=TEXT_DIM)
        
        # Redraw all frames to ensure consistency
        self.update()
        if self._tasks_visible:
            self.tasks_btn.configure(
                fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color=BG_COLOR, border_width=0
            )
        elif self._webapp_visible:
            self.webapp_btn.configure(
                fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color=BG_COLOR, border_width=0
            )
        else:
            self.tasks_btn.configure(
                hover_color=BORDER_COLOR, text_color=TEXT_DIM, border_color=BORDER_COLOR, border_width=1
            )
            self.webapp_btn.configure(
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
        
        # Propagate to webapp loader
        self.webapp_loader.apply_theme()
        
        self.update_idletasks()

    def run(self) -> None:
        """Start the main loop."""
        self.mainloop()
