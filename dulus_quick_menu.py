"""Dulus Quick Menu — popup triggered by double-tap ← in the REPL.

Optional, hot-pluggable module.  If this file is missing, Dulus keeps running
exactly as before because `input.py` imports it inside a bare `try/except`.

Requirements (optional):
    pip install rich prompt_toolkit

What it does:
    • Registers a prompt_toolkit key binding on "left".
    • If the user presses the Left Arrow twice within ~0.28 s, a full-screen
      rich menu pops up.
    • Navigate with ↑/↓, pick with Enter, cancel with Esc or Q.
    • The selected slash command is inserted into the current input buffer.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Optional, Tuple

# Make sure we can print emoji / box-drawing even on legacy Windows consoles.
try:
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── prompt_toolkit availability ──────────────────────────────────────────────
try:
    from prompt_toolkit.key_binding import KeyBindings
    HAS_PROMPT_TOOLKIT = True
except Exception:  # pragma: no cover
    HAS_PROMPT_TOOLKIT = False

# ── Menu data ────────────────────────────────────────────────────────────────
_OPTION = Tuple[str, Optional[str]]
_OPTIONS: list[_OPTION] = [
    # ── Kimi / reasoning cluster (top — the fast path this menu is for) ──
    ("⚡  Effort → high", "/effort high"),
    ("🦅  Effort → max", "/effort max"),
    ("·   Effort → low", "/effort low"),
    ("💭  Thinking (on/off)", "/thinking"),
    ("🌙  Kimi K3  (oauth, 1M)", "/model kimi-oauth/k3"),
    ("🌙  Kimi K3-256k (oauth)", "/model kimi-oauth/k3-256k"),
    # ── general ──
    ("🤖  /model", "/model"),
    ("🔥  /help", "/help"),
    ("🧹  /clear", "/clear"),
    ("🧠  /skills", "/skills"),
    ("🔌  /plugin", "/plugin"),
    ("🎙  /voice", "/voice"),
    ("💾  /memory", "/memory"),
    ("📋  /tasks", "/tasks"),
    ("⚡  /roundtable", "/roundtable"),
    ("🚪  Exit menu", None),
]

_DOUBLE_TAP_WINDOW = 1.0  # seconds between two ← to count as a double-tap
_LEFT_TIMES: list[float] = []


# ── Low-level key reader (cross-platform) ────────────────────────────────────
def _read_raw_key() -> str:
    """Read one logical key press. Returns: up, down, left, right, enter, esc, q, unknown."""
    if sys.platform == "win32":
        import msvcrt

        ch = msvcrt.getch()
        # Arrow keys arrive as a two-byte sequence on Windows.
        if ch in (b"\x00", b"\xe0"):
            code = msvcrt.getch()
            return {
                b"H": "up",
                b"P": "down",
                b"M": "right",
                b"K": "left",
                b"\r": "enter",
            }.get(code, "unknown")
        if ch == b"\r":
            return "enter"
        if ch == b"\x1b":
            return "esc"
        if ch.lower() == b"q":
            return "q"
        return "unknown"

    # Unix / macOS
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            return {
                "[A": "up",
                "[B": "down",
                "[C": "right",
                "[D": "left",
            }.get(seq, "esc")
        if ch in ("\r", "\n"):
            return "enter"
        if ch.lower() == "q":
            return "q"
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x04":
            return "esc"
        return "unknown"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Double-tap detector ──────────────────────────────────────────────────────
def _is_double_tap() -> bool:
    now = time.monotonic()
    _LEFT_TIMES.append(now)
    while len(_LEFT_TIMES) > 2:
        _LEFT_TIMES.pop(0)
    if len(_LEFT_TIMES) != 2:
        return False
    return (_LEFT_TIMES[1] - _LEFT_TIMES[0]) <= _DOUBLE_TAP_WINDOW


# ── Menu rendering ───────────────────────────────────────────────────────────
def _render_menu_rich(options: list[_OPTION], selected: int, console: Any) -> Any:
    """Build a rich Panel for the live menu."""
    from rich.align import Align
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    table = Table(show_header=False, box=None, padding=(0, 2))
    for i, (label, _value) in enumerate(options):
        if i == selected:
            table.add_row(Text(f"▶  {label}", style="bold cyan on grey19"))
        else:
            table.add_row(Text(f"   {label}", style="white"))

    return Panel(
        Align.center(table, vertical="middle"),
        title="[bold magenta]⚡  DULUS QUICK MENU  ⚡[/]",
        subtitle="[dim]↑↓ move  ·  Enter pick  ·  Esc / Q cancel  ·  ←← summoned me[/dim]",
        border_style="cyan",
        padding=(1, 3),
    )


def _show_with_rich() -> Optional[str]:
    from rich.console import Console
    from rich.live import Live

    console = Console()
    selected = 0

    try:
        with Live(
            _render_menu_rich(_OPTIONS, selected, console),
            screen=True,
            refresh_per_second=12,
            console=console,
        ) as live:
            while True:
                key = _read_raw_key()
                if key == "up":
                    selected = (selected - 1) % len(_OPTIONS)
                elif key == "down":
                    selected = (selected + 1) % len(_OPTIONS)
                elif key == "enter":
                    return _OPTIONS[selected][1]
                elif key in ("esc", "q"):
                    return None
                live.update(_render_menu_rich(_OPTIONS, selected, console))
    except Exception:
        # If rich Live fails (e.g. weird terminal), fall back to plain text.
        return _show_fallback()


def _show_fallback() -> Optional[str]:
    """Plain ANSI-free fallback; works even without rich."""
    print("\n--- DULUS QUICK MENU ---")
    for i, (label, _value) in enumerate(_OPTIONS):
        print(f"  {i + 1}. {label}")
    try:
        choice = input(f"Pick [1-{len(_OPTIONS)}] (Enter = cancel): ").strip()
        if not choice:
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(_OPTIONS):
            return _OPTIONS[idx][1]
    except Exception:
        pass
    return None


def show_quick_menu() -> Optional[str]:
    """Display the popup and return the selected command (or None)."""
    try:
        return _show_with_rich()
    except Exception:
        return _show_fallback()


# ── prompt_toolkit integration ───────────────────────────────────────────────
def _open_menu(event: Any) -> None:
    """Run the menu inside prompt_toolkit's run_in_terminal sandbox."""
    buf = event.app.current_buffer

    def _run() -> None:
        choice = show_quick_menu()
        if choice is not None:
            try:
                buf.insert_text(choice)
            except Exception:
                pass

    try:
        event.app.run_in_terminal(_run)
    except Exception:
        pass


def register_key_bindings(kb: Any) -> None:
    """Hook double-tap Left Arrow into the prompt_toolkit session."""
    if not HAS_PROMPT_TOOLKIT:
        return

    @kb.add("left", eager=True)
    def _left_double_tap(event: Any) -> None:
        if _is_double_tap():
            _open_menu(event)
        else:
            # Default cursor-left behavior since we claimed the binding eagerly.
            buf = event.app.current_buffer
            if buf.cursor_position > 0:
                buf.cursor_position -= 1


# Smoke test when run directly.
if __name__ == "__main__":
    print("Selected:", show_quick_menu())
