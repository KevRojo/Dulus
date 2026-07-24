"""Terminal spinners — Claude-style, Braille, Dulus-themed.

Shares padding + color language with the rest of the kit.
"""
from __future__ import annotations

import itertools
import random
import threading
import time
from contextlib import contextmanager
from typing import Iterator, TextIO

from .ansi import (
    C,
    ORANGE,
    MUTED,
    animations_enabled,
    clr,
    pad,
    resolve_stream,
    rgb_tuple,
)

# Claude Code spinner frames
CLAUDE_FRAMES = ["·", "✢", "✳", "✶", "✻", "✽"]

BRAILLE_DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
LINE_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴"]  # keep braille family by default
ARROW_SPINNER = ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"]
BLOCK_SPINNER = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"]
BIRD_SPINNER = ["·", "✦", "✧", "✦"]  # no emoji flicker — cleaner
PULSE_SPINNER = ["○", "◔", "◑", "◕", "●", "◕", "◑", "◔"]
ORBIT_SPINNER = ["◜", "◠", "◝", "◞", "◡", "◟"]

DULUS_PHRASES = [
    "Rewriting light speed",
    "Sharpening talons on the AST",
    "Orbiting the codebase",
    "Hunting for memory leaks",
    "Bending spacetime",
    "Terminal velocity reached",
    "Preying on bugs from above",
    "Hatching a master plan",
]

CLAUDE_PHRASES = [
    "Accomplishing", "Architecting", "Befuddling", "Blooping", "Brewing",
    "Cerebrating", "Combobulating", "Discombobulating", "Elucidating",
    "Flibbertigibbeting", "Hullaballooing", "Nebulizing", "Percolating",
    "Prestidigitating", "Razzmatazzing", "Shenaniganing", "Symbioting",
    "Whatchamacalliting", "Zigzagging",
]

SPINNERS: dict[str, list[str]] = {
    "claude": CLAUDE_FRAMES,
    "braille": BRAILLE_DOTS,
    "line": LINE_SPINNER,
    "arrow": ARROW_SPINNER,
    "block": BLOCK_SPINNER,
    "bird": BIRD_SPINNER,
    "pulse": PULSE_SPINNER,
    "orbit": ORBIT_SPINNER,
}


def _cycle(frames: list[str]) -> Iterator[str]:
    return itertools.cycle(frames)


def _spin_line(frame: str, phrase: str, color: str = "orange") -> str:
    # double-space after glyph → breathes, matches status/progress padding
    return pad(f"{clr(frame, color, 'bold')}  {rgb_tuple(MUTED, phrase)}")


@contextmanager
def spinner(
    message: str = "",
    *,
    style: str = "claude",
    phrases: list[str] | None = None,
    interval: float = 0.08,
    color: str = "orange",
    stream: TextIO | None = None,
):
    """Context manager: animated spinner on one line until the block exits."""
    stream = resolve_stream(stream)
    frames = SPINNERS.get(style, CLAUDE_FRAMES)
    phrase_pool = phrases or []
    if not animations_enabled(stream):
        phrase = message or (random.choice(phrase_pool) if phrase_pool else "Working")
        stream.write(_spin_line(frames[0], phrase, color) + "\n")
        stream.flush()
        yield
        return
    stop = threading.Event()
    frame_iter = _cycle(frames)

    def _run() -> None:
        phrase = message or (random.choice(phrase_pool) if phrase_pool else "Working")
        while not stop.is_set():
            frame = next(frame_iter)
            stream.write(f"\r{C['clear_line']}{_spin_line(frame, phrase, color)}")
            stream.flush()
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


def spin_once(style: str = "claude", frame: int = 0) -> str:
    """Return a single spinner glyph for manual frame control."""
    frames = SPINNERS.get(style, CLAUDE_FRAMES)
    return frames[frame % len(frames)]


def animate_spinner(
    duration: float = 3.0,
    style: str = "claude",
    message: str = "",
    phrases: list[str] | None = None,
    interval: float = 0.08,
    stream: TextIO | None = None,
) -> None:
    """Run a spinner for *duration* seconds (blocking)."""
    stream = resolve_stream(stream)
    if not animations_enabled(stream):
        phrase_pool = phrases or DULUS_PHRASES
        phrase = message or random.choice(phrase_pool)
        stream.write(_spin_line(SPINNERS.get(style, CLAUDE_FRAMES)[0], phrase, "orange") + "\n")
        stream.flush()
        return
    end = time.time() + duration
    frames = _cycle(SPINNERS.get(style, CLAUDE_FRAMES))
    phrase_pool = phrases or DULUS_PHRASES
    stream.write(C["hide_cursor"])
    stream.flush()
    try:
        while time.time() < end:
            phrase = message or random.choice(phrase_pool)
            frame = next(frames)
            stream.write(
                f"\r{C['clear_line']}{_spin_line(frame, phrase + '…')}"
            )
            stream.flush()
            time.sleep(interval)
        stream.write(f"\r{C['clear_line']}")
        stream.flush()
    finally:
        stream.write(C["show_cursor"])
        stream.flush()
