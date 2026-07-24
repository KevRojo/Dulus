"""Visual effects — typewriter, glitch, wave, matrix rain, pulse."""
from __future__ import annotations

import random
import time
from typing import TextIO

from .ansi import (
    C,
    ORANGE,
    GOLD,
    AMBER,
    CYAN,
    PURPLE,
    GREEN,
    clr,
    animations_enabled,
    gradient_text,
    pad,
    resolve_stream,
    rgb,
    rgb_tuple,
)

GLITCH_CHARS = "░▒▓█▄▀■□▪▫"
MATRIX_CHARS = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ01ABCDEF"
WAVE_COLORS = [ORANGE, GOLD, AMBER, CYAN, PURPLE, GREEN]


def typewriter(
    text: str,
    *,
    delay: float = 0.03,
    color: str = "white",
    stream: TextIO | None = None,
) -> None:
    """Print *text* character-by-character."""
    stream = resolve_stream(stream)
    if not animations_enabled(stream):
        stream.write(clr(text, color) + "\n")
        stream.flush()
        return
    for ch in text:
        stream.write(clr(ch, color))
        stream.flush()
        time.sleep(delay)
    stream.write(C["reset"] + "\n")
    stream.flush()


def wave_text(text: str, frame: int = 0) -> str:
    """Brand-palette wave offset by *frame* (returns colored string)."""
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(ch)
            continue
        hue_shift = (i + frame) % len(WAVE_COLORS)
        out.append(rgb_tuple(WAVE_COLORS[hue_shift], ch))
    return "".join(out)


def animate_wave(
    text: str,
    *,
    frames: int = 20,
    interval: float = 0.08,
    stream: TextIO | None = None,
) -> None:
    """Animate a rainbow wave across *text*."""
    stream = resolve_stream(stream)
    if not animations_enabled(stream):
        stream.write(pad(gradient_text(text, ORANGE, CYAN)) + "\n")
        stream.flush()
        return
    stream.write(C["hide_cursor"])
    stream.flush()
    try:
        for f in range(frames):
            line = pad(wave_text(text, f))
            stream.write(f"\r{C['clear_line']}{line}")
            stream.flush()
            time.sleep(interval)
        final = pad(gradient_text(text, ORANGE, CYAN))
        stream.write(f"\r{C['clear_line']}{final}\n")
        stream.flush()
    finally:
        stream.write(C["show_cursor"])
        stream.flush()


def print_creator_signature(
    name: str = "kevrojo",
    *,
    animated: bool = True,
    stream: TextIO | None = None,
) -> None:
    """Render Dulus's creator signature beneath a banner.

    In a real terminal the brand colors travel across the name. Logs, tests,
    pipes and redirected output get the same signature as one clean line.
    """
    stream = resolve_stream(stream)
    signature = f"◆  {name}  ◆"
    if animated and animations_enabled(stream):
        animate_wave(signature, frames=10, interval=0.035, stream=stream)
        return
    stream.write(pad(gradient_text(signature, ORANGE, CYAN)) + "\n")
    stream.flush()


def glitch_text(text: str, *, intensity: float = 0.15) -> str:
    """Return *text* with random glitch characters injected."""
    intensity = max(0.0, min(1.0, intensity))
    out: list[str] = []
    for ch in text:
        if ch != " " and random.random() < intensity:
            out.append(clr(random.choice(GLITCH_CHARS), "cyan"))
        else:
            out.append(ch)
    return "".join(out)


def animate_glitch(
    text: str,
    *,
    frames: int = 12,
    interval: float = 0.07,
    stream: TextIO | None = None,
) -> None:
    """Animate a glitch settle on *text*."""
    stream = resolve_stream(stream)
    if not animations_enabled(stream):
        stream.write(pad(clr(text, "orange", "bold")) + "\n")
        stream.flush()
        return
    stream.write(C["hide_cursor"])
    stream.flush()
    try:
        for f in range(frames):
            intensity = 0.4 if f % 3 == 0 else 0.12
            line = pad(glitch_text(text, intensity=intensity))
            stream.write(f"\r{C['clear_line']}{line}")
            stream.flush()
            time.sleep(interval)
        stream.write(f"\r{C['clear_line']}{pad(clr(text, 'orange', 'bold'))}\n")
        stream.flush()
    finally:
        stream.write(C["show_cursor"])
        stream.flush()


def matrix_rain(
    *,
    cols: int = 40,
    rows: int = 12,
    duration: float = 3.0,
    interval: float = 0.1,
    stream: TextIO | None = None,
) -> None:
    """Matrix-style cascading rain for *duration* seconds."""
    stream = resolve_stream(stream)
    if not animations_enabled(stream):
        stream.write(pad(clr("Matrix rain · interactive terminal preview", "dim")) + "\n")
        stream.flush()
        return
    cols = max(cols, 4)
    rows = max(rows, 3)
    offsets = [random.randint(0, rows) for _ in range(cols)]
    end = time.time() + duration
    stream.write(C["hide_cursor"])
    stream.flush()
    try:
        while time.time() < end:
            grid: list[list[str]] = [[" " for _ in range(cols)] for _ in range(rows)]
            for c in range(cols):
                for r in range(rows):
                    if (r + offsets[c]) % 5 == 0:
                        ch = random.choice(MATRIX_CHARS)
                        bright = r < 2
                        grid[r][c] = (
                            rgb(120, 255, 120, ch) if bright else rgb(0, 180, 60, ch)
                        )
                offsets[c] = (offsets[c] + 1) % (rows * 2)
            for row in grid:
                stream.write(pad("".join(row)) + "\n")
            stream.write(C["cursor_up"] * rows)
            stream.flush()
            time.sleep(interval)
        # Clear the rain area
        for _ in range(rows):
            stream.write(C["clear_line"] + "\n")
        stream.write(C["cursor_up"] * rows)
        stream.flush()
    finally:
        stream.write(C["show_cursor"])
        stream.flush()


def pulse_line(
    text: str,
    *,
    frames: int = 16,
    interval: float = 0.1,
    stream: TextIO | None = None,
) -> None:
    """Pulse orange brightness on a single line of text."""
    stream = resolve_stream(stream)
    if not animations_enabled(stream):
        stream.write(pad(clr(text, "orange", "bold")) + "\n")
        stream.flush()
        return
    stream.write(C["hide_cursor"])
    stream.flush()
    try:
        for f in range(frames):
            brightness = int(135 + 120 * abs((f % 8) - 4) / 4)
            line = pad(rgb(255, brightness, 0, text))
            stream.write(f"\r{C['clear_line']}{line}")
            stream.flush()
            time.sleep(interval)
        stream.write(f"\r{C['clear_line']}{pad(clr(text, 'orange', 'bold'))}\n")
        stream.flush()
    finally:
        stream.write(C["show_cursor"])
        stream.flush()
