#!/usr/bin/env python3
"""Showcase all CLI animations — package entrypoint.

Sections: all | banners | effort | spinners | progress | effects | status
"""
from __future__ import annotations

import sys
import time

from .ansi import (
    ORANGE,
    CYAN,
    MUTED,
    animations_enabled,
    clr,
    gradient_text,
    pad,
    rgb_tuple,
)
from .banners import load_ascii_asset, print_banner, print_box
from .effects import (
    animate_glitch,
    animate_wave,
    matrix_rain,
    print_creator_signature,
    pulse_line,
    typewriter,
)
from .effort_slider import (
    EFFORT_LEVELS,
    effort_ramp_animation,
    render_effort_bar,
    render_effort_slider,
)
from .progress import (
    animate_progress_demo,
    indeterminate_bar,
    render_bar,
    render_segmented,
    render_steps,
)
from .spinners import animate_spinner, spinner
from .status import (
    animate_thinking,
    pipeline_status,
    status_bar,
    toast,
    tool_status,
)


def _ensure_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def header(title: str) -> None:
    print()
    print(pad(rgb_tuple(MUTED, "─" * 52)))
    print(pad(gradient_text(title, ORANGE, CYAN)))
    print(pad(rgb_tuple(MUTED, "─" * 52)))


def _pause(seconds: float) -> None:
    if animations_enabled(sys.stdout):
        time.sleep(seconds)


def demo_banners() -> None:
    header("BANNERS & ASCII ART")
    for name in ("dulus", "god_mode", "cigua"):
        print_banner(name)
        if name == "dulus":
            print_creator_signature("kevrojo")
        print()
    print_box(
        "Agent ready.\nProvider: Kimi\nModel: kimi-k2",
        title="Session",
        color="cyan",
    )
    print()
    for asset in ("dulus_logo", "eagle", "terminal_art"):
        art = load_ascii_asset(asset)
        if art:
            print(pad(clr(f"── assets/{asset}.txt ──", "dim")))
            for line in art.splitlines():
                print(pad(gradient_text(line, ORANGE, (255, 200, 50))))
            print()


def demo_effort() -> None:
    header("EFFORT SLIDER")
    for i in range(len(EFFORT_LEVELS)):
        render_effort_slider(i)
        print()
    print(render_effort_bar(0.72))
    print()
    print(pad(clr("Ramping to max…", "dim")))
    effort_ramp_animation("max", duration=1.2)


def demo_spinners() -> None:
    header("SPINNERS")
    for style in ("claude", "braille", "bird", "block", "orbit", "pulse"):
        print(pad(clr(f"style · {style}", "dim")))
        animate_spinner(0.9, style=style)
    print(pad(clr("context manager", "dim")))
    with spinner("Indexing codebase", style="claude"):
        _pause(1.1)
    print(pad(clr("✓  Done", "green")))


def demo_progress() -> None:
    header("PROGRESS BARS")
    # static samples at different fills so the connection is obvious
    for frac in (0.0, 0.18, 0.42, 0.67, 0.91, 1.0):
        print(render_bar(frac, label="Sync"))
    print()
    animate_progress_demo(1.4)
    print()
    print(render_segmented(2, 5, labels=["boot", "auth", "agent", "tools", "ready"]))
    print()
    print(
        render_steps(
            [
                ("Parse request", "done"),
                ("Run tools", "done"),
                ("Synthesize response", "active"),
                ("Validate output", "pending"),
            ]
        )
    )
    print()
    print(pad(clr("indeterminate", "dim")))
    with indeterminate_bar("Compiling", interval=0.04):
        _pause(1.4)
    print(pad(clr("✓  Complete", "green")))


def demo_effects() -> None:
    header("EFFECTS")
    print(pad(clr("typewriter", "dim")))
    typewriter("  🦅 Dulus is thinking…", delay=0.035, color="orange")
    print()
    animate_wave("DULUS · AGENT RUNTIME", frames=16)
    print()
    animate_glitch("GOD MODE ENGAGED", frames=10)
    print()
    pulse_line("⚡ MAX VELOCITY ⚡", frames=12)
    print()
    print(pad(clr("matrix rain · 2s", "dim")))
    matrix_rain(cols=48, rows=8, duration=2.0)


def demo_status() -> None:
    header("STATUS INDICATORS")
    animate_thinking(1.3)
    print()
    for state in ("running", "done", "error", "pending"):
        print(tool_status("read_file", state, "/src/agent.py"))
    print()
    pipeline_status(
        [
            {"name": "Ingest context", "status": "done"},
            {"name": "Plan tools", "status": "done"},
            {"name": "Execute shell", "status": "running", "detail": "npm test"},
            {"name": "Write response", "status": "pending"},
        ]
    )
    print()
    toast("Provider connected", kind="ok")
    toast("Cache hit 98.8%", kind="info")
    toast("High latency", kind="warn")
    print()
    print(status_bar([("model", "kimi-k2"), ("effort", "high"), ("tokens", "2.25B")]))


SECTIONS = {
    "banners": demo_banners,
    "effort": demo_effort,
    "spinners": demo_spinners,
    "progress": demo_progress,
    "effects": demo_effects,
    "status": demo_status,
}


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    section = (argv[0] if argv else "all").lower()

    print()
    print(pad(gradient_text("CLI ANIMATIONS — Dulus", ORANGE, CYAN)))
    print(pad(clr("v1.2.1 · one visual system · macOS / Linux / Windows", "dim")))
    print(pad(clr(f"platform · {sys.platform} · py {sys.version.split()[0]}", "dim")))

    if section == "all":
        for fn in SECTIONS.values():
            fn()
    elif section in SECTIONS:
        SECTIONS[section]()
    else:
        print(pad(clr(f"Unknown section: {section}", "red")))
        print(pad(clr(f"Available: all, {', '.join(SECTIONS)}", "dim")))
        return 1

    print()
    print(pad(clr("✓  Demo complete", "green")))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
