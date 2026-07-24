"""Status indicators — thinking, tools, pipelines, toasts.

Shares glyphs / colors / padding with the rest of the kit.
"""
from __future__ import annotations

import random
import sys
import time
from typing import TextIO

from .ansi import (
    C,
    GLYPH,
    CYAN,
    GOLD,
    GREEN,
    MUTED,
    ORANGE,
    RED,
    animations_enabled,
    clr,
    pad,
    rgb_tuple,
)
from .spinners import CLAUDE_FRAMES, DULUS_PHRASES

THINKING_DOTS = ["   ", ".  ", ".. ", "..."]


def thinking_line(frame: int = 0, phrase: str = "Thinking") -> str:
    """Single-frame thinking indicator (for manual redraw loops)."""
    dots = THINKING_DOTS[frame % len(THINKING_DOTS)]
    icon = CLAUDE_FRAMES[frame % len(CLAUDE_FRAMES)]
    return pad(
        f"{rgb_tuple(ORANGE, icon)}  {clr(phrase, 'white')}{rgb_tuple(MUTED, dots)}"
    )


def tool_status(name: str, state: str = "running", detail: str = "") -> str:
    """One-line tool status chip — same node glyphs as steps/pipeline."""
    states = {
        "running": (rgb_tuple(GOLD, GLYPH["node_active"]), rgb_tuple(GOLD, "running")),
        "done": (rgb_tuple(GREEN, GLYPH["ok"]), rgb_tuple(GREEN, "done")),
        "error": (rgb_tuple(RED, GLYPH["fail"]), rgb_tuple(RED, "failed")),
        "pending": (rgb_tuple(MUTED, GLYPH["node_pending"]), rgb_tuple(MUTED, "pending")),
    }
    icon, label = states.get(state, states["pending"])
    extra = f"  {clr(detail, 'dim')}" if detail else ""
    return pad(f"{icon}  {clr(name, 'bold')}{extra}  {label}")


def pipeline_status(stages: list[dict], *, stream: TextIO | None = None) -> None:
    """Vertical pipeline with a continuous tree spine.

    Each stage: ``{"name": str, "status": str, "detail": str?}``.
    """
    stream = stream or sys.stdout
    n = len(stages)
    for i, stage in enumerate(stages):
        is_last = i == n - 1
        branch = GLYPH["tree_end"] if is_last else GLYPH["tree_mid"]
        # build status without the default pad, then compose with tree
        name = stage.get("name", "step")
        state = stage.get("status", "pending")
        detail = stage.get("detail", "")

        states = {
            "running": (rgb_tuple(GOLD, GLYPH["node_active"]), rgb_tuple(GOLD, "running")),
            "done": (rgb_tuple(GREEN, GLYPH["ok"]), rgb_tuple(GREEN, "done")),
            "error": (rgb_tuple(RED, GLYPH["fail"]), rgb_tuple(RED, "failed")),
            "pending": (rgb_tuple(MUTED, GLYPH["node_pending"]), rgb_tuple(MUTED, "pending")),
        }
        icon, label = states.get(state, states["pending"])
        extra = f"  {clr(detail, 'dim')}" if detail else ""
        line = (
            f"{rgb_tuple(MUTED, branch)} {icon}  "
            f"{clr(name, 'bold')}{extra}  {label}"
        )
        stream.write(pad(line) + "\n")
    stream.flush()


def toast(message: str, *, kind: str = "info", stream: TextIO | None = None) -> None:
    """Print a one-shot toast notification."""
    styles = {
        "info": (GLYPH["info"], CYAN),
        "ok": (GLYPH["ok"], GREEN),
        "warn": (GLYPH["warn"], GOLD),
        "error": (GLYPH["fail"], RED),
    }
    icon, color = styles.get(kind, styles["info"])
    stream = stream or sys.stdout
    stream.write(pad(f"{rgb_tuple(color, icon)}  {clr(message, 'white')}") + "\n")
    stream.flush()


def animate_thinking(
    duration: float = 2.0,
    phrase: str = "",
    stream: TextIO | None = None,
) -> None:
    """Animate a thinking indicator for *duration* seconds."""
    stream = stream or sys.stdout
    if not animations_enabled(stream):
        stream.write(thinking_line(0, phrase or DULUS_PHRASES[0]) + "\n")
        stream.flush()
        return
    end = time.time() + duration
    frame = 0
    stream.write(C["hide_cursor"])
    stream.flush()
    try:
        while time.time() < end:
            p = phrase or random.choice(DULUS_PHRASES)
            stream.write(f"\r{C['clear_line']}{thinking_line(frame, p)}")
            stream.flush()
            frame += 1
            time.sleep(0.12)
        stream.write(f"\r{C['clear_line']}")
        stream.flush()
    finally:
        stream.write(C["show_cursor"])
        stream.flush()


def status_bar(items: list[tuple[str, str]]) -> str:
    """Horizontal status chips with consistent separators.

        model kimi-k2 │ effort high │ tokens 2.25B
    """
    chips: list[str] = []
    for label, value in items:
        chips.append(
            f"{rgb_tuple(MUTED, label)} {rgb_tuple(ORANGE, value)}"
        )
    sep = f" {rgb_tuple(MUTED, GLYPH['sep'])} "
    return pad(sep.join(chips))
