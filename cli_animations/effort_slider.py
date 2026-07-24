"""Effort slider — Claude Code-style reasoning effort selector.

Uses the SAME continuous track as progress bars (``ansi.render_track``),
so the kit feels coherent. Cross-platform key input:
  * Unix  → termios/tty
  * Windows → msvcrt
  * Non-TTY → numbered menu
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from importlib import import_module
from typing import Any, TextIO, cast

from .ansi import (
    C,
    GLYPH,
    GOLD,
    MUTED,
    ORANGE,
    animations_enabled,
    clr,
    pad,
    render_track,
    resolve_stream,
    rgb_tuple,
)

EFFORT_LEVELS = [
    ("minimal", "⚡", "Fast — surface-level reasoning"),
    ("low", "·", "Quick passes, light thinking"),
    ("medium", "◎", "Balanced depth and speed"),
    ("high", "◆", "Deep analysis, thorough"),
    ("max", "🦅", "God mode — maximum effort"),
]

SLIDER_WIDTH = 28


@dataclass
class EffortConfig:
    level: str = "medium"
    index: int = 2

    @classmethod
    def from_level(cls, level: str) -> "EffortConfig":
        names = [e[0] for e in EFFORT_LEVELS]
        idx = names.index(level) if level in names else 2
        return cls(level=names[idx], index=idx)

    @classmethod
    def from_index(cls, index: int) -> "EffortConfig":
        idx = max(0, min(int(index), len(EFFORT_LEVELS) - 1))
        return cls(level=EFFORT_LEVELS[idx][0], index=idx)


def _fraction_for_index(index: int) -> float:
    n = len(EFFORT_LEVELS)
    if n <= 1:
        return 1.0
    return index / (n - 1)


def render_effort_slider(
    index: int = 2,
    *,
    label: str = "Effort",
    show_labels: bool = True,
    stream: TextIO | None = None,
) -> None:
    """Print a static effort slider at *index* — same track as progress bars."""
    stream = resolve_stream(stream)
    index = max(0, min(index, len(EFFORT_LEVELS) - 1))
    name, icon, desc = EFFORT_LEVELS[index]
    frac = _fraction_for_index(index)
    track = render_track(frac, width=SLIDER_WIDTH, style="line", gradient=True)

    header = (
        f"{clr(label, 'bold', 'white')}  {track}  "
        f"{icon} {rgb_tuple(ORANGE if index < 4 else GOLD, name.upper())}"
    )
    stream.write(pad(header) + "\n")

    if show_labels:
        stream.write(pad(clr(desc, "dim")) + "\n")
        # evenly spaced tick labels under the track
        ticks: list[str] = []
        for i, (lvl, _, _) in enumerate(EFFORT_LEVELS):
            if i == index:
                ticks.append(rgb_tuple(ORANGE, lvl))
            else:
                ticks.append(rgb_tuple(MUTED, lvl))
        # join with soft separators so it reads as one scale
        stream.write(pad(f" {rgb_tuple(MUTED, ' · ').join(ticks)}") + "\n")
    stream.flush()


def render_effort_bar(
    value: float,
    *,
    width: int = SLIDER_WIDTH,
    label: str = "Effort",
) -> str:
    """Static 0.0–1.0 bar — identical language to ``render_bar``."""
    value = max(0.0, min(1.0, value))
    track = render_track(value, width=width, style="line", gradient=True)
    pct = int(value * 100)
    return pad(f"{clr(label, 'bold')}  {track}  {rgb_tuple(GOLD, f'{pct}%')}")


# ── key reading (cross-platform) ───────────────────────────────────────────

def _stdin_is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def _read_key_unix() -> str:
    termios = cast(Any, import_module("termios"))
    tty = cast(Any, import_module("tty"))

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_key_windows() -> str:
    msvcrt = cast(Any, import_module("msvcrt"))

    ch = str(msvcrt.getwch())
    if ch in ("\x00", "\xe0"):
        scan = str(msvcrt.getwch())
        mapping = {
            "K": "\x1b[D",
            "M": "\x1b[C",
            "H": "\x1b[A",
            "P": "\x1b[B",
        }
        return mapping[scan] if scan in mapping else scan
    if ch == "\r":
        return "\r"
    if ch == "\x03":
        return "\x03"
    return ch


def _read_key() -> str:
    if sys.platform == "win32":
        return _read_key_windows()
    return _read_key_unix()


def _select_effort_menu(initial: str, stream: TextIO) -> EffortConfig:
    """Fallback numbered menu for non-TTY / broken raw mode."""
    cfg = EffortConfig.from_level(initial)
    stream.write("\n")
    stream.write(pad(clr("Select effort level", "bold")) + "\n")
    for i, (name, icon, desc) in enumerate(EFFORT_LEVELS):
        mark = rgb_tuple(ORANGE, "→") if i == cfg.index else " "
        stream.write(
            pad(f"{mark} {i + 1}. {icon} {name:<8}  {clr(desc, 'dim')}") + "\n"
        )
    stream.write(
        pad(clr(f"Choice [1-{len(EFFORT_LEVELS)}] (Enter={cfg.level}): ", "dim"))
    )
    stream.flush()
    try:
        raw = input().strip()
    except (EOFError, KeyboardInterrupt):
        stream.write("\n")
        return cfg
    if not raw:
        return cfg
    if raw.isdigit() and 1 <= int(raw) <= len(EFFORT_LEVELS):
        return EffortConfig.from_index(int(raw) - 1)
    names = [e[0] for e in EFFORT_LEVELS]
    if raw.lower() in names:
        return EffortConfig.from_level(raw.lower())
    return cfg


def select_effort(
    initial: str = "medium",
    *,
    stream: TextIO | None = None,
) -> EffortConfig:
    """Interactive effort slider (TTY) or numbered menu (fallback)."""
    stream = resolve_stream(stream)
    cfg = EffortConfig.from_level(initial)
    n = len(EFFORT_LEVELS)

    if not _stdin_is_tty():
        return _select_effort_menu(initial, stream)

    def _draw() -> None:
        # redraw 3 lines: header + desc + ticks
        stream.write(C["cursor_up"] * 3)
        for _ in range(3):
            stream.write(C["clear_line"] + "\n")
        stream.write(C["cursor_up"] * 3)
        render_effort_slider(cfg.index, stream=stream)
        stream.write(
            pad(clr("← → · 1-5 · Enter confirm · q cancel", "dim")) + "\n"
        )
        stream.flush()

    stream.write(C["hide_cursor"])
    stream.write("\n" * 3)
    stream.flush()
    _draw()

    try:
        while True:
            try:
                key = _read_key()
            except Exception:
                stream.write(C["show_cursor"])
                stream.write("\n")
                return _select_effort_menu(cfg.level, stream)

            if key in ("\r", "\n"):
                break
            if key in ("q", "Q", "\x03"):
                break
            if key in ("\x1b[D", "h", "a", "H", "A"):
                cfg.index = max(0, cfg.index - 1)
            elif key in ("\x1b[C", "l", "d", "L", "D"):
                cfg.index = min(n - 1, cfg.index + 1)
            elif key in ("\x1b[A", "k", "w", "K", "W"):
                cfg.index = min(n - 1, cfg.index + 1)
            elif key in ("\x1b[B", "j", "s", "J", "S"):
                cfg.index = max(0, cfg.index - 1)
            elif key.isdigit() and 1 <= int(key) <= n:
                cfg.index = int(key) - 1
            cfg.level = EFFORT_LEVELS[cfg.index][0]
            _draw()
    finally:
        stream.write(C["show_cursor"])
        stream.write("\n")
        stream.flush()

    return cfg


def effort_ramp_animation(
    target: str = "max",
    *,
    duration: float = 1.5,
    stream: TextIO | None = None,
) -> None:
    """Animate slider ramping up to *target* effort."""
    stream = resolve_stream(stream)
    names = [e[0] for e in EFFORT_LEVELS]
    target_idx = names.index(target) if target in names else len(names) - 1
    if not animations_enabled(stream):
        render_effort_slider(target_idx, label="Ramping", show_labels=False, stream=stream)
        return
    steps = max(target_idx * 6, 12)
    stream.write(C["hide_cursor"])
    stream.write("\n\n")
    stream.flush()
    try:
        for step in range(steps + 1):
            t = step / steps
            # ease-out so it feels smooth, not linear-steppy
            eased = 1 - (1 - t) ** 2
            idx = int(round(eased * target_idx))
            stream.write(C["cursor_up"] * 2)
            for _ in range(2):
                stream.write(C["clear_line"] + "\n")
            stream.write(C["cursor_up"] * 2)
            render_effort_slider(
                idx,
                label="Ramping",
                show_labels=False,
                stream=stream,
            )
            stream.flush()
            time.sleep(duration / steps)
        stream.write("\n")
    finally:
        stream.write(C["show_cursor"])
        stream.flush()
