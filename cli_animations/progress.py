"""Progress bars — determinate, indeterminate, segmented, multi-step.

All bars share the same track language from ``ansi.render_track`` so the
kit feels like one system, not four random widgets.
"""
from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from typing import TextIO

from .ansi import (
    C,
    GLYPH,
    GOLD,
    GREEN,
    MUTED,
    ORANGE,
    RED,
    animations_enabled,
    clr,
    pad,
    render_track,
    rgb_tuple,
)

BAR_WIDTH = 28


def render_bar(
    fraction: float,
    *,
    width: int = BAR_WIDTH,
    label: str = "",
    show_pct: bool = True,
    style: str = "line",
) -> str:
    """Determinate progress bar (0.0–1.0).

    Default style is the connected line track:
        label  ━━━━━━━━━━╸─────────  42%
    """
    fraction = max(0.0, min(1.0, fraction))
    track = render_track(fraction, width=width, style=style, gradient=True)
    pct = f" {int(fraction * 100):3d}%" if show_pct else ""
    label_s = f"{clr(label, 'bold')}  " if label else ""
    return pad(f"{label_s}{track}{rgb_tuple(GOLD, pct) if pct else ''}")


def render_segmented(
    current: int,
    total: int,
    *,
    labels: list[str] | None = None,
) -> str:
    """Segmented steps with real spacing — no stuck-together mess.

        ● boot ── ● auth ── ◎ agent ── ○ tools ── ○ ready
    """
    total = max(total, 1)
    current = max(0, min(current, total - 1))
    parts: list[str] = []

    for i in range(total):
        if i < current:
            node = rgb_tuple(ORANGE, GLYPH["node_done"])
            name_color = ORANGE
        elif i == current:
            node = rgb_tuple(GOLD, GLYPH["node_active"])
            name_color = GOLD
        else:
            node = rgb_tuple(MUTED, GLYPH["node_pending"])
            name_color = MUTED

        if labels and i < len(labels):
            name = f" {rgb_tuple(name_color, labels[i])}"
        else:
            name = ""

        parts.append(f"{node}{name}")
        if i < total - 1:
            # connector: solid if the edge is already crossed, soft otherwise
            if i < current:
                parts.append(f" {rgb_tuple(ORANGE, GLYPH['link'])} ")
            else:
                parts.append(f" {rgb_tuple(MUTED, GLYPH['link'])} ")

    return pad("".join(parts))


def render_steps(steps: list[tuple[str, str]]) -> str:
    """Vertical step list with shared status glyphs.

    *steps*: ``[(name, status), ...]``
    status ∈ ``pending | active | done | error``
    """
    icons = {
        "pending": rgb_tuple(MUTED, GLYPH["node_pending"]),
        "active": rgb_tuple(GOLD, GLYPH["node_active"]),
        "done": rgb_tuple(GREEN, GLYPH["ok"]),
        "error": rgb_tuple(RED, GLYPH["fail"]),
    }
    lines: list[str] = []
    n = len(steps)
    for i, (name, status) in enumerate(steps):
        icon = icons.get(status, icons["pending"])
        if status == "active":
            text = clr(name, "bold", "white")
        elif status == "pending":
            text = rgb_tuple(MUTED, name)
        elif status == "error":
            text = rgb_tuple(RED, name)
        else:
            text = clr(name, "white")

        # subtle tree spine so the list feels connected
        if n == 1:
            prefix = ""
        elif i == n - 1:
            prefix = f"{rgb_tuple(MUTED, GLYPH['tree_end'])} "
        else:
            prefix = f"{rgb_tuple(MUTED, GLYPH['tree_mid'])} "

        lines.append(pad(f"{prefix}{icon}  {text}"))
    return "\n".join(lines)


@contextmanager
def progress_bar(
    total: int,
    *,
    label: str = "Progress",
    width: int = BAR_WIDTH,
    style: str = "line",
    stream: TextIO | None = None,
):
    """Context manager yielding ``(update, set_progress)`` callables."""
    stream = stream or sys.stdout
    state = {"current": 0}
    total = max(total, 1)

    def _draw(message: str = "") -> None:
        frac = state["current"] / total
        msg = f"  {clr(message, 'dim')}" if message else ""
        line = render_bar(frac, width=width, label=label, style=style) + msg
        stream.write(f"\r{C['clear_line']}{line}")
        stream.flush()

    def update(n: int = 1, message: str = "") -> None:
        state["current"] = min(state["current"] + n, total)
        _draw(message)

    def set_progress(current: int, message: str = "") -> None:
        state["current"] = min(max(current, 0), total)
        _draw(message)

    if not animations_enabled(stream):
        def _quiet_update(n: int = 1, message: str = "") -> None:
            state["current"] = min(state["current"] + n, total)

        def _quiet_set(current: int, message: str = "") -> None:
            state["current"] = min(max(current, 0), total)

        try:
            yield _quiet_update, _quiet_set
        finally:
            stream.write(render_bar(1.0, width=width, label=label, style=style) + "\n")
            stream.flush()
        return

    stream.write(C["hide_cursor"])
    stream.flush()
    _draw()
    try:
        yield update, set_progress
    finally:
        set_progress(total)
        stream.write("\n")
        stream.write(C["show_cursor"])
        stream.flush()


@contextmanager
def indeterminate_bar(
    label: str = "Loading",
    *,
    width: int = BAR_WIDTH,
    interval: float = 0.05,
    stream: TextIO | None = None,
):
    """Indeterminate shimmer bar — a glowing window slides along the track."""
    stream = stream or sys.stdout
    if not animations_enabled(stream):
        stream.write(pad(clr(f"{label}…", "dim")) + "\n")
        stream.flush()
        yield
        return
    stop = threading.Event()

    def _run() -> None:
        pos = 0
        window = max(5, width // 5)
        direction = 1
        while not stop.is_set():
            # bounce
            if pos + window >= width:
                direction = -1
            elif pos <= 0:
                direction = 1
            # build a soft gradient window on a muted track
            cells: list[str] = []
            for i in range(width):
                if pos <= i < pos + window:
                    local = (i - pos) / max(window - 1, 1)
                    # bright in the middle of the window
                    peak = 1.0 - abs(local - 0.5) * 2
                    from .ansi import gradient_stops, lerp_color, BAR_GRADIENT
                    base = gradient_stops(i / max(width - 1, 1), BAR_GRADIENT)
                    # mix toward white for the tip
                    color = lerp_color(base, (255, 230, 160), peak * 0.55)
                    cells.append(rgb_tuple(color, GLYPH["bar_full"]))
                else:
                    cells.append(rgb_tuple(MUTED, GLYPH["bar_empty"]))
            line = pad(f"{clr(label, 'bold')}  {''.join(cells)}")
            stream.write(f"\r{C['clear_line']}{line}")
            stream.flush()
            pos += direction
            stop.wait(interval)

    thread = threading.Thread(target=_run, daemon=True)
    stream.write(C["hide_cursor"])
    stream.flush()
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=2.0)
        stream.write(f"\r{C['clear_line']}")
        stream.flush()
        stream.write(C["show_cursor"])
        stream.flush()


def animate_progress_demo(
    duration: float = 2.0,
    stream: TextIO | None = None,
) -> None:
    """Animate a determinate bar from 0→100% (for demos)."""
    stream = stream or sys.stdout
    if not animations_enabled(stream):
        stream.write(render_bar(1.0, label="Downloading") + "\n")
        stream.flush()
        return
    steps = 48
    stream.write(C["hide_cursor"])
    stream.flush()
    try:
        for i in range(steps + 1):
            line = render_bar(i / steps, label="Downloading")
            stream.write(f"\r{C['clear_line']}{line}")
            stream.flush()
            time.sleep(duration / steps)
        stream.write("\n")
    finally:
        stream.write(C["show_cursor"])
        stream.flush()
