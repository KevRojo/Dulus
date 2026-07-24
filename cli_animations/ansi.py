"""ANSI color + shared design tokens for the Dulus terminal.

One visual language for every module: same palette, same bar glyphs,
same connectors, same status icons. Cross-platform (macOS/Linux/Windows).
"""
from __future__ import annotations

import os
import sys
from typing import Sequence


def _enable_windows_ansi() -> None:
    """Enable virtual terminal sequences on Windows consoles."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _ensure_utf8() -> None:
    """Make stdout/stderr UTF-8 so box-drawing glyphs and emoji never raise
    UnicodeEncodeError on legacy Windows (cp1252) consoles.

    Runs on import so even a bare ``print_banner()`` is safe — not just the
    demo. Best-effort and idempotent: it never raises, even if a stream can't
    be reconfigured. ``errors='replace'`` is a final backstop so an odd glyph
    degrades to a placeholder instead of crashing the host program.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
            if enc == "utf8":
                continue
            reconfigure = getattr(stream, "reconfigure", None)
            if callable(reconfigure):
                reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_enable_windows_ansi()
_ensure_utf8()

# ── Brand RGB ──────────────────────────────────────────────────────────────
ORANGE = (255, 135, 0)
GOLD = (255, 175, 0)
AMBER = (255, 200, 50)
CYAN = (0, 200, 255)
PURPLE = (160, 100, 255)
GREEN = (80, 220, 120)
RED = (255, 70, 70)
WHITE = (240, 240, 240)
MUTED = (110, 110, 120)  # track / empty / pending
DIM_RGB = (80, 80, 88)

# Smooth bar gradient stops: empty → fill head (left→right warmth)
BAR_GRADIENT: list[tuple[int, int, int]] = [
    (255, 120, 0),   # deep orange
    (255, 155, 20),  # mid
    (255, 195, 60),  # gold tip
]

# ── ANSI codes ─────────────────────────────────────────────────────────────
DULUS_ORANGE = f"\033[38;2;{ORANGE[0]};{ORANGE[1]};{ORANGE[2]}m"
DULUS_GOLD = f"\033[38;2;{GOLD[0]};{GOLD[1]};{GOLD[2]}m"
DULUS_AMBER = f"\033[38;2;{AMBER[0]};{AMBER[1]};{AMBER[2]}m"
DULUS_CYAN = f"\033[38;2;{CYAN[0]};{CYAN[1]};{CYAN[2]}m"
DULUS_PURPLE = f"\033[38;2;{PURPLE[0]};{PURPLE[1]};{PURPLE[2]}m"

C = {
    "orange": DULUS_ORANGE,
    "gold": DULUS_GOLD,
    "amber": DULUS_AMBER,
    "cyan": DULUS_CYAN,
    "purple": DULUS_PURPLE,
    "green": f"\033[38;2;{GREEN[0]};{GREEN[1]};{GREEN[2]}m",
    "red": f"\033[38;2;{RED[0]};{RED[1]};{RED[2]}m",
    "white": "\033[97m",
    "gray": f"\033[38;2;{MUTED[0]};{MUTED[1]};{MUTED[2]}m",
    "muted": f"\033[38;2;{MUTED[0]};{MUTED[1]};{MUTED[2]}m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "italic": "\033[3m",
    "underline": "\033[4m",
    "reset": "\033[0m",
    "clear_line": "\033[2K",
    "cursor_up": "\033[1A",
    "hide_cursor": "\033[?25l",
    "show_cursor": "\033[?25h",
}

# ── Shared glyphs (ONE alphabet for the whole kit) ─────────────────────────
GLYPH = {
    # continuous bars (same family everywhere)
    "bar_full": "━",
    "bar_half": "╸",
    "bar_empty": "─",
    "bar_block": "█",       # solid block (dense mode)
    "bar_block_empty": "░",
    "bar_soft_empty": "┄",  # soft track
    # nodes / steps
    "node_done": "●",
    "node_active": "◎",
    "node_pending": "○",
    "node_error": "✕",
    # connectors
    "link": "──",
    "link_soft": " · ",
    "tree_mid": "├─",
    "tree_end": "└─",
    "tree_pipe": "│",
    "sep": "│",
    # status
    "ok": "✓",
    "fail": "✕",
    "warn": "!",
    "info": "i",
    "run": "◎",
    # framing
    "bracket_l": "⟨",
    "bracket_r": "⟩",
    "pad": "  ",  # left indent for every line
}


def supports_color() -> bool:
    """Return True when ANSI colors should be emitted."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if hasattr(sys.stdout, "isatty"):
        return bool(sys.stdout.isatty())
    return False


def animations_enabled(stream=None) -> bool:
    """Return True when cursor-based animation is safe and desired.

    Redirected output, CI logs, ``TERM=dumb`` and the explicit
    ``DULUS_NO_ANIMATIONS`` switch all receive an immediate static render.
    """
    if os.environ.get("DULUS_NO_ANIMATIONS"):
        return False
    if os.environ.get("TERM", "").lower() == "dumb":
        return False
    target = stream or sys.stdout
    try:
        return bool(target.isatty())
    except Exception:
        return False


def clr(text: str, *keys: str) -> str:
    """Wrap *text* with one or more named styles from ``C``."""
    if not supports_color():
        return str(text)
    try:
        prefix = "".join(C[k] for k in keys)
    except KeyError as exc:
        raise KeyError(f"Unknown color/style key: {exc.args[0]!r}") from None
    return prefix + str(text) + C["reset"]


def rgb(r: int, g: int, b: int, text: str) -> str:
    """Truecolor foreground for a single string."""
    if not supports_color():
        return str(text)
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return f"\033[38;2;{r};{g};{b}m{text}{C['reset']}"


def rgb_tuple(color: tuple[int, int, int], text: str) -> str:
    return rgb(color[0], color[1], color[2], text)


def lerp_color(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(start[0] + (end[0] - start[0]) * t),
        int(start[1] + (end[1] - start[1]) * t),
        int(start[2] + (end[2] - start[2]) * t),
    )


def gradient_stops(
    t: float,
    stops: Sequence[tuple[int, int, int]] = BAR_GRADIENT,
) -> tuple[int, int, int]:
    """Sample a multi-stop gradient at t∈[0,1]."""
    if not stops:
        return ORANGE
    if len(stops) == 1:
        return stops[0]
    t = max(0.0, min(1.0, t))
    pos = t * (len(stops) - 1)
    i = int(pos)
    if i >= len(stops) - 1:
        return stops[-1]
    frac = pos - i
    return lerp_color(stops[i], stops[i + 1], frac)


def gradient_text(
    text: str,
    start: tuple[int, int, int] = ORANGE,
    end: tuple[int, int, int] = AMBER,
) -> str:
    """Per-character linear RGB gradient from *start* to *end*."""
    if not text or not supports_color():
        return text
    n = len(text)
    parts: list[str] = []
    for i, ch in enumerate(text):
        t = i / max(n - 1, 1)
        parts.append(rgb_tuple(lerp_color(start, end, t), ch))
    return "".join(parts)


def render_track(
    fraction: float,
    *,
    width: int = 28,
    style: str = "line",
    gradient: bool = True,
) -> str:
    """Unified continuous track used by progress bars AND effort slider.

    style:
      * ``line``  — ━ / ╸ / ─  (sleek, connected)
      * ``block`` — █ / ░      (dense)
      * ``soft``  — ━ / ┄      (soft empty)
    """
    fraction = max(0.0, min(1.0, fraction))
    exact = fraction * width
    full = int(exact)
    partial = exact - full  # 0..1 leftover cell

    if style == "block":
        filled_ch = GLYPH["bar_block"]
        empty_ch = GLYPH["bar_block_empty"]
        half_ch = "▓"
    elif style == "soft":
        filled_ch = GLYPH["bar_full"]
        empty_ch = GLYPH["bar_soft_empty"]
        half_ch = GLYPH["bar_half"]
    else:  # line (default — the connected look)
        filled_ch = GLYPH["bar_full"]
        empty_ch = GLYPH["bar_empty"]
        half_ch = GLYPH["bar_half"]

    parts: list[str] = []
    for i in range(width):
        t = i / max(width - 1, 1)
        if i < full:
            color = gradient_stops(t) if gradient else ORANGE
            parts.append(rgb_tuple(color, filled_ch))
        elif i == full and partial >= 0.3:
            color = gradient_stops(t) if gradient else GOLD
            parts.append(rgb_tuple(color, half_ch))
        else:
            parts.append(rgb_tuple(MUTED, empty_ch))
    return "".join(parts)


def pad(text: str = "") -> str:
    """Left-pad every public line the same way."""
    return GLYPH["pad"] + text
