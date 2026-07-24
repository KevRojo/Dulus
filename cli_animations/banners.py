"""ASCII banners and decorative frames for Dulus."""
from __future__ import annotations

from pathlib import Path
from typing import TextIO

from .ansi import ORANGE, AMBER, clr, gradient_text, pad, resolve_stream

ASSETS = Path(__file__).resolve().parent / "assets" / "ascii"

DULUS_BANNER = r"""
 ██████╗ ██╗   ██╗██╗     ██╗   ██╗███████╗
 ██╔══██╗██║   ██║██║     ██║   ██║██╔════╝
 ██║  ██║██║   ██║██║     ██║   ██║███████╗
 ██║  ██║██║   ██║██║     ██║   ██║╚════██║
 ██████╔╝╚██████╔╝███████╗╚██████╔╝███████║
 ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝
        🦅  Your feathered AI companion
"""

GOD_MODE_BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║  🦅  GOD MODE  ·  MAX EFFORT  ·  LOS MEJORES DEL PLANETA ║
║     Padre e hija 💜  ·  Santo Domingo 🇩🇴                ║
╚══════════════════════════════════════════════════════════╝
"""

CIGUA_PALMERA = r"""
                    🦅
                .--._.
               / o o \
              |   >   |
               \\ - /
            .-'  |  '-.
           /  .-'|'-._ \
          |  /   |    \ |
          |  |  ~+~   | |
           \ |  \|/  | /
            \|   |   |/
             |   |   |
            /    |    \
           /  .--|--.  \
          '   |  |  |   '
              |  |  |
             .|  |  |.
            (_|  |  |_)
               \/ \/
         ~ The Cigua Palmera ~
      National bird of Dominican Republic
"""

WAVE_DIVIDER = "═" * 56
DOT_DIVIDER = "· " * 28

FRAMES = {
    "single": ("┌", "┐", "└", "┘", "─", "│"),
    "double": ("╔", "╗", "╚", "╝", "═", "║"),
    "round": ("╭", "╮", "╰", "╯", "─", "│"),
    "heavy": ("┏", "┓", "┗", "┛", "━", "┃"),
}

BANNERS = {
    "dulus": DULUS_BANNER,
    "god_mode": GOD_MODE_BANNER,
    "cigua": CIGUA_PALMERA,
}


def print_banner(name: str = "dulus", *, stream: TextIO | None = None) -> None:
    """Print a named banner with Dulus orange→gold gradient."""
    stream = resolve_stream(stream)
    art = BANNERS.get(name, DULUS_BANNER)
    for line in art.strip("\n").splitlines():
        stream.write(pad(gradient_text(line, ORANGE, AMBER)) + "\n")
    stream.flush()


def box(
    text: str,
    *,
    title: str = "",
    width: int = 58,
    style: str = "double",
) -> str:
    """Return *text* wrapped in a box frame (no color)."""
    tl, tr, bl, br, h, v = FRAMES.get(style, FRAMES["double"])
    inner_w = max(width - 2, 4)
    lines = text.splitlines() or [""]
    if title:
        title_line = f" {title} "
        # Keep title inside the top border without overflowing
        title_line = title_line[:inner_w]
        top = tl + title_line + h * (inner_w - len(title_line)) + tr
    else:
        top = tl + h * inner_w + tr
    body = [v + line.ljust(inner_w)[:inner_w] + v for line in lines]
    bottom = bl + h * inner_w + br
    return "\n".join([top] + body + [bottom])


def print_box(
    text: str,
    *,
    title: str = "",
    color: str = "orange",
    width: int = 58,
    style: str = "double",
    stream: TextIO | None = None,
) -> None:
    """Print a colored box to *stream*."""
    stream = resolve_stream(stream)
    framed = box(text, title=title, width=width, style=style)
    for line in framed.splitlines():
        stream.write(pad(clr(line, color)) + "\n")
    stream.flush()


def load_ascii_asset(name: str) -> str:
    """Load an ASCII art file from ``assets/ascii/{name}.txt``."""
    # Accept with or without .txt
    stem = name[:-4] if name.endswith(".txt") else name
    path = ASSETS / f"{stem}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def type_banner(text: str, *, char: str = "█", width: int = 56) -> str:
    """Simple block-letter style header bar."""
    return char * width + "\n" + text.center(width) + "\n" + char * width
