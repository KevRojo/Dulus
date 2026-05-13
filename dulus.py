#!/usr/bin/env python3
"""
Dulus — Next-gen Python Autonomous Agent.

Usage:
  python dulus.py [options] [prompt]
  dulus [options] [prompt]           (if dulus.bat is in PATH)

Options:
  -p, --print          Non-interactive: run prompt and exit (also --print-output)
  -m, --model MODEL    Override model (e.g., -m kimi/kimi-k2.5, -m gpt-4o)
  --accept-all         Never ask permission (dangerous)
  --verbose            Show thinking + token counts
  --version            Print version and exit
  -h, --help           Show this help message
  
  -c, --cmd COMMAND    Execute a Dulus slash command and exit (no REPL)
                       Useful for scripting and automation.
                       Examples:
                         dulus --cmd "plugin reload"
                         dulus --cmd "status"
                         dulus --cmd "kill_tmux"
                         dulus --cmd "checkpoint clear"
                         dulus -c "skills"
                       Note: Some commands require an active session.

Non-interactive Examples:
  dulus "explain this code"                    # Quick question and exit
  dulus -p "refactor this function"            # Same, explicit flag
  dulus --cmd "plugin install art@gh"          # Install plugin from CLI
  dulus --cmd "checkpoint"                     # List checkpoints

Slash commands in REPL:
  /help       Show this help
  /clear      Clear conversation
  /model [m]  Show or set model
  /config     Show config / set key=value
  /save [f]   Save session to file
  /load [f]   Load session from file
  /history    Print conversation history
  /context    Show context window usage
  /cost       Show API cost this session
  /verbose    Toggle verbose mode
  /thinking [off|min|med|max|raw|0-4]  Set extended-thinking level (raw = API default, no nudges; no arg = toggle)
  /soul [name]  List souls / switch active soul (e.g. /soul chill, /soul forensic)
  /schema [tool]  Inspect tool input schema (human-facing; model does not see this)
                  /schema              -> list all tools grouped
                  /schema <tool>       -> pretty-print inputs + description
                  /schema --json <t>   -> raw JSON dump
  /deep_override Toggle DeepSeek simplified prompt (requires restart)
  /deep_tools Toggle DeepSeek auto tool-wrap for JSON calls
  /autojob    Toggle auto-job printer (auto-print job results)
  /auto_show  Toggle auto-show for visual tools (ASCII art, etc.)
  /ultra_search Toggle ULTRA_SEARCH mode
  /permissions [mode]  Set permission mode
  /afk       Toggle AFK mode (auto-dismiss questions, auto-approve tools)
  /yolo      Toggle YOLO mode (auto-approve ALL actions without prompts)
  /cwd [path] Show or change working directory
  /memory [query]         Search persistent memories
  /memory list            List all stored memories formatted
  /memory load [n|name]   Inject numbered memory (or multiple: 1,2,3) into context
  /memory delete <name>   Delete a specific memory by name
  /memory purge           Total wipe of memories EXCEPT the 'Soul'
  /memory purge-soul      Total wipe of EVERYTHING (Danger)
  /memory consolidate     Extract long-term insights from session via AI
  /skills           List active Dulus skills (loaded each turn)
  /skill            Browse + manage Anthropic/ClawHub skills
  /skill list       Show installed + all available Anthropic skills
  /skill get <plugin/skill>  Install a skill (e.g. /skill get frontend-design/frontend-design)
  /skill use <name> Inject skill into next message  /skill remove <name>  Uninstall
  /agents           Show sub-agent tasks
  /mcp              List MCP servers and their tools
  /mcp reload       Reconnect all MCP servers
  /mcp add <n> <cmd> [args]  Add a stdio MCP server
  /mcp remove <n>   Remove an MCP server from config
  /plugin           List installed plugins
  /plugin install name@url [--project] [--main-agent]
                             Install a plugin. --main-agent hands off to the
                             main agent post-install to review/adapt the plugin
  /plugin uninstall name     Uninstall a plugin
  /plugin enable/disable name  Toggle plugin
  /plugin update name        Update a plugin
  /plugin recommend [ctx]    Recommend plugins for context
  /tasks            List all tasks
  /tasks create <subject>    Quick-create a task
  /tasks start/done/cancel <id>  Update task status
  /tasks delete <id>         Delete a task
  /tasks get <id>            Show full task details
  /tasks clear               Delete all tasks
  /voice            Record voice input, transcribe, and submit
  /voice status     Show available recording and STT backends
  /voice lang <code>  Set STT language (e.g. zh, en, ja — default: auto)
  /wake on|off      Toggle wake-word (hotword) detection — say "Hey Dulus"
  /wake status      Show wake-word listener state
  /wake phrases     List recognised wake phrases
  /wake calibrate   Measure your mic levels for 5s and suggest a threshold
  /wake test        Debug mode — shows RMS + STT output for 10 seconds
  /wake threshold <n>  Tune mic sensitivity (0.001-1.0, default 0.020)
  /proactive [dur]  Background sentinel polling (e.g. /proactive 5m)
  /proactive off    Disable proactive polling
  /cloudsave setup <token>   Configure GitHub token for cloud sync
  /cloudsave        Upload current session to GitHub Gist
  /cloudsave push [desc]     Upload with optional description
  /cloudsave auto on|off     Toggle auto-upload on exit
  /cloudsave list   List your dulus Gists
  /cloudsave load <gist_id>  Download and load a session from Gist
  /kill_tmux        Kill all stuck tmux/psmux sessions (cleanup)
  /shell [cmd|on|off] Toggle shell mode or execute shell command
  /copy [file]      Copy last response or file content to clipboard
  /batch            Manage Kimi Batch tasks (list, status, fetch)
  /roundtable       Start a multi-model roundtable discussion
  /fork             Fork session at a given turn
  /undo             Undo last turn
  /add-dir [path]   Manage additional workspace directories
  /import <file>    Import conversation from file or session
  /harvest          Harvest Claude.ai cookies (alias: /harvest-claude)
  /harvest-claude   Harvest Claude.ai cookies
  /harvest-kimi     Harvest Kimi.com (Consumer) session/gRPC tokens
  /harvest-gemini   Harvest Gemini (Consumer) session tokens
  /harvest-qwen     Harvest Qwen (chat.qwen.ai) session tokens
  /kimi_chats       List recent Kimi conversations
  /webchat [port]   Spawn web chat UI (background Flask server)
  /webchat stop     Kill the webchat server
  /sandbox          Open Dulus Sandbox OS in browser (starts webchat if needed)
  /sandbox stop     Stop the webchat server
  /rtk [on|off]     Toggle RTK token-optimized shell command rewriting
  /exit /quit Exit
"""
from __future__ import annotations

import sys
# ── Windows UTF-8 stdout fix ─────────────────────────────────────────────
# Prevents cp1252 crashes on emoji / international characters.
# Uses reconfigure() so the underlying file descriptor stays intact
# (argparse and other libs need a working fileno()/isatty()).
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Suppress noisy third-party startup warnings ──────────────────────────
# These don't affect functionality but pollute every Dulus boot (REPL,
# daemon, --print, every shell call). Filtered globally so logs stay clean.
import warnings as _warnings
# requests >= 2.32 nags about urllib3/chardet version pins on Python 3.13+.
_warnings.filterwarnings("ignore", message=r".*urllib3.*")
_warnings.filterwarnings("ignore", message=r".*chardet.*charset_normalizer.*")
_warnings.filterwarnings("ignore", message=r".*RequestsDependencyWarning.*")
# Dulus's own dev-license warning — only relevant if you're building
# license keys for production, not noise we want on every boot.
_warnings.filterwarnings("ignore", message=r".*DULUS_LICENSE_SECRET.*")
# Catch-all: any RequestsDependencyWarning by category, regardless of msg.
try:
    from requests.exceptions import RequestsDependencyWarning as _RDW  # type: ignore
    _warnings.filterwarnings("ignore", category=_RDW)
except Exception:
    pass
# pkg_resources / setuptools-based deprecations from optional plugins.
_warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"pkg_resources.*")
from pathlib import Path

# ── Global Import Hook ───────────────────────────────────────────────────────
# This allows running dulus.py from any directory while keeping its modules.
# We find the directory where dulus.py actually lives.
DULUS_CODE_ROOT = Path(__file__).resolve().parent
if str(DULUS_CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(DULUS_CODE_ROOT))

from tools import ask_input_interactive, _tg_thread_local, _is_in_tg_turn
import input as dulus_input
try:
    import paste_placeholders as _paste_ph  # type: ignore
except ImportError:
    _paste_ph = None  # type: ignore[assignment]
try:
    import git_prompt as _git_prompt  # type: ignore
except ImportError:
    _git_prompt = None  # type: ignore[assignment]
try:
    from common import C
except ImportError:
    # Fallback uses Dulus orange (default theme accent) instead of generic cyan
    _DULUS_ORANGE = "\033[38;2;255;135;0m"
    C = {"cyan": _DULUS_ORANGE, "green": _DULUS_ORANGE, "blue": _DULUS_ORANGE,
         "bold": "\033[1m", "reset": "\033[0m", "gray": "\033[90m", "dim": "\033[2m"}

# ── License gate (KevRojo — tu esfuerzo, tu leche) ──────────────────────────
from license_manager import LicenseManager, LicenseTier

import argparse
import atexit
import json
import os
import re
import textwrap
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Any, Callable

if sys.platform == "win32":
    os.system("")  # Enable ANSI escape codes on Windows CMD
    # IDLE wraps stdout/stderr in StdOutputFile which lacks .reconfigure —
    # guard so launching from the IDLE editor doesn't crash at import time.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except (AttributeError, Exception):
            pass

try:
    import readline
except ImportError:
    readline = None  # Windows compatibility
# ── Optional rich for markdown rendering ──────────────────────────────────
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich import print as rprint
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False
    console = None

# ── Optional bubblewrap for chat bubbles (NerdFont required) ──────────────
try:
    from bubblewrap import Bubbles as _BubblesClass
    _bubbles = _BubblesClass()
    # Probe: can stdout actually encode the NerdFont powerline characters?
    # On legacy Windows consoles (cp1252) these fail with UnicodeEncodeError.
    _nf_test_chars = "\ue0b6\ue0b4"  # rounded powerline glyphs used by bubblewrap
    try:
        _enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        _nf_test_chars.encode(_enc)
        _HAS_BUBBLES = True
    except (UnicodeEncodeError, LookupError):
        _HAS_BUBBLES = False
        _bubbles = None
except ImportError:
    _HAS_BUBBLES = False
    _bubbles = None

# Single source of truth: pyproject.toml. Falls back to a hardcoded value
# only when the package isn't installed (e.g. running dulus.py from source
# without a `pip install -e .`).
try:
    from importlib.metadata import version as _pkg_version
    VERSION = _pkg_version("dulus")
except Exception:
    VERSION = "0.2.36"  # dev fallback — keep in sync with pyproject.toml

# ── ANSI helpers (used even with rich for non-markdown output) ─────────────
from common import C, clr, info, ok, warn, err, stream_thinking, print_tool_start, print_tool_end, sanitize_text

def _rl_safe(prompt: str) -> str:
    """Wrap ANSI escape sequences with \\001/\\002 so readline ignores them
    when calculating visible prompt width.  Fixes duplicate-on-scroll and
    cursor-misalignment bugs in terminals that use readline."""
    import re
    return re.sub(r'(\033\[[0-9;]*m)', r'\001\1\002', prompt)

# info, ok, warn, err, stream_thinking are imported from common above


def render_diff(text: str):
    """Print diff text with ANSI colors: red for removals, green for additions."""
    for line in text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            print(C["bold"] + line + C["reset"])
        elif line.startswith("+"):
            print(C["green"] + line + C["reset"])
        elif line.startswith("-"):
            print(C["red"] + line + C["reset"])
        elif line.startswith("@@"):
            print(C["cyan"] + line + C["reset"])
        else:
            print(line)

def _has_diff(text: str) -> bool:
    """Check if text contains a unified diff."""
    return "--- a/" in text and "+++ b/" in text


# ── Conversation rendering ─────────────────────────────────────────────────
# NOTE: This section mirrors ui/render.py with dulus-specific optimizations.
# Keep in sync with ui/render.py when making changes.

_accumulated_text: list[str] = []   # buffer text during streaming
_current_live: "Live | None" = None  # active Rich Live instance (one at a time)
_RICH_LIVE = True  # set to False (via config rich_live=false) to disable in-place Live streaming
_SUPPRESS_CONSOLE = False  # When True, all console output is suppressed (for background mode)

def _make_renderable(text: str):
    """Return a Rich renderable: Markdown if text contains markup, else plain."""
    if any(c in text for c in ("#", "*", "`", "_", "[")):
        # We use a custom style for code blocks to make them more subtle (less "blocky" background)
        # Default code block background can be aggressive for ASCII art.
        import common as _cm
        return Markdown(text, code_theme=getattr(_cm, "CODE_THEME", "monokai"))
    return text

def _use_bubbles() -> bool:
    """Whether to use bubblewrap chat-bubble mode (requires NerdFont + Rich)."""
    return _HAS_BUBBLES and _RICH

def _wrap_in_bubble(renderable, raw_text: str = ""):
    """Wrap a Rich renderable in a rounded Panel for chat-bubble effect.
    Calculates a snug width from the raw text to prevent the Panel from 
    taking up 100% of the screen width when rendering Markdown rules/tables."""
    from rich.box import ROUNDED
    kw = {"box": ROUNDED, "border_style": "bright_black", "padding": (0, 1), "expand": False}
    
    if raw_text:
        lines = raw_text.split("\n")
        # Estimate visual width (ignore minor ANSI/emoji double-width inaccuracies)
        max_len = max((len(line) for line in lines), default=0)
        # Add buffer space: ~2 for left/right borders, 2 for padding, + 6 margin for blockquotes
        snug_width = min(console.width - 2, max_len + 10)
        kw["width"] = snug_width
    else:
        kw["width"] = console.width - 2
        
    return Panel(renderable, **kw)

def _start_live() -> None:
    """Start a Rich Live block for in-place Markdown streaming (no-op if not Rich)."""
    global _current_live
    if _RICH and _RICH_LIVE and _current_live is None:
        _current_live = Live(console=console, auto_refresh=False,
                             vertical_overflow="visible")
        _current_live.start()

_last_live_update = 0
_LIVE_UPDATE_INTERVAL = 0.03  # 30ms throttle (~33 FPS) — keeps streaming fluid
_buffered_since_render = 0    # chunks buffered without a Live update
_LIVE_LINE_LIMIT = 80  # auto-switch to plain streaming beyond this many lines
_streamed_plain = False  # when bubbles forced plain streaming, skip bubble in flush

def stream_text(chunk: str) -> None:
    """Buffer chunk; update Live in-place when Rich available, else print directly.

    Safety: if accumulated text exceeds _LIVE_LINE_LIMIT lines, auto-switch
    from Rich Live to plain streaming to prevent terminal re-render duplication
    on terminals that can't handle large Live areas (Windows Terminal, etc.).
    """
    global _current_live, _last_live_update, _buffered_since_render
    _accumulated_text.append(chunk)

    # Suppress all console output when in background/silent mode
    if _SUPPRESS_CONSOLE:
        return

    # In split-layout mode stdout is redirected to _OutputRedirector; Rich
    # Live's cursor-based repaint pollutes the output buffer with ghost
    # lines (those "stuck messages" that keep reappearing). Force plain
    # streaming in that case — each chunk becomes one clean append.
    _redirected = type(sys.stdout).__name__ == "_OutputRedirector"

    # When bubbles are on, Live's cursor-up math goes wrong because the
    # snug Panel width grows mid-stream. Result: the bubble re-prints
    # stacked instead of in-place (the duplicated-bubble bug). Stream
    # plain during the response, render the bubble once in flush_response.
    _bubble_active = _use_bubbles()

    if _RICH and _RICH_LIVE and not _redirected and not _bubble_active:
        full = "".join(_accumulated_text)
        line_count = full.count("\n")

        # Safety: too many lines → kill Live and fall back to plain streaming
        if _current_live is not None and line_count > _LIVE_LINE_LIMIT:
            _current_live.stop()
            _current_live = None
            # Print the full text once (Live already displayed partial content,
            # but stopping Live clears it — so we re-print cleanly)
            _r = _make_renderable(full)
            if _use_bubbles():
                _r = _wrap_in_bubble(_r, full)
            console.print(_r)
            _accumulated_text.clear()
            return

        if line_count <= _LIVE_LINE_LIMIT:
            if _current_live is None:
                _start_live()
            # Throttle updates for performance
            _buffered_since_render += 1
            now = time.time()
            if ((now - _last_live_update) > _LIVE_UPDATE_INTERVAL
                    or len(chunk) > 50
                    or _buffered_since_render >= 5):
                _r = _make_renderable(full)
                if _use_bubbles():
                    _r = _wrap_in_bubble(_r, full)
                _current_live.update(_r, refresh=True)
                _last_live_update = now
                _buffered_since_render = 0
        else:
            # Already past limit, no Live — just append new chunk
            print(chunk, end="", flush=True)
    elif _bubble_active:
        # Bubble mode: stream plain so the user sees progress. We mark
        # _streamed_plain so flush_response skips the bubble repaint
        # (text is already on screen — re-printing it inside a Panel
        # would duplicate the response).
        global _streamed_plain
        # Defensive: if a Live instance leaked from a previous turn
        # (sub-agent flow, exception during streaming, etc.) kill it.
        # Otherwise that orphan Live keeps repainting bubbles below us.
        if _current_live is not None:
            try:
                _current_live.stop()
            except Exception:
                pass
            _current_live = None
        _streamed_plain = True
        print(chunk, end="", flush=True)
    else:
        print(chunk, end="", flush=True)

# stream_thinking imported from common above

def _count_visual_lines(text: str, width: int) -> int:
    """How many terminal rows did `text` occupy when streamed plain?
    Counts wraps for long logical lines, ignores ANSI for length math.
    Approximate (doesn't track double-width emoji exactly) but good
    enough for the bubble re-render erase trick."""
    import re as _re
    total = 0
    width = max(1, width)
    for line in text.split("\n"):
        stripped = _re.sub(r'\x1b\[[0-9;]*m', '', line)
        visible = len(stripped)
        wrapped = max(1, (visible + width - 1) // width) if visible else 1
        total += wrapped
    return total


def flush_response() -> None:
    """Commit buffered text to screen: stop Live (freezes rendered Markdown in place)."""
    global _current_live, _streamed_plain
    full = "".join(_accumulated_text)
    _accumulated_text.clear()

    # If bubbles forced plain streaming, erase what we streamed and
    # repaint the whole response inside a Panel — gives the user the
    # clean bubble without the mid-stream duplication bug.
    if _streamed_plain:
        _streamed_plain = False
        if full.strip():
            try:
                lines = _count_visual_lines(full, console.width)
                # Move cursor up `lines` rows to col 0, clear from there to EOS.
                sys.stdout.write(f"\r\033[{lines}A\033[J")
                sys.stdout.flush()
                _r = _make_renderable(full)
                _r = _wrap_in_bubble(_r, full)
                out_c = Console(
                    file=sys.stdout,
                    width=console.width,
                    force_terminal=console.is_terminal,
                    color_system=console.color_system,
                    legacy_windows=console.legacy_windows,
                )
                out_c.print(_r)
            except Exception:
                # Fallback: if escape codes don't work, just close cleanly.
                # The plain text stays on screen — no bubble but no duplicate.
                print()
        return

    if _current_live is not None:
        try:
            # Final render pass — chunks buffered within the last window may not
            # have triggered an update() yet. Freeze the Live at the complete text.
            if full:
                _r = _make_renderable(full)
                if _use_bubbles():
                    _r = _wrap_in_bubble(_r, full)
                _current_live.update(_r, refresh=True)
            _current_live.stop()
        except Exception:
            pass
        finally:
            _current_live = None
    elif _use_bubbles() and full.strip():
        # Bubble mode without Live (background turns, etc.):
        # Render Panel natively directly to sys.stdout (even if it's a StringIO).
        # Conserving original terminal capabilities so it renders actual Unicode borders.
        _r = _make_renderable(full)
        _r = _wrap_in_bubble(_r, full)
        out_c = Console(
            file=sys.stdout,
            width=console.width,
            force_terminal=console.is_terminal,
            color_system=console.color_system,
            legacy_windows=console.legacy_windows
        )
        out_c.print(_r)
    elif _RICH and full.strip() and type(sys.stdout).__name__ != "_OutputRedirector":
        # Fallback: Rich available but no bubbles — render markdown statically
        console.print(_make_renderable(full))
    else:
        print()
    sys.stdout.flush()

from spinner import TOOL_SPINNER_PHRASES as _TOOL_SPINNER_PHRASES
from spinner import DEBATE_SPINNER_PHRASES as _DEBATE_SPINNER_PHRASES

_tool_spinner_thread = None
_tool_spinner_stop = threading.Event()

_telegram_thread: threading.Thread | None = None
_telegram_stop: threading.Event | None = None

_spinner_phrase = ""
_spinner_lock = threading.Lock()

def _run_tool_spinner():
    """Background spinner on a single line using carriage return.

    In split-input mode stdout is redirected to _OutputRedirector (which
    line-buffers and strips \\r), so each spinner frame would eventually
    accumulate into the output area. Skip writes in that case — the split
    layout has its own visual affordance.
    """
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not _tool_spinner_stop.is_set():
        with _spinner_lock:
            phrase = _spinner_phrase
        frame = chars[i % len(chars)]
        _redirected = type(sys.stdout).__name__ == "_OutputRedirector"
        if not _SUPPRESS_CONSOLE and not _redirected:
            sys.stdout.write(f"\033[2K\r  {frame} {clr(phrase, 'dim')}   ")
            sys.stdout.flush()
        i += 1
        _tool_spinner_stop.wait(0.1)

def _start_tool_spinner(phrase: str | None = None):
    global _tool_spinner_thread
    if _tool_spinner_thread and _tool_spinner_thread.is_alive():
        return  # already running
    import random
    with _spinner_lock:
        global _spinner_phrase
        _spinner_phrase = phrase or random.choice(_TOOL_SPINNER_PHRASES)
    _tool_spinner_stop.clear()
    _tool_spinner_thread = threading.Thread(target=_run_tool_spinner, daemon=True)
    _tool_spinner_thread.start()

def _change_spinner_phrase():
    """Change the spinner phrase without stopping it."""
    import random
    with _spinner_lock:
        global _spinner_phrase
        _spinner_phrase = random.choice(_TOOL_SPINNER_PHRASES)

def _stop_tool_spinner():
    global _tool_spinner_thread
    if not _tool_spinner_thread:
        return
    _tool_spinner_stop.set()
    _tool_spinner_thread.join(timeout=1)
    _tool_spinner_thread = None
    # Clear entire line regardless of cursor position
    _redirected = type(sys.stdout).__name__ == "_OutputRedirector"
    if not _SUPPRESS_CONSOLE and not _redirected:
        sys.stdout.write("\033[2K\r")
        sys.stdout.flush()

def print_tool_start(name: str, inputs: dict, verbose: bool):
    """Show tool invocation."""
    desc = _tool_desc(name, inputs)
    print(clr(f"  ⚙  {desc}", "dim", "cyan"), flush=True)
    if verbose:
        print(clr(f"     inputs: {json.dumps(inputs, ensure_ascii=False)[:200]}", "dim"))

def print_tool_end(name: str, result: str, verbose: bool, config: dict = None):
    # Special handling for PrintToConsole - always show full content
    if name == "PrintToConsole":
        print(clr(f"  [PrintToConsole] {len(result)} chars", "dim", "cyan"), flush=True)
        print()
        # Print content directly to avoid encoding issues with clr()
        # NO TRUNCATION - PrintToConsole shows EVERYTHING to the console (0 tokens)
        try:
            print(result, flush=True)
        except UnicodeEncodeError:
            print(result.encode('utf-8', errors='replace').decode('utf-8'), flush=True)
        print(flush=True)
        return
    
    # Check if this is a display-only tool (visual output like ASCII art)
    from tool_registry import is_display_only
    is_display = is_display_only(name)
    
    # auto_show is the master switch for user-facing output.
    # ON  → render the tool's full output to the user (display tools, bash, reads, etc.)
    # OFF → suppress automatic render; a hint is injected into the model's view
    #       (see agent.py) so it can call PrintToConsole when output matters.
    auto_show = config.get("auto_show", True) if config else True

    lines = result.count("\n") + 1
    size = len(result)
    summary = f"-> {lines} lines ({size} chars)"
    if not result.startswith("Error") and not result.startswith("Denied"):
        print(clr(f"  [OK] {summary}", "dim", "green"), flush=True)

        # Display-only tools render their full output when auto_show is ON.
        if is_display and auto_show:
            print()
            try:
                print(result)
            except UnicodeEncodeError:
                print(result.encode('utf-8', errors='replace').decode('utf-8'))
            print()

        # Render diff for Edit/Write results only in verbose mode
        if verbose and name in ("Edit", "Write") and _has_diff(result):
            parts = result.split("\n\n", 1)
            if len(parts) == 2:
                print(clr(f"  {parts[0]}", "dim"))
                render_diff(parts[1])
    else:
        print(clr(f"  [X] {result[:120]}", "dim", "red"), flush=True)
    if verbose and not result.startswith("Denied") and not (is_display and auto_show):
        preview = result[:500] + ("..." if len(result) > 500 else "")
        try:
            print(clr(f"     {preview.replace(chr(10), chr(10)+'     ')}", "dim"))
        except UnicodeEncodeError:
            safe = preview.encode('ascii', errors='replace').decode('ascii')
            print(clr(f"     {safe}", "dim"))

def _tool_desc(name: str, inputs: dict) -> str:
    if name == "Read":   return f"Read({inputs.get('file_path','')})"
    if name == "Write":  return f"Write({inputs.get('file_path','')})"
    if name == "Edit":   return f"Edit({inputs.get('file_path','')})"
    if name == "Bash":   return f"Bash({inputs.get('command','')[:80]})"
    if name == "Glob":   return f"Glob({inputs.get('pattern','')})"
    if name == "Grep":   return f"Grep({inputs.get('pattern','')})"
    if name == "WebFetch":    return f"WebFetch({inputs.get('url','')[:60]})"
    if name == "WebSearch":   return f"WebSearch({inputs.get('query','')})"
    if name == "Agent":
        atype = inputs.get("subagent_type", "")
        aname = inputs.get("name", "")
        iso   = inputs.get("isolation", "")
        parts = []
        if atype:  parts.append(atype)
        if aname:  parts.append(f"name={aname}")
        if iso:    parts.append(f"isolation={iso}")
        suffix = f"({', '.join(parts)})" if parts else ""
        prompt_short = inputs.get("prompt", "")[:60]
        return f"Agent{suffix}: {prompt_short}"
    if name == "SendMessage":
        return f"SendMessage(to={inputs.get('to','')}: {inputs.get('message','')[:50]})"
    if name == "CheckAgentResult": return f"CheckAgentResult({inputs.get('task_id','')})"
    if name == "ListAgentTasks":   return "ListAgentTasks()"
    if name == "ListAgentTypes":   return "ListAgentTypes()"
    return f"{name}({list(inputs.values())[:1]})"


# ── Permission prompt ──────────────────────────────────────────────────────

def ask_permission_interactive(desc: str, config: dict) -> bool:
    text = ask_input_interactive(f"  Allow: {desc}  [y/N/a(ccept-all)] ", config).strip().lower()

    if text == "a" or text == "accept all" or text == "accept-all":
        config["permission_mode"] = "accept-all"
        if _is_in_tg_turn(config):
            token = config.get("telegram_token")
            # Reply to the user who actually triggered this prompt; fall back
            # to the first configured chat_id if the active one is unknown.
            cid = config.get("_active_tg_chat_id") or (_tg_get_chat_ids(config) or [None])[0]
            if cid:
                _tg_send(token, cid, "✅ Permission mode set to accept-all for this session.")
        else:
            ok("  Permission mode set to accept-all for this session.")
        return True
    
    return text in ("y", "yes")


# ── Slash commands ─────────────────────────────────────────────────────────

import time
import traceback

def _proactive_watcher_loop(config):
    """Background daemon that fires a wake-up prompt after a period of inactivity."""
    while True:
        time.sleep(1)
        if not config.get("_proactive_enabled"):
            continue
        try:
            now = time.time()
            interval = config.get("_proactive_interval", 300)
            last = config.get("_last_interaction_time", now)
            if now - last >= interval:
                config["_last_interaction_time"] = now
                cb = config.get("_run_query_callback")
                if cb:
                    # Grace period: the user may have sent a message exactly
                    # when the timer fired. Wait a beat and re-check. If they
                    # did, abort this firing to prevent output reordering
                    # (background landing after the user's turn).
                    time.sleep(0.5)
                    if time.time() - config.get("_last_interaction_time", 0) < 5:
                        continue
                    cb(f"(System Automated Event) You have been inactive for {interval} seconds. "
                           "Before doing anything else, review your previous messages in this conversation. "
                           "💡 CRITICAL HINT: Look up to find the LAST true direct message from the user so you don't lose the context of the conversation! "
                           "If you said you would implement, fix, or do something and didn't finish it, "
                           "continue and complete that work now. "
                           "Otherwise, check if you have any pending tasks to execute or simply say 'No pending tasks'.")
        except Exception as e:
            print(f"\n[proactive watcher error]: {e}", flush=True)

# Categorized command catalog for /help. Order = page order.
# Each entry: (page_title, [(command, one_line_description), ...])
_HELP_PAGES = [
    ("Core", [
        ("/help",        "Show this help (paginated)"),
        ("/clear",       "Clear conversation"),
        ("/model [m]",   "Show or set the active model"),
        ("/config",      "Show config / set key=value"),
        ("/cwd [path]",  "Show or change working directory"),
        ("/copy [file]", "Copy last response (or file) to clipboard"),
        ("/shell [cmd|on|off]", "Shell mode toggle or one-shot command"),
        ("/exit /quit",  "Exit Dulus"),
    ]),
    ("Session", [
        ("/save [name]",  "Save session to file (any name)"),
        ("/load",         "Load session — paginated by day (*D*S syntax)"),
        ("/history",      "Print conversation history"),
        ("/context",      "Show context window usage"),
        ("/cost",         "Show API cost this session"),
        ("/fork",         "Fork session at a given turn"),
        ("/undo",         "Undo last turn"),
        ("/import <file>","Import conversation from file/session"),
        ("/add-dir [path]","Manage additional workspace directories"),
        ("/batch",        "Manage Kimi Batch tasks"),
        ("/roundtable",   "Multi-model roundtable discussion"),
    ]),
    ("Memory & Soul", [
        ("/memory [query]",      "Search persistent memories"),
        ("/memory list",         "List all stored memories"),
        ("/memory load <n|name>","Inject memory into context"),
        ("/memory delete <name>","Delete a specific memory"),
        ("/memory purge",        "Wipe memories (keep Soul)"),
        ("/memory purge-soul",   "Wipe EVERYTHING (danger)"),
        ("/memory consolidate",  "Extract long-term insights via AI"),
        ("/soul [name]",         "List souls / switch active soul"),
    ]),
    ("Skills · Plugins · Agents · MCP · Tasks", [
        ("/skills",                 "List active Dulus skills"),
        ("/skill list",             "Browse installed + available skills"),
        ("/skill get <slug>",       "Install an Anthropic/ClawHub skill"),
        ("/skill use <name>",       "Inject skill into next message"),
        ("/skill remove <name>",    "Uninstall a skill"),
        ("/plugin",                 "List installed plugins"),
        ("/plugin install <name@url>","Install a plugin"),
        ("/plugin uninstall <name>","Uninstall a plugin"),
        ("/plugin enable|disable <n>","Toggle a plugin"),
        ("/plugin update <name>",   "Update a plugin"),
        ("/plugin recommend [ctx]", "Recommend plugins for a context"),
        ("/agents",                 "Show sub-agent tasks"),
        ("/mcp",                    "List MCP servers and tools"),
        ("/mcp reload | add | remove","Manage MCP servers"),
        ("/tasks",                  "List/create/update tasks"),
    ]),
    ("Voice · Wake", [
        ("/voice",                  "Record voice → transcribe → submit"),
        ("/voice status",           "Show recording + STT backends"),
        ("/voice lang <code>",      "Set STT language (zh/en/ja/auto)"),
        ("/wake on|off",            "Toggle wake-word ('Hey Dulus')"),
        ("/wake status",            "Show wake-word listener state"),
        ("/wake phrases",           "List recognised wake phrases"),
        ("/wake calibrate",         "Measure mic 5s, suggest threshold"),
        ("/wake test",              "Debug mode (RMS + STT for 10s)"),
        ("/wake threshold <n>",     "Tune mic sensitivity (0.001–1.0)"),
    ]),
    ("Web · Sandbox · Cloud · Harvest", [
        ("/webchat [port]",         "Spawn web chat UI (Flask)"),
        ("/webchat stop",           "Kill the webchat server"),
        ("/sandbox",                "Open Dulus Sandbox OS in browser"),
        ("/sandbox stop",           "Stop the sandbox server"),
        ("/cloudsave",              "Upload current session to GitHub Gist"),
        ("/cloudsave setup <token>","Configure GitHub token"),
        ("/cloudsave auto on|off",  "Toggle auto-upload on exit"),
        ("/cloudsave list",         "List your Dulus Gists"),
        ("/cloudsave load <id>",    "Download + load a session from Gist"),
        ("/harvest",                "Harvest Claude.ai cookies"),
        ("/harvest-kimi",           "Harvest Kimi consumer tokens"),
        ("/harvest-gemini",         "Harvest Gemini consumer tokens"),
        ("/harvest-qwen",           "Harvest Qwen tokens"),
        ("/kimi_chats",             "List recent Kimi conversations"),
    ]),
    ("Advanced", [
        ("/thinking [off|min|med|max|raw|0-4]","Set extended-thinking level"),
        ("/schema [tool]",          "Inspect tool input schema"),
        ("/deep_override",          "DeepSeek simplified prompt (toggle)"),
        ("/deep_tools",             "DeepSeek auto JSON tool-wrap (toggle)"),
        ("/autojob",                "Auto-print job results (toggle)"),
        ("/auto_show",              "Auto-render visual tools (toggle)"),
        ("/ultra_search",           "Aggressive multi-query search"),
        ("/permissions [mode]",     "Set permission mode"),
        ("/afk",                    "AFK mode (auto-approve tools)"),
        ("/yolo",                   "YOLO mode (auto-approve ALL)"),
        ("/proactive [dur|off]",    "Background sentinel polling"),
        ("/kill_tmux",              "Kill stuck tmux/psmux sessions"),
        ("/rtk [on|off]",           "Toggle RTK shell-command rewriting"),
    ]),
]


def _render_toggle_footer(config) -> None:
    """Print the toggle status block. Called at the bottom of every /help page
    so the user always sees current state without scrolling.
    """
    _toggles = [
        ("auto_show",       True,  "/auto_show",       "Visual tools auto-render to console"),
        ("autojob",         False, "/autojob",         "Auto-print full background-job results"),
        ("verbose",         False, "/verbose",         "Verbose output (thinking chunks, debug)"),
        ("sticky_input",    True,  "/sticky_input",    "Anchored input bar (prompt_toolkit)"),
        ("hide_sender",     True,  "/hide_sender",     "Hide typed message above the bar"),
        ("mem_palace",      True,  "/mem_palace",      "Per-turn MemPalace memory injection"),
        ("mem_palace_print",False, "/mem_palace print","Debug-print MemPalace injections"),
        ("schema_autoload", True,  "/schema_autoload", "Inject full tool inventory at startup"),
        ("ultra_search",    False, "/ultra_search",    "Aggressive multi-query search"),
        ("proactive",       False, "/proactive",       "Background sentinel polling"),
        ("cloudsave_auto",  False, "/cloudsave auto",  "Auto-upload session to Gist on exit"),
        ("lite_mode",       False, "/lite",            "Lite mode (smaller system prompt)"),
        ("brave_search_enabled", False, "/brave",      "Brave Search API integration"),
        ("tts_enabled",     False, "/tts",             "Automatic Text-to-Speech"),
        ("wake_enabled",    False, "/wake",            "Wake-word hotword detection"),
        ("daemon",          False, "/daemon",          "External triggers without REPL"),
        ("afk_mode",        False, "/afk",             "AFK mode (auto-approve tools)"),
        ("yolo_mode",       False, "/yolo",            "YOLO mode (auto-approve ALL)"),
        ("rtk_enabled",     True,  "/rtk",             "RTK shell command rewriting"),
    ]
    print(clr("  ── Toggles ──", "cyan", "bold"))
    for key, default, cmd, desc in _toggles:
        val = config.get(key, default)
        state_str = clr("ON ", "green") if val else clr("OFF", "red")
        print(f"  [{state_str}]  {clr(cmd, 'magenta'):<28} {clr(desc, 'dim')}")


def _render_help_page_telegram(config) -> None:
    """Telegram-friendly rendering: full categorized dump, no pagination.
    Telegram users can scroll the message; pagination would need extra UX
    wiring through the bot. Toggles are appended at the end once.
    """
    print("Dulus — Commands\n")
    for title, items in _HELP_PAGES:
        print(f"━━ {title} ━━")
        for cmd, desc in items:
            print(f"  {cmd:<32} {desc}")
        print()
    print("━━ Toggles ━━")
    _render_toggle_footer(config)


def cmd_help(_args: str, _state, config) -> bool:
    # ── Telegram routing ────────────────────────────────────────────────
    # When /help arrives via the Telegram bridge, pagination is hostile —
    # there's no live keyboard. Dump a single categorized message and bail.
    if config.get("_telegram_incoming"):
        _render_help_page_telegram(config)
        return True

    # ── REPL: full-redraw paginated help (Mr. Robot style) ──────────────
    # Each page = ANSI clear + header + category block + toggle footer.
    # Nav: [n]ext, [p]rev, [number]=jump, Enter/q to quit. Toggles are
    # reprinted on every page so current state is always visible.
    pages = _HELP_PAGES
    total = len(pages)
    idx = 0
    is_tty = sys.stdin.isatty()
    while True:
        # Clear screen (ANSI). Falls back to blank lines when stdout isn't
        # a TTY (e.g. piped to a file).
        if is_tty:
            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.flush()
        else:
            print("\n" * 3)

        title, items = pages[idx]
        print(clr(f"  Dulus — Commands   ({idx+1}/{total})  {title}", "cyan", "bold"))
        print(clr("  " + "─" * 60, "dim"))
        for cmd, desc in items:
            print(f"  {clr(cmd, 'magenta'):<40} {clr(desc, 'dim')}")

        print()
        _render_toggle_footer(config)

        if not is_tty or total <= 1:
            # Single-page or non-TTY → render once and stop.
            return True

        nav = clr(
            f"\n  [n]ext · [p]rev · 1-{total} jump · Enter/q quit  > ",
            "yellow",
        )
        try:
            choice = input(nav).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return True

        if not choice or choice in ("q", "quit", "exit"):
            return True
        if choice in ("n", "next", " "):
            idx = (idx + 1) % total
            continue
        if choice in ("p", "prev", "b", "back"):
            idx = (idx - 1) % total
            continue
        if choice.isdigit():
            n = int(choice)
            if 1 <= n <= total:
                idx = n - 1
                continue
        # Unknown input → just redraw current page.
        continue

def cmd_model(args: str, _state, config) -> bool:
    from providers import PROVIDERS, detect_provider
    if not args:
        model = config["model"]
        pname = detect_provider(model)
        info(f"Current model:    {model}  (provider: {pname})")
        info("\nAvailable models by provider:")
        for pn, pdata in PROVIDERS.items():
            ms = pdata.get("models", [])
            if ms:
                info(f"  {pn:12s}  " + ", ".join(ms[:4]) + ("..." if len(ms) > 4 else ""))
        info("\nFormat: 'provider/model' or just model name (auto-detected)")
        info("  e.g. /model gpt-4o")
        info("  e.g. /model ollama/qwen2.5-coder")
        info("  e.g. /model kimi:moonshot-v1-32k")
    else:
        # Accept both "ollama/model" and "ollama:model" syntax
        # Only treat ':' as provider separator if left side is a known provider
        m = args.strip()
        if "/" not in m and ":" in m:
            left, right = m.split(":", 1)
            if left in PROVIDERS:
                m = f"{left}/{right}"
        config["model"] = m
        pname = detect_provider(m)
        ok(f"Model set to {m}  (provider: {pname})")
        from config import save_config
        save_config(config)
    return True

def _generate_personas(topic: str, curr_model: str, config: dict, count: int = 5) -> dict | None:
    """Ask the LLM to generate `count` topic-appropriate expert personas as a dict."""
    from providers import stream, TextChunk
    import json

    example_entries = "\n".join(
        f'  "p{i+1}": {{"icon": "emoji", "role": "Expert Title", "desc": "One sentence describing their analytical angle."}}'
        for i in range(count)
    )
    user_msg = f"""Generate {count} expert personas for a multi-perspective brainstorming debate on: "{topic}"

Return ONLY a valid JSON object — no markdown fences, no extra text — like this:
{{
{example_entries}
}}

Choose experts whose domains are most relevant to analyzing "{topic}" from different angles."""

    internal_config = config.copy()
    internal_config["no_tools"] = True
    chunks = []
    try:
        for event in stream(curr_model, "You are a debate facilitator. Return only valid JSON.", [{"role": "user", "content": user_msg}], [], internal_config):
            if isinstance(event, TextChunk):
                chunks.append(event.text)
    except Exception:
        return None

    raw = "".join(chunks).strip()
    # Strip markdown code fences if the model wraps in ```json ... ```
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    try:
        return json.loads(raw)
    except Exception:
        return None


_TECH_PERSONAS = {
    "architect":   {"icon": "🏗️", "role": "Principal Software Architect",       "desc": "Focus on modularity, clear boundaries, patterns, and long-term maintainability."},
    "innovator":   {"icon": "💡", "role": "Pragmatic Product Innovator",          "desc": "Focus on bold, technically feasible ideas that add high user value and differentiation."},
    "security":    {"icon": "🛡️", "role": "Security & Risk Engineer",            "desc": "Focus on vulnerabilities, data integrity, secrets handling, and project robustness."},
    "refactor":    {"icon": "🔧", "role": "Senior Code Quality Lead",             "desc": "Focus on code smells, complexity reduction, DRY principles, and readability."},
    "performance": {"icon": "⚡", "role": "Performance & Optimization Specialist","desc": "Focus on I/O bottlenecks, resource efficiency, latency, and scalability."},
}


def _interactive_ollama_picker(config: dict) -> bool:
    """Prompt the user to select from locally available Ollama models."""
    from providers import PROVIDERS, list_ollama_models
    prov = PROVIDERS.get("ollama", {})
    base_url = prov.get("base_url", "http://localhost:11434")
    
    models = list_ollama_models(base_url)
    if not models:
        err(f"No local Ollama models found at {base_url}.")
        return False
        
    menu_buf = clr("\n  ── Local Ollama Models ──", "dim")
    for i, m in enumerate(models):
        menu_buf += "\n" + clr(f"  [{i+1:2d}] ", "yellow") + m
    print(menu_buf)
    print()

    try:
        ans = ask_input_interactive(clr("  Select a model number or Enter to cancel > ", "cyan"), config, menu_buf).strip()
        if not ans: return False
        idx = int(ans) - 1
        if 0 <= idx < len(models):
            new_model = f"ollama/{models[idx]}"
            config["model"] = new_model
            from config import save_config
            save_config(config)
            ok(f"Model updated to {new_model}")
            return True
        else:
            err("Invalid selection.")
    except (ValueError, KeyboardInterrupt, EOFError):
        pass
    return False

def cmd_brainstorm(args: str, state, config) -> bool:
    """Run a multi-persona iterative brainstorming session on the project.
    
    Usage: /brainstorm [topic]
    """
    from providers import stream
    import time
    from pathlib import Path
    
    # ── Context Snapshot ──────────────────────────────────────────────────
    readme_path = Path("README.md")
    readme_content = ""
    if readme_path.exists():
        readme_content = readme_path.read_text("utf-8", errors="replace")
    
    dulus_md = Path("DULUS.md")
    dulus_content = ""
    if dulus_md.exists():
        dulus_content = dulus_md.read_text("utf-8", errors="replace")
        
    project_files = "\n".join([f.name for f in Path(".").glob("*") if f.is_file() and not f.name.startswith(".")])
    
    user_topic = args.strip() or "general project improvement and architectural evolution"

    # ── Ask user for agent count interactively ────────────────────────────
    if config.get("_telegram_incoming"):
        agent_count = 5  # skip interactive input when called from Telegram
    else:
        try:
            ans = ask_input_interactive(clr(f"  How many agents? (2-100, default 5) > ", "cyan"), config).strip()
            agent_count = int(ans) if ans else 5
            agent_count = max(2, min(agent_count, 100))
        except (ValueError, KeyboardInterrupt, EOFError):
            agent_count = 5
    
    snapshot = f"""PROJECT CONTEXT:
README:
{readme_content[:3000]}

DULUS.MD:
{dulus_content[:1000]}

ROOT FILES:
{project_files}

USER FOCUS: {user_topic}
"""
    curr_model = config["model"]

    # ── Personas (dynamically generated per topic) ────────────────────────
    info(clr(f"Generating {agent_count} topic-appropriate expert personas...", "dim"))
    personas = _generate_personas(user_topic, curr_model, config, count=agent_count)
    if not personas:
        info(clr("(persona generation failed, using default tech personas)", "dim"))
        personas = dict(list(_TECH_PERSONAS.items())[:agent_count])
    
    # ── Identity Generator ────────────────────────────────────────────────
    def get_identity(letter):
        try:
            from faker import Faker
            fake = Faker()
            return f"{letter}", fake.name()
        except ImportError:
            first = ["Alex", "Sam", "Taylor", "Jordan", "Casey", "Riley", "Drew", "Avery"]
            last = ["Garcia", "Martinez", "Lopez", "Hernandez", "Gonzalez", "Sanchez", "Ramirez", "Torres"]
            import random
            return f"{letter}", f"{random.choice(first)} {random.choice(last)}"
            
    # ── Debate Loop ───────────────────────────────────────────────────────
    outputs_dir = Path("brainstorm_outputs")
    outputs_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_file = outputs_dir / f"brainstorm_{ts}.md"
    
    brainstorm_history = []
    
    ok(f"Starting {agent_count}-Agent Brainstorming Session on: {clr(user_topic, 'bold')}")
    info(clr("Generating diverse perspectives...", "dim"))

    # Helper function to call the model via the unified stream() function
    def call_persona(persona_name, p_data, history):
        letter, name = get_identity(persona_name[0].upper())
        # We wrap the persona instructions into a 'system' role
        system_prompt = f"""You are {name}, the {p_data['role']}. Identity: Agent {letter}.
{p_data['desc']}

TOPIC UNDER DISCUSSION: {user_topic}

PROJECT CONTEXT (if relevant to the topic):
{snapshot}

INSTRUCTIONS:
1. Provide 3-5 concrete, actionable insights or ideas from your expert perspective on the topic.
2. If there are prior ideas from other agents, briefly acknowledge them and build upon or challenge them.
3. Be specific, well-reasoned, and professional. Stay in character as your role.
4. Prefix each of your points with: [Agent {letter} — {name}]
5. Output your response in clean Markdown.
"""
        user_msg = f"TOPIC: {user_topic}\n\nPRIOR IDEAS FROM DEBATE:\n{history or 'No previous ideas yet. You are the first to speak.'}"
        
        full_response = []
        # Internal calls should not include tools (tool_schemas already passed as [])
        internal_config = config.copy()
        internal_config["no_tools"] = True
        
        try:
            from providers import TextChunk
            for event in stream(curr_model, system_prompt, [{"role": "user", "content": user_msg}], [], internal_config):
                if isinstance(event, TextChunk):
                    full_response.append(event.text)
        except Exception as e:
            return f"Error from Agent {letter}: {e}"
            
        return "".join(full_response).strip()

    full_log = [f"# Brainstorming Session: {user_topic}", f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}", f"**Model:** {curr_model}", "---"]
    
    for p_name, p_data in personas.items():
        icon = p_data.get("icon", "🤖")
        info(f"{icon} {clr(p_data['role'], 'yellow')} is thinking...")
        _start_tool_spinner()

        hist_text = "\n\n".join(brainstorm_history) if brainstorm_history else ""
        content = call_persona(p_name, p_data, hist_text)

        _stop_tool_spinner()
        if content:
            brainstorm_history.append(content)
            full_log.append(f"## {icon} {p_data['role']}\n{content}")
            print(clr("  └─ Perspective captured.", "dim"))
        else:
            err(f"  └─ Failed to capture {p_name} perspective.")

    # Save to file
    final_output = "\n\n".join(full_log)
    out_file.write_text(final_output, encoding="utf-8")
    
    ok(f"Brainstorming complete! Results saved to {clr(str(out_file), 'bold')}")
    
    # ── Synthetic Injection ──────────────────────────────────────────────
    info(clr("Injecting debate results into current session for final analysis...", "dim"))

    synthesis_prompt = f"""I have just completed a multi-agent brainstorming session regarding: '{user_topic}'.
The full debate results have been saved to the file: {out_file}

Please read that file, then analyze the diverse perspectives. Identify the strongest ideas, potential conflicts, and provide a synthesized 'Master Plan' with concrete phases. Be concise and actionable."""

    # Return sentinel to trigger synthesis via run_query in the main REPL loop
    # Pass out_file so the REPL can append the synthesis to the same file.
    return ("__brainstorm__", synthesis_prompt, str(out_file))

def _save_synthesis(state, out_file: str) -> None:
    """Append the last assistant response as the synthesis section of the brainstorm file."""
    from pathlib import Path
    for msg in reversed(state.messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            return
        text = text.strip()
        if not text:
            return
        try:
            with Path(out_file).open("a", encoding="utf-8") as f:
                f.write("\n\n---\n\n## 🧠 Synthesis — Master Plan\n\n")
                f.write(text)
                f.write("\n")
            ok(f"Synthesis appended to {clr(out_file, 'bold')}")
        except Exception as e:
            err(f"Failed to save synthesis: {e}")
        return


def _print_dulus_banner(config: dict, with_logo: bool = True) -> None:
    """Reprint the Dulus logo + info box (used by startup and /clear)."""
    from providers import detect_provider
    if with_logo:
        logo = globals().get("_DULUS_LOGO_CACHED")
        if logo:
            for line in logo:
                print(clr(line, "cyan", "bold"))
            print()
    model    = config["model"]
    pname    = detect_provider(model)
    model_clr = clr(model, "cyan", "bold")
    prov_clr  = clr(f"({pname})", "dim")
    pmode     = clr(config.get("permission_mode", "auto"), "yellow")
    ver_clr   = clr(f"v{VERSION}", "green")
    print(clr("  ╭─ ", "dim") + clr("Dulus ", "cyan", "bold") + ver_clr + clr(" ─────────────────────────────────╮", "dim"))
    print(clr("  │", "dim") + clr("  Model: ", "dim") + model_clr + " " + prov_clr)
    print(clr("  │", "dim") + clr("  Permissions: ", "dim") + pmode)
    print(clr("  │", "dim") + clr("  /model to switch · /help for commands", "dim"))
    print(clr("  ╰──────────────────────────────────────────────────────╯", "dim"))


def cmd_clear(_args: str, state, config) -> bool:
    state.messages.clear()
    state.turn_count = 0
    # Wipe paste placeholders so old pasted text doesn't leak into new session
    if _paste_ph is not None:
        _paste_ph.reset_handler()
    # Reset git prompt cache so branch info refreshes after clear
    if _git_prompt is not None:
        _git_prompt.reset_git_cache()
    # Wipe the split-layout output buffer too — otherwise its contents get
    # re-rendered on the next app refresh and "ghost" back below new output.
    try:
        import input as _dulus_input
        if hasattr(_dulus_input, "clear_split_output"):
            _dulus_input.clear_split_output()
    except Exception:
        pass
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass
    try:
        _print_dulus_banner(config)
    except Exception:
        pass
    ok("Conversation cleared.")
    return True

_SECRET_PATTERNS = ("api_key", "token", "secret", "password", "passwd", "credential")

def _redact_secret(value) -> str:
    """Mask all but last 4 chars of a secret value."""
    if not isinstance(value, str) or not value:
        return "(empty)"
    if len(value) <= 8:
        return "***"
    return f"***{value[-4:]}"

def _is_secret_key(key: str) -> bool:
    kl = key.lower()
    return any(pat in kl for pat in _SECRET_PATTERNS)

def cmd_config(args: str, _state, config) -> bool:
    from config import save_config
    if not args:
        # Redact anything that looks like a secret (api_key/*_token/etc).
        display = {}
        for k, v in config.items():
            if k.startswith("_"):
                continue
            display[k] = _redact_secret(v) if _is_secret_key(k) else v
        print(json.dumps(display, indent=2))
    elif "=" in args:
        key, _, val = args.partition("=")
        key, val = key.strip(), val.strip()
        # Type coercion
        if val.lower() in ("true", "false"):
            val = val.lower() == "true"
        elif val.isdigit():
            val = int(val)
        config[key] = val
        # Immediate env-bridge for keys that submodules read from os.environ
        if key == "azure_speech_key" and val:
            os.environ["AZURE_SPEECH_KEY"] = val
        if key == "azure_speech_region" and val:
            os.environ["AZURE_SPEECH_REGION"] = val
        save_config(config)
        shown = _redact_secret(val) if _is_secret_key(key) else val
        ok(f"Set {key} = {shown}")
    else:
        k = args.strip()
        v = config.get(k, "(not set)")
        if _is_secret_key(k) and v != "(not set)":
            v = _redact_secret(v)
        info(f"{k} = {v}")
    return True

def _atomic_write_json(path: Path, data) -> None:
    """Write JSON atomically: write to .tmp sibling, then rename. Prevents
    half-written files when the process is killed mid-save."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    # os.replace is atomic on both POSIX and Windows for files on the same fs.
    os.replace(tmp, path)


def _save_roundtable_session(log: list, save_path=None):
    """Save the full roundtable session log to a JSON file.

    Sessions go under config.SESSIONS_DIR (~/.dulus/sessions/),
    consistent with /save and other session artifacts. Pass an explicit
    save_path to override (used to keep all turns of one debate in one file).
    """
    if not log:
        return
    if save_path is None:
        from datetime import datetime as _dt
        from config import SESSIONS_DIR
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = SESSIONS_DIR / f"round_table_{_dt.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        _atomic_write_json(save_path, log)
        ok(f"Sesión de Mesa Redonda guardada en: {save_path}")
    except Exception as e:
        warn(f"Error al guardar la sesión: {e}")

def cmd_save(args: str, state, config) -> bool:
    from config import SESSIONS_DIR
    import uuid
    sid   = uuid.uuid4().hex[:8]
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = args.strip() or f"session_{ts}_{sid}.json"
    path  = Path(fname) if "/" in fname else SESSIONS_DIR / fname
    data  = _build_session_data(state, session_id=sid)
    _atomic_write_json(path, data)
    ok(f"Session saved → {path}  (id: {sid})"  )
    return True

# Sessions shorter than this are not auto-persisted on /exit. Users who
# want a small/exploratory session saved must run `/save` explicitly.
MIN_AUTO_SAVE_TURNS = 20


def save_latest(args: str, state, config=None, mode: str = "full") -> bool:
    """Save session on exit.

    mode="full"  → session_latest.json + daily/ copy + append to history.json (REPL default)
    mode="daemon"→ only overwrite SESSIONS_DIR/session_<sid>.json, skip latest/history/daily.

    In ``full`` mode we skip persistence entirely when the session has fewer
    than ``MIN_AUTO_SAVE_TURNS`` turns — every brief session used to be saved
    as if it mattered, drowning real sessions in noise. ``/save <name>`` still
    works for short sessions the user explicitly wants to keep.
    """
    from config import DAILY_DIR, SESSION_HIST_FILE, SESSIONS_DIR
    if not state.messages:
        return True

    if mode == "full":
        turns = getattr(state, "turn_count", 0) or 0
        if turns < MIN_AUTO_SAVE_TURNS:
            info(
                f"Session not auto-saved ({turns}/{MIN_AUTO_SAVE_TURNS} turns). "
                f"Run /save to keep it."
            )
            return True

    cfg = config or {}
    import uuid
    sid = cfg.get("_session_id") or uuid.uuid4().hex[:8]
    cfg["_session_id"] = sid
    data = _build_session_data(state, session_id=sid)
    payload = json.dumps(data, indent=2, default=str)

    # ── Daemon mode: single file, no history/latest noise ──
    if mode == "daemon":
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        sess_path = SESSIONS_DIR / f"session_{sid}.json"
        sess_path.write_text(payload)
        ok(f"Session saved → {sess_path}  (id: {sid})")
        return True

    # ── Full mode (REPL exit) ──
    daily_limit   = cfg.get("session_limit_daily",   10)
    history_limit = cfg.get("session_limit_history", 200)

    now = datetime.now()
    ts  = now.strftime("%H%M%S")
    date_str = now.strftime("%Y-%m-%d")

    # 1. session_latest.json — always overwrite for quick /resume
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = SESSIONS_DIR / "session_latest.json"
    latest_path.write_text(payload)

    # 2. daily/YYYY-MM-DD/session_HHMMSS_sid.json
    day_dir = DAILY_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)

    # Delete older copies of this same session ID to prevent duplication
    for old_copy in day_dir.glob(f"session_*_{sid}.json"):
        try:
            old_copy.unlink()
        except Exception:
            pass

    daily_path = day_dir / f"session_{ts}_{sid}.json"
    daily_path.write_text(payload)

    # 3. Append to history.json (master file)
    if SESSION_HIST_FILE.exists():
        try:
            hist = json.loads(SESSION_HIST_FILE.read_text())
        except Exception:
            hist = {"total_turns": 0, "sessions": []}
    else:
        hist = {"total_turns": 0, "sessions": []}

    hist["sessions"].append(data)
    hist["total_turns"] = sum(s.get("turn_count", 0) for s in hist["sessions"])

    # Prune history: keep only the latest `history_limit` sessions
    if len(hist["sessions"]) > history_limit:
        hist["sessions"] = hist["sessions"][-history_limit:]

    SESSION_HIST_FILE.write_text(json.dumps(hist, indent=2, default=str))

    ok(f"Session saved → {latest_path}")
    ok(f"             → {daily_path}  (id: {sid})")
    ok(f"             → {SESSION_HIST_FILE}  ({len(hist['sessions'])} sessions / {hist['total_turns']} total turns)")
    return True
def cmd_load(args: str, state, config) -> bool:
    from config import SESSIONS_DIR, DAILY_DIR

    path = None
    if not args.strip():
        # Group sessions by day (newest day first). Each day shows at most
        # PER_DAY_SHOW sessions (newest first); the rest are kept in `extras`
        # and surfaced only if the user asks for that day's full list.
        PER_DAY_SHOW = 7
        days: list[tuple[str, list[Path], int]] = []  # (date_label, shown, hidden_count)
        if DAILY_DIR.exists():
            for day_dir in sorted(DAILY_DIR.iterdir(), reverse=True):
                if not day_dir.is_dir():
                    continue
                all_in_day = sorted(day_dir.glob("session_*.json"), reverse=True)
                if not all_in_day:
                    continue
                shown = all_in_day[:PER_DAY_SHOW]
                hidden = max(0, len(all_in_day) - PER_DAY_SHOW)
                days.append((day_dir.name, shown, hidden))

        if not days:
            info("No saved sessions found.")
            return True

        # ── Render menu (day-indexed, session-indexed within day) ───────
        header = clr("  Select session(s) — syntax: *<day>*<session>, comma-separated", "cyan", "bold")
        print(header)
        print(clr("  Example: *1*3        → day 1, session 3", "dim"))
        print(clr("           *1*3,*2*7   → load both, merged in that order", "dim"))
        menu_buf = header
        for di, (date_label, shown, hidden) in enumerate(days, 1):
            day_hdr = f"\n  Day {di}  ── {date_label} ──"
            print(clr(day_hdr, "yellow", "bold"))
            menu_buf += "\n" + clr(day_hdr, "yellow", "bold")
            for si, s in enumerate(shown, 1):
                label = s.name
                try:
                    meta     = json.loads(s.read_text(encoding="utf-8", errors="replace"))
                    saved_at = (meta.get("saved_at", "") or "")[-8:]
                    sid      = meta.get("session_id", "")
                    turns    = meta.get("turn_count", "?")
                    label    = f"{saved_at}  id:{sid}  turns:{turns}"
                except Exception:
                    pass
                line = "   " + clr(f"*{di}*{si}", "green") + "  " + label
                print(line)
                menu_buf += "\n" + line
            if hidden:
                hint = clr(f"        ({hidden} more in this day — open the dir to see all)", "dim")
                print(hint)
                menu_buf += "\n" + hint

        # Show history.json option at the bottom if it exists
        from config import SESSION_HIST_FILE
        has_history = SESSION_HIST_FILE.exists()
        if has_history:
            try:
                hist_meta = json.loads(SESSION_HIST_FILE.read_text())
                n_sess  = len(hist_meta.get("sessions", []))
                n_turns = hist_meta.get("total_turns", 0)
                hdr2 = clr("\n  Complete History", "dim", "bold")
                print(hdr2)
                menu_buf += "\n" + hdr2
                hist_prt = "   " + clr("H", "green") + f"     Load ALL history  ({n_sess} sessions / {n_turns} total turns)"
                print(hist_prt)
                menu_buf += "\n" + hist_prt
            except Exception:
                has_history = False

        print()
        ans = ask_input_interactive(
            clr("  > ", "cyan"),
            config,
            menu_buf,
        ).strip().lower()

        if not ans:
            info("  Cancelled.")
            return True

        if ans == "h":
            if not has_history:
                err("history.json not found.")
                return True
            hist_data = json.loads(SESSION_HIST_FILE.read_text(encoding="utf-8", errors="replace"))
            all_sessions = hist_data.get("sessions", [])
            if not all_sessions:
                info("history.json is empty.")
                return True
            all_messages = []
            for s in all_sessions:
                all_messages.extend(s.get("messages", []))
            total_turns = sum(s.get("turn_count", 0) for s in all_sessions)
            est_tokens = sum(len(str(m.get("content", ""))) for m in all_messages) // 4
            print()
            print(clr(f"  {len(all_messages)} messages / ~{est_tokens:,} tokens estimated", "dim"))
            confirm = ask_input_interactive(clr("  Load full history into current session? [y/N] > ", "yellow"), config).strip().lower()
            if confirm != "y":
                info("  Cancelled.")
                return True
            state.messages = all_messages
            state.turn_count = total_turns
            ok(f"Full history loaded from {SESSION_HIST_FILE} ({len(all_messages)} messages across {len(all_sessions)} sessions)")
            return True

        # ── Parse `*D*S` tokens, comma-separated ────────────────────────
        import re as _re
        token_re = _re.compile(r"^\*(\d+)\*(\d+)$")
        raw_parts = [p.strip() for p in ans.split(",") if p.strip()]
        picked: list[Path] = []
        seen: set = set()
        for p in raw_parts:
            m = token_re.match(p)
            if not m:
                err(f"Invalid token '{p}'. Use *day*session, e.g. *1*3 or *1*3,*2*7")
                return True
            d_i = int(m.group(1))
            s_i = int(m.group(2))
            if d_i < 1 or d_i > len(days):
                err(f"Day {d_i} out of range (valid: 1–{len(days)})")
                return True
            _label, shown, _hidden = days[d_i - 1]
            if s_i < 1 or s_i > len(shown):
                err(f"Session {s_i} out of range for day {d_i} (valid: 1–{len(shown)})")
                return True
            chosen = shown[s_i - 1]
            key = str(chosen)
            if key in seen:
                continue
            seen.add(key)
            picked.append(chosen)

        if not picked:
            info("  Cancelled.")
            return True

        if len(picked) == 1:
            path = picked[0]
        else:
            # Merge multiple sessions in pick order
            all_messages = []
            total_turns  = 0
            loaded_names = []
            for s_path in picked:
                s_data = json.loads(s_path.read_text(encoding="utf-8", errors="replace"))
                all_messages.extend(s_data.get("messages", []))
                total_turns += s_data.get("turn_count", 0)
                loaded_names.append(s_path.name)
            est_tokens = sum(len(str(m.get("content", ""))) for m in all_messages) // 4
            print()
            print(clr(f"  {len(loaded_names)} sessions / {len(all_messages)} messages / ~{est_tokens:,} tokens estimated", "dim"))
            confirm = ask_input_interactive(clr("  Merge and load? [y/N] > ", "yellow"), config).strip().lower()
            if confirm != "y":
                info("  Cancelled.")
                return True
            state.messages = all_messages
            state.turn_count = total_turns
            ok(f"Loaded {len(loaded_names)} sessions ({len(all_messages)} messages): {', '.join(loaded_names)}")
            return True

    if not path:
        fname = args.strip()
        path = Path(fname) if "/" in fname or "\\" in fname else SESSIONS_DIR / fname
        if not path.exists() and ("/" not in fname and "\\" not in fname):
            for alt in [*(d / fname for d in DAILY_DIR.iterdir()
                          if DAILY_DIR.exists() and d.is_dir())]:
                if alt.exists():
                    path = alt
                    break
        if not path.exists():
            err(f"File not found: {path}")
            return True
        
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    state.messages = data.get("messages", [])
    state.turn_count = data.get("turn_count", 0)
    state.total_input_tokens = data.get("total_input_tokens", 0)
    state.total_output_tokens = data.get("total_output_tokens", 0)
    ok(f"Session loaded from {path} ({len(state.messages)} messages)")
    return True

def cmd_resume(args: str, state, config) -> bool:
    from config import SESSIONS_DIR

    if not args.strip():
        path = SESSIONS_DIR / "session_latest.json"
        if not path.exists():
            info("No auto-saved sessions found.")
            return True
    else:
        fname = args.strip()
        path = Path(fname) if "/" in fname else SESSIONS_DIR / fname

    if not path.exists():
        err(f"File not found: {path}")
        return True

    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    state.messages = data.get("messages", [])
    state.turn_count = data.get("turn_count", 0)
    state.total_input_tokens = data.get("total_input_tokens", 0)
    state.total_output_tokens = data.get("total_output_tokens", 0)
    ok(f"Session loaded from {path} ({len(state.messages)} messages)")
    return True

def cmd_history(_args: str, state, config) -> bool:
    if not state.messages:
        info("(empty conversation)")
        return True
    for i, m in enumerate(state.messages):
        role = clr(m["role"].upper(), "bold",
                   "cyan" if m["role"] == "user" else "green")
        content = m["content"]
        if isinstance(content, str):
            print(f"[{i}] {role}: {content[:200]}")
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type", "")
                else:
                    btype = getattr(block, "type", "")
                if btype == "text":
                    text = block.get("text", "") if isinstance(block, dict) else block.text
                    print(f"[{i}] {role}: {text[:200]}")
                elif btype == "tool_use":
                    name = block.get("name", "") if isinstance(block, dict) else block.name
                    print(f"[{i}] {role}: [tool_use: {name}]")
                elif btype == "tool_result":
                    cval = block.get("content", "") if isinstance(block, dict) else block.content
                    print(f"[{i}] {role}: [tool_result: {str(cval)[:100]}]")
    return True

def cmd_context(_args: str, state, config) -> bool:
    from compaction import estimate_tokens
    # Use enhanced token estimation (includes Kimi API when available)
    est_tokens = estimate_tokens(state.messages, model=config.get("model", ""), config=config)
    info(f"Messages:         {len(state.messages)}")
    info(f"Estimated tokens: ~{est_tokens:,}")
    info(f"Model:            {config['model']}")
    info(f"Max tokens:       {config['max_tokens']:,}")
    return True

def cmd_cost(_args: str, state, config) -> bool:
    from config import calc_cost
    from compaction import estimate_tokens

    # The accumulated counters (total_input_tokens etc.) sum the provider's
    # reported "tokens in this request" which includes the ENTIRE context
    # window every turn. That creates a quadratic explosion and is useless
    # for cost estimation. Instead, estimate from the actual message list.
    est_input = estimate_tokens(state.messages, model=config.get("model", ""), config=config)
    # Output is trickier to estimate from history alone; use the accumulated
    # counter as a lower-bound fallback but cap it to something sane.
    est_output = min(state.total_output_tokens, est_input)

    cost = calc_cost(config["model"], est_input, est_output)
    info(f"Input tokens:  ~{est_input:,} (estimated from {len(state.messages)} messages)")
    info(f"Output tokens: ~{est_output:,}")
    c_read = getattr(state, "total_cache_read_tokens", 0)
    c_write = getattr(state, "total_cache_creation_tokens", 0)
    if c_read > 0 or c_write > 0:
        info(f"Cache usage:   {c_read:,} hits / {c_write:,} created")
    info(f"Est. cost:     ${cost:.4f} USD")
    return True

def cmd_verbose(_args: str, _state, config) -> bool:
    from config import save_config
    config["verbose"] = not config.get("verbose", False)
    state_str = "ON" if config["verbose"] else "OFF"
    ok(f"Verbose mode: {state_str}")
    save_config(config)
    return True

def cmd_brave(_args: str, _state, config) -> bool:
    from config import save_config
    config["brave_search_enabled"] = not config.get("brave_search_enabled", False)
    state_str = "ON" if config["brave_search_enabled"] else "OFF"
    ok(f"Brave Search: {state_str}")
    save_config(config)
    return True

def cmd_rtk(args: str, _state, config) -> bool:
    """Toggle RTK transparent shell command rewriting (token-optimized output)."""
    from config import save_config
    arg = (args or "").strip().lower()
    if arg in ("on", "true", "1"):
        config["rtk_enabled"] = True
    elif arg in ("off", "false", "0"):
        config["rtk_enabled"] = False
    else:
        config["rtk_enabled"] = not config.get("rtk_enabled", True)
    save_config(config)

    state_str = "ON" if config["rtk_enabled"] else "OFF"
    ok(f"RTK: {state_str}")

    if config["rtk_enabled"]:
        try:
            from tools import _rtk_binary
            binary = _rtk_binary()
            if binary:
                info(f"  binary: {binary}")
            else:
                import sys as _sys
                hint = "rtk.exe (bundled in dulus-stable/rtk/)" if _sys.platform == "win32" \
                    else "bash rtk/install.sh  # to fetch the binary"
                info(f"  [warn] rtk binary not found — falling back to raw commands. Hint: {hint}")
        except Exception:
            pass
    return True

def cmd_git(_args: str, _state, config) -> bool:
    from config import save_config
    config["git_status"] = not config.get("git_status", True)
    state_str = "ON" if config["git_status"] else "OFF"
    ok(f"Git status injection: {state_str}")
    save_config(config)
    return True

def cmd_daemon(args: str, _state, config) -> bool:
    from config import save_config
    args = (args or "").strip().lower()
    if args in ("on", "1", "true", "yes"):
        config["daemon"] = True
    elif args in ("off", "0", "false", "no"):
        config["daemon"] = False
    else:
        config["daemon"] = not config.get("daemon", False)
    state_str = "ON" if config["daemon"] else "OFF"
    ok(f"Daemon (external triggers): {state_str}")
    save_config(config)
    return True

def cmd_bg(args: str, _state, config) -> bool:
    """Background Dulus via tmux session.

    /bg start [--web-port PORT]  — create detached tmux session running daemon
    /bg stop                     — kill tmux session
    /bg kill                     — alias of stop
    /bg status                   — tmux session alive? IPC responding?
    /bg attach                   — attach to tmux session synchronously
    """
    import subprocess as _sp, socket as _socket, time as _time

    parts = (args or "").strip().split()
    sub = parts[0].lower() if parts else "status"
    TMUX_SESSION = "dulus"

    def _ipc_alive() -> bool:
        try:
            s = _socket.create_connection(("127.0.0.1", DULUS_IPC_PORT), timeout=0.5)
            s.close()
            return True
        except Exception:
            return False

    def _wc_port_alive(p: int) -> bool:
        import urllib.request
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{p}/api/health", timeout=0.5).read(1)
            return True
        except Exception:
            return False

    def _tmux_session_exists() -> bool:
        try:
            result = _sp.run(["tmux", "has-session", "-t", TMUX_SESSION],
                             capture_output=True, timeout=2)
            return result.returncode == 0
        except Exception:
            return False

    # ── /bg status ────────────────────────────────────────────────────────
    if sub == "status":
        tmux_alive = _tmux_session_exists()
        ipc = _ipc_alive()
        if tmux_alive and ipc:
            ok("Dulus background daemon: RUNNING")
            info(f"  IPC: 127.0.0.1:{DULUS_IPC_PORT} (responding)")
            info(f"  Web: http://127.0.0.1:{config.get('_webchat_port', 5000)}/")
        elif tmux_alive and not ipc:
            warn("tmux session exists but IPC not responding (still booting?)")
        elif ipc:
            info("No tmux session running, but IPC port is in use.")
            info(f"  Likely your own Dulus REPL on port {DULUS_IPC_PORT}.")
        else:
            info("Dulus background daemon: NOT RUNNING")
        return True

    # ── /bg stop / kill ───────────────────────────────────────────────────
    if sub in ("stop", "kill"):
        if not _tmux_session_exists():
            info("No background daemon to stop.")
            return True
        try:
            _sp.run(["tmux", "kill-session", "-t", TMUX_SESSION],
                    capture_output=True, timeout=5)
            ok("Dulus background stopped.")
        except Exception as e:
            err(f"Failed to kill tmux session: {e}")
        return True

    # ── /bg attach ────────────────────────────────────────────────────────
    if sub == "attach":
        if not _tmux_session_exists():
            warn("No background daemon running. Use `/bg start` first.")
            return True
        ok("Attaching to tmux session 'dulus' (Ctrl+B D to detach)...")
        try:
            _sp.run(["tmux", "attach", "-t", TMUX_SESSION], capture_output=False)
        except Exception as e:
            err(f"Failed to attach: {e}")
        return True

    # ── /bg start ─────────────────────────────────────────────────────────
    if sub == "start":
        if _tmux_session_exists():
            info("Background daemon already running.  Use `/bg status` for details.")
            return True

        # If this REPL owns the IPC port, release it first
        if _ipc_alive() and config.get("_ipc_thread") is not None:
            info("Releasing this REPL's IPC port so the daemon can take over...")
            config["_ipc_stop"] = True
            ipc_thread = config.get("_ipc_thread")
            try:
                ipc_thread.join(timeout=2.5)
            except Exception:
                pass
            config["_ipc_thread"] = None
            config.pop("_ipc_listening", None)
            _time.sleep(0.6)

        if _ipc_alive():
            warn(f"Port {DULUS_IPC_PORT} is in use by another process.")
            info("Run `/bg kill` first if it's a stale daemon.")
            return True

        web_port = config.get("_webchat_port", 5000)
        if _wc_port_alive(web_port):
            info(f"WebChat already running on port {web_port}.")
            info(f"  URL: http://127.0.0.1:{web_port}/")
            info("Use `/webchat stop` to stop it, or pick a different port with `--web-port`.")
            return True

        if "--web-port" in parts:
            try:
                web_port = int(parts[parts.index("--web-port") + 1])
            except (IndexError, ValueError):
                err("--web-port needs a number")
                return True
        config["_webchat_port"] = web_port
        from config import save_config
        save_config(config)

        cmd = "python dulus.py --daemon"
        try:
            result = _sp.run(["tmux", "new-session", "-d", "-s", TMUX_SESSION, cmd],
                             capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                err(f"tmux failed: {result.stderr.strip() or result.stdout.strip()}")
                return True
        except Exception as e:
            err(f"Failed to start tmux session: {e}")
            return True

        # Wait briefly for the IPC port to come up
        for _ in range(40):
            if _ipc_alive():
                break
            _time.sleep(0.25)

        ok("Dulus background started in tmux session 'dulus'.")
        info(f"  IPC: 127.0.0.1:{DULUS_IPC_PORT}")
        info(f"  Web: http://127.0.0.1:{web_port}/")
        info("  Stop with `/bg stop`.  Attach with `/bg attach`.")
        return True

    err(f"Unknown subcommand: {sub}.  Use start | stop | status | attach")
    return True


def cmd_webchat(args: str, state, config) -> bool:
    """Start the in-process webchat mirror. /webchat stop kills it."""
    import time, urllib.request, socket
    import webchat_server
    arg = (args or "").strip().lower()
    port = config.get("_webchat_port", 5000)

    def _lan_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    if arg in ("stop", "kill", "off"):
        if webchat_server.is_running():
            webchat_server.stop()
            ok(f"WebChat stopped (was on :{port})")
        else:
            info("WebChat not running")
        config.pop("_webchat_proc", None)
        return True

    # /webchat lan on|off — toggle LAN exposure (default: loopback only)
    if arg.startswith("lan"):
        from config import save_config
        sub = arg.replace("lan", "", 1).strip()
        if sub in ("on", "1", "true", "yes"):
            config["webchat_lan"] = True
        elif sub in ("off", "0", "false", "no"):
            config["webchat_lan"] = False
        else:
            info(f"WebChat LAN exposure: {'ON' if config.get('webchat_lan') else 'OFF (loopback only)'}")
            info("Use `/webchat lan on` to expose to the local network.")
            return True
        save_config(config)
        state_str = "ON — visible on the LAN" if config["webchat_lan"] else "OFF — loopback only (safe)"
        ok(f"WebChat LAN exposure: {state_str}")
        if webchat_server.is_running():
            warn("Restart with `/webchat stop` then `/webchat` to apply the new bind.")
        return True

    active_model = config.get("model", "")

    # Guard against duplicate webchat servers across processes (/bg vs /webchat)
    def _wc_port_alive(p):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{p}/api/health", timeout=0.5).read(1)
            return True
        except Exception:
            return False

    if _wc_port_alive(port):
        info(f"WebChat already running on port {port} (started by /bg or another process).")
        info(f"  URL: http://127.0.0.1:{port}/")
        lan = _lan_ip()
        if lan:
            info(f"  LAN: http://{lan}:{port}/")
        return True

    if webchat_server.is_running():
        # If model changed since last spawn, auto-restart so webchat stays synced
        last_model = config.get("_webchat_model", "")
        if last_model and last_model != active_model:
            info(f"Model changed ({last_model} -> {active_model}), restarting WebChat...")
            webchat_server.stop()
            config.pop("_webchat_proc", None)
            # fall through to respawn below
        else:
            lan = _lan_ip()
            info(f"WebChat already running -> http://127.0.0.1:{port}/" + (f"  |  LAN: http://{lan}:{port}/" if lan else ""))
            return True

    parts = arg.split()
    if parts and parts[0].isdigit():
        port = int(parts[0])

    ok(f"Starting WebChat mirror on port {port}...")
    started = webchat_server.start(state, config, port=port)
    if not started:
        info("WebChat failed to start (already running?)")
        return True

    config["_webchat_port"] = port
    config["_webchat_model"] = active_model

    local_url = f"http://127.0.0.1:{port}/"
    for _ in range(20):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(local_url, timeout=0.4).read(1)
            lan = _lan_ip()
            ok(f"WebChat listening -> {local_url}  (model: {config.get('model','?')})")
            if lan:
                ok(f"From phone (same wifi) -> http://{lan}:{port}/")
            info("Stop with: /webchat stop")
            return True
        except Exception:
            if not webchat_server.is_running():
                info("WebChat exited early")
                config.pop("_webchat_proc", None)
                return True
    info(f"WebChat spawn timed out -- try opening {local_url} manually or check :{port}")
    return True


def cmd_sandbox(args: str, state, config) -> bool:
    """Open the Dulus Sandbox OS in the browser.

    /sandbox          — Ensure webchat is running, open /sandbox in browser
    /sandbox stop     — Alias for /webchat stop
    """
    import webbrowser, time, urllib.request

    arg = (args or "").strip().lower()

    if arg in ("stop", "kill", "off"):
        return cmd_webchat("stop", state, config)

    # Make sure webchat is running first
    import webchat_server
    port = config.get("_webchat_port", 5000)

    def _wc_alive(p):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{p}/api/health", timeout=0.5).read(1)
            return True
        except Exception:
            return False

    if not _wc_alive(port):
        ok("Starting WebChat first...")
        cmd_webchat("", state, config)
        # Wait up to 5s for it to be ready
        for _ in range(20):
            if _wc_alive(port):
                break
            time.sleep(0.25)

    sandbox_url = f"http://127.0.0.1:{port}/sandbox"
    ok(f"Opening Sandbox OS -> {sandbox_url}")
    webbrowser.open(sandbox_url)
    info("Mini OS running in your browser. Use /sandbox stop to shut down the server.")
    return True

def cmd_gui(_args: str, _state, config) -> bool:
    """Launch the desktop GUI from the REPL."""
    try:
        from dulus_gui import launch_gui
        info("Launching Dulus GUI...")
        # Run GUI in a separate thread so the REPL stays alive
        import threading
        t = threading.Thread(
            target=launch_gui,
            kwargs={"config": config, "initial_prompt": None},
            daemon=True,
        )
        t.start()
        ok("GUI launched in background. Use --gui flag to run GUI-only mode.")
    except ImportError as exc:
        err(f"GUI dependencies missing: {exc}. Run: pip install customtkinter")
    return True

def cmd_max_fix(args: str, _state, config) -> bool:
    from config import save_config
    current = config.get("adapter_max_fix_attempts", 20)
    if not args.strip():
        info(f"adapter_max_fix_attempts: {current}  (fix attempts per task in autoadapter)")
        info("Usage: /max_fix <number>   e.g. /max_fix 30")
        return True
    try:
        n = int(args.strip())
        if n < 1:
            err("Value must be >= 1")
            return True
        config["adapter_max_fix_attempts"] = n
        save_config(config)
        ok(f"adapter_max_fix_attempts set to {n}")
    except ValueError:
        err(f"Invalid number: {args.strip()!r}")
    return True

def cmd_thinking(_args: str, _state, config) -> bool:
    """Set or toggle extended thinking.

    /thinking                     — toggle between OFF and the last non-zero level (default 2)
    /thinking 0|off               — disable thinking entirely
    /thinking 1|min               — minimal: low budget + "think briefly" prompt hint
    /thinking 2|med|medium        — moderate: medium budget + "think as needed" hint
    /thinking 3|max|on            — deep: high budget + "think thoroughly" hint
    /thinking 4|raw|normal|plain  — raw: medium budget, NO prompt nudges (API default behavior)
    """
    from config import save_config
    arg = (_args or "").strip().lower()

    aliases = {
        "":        None,   # toggle
        "off":     0, "0": 0,
        "min":     1, "minimal": 1, "low": 1, "1": 1,
        "med":     2, "medium":  2, "mid": 2, "2": 2,
        "max":     3, "deep":    3, "high": 3, "on": 3, "3": 3,
        "raw":     4, "normal":  4, "default": 4, "plain": 4, "4": 4,
    }
    if arg not in aliases:
        err(f"Unknown thinking argument: '{arg}'. Use: off | min | med | max | raw | 0-4")
        return True

    current = _normalize_thinking_level(config.get("thinking", 0))
    if aliases[arg] is None:
        # Toggle: if any level active → OFF; if OFF → restore last level or default to 2
        if current > 0:
            new_level = 0
        else:
            new_level = config.get("_thinking_last_level", 2) or 2
    else:
        new_level = aliases[arg]

    config["thinking"] = new_level
    if new_level > 0:
        config["_thinking_last_level"] = new_level

    labels = {0: "OFF", 1: "MIN", 2: "MED", 3: "MAX", 4: "RAW"}
    ok(f"Extended thinking: {labels[new_level]}  (level={new_level})")
    save_config(config)
    return True


def _normalize_thinking_level(value) -> int:
    """Coerce legacy bool/int/str thinking config into an int 0-4."""
    if value is True:
        return 3
    if value is False or value is None:
        return 0
    try:
        lvl = int(value)
    except (TypeError, ValueError):
        return 0
    if lvl < 0: return 0
    if lvl > 4: return 4
    return lvl

def cmd_soul(args: str, state, config) -> bool:
    """List available souls or switch the active one mid-session.

    /soul            — list souls + show active
    /soul <name>     — switch to <name> (e.g. chill, forensic) by injecting it
                       as an assistant message (same mechanism as startup load)
    """
    from memory import USER_MEMORY_DIR
    from config import save_config

    soul_paths = sorted(USER_MEMORY_DIR.glob("soul*.md"))
    souls: list[tuple[str, str, str, str]] = []
    for p in soul_paths:
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        name = p.stem
        desc = ""
        body = raw
        if raw.startswith("---"):
            end = raw.find("\n---", 3)
            if end != -1:
                fm = raw[3:end]
                body = raw[end + 4:].lstrip("\n")
                for line in fm.splitlines():
                    if line.lower().startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
        if body.strip():
            souls.append((name, str(p), desc, body))

    if not souls:
        warn("No soul files found in " + str(USER_MEMORY_DIR))
        return True

    arg = args.strip().lower()
    active = config.get("_soul_active", "")

    if not arg:
        info("Available souls:")
        for n, _p, d, _b in souls:
            marker = clr("  ← active", "green", "bold") if n == active else ""
            label = n.replace("soul_", "").replace("soul", "default") or "default"
            print(f"  - {clr(label, 'magenta', 'bold'):<20} {clr(d, 'dim')}{marker}")
        info("Switch with: /soul <name>  (e.g. /soul forensic)")
        return True

    match = None
    for s in souls:
        nlow = s[0].lower()
        if nlow == arg or nlow.endswith(f"_{arg}") or nlow == f"soul_{arg}":
            match = s
            break
    if match is None:
        err(f"No soul matches '{arg}'. Available: "
            + ", ".join(s[0].replace("soul_", "").replace("soul", "default") for s in souls))
        return True

    name, _p, desc, body = match
    state.messages.append({
        "role": "assistant",
        "content": f"[Identity Essence Reloaded: {name}]\n\n{body}",
    })
    config["_soul_active"] = name
    config["soul_default"] = name  # persist as default for next startup
    save_config(config)
    ok(f"Soul switched to: {name}" + (f" — {desc}" if desc else ""))
    return True


def cmd_schema(args: str, _state, _config) -> bool:
    """Inspect tool schemas (human-facing; model doesn't see this command).

    /schema              — list all registered tools, grouped
    /schema <tool>       — show full input_schema + description for one tool
    /schema --json <t>   — raw JSON dump of the tool's schema

    Useful for telling the agent: "use tool X with option Y that you haven't tried".
    """
    from tool_registry import get_all_tools, get_tool

    arg = args.strip()
    as_json = False
    if arg.startswith("--json"):
        as_json = True
        arg = arg[len("--json"):].strip()

    if not arg:
        tools = get_all_tools()
        if not tools:
            warn("No tools registered.")
            return True
        info(f"Registered tools ({len(tools)} total):")
        # Group by prefix convention: plugin tools often have underscore prefixes
        groups: dict[str, list] = {}
        for t in tools:
            key = "Core"
            name = t.name
            # Heuristic: tools from plugins typically prefixed plugin_<n> or plugin-like names
            sch = t.schema or {}
            if sch.get("_plugin"):
                key = sch["_plugin"]
            elif "_" in name and name.split("_", 1)[0] in {
                "memory", "tmux", "task", "plugin", "skill", "mcp", "subagent",
            }:
                key = name.split("_", 1)[0].capitalize()
            groups.setdefault(key, []).append(t)
        for key in sorted(groups):
            print(f"\n  {clr(key, 'cyan', 'bold')}  ({len(groups[key])})")
            for t in groups[key]:
                desc = (t.schema or {}).get("description", "")
                if len(desc) > 70:
                    desc = desc[:67] + "..."
                print(f"    - {clr(t.name, 'magenta'):<36} {clr(desc, 'dim')}")
        info("\nInspect one: /schema <tool_name>   |   Raw JSON: /schema --json <tool_name>")
        return True

    tool = get_tool(arg)
    if tool is None:
        # try fuzzy
        tools = get_all_tools()
        matches = [t for t in tools if arg.lower() in t.name.lower()]
        if not matches:
            err(f"No tool matches '{arg}'")
            return True
        if len(matches) > 1:
            info(f"Multiple matches for '{arg}':")
            for t in matches:
                print(f"  - {t.name}")
            return True
        tool = matches[0]

    sch = tool.schema or {}
    if as_json:
        print(json.dumps(sch, indent=2, ensure_ascii=False))
        return True

    print()
    print(clr(f"╭─ {tool.name} ", "cyan", "bold") + clr("─" * max(1, 50 - len(tool.name)), "cyan"))
    desc = sch.get("description", "(no description)")
    for line in desc.splitlines() or [""]:
        print(clr("│ ", "cyan") + line)
    flags = []
    if tool.read_only: flags.append("read_only")
    if tool.concurrent_safe: flags.append("concurrent_safe")
    if tool.display_only: flags.append("display_only")
    if flags:
        print(clr("│ ", "cyan") + clr("flags: ", "dim") + clr(", ".join(flags), "yellow"))

    input_schema = sch.get("input_schema") or sch.get("parameters") or {}
    props = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
    required = set(input_schema.get("required", []) if isinstance(input_schema, dict) else [])

    if props:
        print(clr("│", "cyan"))
        print(clr("│ Inputs:", "cyan", "bold"))
        for pname, pspec in props.items():
            if not isinstance(pspec, dict):
                continue
            ptype = pspec.get("type", "any")
            req_mark = clr("*", "red", "bold") if pname in required else " "
            pdesc = pspec.get("description", "")
            enum = pspec.get("enum")
            default = pspec.get("default")
            head = f"  {req_mark} {clr(pname, 'magenta'):<30} {clr(ptype, 'yellow')}"
            print(clr("│", "cyan") + head)
            if pdesc:
                for ln in str(pdesc).splitlines():
                    print(clr("│       ", "cyan") + clr(ln, "dim"))
            if enum:
                print(clr("│       ", "cyan") + clr(f"enum: {enum}", "dim"))
            if default is not None:
                print(clr("│       ", "cyan") + clr(f"default: {default!r}", "dim"))
        if required:
            print(clr("│", "cyan"))
            print(clr("│ ", "cyan") + clr("* = required", "red", "dim"))
    else:
        print(clr("│ (no inputs)", "cyan"))

    print(clr("╰" + "─" * 52, "cyan"))
    return True


def cmd_deep_override(_args: str, _state, config) -> bool:
    from config import save_config
    config["deep_override"] = not config.get("deep_override", False)
    state_str = "ON" if config["deep_override"] else "OFF"
    ok(f"DeepSeek override (simplified prompt): {state_str}")
    info("Requires restart to take effect" if config["deep_override"] else "DeepSeek will use full prompt on restart")
    save_config(config)
    return True

def cmd_deep_tools(_args: str, _state, config) -> bool:
    from config import save_config
    config["deep_tools"] = not config.get("deep_tools", False)
    state_str = "ON" if config["deep_tools"] else "OFF"
    ok(f"DeepSeek auto tool-wrap: {state_str}")
    info("Auto-wraps raw JSON tool calls for DeepSeek models")
    save_config(config)
    return True

def cmd_autojob(_args: str, _state, config) -> bool:
    from config import save_config
    config["autojob"] = not config.get("autojob", False)
    state_str = "ON" if config["autojob"] else "OFF"
    ok(f"Auto-job printer: {state_str}")
    if config["autojob"]:
        info("Jobs will be automatically printed to console when completed")
    else:
        info("Job notifications will show as normal")
    save_config(config)
    return True

def cmd_auto_show(_args: str, _state, config) -> bool:
    from config import save_config
    config["auto_show"] = not config.get("auto_show", True)  # Default is ON
    state_str = "ON" if config["auto_show"] else "OFF"
    ok(f"Auto-show display-only tools: {state_str}")
    if config["auto_show"]:
        info("ASCII art and visual tools will be shown automatically")
    else:
        info("Visual tools will NOT auto-display (use PrintToConsole manually)")
    save_config(config)
    return True

def cmd_schema_autoload(_args: str, _state, config) -> bool:
    """Toggle auto-injection of the full tool schema inventory at startup.

    ON  → at boot, the agent sees a system message listing every registered
          tool (name + description, grouped). Helps the model pick the right
          tool instead of reinventing via Bash. Costs ~3-5k chars per session.
    OFF → no inventory inject. The agent discovers tools as it goes.
    """
    from config import save_config
    config["schema_autoload"] = not config.get("schema_autoload", True)
    state_str = "ON" if config["schema_autoload"] else "OFF"
    ok(f"Schema autoload at startup: {state_str}  (restart Dulus to take effect)")
    save_config(config)
    return True


def cmd_mem_palace(args: str, _state, config) -> bool:
    """Toggle MemPalace per-turn memory injection.

    /mem_palace          → toggle the injection ON/OFF
    /mem_palace print    → toggle visibility: print to console what's being
                           injected to the model (debug — see klk pasa)
    /mem_palace reset    → clear the per-session dedup cache (allows already-
                           injected memories to be re-injected on next match)

    ON  → before each user turn, runs `search_memory(query=user_msg, k=3)`
          via the mempalace plugin and injects the top hits as a system
          message. Costs more tokens, but the agent gets relevant past
          context automatically.
    OFF → no auto-search. The agent can still call `search_memory` manually.
    """
    from config import save_config
    sub = args.strip().lower()
    if sub == "print":
        config["mem_palace_print"] = not config.get("mem_palace_print", False)
        state_str = "ON" if config["mem_palace_print"] else "OFF"
        ok(f"MemPalace injection-print (debug): {state_str}")
        save_config(config)
        return True
    if sub in ("reset", "clear", "forget"):
        # Clear the per-session dedup cache so memories injected earlier in
        # this conversation can be re-injected if they match a new query.
        n = len(config.get("_mp_injected_keys", set()))
        config["_mp_injected_keys"] = set()
        # also clear legacy name-based cache if present
        config.pop("_mp_injected_names", None)
        ok(f"MemPalace dedup cache cleared ({n} memories forgotten).")
        return True
    config["mem_palace"] = not config.get("mem_palace", True)
    state_str = "ON" if config["mem_palace"] else "OFF"
    ok(f"MemPalace auto-injection: {state_str}")
    save_config(config)
    return True


    return True


def cmd_harvest(_args: str, _state, config) -> bool:
    """Harvest fresh cookies from claude.ai using Playwright.

    Opens a visible Chrome window with a persistent profile.
    If already logged in, cookies are collected automatically.
    If not, log in manually then press ENTER in the terminal.
    Cookies are saved to ~/.dulus/claude_cookies.json and any
    active claude-web conversation is reset so the new cookies
    take effect immediately.
    """
    import pathlib, json as _json

    out_path = pathlib.Path.home() / ".dulus" / "claude_cookies.json"
    ok(f"Starting Playwright harvest → {out_path}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        import os
        info("Installing playwright...")
        os.system("pip install playwright")
        os.system("playwright install chromium")
        from playwright.sync_api import sync_playwright

    import os, time
    from datetime import datetime

    pw_profile = os.path.join(os.path.expanduser("~"), ".dulus", "playwright", "claude")
    os.makedirs(pw_profile, exist_ok=True)

    try:
        cookies = []
        headers_data: dict = {}
        conversation_ids: list = []
        user_agent = ""

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=pw_profile,
                    channel="chrome",
                    headless=False,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--window-size=1400,900",
                    ],
                    viewport={"width": 1400, "height": 900},
                    timeout=60000,
                )

                page = browser.pages[0] if browser.pages else browser.new_page()
                info("Navigating to claude.ai ...")
                page.goto("https://claude.ai", wait_until="networkidle")
                time.sleep(3)

                if "login" in page.url.lower() or "signin" in page.url.lower():
                    info("Login page detected. Please log in manually, then press ENTER here...")
                    input()

                page.goto("https://claude.ai/new", wait_until="networkidle")
                time.sleep(2)

                user_agent = page.evaluate("navigator.userAgent") if browser.pages else ""

                def _handle_req(req):
                    if "claude.ai/api" in req.url:
                        headers_data["url"]     = req.url
                        headers_data["headers"] = dict(req.headers)
                        if "chat_conversations" in req.url:
                            parts = req.url.split("/")
                            for i, part in enumerate(parts):
                                if part == "chat_conversations" and i + 1 < len(parts):
                                    cid = parts[i + 1].split("?")[0]
                                    if cid and len(cid) > 10:
                                        conversation_ids.append(cid)

                page.on("request", _handle_req)
                try:
                    page.click('div[contenteditable="true"]', timeout=4000)
                    time.sleep(1)
                except Exception:
                    pass

                cookies = browser.cookies()
                try:
                    browser.close()
                except BaseException:
                    pass
        except KeyboardInterrupt:
            info("Harvest interrupted — saving cookies collected so far...")
        except Exception as _e:
            if cookies:
                info(f"Browser error ({_e}) — saving cookies collected so far...")
            else:
                raise

        if not cookies:
            err("No cookies collected. Try /harvest again.")
            return True

        # ── Test cookies before overwriting the working ones ─────────────
        info("Testing new cookies before saving...")
        try:
            import requests as _rq
            _s = _rq.Session()
            for c in cookies:
                _s.cookies.set(c["name"], c["value"],
                               domain=c.get("domain", "claude.ai"),
                               path=c.get("path", "/"))
            _s.headers["User-Agent"] = user_agent or "Mozilla/5.0"
            _s.headers["anthropic-client-platform"] = "web_claude_ai"
            _s.headers["Origin"] = "https://claude.ai"
            _r = _s.get("https://claude.ai/api/organizations", timeout=10)
            if _r.status_code != 200:
                err(f"New cookies failed test ({_r.status_code}) — keeping old cookies intact.")
                return True
            info(f"Cookies valid ✓ (org check: {_r.status_code})")
        except Exception as _te:
            err(f"Cookie test error: {_te} — keeping old cookies intact.")
            return True

        data = {
            "cookies":          cookies,
            "headers":          headers_data.get("headers", {}),
            "conversation_ids": list(set(conversation_ids)),
            "harvested_at":     datetime.now().isoformat(),
            "user_agent":       user_agent,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2)

        # Reset active conversation so new cookies are used next turn
        config.pop("claude_web_conv_id", None)
        config.pop("_claude_web_org_id",  None)

        ok(f"Harvested {len(cookies)} cookies → {out_path}")
        ok("claude-web session reset — next message will use fresh cookies.")
    except Exception as e:
        err(f"Harvest failed: {e}")

    return True


def cmd_harvest_kimi(_args: str, _state, config) -> bool:
    """Harvest fresh gRPC tokens from kimi.com (Consumer) using Playwright.

    Opens a visible Chrome window and navigates to kimi.com.
    You must send a single message in the browser chat for the script
    to intercept the necessary gRPC-Web (Connect) headers and payloads.
    Data is saved to ~/.dulus/kimi_consumer.json for use by kimi-web.
    """
    import pathlib, json as _json, time, os, struct, re
    from datetime import datetime

    out_path = pathlib.Path.home() / ".dulus" / "kimi_consumer.json"
    ok(f"Starting Kimi Harvester → {out_path}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        info("Installing playwright...")
        os.system("pip install playwright")
        os.system("playwright install chromium")
        from playwright.sync_api import sync_playwright

    pw_profile = os.path.join(os.path.expanduser("~"), ".dulus", "playwright", "kimi-consumer")
    os.makedirs(pw_profile, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=pw_profile,
                channel="chrome",
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--window-size=1400,900",
                ],
                viewport={"width": 1400, "height": 900},
                timeout=60000,
            )

            page = browser.pages[0] if browser.pages else browser.new_page()
            
            intercepted_auth = {}
            last_payload = {}

            def _handle_req(request):
                if "ChatService/Chat" in request.url:
                    try:
                        raw = request.post_data_buffer
                        if raw:
                            text = raw.decode('utf-8', errors='ignore')
                            match = re.search(r'(\{.*"chat_id".*\})', text)
                            if match:
                                nonlocal last_payload
                                last_payload = _json.loads(match.group(0))
                                intercepted_auth['headers'] = dict(request.headers)
                                intercepted_auth['url'] = request.url
                                ok("¡Kimi Payload intercepted! 🎯")
                    except Exception:
                        pass

            page.on("request", _handle_req)

            info("Navigating to www.kimi.com ...")
            page.goto("https://www.kimi.com", wait_until="networkidle")
            
            warn("🚨  ACTION REQUIRED:")
            warn("  1. Make sure you are logged in.")
            warn("  2. Type and SEND a single message in the Kimi chat.")
            warn("  Waiting for interception (timeout 3 min)...")

            timeout_limit = 180
            start_t = time.time()
            while time.time() - start_t < timeout_limit:
                if 'url' in intercepted_auth:
                    break
                page.wait_for_timeout(1000)

            if 'url' not in intercepted_auth:
                err("Harvest timeout or window closed before interception.")
                browser.close()
                return True

            cookies = browser.cookies()
            browser.close()

        data = {
            "cookies":          cookies,
            "headers":          intercepted_auth.get("headers", {}),
            "url":              intercepted_auth.get("url"),
            "last_payload":     last_payload,
            "harvested_at":     datetime.now().isoformat(),
        }
        
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2)

        # Clear state so new parent_id etc are picked up
        config.pop("_kimi_web_parent_id", None)
        
        ok(f"Harvested Kimi tokens → {out_path}")
        ok("kimi-web provider updated — next message will use fresh tokens.")
    except Exception as e:
        err(f"Kimi Harvest failed: {e}")

    return True


def cmd_harvest_gemini(_args: str, _state, config) -> bool:
    """Harvest fresh session data from gemini.google.com using Playwright.

    Opens a visible Chrome window and navigates to gemini.google.com.
    You must send a single message in the browser chat for the script
    to intercept the necessary internal API headers/cookies.
    Data is saved to ~/.dulus/gemini_web.json for use by gemini-web.
    """
    import pathlib, json as _json, time, os, re
    from datetime import datetime

    out_path = pathlib.Path.home() / ".dulus" / "gemini_web.json"
    ok(f"Starting Gemini Harvester → {out_path}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        info("Installing playwright...")
        os.system("pip install playwright")
        os.system("playwright install chromium")
        from playwright.sync_api import sync_playwright

    # Reutiliza el perfil de Gemini para no loguear cada vez
    pw_profile = os.path.join(os.path.expanduser("~"), ".dulus", "playwright", "gemini-interceptor")
    os.makedirs(pw_profile, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=pw_profile,
                channel="chrome",
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-default-browser-check",
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1400, "height": 900},
                timeout=60000,
            )

            page = browser.pages[0] if browser.pages else browser.new_page()
            
            intercepted = []

            def _handle_req(request):
                # Captura cualquier POST a gemini.google.com que tenga f.req y "dulus"
                if "gemini.google.com" in request.url and request.method == "POST":
                    try:
                        pd = request.post_data or ""
                    except Exception:
                        pd = ""
                    if "f.req" in pd and "dulus" in pd.lower():
                        if not intercepted:
                            intercepted.append({
                                "url": request.url,
                                "headers": dict(request.headers),
                                "method": request.method,
                                "post_data": pd[:15000],
                            })
                            ok("¡Gemini Payload intercepted! 🎯")

            page.on("request", _handle_req)

            info("Navigating to gemini.google.com ...")
            try:
                page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass

            warn("🚨  ACTION REQUIRED:")
            warn("  1. Make sure you are logged in to Google.")
            warn('  2. Type and SEND the exact word  DULUS  in the Gemini chat.')
            warn("  Waiting for interception (timeout 3 min)...")

            timeout_limit = 180
            start_t = time.time()
            while time.time() - start_t < timeout_limit:
                if intercepted:
                    break
                page.wait_for_timeout(1000)

            if not intercepted:
                err("No se interceptaron requests. Asegúrate de haber enviado 'DULUS'.")
                browser.close()
                return True

            # Extraemos SNlM0e (token de seguridad de Google)
            snlm0e = None
            try:
                # Use a small timeout for SNlM0e capture to avoid hangs
                snlm0e = page.evaluate("window.WIZ_global_data?.SNlM0e")
                if not snlm0e:
                    # Fallback: check HTML without full content dump if possible
                    # but simple re.search on page.content() is usually okay
                    match = re.search(r'"SNlM0e":"(.*?)"', page.content())
                    if match:
                        snlm0e = match.group(1)
                
                if snlm0e:
                    ok(f"¡SNlM0e captured! 🔑 ({snlm0e[:10]}...)")
                else:
                    warn("Could not capture SNlM0e. Some requests might fail.")
            except Exception as e:
                warn(f"SNlM0e capture failed/timed out: {e}")

            cookies = browser.cookies()
            try:
                browser.close()
            except Exception as e:
                warn(f"browser.close failed: {e}")

        data = {
            "cookies":          cookies,
            "snlm0e":           snlm0e,
            "intercepted_requests": intercepted[-5:],
            "harvested_at":     datetime.now().isoformat(),
        }
        
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2)

        # Try to extract conversation IDs from the intercepted request to sync immediately
        try:
            import urllib.parse
            last_pd = intercepted[-1].get("post_data", "")
            if last_pd:
                pd_parsed = urllib.parse.parse_qs(last_pd)
                if "f.req" in pd_parsed:
                    # f.req = [[["otAQ7b", "<inner_json_str>", null, "generic"]]]
                    f_req_outer = _json.loads(pd_parsed["f.req"][0])
                    inner_str = f_req_outer[0][0][1]  # the inner JSON string
                    inner = _json.loads(inner_str)
                    # inner = [message, null, null, [], ..., [[c_id, r_id, rc_id]]]
                    # IDs are in the last non-null list element
                    ids_list = None
                    for part in reversed(inner):
                        if isinstance(part, list) and part:
                            ids_list = part
                            break
                    if ids_list and isinstance(ids_list[0], list) and len(ids_list[0]) >= 2:
                        c = ids_list[0][0]
                        r = ids_list[0][1]
                        rc = ids_list[0][2] if len(ids_list[0]) > 2 else ""
                        if c: config["gemini_web_c_id"] = c
                        if r: config["gemini_web_r_id"] = r
                        if rc: config["gemini_web_rc_id"] = rc
                        from config import save_config
                        save_config(config)
                        ok(f"¡Active Gemini session synced! → {config.get('gemini_web_c_id','?')[:10]}...")
        except Exception:
            pass

        ok(f"Harvested Gemini tokens → {out_path}")
        ok("gemini-web provider updated — next message will use the selected chat.")
    except Exception as e:
        return True


def cmd_harvest_deepseek(_args: str, _state, config) -> bool:
    """Harvest fresh session data from chat.deepseek.com using Playwright.

    Opens a visible Chrome window and navigates to chat.deepseek.com.
    The script intercepts the Authorization Bearer token and cookies
    automatically on the first chat response.
    Data is saved to ~/.dulus/deepseek_web.json for use by deepseek-web.

    Usage:
        /harvest-deepseek
        /harvest-deepseek https://chat.deepseek.com/a/chat/s/<session_id>
    """
    import pathlib, json as _json, time, os
    from datetime import datetime

    out_path = pathlib.Path.home() / ".dulus" / "deepseek_web.json"
    ok(f"Starting DeepSeek Harvester → {out_path}")

    # Optional: navigate directly to a specific chat session from arg
    start_url = _args.strip() if _args.strip().startswith("http") else "https://chat.deepseek.com/"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        info("Installing playwright...")
        os.system("pip install playwright")
        os.system("playwright install chromium")
        from playwright.sync_api import sync_playwright

    pw_profile = os.path.join(os.path.expanduser("~"), ".dulus", "playwright", "deepseek-interceptor")
    os.makedirs(pw_profile, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=pw_profile,
                channel="chrome",
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1400, "height": 900},
                timeout=60000,
            )

            page = browser.pages[0] if browser.pages else browser.new_page()

            captured_token = [None]
            captured_model = [None]
            captured_session_id = [None]
            captured_headers = [{}]

            def _handle_req(request):
                """Intercept DeepSeek completion requests to grab Bearer token."""
                url = request.url
                if "chat.deepseek.com" in url and "/chat/completion" in url and request.method == "POST":
                    try:
                        hdrs = dict(request.headers)
                        auth = hdrs.get("authorization", "")
                        if auth and not captured_token[0]:
                            captured_token[0] = auth.replace("Bearer ", "").strip()
                            captured_headers[0] = hdrs
                            ok(f"Bearer token captured! 🔑 ({captured_token[0][:20]}...)")
                        # Try to grab model and session_id from body
                        try:
                            body = request.post_data
                            if body:
                                body_json = _json.loads(body)
                                if not captured_model[0]:
                                    captured_model[0] = body_json.get("model", "deepseek_v3")
                                if not captured_session_id[0]:
                                    captured_session_id[0] = body_json.get("chat_session_id")
                        except Exception:
                            pass
                    except Exception:
                        pass

            page.on("request", _handle_req)

            info(f"Navigating to {start_url} ...")
            try:
                page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass

            warn("🚨  ACTION REQUIRED:")
            warn("  1. Make sure you are logged in to DeepSeek.")
            warn("  2. Send ANY message in the chat.")
            warn("  Waiting for token interception (timeout 3 min)...")

            timeout_limit = 180
            start_t = time.time()
            while time.time() - start_t < timeout_limit:
                if captured_token[0]:
                    break
                page.wait_for_timeout(1000)

            if not captured_token[0]:
                err("No token intercepted. Make sure you sent a message and are logged in.")
                browser.close()
                return True

            cookies = browser.cookies()
            try:
                browser.close()
            except Exception:
                pass

        # Extract session ID from URL if not captured from request body
        if not captured_session_id[0] and "/s/" in start_url:
            captured_session_id[0] = start_url.split("/s/")[-1].split("?")[0].strip()

        data = {
            "token":            captured_token[0],
            "model":            captured_model[0] or "deepseek_v3",
            "chat_session_id":  captured_session_id[0],
            "cookies":          cookies,
            "headers":          {
                k: v for k, v in captured_headers[0].items()
                if k.lower() not in ("authorization", "content-length", "accept-encoding")
            },
            "url":              "https://chat.deepseek.com/api/v0/chat/completion",
            "harvested_at":     datetime.now().isoformat(),
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2)

        # Sync session ID into config for continuity
        if captured_session_id[0]:
            config["deepseek_web_session_id"] = captured_session_id[0]
            from config import save_config
            save_config(config)
            ok(f"Session synced → {captured_session_id[0]}")

        ok(f"Harvested DeepSeek tokens → {out_path}")
        ok("deepseek-web provider ready — use model: deepseek-web/deepseek-v3 or deepseek-web/deepseek-r1")

    except Exception as e:
        err(f"Harvest failed: {e}")

    return True


def cmd_harvest_qwen(_args: str, _state, config) -> bool:
    """Harvest fresh session data from chat.qwen.ai using Playwright.

    Opens a visible Chrome window and navigates to chat.qwen.ai. The
    script intercepts the JWT `token` cookie and POST headers/cookies the
    first time you send a message in the chat. Data is saved to
    ~/.dulus/qwen_web.json for the qwen-web provider.

    Usage:
        /harvest-qwen
        /harvest-qwen https://chat.qwen.ai/c/<chat_id>
    """
    import pathlib, json as _json, time, os
    from datetime import datetime

    out_path = pathlib.Path.home() / ".dulus" / "qwen_web.json"
    ok(f"Starting Qwen Harvester → {out_path}")

    start_url = _args.strip() if _args.strip().startswith("http") else "https://chat.qwen.ai/"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        info("Installing playwright...")
        os.system("pip install playwright")
        os.system("playwright install chromium")
        from playwright.sync_api import sync_playwright

    pw_profile = os.path.join(os.path.expanduser("~"), ".dulus", "playwright", "qwen-interceptor")
    os.makedirs(pw_profile, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=pw_profile,
                channel="chrome",
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1400, "height": 900},
                timeout=60000,
            )

            page = browser.pages[0] if browser.pages else browser.new_page()

            captured_token = [None]
            captured_model = [None]
            captured_chat_id = [None]
            captured_parent_id = [None]
            captured_headers = [{}]

            def _handle_req(request):
                """Intercept Qwen completion requests to grab JWT and metadata."""
                url = request.url
                if "chat.qwen.ai" in url and "/chat/completions" in url and request.method == "POST":
                    try:
                        hdrs = dict(request.headers)
                        if not captured_headers[0]:
                            captured_headers[0] = hdrs
                        try:
                            body = request.post_data
                            if body:
                                body_json = _json.loads(body)
                                if not captured_model[0]:
                                    captured_model[0] = body_json.get("model", "qwen3.6-plus")
                                if not captured_chat_id[0]:
                                    captured_chat_id[0] = body_json.get("chat_id")
                                if not captured_parent_id[0]:
                                    captured_parent_id[0] = body_json.get("parent_id")
                        except Exception:
                            pass
                    except Exception:
                        pass

            page.on("request", _handle_req)

            info(f"Navigating to {start_url} ...")
            try:
                page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass

            warn("🚨  ACTION REQUIRED:")
            warn("  1. Make sure you are logged in to Qwen.")
            warn("  2. Send ANY message in the chat.")
            warn("  Waiting for token interception (timeout 3 min)...")

            timeout_limit = 180
            start_t = time.time()
            while time.time() - start_t < timeout_limit:
                # Pull the JWT cookie as soon as it's set
                if not captured_token[0]:
                    for c in browser.cookies():
                        if c.get("name") == "token" and c.get("value"):
                            captured_token[0] = c["value"]
                            ok(f"JWT token captured! 🔑 ({captured_token[0][:20]}...)")
                            break
                # We also need at least one POST to grab chat_id
                if captured_token[0] and captured_chat_id[0]:
                    break
                page.wait_for_timeout(1000)

            if not captured_token[0]:
                err("No token cookie found. Make sure you are logged in to Qwen.")
                browser.close()
                return True

            cookies = browser.cookies()
            try:
                browser.close()
            except Exception:
                pass

        # Fallback: extract chat_id from URL
        if not captured_chat_id[0] and "/c/" in start_url:
            captured_chat_id[0] = start_url.split("/c/")[-1].split("?")[0].strip()

        data = {
            "token":      captured_token[0],
            "model":      captured_model[0] or "qwen3.6-plus",
            "chat_id":    captured_chat_id[0],
            "parent_id":  captured_parent_id[0],
            "cookies":    cookies,
            "headers":    {
                k: v for k, v in captured_headers[0].items()
                if k.lower() not in ("content-length", "accept-encoding", "cookie")
            },
            "url":        "https://chat.qwen.ai/api/v2/chat/completions",
            "harvested_at": datetime.now().isoformat(),
        }

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2)

        if captured_chat_id[0]:
            config["qwen_web_chat_id"] = captured_chat_id[0]
        if captured_parent_id[0]:
            config["qwen_web_parent_id"] = captured_parent_id[0]
        from config import save_config
        save_config(config)

        ok(f"Harvested Qwen session → {out_path}")
        ok("qwen-web provider ready — use model: qwen-web/qwen3.6-plus (or qwen-max, qwen-turbo, qwen-plus)")

    except Exception as e:
        err(f"Harvest failed: {e}")

    return True


def cmd_gemini_chats(args: str, _state, config) -> bool:
    """Manage Gemini Web conversations.
    
    /gemini_chats         — show current conversation IDs
    /gemini_chats new     — start a fresh conversation
    """
    from config import save_config
    arg = args.strip().lower()
    if arg == "new":
        config.pop("gemini_web_c_id", None)
        config.pop("gemini_web_r_id", None)
        config.pop("gemini_web_rc_id", None)
        save_config(config)
        ok("Gemini context cleared. Next message will start a new chat.")
        return True
    
    c_id = config.get("gemini_web_c_id") or "—"
    r_id = config.get("gemini_web_r_id") or "—"
    rc_id = config.get("gemini_web_rc_id") or "—"
    
    print(clr("\n  Gemini Web Session info:", "cyan", "bold"))
    print(f"  Conversation ID: {clr(c_id, 'yellow')}")
    print(f"  Response ID:     {clr(r_id, 'dim')}")
    print(f"  Candidate ID:    {clr(rc_id, 'dim')}")
    print()
    info("Use '/gemini_chats new' to start a fresh thread.")
    return True


def cmd_kimi_chats(args: str, _state, config) -> bool:
    """List and select Kimi.com chats.

    /kimi_chats            — show last 20 chats (numbered)
    /kimi_chats all        — show up to 200 chats
    /kimi_chats use <N>    — switch to chat #N from the list
    /kimi_chats use <id>   — switch to chat by id prefix
    /kimi_chats new        — clear current chat (next message creates a new one)
    """
    import pathlib
    import json as _json
    from providers import _kimi_web_auth_path, _kimi_web_list_chats
    from config import save_config

    a = args.strip()

    apath = pathlib.Path(_kimi_web_auth_path(config))

    def _persist_kimi_chat(chat_id: str | None):
        """Sync chat_id (and clear parent_id) into both config AND kimi_consumer.json.

        Required because stream_kimi_web reads the harvested last_payload.chat_id
        as a fallback and the parent_id only re-uses config when chat_ids match.
        Leaving them out of sync causes the next stream to inherit a stale
        parent_id from the OLD chat and break threading.
        """
        if chat_id:
            config["kimi_web_chat_id"] = chat_id
        else:
            config.pop("kimi_web_chat_id", None)
        config.pop("kimi_web_parent_id", None)
        save_config(config)

        try:
            if apath.exists():
                with open(apath, encoding="utf-8") as fh:
                    blob = _json.load(fh)
                lp = blob.setdefault("last_payload", {})
                lp["chat_id"] = chat_id or ""
                msg = lp.setdefault("message", {})
                msg["parent_id"] = ""
                # Reset blocks too so harvested user-text doesn't leak in
                msg["blocks"] = [{"message_id": "", "text": {"content": ""}}]
                with open(apath, "w", encoding="utf-8") as fh:
                    _json.dump(blob, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            err(f"Warning: could not update {apath.name}: {exc}")

    # /kimi_chats new — reset to a fresh chat
    if a.lower() == "new":
        _persist_kimi_chat(None)
        ok("Kimi-web will create a new chat on the next message.")
        return True

    if not apath.exists():
        err(f"No Kimi auth file at {apath}. Run /harvest first.")
        return True

    with open(apath, encoding="utf-8") as f:
        auth_data = _json.load(f)

    # Pagination — kimi gives a page_token; we fetch up to 200 in "all" mode.
    limit = 200 if a.lower() == "all" else 20
    chats = []
    page_token = ""
    try:
        while len(chats) < limit:
            data = _kimi_web_list_chats(auth_data, page_size=min(50, limit - len(chats)),
                                        page_token=page_token)
            batch = data.get("chats") or data.get("items") or []
            if not batch:
                break
            chats.extend(batch)
            page_token = data.get("next_page_token") or data.get("nextPageToken") or ""
            if not page_token:
                break
    except Exception as e:
        err(f"Failed to fetch chats: {e}. Cookies may be expired — run /harvest.")
        return True

    if not chats:
        info("No chats found.")
        return True

    # /kimi_chats use <N or id-prefix>
    if a.lower().startswith("use "):
        selector = a[4:].strip()
        chosen = None
        if selector.isdigit():
            idx = int(selector) - 1
            if 0 <= idx < len(chats):
                chosen = chats[idx]
            else:
                err(f"No chat #{selector} in list (only {len(chats)} shown).")
                return True
        else:
            for c in chats:
                cid = c.get("id") or c.get("chat_id") or ""
                if cid.startswith(selector):
                    chosen = c
                    break
            if not chosen:
                err(f"No chat matching '{selector}'.")
                return True

        chat_id = chosen.get("id") or chosen.get("chat_id") or ""
        name = chosen.get("name") or chosen.get("title") or "(untitled)"
        _persist_kimi_chat(chat_id)
        ok(f"Switched to: {clr(name, 'cyan')}  {clr(chat_id[:12], 'yellow')}")
        return True

    # Default: list chats
    current = config.get("kimi_web_chat_id", "")
    print(clr(f"\n  Kimi.com Chats ({len(chats)} shown):", "cyan", "bold"))
    print(clr("  " + "-" * 70, "dim"))
    for i, c in enumerate(chats, 1):
        cid     = c.get("id") or c.get("chat_id") or ""
        name    = c.get("name") or c.get("title") or "(untitled)"
        updated = (c.get("updateTime") or c.get("createTime")
                   or c.get("updated_at") or c.get("created_at") or "")[:16]
        if len(name) > 52:
            name = name[:49] + "..."
        active = clr(" ◀", "green", "bold") if current and cid.startswith(current[:8]) else ""
        num = clr(f"{i:>3}.", "dim")
        print(f"  {num} {clr(cid[:12], 'yellow')}  {name}  {clr(updated, 'dim')}{active}")
    print(clr("  " + "-" * 70, "dim"))
    cur_display = current[:12] if current else "none (will create new)"
    info(f"Current: {cur_display}  |  Switch: /kimi_chats use <#>  |  New: /kimi_chats new")

    return True


def cmd_claude_chats(args: str, _state, config) -> bool:
    """List and select Claude.ai conversations.

    /claude_chats            — show last 20 conversations (numbered)
    /claude_chats all        — show all conversations
    /claude_chats use <N>    — switch to conversation #N from the list
    /claude_chats use <uuid> — switch to conversation by UUID prefix
    /claude_chats new        — clear current conv (next message creates a new one)
    """
    import pathlib, json as _json, urllib.request, urllib.error
    from providers import (
        _claude_web_cookies_path, _claude_web_org_id, _claude_web_headers,
    )
    from config import save_config

    a = args.strip()

    # /claude_chats new — reset to a fresh conversation
    if a.lower() == "new":
        config.pop("claude_web_conv_id", None)
        save_config(config)
        ok("Claude-web will create a new conversation on the next message.")
        return True

    cpath = pathlib.Path(_claude_web_cookies_path(config))
    if not cpath.exists():
        err(f"No cookies file found at {cpath}. Run /harvest first.")
        return True

    with open(cpath, encoding="utf-8") as f:
        cookies_data = _json.load(f)

    org_id = _claude_web_org_id(cookies_data, config)
    if not org_id:
        err("Could not determine org ID. Run /harvest.")
        return True

    limit = 9999 if a.lower() == "all" else 20
    url = f"https://claude.ai/api/organizations/{org_id}/chat_conversations?limit={limit}"
    headers = _claude_web_headers(cookies_data)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            convos = _json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err(f"HTTP {e.code} fetching conversations. Cookies may be expired — run /harvest.")
        return True
    except Exception as e:
        err(f"Failed to fetch conversations: {e}")
        return True

    if not convos:
        info("No conversations found.")
        return True

    # /claude_chats use <N or uuid>
    if a.lower().startswith("use "):
        selector = a[4:].strip()
        chosen = None
        if selector.isdigit():
            idx = int(selector) - 1
            if 0 <= idx < len(convos):
                chosen = convos[idx]
            else:
                err(f"No conversation #{selector} in list (only {len(convos)} shown).")
                return True
        else:
            # Match by UUID prefix
            for c in convos:
                if c.get("uuid", "").startswith(selector):
                    chosen = c
                    break
            if not chosen:
                err(f"No conversation matching '{selector}'.")
                return True

        full_uuid = chosen.get("uuid", "")
        name = chosen.get("name") or chosen.get("title") or "(untitled)"
        config["claude_web_conv_id"] = full_uuid
        save_config(config)
        ok(f"Switched to: {clr(name, 'cyan')}  {clr(full_uuid[:12], 'yellow')}")
        return True

    # Default: list conversations
    current = config.get("claude_web_conv_id", "")
    print(clr(f"\n  Claude.ai Conversations ({len(convos)} shown):", "cyan", "bold"))
    print(clr("  " + "-" * 70, "dim"))
    for i, c in enumerate(convos, 1):
        cid   = c.get("uuid", "")
        name  = c.get("name") or c.get("title") or "(untitled)"
        model = c.get("model", "")
        updated = (c.get("updated_at") or c.get("created_at") or "")[:16]
        if len(name) > 52:
            name = name[:49] + "..."
        model_tag = f" [{model}]" if model else ""
        active = clr(" ◀", "green", "bold") if current and cid.startswith(current[:8]) else ""
        num = clr(f"{i:>3}.", "dim")
        print(f"  {num} {clr(cid[:12], 'yellow')}  {name}  {clr(updated, 'dim')}{clr(model_tag, 'dim')}{active}")
    print(clr("  " + "-" * 70, "dim"))
    cur_display = current[:12] if current else "none (will create new)"
    info(f"Current: {cur_display}  |  Switch: /claude_chats use <#>  |  New: /claude_chats new")

    return True


def cmd_hide_sender(_args: str, _state, config) -> bool:
    """Toggle echoing your typed message above the sticky input bar.

    ON  → message disappears on send; output area shows only Dulus's responses
          (use /history to recall what you typed).
    OFF → your message stays visible above as `» <msg>`.
    """
    from config import save_config
    config["hide_sender"] = not config.get("hide_sender", True)
    state_str = "ON" if config["hide_sender"] else "OFF"
    ok(f"Hide sender: {state_str}")
    save_config(config)
    try:
        import input as dulus_input
        if hasattr(dulus_input, "set_hide_sender"):
            dulus_input.set_hide_sender(config["hide_sender"])
    except Exception:
        pass
    return True


def cmd_history(args: str, state, _config) -> bool:
    """Show previous user messages from this session.

    /history          → last 20 user messages
    /history N        → last N user messages
    /history all      → all user messages
    """
    msgs = [m for m in (state.messages or []) if m.get("role") == "user"]
    if not msgs:
        info("No user messages in this session yet.")
        return True
    arg = (args or "").strip().lower()
    if arg == "all":
        slice_ = msgs
    else:
        try:
            n = int(arg) if arg else 20
        except ValueError:
            n = 20
        slice_ = msgs[-n:]
    total = len(msgs)
    start = total - len(slice_) + 1
    print(clr(f"  ── History ({len(slice_)}/{total} user messages) ──", "cyan", "bold"))
    for i, m in enumerate(slice_, start=start):
        body = m.get("content", "")
        if isinstance(body, list):
            body = " ".join(p.get("text", "") for p in body if isinstance(p, dict))
        body = str(body).strip().replace("\n", " ")
        if len(body) > 200:
            body = body[:197] + "..."
        print(clr(f"  [{i}] ", "dim") + body)
    return True


def cmd_sticky_input(_args: str, _state, config) -> bool:
    """Toggle the prompt_toolkit anchored input bar.

    ON  → input line stays pinned at the bottom; background notifications
          flow above it (can jitter on Windows consoles).
    OFF → plain input() — native terminal behavior, zero redraws.
          Background notifications land where they land.
    """
    from config import save_config
    config["sticky_input"] = not config.get("sticky_input", True)
    state_str = "ON" if config["sticky_input"] else "OFF"
    ok(f"Sticky input bar: {state_str}  (restart Dulus to take effect)")
    save_config(config)
    return True


def cmd_theme(args: str, _state, config) -> bool:
    """Switch the Dulus color palette. `/theme` lists, `/theme <name>` applies."""
    from config import save_config
    import common as _cm
    name = (args or "").strip().lower()
    if not name:
        current = config.get("theme", "dulus")
        print(clr("  ── Available themes ──", "cyan", "bold"))
        _RESET = "\033[0m"
        for t, p in _cm.THEMES.items():
            marker = "●" if t == current else " "
            if p.get("disable_color"):
                swatch = "  (no color)  "
            else:
                fb = p.get("accent", "#FFFFFF")
                swatch = (
                    f"{_cm._rgb(p.get('accent', fb))} info {_RESET}"
                    f"{_cm._rgb(p.get('ok', fb))} ok {_RESET}"
                    f"{_cm._rgb(p.get('warn', fb))} warn {_RESET}"
                    f"{_cm._rgb(p.get('err', '#FF5555'))} err {_RESET}"
                )
            print(f"  {marker} {t:<14} {swatch}  ({p['code']})")
        print(clr(f"  Use: /theme <name>   (current: {current})", "dim"))
        return True
    if not _cm.apply_theme(name):
        err(f"Unknown theme '{name}'. Run /theme for the list.")
        return True
    config["theme"] = name
    save_config(config)
    # Clear screen and reprint banner with new theme colors
    try:
        import sys
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass
    _print_dulus_banner(config)
    return True


def cmd_ultra_search(_args: str, _state, config) -> bool:
    from config import save_config
    current = config.get("ULTRA_SEARCH") in (1, "1", True, "true")
    config["ULTRA_SEARCH"] = 1 if not current else 0
    state_str = "ON" if config["ULTRA_SEARCH"] else "OFF"
    ok(f"ULTRA_SEARCH mode: {state_str}")
    save_config(config)
    return True

def cmd_permissions(args: str, _state, config) -> bool:
    from config import save_config
    modes = ["auto", "accept-all", "manual"]
    mode_desc = {
        "auto":       "Prompt for each tool call (default)",
        "accept-all": "Allow all tool calls silently",
        "manual":     "Prompt for each tool call (strict)",
    }
    if not args.strip():
        current = config.get("permission_mode", "auto")
        menu_buf = clr("\n  ── Permission Mode ──", "dim")
        for i, m in enumerate(modes):
            marker = clr("●", "green") if m == current else clr("○", "dim")
            menu_buf += f"\n  {marker} {clr(f'[{i+1}]', 'yellow')} {clr(m, 'cyan')}  {clr(mode_desc[m], 'dim')}"
        print(menu_buf)
        print()
        try:
            ans = ask_input_interactive(clr("  Select a mode number or Enter to cancel > ", "cyan"), config, menu_buf).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return True
        if not ans:
            return True
        if ans.isdigit() and 1 <= int(ans) <= len(modes):
            m = modes[int(ans) - 1]
            config["permission_mode"] = m
            save_config(config)
            ok(f"Permission mode set to: {m}")
        else:
            err(f"Invalid selection.")
    else:
        m = args.strip()
        if m not in modes:
            err(f"Unknown mode: {m}. Choose: {', '.join(modes)}")
        else:
            config["permission_mode"] = m
            save_config(config)
            ok(f"Permission mode set to: {m}")
    return True

def _import_dulus_module(mod_name: str):
    """Import a module from the dulus_tools/ package, handling dulus.py name shadow."""
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent
    mod_path = root / "dulus_tools" / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(f"dulus_{mod_name}", mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"dulus_{mod_name}"] = mod
    spec.loader.exec_module(mod)
    return mod


def cmd_afk(_args: str, _state, config) -> bool:
    """Toggle AFK mode - auto-dismiss AskUserQuestion and auto-approve tool calls."""
    from config import save_config
    afk_mod = _import_dulus_module("afk_mode")
    afk = afk_mod.AFKMode()
    afk._enabled = config.get("afk_mode", False)
    new_state = afk.toggle()
    config["afk_mode"] = new_state
    save_config(config)
    status = clr("ENABLED", "green", "bold") if new_state else clr("DISABLED", "red", "bold")
    ok(f"AFK mode {status}")
    if new_state:
        info("  AskUserQuestion will be auto-dismissed, tool calls auto-approved.")
    return True


def cmd_yolo(_args: str, _state, config) -> bool:
    """Toggle YOLO mode - auto-approve ALL actions without prompts."""
    from config import save_config
    yolo_mod = _import_dulus_module("yolo_mode")
    yolo = yolo_mod.YOLOMode()
    yolo._enabled = config.get("yolo_mode", False)
    new_state = yolo.toggle()
    config["yolo_mode"] = new_state
    save_config(config)
    status = clr("ENABLED", "green", "bold") if new_state else clr("DISABLED", "red", "bold")
    ok(f"YOLO mode {status}")
    if new_state:
        warn("  ALL actions will be approved without prompts. Use with caution!")
    return True


def cmd_cwd(args: str, _state, config) -> bool:
    if not args.strip():
        info(f"Working directory: {os.getcwd()}")
    else:
        p = args.strip()
        try:
            os.chdir(p)
            ok(f"Changed directory to: {os.getcwd()}")
            # Directory changed — git info is stale
            if _git_prompt is not None:
                _git_prompt.reset_git_cache()
        except Exception as e:
            err(str(e))
    return True

def _build_session_data(state, session_id: str | None = None) -> dict:
    """Serialize current conversation state to a JSON-serializable dict."""
    import uuid
    return {
        "session_id": session_id or uuid.uuid4().hex[:8],
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": [
            m if not isinstance(m.get("content"), list) else
            {**m, "content": [
                b if isinstance(b, dict) else b.model_dump()
                for b in m["content"]
            ]}
            for m in state.messages
        ],
        "turn_count": state.turn_count,
        "total_input_tokens": state.total_input_tokens,
        "total_output_tokens": state.total_output_tokens,
    }


def cmd_cloudsave(args: str, state, config) -> bool:
    """Sync sessions to GitHub Gist.

    /cloudsave setup <token>   — configure GitHub Personal Access Token
    /cloudsave                 — upload current session to Gist
    /cloudsave push [desc]     — same as above with optional description
    /cloudsave auto on|off     — toggle auto-upload on /exit
    /cloudsave list            — list your dulus Gists
    /cloudsave load <gist_id>  — download and load a session from Gist
    """
    from cloudsave import validate_token, upload_session, list_sessions, download_session
    from config import save_config

    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    token = config.get("gist_token", "")

    # ── setup ──────────────────────────────────────────────────────────────────
    if sub == "setup":
        if not rest:
            err("Usage: /cloudsave setup <GitHub_Personal_Access_Token>")
            return True
        new_token = rest.strip()
        info("Validating token…")
        valid, msg = validate_token(new_token)
        if not valid:
            err(msg)
            return True
        config["gist_token"] = new_token
        save_config(config)
        ok(f"GitHub token saved (logged in as: {msg}). Cloud sync is ready.")
        return True

    # ── auto on/off ────────────────────────────────────────────────────────────
    if sub == "auto":
        flag = rest.strip().lower()
        if flag == "on":
            config["cloudsave_auto"] = True
            save_config(config)
            ok("Auto cloud-sync ON — session will be uploaded to Gist on /exit.")
        elif flag == "off":
            config["cloudsave_auto"] = False
            save_config(config)
            ok("Auto cloud-sync OFF.")
        else:
            status = "ON" if config.get("cloudsave_auto") else "OFF"
            info(f"Auto cloud-sync is currently {status}. Use 'on' or 'off' to toggle.")
        return True

    # ── remaining subcommands require a token ─────────────────────────────────
    if not token:
        err("No GitHub token configured. Run: /cloudsave setup <token>")
        info("Get a token at https://github.com/settings/tokens (needs 'gist' scope)")
        return True

    # ── list ───────────────────────────────────────────────────────────────────
    if sub == "list":
        info("Fetching your dulus sessions from GitHub Gist…")
        sessions, err_msg = list_sessions(token)
        if err_msg:
            err(err_msg)
            return True
        if not sessions:
            info("No sessions found. Upload one with /cloudsave")
            return True
        info(f"Found {len(sessions)} session(s):")
        for s in sessions:
            ts = s["updated_at"][:16].replace("T", " ")
            desc = s["description"].replace("[dulus]", "").strip()
            print(f"  {clr(s['id'][:8], 'yellow')}…  {clr(ts, 'dim')}  {desc or s['files'][0]}")
        return True

    # ── load ───────────────────────────────────────────────────────────────────
    if sub == "load":
        gist_id = rest.strip()
        if not gist_id:
            err("Usage: /cloudsave load <gist_id>")
            return True
        info(f"Downloading session {gist_id[:8]}… from Gist…")
        data, err_msg = download_session(token, gist_id)
        if err_msg:
            err(err_msg)
            return True
        state.messages = data.get("messages", [])
        state.turn_count = data.get("turn_count", 0)
        state.total_input_tokens = data.get("total_input_tokens", 0)
        state.total_output_tokens = data.get("total_output_tokens", 0)
        ok(f"Session loaded from Gist ({len(state.messages)} messages).")
        return True

    # ── push (default when no subcommand or sub == "push") ────────────────────
    if sub in ("", "push"):
        description = rest.strip() if sub == "push" else ""
        if not state.messages:
            info("Nothing to save — conversation is empty.")
            return True
        info("Uploading session to GitHub Gist…")
        session_data = _build_session_data(state)
        existing_id = config.get("cloudsave_last_gist_id")
        gist_id, err_msg = upload_session(session_data, token, description, existing_id)
        if err_msg:
            err(f"Upload failed: {err_msg}")
            return True
        config["cloudsave_last_gist_id"] = gist_id
        save_config(config)
        ok(f"Session uploaded → https://gist.github.com/{gist_id}")
        return True

    err(f"Unknown subcommand '{sub}'. Run /help for usage.")
    return True


def cmd_exit(_args: str, _state, config) -> bool:
    # ── Sleep Trigger: Ask to consolidate before exit ──────────────────
    try:
        if _state.messages and _state.turn_count > 1:
            print(
                clr("\n  [Dulus is still awake] ", "cyan")
                + clr("Consolidate memories before leaving? [y/N] ", "white", "bold"),
                end="", flush=True,
            )
            try:
                choice = input("").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = ""
                print()
            if choice == "y":
                from memory import (
                    consolidate_session, mine_files,
                    snapshot_memory_files, new_memory_files,
                )
                # Snapshot existing memory .md files BEFORE consolidating,
                # so we can detect exactly which ones consolidate just created.
                snap = snapshot_memory_files()
                info("Consolidating session memories…")
                saved = consolidate_session(_state.messages, config)
                if saved:
                    ok(f"Consolidated {len(saved)} memories: {', '.join(saved)}")
                else:
                    info("No new insights to consolidate.")
                # If MemPalace is ON, mine the .md files just created in
                # the memory dir (works without git).
                if config.get("mem_palace", True):
                    fresh = new_memory_files(snap)
                    if fresh:
                        info(f"MemPalace ON → mining {len(fresh)} fresh memory file(s)…")
                        mined = mine_files(fresh, config)
                        if mined:
                            ok(f"Mined {len(mined)} extra memories: {', '.join(mined)}")
                        else:
                            info("No additional insights mined.")
                # When the user opts into consolidation, they're telling us this
                # session matters — persist it explicitly regardless of the
                # MIN_AUTO_SAVE_TURNS gate that save_latest enforces later.
                try:
                    cmd_save("", _state, config)
                    config["_session_explicit_saved"] = True
                except Exception as e:
                    warn(f"Explicit save after consolidation failed: {e}")
    except Exception as e:
        warn(f"Consolidation trigger failed: {e}")

    if sys.stdin.isatty() and sys.platform != "win32":
        sys.stdout.write("\x1b[?2004l")  # disable bracketed paste mode
        sys.stdout.flush()
    ok("Goodbye!")
    save_latest("", _state, config)
    # Auto cloud-sync if enabled
    if config.get("cloudsave_auto") and config.get("gist_token") and _state.messages:
        info("Auto cloud-sync: uploading session to Gist…")
        from cloudsave import upload_session
        from config import save_config
        session_data = _build_session_data(_state)
        gist_id, err_msg = upload_session(
            session_data, config["gist_token"],
            gist_id=config.get("cloudsave_last_gist_id"),
        )
        if err_msg:
            err(f"Cloud sync failed: {err_msg}")
        else:
            config["cloudsave_last_gist_id"] = gist_id
            save_config(config)
            ok(f"Session synced → https://gist.github.com/{gist_id}")
    os._exit(0)

def cmd_memory(args: str, _state, config) -> bool:
    from memory import search_memory, load_index, delete_memory
    from memory.scan import scan_all_memories, format_memory_manifest, memory_freshness_text

    stripped = args.strip()
    parts = stripped.split(None, 1)
    subcmd = parts[0].lower() if parts else "all"
    subargs = parts[1] if len(parts) > 1 else ""

    # /memory load [name|number|n,n,n]  — inject memory content into conversation
    if subcmd == "load":
        entries = load_index("all")
        if not entries:
            info("Memory is empty — nothing to load.")
            return True

        # Interactive picker when no target is given
        if not subargs:
            print(clr("  Select memory to load (will be injected into context):", "cyan", "bold"))
            menu_buf = clr("  Select memory to load:", "cyan", "bold")
            for i, e in enumerate(entries):
                scope_lbl = clr(f"[{e.scope}]", "dim")
                hall_lbl  = clr(f"({e.hall})", "cyan") if e.hall else ""
                is_soul   = e.name.lower() == "soul" or (e.hall or "").lower() == "soul"
                name_clr  = "yellow" if is_soul else "white"
                line = f"  {clr(f'[{i+1:2d}]', 'yellow')} {clr(e.name, name_clr, 'bold'):<24} {hall_lbl:<15} {scope_lbl} {e.description[:60]}"
                print(line)
                menu_buf += "\n" + line
            print()
            ans = ask_input_interactive(
                clr("  Enter number(s) (e.g. 1 or 1,2,3), name, or Enter to cancel > ", "cyan"),
                config, menu_buf,
            ).strip()
            if not ans:
                info("  Cancelled.")
                return True
            subargs = ans

        # Resolve subargs → list of MemoryEntry
        selected: list = []
        tokens = [t.strip() for t in subargs.replace(",", " ").split() if t.strip()]
        for tok in tokens:
            if tok.isdigit():
                idx = int(tok) - 1
                if 0 <= idx < len(entries):
                    selected.append(entries[idx])
                else:
                    warn(f"Index {tok} out of range (1-{len(entries)}). Skipping.")
            else:
                match = next((e for e in entries if e.name.lower() == tok.lower()), None)
                if match is None:
                    warn(f"No memory named '{tok}'. Skipping.")
                else:
                    selected.append(match)

        if not selected:
            err("No valid memory selected.")
            return True

        # Inject selected memories as a user-role message so they enter context
        # for the next turn. Use role=user (not system) because some providers
        # reject non-standard system messages mid-conversation.
        blocks = []
        for e in selected:
            header = f"## Memory: {e.name}"
            if e.description:
                header += f"  —  {e.description}"
            blocks.append(f"{header}\n\n{e.content.strip()}")
        body = (
            "(Memory load requested by the user — treat the following as loaded context; "
            "do not echo it back unless asked.)\n\n"
            + "\n\n---\n\n".join(blocks)
        )
        try:
            _state.messages.append({"role": "user", "content": body})
        except Exception as ex:
            err(f"Failed to inject memory into context: {ex}")
            return True

        names = ", ".join(f"'{e.name}'" for e in selected)
        ok(f"Loaded {len(selected)} memory block(s) into context: {names}")
        return True

    # /memory consolidate  — trigger a structured self-reflection turn
    if subcmd == "consolidate":
        from memory import consolidate_session
        info("Consolidating session insights…")
        saved = consolidate_session(_state.messages, config)
        if saved:
            ok(f"Consolidated {len(saved)} new memories: {', '.join(saved)}")
        else:
            info("Found no new critical insights to consolidate at this time.")
        return True

    # /memory delete <name>
    if subcmd == "delete":
        if not subargs:
            err("Usage: /memory delete <name>")
            return True
        delete_memory(subargs, scope="user")
        delete_memory(subargs, scope="project")
        ok(f"Memory '{subargs}' deleted.")
        return True

    # /memory purge (keep soul)
    if subcmd == "purge":
        entries = load_index("all")
        count = 0
        for e in entries:
            is_soul = e.name.lower() == "soul" or e.hall.lower() == "soul"
            if not is_soul:
                delete_memory(e.name, scope=e.scope)
                count += 1
        ok(f"Purged {count} memories. (Soul preserved)")
        return True

    # /memory purge-soul (delete ALL)
    if subcmd == "purge-soul":
        entries = load_index("all")
        count = 0
        for e in entries:
            delete_memory(e.name, scope=e.scope)
            count += 1
        ok(f"Total purge complete. {count} memories deleted.")
        return True

    # /memory permanent [n|name]  — toggle GOLD flag (auto-load at startup)
    if subcmd == "permanent":
        from memory import save_memory
        entries = load_index("all")
        if not entries:
            info("Memory is empty.")
            return True

        if not subargs:
            print(clr("  Toggle PERMANENT (gold) — auto-loaded at startup:", "yellow", "bold"))
            menu_buf = clr("  Toggle permanent memories:", "yellow", "bold")
            for i, e in enumerate(entries):
                is_gold  = getattr(e, "gold", False)
                gold_tag = clr(" 🏆", "yellow", "bold") if is_gold else "  "
                name_clr = "yellow" if is_gold else "white"
                line = f"  {clr(f'[{i+1:2d}]', 'yellow')}{gold_tag} {clr(e.name, name_clr, 'bold'):<24} {clr(e.description[:50], 'dim')}"
                print(line)
                menu_buf += "\n" + line
            print()
            ans = ask_input_interactive(
                clr("  Enter number(s) to toggle (e.g. 1,2,3) or Enter to cancel > ", "yellow"),
                config, menu_buf,
            ).strip()
            if not ans:
                info("  Cancelled.")
                return True
            subargs = ans

        tokens = [t.strip() for t in subargs.replace(",", " ").split() if t.strip()]
        count = 0
        for tok in tokens:
            target = None
            if tok.isdigit():
                idx = int(tok) - 1
                if 0 <= idx < len(entries):
                    target = entries[idx]
            else:
                target = next((e for e in entries if e.name.lower() == tok.lower()), None)
            if target is None:
                warn(f"Skipping '{tok}' (not found)")
                continue
            target.gold = not getattr(target, "gold", False)
            save_memory(target, scope=target.scope)
            if target.gold:
                ok(f"'{target.name}' is now PERMANENT 🏆")
            else:
                ok(f"'{target.name}' is no longer permanent")
            count += 1
        if count:
            info(f"Done. {count} memories updated.")
        return True

    # /memory unbind [n|name]  — remove GOLD flag (only lists current gold)
    if subcmd == "unbind":
        from memory import save_memory
        entries = [e for e in load_index("all") if getattr(e, "gold", False)]
        if not entries:
            info("No permanent (gold) memories to unbind.")
            return True

        if not subargs:
            print(clr("  Select PERMANENT memories to remove gold flag:", "white", "bold"))
            menu_buf = clr("  Unbind from gold:", "white", "bold")
            for i, e in enumerate(entries):
                line = f"  {clr(f'[{i+1:2d}]', 'yellow')} 🏆 {clr(e.name, 'yellow', 'bold')}"
                print(line)
                menu_buf += "\n" + line
            print()
            ans = ask_input_interactive(
                clr("  Enter number(s) or Enter to cancel > ", "white"),
                config, menu_buf,
            ).strip()
            if not ans:
                info("  Cancelled.")
                return True
            subargs = ans

        tokens = [t.strip() for t in subargs.replace(",", " ").split() if t.strip()]
        count = 0
        for tok in tokens:
            target = None
            if tok.isdigit():
                idx = int(tok) - 1
                if 0 <= idx < len(entries):
                    target = entries[idx]
            else:
                target = next((e for e in entries if e.name.lower() == tok.lower()), None)
            if target is None:
                warn(f"Skipping '{tok}'")
                continue
            target.gold = False
            save_memory(target, scope=target.scope)
            ok(f"'{target.name}' unbound (no longer gold)")
            count += 1
        if count:
            info(f"Done. {count} memories updated.")
        return True

    # /memory list (or no args)
    if not stripped or subcmd == "all" or subcmd == "list":
        entries = load_index("all")
        if not entries:
            info("Memory is empty.")
            return True
        info(f"  {len(entries)} persistent memories found:")
        for e in entries:
            scope_clr = clr(f"[{e.scope}]", "dim")
            hall_hint = clr(f"({e.hall})", "cyan") if e.hall else ""
            # Highlight the Soul or Gold memories in yellow
            is_soul = e.name.lower() == "soul" or e.hall.lower() == "soul"
            is_gold = getattr(e, "gold", False)
            gold_tag = clr(" 🏆", "yellow", "bold") if is_gold else "  "
            name_color = "yellow" if (is_soul or is_gold) else "white"
            print(f"    • {clr(e.name, name_color, 'bold'):<20}{gold_tag} {hall_hint:<15} {scope_clr} {e.description}")
        return True

    # Else: treat as search query
    results = search_memory(stripped)
    if not results:
        info(f"No memories matching '{stripped}'")
        return True
    
    info(f"  {len(results)} search result(s) for '{stripped}':")
    for m in results:
        conf_tag = f" conf:{m.confidence:.0%}" if m.confidence < 1.0 else ""
        scope_clr = clr(f"[{m.scope}]", "dim")
        # Highlight the Soul in yellow in search results too
        is_soul = m.name.lower() == "soul" or m.hall.lower() == "soul"
        name_color = "yellow" if is_soul else "white"
        print(f"    • {clr(m.name, name_color, 'bold'):<20} {scope_clr}{clr(conf_tag, 'yellow')} {m.description}")
    return True

def cmd_agents(_args: str, _state, config) -> bool:
    try:
        from multi_agent.tools import get_agent_manager
        mgr = get_agent_manager()
        tasks = mgr.list_tasks()
        if not tasks:
            info("No sub-agent tasks.")
            return True
        info(f"  {len(tasks)} sub-agent task(s):")
        for t in tasks:
            preview = t.prompt[:50] + ("..." if len(t.prompt) > 50 else "")
            wt_info = f"  branch:{t.worktree_branch}" if t.worktree_branch else ""
            info(f"  {t.id} [{t.status:9s}] name={t.name}{wt_info}  {preview}")
    except Exception:
        info("Sub-agent system not initialized.")
    return True


def _print_background_notifications(state=None):
    """Print notifications and inject completions into state messages.
    Returns True if any NEW completion/failure was handled.
    """

    new_found = False
    try:
        from multi_agent.tools import get_agent_manager
        mgr = get_agent_manager()
    except Exception:
        mgr = None

    if not hasattr(_print_background_notifications, "_seen"):
        _print_background_notifications._seen = set()

    if mgr:
        for task in mgr.list_tasks():
            if task.id in _print_background_notifications._seen:
                continue
            if task.status in ("completed", "failed", "cancelled"):
                _print_background_notifications._seen.add(task.id)
                new_found = True
                if state:
                    state.messages.append({"role": "system", "content": f"System Notification: Background agent '{task.name}' {task.status}. Use CheckAgentResult to read the output."})

    # ── Offloaded Tmux Jobs ────────────────────────────────────────────────
    try:
        from pathlib import Path
        import json
        jobs_dir = Path.home() / ".dulus" / "jobs"
        if jobs_dir.is_dir():
            for fp in list(jobs_dir.glob("*.json")):
                job_id = fp.stem
                if job_id in _print_background_notifications._seen:
                    continue
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        job = json.load(f)
                    if job.get("status") in ("completed", "failed"):
                        # PID ownership check: only the Dulus instance that launched
                        # this job should claim it. This prevents cross-instance
                        # notification theft when 2+ Duluss share ~/.dulus/jobs/.
                        owner_pid = job.get("owner_pid")
                        if owner_pid and owner_pid != os.getpid():
                            # Looser check: if the owner PID is already dead,
                            # we can safely claim it in this session.
                            try:
                                import psutil
                                is_alive = psutil.pid_exists(owner_pid)
                            except Exception:
                                # Fallback if psutil is missing
                                try:
                                    if os.name == 'nt':
                                        # On Windows, os.kill(pid, 0) is not reliable for "is alive"
                                        # without causing issues, using tasklist snippet instead
                                        import subprocess
                                        p = subprocess.run(['tasklist', '/FI', f'PID eq {owner_pid}'], 
                                                       capture_output=True, text=True)
                                        is_alive = str(owner_pid) in p.stdout
                                    else:
                                        os.kill(owner_pid, 0)
                                        is_alive = True
                                except Exception:
                                    is_alive = False
                            
                            if is_alive:
                                continue  # This job definitely belongs to another ACTIVE Dulus instance
                        # Archive to disk FIRST — prevents race condition where
                        # sentinel thread + main loop both read "completed" simultaneously
                        job_status = job["status"]
                        job["status"] = "archived"
                        try:
                            with open(fp, "w", encoding="utf-8") as f:
                                json.dump(job, f, indent=2, ensure_ascii=False)
                        except Exception:
                            pass
                        # Now check _seen (another thread may have beaten us here)
                        if job_id in _print_background_notifications._seen:
                            continue
                        _print_background_notifications._seen.add(job_id)
                        new_found = True
                        # Surface the completed batch id so `/batch status` and
                        # `/batch fetch` (no arg) default to it.
                        _bid = job.get("batch_id") or (job.get("params") or {}).get("batch_id")
                        if not _bid and job.get("tool_name") == "kimi_batch":
                            _bid = job_id
                        if _bid:
                            globals()["_LAST_NOTIFIED_BATCH_ID"] = _bid
                        if state:
                            log_path = jobs_dir / f"{job_id}.log"
                            last_log = jobs_dir / "last_background_output.txt"
                            msg = (
                                f"System Notification: Offloaded tool '{job['tool_name']}' FINISHED (Job: {job_id}).\n"
                                f"IMPORTANT: The full output is saved at `{last_log}`. "
                                f"If the results below appear truncated, use the `SearchLastOutput` or `Read` tool on that file to see everything. "
                                f"DO NOT run '{job['tool_name']}' again."
                            )
                            if job.get("error"): msg += f"\nERROR: {job['error']}"
                            state.messages.append({"role": "system", "content": msg})

                        try:
                            if 'log_path' in locals() and log_path.exists():
                                log_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass
    return new_found


# ── IPC server: shared session via TCP socket ─────────────────────────────
# When a Dulus REPL or daemon is running, it listens on 127.0.0.1:5151. Any
# `dulus "..."` invocation from another shell first probes this port — if the
# server answers, the prompt is forwarded over the wire and the response is
# streamed back, so multiple shells share the SAME live session (history,
# memory, tool state, all of it). If the port is dead, the CLI falls back to
# spawning its own --print process.
#
# This is the dominican workaround: 80 lines of socket code instead of a
# session manager + IPC framework + daemon orchestrator. Same UX, 1/100th
# the surface area.

DULUS_IPC_HOST = "127.0.0.1"
DULUS_IPC_PORT = 5151


def _ipc_server_loop(config, state):
    """Tiny TCP server: accepts one JSON request per connection, runs it on
    the live session, and writes the assistant reply back as JSON.
    Robust to port-already-in-use (we just exit silently — another instance
    is the listener and that's fine)."""
    import socket as _socket
    import json as _json

    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    # On Windows, SO_REUSEADDR lets two sockets share a port — wrong here; we
    # want a hard "port is taken, back off." SO_EXCLUSIVEADDRUSE gives us that.
    # On Linux, SO_REUSEADDR only matters for TIME_WAIT recovery, so skipping
    # it is fine — restart cooldown is a few seconds at worst.
    if hasattr(_socket, "SO_EXCLUSIVEADDRUSE"):
        try:
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_EXCLUSIVEADDRUSE, 1)
        except OSError:
            pass
    try:
        sock.bind((DULUS_IPC_HOST, DULUS_IPC_PORT))
    except OSError:
        return  # another Dulus already listening — fine, we're the client one
    sock.listen(4)
    sock.settimeout(1.0)
    config["_ipc_listening"] = True

    while not config.get("_ipc_stop"):
        try:
            conn, _addr = sock.accept()
        except _socket.timeout:
            continue
        except Exception:
            continue
        try:
            conn.settimeout(60.0)
            buf = b""
            while b"\n" not in buf and len(buf) < 64 * 1024:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
            line = buf.split(b"\n", 1)[0].decode("utf-8", errors="ignore").strip()
            if not line:
                conn.close()
                continue
            try:
                req = _json.loads(line)
            except Exception:
                conn.sendall(b'{"error":"bad json"}\n')
                conn.close()
                continue

            prompt = (req.get("prompt") or "").strip()
            if not prompt:
                conn.sendall(b'{"error":"empty prompt"}\n')
                conn.close()
                continue

            cb = config.get("_run_query_callback")
            if not cb:
                conn.sendall(b'{"error":"no run_query callback registered"}\n')
                conn.close()
                continue

            # Snapshot the message count so we can lift the new assistant
            # reply after the turn completes.
            before = len(state.messages) if state else 0
            try:
                cb(prompt)
            except Exception as e:
                conn.sendall(_json.dumps({"error": f"{type(e).__name__}: {e}"}).encode() + b"\n")
                conn.close()
                continue

            response_text = ""
            if state and state.messages:
                for m in reversed(state.messages[before:] or state.messages):
                    if m.get("role") == "assistant":
                        content = m.get("content", "")
                        if isinstance(content, list):
                            parts = []
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    parts.append(block["text"])
                                elif isinstance(block, str):
                                    parts.append(block)
                            content = "\n".join(parts)
                        if content:
                            response_text = content
                            break
            payload = _json.dumps({"response": response_text or "(no reply)"}).encode() + b"\n"
            try:
                conn.sendall(payload)
            except Exception:
                pass
        except (_socket.timeout, TimeoutError, ConnectionResetError, BrokenPipeError, OSError):
            # Common transient socket errors: client opened conn and walked
            # away (recv timeout), client killed mid-write, etc. Drop this
            # connection but keep the server thread running.
            pass
        except Exception:
            # Catch-all so a single bad request never takes down the IPC
            # server thread (which would silently break /bg start's promise).
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # Release the port immediately on shutdown so a daemon spawned right
    # after `/bg start` can bind without waiting for TIME_WAIT to expire.
    # SO_LINGER {onoff:1, linger:0} forces an RST close that bypasses
    # the TIME_WAIT state (cost: any in-flight bytes are dropped, which is
    # fine — we're not sending anything when we shut down).
    try:
        import struct as _struct
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_LINGER,
                        _struct.pack("ii", 1, 0))
    except Exception:
        pass
    try:
        sock.shutdown(_socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        sock.close()
    except Exception:
        pass
    config["_ipc_listening"] = False


def _try_ipc_dispatch(prompt: str, timeout: float = 0.4) -> bool:
    """Client side: probe the IPC server, send a prompt, print the response,
    return True if it succeeded. Returns False if no server is listening,
    so callers can fall back to the in-process --print path."""
    import socket as _socket
    import json as _json

    try:
        sock = _socket.create_connection(
            (DULUS_IPC_HOST, DULUS_IPC_PORT), timeout=timeout
        )
    except (_socket.timeout, ConnectionRefusedError, OSError):
        return False
    try:
        sock.settimeout(180.0)
        sock.sendall((_json.dumps({"prompt": prompt, "v": 1}) + "\n").encode())
        buf = b""
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break
        line = buf.split(b"\n", 1)[0].decode("utf-8", errors="ignore").strip()
        try:
            data = _json.loads(line)
        except Exception:
            return False
        if "error" in data:
            print(f"[ipc] {data['error']}", flush=True)
            return True  # we did get a reply, just an error one — don't fall back
        print(data.get("response", ""), flush=True)
        return True
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _job_sentinel_loop(config, state):
    """Background daemon that triggers run_query as soon as a job finishes.
    
    SAFETY: Only fires if the chat has been idle for at least 10 seconds.
    This prevents background notifications from colliding with active
    conversation turns (user typing, model streaming, Telegram messages).
    If a job finishes during active chat, it stays pending until either:
    - The chat goes quiet for 10s, then the sentinel fires the callback.
    - The user sends their next message; run_query() injects the
      notification into context at line 6187 without firing a background event.
    """
    while True:
        try:
            # Cooldown guard: don't interrupt an active conversation
            idle_seconds = time.time() - config.get("_last_interaction_time", 0)
            if idle_seconds < 10:
                pass  # too soon; wait for quiet period
            elif _print_background_notifications(state):
                cb = config.get("_run_query_callback")
                if cb:
                    # Grace period: if the user sent a message right when the
                    # job completed, abort to prevent output reordering.
                    time.sleep(0.5)
                    if time.time() - config.get("_last_interaction_time", 0) < 5:
                        continue
                    # Wait until any active run_query finishes before firing
                    # so background output doesn't collide with active streaming
                    lock = config.get("_query_lock")
                    if lock:
                        with lock:
                            config["_last_interaction_time"] = time.time()
                            cb("(System Automated Event): One or more background jobs have finished. "
                               "Please review the results and report back to the user.")
                    else:
                        config["_last_interaction_time"] = time.time()
                        cb("(System Automated Event): One or more background jobs have finished. "
                           "Please review the results and report back to the user.")
        except Exception:
            pass
        time.sleep(2)

def cmd_skills(_args: str, _state, config) -> bool:
    from skill import load_skills
    skills = load_skills()
    if not skills:
        info("No skills found.")
        return True
    info(f"Available skills ({len(skills)}):")
    for s in skills:
        triggers = ", ".join(s.triggers)
        source_label = f"[{s.source}]" if s.source != "builtin" else ""
        hint = f"  args: {s.argument_hint}" if s.argument_hint else ""
        print(f"  {clr(s.name, 'cyan'):24s} {s.description}  {clr(triggers, 'dim')}{hint} {clr(source_label, 'yellow')}")
        if s.when_to_use:
            print(f"    {clr(s.when_to_use[:80], 'dim')}")
    return True

def _pager(header: str, lines: list, page_size: int = 30) -> None:
    """Simple terminal pager: shows page_size lines, waits for n/q."""
    import msvcrt
    total = len(lines)
    i = 0
    while i < total:
        chunk = lines[i:i + page_size]
        if i == 0:
            info(header)
        for line in chunk:
            print(line)
        i += page_size
        if i < total:
            remaining = total - i
            sys.stdout.write(
                clr(f"\n  ── {remaining} more ── [n] next page  [q] quit ── ", "cyan")
            )
            sys.stdout.flush()
            while True:
                ch = msvcrt.getwch().lower()
                if ch in ("n", "\r", "\n", " "):
                    print()
                    break
                if ch == "q":
                    print()
                    return
    print(clr(f"\n  ── end ({total} skills) ──", "dim"))


def cmd_skill(args: str, state, config) -> bool:
    """Browse and install skills from Anthropic marketplace or ClawHub.

    /skill                     — list installed skills + show help
    /skill list                — list installed skills
    /skill list local [q]      — browse/search Anthropic skills on disk
    /skill list clawhub [q]    — search ClawHub (WIP)
    /skill get <slug>          — install (e.g. /skill get frontend-design/frontend-design)
    /skill use <name>          — inject skill as context for this turn
    /skill remove <name>       — uninstall skill
    """
    from skill.clawhub import (
        list_local, list_installed, install_local, install_clawhub,
        search_clawhub, read_skill,
        list_awesome_remote, list_composio_toolkits,
        install_awesome_remote,
    )
    from pathlib import Path as _Path

    parts = args.strip().split(None, 1)
    subcmd = parts[0].lower() if parts else ""
    rest   = parts[1].strip() if len(parts) > 1 else ""

    # ── /skill (no args) = show help + installed list ─────────────────────
    if not subcmd:
        print(clr("\n  Dulus Skill Manager", "cyan", "bold"))
        print(f"  {clr('Skills directory:', 'dim')} {str(_Path.home() / '.dulus/skills')}")
        print(f"  {clr('/skill list local [q]', 'yellow'):30s} Browse available marketplace skills")
        print(f"  {clr('/skill get <slug>', 'yellow'):30s} Install a skill by its slug")
        print(f"  {clr('/skill use <name>', 'yellow'):30s} Inject an installed skill into this turn")
        print(f"  {clr('/skill remove <name>', 'yellow'):30s} Uninstall a skill")
        
        skills = list_installed()
        if skills:
            print(clr(f"\n  Installed skills ({len(skills)}):", "green"))
            for s in skills:
                print(f"  • {clr(s['name'], 'cyan'):22s} {s['description'][:60]}")
        else:
            print(clr("\n  No skills installed yet. Try '/skill list local' to find some!", "dim"))
        print()
        return True

    # ── /skill list ────────────────────────────────────────────────────────
    if subcmd == "list":
        # Interactive picker when called with no source — pick where to look.
        if not rest:
            print(clr("\n  Pick a source:", "cyan", "bold"))
            print(f"  1) {clr('awesome', 'yellow')}   — alirezarezvani/claude-skills (~235 skills, live from GitHub)")
            print(f"  2) {clr('composio', 'yellow')}  — Composio Tool Router (1000+ apps via API)")
            print(f"  3) {clr('local', 'yellow')}     — Anthropic + awesome marketplaces on disk (~/.claude/...)")
            print(f"  4) {clr('installed', 'yellow')} — skills already in ~/.dulus/skills/")
            print(f"  5) {clr('all', 'yellow')}       — combine awesome + composio + local")
            try:
                choice = input(clr("  > ", "cyan")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                return True
            mapping = {"1": "awesome", "2": "composio", "3": "local", "4": "installed", "5": "all"}
            rest = mapping.get(choice, choice)

        if rest.startswith("awesome"):
            query = rest[7:].strip()
            # `--fast` skips descriptions for an instant list; default pulls them in parallel.
            fast = False
            if "--fast" in query.split():
                fast = True
                query = " ".join(t for t in query.split() if t != "--fast").strip()
            if fast:
                info("Fetching awesome skill list from GitHub (instant, no descriptions)...")
            else:
                info("Fetching awesome skills + descriptions from GitHub (parallel, ~5s)...")
            skills = list_awesome_remote(query, with_descriptions=not fast)
            if not skills:
                err("Could not fetch awesome skills (network or rate-limit).")
                return True
            lines = [
                f"  {clr(s['id'], 'cyan'):55s}  {s.get('description', '')[:80]}"
                for s in skills
            ]
            header = f"Awesome skills ({len(skills)})" + (f" matching '{query}'" if query else "")
            hint = "" if not fast else " — remove `--fast` for descriptions"
            _pager(f"{header}{hint} — n=next q=quit", lines)
            return True

        if rest.startswith("composio"):
            query = rest[8:].strip()
            info("Fetching Composio toolkits (cached 24h)...")
            skills = list_composio_toolkits(query)
            if not skills:
                err("Could not fetch Composio toolkits.")
                return True
            lines = [
                f"  {clr(s['id'], 'cyan'):40s}  {s['description'][:80]}"
                for s in skills
            ]
            header = f"Composio toolkits ({len(skills)})" + (f" matching '{query}'" if query else "")
            _pager(f"{header} — use composio_create_session to connect — n=next q=quit", lines)
            return True

        if rest.startswith("all"):
            query = rest[3:].strip()
            combined = (
                list_awesome_remote(query)
                + list_composio_toolkits(query)
                + list_local(query)
            )
            if not combined:
                err("No skills found across any source.")
                return True
            lines = [
                f"  {clr(s['id'], 'cyan'):55s}  [{clr(s['source'],'yellow')}]  {s['description'][:60]}"
                for s in combined
            ]
            _pager(f"All sources ({len(combined)}) — n=next q=quit", lines)
            return True

        if rest.startswith("local"):
            query = rest[5:].strip()
            skills = list_local(query)
            # Fall back to awesome remote when local marketplaces aren't on
            # disk (i.e. user installed Dulus without Claude Code present).
            if not skills and not query:
                info("No local marketplace on disk — fetching awesome from GitHub...")
                skills = list_awesome_remote()
            if not skills:
                info(f"No local skills found matching '{query}'.")
                return True
            lines = [
                f"  {clr(s['id'], 'cyan'):45s}  [{clr(s['source'],'yellow')}]  {s['description']}"
                for s in skills
            ]
            header = f"Available skills ({len(skills)})" + (f" matching '{query}'" if query else "")
            _pager(f"{header} — n=next q=quit", lines)
            return True

        if rest.startswith("clawhub"):
            q = rest.replace("clawhub", "").strip()
            results = search_clawhub(q or "")
            if not results:
                info("ClawHub search not yet wired (API endpoint pending).")
            else:
                for r in results:
                    print(f"  {clr(r['slug'], 'cyan'):30s}  {r.get('description','')[:60]}")
            return True

        if rest.startswith("installed"):
            query = rest[9:].strip()
            skills = list_installed(query)
            if not skills:
                if query:
                    info(f"No installed skills matching '{query}'.")
                else:
                    info("No skills installed yet.")
                return True
            header = f"Installed skills ({len(skills)})" + (f" matching '{query}'" if query else "")
            info(header + ":")
            for s in skills:
                print(f"  • {clr(s['name'], 'cyan'):22s} [{s['source']}]  {s['description']}")
            return True

        # /skill info <name>
        if subcmd == "info":
            if not rest:
                info("Usage: /skill info <skill-name>")
                return True
            content = read_skill(rest)
            if not content:
                info(f"Skill '{rest}' not found.")
            else:
                _pager(f"Skill '{rest}' (preview) — n=next q=quit", content.splitlines())
            return True

        # default: list installed
        query = rest.strip()
        skills = list_installed(query)
        if not skills:
            if query:
                info(f"No installed skills matching '{query}'.")
            else:
                info("No skills installed yet. Some popular options:")
                for s in list_local()[:10]:
                    print(f"  {clr(s['id'], 'dim'):45s}  {s['description'][:55]}")
                print(clr(f"\n  → /skill get <plugin/skill>  to install", "yellow"))
            return True
            
        header = f"Installed skills ({len(skills)})" + (f" matching '{query}'" if query else "")
        info(header + ":")
        for s in skills:
            print(f"  • {clr(s['name'], 'cyan'):22s} [{s['source']}]  {s['description']}")
        return True

    # ── /skill get ─────────────────────────────────────────────────────────
    if subcmd == "get":
        if not rest:
            err("Usage: /skill get <plugin/skill>  or  /skill get clawhub:<slug>")
            return True
        if rest.startswith("clawhub:"):
            slug = rest[8:]
            success, msg = install_clawhub(slug)
        elif rest.startswith("awesome/"):
            success, msg = install_awesome_remote(rest)
        else:
            success, msg = install_local(rest)
            # Fallback to awesome-remote if not found locally
            if not success:
                success, msg = install_awesome_remote(rest)
        (ok if success else err)(msg)
        return True

    # ── /skill use ─────────────────────────────────────────────────────────
    if subcmd == "use":
        from skill.clawhub import DULUS_SKILLS_DIR
        installed = list_installed()
        if not installed:
            err("No skills installed yet. Run /skill list to browse and install skills.")
            return True

        # Interactive picker when no target is given
        if not rest:
            print(clr("  Select skill(s) to inject (active for this turn):", "cyan", "bold"))
            menu_buf = clr("  Select skill(s) to inject:", "cyan", "bold")
            for i, s in enumerate(installed):
                line = f"  {clr(f'[{i+1:2d}]', 'yellow')} {clr(s['name'], 'white', 'bold'):<24} [{clr(s['source'], 'dim')}]  {s['description'][:55]}"
                print(line)
                menu_buf += "\n" + line
            print()
            ans = ask_input_interactive(
                clr("  Enter number(s) (e.g. 1 or 1,2,3), name, or Enter to cancel > ", "cyan"),
                config, menu_buf,
            ).strip()
            if not ans:
                info("  Cancelled.")
                return True
            rest = ans

        # Resolve rest → list of skill names
        selected_names: list[str] = []
        tokens = [t.strip() for t in rest.replace(",", " ").split() if t.strip()]
        for tok in tokens:
            if tok.isdigit():
                idx = int(tok) - 1
                if 0 <= idx < len(installed):
                    selected_names.append(installed[idx]["name"])
                else:
                    warn(f"Index {tok} out of range (1-{len(installed)}). Skipping.")
            else:
                match = next((s["name"] for s in installed if s["name"].lower() == tok.lower()), None)
                if match is None:
                    warn(f"No skill named '{tok}'. Skipping.")
                else:
                    selected_names.append(match)

        if not selected_names:
            err("No valid skill selected.")
            return True

        # Inject selected skills into context
        blocks = []
        for name in selected_names:
            body = read_skill(name)
            if not body:
                warn(f"Skill '{name}' could not be read. Skipping.")
                continue
            skill_dir = DULUS_SKILLS_DIR / name
            path_hint = f"\n\n# NOTE: Skill '{name}' files are located at: {skill_dir}" if skill_dir.exists() else ""
            blocks.append(f"## Skill: {name}\n\n{body}{path_hint}")

        if not blocks:
            err("No skills could be injected.")
            return True

        existing = config.get("_skill_inject", "")
        new_inject = "\n\n---\n\n".join(blocks)
        config["_skill_inject"] = (existing + "\n\n" + new_inject).strip() if existing else new_inject
        names_txt = ", ".join(f"'{n}'" for n in selected_names)
        ok(f"Injected {len(blocks)} skill(s) — active for this turn: {names_txt}")
        return True

    # ── /skill remove ──────────────────────────────────────────────────────
    if subcmd == "remove":
        if not rest:
            err("Usage: /skill remove <name>")
            return True
        from skill.clawhub import DULUS_SKILLS_DIR
        import shutil
        
        path_md = DULUS_SKILLS_DIR / f"{rest}.md"
        path_dir = DULUS_SKILLS_DIR / rest
        
        if path_md.exists():
            path_md.unlink()
            ok(f"Removed skill '{rest}'.")
        elif path_dir.is_dir():
            shutil.rmtree(path_dir)
            ok(f"Removed skill directory '{rest}'.")
        else:
            err(f"Skill '{rest}' not found.")
        return True

    err(f"Unknown subcommand '{subcmd}'. See /help for usage.")
    return True


def cmd_mcp(args: str, _state, config) -> bool:
    """Show MCP server status, or manage servers.

    /mcp               — list all configured servers and their tools
    /mcp reload        — reconnect all servers and refresh tools
    /mcp reload <name> — reconnect a single server
    /mcp add <name> <command> [args...] — add a stdio server to user config
    /mcp remove <name> — remove a server from user config
    """
    from dulus_mcp.client import get_mcp_manager
    from dulus_mcp.config import (load_mcp_configs, add_server_to_user_config,
                             remove_server_from_user_config, list_config_files)
    from dulus_mcp.tools import initialize_mcp, reload_mcp, refresh_server

    parts = args.split() if args.strip() else []
    subcmd = parts[0].lower() if parts else ""

    if subcmd == "reload":
        target = parts[1] if len(parts) > 1 else ""
        if target:
            err = refresh_server(target)
            if err:
                err(f"Failed to reload '{target}': {err}")
            else:
                ok(f"Reloaded MCP server: {target}")
        else:
            errors = reload_mcp()
            for name, e in errors.items():
                if e:
                    print(f"  {clr('✗', 'red')} {name}: {e}")
                else:
                    print(f"  {clr('✓', 'green')} {name}: connected")
        return True

    if subcmd == "add":
        if len(parts) < 3:
            err("Usage: /mcp add <name> <command> [arg1 arg2 ...]")
            return True
        name = parts[1]
        command = parts[2]
        cmd_args = parts[3:]
        raw = {"type": "stdio", "command": command}
        if cmd_args:
            raw["args"] = cmd_args
        add_server_to_user_config(name, raw)
        ok(f"Added MCP server '{name}' → restart or /mcp reload to connect")
        return True

    if subcmd == "remove":
        if len(parts) < 2:
            err("Usage: /mcp remove <name>")
            return True
        name = parts[1]
        removed = remove_server_from_user_config(name)
        if removed:
            ok(f"Removed MCP server '{name}' from user config")
        else:
            err(f"Server '{name}' not found in user config")
        return True

    # Default: list servers
    mgr = get_mcp_manager()
    servers = mgr.list_servers()

    config_files = list_config_files()
    if config_files:
        info(f"Config files: {', '.join(str(f) for f in config_files)}")

    if not servers:
        configs = load_mcp_configs()
        if not configs:
            info("No MCP servers configured.")
            info("Add servers in ~/.dulus/mcp.json or .mcp.json")
            info("Example: /mcp add my-git uvx mcp-server-git")
        else:
            info("MCP servers configured but not yet connected. Run /mcp reload")
        return True

    info(f"MCP servers ({len(servers)}):")
    total_tools = 0
    for client in servers:
        status_color = {
            "connected":    "green",
            "connecting":   "yellow",
            "disconnected": "dim",
            "error":        "red",
        }.get(client.state.value, "dim")
        print(f"  {clr(client.status_line(), status_color)}")
        for tool in client._tools:
            print(f"      {clr(tool.qualified_name, 'cyan')}  {tool.description[:60]}")
            total_tools += 1

    if total_tools:
        info(f"Total: {total_tools} MCP tool(s) available to Dulus")
    return True


def cmd_plugin(args: str, _state, config) -> bool:
    """Manage plugins.

    /plugin                                  — list installed plugins
    /plugin install name@url [--main-agent]  — install a plugin; with --main-agent, hand off to the main agent after install
    /plugin uninstall name                   — uninstall a plugin
    /plugin enable name                      — enable a plugin
    /plugin disable name                     — disable a plugin
    /plugin disable-all                      — disable all plugins
    /plugin update name                      — update a plugin from its source
    /plugin reload                           — reload all plugins and register tools
    /plugin recommend [context]              — recommend plugins for context
    /plugin info name                        — show plugin details
    """
    from plugin import (
        install_plugin, uninstall_plugin, enable_plugin, disable_plugin,
        disable_all_plugins, update_plugin, list_plugins, get_plugin,
        PluginScope, recommend_plugins, format_recommendations, reload_plugins,
        parse_plugin_identifier,
    )

    parts = args.split(None, 1)
    subcmd = parts[0].lower() if parts else ""
    rest   = parts[1].strip() if len(parts) > 1 else ""

    if not subcmd:
        # List all plugins
        plugins = list_plugins()
        if not plugins:
            info("No plugins installed.")
            info("Install: /plugin install name@git_url")
            info("Recommend: /plugin recommend")
            return True
        info(f"Installed plugins ({len(plugins)}):")
        for p in plugins:
            state_color = "green" if p.enabled else "dim"
            state_str   = "enabled" if p.enabled else "disabled"
            desc = p.manifest.description if p.manifest else ""
            print(f"  {clr(p.name, state_color)} [{p.scope.value}] {state_str}  {desc[:60]}")
        return True

    if subcmd == "install":
        if not rest:
            err("Usage: /plugin install name@git_url [--project] [--main-agent]")
            return True
        scope_str = "user"
        if " --project" in rest or rest.endswith("--project"):
            scope_str = "project"
            rest = rest.replace("--project", "").strip()
        main_agent = False
        if "--main-agent" in rest:
            main_agent = True
            rest = rest.replace("--main-agent", "").strip()
        scope = PluginScope(scope_str)
        success, msg = install_plugin(rest, scope=scope)
        (ok if success else err)(msg)
        if success and main_agent:
            plugin_name, plugin_source = parse_plugin_identifier(rest)
            return ("__plugin_main_agent__", plugin_name, plugin_source or "")
        return True

    if subcmd == "uninstall":
        if not rest:
            err("Usage: /plugin uninstall name")
            return True
        success, msg = uninstall_plugin(rest)
        (ok if success else err)(msg)
        return True

    if subcmd == "enable":
        if not rest:
            err("Usage: /plugin enable name")
            return True
        success, msg = enable_plugin(rest)
        (ok if success else err)(msg)
        return True

    if subcmd == "disable":
        if not rest:
            err("Usage: /plugin disable name")
            return True
        success, msg = disable_plugin(rest)
        (ok if success else err)(msg)
        return True

    if subcmd == "disable-all":
        success, msg = disable_all_plugins()
        (ok if success else err)(msg)
        return True

    if subcmd == "update":
        if not rest:
            err("Usage: /plugin update name")
            return True
        success, msg = update_plugin(rest)
        (ok if success else err)(msg)
        return True

    if subcmd == "reload":
        result = reload_plugins()
        ok(f"Reloaded plugins: {result['tools_registered']} tools registered, {result['modules_cleared']} modules cleared")
        return True

    if subcmd == "recommend":
        from pathlib import Path as _Path
        context = rest
        if not context:
            # Auto-detect context from project files
            from plugin.recommend import recommend_from_files
            files = list(_Path.cwd().glob("**/*"))[:200]
            recs = recommend_from_files(files)
        else:
            recs = recommend_plugins(context)
        print(format_recommendations(recs))
        return True

    if subcmd == "info":
        if not rest:
            err("Usage: /plugin info name")
            return True
        entry = get_plugin(rest)
        if entry is None:
            err(f"Plugin '{rest}' not found.")
            return True
        m = entry.manifest
        print(f"Name:    {entry.name}")
        print(f"Scope:   {entry.scope.value}")
        print(f"Source:  {entry.source}")
        print(f"Dir:     {entry.install_dir}")
        print(f"Enabled: {entry.enabled}")
        if m:
            print(f"Version: {m.version}")
            print(f"Author:  {m.author}")
            print(f"Desc:    {m.description}")
            if m.tags:
                print(f"Tags:    {', '.join(m.tags)}")
            if m.tools:
                print(f"Tools:   {', '.join(m.tools)}")
            if m.skills:
                print(f"Skills:  {', '.join(m.skills)}")
        return True

    err(f"Unknown plugin subcommand: {subcmd}  (try /plugin or /help)")
    return True


def cmd_tasks(args: str, _state, config) -> bool:
    """Show and manage tasks.

    /tasks                  — list all tasks
    /tasks create <subject> — quick-create a task
    /tasks done <id>        — mark task completed
    /tasks start <id>       — mark task in_progress
    /tasks cancel <id>      — mark task cancelled
    /tasks delete <id>      — delete a task
    /tasks get <id>         — show full task details
    /tasks clear            — delete all tasks
    """
    from task import list_tasks, get_task, create_task, update_task, delete_task, clear_all_tasks
    from task.types import TaskStatus

    parts = args.split(None, 1)
    subcmd = parts[0].lower() if parts else ""
    rest   = parts[1].strip() if len(parts) > 1 else ""

    STATUS_MAP = {
        "done":   "completed",
        "start":  "in_progress",
        "cancel": "cancelled",
    }

    if not subcmd:
        tasks = list_tasks()
        if not tasks:
            info("No tasks. Use TaskCreate tool or /tasks create <subject>.")
            return True
        resolved = {t.id for t in tasks if t.status == TaskStatus.COMPLETED}
        total = len(tasks)
        done  = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        info(f"Tasks ({done}/{total} completed):")
        for t in tasks:
            pending_blockers = [b for b in t.blocked_by if b not in resolved]
            owner_str   = f" {clr(f'({t.owner})', 'dim')}" if t.owner else ""
            blocked_str = clr(f" [blocked by #{', #'.join(pending_blockers)}]", "yellow") if pending_blockers else ""
            status_color = {
                TaskStatus.PENDING:     "dim",
                TaskStatus.IN_PROGRESS: "cyan",
                TaskStatus.COMPLETED:   "green",
                TaskStatus.CANCELLED:   "red",
            }.get(t.status, "dim")
            icon = t.status_icon()
            print(f"  #{t.id} {clr(icon + ' ' + t.status.value, status_color)} {t.subject}{owner_str}{blocked_str}")
        return True

    if subcmd == "create":
        if not rest:
            err("Usage: /tasks create <subject>")
            return True
        t = create_task(rest, description="(created via REPL)")
        ok(f"Task #{t.id} created: {t.subject}")
        return True

    if subcmd in STATUS_MAP:
        new_status = STATUS_MAP[subcmd]
        if not rest:
            err(f"Usage: /tasks {subcmd} <task_id>")
            return True
        task, fields = update_task(rest, status=new_status)
        if task is None:
            err(f"Task #{rest} not found.")
        else:
            ok(f"Task #{task.id} → {new_status}: {task.subject}")
        return True

    if subcmd == "delete":
        if not rest:
            err("Usage: /tasks delete <task_id>")
            return True
        removed = delete_task(rest)
        if removed:
            ok(f"Task #{rest} deleted.")
        else:
            err(f"Task #{rest} not found.")
        return True

    if subcmd == "get":
        if not rest:
            err("Usage: /tasks get <task_id>")
            return True
        t = get_task(rest)
        if t is None:
            err(f"Task #{rest} not found.")
            return True
        print(f"  #{t.id} [{t.status.value}] {t.subject}")
        print(f"  Description: {t.description}")
        if t.owner:         print(f"  Owner:       {t.owner}")
        if t.active_form:   print(f"  Active form: {t.active_form}")
        if t.blocked_by:    print(f"  Blocked by:  #{', #'.join(t.blocked_by)}")
        if t.blocks:        print(f"  Blocks:      #{', #'.join(t.blocks)}")
        if t.metadata:      print(f"  Metadata:    {t.metadata}")
        print(f"  Created: {t.created_at[:19]}  Updated: {t.updated_at[:19]}")
        return True

    if subcmd == "clear":
        clear_all_tasks()
        ok("All tasks deleted.")
        return True

    err(f"Unknown tasks subcommand: {subcmd}  (try /tasks or /help)")
    return True


# ── SSJ Developer Mode ─────────────────────────────────────────────────────

def cmd_ssj(args: str, state, config) -> bool:
    """SSJ Developer Mode — Interactive power menu for project workflows.

    Usage: /ssj
    """
    _SSJ_MENU = (
        clr("\n╭─ SSJ Developer Mode ", "dim") + clr("⚡", "yellow") + clr(" ─────────────────────────", "dim")
        + "\n│"
        + "\n│  " + clr(" 1.", "bold") + " 💡  Brainstorm — Multi-persona AI debate"
        + "\n│  " + clr(" 2.", "bold") + " 📋  Show TODO — View todo_list.txt"
        + "\n│  " + clr(" 3.", "bold") + " 👷  Worker — Auto-implement pending tasks"
        + "\n│  " + clr(" 4.", "bold") + " 🧠  Debate — Expert debate on a file"
        + "\n│  " + clr(" 5.", "bold") + " ✨  Propose — AI improvement for a file"
        + "\n│  " + clr(" 6.", "bold") + " 🔎  Review — Quick file analysis"
        + "\n│  " + clr(" 7.", "bold") + " 📘  Readme — Auto-generate README.md"
        + "\n│  " + clr(" 8.", "bold") + " 💬  Commit — AI-suggested commit message"
        + "\n│  " + clr(" 9.", "bold") + " 🧪  Scan — Analyze git diff"
        + "\n│  " + clr("10.", "bold") + " 📝  Promote — Idea to tasks"
        + "\n│  " + clr(" 0.", "bold") + " 🚪  Exit SSJ Mode"
        + "\n│"
        + "\n" + clr("╰──────────────────────────────────────────────", "dim")
    )

    from pathlib import Path

    def _pick_file(prompt_text="  Select file #: ", exts=None):
        """Show numbered file list and let user pick one."""
        files = sorted([
            f for f in Path(".").iterdir()
            if f.is_file() and not f.name.startswith(".")
            and (exts is None or f.suffix in exts)
        ])
        if not files:
            err("No matching files found in current directory.")
            return None
        menu_text = clr(f"\n  📂 Files in {Path.cwd().name}/", "cyan")
        for i, f in enumerate(files, 1):
            menu_text += ("\n" + f"  {i:3d}. {f.name}")
        sel = ask_input_interactive(clr(prompt_text, "cyan"), config, menu_text).strip()
        if sel.isdigit() and 1 <= int(sel) <= len(files):
            return str(files[int(sel) - 1])
        elif sel:  # typed a filename directly
            return sel
        err("Invalid selection.")
        return None

    print(_SSJ_MENU)

    while True:
        try:
            choice = ask_input_interactive(clr("\n  ⚡ SSJ » ", "yellow", "bold"), config, _SSJ_MENU).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice.startswith("/"):
            # Pass slash commands through to dulus — exit SSJ and let REPL handle it
            return ("__ssj_passthrough__", choice)

        if choice == "0" or choice.lower() in ("exit", "q"):
            ok("Exiting SSJ Mode.")
            break

        elif choice == "1":
            topic = ask_input_interactive(clr("  Topic (Enter for general): ", "cyan"), config).strip()
            return ("__ssj_cmd__", "brainstorm", topic)

        elif choice == "2":
            todo_path = Path("brainstorm_outputs") / "todo_list.txt"
            if todo_path.exists():
                content = todo_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                task_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith("- [")]
                pending_lines = [(i, l) for i, l in task_lines if l.strip().startswith("- [ ]")]
                done_lines = [(i, l) for i, l in task_lines if l.strip().startswith("- [x]")]
                pending = len(pending_lines)
                done = len(done_lines)
                print(clr(f"\n  📋 TODO List ({done} done / {pending} pending):", "cyan"))
                print(clr("  " + "─" * 46, "dim"))
                for _, ln in done_lines:
                    label = ln.strip()[5:].strip()
                    print(clr(f"       ✓ {label}", "green"))
                for num, (_, ln) in enumerate(pending_lines, 1):
                    label = ln.strip()[5:].strip()
                    print(f"  {num:3d}. ○ {label}")
                print(clr("  " + "─" * 46, "dim"))
                print(clr("  Tip: use Worker (3) with pending task #s e.g. 1,4,6", "dim"))
            else:
                err("No todo_list.txt found. Run Brainstorm (1) first.")
            print(_SSJ_MENU)
            continue

        elif choice == "3":
            # Preview current default todo file status
            _default_todo = Path("brainstorm_outputs") / "todo_list.txt"
            if _default_todo.exists():
                _lines = _default_todo.read_text(encoding="utf-8", errors="replace").splitlines()
                _pend  = sum(1 for l in _lines if l.strip().startswith("- [ ]"))
                _done  = sum(1 for l in _lines if l.strip().startswith("- [x]"))
                print(clr(f"\n  📋 Default todo: brainstorm_outputs/todo_list.txt  "
                          f"({_done} done / {_pend} pending)", "cyan"))
            else:
                print(clr("\n  ℹ  No brainstorm_outputs/todo_list.txt yet. "
                          "You can specify a path or generate one from a brainstorm file.", "dim"))
            print(clr("  ──────────────────────────────────────────────────────", "dim"))
            print(clr("  Note: todo file must contain tasks in '- [ ] task' format.", "dim"))
            todo_input = ask_input_interactive(clr("  Path to todo file (Enter for default): ", "cyan"), config).strip()

            # Track original md path in case we need Promote→Worker chain
            _original_md = None
            if todo_input.endswith(".md") and "brainstorm_" in todo_input:
                warn("That looks like a brainstorm output file, not a todo list.")
                _suggested = str(Path(todo_input).parent / "todo_list.txt")
                print(clr(f"  Suggested todo path: {_suggested}", "yellow"))
                _fix = ask_input_interactive(clr("  Use that path instead? [Y/n]: ", "cyan"), config).strip().lower()
                if _fix in ("", "y"):
                    _original_md = todo_input
                    todo_input = _suggested

            task_num = ask_input_interactive(clr("  Task # (Enter for all, or e.g. 1,4,6): ", "cyan"), config).strip()
            workers  = ask_input_interactive(clr("  Max tasks this session (Enter for all): ", "cyan"), config).strip()

            # Resolve the final path to check existence
            _resolved = Path(todo_input) if todo_input else _default_todo
            if not _resolved.exists():
                if _original_md and Path(_original_md).exists():
                    # Offer to auto-generate todo_list.txt from the brainstorm .md, then run worker
                    print(clr(f"\n  ℹ  {_resolved} not found.", "yellow"))
                    _gen = ask_input_interactive(clr(f"  Generate todo_list.txt from {Path(_original_md).name} first, then run Worker? [Y/n]: ",
                                     "cyan"), config).strip().lower()
                    if _gen in ("", "y"):
                        return ("__ssj_promote_worker__",
                                _original_md, str(_resolved), task_num, workers)
                # No auto-generate possible — let cmd_worker show the error
            arg_parts = []
            if todo_input:
                arg_parts.append(f"--path {todo_input}")
            if task_num:
                arg_parts.append(f"--tasks {task_num}")
            if workers and workers.isdigit() and int(workers) >= 1:
                arg_parts.append(f"--workers {workers}")
            return ("__ssj_cmd__", "worker", " ".join(arg_parts))

        elif choice == "4":
            filepath = _pick_file("  File to debate #: ")
            if not filepath:
                continue
            _nagents_raw = ask_input_interactive(clr("  Number of debate agents (Enter for 2): ", "cyan"), config).strip()
            try:
                _nagents = max(2, int(_nagents_raw)) if _nagents_raw else 2
            except ValueError:
                err("Invalid number, using 2.")
                _nagents = 2
            _rounds = max(1, (_nagents * 2 - 1))
            # Derive output path: same dir as debated file, stem + _debate_HHMMSS.md
            _fp = Path(filepath)
            _debate_out = str(_fp.parent / f"{_fp.stem}_debate_{time.strftime('%H%M%S')}.md")
            info(f"Debate result will be saved to: {_debate_out}")
            # Return structured sentinel so the handler can drive each round separately
            return ("__ssj_debate__", filepath, _nagents, _rounds, _debate_out)

        elif choice == "5":
            filepath = _pick_file("  File to improve #: ")
            if not filepath:
                continue
            return ("__ssj_query__", (
                f"Read {filepath} and propose specific, concrete improvements. "
                f"For each improvement: explain the problem, show the fix, and apply it with Edit if the user approves. "
                f"Focus on bugs, performance, readability, and security. Be concise."
            ))

        elif choice == "6":
            filepath = _pick_file("  File to review #: ")
            if not filepath:
                continue
            return ("__ssj_query__", (
                f"Read {filepath} and provide a thorough code review. "
                f"Rate it 1-10 on: readability, maintainability, performance, security. "
                f"List specific issues with line numbers. Do NOT modify the file, review only."
            ))

        elif choice == "7":
            filepath = _pick_file("  Generate README for file #: ", exts={".py", ".js", ".ts", ".go", ".rs"})
            if not filepath:
                continue
            return ("__ssj_query__", (
                f"Read ONLY the file {filepath}. Based on that single file, generate a professional README.md. "
                f"Include: project description, features, installation, usage with examples, "
                f"and contributing guidelines. Use the Write tool to create README.md. "
                f"Do NOT read other files unless the user explicitly asks."
            ))

        elif choice == "8":
            return ("__ssj_query__", (
                "Run 'git diff --cached' and 'git diff' using Bash, analyze ALL changes, "
                "and suggest a concise, descriptive commit message following conventional commits format. "
                "Show the suggested message and ask for confirmation before committing."
            ))

        elif choice == "9":
            return ("__ssj_query__", (
                "Run 'git status' and 'git diff' using Bash. Analyze the current state of the repository. "
                "Summarize: what files changed, what was added/removed, potential issues in the changes, "
                "and suggest next steps."
            ))

        elif choice == "10":
            brainstorm_dir = Path("brainstorm_outputs")
            if not brainstorm_dir.exists() or not list(brainstorm_dir.glob("*.md")):
                err("No brainstorm outputs found. Run Brainstorm (1) first.")
                continue
            latest = sorted(brainstorm_dir.glob("*.md"))[-1]
            return ("__ssj_query__", (
                f"Read the brainstorm file {latest} and extract all actionable ideas. "
                f"Convert each idea into a task with checkbox format (- [ ] task description). "
                f"Write them to brainstorm_outputs/todo_list.txt using the Write tool. Prioritize by impact."
            ))

        else:
            err("Invalid option. Pick 0-10.")

    return True


# ── Kill Tmux command ─────────────────────────────────────────────────────

def cmd_kill_tmux(_args: str, _state, config) -> bool:
    """Kill all tmux and psmux sessions.
    
    Usage: /kill_tmux
    Useful when tmux/psmux sessions are stuck or causing problems.
    """
    import subprocess
    from common import info, ok, err
    
    killed = []
    
    # Try tmux kill-server
    try:
        result = subprocess.run(["tmux", "kill-server"], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5)
        if result.returncode == 0:
            killed.append("tmux")
    except Exception:
        pass
    
    # Try psmux kill-server
    try:
        result = subprocess.run(["psmux", "kill-server"], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5)
        if result.returncode == 0:
            killed.append("psmux")
    except Exception:
        pass
    
    if killed:
        ok(f"Killed {', '.join(killed)} servers.")
    else:
        info("No tmux/psmux servers found (or they were already stopped).")
    
    return True


# ── Worker command ─────────────────────────────────────────────────────────

def cmd_worker(args: str, state, config) -> bool:
    """Auto-implement pending tasks from a todo_list.txt file.

    Usage:
      /worker                              — all pending tasks, default path
      /worker 1,4,6                        — specific task numbers, default path
      /worker --path /some/todo.txt        — all tasks from custom path
      /worker --path /some/todo.txt 1,4,6  — specific tasks from custom path
      --tasks 1,4,6                        — explicit task selection flag
      --workers N                          — run at most N tasks this session
    """
    import shlex
    from pathlib import Path

    # ── Arg parsing ───────────────────────────────────────────────────────
    raw = args.strip()
    todo_path_override = None
    task_nums_str      = None
    max_workers        = None

    tokens = raw.split() if raw else []
    remaining = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--path" and i + 1 < len(tokens):
            todo_path_override = tokens[i + 1]
            i += 2
        elif tok.startswith("--path="):
            todo_path_override = tok[len("--path="):]
            i += 1
        elif tok == "--tasks" and i + 1 < len(tokens):
            task_nums_str = tokens[i + 1]
            i += 2
        elif tok.startswith("--tasks="):
            task_nums_str = tok[len("--tasks="):]
            i += 1
        elif tok == "--workers" and i + 1 < len(tokens):
            max_workers = tokens[i + 1]
            i += 2
        elif tok.startswith("--workers="):
            max_workers = tok[len("--workers="):]
            i += 1
        else:
            remaining.append(tok)
            i += 1

    # Remaining token: if it looks like a path use it, else treat as task nums
    if remaining:
        leftover = " ".join(remaining)
        if todo_path_override is None and (
            "/" in leftover or "\\" in leftover
            or leftover.endswith(".txt") or leftover.endswith(".md")
        ):
            todo_path_override = leftover
        elif task_nums_str is None:
            task_nums_str = leftover

    # Resolve todo path
    todo_path = Path(todo_path_override) if todo_path_override else Path("brainstorm_outputs") / "todo_list.txt"

    if not todo_path.exists():
        err(f"No todo file found at {todo_path}.")
        if not todo_path_override:
            info("Run /brainstorm first, or specify a path with --path /your/todo.txt")
        return True

    # ── Load pending tasks ────────────────────────────────────────────────
    content = todo_path.read_text(encoding="utf-8", errors="replace")
    lines   = content.splitlines()
    pending = [(i, ln) for i, ln in enumerate(lines) if ln.strip().startswith("- [ ]")]

    if not pending:
        # Check if file has *any* task lines at all to give a clearer message
        any_tasks = any(ln.strip().startswith("- [") for ln in lines)
        if any_tasks:
            ok(f"All tasks completed! No pending items in {todo_path}.")
        else:
            err(f"No task lines found in {todo_path}.")
            info("Worker expects lines like:  - [ ] task description")
            if str(todo_path).endswith(".md") and "brainstorm_" in str(todo_path):
                _suggested = str(Path(todo_path).parent / "todo_list.txt")
                info(f"If you meant the todo list, try: /worker --path {_suggested}")
        return True

    # ── Filter by task numbers ────────────────────────────────────────────
    if task_nums_str:
        try:
            nums = [int(x.strip()) for x in task_nums_str.split(",") if x.strip()]
            selected = []
            for n in nums:
                if 1 <= n <= len(pending):
                    selected.append(pending[n - 1])
                else:
                    err(f"Task #{n} out of range (1-{len(pending)}).")
                    return True
            pending = selected
        except ValueError:
            err(f"Invalid task number(s): '{task_nums_str}'. Use e.g. 1,4,6")
            return True

    # ── Apply worker batch limit ──────────────────────────────────────────
    worker_count = len(pending)  # default: run all pending tasks
    if max_workers is not None:
        try:
            worker_count = max(1, int(max_workers))
        except ValueError:
            err(f"Invalid --workers value: '{max_workers}'. Must be a positive integer.")
            return True
    if worker_count < len(pending):
        info(f"Workers: {worker_count} — running first {worker_count} of {len(pending)} pending task(s) this session.")
        pending = pending[:worker_count]

    ok(f"Worker starting — {len(pending)} task(s) | file: {todo_path}")
    info("Pending tasks:")
    for n, (_, ln) in enumerate(pending, 1):
        print(f"  {n}. {ln.strip()}")

    # ── Build prompts ─────────────────────────────────────────────────────
    worker_prompts = []
    for line_idx, task_line in pending:
        task_text = task_line.strip().replace("- [ ] ", "", 1)
        prompt = (
            f"You are the Worker. Your job is to implement this task:\n\n"
            f"  {task_text}\n\n"
            f"Instructions:\n"
            f"1. Read the relevant files, understand the codebase.\n"
            f"2. Implement the task — write code, edit files, run tests.\n"
            f"3. When DONE, use the Edit tool to mark this exact line in {todo_path}:\n"
            f'   Change "- [ ] {task_text}" to "- [x] {task_text}"\n'
            f"4. If you CANNOT complete it, leave it as - [ ] and explain why.\n"
            f"5. Be concise. Act, don't explain."
        )
        worker_prompts.append((line_idx, task_text, prompt))

    return ("__worker__", worker_prompts)


# ── Telegram bot ───────────────────────────────────────────────────────────

_telegram_thread = None
_telegram_stop = threading.Event()

def _tg_api(token: str, method: str, params: dict = None):
    """Call Telegram Bot API. Returns parsed JSON or None on error."""
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception:
        return None

def _tg_register_commands(token: str) -> bool:
    """Register slash commands with Telegram so the native UI suggests them as
    the user types '/'. Called once when the bridge starts.

    Telegram rules: command name must be 1-32 chars, lowercase letters/digits/
    underscores; description up to 256 chars; max 100 commands per bot.
    """
    import re
    cmds = []
    for name, (desc, _subs) in _CMD_META.items():
        # Filter illegal names (Telegram: ^[a-z0-9_]{1,32}$)
        if not re.match(r"^[a-z0-9_]{1,32}$", name):
            continue
        short_desc = (desc or name).strip()[:256] or name
        cmds.append({"command": name, "description": short_desc})
        if len(cmds) >= 100:
            break
    result = _tg_api(token, "setMyCommands", {"commands": cmds})
    return bool(result and result.get("ok"))


def _tg_send(token: str, chat_id: int, text: str):
    """Send a message to a Telegram chat, splitting if too long."""
    MAX = 4000  # Telegram limit is 4096, leave margin
    chunks = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    for chunk in chunks:
        # Try Markdown first, fallback to plain text if parse fails
        result = _tg_api(token, "sendMessage", {"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"})
        if not result or not result.get("ok"):
            _tg_api(token, "sendMessage", {"chat_id": chat_id, "text": chunk})

def _tg_typing_loop(token: str, chat_id: int, stop_event: threading.Event, config: dict = None):
    """Send 'typing...' indicator every 4 seconds until stop_event is set."""
    while not stop_event.is_set():
        if config and config.get("_tg_pause_typing"):
            stop_event.wait(1)
            continue
        _tg_api(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
        stop_event.wait(4)

def _parse_chat_ids(value) -> list[int]:
    """Accept int, list, or comma-separated string ('123,456,,') → list[int].
    Empty parts (from trailing commas) are dropped.
    """
    if not value:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        out = []
        for x in value:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(value, str):
        out = []
        for p in value.split(","):
            p = p.strip()
            if not p:
                continue
            try:
                out.append(int(p))
            except ValueError:
                continue
        return out
    return []

def _tg_get_chat_ids(config: dict) -> list[int]:
    """Read configured chat ids from config. Supports legacy single int and
    new comma-separated string / list."""
    ids = _parse_chat_ids(config.get("telegram_chat_ids")) or _parse_chat_ids(config.get("telegram_chat_id"))
    return ids

def _tg_poll_loop(token: str, chat_ids, config: dict):
    """Long-polling loop. chat_ids: int (legacy) or list[int].
    All listed users are authorized; replies go back to whoever sent the msg.
    """
    if isinstance(chat_ids, int):
        chat_ids = [chat_ids]
    chat_ids = list(chat_ids or [])
    authorized = set(chat_ids)

    run_query_cb = config.get("_run_query_callback")
    # Flush old messages so we don't process stale commands on startup
    flush = _tg_api(token, "getUpdates", {"offset": -1, "timeout": 0})
    if flush and flush.get("ok") and flush.get("result"):
        offset = flush["result"][-1]["update_id"] + 1
    else:
        offset = 0
    # Register slash commands with Telegram so the UI autosuggests them.
    try:
        _tg_register_commands(token)
    except Exception:
        pass
    # Notify all configured users that the bot is online
    for cid in chat_ids:
        _tg_send(token, cid, "🟢 Dulus\nSend me a message and I'll process it.")

    while not _telegram_stop.is_set():
        try:
            result = _tg_api(token, "getUpdates", {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message"]
            })
            if not result or not result.get("ok"):
                _telegram_stop.wait(5)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                if not msg:
                    continue  # skip non-message updates (edits, callbacks, etc.)
                msg_chat_id = msg.get("chat", {}).get("id")
                text = sanitize_text(msg.get("text", ""))

                if msg_chat_id not in authorized:
                    _tg_api(token, "sendMessage", {
                        "chat_id": msg_chat_id,
                        "text": "⛔ Unauthorized."
                    })
                    continue

                # Track who is currently active so other code (permission
                # prompts, etc.) can reply to the right user.
                config["_active_tg_chat_id"] = msg_chat_id
                # Bind chat_id to the originating user so all downstream
                # references in this iteration (and closures spawned below)
                # send replies back to whoever messaged.
                chat_id = msg_chat_id

                # ── Handle photo messages from Telegram ──
                photo_list = msg.get("photo")
                if photo_list:
                    caption = msg.get("caption", "").strip() or "What do you see in this image? Describe it in detail."
                    file_id = photo_list[-1]["file_id"]  # largest size
                    try:
                        file_info = _tg_api(token, "getFile", {"file_id": file_id})
                        if file_info and file_info.get("ok"):
                            file_path = file_info["result"]["file_path"]
                            import urllib.request, base64
                            url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                            with urllib.request.urlopen(url, timeout=30) as resp:
                                img_bytes = resp.read()
                            b64 = base64.b64encode(img_bytes).decode("utf-8")
                            size_kb = len(img_bytes) / 1024
                            config["_pending_image"] = b64
                            text = caption
                            print(clr(f"\n  📩 Telegram: 📷 image ({size_kb:.0f} KB) + \"{caption[:50]}\"", "cyan"))
                        else:
                            _tg_send(token, chat_id, "⚠ Could not download image.")
                            continue
                    except Exception as e:
                        _tg_send(token, chat_id, f"⚠ Image error: {e}")
                        continue

                is_transcribed = False
                # ── Handle voice messages from Telegram ──
                voice_msg = msg.get("voice") or msg.get("audio")
                if voice_msg and not text:
                    file_id = voice_msg["file_id"]
                    duration = voice_msg.get("duration", 0)
                    try:
                        file_info = _tg_api(token, "getFile", {"file_id": file_id})
                        if file_info and file_info.get("ok"):
                            file_path = file_info["result"]["file_path"]
                            import urllib.request
                            url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                            with urllib.request.urlopen(url, timeout=30) as resp:
                                audio_bytes = resp.read()
                            size_kb = len(audio_bytes) / 1024
                            _tg_send(token, chat_id, f"🎙 Voice received ({duration}s, {size_kb:.0f} KB) — transcribing...")
                            # NOTE: We intentionally do NOT print the intermediate
                            # voice notification to the CLI. Only the final transcription
                            # (handled below at line ~5663) is shown locally to avoid
                            # accumulation of Telegram notifications in the terminal.
                            from voice import transcribe_audio_file
                            suffix = ".ogg" if msg.get("voice") else ".mp3"
                            transcribed = transcribe_audio_file(audio_bytes, suffix=suffix)
                            if transcribed:
                                _tg_send(token, chat_id, f"📝 Transcribed: \"{transcribed}\"")
                                text = transcribed
                                is_transcribed = True
                            else:
                                _tg_send(token, chat_id, "⚠ No speech detected in voice message.")
                                continue
                        else:
                            _tg_send(token, chat_id, "⚠ Could not download voice message.")
                            continue
                    except Exception as e:
                        _tg_send(token, chat_id, f"⚠ Voice error: {e}")
                        continue

                if not text:
                    continue

                # Intercept text if a permission prompt is waiting
                evt = config.get("_tg_input_event")
                if evt:
                    config["_tg_input_value"] = text
                    evt.set()
                    continue

                # Handle Telegram bot commands
                if text.strip().startswith("/"):
                    tg_cmd = text.strip().lower()
                    if tg_cmd in ("/stop", "/off"):
                        _tg_send(token, chat_id, "🔴 Telegram bridge stopped.")
                        _telegram_stop.set()
                        break
                    elif tg_cmd == "/start":
                        _tg_send(token, chat_id, "🟢 dulus bridge is active. Send me anything.")
                        continue
                    # Pass dulus slash commands through handle_slash
                    # Run in a separate thread so interactive commands
                    # (ask_input_interactive) don't block the polling loop.
                    slash_cb = config.get("_handle_slash_callback")
                    if slash_cb:
                        def _slash_runner(_slash_text, _token, _chat_id):
                            import io, sys, re
                            _tg_thread_local.active = True
                            # Capture stdout so printed output reaches Telegram
                            old_stdout = sys.stdout
                            buf = io.StringIO()
                            sys.stdout = buf
                            try:
                                cmd_type = slash_cb(_slash_text)
                            except Exception as e:
                                sys.stdout = old_stdout
                                _tg_send(_token, _chat_id, f"⚠ Error: {e}")
                                return
                            finally:
                                _tg_thread_local.active = False
                            sys.stdout = old_stdout
                            captured = buf.getvalue()
                            # Strip ANSI escape codes for Telegram
                            captured_clean = re.sub(r'\x1b\[[0-9;]*m', '', captured)
                            # Send captured output (commands like /plugin list print here)
                            if captured_clean.strip():
                                MAX_TG = 4000
                                out = captured_clean.strip()
                                if len(out) > MAX_TG:
                                    out = out[:MAX_TG] + "\n\n…truncated"
                                _tg_send(_token, _chat_id, f"```{out}```")
                            elif cmd_type == "simple":
                                cmd_name = _slash_text.strip().split()[0]
                                _tg_send(_token, _chat_id, f"✅ {cmd_name} executed.")
                            # Query commands — ALSO grab the model response
                            if cmd_type == "query":
                                tg_state = config.get("_state")
                                if tg_state and tg_state.messages:
                                    for m in reversed(tg_state.messages):
                                        if m.get("role") == "assistant":
                                            content = m.get("content", "")
                                            if isinstance(content, list):
                                                parts = []
                                                for block in content:
                                                    if isinstance(block, dict) and block.get("type") == "text":
                                                        parts.append(block["text"])
                                                    elif isinstance(block, str):
                                                        parts.append(block)
                                                content = "\n".join(parts)
                                            if content:
                                                _tg_send(_token, _chat_id, content)
                                            break
                        threading.Thread(target=_slash_runner, args=(text, token, chat_id), daemon=True).start()
                    continue

                # Show on local terminal safely (avoid corrupting prompt_toolkit)
                label = "🎙 Transcribed" if is_transcribed else "📩 Telegram"
                try:
                    import input as dulus_input
                    dulus_input.safe_print_notification(clr(f"  {label}: {text}", "cyan"))
                except Exception:
                    print(clr(f"\n  {label}: {text}", "cyan"))

                # Run through dulus's model in a separate thread to prevent blocking poll loop
                def _bg_runner(q_text, chat_token, chat_id):
                    _typing_stop = threading.Event()
                    _typing_t = threading.Thread(target=_tg_typing_loop, args=(chat_token, chat_id, _typing_stop, config), daemon=True)
                    _typing_t.start()
                    
                    # Clear the input bar so stale text doesn't persist after a
                    # Telegram turn (thread-safe: invalidate() is designed for
                    # cross-thread use).
                    try:
                        import input as dulus_input
                        if dulus_input._split_buffer:
                            dulus_input._split_buffer.text = ""
                        if dulus_input._split_app:
                            dulus_input._split_app.invalidate()
                    except Exception:
                        pass
                    
                    if run_query_cb:
                        try:
                            config["_telegram_incoming"] = True
                            run_query_cb(q_text)
                        except Exception as e:
                            _typing_stop.set()
                            _tg_send(chat_token, chat_id, f"⚠ Error: {e}")
                            return
                        _typing_stop.set()
                        # Grab the last assistant response from state
                        state = config.get("_state")
                        if state and state.messages:
                            for m in reversed(state.messages):
                                if m.get("role") == "assistant":
                                    content = m.get("content", "")
                                    if isinstance(content, list):
                                        parts = []
                                        for block in content:
                                            if isinstance(block, dict) and block.get("type") == "text":
                                                parts.append(block["text"])
                                            elif isinstance(block, str):
                                                parts.append(block)
                                        content = "\n".join(parts)
                                    if content:
                                        _tg_send(chat_token, chat_id, content)
                                    break
                        return

                    # No REPL running — check if daemon allows external triggers
                    _typing_stop.set()
                    try:
                        from config import load_config
                        fresh_config = load_config()
                    except Exception:
                        fresh_config = config
                    if not fresh_config.get("daemon"):
                        _tg_send(chat_token, chat_id, "🔴 No REPL session active. Use `/daemon on` to allow external triggers, or open Dulus locally.")
                        return
                    import subprocess, os, sys
                    dulus_script = os.path.abspath(sys.argv[0] if sys.argv[0].endswith('.py') else __file__)
                    try:
                        proc = subprocess.run(
                            [sys.executable, dulus_script, "--print", q_text],
                            capture_output=True, text=True, timeout=300,
                            cwd=os.path.dirname(dulus_script)
                        )
                        out = proc.stdout.strip()
                        err_out = proc.stderr.strip()
                        full = (out + "\n" + err_out).strip()
                        if not full:
                            full = "⚠ No response from Dulus."
                        MAX_TG = 4000
                        if len(full) > MAX_TG:
                            full = full[:MAX_TG] + "\n\n…truncated"
                        _tg_send(chat_token, chat_id, full)
                    except Exception as e:
                        _tg_send(chat_token, chat_id, f"⚠ Dulus process error: {e}")

                threading.Thread(target=_bg_runner, args=(text, token, chat_id), daemon=True).start()
        except Exception:
            _telegram_stop.wait(5)

    global _telegram_thread
    _telegram_thread = None


def _run_daemon(config: dict) -> None:
    """Daemon mode — keep Dulus alive in the background for Telegram bridges.

    No REPL, no GUI. Just a persistent state + callback loop so external
    triggers (Telegram) can wake the agent at any time.
    """
    from agent import AgentState, run as agent_run
    from checkpoint import set_session
    from common import ok, info, warn, err, clr

    session_id = config.get("_session_id") or uuid.uuid4().hex[:8]
    set_session(session_id)

    state = AgentState()
    config["_state"] = state
    config["_session_id"] = session_id
    config["_last_interaction_time"] = time.time()

    # Same callback used by the REPL so Telegram / IPC can trigger runs.
    # The `agent.run()` signature is (user_message, state, config, system_prompt, ...)
    # — earlier I called it with the wrong arg order + a non-existent
    # `is_background` kwarg, which made every Telegram/IPC turn raise
    # silently and never actually answer the user. Fixed now.
    def _daemon_run_query(msg):
        qlock = config.get("_query_lock")
        if qlock:
            qlock.acquire()
        try:
            import sys
            import checkpoint as ckpt
            from agent import run as agent_run
            from context import build_system_prompt
            from dulus import save_latest, _tg_get_chat_ids, _telegram_stop, _tg_send
            
            sys_prompt = build_system_prompt(config)
            is_telegram_turn = config.get("_telegram_incoming", False)
            # Basic heuristic: if the message starts with System Automated Event, it's a background event
            is_background = msg.startswith("(System Automated Event)")
            
            if is_background and not is_telegram_turn:
                ttok = config.get("telegram_token")
                _tids = _tg_get_chat_ids(config)
                tchat = config.get("_active_tg_chat_id") or (_tids[0] if _tids else 0)
                if ttok and tchat and _telegram_stop and not _telegram_stop.is_set():
                    import threading as _tg_thread
                    from dulus import _tg_send
                    _tg_thread.Thread(target=_tg_send, args=(ttok, tchat, f"⚙ {msg}"), daemon=True).start()
            
            for ev in agent_run(msg, state, config, sys_prompt):
                if "webchat_server" in sys.modules and sys.modules["webchat_server"].is_running():
                    try:
                        import webchat_server as _wcs
                        r = _wcs._event_to_dict(ev)
                        if r:
                            if isinstance(r, tuple):
                                payload, wait_event = r
                                _wcs.broadcast_event("chunk", payload)
                                wait_event.wait(timeout=2.0)
                            else:
                                _wcs.broadcast_event("chunk", r)
                    except Exception:
                        pass
                _ = ev
            
            try:
                tracked = ckpt.get_tracked_edits()
                last_snaps = ckpt.list_snapshots(session_id)
                skip = False
                if not tracked and last_snaps:
                    if len(state.messages) == last_snaps[-1].get("message_index", -1):
                        skip = True
                if not skip:
                    ckpt.make_snapshot(session_id, state, config, msg, tracked_edits=tracked)
                ckpt.reset_tracked()
            except Exception:
                pass
            
            try:
                save_latest("", state, config, mode="daemon")
            except Exception:
                pass

            # Broadcast background notifications to Telegram to maintain parity with REPL
            if is_background and not is_telegram_turn:
                ttok = config.get("telegram_token")
                _tids = _tg_get_chat_ids(config)
                tchat = config.get("_active_tg_chat_id") or (_tids[0] if _tids else 0)
                
                if ttok and tchat and _telegram_stop and not _telegram_stop.is_set():
                    if state.messages and state.messages[-1].get("role") == "assistant":
                        ans_content = state.messages[-1].get("content", "")
                        if isinstance(ans_content, list):
                            parts = [b["text"] if isinstance(b, dict) else str(b) for b in ans_content if (isinstance(b, dict) and b.get("type") == "text") or isinstance(b, str)]
                            ans_content = "\n".join(parts)
                        if ans_content:
                            import threading as _tg_thread
                            _tg_thread.Thread(target=_tg_send, args=(ttok, tchat, ans_content), daemon=True).start()

        except Exception as _e:
            err(f"daemon run_query error: {type(_e).__name__}: {_e}")
        finally:
            if qlock:
                qlock.release()
    config["_run_query_callback"] = _daemon_run_query

    # Register slash-command callback so Telegram and WebChat can run
    # /commands in daemon mode (without this, slash_cb is None and
    # commands are silently dropped).
    def _daemon_handle_slash(line: str):
        """Process a /command in daemon mode — mirrors the REPL callback."""
        result = handle_slash(line, state, config)
        if not isinstance(result, tuple):
            return "simple"
        if result[0] == "__brainstorm__":
            _, brain_prompt, brain_out_file = result
            _daemon_run_query(brain_prompt)
            _save_synthesis(state, brain_out_file)
            _todo_path = str(Path(brain_out_file).parent / "todo_list.txt")
            _daemon_run_query(
                f"Based on the Master Plan you just synthesized, generate a todo list file at {_todo_path}. "
                "Format: one task per line, each starting with '- [ ] '. "
                "Order by priority. Include ALL actionable items from the plan. "
                "Use the Write tool to create the file. Do NOT explain, just write the file now."
            )
        elif result[0] == "__worker__":
            _, worker_tasks = result
            for i, (line_idx, task_text, prompt) in enumerate(worker_tasks):
                _daemon_run_query(prompt)
        return "query"

    config["_handle_slash_callback"] = _daemon_handle_slash

    # Auto-start the webchat server alongside the daemon — always, by default.
    # The whole point of daemon mode is "headless Dulus serving every entry
    # point at once" (CLI via IPC, browser via WebChat, Telegram via bridge).
    # Skip only if config["webchat_disabled"] is true OR env var
    # DULUS_DAEMON_NO_WEB=1 is set (escape hatch for users who explicitly
    # don't want a browser endpoint exposed even on loopback).
    import os as _os_d
    _no_web = (
        config.get("webchat_disabled")
        or _os_d.environ.get("DULUS_DAEMON_NO_WEB") == "1"
    )
    if not _no_web:
        # If /bg start passed an explicit port through env, honor it.
        env_port = _os_d.environ.get("DULUS_BG_WEBCHAT_PORT")
        if env_port:
            try:
                config["_webchat_port"] = int(env_port)
            except ValueError:
                pass
        try:
            import urllib.request
            _wc_port = int(config.get("_webchat_port", 5000))
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{_wc_port}/api/health", timeout=0.5).read(1)
                info(f"WebChat already running on port {_wc_port} — not starting a second one.")
            except Exception:
                import webchat_server as _wc
                if not _wc.is_running():
                    _wc.start(state, config, port=_wc_port)
                    ok(f"WebChat started → http://127.0.0.1:{_wc_port}/")
        except Exception as _wce:
            warn(f"WebChat auto-start failed: {_wce}")

    # IPC server — same socket the REPL uses, so external `dulus "..."` calls
    # land in this daemon's session.
    if config.get("_ipc_thread") is None and not config.get("_ipc_disabled"):
        ti = threading.Thread(
            target=_ipc_server_loop, args=(config, state), daemon=True
        )
        config["_ipc_thread"] = ti
        ti.start()

    # Job Sentinel: Detect background completions and wake up the agent
    if config.get("_job_sentinel_thread") is None:
        tj = threading.Thread(target=_job_sentinel_loop, args=(config, state), daemon=True)
        config["_job_sentinel_thread"] = tj
        tj.start()

    # 'accent' / 'orange' are only present in some custom themes; default
    # palette is {blue, cyan, gray, green, magenta, red, white, yellow}.
    # KeyError here would crash the daemon before the user ever sees a prompt.
    try:
        print(clr("\n  ▲ DULUS DAEMON", "yellow", "bold"))
    except KeyError:
        print("\n  ▲ DULUS DAEMON")
    print(clr("  " + "─" * 40, "dim"))
    info(f"Session: {session_id}")
    info("Daemon active — waiting for triggers…")

    # Start Telegram bridge if previously configured
    token = config.get("telegram_token", "")
    chat_ids = _tg_get_chat_ids(config)
    if token and chat_ids:
        global _telegram_stop, _telegram_thread
        _telegram_stop = threading.Event()
        _telegram_thread = threading.Thread(
            target=_tg_poll_loop, args=(token, chat_ids, config), daemon=True
        )
        _telegram_thread.start()
        ok(f"Telegram bridge started  →  chats: {', '.join(str(c) for c in chat_ids)}")
    else:
        warn("No Telegram config found. Bridge not started.")
        info("Set it later with: /telegram <token> <chat_id>[,<chat_id>...]")

    info("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
            # Proactive watcher (optional, mirroring REPL behavior)
            if config.get("_proactive_enabled"):
                now = time.time()
                interval = config.get("_proactive_interval", 300)
                last = config.get("_last_interaction_time", now)
                if now - last >= interval:
                    config["_last_interaction_time"] = now
                    cb = config.get("_run_query_callback")
                    if cb:
                        cb(
                            f"(System Automated Event) You have been inactive for {interval} seconds. "
                            "Check for anything that needs attention and report briefly."
                        )
    except KeyboardInterrupt:
        print()
        info("Daemon shutting down…")
        if _telegram_stop is not None:
            _telegram_stop.set()
        if _telegram_thread and _telegram_thread.is_alive():
            _telegram_thread.join(timeout=3)
        ok("Daemon stopped.")
        sys.exit(0)


def cmd_telegram(args: str, _state, config) -> bool:
    """Telegram bot bridge — receive and respond to messages via Telegram.

    Usage: /telegram <bot_token> <chat_id>   — start the bridge
           /telegram stop                    — stop the bridge
           /telegram status                  — show current status

    First time: create a bot via @BotFather, then send any message to your bot
    and check https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat_id.
    Settings are saved so you only configure once.
    """
    global _telegram_thread, _telegram_stop
    from config import save_config

    parts = args.strip().split()

    # /telegram stop
    if parts and parts[0].lower() in ("stop", "off"):
        if _telegram_thread and _telegram_thread.is_alive():
            _telegram_stop.set()
            _telegram_thread.join(timeout=5)
            _telegram_thread = None
            ok("Telegram bridge stopped.")
        else:
            warn("Telegram bridge is not running.")
        return True

    # /telegram status
    if parts and parts[0].lower() == "status":
        running = _telegram_thread and _telegram_thread.is_alive()
        token = config.get("telegram_token", "")
        chat_ids = _tg_get_chat_ids(config)
        ids_str = ",".join(str(c) for c in chat_ids) if chat_ids else "(none)"
        if running:
            ok(f"Telegram bridge is running. Chat IDs: {ids_str}")
        elif token:
            info(f"Configured but not running. Use /telegram to start.")
        else:
            info("Not configured. Use /telegram <bot_token> <chat_id>[,<chat_id>...]")
        return True

    # /telegram <token> <chat_id>[,<chat_id>...] — configure and start
    if len(parts) >= 2:
        token = parts[0]
        chat_ids = _parse_chat_ids(parts[1])
        if not chat_ids:
            err("Chat ID must be a number (or comma-separated list, e.g. 12345,67890).")
            return True
        config["telegram_token"] = token
        # Persist as comma-separated string in the new key; clear the legacy
        # single-id key so the file stays clean.
        config["telegram_chat_ids"] = ",".join(str(c) for c in chat_ids)
        config.pop("telegram_chat_id", None)
        save_config(config)
        ok(f"Telegram config saved. Authorized chats: {', '.join(str(c) for c in chat_ids)}")
    else:
        # Try to use saved config
        token = config.get("telegram_token", "")
        chat_ids = _tg_get_chat_ids(config)

    if not token or not chat_ids:
        err("No config found. Usage: /telegram <bot_token> <chat_id>[,<chat_id>...]")
        return True

    # Already running?
    if _telegram_thread and _telegram_thread.is_alive():
        warn("Telegram bridge is already running. Use /telegram stop first.")
        return True

    # Verify token
    me = _tg_api(token, "getMe")
    if not me or not me.get("ok"):
        err("Invalid bot token. Check your token from @BotFather.")
        return True

    bot_name = me["result"].get("username", "unknown")
    ok(f"Connected to @{bot_name}. Starting bridge...")

    # Store state reference so the poll loop can read responses
    config["_state"] = _state

    _telegram_stop = threading.Event()
    _telegram_thread = threading.Thread(
        target=_tg_poll_loop, args=(token, chat_ids, config), daemon=True
    )
    _telegram_thread.start()
    ok(f"Telegram bridge active. Chat IDs: {', '.join(str(c) for c in chat_ids)}")
    info("Send messages to your bot — they'll be processed here.")
    info("Stop with /telegram stop or send /stop in Telegram.")
    return True


# ── Voice command ──────────────────────────────────────────────────────────

# Per-session voice language setting (BCP-47 code or "auto")
_voice_language: str = "auto"


def cmd_proactive(args: str, state, config) -> bool:
    """Manage proactive background polling.

    /proactive            — show current status
    /proactive 5m         — enable, trigger after 5 min of inactivity
    /proactive 30s / 1h   — enable with custom interval
    /proactive off        — disable
    """
    args = args.strip().lower()

    # Status query: no args → just print current state
    if not args:
        if config.get("_proactive_enabled"):
            interval = config.get("_proactive_interval", 300)
            info(f"Proactive background polling: ON  (triggering every {interval}s of inactivity)")
        else:
            info("Proactive background polling: OFF  (use /proactive 5m to enable)")
        return True

    # Explicit disable
    if args == "off":
        config["_proactive_enabled"] = False
        info("Proactive background polling: OFF")
        return True

    # Parse duration (e.g. "5m", "30s", "1h", or plain integer seconds)
    multiplier = 1
    val_str = args
    if args.endswith("m"):
        multiplier = 60
        val_str = args[:-1]
    elif args.endswith("h"):
        multiplier = 3600
        val_str = args[:-1]
    elif args.endswith("s"):
        val_str = args[:-1]

    try:
        val = int(val_str)
        config["_proactive_interval"] = val * multiplier
    except ValueError:
        err(f"Invalid duration: '{args}'. Use '5m', '30s', '1h', or 'off'.")
        return True

    config["_proactive_enabled"] = True
    config["_last_interaction_time"] = time.time()
    info(f"Proactive background polling: ON  (triggering every {config['_proactive_interval']}s of inactivity)")
    return True

def cmd_lite(args: str, state, config) -> bool:
    """
    Toggle LITE mode - reduces system prompt from ~10K to ~500 tokens.
    
    /lite         — toggle ON/OFF
    /lite on      — force ON (minimal rules)
    /lite off     — force OFF (full rules with all examples)
    
    LITE mode keeps only essential rules:
    - TmuxOffload for >5 seconds
    - SearchLastOutput for truncated
    - PrintToConsole for long text
    
    FULL mode includes detailed examples and explanations (~10K tokens).
    """
    from config import save_config
    
    current = config.get("lite_mode", False)
    
    # Parse args
    if args.strip().lower() == "on":
        new_val = True
    elif args.strip().lower() == "off":
        new_val = False
    else:
        # Toggle
        new_val = not current
    
    config["lite_mode"] = new_val
    save_config(config)
    
    if new_val:
        ok("🪶 LITE mode: ON")
        info("   System prompt reduced to ~500 tokens")
        info("   Essential rules only (TmuxOffload, SearchLastOutput, PrintToConsole)")
        info("   Run '/lite off' for full rules with examples")
    else:
        ok("📚 LITE mode: OFF (FULL mode)")
        info("   System prompt: ~10K tokens with detailed examples")
        info("   All guidelines, patterns, and best practices loaded")
        info("   Run '/lite' to switch back to lite mode")
    
    return True

def cmd_tts(args: str, state, config) -> bool:
    """TTS: toggle automatic voice output, or set language / provider / auto-listen.

    /tts                      — toggle TTS ON/OFF
    /tts lang <code>          — set language (es, en, fr, pt, ja…)
    /tts lang                 — show current language
    /tts provider             — show current TTS provider
    /tts provider <name>      — set provider (auto, azure, riva, openai, gtts, pyttsx3)
    /tts auto                 — toggle auto-listen: after Dulus speaks, mic opens for
                                your next reply (continuous voice conversation)
    /tts auto on|off          — explicit auto-listen toggle
    """
    from config import save_config

    arg = args.strip()
    parts = arg.split(None, 1)

    if parts and parts[0].lower() == "lang":
        code = parts[1].strip().lower() if len(parts) > 1 else ""
        if not code:
            current = config.get("tts_lang", "es")
            info(f"TTS language: {current}")
            return True
        config["tts_lang"] = code
        ok(f"TTS language set to: {code}")
        save_config(config)
        return True

    if parts and parts[0].lower() == "provider":
        name = parts[1].strip().lower() if len(parts) > 1 else ""
        valid = ("auto", "azure", "riva", "openai", "gtts", "pyttsx3")
        if not name:
            current = config.get("tts_provider", "auto")
            info(f"TTS provider: {current}")
            info(f"Available providers: {', '.join(valid)}")
            return True
        if name not in valid:
            err(f"Invalid provider '{name}'. Choose from: {', '.join(valid)}")
            return True
        config["tts_provider"] = name
        ok(f"TTS provider set to: {name}")
        save_config(config)
        return True

    if parts and parts[0].lower() == "voice":
        name = parts[1].strip() if len(parts) > 1 else ""
        if not name:
            current = config.get("azure_tts_voice", "")
            info(f"Azure TTS voice: {current or '(default by language)'}")
            info("Examples: es-ES-AlvaroNeural, es-ES-ElviraNeural, es-MX-JorgeNeural, en-US-GuyNeural")
            return True
        config["azure_tts_voice"] = name
        ok(f"Azure TTS voice set to: {name}")
        save_config(config)
        return True

    if parts and parts[0].lower() == "auto":
        sub = parts[1].strip().lower() if len(parts) > 1 else ""
        if sub in ("on", "true", "enable"):
            config["tts_auto_listen"] = True
        elif sub in ("off", "false", "disable"):
            config["tts_auto_listen"] = False
        else:
            config["tts_auto_listen"] = not config.get("tts_auto_listen", False)
        state_str = "ON" if config["tts_auto_listen"] else "OFF"
        ok(f"TTS auto-listen: {state_str}  (mic opens automatically after each spoken reply)")
        if config["tts_auto_listen"] and not config.get("tts_enabled", False):
            warn("Tip: also enable /tts so Dulus actually speaks.")
        save_config(config)
        return True

    arg_lower = arg.lower()
    if arg_lower in ["on", "true", "enable"]:
        config["tts_enabled"] = True
    elif arg_lower in ["off", "false", "disable"]:
        config["tts_enabled"] = False
    else:
        config["tts_enabled"] = not config.get("tts_enabled", False)

    state_str = "ON" if config["tts_enabled"] else "OFF"
    auto_state = "ON" if config.get("tts_auto_listen", False) else "OFF"
    provider = config.get("tts_provider", "auto")
    ok(f"Automatic TTS: {state_str}  (lang: {config.get('tts_lang', 'es')}, provider: {provider}, auto-listen: {auto_state})")
    save_config(config)
    return True


def cmd_say(args: str, state, config) -> bool:
    """TTS: speak the provided text immediately.

    /say <text>  — speak the given text using the best available backend
    """
    if not args.strip():
        print("  Usage: /say <text>")
        return True

    try:
        from voice import say
        say(args, provider=config.get("tts_provider", "auto"))
    except ImportError:
        err("voice package not available")
    except Exception as e:
        err(f"TTS error: {e}")
    return True


def cmd_voice(args: str, state, config) -> bool:
    """Voice input: record → STT → auto-submit as user message.

    /voice            — record once, transcribe, submit
    /voice status     — show backend availability
    /voice lang <code> — set STT language (e.g. zh, en, ja; 'auto' to reset)
    /voice device     — list and select input microphone
    """
    global _voice_language

    subcmd = args.strip().lower().split()[0] if args.strip() else ""
    rest = args.strip()[len(subcmd):].strip()

    # ── /voice device ──
    if subcmd == "device":
        try:
            from voice import list_input_devices
        except ImportError:
            err("sounddevice not available. Install with: pip install sounddevice")
            return True
        try:
            devices = list_input_devices()
        except Exception as e:
            err(f"Could not list devices: {e}")
            return True
        if not devices:
            err("No input devices found.")
            return True
        # Migrate from old non-persistent key
        if "_voice_device_index" in config and "voice_device_index" not in config:
            config["voice_device_index"] = config.pop("_voice_device_index")
        current = config.get("voice_device_index")
        print(clr("  🎙  Available input devices:", "cyan", "bold"))
        for d in devices:
            marker = " ◀" if current == d["index"] else ""
            print(f"  {d['index']:3d}. {d['name']}{clr(marker, 'green', 'bold')}")
        sel = ask_input_interactive(clr("  Select device # (Enter to cancel): ", "cyan"), config).strip()
        if sel.isdigit():
            idx = int(sel)
            valid = [d["index"] for d in devices]
            if idx in valid:
                config["voice_device_index"] = idx
                name = next(d["name"] for d in devices if d["index"] == idx)
                ok(f"Microphone set to: [{idx}] {name}")
                try:
                    from config import save_config
                    save_config(config)
                except Exception:
                    pass
            else:
                err(f"Invalid device index: {idx}")
        return True

    # ── /voice lang <code> ──
    if subcmd == "lang":
        if not rest:
            info(f"Current STT language: {_voice_language}  (use '/voice lang auto' to reset)")
            return True
        _voice_language = rest.lower()
        ok(f"STT language set to '{_voice_language}'")
        return True

    # ── /voice status ──
    if subcmd == "status":
        try:
            from voice import check_voice_deps, check_recording_availability, check_stt_availability
            from voice.stt import get_stt_backend_name
        except ImportError as e:
            err(f"voice package not available: {e}")
            return True

        rec_ok, rec_reason = check_recording_availability()
        stt_ok, stt_reason = check_stt_availability()

        print(clr("  Voice status:", "cyan", "bold"))
        if rec_ok:
            ok("  Recording backend: available")
        else:
            err(f"  Recording: {rec_reason}")
        if stt_ok:
            ok(f"  STT backend:       {get_stt_backend_name()}")
        else:
            err(f"  STT: {stt_reason}")
        dev_idx = config.get("voice_device_index", config.get("_voice_device_index"))
        if dev_idx is not None:
            try:
                from voice import list_input_devices
                devs = list_input_devices()
                dev_name = next((d["name"] for d in devs if d["index"] == dev_idx), f"#{dev_idx}")
            except Exception:
                dev_name = f"#{dev_idx}"
            info(f"  Microphone:    [{dev_idx}] {dev_name}")
        else:
            info("  Microphone:    system default")
        info(f"  Language: {_voice_language}")
        info("  Env override: DULUS_WHISPER_MODEL (default: base)")
        return True

    # ── /voice [start] — record once and submit ──
    try:
        from voice import check_voice_deps, voice_input as _voice_input
    except ImportError:
        err("voice/ package not found — this should not happen")
        return True

    available, reason = check_voice_deps()
    if not available:
        err(f"Voice input not available:\n{reason}")
        return True

    # Live energy bar (blocks are ▁▂▃▄▅▆▇█)
    _BARS = " ▁▂▃▄▅▆▇█"
    _last_bar: list[str] = [""]

    def on_energy(rms: float) -> None:
        level = min(int(rms * 8 / 0.08), 8)  # normalise ~0–0.08 to 0–8
        bar = _BARS[level]
        if bar != _last_bar[0]:
            _last_bar[0] = bar
            print(f"\r\033[K  🎙  {bar}  ", end="", flush=True)

    print(clr("  🎙  Listening… (speak now, auto-stops on silence, Ctrl+C to cancel)", "cyan"))

    try:
        text = _voice_input(language=_voice_language, on_energy=on_energy, device_index=config.get("voice_device_index", config.get("_voice_device_index")))
    except KeyboardInterrupt:
        print()
        info("  Voice input cancelled.")
        return True
    except Exception as e:
        print()
        err(f"Voice input error: {e}")
        return True

    print()  # newline after energy bar

    if not text:
        info("  (nothing transcribed — no speech detected)")
        return True

    ok(f'  Transcribed: \u201c{text}\u201d')
    print()

    # Submit the transcribed text as a user message (same path as typed input)
    # We call run_query via the closure captured in repl().
    # Since cmd_voice is called from handle_slash which is inside repl(),
    # we pass the text back via a sentinel return value that repl() recognises.
    return ("__voice__", text)


# Global handle to the running wake-word listener (managed by repl)
_wake_listener: Any = None


def cmd_wake(args: str, state, config) -> bool:
    """Wake-word (hotword) detection — hands-free voice activation.

    /wake on       — start listening for "Hey Dulus" in background
    /wake off      — stop the background listener
    /wake status   — show whether listener is active
    /wake phrases  — list recognised wake phrases
    /wake threshold <0.01-0.20> — tune mic sensitivity (default 0.035)
    """
    global _wake_listener

    subcmd = args.strip().lower().split()[0] if args.strip() else ""
    rest = args.strip()[len(subcmd):].strip()

    # ── /wake threshold ──
    if subcmd == "threshold":
        if not rest:
            current = config.get("wake_threshold", 0.020)
            info(f"Current wake threshold: {current}  (higher = less sensitive)")
            return True
        try:
            val = float(rest)
            if not 0.001 <= val <= 1.0:
                raise ValueError
            config["wake_threshold"] = val
            ok(f"Wake threshold set to {val}")
            try:
                from config import save_config
                save_config(config)
            except Exception as e:
                warn(f"Could not save config: {e}")
        except ValueError:
            err("Threshold must be a number between 0.001 and 1.0")
        return True

    # ── /wake phrases ──
    if subcmd == "phrases":
        try:
            from voice.wake_word import WAKE_PHRASES
        except ImportError:
            err("voice/wake_word.py not found")
            return True
        print(clr("  Recognised wake phrases:", "cyan", "bold"))
        for p in WAKE_PHRASES:
            print(f"    • {p}")
        return True

    # ── /wake calibrate ──
    if subcmd == "calibrate":
        try:
            from voice import check_voice_deps
        except ImportError:
            err("voice package not available")
            return True
        available, reason = check_voice_deps()
        if not available:
            err(f"Voice deps missing: {reason}")
            return True
        print(clr("  🎙  Calibrating mic — speak normally for 5 seconds…", "cyan"))
        print(clr("  Press Ctrl+C when done.\n", "dim"))
        try:
            import sounddevice as sd
            import numpy as np
            _chunk = int(16000 * 0.3)
            _bars = " ▁▂▃▄▅▆▇█"
            _max_rms = 0.0
            with sd.InputStream(
                samplerate=16000, channels=1, dtype="int16",
                blocksize=_chunk,
                device=config.get("voice_device_index", config.get("_voice_device_index")),
            ) as stream:
                import time as _time
                _t0 = _time.monotonic()
                while _time.monotonic() - _t0 < 5.0:
                    pcm, _ = stream.read(_chunk)
                    arr = np.frombuffer(pcm.tobytes(), dtype=np.int16).astype(np.float32)
                    if arr.size:
                        rms = float(np.sqrt(np.mean(arr ** 2))) / 32768.0
                        _max_rms = max(_max_rms, rms)
                        lvl = min(int(rms * 8 / 0.08), 8)
                        bar = _bars[lvl]
                        print(f"\r  RMS: {rms:.4f}  {bar}  (max {_max_rms:.4f})", end="", flush=True)
                    _time.sleep(0.05)
            print()
            print(clr(f"\n  Max RMS detected: {_max_rms:.4f}", "cyan", "bold"))
            rec = _max_rms * 0.7
            if rec < 0.005:
                rec = 0.010
            info(f"  Recommended threshold: ~{rec:.3f}")
            info(f"  Current threshold:     {config.get('wake_threshold', 0.020)}")
            info("  Use '/wake threshold <n>' to adjust.")
        except KeyboardInterrupt:
            print()
        except Exception as e:
            err(f"Calibration failed: {e}")
        return True

    # ── /wake test ──
    if subcmd == "test":
        try:
            from voice import check_voice_deps
            from voice.wake_word import WakeWordListener
        except ImportError as e:
            err(f"Wake-word module not available: {e}")
            return True
        available, reason = check_voice_deps()
        if not available:
            err(f"Voice input not available:\n{reason}")
            return True
        print(clr("  🎙  Wake-word TEST mode — debug output ON for 10 seconds", "cyan", "bold"))
        print(clr("  Say 'Hey Dulus' now. Press Ctrl+C to stop early.\n", "dim"))
        _test_listener = WakeWordListener(
            rms_threshold=config.get("wake_threshold", 0.020),
            device_index=config.get("voice_device_index", config.get("_voice_device_index")),
            language=_voice_language,
            debug=True,
        )
        _found: list[str] = []

        def _test_wake(phrase: str) -> None:
            print(clr(f"\n  ✅ WAKE DETECTED: '{phrase}'", "green", "bold"))

        def _test_cmd(text: str) -> None:
            _found.append(text)
            print(clr(f'\n  🎙️  COMMAND: "{text}"', "green", "bold"))

        _test_listener.start(on_wake=_test_wake, on_command=_test_cmd)
        try:
            import time as _time
            _time.sleep(10)
        except KeyboardInterrupt:
            print()
        finally:
            _test_listener.stop()
        if not _found:
            warn("  No wake word detected in 10s. Try '/wake calibrate' to check your mic levels.")
        return True

    # ── /wake status ──
    if subcmd == "status":
        try:
            from voice import check_voice_deps
        except ImportError:
            err("voice package not available")
            return True
        available, reason = check_voice_deps()
        if not available:
            err(f"Voice deps missing: {reason}")
            return True
        active = _wake_listener is not None and getattr(_wake_listener, "is_running", lambda: False)()
        state_str = clr("ACTIVE", "green", "bold") if active else clr("OFF", "gray")
        info(f"Wake-word listener: {state_str}")
        info(f"Threshold: {config.get('wake_threshold', 0.020)}")
        if active:
            info("Say 'Hey Dulus' followed by your command.")
        else:
            info("Use '/wake on' to start listening.")
        return True

    # ── /wake off ──
    if subcmd in ["off", "false", "disable", "stop"]:
        config["wake_enabled"] = False
        try:
            from config import save_config
            save_config(config)
        except Exception:
            pass
        if _wake_listener is not None:
            try:
                _wake_listener.stop()
            except Exception as e:
                warn(f"Error stopping wake listener: {e}")
            _wake_listener = None
            ok("Wake-word listener stopped.")
        else:
            info("Wake-word listener was not running.")
        return True

    # ── /wake on ──
    if subcmd in ["on", "true", "enable", "start"]:
        if _wake_listener is not None and getattr(_wake_listener, "is_running", lambda: False)():
            info("Wake-word listener is already active.")
            return True

        try:
            from voice import check_voice_deps
            from voice.wake_word import WakeWordListener
        except ImportError as e:
            err(f"Wake-word module not available: {e}")
            return True

        available, reason = check_voice_deps()
        if not available:
            err(f"Voice input not available:\n{reason}")
            return True

        # The actual on_wake / on_command callbacks are injected by repl()
        # via the _wake_listener global handle.  Here we just create the
        # object; repl() wires the queue when it sees the handle change.
        _wake_listener = WakeWordListener(
            rms_threshold=config.get("wake_threshold", 0.035),
            device_index=config.get("voice_device_index", config.get("_voice_device_index")),
            language=_voice_language,
        )
        config["wake_enabled"] = True
        try:
            from config import save_config
            save_config(config)
        except Exception:
            pass
        ok("Wake-word listener starting… Say 'Hey Dulus' to activate.")
        return True

    # ── Toggle ──
    if _wake_listener is not None and getattr(_wake_listener, "is_running", lambda: False)():
        return cmd_wake("off", state, config)
    else:
        return cmd_wake("on", state, config)


def cmd_image(args: str, state, config) -> Union[bool, tuple]:
    """Grab image from clipboard and send to vision model with optional prompt."""
    import sys as _sys
    try:
        from PIL import Image
        import io, base64
    except ImportError:
        err("Pillow is required for /image. Install with: pip install dulus[vision]")
        return True

    # Use kimi-cli style robust clipboard (Linux xclip/wl-paste, macOS native, Windows)
    try:
        from clipboard_utils import grab_media_from_clipboard, is_media_clipboard_available
    except ImportError:
        err("clipboard_utils module not found.")
        return True

    if not is_media_clipboard_available():
        err("No clipboard tool found. Install xclip (X11) or wl-clipboard (Wayland).")
        return True

    result = grab_media_from_clipboard()
    if result is None or not result.images:
        err("No image found in clipboard. Copy an image first.")
        return True

    img = result.images[0]
    try:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        size_kb = len(buf.getvalue()) / 1024
        info(f"📷 Clipboard image captured ({size_kb:.0f} KB, {img.size[0]}x{img.size[1]})")
    except Exception as e:
        err(f"Failed to process clipboard image: {e}")
        return True

    # Store in config for agent.py to pick up
    config["_pending_image"] = b64

    prompt = args.strip() if args.strip() else "What do you see in this image? Describe it in detail."
    return ("__image__", prompt)


def cmd_checkpoint(args: str, state, config) -> bool:
    """List or restore checkpoints.

    /checkpoint          — list all checkpoints
    /checkpoint <id>     — restore to checkpoint #id
    /checkpoint clear    — delete all checkpoints for this session
    """
    import checkpoint as ckpt

    session_id = config.get("_session_id")
    if not session_id:
        err("No active session.")
        return True

    arg = args.strip()

    # /checkpoint clear
    if arg == "clear":
        ckpt.delete_session_checkpoints(session_id)
        info("All checkpoints cleared.")
        return True

    # /checkpoint (no args) — list
    if not arg:
        snaps = ckpt.list_snapshots(session_id)
        if not snaps:
            info("No checkpoints yet.")
            return True
        info(f"Checkpoints ({len(snaps)} total):")
        for s in snaps:
            ts = s["created_at"]
            try:
                t = datetime.fromisoformat(ts).strftime("%H:%M")
            except Exception:
                t = ts[:16]
            preview = s["user_prompt_preview"]
            if preview:
                preview = f'  "{preview[:40]}{"..." if len(preview) > 40 else ""}"'
            else:
                preview = "  (initial state)"
            print(f"  #{s['id']:<3} [turn {s['turn_count']}]  {t}{preview}")
        return True

    # /checkpoint <id> — restore
    try:
        snap_id = int(arg)
    except ValueError:
        err(f"Unknown subcommand: {arg}")
        return True

    snap = ckpt.get_snapshot(session_id, snap_id)
    if snap is None:
        err(f"Checkpoint #{snap_id} not found.")
        return True

    changed = ckpt.files_changed_since(session_id, snap_id)
    ts = snap.created_at
    try:
        t = datetime.fromisoformat(ts).strftime("%H:%M")
    except Exception:
        t = ts[:16]

    info(f"Checkpoint #{snap_id} (turn {snap.turn_count}, {t})")
    if changed:
        shown = changed[:4]
        extra = f" (+{len(changed) - 4} files)" if len(changed) > 4 else ""
        info(f"Files changed since: {', '.join(Path(f).name for f in shown)}{extra}")
    print()
    menu_buf = "  1. Restore conversation + files\n  2. Restore conversation only\n  3. Restore files only\n  4. Cancel"
    print(menu_buf)
    print()

    try:
        choice = ask_input_interactive("Choice [1-4]: ", config, menu_buf).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return True

    restore_conversation = choice in ("1", "2")
    restore_files = choice in ("1", "3")

    if choice == "4" or choice not in ("1", "2", "3"):
        info("Cancelled.")
        return True

    results = []

    if restore_conversation:
        state.messages = state.messages[:snap.message_index]
        state.turn_count = snap.turn_count
        state.total_input_tokens = snap.token_snapshot.get("input", 0)
        state.total_output_tokens = snap.token_snapshot.get("output", 0)
        results.append("conversation restored")

    if restore_files:
        file_results = ckpt.rewind_files(session_id, snap_id)
        for r in file_results:
            print(f"  {r}")
        results.append(f"{len(file_results)} file(s) processed")

    # Reset tracking and create a fresh snapshot of current state
    ckpt.reset_tracked()
    ckpt.make_snapshot(
        session_id, state, config,
        f"[rewind to #{snap_id}]",
        tracked_edits=None,
    )

    info(f"Done: {', '.join(results)}. New checkpoint created.")
    return True


# /rewind is an alias for /checkpoint
cmd_rewind = cmd_checkpoint


def cmd_plan(args: str, state, config) -> bool:
    """Enter/exit plan mode or show current plan.

    /plan <description>  — enter plan mode and start planning
    /plan                — show current plan file contents
    /plan done           — exit plan mode, restore permissions
    /plan status         — show plan mode status
    """
    arg = args.strip()

    plan_file = config.get("_plan_file", "")
    in_plan_mode = config.get("permission_mode") == "plan"

    # /plan done — exit plan mode
    if arg == "done":
        if not in_plan_mode:
            err("Not in plan mode.")
            return True
        prev = config.pop("_prev_permission_mode", "auto")
        config["permission_mode"] = prev
        info(f"Exited plan mode. Permission mode restored to: {prev}")
        if plan_file:
            info(f"Plan saved at: {plan_file}")
            info("You can now ask Dulus to implement the plan.")
        return True

    # /plan status
    if arg == "status":
        if in_plan_mode:
            info(f"Plan mode: ACTIVE")
            info(f"Plan file: {plan_file}")
            info(f"Only the plan file is writable. Use /plan done to exit.")
        else:
            info("Plan mode: inactive")
        return True

    # /plan (no args) — show plan contents
    if not arg:
        if not plan_file:
            info("Not in plan mode. Use /plan <description> to start planning.")
            return True
        p = Path(plan_file)
        if p.exists() and p.stat().st_size > 0:
            info(f"Plan file: {plan_file}")
            print(p.read_text(encoding="utf-8"))
        else:
            info(f"Plan file is empty: {plan_file}")
        return True

    # /plan <description> — enter plan mode
    if in_plan_mode:
        err("Already in plan mode. Use /plan done to exit first.")
        return True

    # Create plan file
    session_id = config.get("_session_id", "default")
    plans_dir = Path.cwd() / ".dulus-context" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{session_id}.md"
    plan_path.write_text(f"# Plan: {arg}\n\n", encoding="utf-8")

    # Switch to plan mode
    config["_prev_permission_mode"] = config.get("permission_mode", "auto")
    config["permission_mode"] = "plan"
    config["_plan_file"] = str(plan_path)

    info("Plan mode activated (read-only except plan file).")
    info(f"Plan file: {plan_path}")
    info("Use /plan done to exit and start implementation.")
    print()

    # Return sentinel to trigger run_query with the description
    return ("__plan__", arg)


def cmd_compact(args: str, state, config) -> bool:
    """Manually compact conversation history.

    /compact              — compact with default summarization
    /compact <focus>      — compact with focus instructions
    """
    from compaction import manual_compact
    focus = args.strip()

    if focus:
        info(f"Compacting with focus: {focus}")
    else:
        info("Compacting conversation...")

    success, msg = manual_compact(state, config, focus=focus)
    if success:
        info(msg)
    else:
        err(msg)
    return True


def cmd_news(args: str, state, config) -> bool:
    """Show the latest news from docs/news.md."""
    news_file = Path(__file__).parent / "docs" / "news.md"
    if not news_file.exists():
        err("News file not found.")
        return True

    try:
        content = news_file.read_text(encoding="utf-8")
        if _RICH:
            from rich.console import Console
            from rich.markdown import Markdown
            c = Console()
            c.print(Markdown(content))
        else:
            print(content)
    except Exception as e:
        err(f"Failed to read news: {e}")
    return True


def cmd_init(args: str, state, config) -> bool:
    """Initialize a DULUS.md file in the current directory.

    /init          — create DULUS.md with a starter template
    """
    target = Path.cwd() / "DULUS.md"
    if target.exists():
        err(f"DULUS.md already exists at {target}")
        info("Edit it directly or delete it first.")
        return True

    project_name = Path.cwd().name
    template = (
        f"# {project_name}\n\n"
        "## Project Overview\n"
        "<!-- Describe what this project does -->\n\n"
        "## Tech Stack\n"
        "<!-- Languages, frameworks, key dependencies -->\n\n"
        "## Conventions\n"
        "<!-- Coding style, naming conventions, patterns to follow -->\n\n"
        "## Important Files\n"
        "<!-- Key entry points, config files, etc. -->\n\n"
        "## Testing\n"
        "<!-- How to run tests, testing conventions -->\n\n"
    )
    target.write_text(template, encoding="utf-8")
    info(f"Created {target}")
    info("Edit it to give Dulus context about your project.")
    return True


def cmd_export(args: str, state, config) -> bool:
    """Export conversation history to a file.

    /export              — export as markdown to .dulus/exports/
    /export <filename>   — export to a specific file (.md or .json)
    """
    if not state.messages:
        err("No conversation to export.")
        return True

    arg = args.strip()
    if arg:
        out_path = Path(arg)
    else:
        export_dir = Path.cwd() / ".dulus-context" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = export_dir / f"conversation_{ts}.md"

    is_json = out_path.suffix.lower() == ".json"

    if is_json:
        out_path.write_text(
            json.dumps(state.messages, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        lines = []
        for m in state.messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            if isinstance(content, list):
                content = "(structured content)"
            if role == "user":
                lines.append(f"## User\n\n{content}\n")
            elif role == "assistant":
                lines.append(f"## Assistant\n\n{content}\n")
            elif role == "tool":
                name = m.get("name", "tool")
                lines.append(f"### Tool: {name}\n\n```\n{content[:2000]}\n```\n")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")

    info(f"Exported {len(state.messages)} messages to {out_path}")
    return True


def cmd_fork(args: str, state, config) -> bool:
    """Fork the current session at a given turn.

    /fork              - list turns and prompt for which to fork at
    /fork <turn_index> - fork at the specified turn (0-based)
    """
    import asyncio
    from pathlib import Path

    _sf_path = Path(__file__).resolve().parent / "dulus" / "session_fork.py"
    _sf_spec = __import__('importlib.util').util.spec_from_file_location("session_fork", _sf_path)
    _sf_mod = __import__('importlib.util').util.module_from_spec(_sf_spec)
    _sf_spec.loader.exec_module(_sf_mod)
    SessionFork = _sf_mod.SessionFork

    session_id = config.get("_session_id", "")
    if not session_id:
        err("No active session to fork.")
        return True

    from config import MR_SESSION_DIR
    session_dir = MR_SESSION_DIR / session_id
    if not session_dir.exists():
        session_dir.mkdir(parents=True, exist_ok=True)

    forker = SessionFork(str(session_dir))
    turns = forker.enumerate_turns()

    if not turns:
        err("No turns found in current session.")
        return True

    arg = args.strip()
    if arg:
        try:
            turn_index = int(arg)
        except ValueError:
            err(f"Invalid turn index: {arg}")
            return True
        if turn_index < 0 or turn_index >= len(turns):
            err(f"Turn index {turn_index} out of range (0-{len(turns) - 1}).")
            return True
    else:
        print("  Available turns:")
        for t in turns:
            print(f"    [{t.index}] {t.user_text}")
        try:
            choice = input("  Fork at turn: ").strip()
            turn_index = int(choice)
        except (ValueError, EOFError):
            err("Invalid selection.")
            return True
        if turn_index < 0 or turn_index >= len(turns):
            err(f"Turn index {turn_index} out of range.")
            return True

    try:
        new_sid = asyncio.get_event_loop().run_until_complete(forker.fork(turn_index=turn_index))
        ok(f"Forked session: {new_sid}")
    except Exception as exc:
        err(f"Fork failed: {exc}")

    return True


def cmd_undo(_args: str, state, config) -> bool:
    """Undo the last turn by forking at the second-to-last turn.

    /undo - remove the most recent turn
    """
    import asyncio
    from pathlib import Path

    _sf_path = Path(__file__).resolve().parent / "dulus" / "session_fork.py"
    _sf_spec = __import__('importlib.util').util.spec_from_file_location("session_fork", _sf_path)
    _sf_mod = __import__('importlib.util').util.module_from_spec(_sf_spec)
    _sf_spec.loader.exec_module(_sf_mod)
    SessionFork = _sf_mod.SessionFork

    session_id = config.get("_session_id", "")
    if not session_id:
        err("No active session to undo.")
        return True

    from config import MR_SESSION_DIR
    session_dir = MR_SESSION_DIR / session_id
    if not session_dir.exists():
        err("Session directory not found.")
        return True

    forker = SessionFork(str(session_dir))
    try:
        new_sid = asyncio.get_event_loop().run_until_complete(forker.undo())
        ok(f"Undone last turn. New session: {new_sid}")
    except ValueError as exc:
        err(str(exc))
    except Exception as exc:
        err(f"Undo failed: {exc}")

    return True


def cmd_add_dir(args: str, _state, config) -> bool:
    """Manage additional workspace directories.

    /add-dir <path>  - add a directory to the workspace
    /add-dir list    - list added directories
    /add-dir remove <path> - remove a directory
    """
    from pathlib import Path
    _adm_path = Path(__file__).resolve().parent / "dulus" / "add_dir_manager.py"
    _adm_spec = __import__('importlib.util').util.spec_from_file_location("add_dir_manager", _adm_path)
    _adm_mod = __import__('importlib.util').util.module_from_spec(_adm_spec)
    _adm_spec.loader.exec_module(_adm_mod)
    AddDirManager = _adm_mod.AddDirManager

    manager_key = "_add_dir_manager"
    manager = config.get(manager_key)
    if manager is None:
        manager = AddDirManager(str(Path.cwd()))
        config[manager_key] = manager

    arg = args.strip()
    if not arg or arg == "list":
        dirs = manager.list()
        if not dirs:
            info("No additional directories in workspace.")
        else:
            print(f"  Working directory: {Path.cwd()}")
            for d in dirs:
                print(f"  + {d}")
        return True

    if arg.startswith("remove "):
        path = arg[7:].strip()
        if manager.remove(path):
            ok(f"Removed directory: {path}")
        else:
            err(f"Directory not in workspace: {path}")
        return True

    success, msg = manager.add(arg)
    if success:
        ok(msg)
    else:
        err(msg)
    return True


def cmd_import(args: str, state, config) -> bool:
    """Import conversation data from a file or another session.

    /import <file_path>  - import from .json, .md, or .txt
    /import <session_id> - import from another Dulus session
    """
    from pathlib import Path
    _ei_path = Path(__file__).resolve().parent / "dulus" / "export_import.py"
    _ei_spec = __import__('importlib.util').util.spec_from_file_location("export_import", _ei_path)
    _ei_mod = __import__('importlib.util').util.module_from_spec(_ei_spec)
    _ei_spec.loader.exec_module(_ei_mod)
    SessionImporter = _ei_mod.SessionImporter

    arg = args.strip()
    if not arg:
        err("Usage: /import <file_path_or_session_id>")
        return True

    importer = SessionImporter()
    path = Path(arg)
    if path.exists():
        desc, length = importer.import_from_file(arg)
    elif (Path.home() / ".dulus" / "sessions" / arg).exists():
        desc, length = importer.import_from_session_id(arg)
    else:
        desc, length = importer.import_from_file(arg)

    if desc.startswith("Error:"):
        err(desc)
        return True

    ok(f"Imported from {desc}")
    return True


def cmd_copy(args: str, state, config) -> bool:
    """Copy the last assistant response or file content to clipboard.

    /copy         - copy last assistant message
    /copy <file>  - copy file contents
    """
    from dulus_tools.clipboard_utils import ClipboardUtils

    if args.strip():
        file_path = args.strip()
        success = ClipboardUtils.copy_file_content(file_path)
        if success:
            info(f"Copied file to clipboard: {file_path}")
        else:
            err(f"Failed to copy file: {file_path}")
        return True

    last_reply = None
    for m in reversed(state.messages):
        if m.get("role") == "assistant":
            content = m.get("content", "")
            if isinstance(content, str) and content.strip():
                last_reply = content
                break

    if not last_reply:
        err("No assistant response to copy.")
        return True

    success = ClipboardUtils.copy_text(last_reply)
    if success:
        info(f"Copied {len(last_reply)} chars to clipboard.")
    else:
        err("Failed to copy: clipboard tool not available.")
    return True


def cmd_shell(args: str, state, config) -> bool:
    """Toggle or use shell mode for direct command execution.

    /shell           - toggle shell mode
    /shell on|off    - activate/deactivate
    /shell <command> - execute directly
    """
    from dulus_tools.shell_mode import ShellMode

    if not hasattr(state, "_shell_mode") or state._shell_mode is None:
        state._shell_mode = ShellMode()

    shell = state._shell_mode

    if not args:
        new_state = shell.toggle()
        info(f"Shell mode: {'ON' if new_state else 'OFF'}")
        return True

    subcmd = args.strip().lower()
    if subcmd == "on":
        shell.activate()
        info("Shell mode: ON")
        return True
    elif subcmd == "off":
        shell.deactivate()
        info("Shell mode: OFF")
        return True

    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(shell.execute(args))
    output = result.get("output", "")
    if output:
        print(output)
    if result.get("exit_code", 0) != 0:
        err(result.get("message", ""))
    else:
        info(result.get("message", ""))
    return True


def cmd_status(args: str, state, config) -> bool:
    """Show current session status.

    /status   — model, provider, permissions, session info
    """
    from providers import detect_provider
    from compaction import estimate_tokens, get_context_limit

    model = config.get("model", "unknown")
    provider = detect_provider(model)
    perm_mode = config.get("permission_mode", "auto")
    session_id = config.get("_session_id", "N/A")
    turn_count = getattr(state, "turn_count", 0)
    msg_count = len(getattr(state, "messages", []))
    tokens_in = getattr(state, "total_input_tokens", 0)
    tokens_out = getattr(state, "total_output_tokens", 0)
    est_ctx = estimate_tokens(getattr(state, "messages", []), model=model, config=config)
    ctx_limit = get_context_limit(model)
    ctx_pct = (est_ctx / ctx_limit * 100) if ctx_limit else 0
    plan_mode = config.get("permission_mode") == "plan"

    print(f"  Version:     {VERSION}")
    print(f"  Model:       {model} ({provider})")
    print(f"  Permissions: {perm_mode}" + (" [PLAN MODE]" if plan_mode else ""))
    print(f"  Session:     {session_id}")
    print(f"  Turns:       {turn_count}")
    print(f"  Messages:    {msg_count}")
    print(f"  Tokens:      ~{tokens_in} in / ~{tokens_out} out")
    print(f"  Context:     ~{est_ctx} / {ctx_limit} ({ctx_pct:.0f}%)")
    return True


def cmd_doctor(args: str, state, config) -> bool:
    """Diagnose installation health and connectivity.

    /doctor   — run all health checks
    """
    import subprocess as _sp
    import sys as _sys
    from providers import PROVIDERS, detect_provider, get_api_key

    ok_n = warn_n = fail_n = 0

    def _print_safe(s):
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("ascii", errors="replace").decode())

    def ok(msg):
        nonlocal ok_n; ok_n += 1
        _print_safe(clr("  [PASS] ", "green") + msg)

    def warn(msg):
        nonlocal warn_n; warn_n += 1
        _print_safe(clr("  [WARN] ", "yellow") + msg)

    def fail(msg):
        nonlocal fail_n; fail_n += 1
        _print_safe(clr("  [FAIL] ", "red") + msg)

    info("Running diagnostics...")
    print()

    # ── 1. Python version ──
    v = _sys.version_info
    if v >= (3, 10):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python {v.major}.{v.minor}.{v.micro} (need ≥3.10)")

    # ── 2. Git ──
    try:
        r = _sp.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            ok(f"Git: {r.stdout.strip()}")
        else:
            fail("Git: not working")
    except Exception:
        fail("Git: not found")

    try:
        r = _sp.run(["git", "rev-parse", "--is-inside-work-tree"],
                     capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            ok("Inside a git repository")
        else:
            warn("Not inside a git repository")
    except Exception:
        warn("Could not check git repo status")

    # ── 3. Current model + API key ──
    model = config.get("model", "")
    provider = detect_provider(model)
    key = get_api_key(provider, config)

    if key:
        ok(f"API key for {provider}: set ({key[:4]}...{key[-4:]})")
    elif provider in ("ollama", "lmstudio"):
        ok(f"Provider {provider}: no key needed (local)")
    else:
        fail(f"API key for {provider}: NOT SET")

    # ── 4. API connectivity test ──
    if key or provider in ("ollama", "lmstudio"):
        print(f"  ... testing {provider} API connectivity...")
        try:
            import urllib.request, urllib.error
            prov = PROVIDERS.get(provider, {})
            ptype = prov.get("type", "openai")

            if ptype == "anthropic":
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=json.dumps({
                        "model": model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    }).encode(),
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                )
                try:
                    urllib.request.urlopen(req, timeout=10)
                    ok(f"Anthropic API: reachable, model {model} works")
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        fail("Anthropic API: invalid API key (401)")
                    elif e.code == 404:
                        fail(f"Anthropic API: model {model} not found (404)")
                    elif e.code == 429:
                        warn("Anthropic API: rate limited (429) — key is valid")
                    else:
                        warn(f"Anthropic API: HTTP {e.code}")
                except Exception as e:
                    fail(f"Anthropic API: connection error — {e}")

            elif ptype == "ollama":
                base = prov.get("base_url", "http://localhost:11434")
                try:
                    urllib.request.urlopen(f"{base}/api/tags", timeout=5)
                    ok(f"Ollama: reachable at {base}")
                except Exception:
                    fail(f"Ollama: cannot reach {base} — is Ollama running?")

            else:
                base = prov.get("base_url", "")
                if provider == "custom":
                    base = config.get("custom_base_url", base or "")
                if base:
                    models_url = base.rstrip("/") + "/models"
                    req = urllib.request.Request(
                        models_url,
                        headers={"Authorization": f"Bearer {key}"},
                    )
                    try:
                        urllib.request.urlopen(req, timeout=10)
                        ok(f"{provider} API: reachable")
                    except urllib.error.HTTPError as e:
                        if e.code == 401:
                            fail(f"{provider} API: invalid API key (401)")
                        elif e.code == 429:
                            warn(f"{provider} API: rate limited (429) — key is valid")
                        else:
                            warn(f"{provider} API: HTTP {e.code}")
                    except Exception as e:
                        fail(f"{provider} API: connection error — {e}")
                else:
                    warn(f"{provider}: no base_url configured")
        except Exception as e:
            warn(f"API test skipped: {e}")

    # ── 5. Other configured API keys ──
    print()
    for pname, pdata in PROVIDERS.items():
        if pname == provider:
            continue
        env_var = pdata.get("api_key_env")
        if env_var and os.environ.get(env_var, ""):
            ok(f"{pname} key ({env_var}): set")

    # ── 6. Optional dependencies ──
    print()
    for mod, desc in [
        ("rich", "Rich (live markdown rendering)"),
        ("PIL", "Pillow (clipboard image /image)"),
        ("sounddevice", "sounddevice (voice recording)"),
        ("faster_whisper", "faster-whisper (local STT)"),
    ]:
        try:
            __import__(mod)
            ok(desc)
        except ImportError:
            warn(f"{desc}: not installed")

    # ── 7. DULUS.md / CLAUDE.md ──
    print()
    dulus_md = Path.cwd() / "DULUS.md"
    claude_md = Path.cwd() / "CLAUDE.md"
    global_dulus = Path.home() / ".dulus" / "DULUS.md"
    global_claude = Path.home() / ".claude" / "CLAUDE.md"

    if dulus_md.exists():
        ok(f"Project DULUS.md: {dulus_md}")
    elif claude_md.exists():
        ok(f"Project CLAUDE.md: {claude_md} (Consider renaming to DULUS.md)")
    else:
        warn("No project DULUS.md (run /init to create)")

    if global_dulus.exists():
        ok(f"Global DULUS.md: {global_dulus}")
    elif global_claude.exists():
        ok(f"Global CLAUDE.md: {global_claude}")

    # ── 8. Checkpoints disk usage ──
    ckpt_root = Path.home() / ".dulus" / "checkpoints"
    if ckpt_root.exists():
        total = sum(f.stat().st_size for f in ckpt_root.rglob("*") if f.is_file())
        mb = total / (1024 * 1024)
        sessions = sum(1 for d in ckpt_root.iterdir() if d.is_dir())
        if mb > 100:
            warn(f"Checkpoints: {mb:.1f} MB ({sessions} sessions)")
        else:
            ok(f"Checkpoints: {mb:.1f} MB ({sessions} sessions)")

    # ── 9. Permission mode ──
    perm = config.get("permission_mode", "auto")
    if perm == "accept-all":
        warn(f"Permission mode: {perm} (all operations auto-approved)")
    else:
        ok(f"Permission mode: {perm}")

    # ── Summary ──
    print()
    total = ok_n + warn_n + fail_n
    summary = f"  {ok_n} passed, {warn_n} warnings, {fail_n} failures ({total} checks)"
    if fail_n:
        _print_safe(clr(summary, "red"))
    elif warn_n:
        _print_safe(clr(summary, "yellow"))
    else:
        _print_safe(clr(summary, "green"))

    return True


def cmd_roundtable(args: str, _state, config) -> Union[bool, tuple]:
    """Start a roundtable discussion among different models.

    /roundtable               - Enter setup mode to define models
    /roundtable stop          - Exit roundtable mode
    /roundtable proactive 3m  - Auto-send 'ok ok' every 3m to keep the table alive
    /roundtable proactive off  - Disable roundtable proactive
    """
    a = args.strip().lower()

    if a in ("stop", "exit", "end"):
        config["_roundtable_proactive_enabled"] = False
        return ("__roundtable_stop__",)

    # /roundtable proactive [interval|off]
    if a.startswith("proactive"):
        parts = a.split()
        sub = parts[1] if len(parts) > 1 else ""
        if sub == "off":
            config["_roundtable_proactive_enabled"] = False
            ok("Roundtable proactive: OFF")
            return True
        # Parse duration: 3m, 30s, 1h
        val = 180  # default 3m
        if sub:
            try:
                if sub.endswith("m"):
                    val = int(sub[:-1]) * 60
                elif sub.endswith("s"):
                    val = int(sub[:-1])
                elif sub.endswith("h"):
                    val = int(sub[:-1]) * 3600
                else:
                    val = int(sub)
            except ValueError:
                err(f"Invalid duration '{sub}'. Use 30s, 3m, 1h.")
                return True
        config["_roundtable_proactive_enabled"] = True
        config["_roundtable_proactive_interval"] = val
        config["_roundtable_proactive_last_fire"] = time.time()
        ok(f"Roundtable proactive: ON  (sending 'ok ok' every {val}s)")
        return True

    return ("__roundtable__",)

def cmd_batch(args: str, _state, config) -> bool:
    """Manage Kimi Batch tasks.
    
    /batch status [id]  — check progress
    /batch list         — list recent batch jobs
    /batch fetch [id]   — download results when completed
    """
    from batch_api import BatchManager, list_batch_jobs, get_batch_job_by_id
    from providers import get_api_key
    
    api_key = get_api_key("kimi", config)
    if not api_key:
        err("Kimi API key missing.")
        return True

    mgr = BatchManager(api_key, base_url="https://api.moonshot.ai")
    parts = args.strip().split()
    sub = parts[0].lower() if parts else "list"
    
    if sub == "list":
        jobs = list_batch_jobs(include_pollers=True)
        if not jobs:
            info("No batch jobs found.")
            return True
        print(clr("\n  Recent Kimi Batch Jobs:", "cyan", "bold"))
        for j in reversed(jobs[-10:]):
            st = j.get('status', 'unknown')
            s_clr = "green" if st == "completed" else ("red" if st in ("failed", "expired", "cancelled") else "yellow")
            # Show counts if available
            counts = j.get('request_counts', {})
            count_str = f"({counts.get('completed', 0)}/{counts.get('total', 0)})" if counts else ""
            from_poller = " ✓" if j.get('_from_poller') else ""
            print(f"    {clr(j['id'], 'yellow')} | {j.get('created_at', 'N/A')[:19]} | {clr(st, s_clr)} {count_str}{from_poller}")
            if j.get('description'):
                print(clr(f"      {j['description']}", "dim"))
        return True
        
    if sub == "status":
        batch_id = parts[1] if len(parts) > 1 else None
        if not batch_id:
            # Prefer the batch that just announced itself via notification —
            # that's almost always what the user means when they type
            # `/batch status` right after a "[Background Event Triggered]".
            batch_id = globals().get("_LAST_NOTIFIED_BATCH_ID")
            if batch_id:
                info(f"Using last-notified batch: {batch_id}")
            else:
                jobs = list_batch_jobs(include_pollers=True)
                if jobs: batch_id = jobs[0]['id']  # [0] = most recent (sorted newest-first)
                else:
                    err("No batch ID provided and no recent jobs found.")
                    return True
        
        try:
            res = mgr.retrieve_batch(batch_id)
            status = res.get("status", "unknown")
            counts = res.get("request_counts", {})
            comp = counts.get("completed", 0)
            total = counts.get("total", 0)
            s_clr = "green" if status == "completed" else ("red" if status in ("failed", "expired", "cancelled") else "yellow")

            # Sync real status back to local job file so /batch list stays current
            from batch_api import update_batch_job_status
            update_batch_job_status(batch_id, {
                "status": status,
                "request_counts": counts,
                "output_file_id": res.get("output_file_id"),
                "completed_at": res.get("completed_at"),
            })

            ok(f"Batch {batch_id}: {clr(status, s_clr)} ({comp}/{total})")

            if status == "completed":
                out_id = res.get("output_file_id")
                if out_id:
                    info(f"Results ready. Output File ID: {out_id}")
                    print(clr("    To fetch results, run: ", "dim") + clr(f"/batch fetch {batch_id}", "white"))
        except Exception as e:
            err(f"Failed to retrieve batch: {e}")
        return True
        
    if sub == "fetch":
        batch_id = parts[1] if len(parts) > 1 else None
        if not batch_id:
            # Prefer the batch that just notified. Falls back to most-recent-completed.
            _ln = globals().get("_LAST_NOTIFIED_BATCH_ID")
            if _ln:
                batch_id = _ln
                info(f"Using last-notified batch: {batch_id}")
            else:
                jobs = list_batch_jobs(include_pollers=True)
                completed_jobs = [j for j in jobs if j.get('status') == 'completed']
                if completed_jobs:
                    batch_id = completed_jobs[0]['id']  # newest completed
                    info(f"Using most recent completed batch: {batch_id}")
                elif jobs:
                    batch_id = jobs[0]['id']
                    info(f"Using most recent batch (not completed): {batch_id}")
                else:
                    err("No batch jobs found.")
                    return True
        # Consume: once fetched by default, don't keep re-defaulting to the same one.
        if globals().get("_LAST_NOTIFIED_BATCH_ID") == batch_id:
            globals()["_LAST_NOTIFIED_BATCH_ID"] = None
            
        try:
            res = mgr.retrieve_batch(batch_id)
            if res.get("status") != "completed":
                err(f"Batch {batch_id} is not completed yet (status: {res.get('status')}).")
                return True
            out_id = res.get("output_file_id")
            if not out_id: 
                err("No output file ID found for this batch.")
                return True
            
            content = mgr.get_file_content(out_id)
            results_dir = Path.home() / ".dulus" / "batch_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            out_file = results_dir / f"results_{batch_id}.jsonl"
            out_file.write_text(content, encoding="utf-8")
            ok(f"Results saved to {out_file}")
            
            # Preview first result
            lines = content.strip().splitlines()
            if lines:
                data = json.loads(lines[0])
                print(clr("\n  Preview of first result:", "dim"))
                content = data.get("response", {}).get("body", {}).get("choices", [{}])[0].get("message", {}).get("content", "No content")
                print(clr(content, "cyan"))
        except Exception as e:
            err(f"Fetch failed: {e}")
        return True

    return True


def cmd_webbridge(args: str, state, config) -> bool:
    """Control the Dulus WebBridge browser automation."""
    from os import makedirs, path, getenv
    from datetime import datetime
    try:
        from webbridge.core import DulusWebBridge
    except ImportError:
        err("WebBridge not available. Install dependencies: pip install playwright")
        return True

    bridge = DulusWebBridge()
    parts = (args or "").strip().split()
    sub = parts[0].lower() if parts else "status"

    if sub in ("status", ""):
        try:
            st = bridge.status()
            if st.get("browser_open"):
                ok("Browser: OPEN")
                info(f"  URL: {st.get('url', 'N/A')}")
            else:
                info("Browser: CLOSED")
        except Exception as e:
            err(f"Status check failed: {e}")
        return True

    if sub == "open":
        if len(parts) < 2:
            err("Usage: /webbridge open <url>")
            return True
        url = parts[1]
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            bridge.navigate_sync(url)
            ok(f"Opened: {url}")
        except Exception as e:
            err(f"Failed to open URL: {e}")
        return True

    if sub == "click":
        if len(parts) < 2:
            err("Usage: /webbridge click <selector>")
            return True
        selector = parts[1]
        try:
            bridge.click_sync(selector)
            ok(f"Clicked: {selector}")
        except Exception as e:
            err(f"Click failed: {e}")
        return True

    if sub == "type":
        if len(parts) < 3:
            err("Usage: /webbridge type <selector> <text>")
            return True
        selector = parts[1]
        text = " ".join(parts[2:])
        try:
            bridge.type_sync(selector, text)
            ok(f"Typed into: {selector}")
        except Exception as e:
            err(f"Type failed: {e}")
        return True

    if sub == "screenshot":
        save_path = None
        if len(parts) >= 2:
            save_path = parts[1]
        else:
            screenshots_dir = path.join(getenv("USERPROFILE", getenv("HOME", ".")), ".dulus", "screenshots")
            makedirs(screenshots_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = path.join(screenshots_dir, f"webbridge_{ts}.png")
        try:
            bridge.screenshot_sync(save_path)
            ok(f"Screenshot saved: {save_path}")
        except Exception as e:
            err(f"Screenshot failed: {e}")
        return True

    if sub == "extract":
        mode = parts[1].lower() if len(parts) >= 2 else "text"
        if mode not in ("text", "dom"):
            mode = "text"
        try:
            if mode == "text":
                content = bridge.get_text_sync()
            else:
                content = bridge.get_dom_sync()
            preview = content[:2000]
            ok(f"Extracted ({mode}) — {len(content)} chars")
            info(preview)
            if len(content) > 2000:
                info(f"... ({len(content) - 2000} more chars)")
        except Exception as e:
            err(f"Extract failed: {e}")
        return True

    if sub == "scroll":
        direction = parts[1].lower() if len(parts) >= 2 else "down"
        if direction not in ("up", "down"):
            direction = "down"
        try:
            bridge.scroll_sync(direction)
            ok(f"Scrolled {direction}")
        except Exception as e:
            err(f"Scroll failed: {e}")
        return True

    if sub == "close":
        try:
            bridge.close_sync()
            ok("Browser closed")
        except Exception as e:
            err(f"Close failed: {e}")
        return True

    if sub == "newtab":
        url = parts[1] if len(parts) >= 2 else "about:blank"
        try:
            result = bridge.new_tab_sync(url)
            if result.get("ok"):
                ok(f"New tab: {result.get('tab_id')} — {result.get('url')}")
            else:
                err(f"newtab failed: {result.get('error')}")
        except Exception as e:
            err(f"newtab failed: {e}")
        return True

    if sub == "switchtab":
        if len(parts) < 2:
            err("Usage: /webbridge switchtab <tab_id>")
            return True
        tab_id = parts[1]
        try:
            result = bridge.switch_tab_sync(tab_id)
            if result.get("ok"):
                ok(f"Switched to: {tab_id} — {result.get('url')}")
            else:
                err(f"switchtab failed: {result.get('error')}")
        except Exception as e:
            err(f"switchtab failed: {e}")
        return True

    if sub == "closetab":
        if len(parts) < 2:
            err("Usage: /webbridge closetab <tab_id>")
            return True
        tab_id = parts[1]
        try:
            result = bridge.close_tab_sync(tab_id)
            if result.get("ok"):
                ok(f"Closed: {tab_id}")
                info(f"Active tab: {result.get('active_tab')}")
                info(f"Remaining: {', '.join(result.get('remaining_tabs', []))}")
            else:
                err(f"closetab failed: {result.get('error')}")
        except Exception as e:
            err(f"closetab failed: {e}")
        return True

    if sub == "listtabs":
        try:
            result = bridge.list_tabs_sync()
            if result.get("ok"):
                ok(f"Tabs ({len(result.get('tabs', []))}):")
                for t in result.get("tabs", []):
                    marker = " ●" if t.get("active") else ""
                    info(f"  {t.get('tab_id')}{marker} — {t.get('title', 'N/A')[:40]} — {t.get('url', 'N/A')[:60]}")
            else:
                err(f"listtabs failed: {result.get('error')}")
        except Exception as e:
            err(f"listtabs failed: {e}")
        return True

    if sub == "help":
        info("WebBridge commands:")
        info("  /webbridge status          — Show browser status")
        info("  /webbridge open <url>      — Open URL")
        info("  /webbridge click <sel>     — Click element")
        info("  /webbridge type <sel> <t>  — Type text")
        info("  /webbridge screenshot [p]  — Take screenshot")
        info("  /webbridge extract [t|d]   — Extract text or DOM")
        info("  /webbridge scroll [u|d]    — Scroll page")
        info("  /webbridge newtab [url]    — Open new tab")
        info("  /webbridge switchtab <id>  — Switch to tab")
        info("  /webbridge closetab <id>   — Close tab")
        info("  /webbridge listtabs        — List all tabs")
        info("  /webbridge close           — Close browser")
        info("  /webbridge help            — Show this help")
        return True

    err(f"Unknown subcommand: {sub}.  Use /webbridge help")
    return True


COMMANDS = {
    "tts":         cmd_tts,
    "say":         cmd_say,
    "help":        cmd_help,
    "clear":       cmd_clear,
    "model":       cmd_model,
    "config":      cmd_config,
    "save":        cmd_save,
    "load":        cmd_load,
    "history":     cmd_history,
    "context":     cmd_context,
    "cost":        cmd_cost,
    "verbose":     cmd_verbose,
    "max_fix":     cmd_max_fix,
    "thinking":    cmd_thinking,
    "soul":        cmd_soul,
    "schema":      cmd_schema,
    "deep_override": cmd_deep_override,
    "deep_tools":  cmd_deep_tools,
    "autojob":     cmd_autojob,
    "auto_show":   cmd_auto_show,
    "sticky_input": cmd_sticky_input,
    "hide_sender": cmd_hide_sender,
    "theme": cmd_theme,
    "history":     cmd_history,
    "mem_palace":  cmd_mem_palace,
    "harvest":  cmd_harvest,
    "harvest-claude": cmd_harvest,
    "claude-harvest": cmd_harvest,
    "harvest-kimi": cmd_harvest_kimi,
    "harvest-gemini": cmd_harvest_gemini,
    "gemini-harvest": cmd_harvest_gemini,
    "gemini_harvest": cmd_harvest_gemini,
    "harvest-deepseek": cmd_harvest_deepseek,
    "deepseek-harvest": cmd_harvest_deepseek,
    "harvest-qwen":     cmd_harvest_qwen,
    "qwen-harvest":     cmd_harvest_qwen,
    "gemini_chats": cmd_gemini_chats,
    "kimi_chats": cmd_kimi_chats,
    "schema_autoload": cmd_schema_autoload,
    "ultra_search": cmd_ultra_search,
    "permissions": cmd_permissions,
    "afk":         cmd_afk,
    "yolo":        cmd_yolo,
    "cwd":         cmd_cwd,
    "skills":      cmd_skills,
    "skill":       cmd_skill,
    "memory":      cmd_memory,
    "agents":      cmd_agents,
    "mcp":         cmd_mcp,
    "plugin":      cmd_plugin,
    "tasks":       cmd_tasks,
    "task":        cmd_tasks,
    "proactive":   cmd_proactive,
    "daemon":      cmd_daemon,
    "bg":          cmd_bg,
    "lite":        cmd_lite,
    "cloudsave":   cmd_cloudsave,
    "voice":       cmd_voice,
    "wake":        cmd_wake,
    "git":         cmd_git,
    "webchat":     cmd_webchat,
    "webbridge":   cmd_webbridge,
    "sandbox":     cmd_sandbox,
    "gui":         cmd_gui,
    "brave":       cmd_brave,
    "rtk":         cmd_rtk,
    "image":       cmd_image,
    "img":         cmd_image,
    "brainstorm":  cmd_brainstorm,
    "worker":      cmd_worker,
    "kill_tmux":   cmd_kill_tmux,
    "ssj":         cmd_ssj,
    "telegram":    cmd_telegram,
    "checkpoint":  cmd_checkpoint,
    "rewind":      cmd_rewind,
    "plan":        cmd_plan,
    "compact":     cmd_compact,
    "init":        cmd_init,
    "export":      cmd_export,
    "fork":        cmd_fork,
    "undo":        cmd_undo,
    "add-dir":     cmd_add_dir,
    "import":      cmd_import,
    "copy":        cmd_copy,
    "shell":       cmd_shell,
    "status":      cmd_status,
    "doctor":      cmd_doctor,
    "exit":        cmd_exit,
    "quit":        cmd_exit,
    "resume":      cmd_resume,
    "news":        cmd_news,
    "batch":       cmd_batch,
    "claude_chats": cmd_claude_chats,
    "roundtable":  cmd_roundtable,
}


def handle_slash(line: str, state, config) -> Union[bool, tuple]:
    """Handle /command [args]. Returns True if handled, tuple (skill, args) for skill match."""
    if not line.startswith("/"):
        return False
    parts = line[1:].split(None, 1)
    if not parts:
        return False
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    handler = COMMANDS.get(cmd)
    if handler:
        result = handler(args, state, config)
        # cmd_voice/cmd_image/cmd_brainstorm/cmd_plan return sentinels to ask the REPL to run_query
        if isinstance(result, tuple) and result[0] in ("__voice__", "__image__", "__brainstorm__", "__worker__", "__ssj_cmd__", "__ssj_query__", "__ssj_debate__", "__ssj_passthrough__", "__ssj_promote_worker__", "__plan__", "__plugin_main_agent__", "__roundtable__", "__roundtable_stop__"):
            return result
        return True

    # Fall through to skill lookup
    from skill import find_skill
    skill = find_skill(line)
    if skill:
        cmd_parts = line.strip().split(maxsplit=1)
        skill_args = cmd_parts[1] if len(cmd_parts) > 1 else ""
        return (skill, skill_args)

    err(f"Unknown command: /{cmd}  (type /help for commands)")
    return True


# ── Input history setup ────────────────────────────────────────────────────

# Descriptions and subcommands for each slash command (used by Tab completion)
_CMD_META: dict[str, tuple[str, list[str]]] = {
    "help":        ("Show help",                          []),
    "clear":       ("Clear conversation history",         []),
    "model":       ("Show / set model",                   []),
    "config":      ("Show / set config key=value",        []),
    "save":        ("Save session to file",               []),
    "load":        ("Load a saved session",               []),
    "history":     ("Show conversation history",          []),
    "context":     ("Show token-context usage",           []),
    "cost":        ("Show cost estimate",                 []),
    "verbose":     ("Toggle verbose output",              []),
    "git":         ("Toggle Git status injection",        []),
    "thinking":    ("Set extended-thinking level",        ["off", "min", "med", "max", "raw", "normal", "0", "1", "2", "3", "4"]),
    "soul":        ("List/switch active soul identity",   ["chill", "forensic"]),
    "schema":      ("Inspect tool input schemas (human)",  ["--json"]),
    "deep_override": ("Toggle DeepSeek simplified prompt",  []),
    "deep_tools":  ("Toggle DeepSeek auto tool-wrap",     []),
    "autojob":     ("Toggle auto-job printer",            []),
    "permissions": ("Set permission mode",                ["auto", "accept-all", "manual"]),
    "afk":         ("Toggle AFK mode (auto-dismiss, auto-approve)", []),
    "yolo":        ("Toggle YOLO mode (auto-approve ALL)", []),
    "cwd":         ("Show / change working directory",    []),
    "skills":      ("List available skills",              []),
    "skill":       ("Manage skills",                      ["list", "get", "use", "remove", "info"]),
    "memory":      ("Manage persistent memories",          ["list", "load", "permanent", "unbind", "consolidate", "delete", "purge", "purge-soul"]),
    "agents":      ("Show background agents",             []),
    "mcp":         ("Manage MCP servers",                 ["reload", "add", "remove"]),
    "plugin":      ("Manage plugins",                     ["install", "uninstall", "enable",
                                                           "disable", "disable-all", "update",
                                                           "recommend", "info"]),
    "tasks":       ("Manage tasks",                       ["create", "delete", "get", "clear",
                                                           "todo", "in-progress", "done", "blocked"]),
    "task":        ("Manage tasks (alias)",               ["create", "delete", "get", "clear",
                                                           "todo", "in-progress", "done", "blocked"]),
    "proactive":   ("Manage proactive background watcher", ["off"]),
    "daemon":      ("Toggle daemon — allow external triggers (Telegram) to spawn Dulus", ["on", "off"]),
    "bg":          ("Background Dulus — one detached daemon for CLI + Web + Telegram", ["start", "stop", "kill", "status", "attach"]),
    "lite":        ("Toggle lite mode (reduce system prompt)", ["on", "off"]),
    "rtk":         ("Toggle RTK token-optimized shell rewriting", ["on", "off"]),
    "cloudsave":   ("Cloud-sync sessions to GitHub Gist", ["setup", "auto", "list", "load", "push"]),
    "tts":         ("Toggle automatic TTS + lang/provider/auto", ["lang", "provider", "voice", "auto"]),
    "voice":       ("Voice input (record → STT)",         ["lang", "status", "device"]),
    "wake":        ("Wake-word hotword detection",        ["on", "off", "status", "phrases", "calibrate", "test", "threshold"]),
    "image":       ("Send clipboard image to model",      []),
    "img":         ("Send clipboard image (alias)",       []),
    "batch":       ("Manage Kimi Batch tasks",            ["status", "list", "fetch"]),
    "roundtable":  ("Start a multi-model roundtable discussion", ["stop"]),
    "brainstorm":  ("Multi-persona AI debate + auto tasks", []),
    "worker":      ("Auto-implement pending tasks",       []),
    "kill_tmux":   ("Kill all tmux/psmux servers",        []),
    "ssj":         ("SSJ Developer Mode — power menu",    []),
    "telegram":    ("Telegram bot bridge",                ["stop", "status"]),
    "checkpoint":  ("List / restore checkpoints",          ["clear"]),
    "rewind":      ("Rewind to checkpoint (alias)",        ["clear"]),
    "plan":        ("Enter/exit plan mode",                ["done", "status"]),
    "compact":     ("Compact conversation history",         []),
    "init":        ("Initialize DULUS.md template",        []),
    "export":      ("Export conversation to file",          []),
    "fork":        ("Fork session at a turn",               []),
    "undo":        ("Undo last turn",                       []),
    "add-dir":     ("Manage additional workspace dirs",     ["list", "remove"]),
    "import":      ("Import from file or session",          []),
    "copy":        ("Copy last response or file to clipboard", ["file"]),
    "shell":       ("Toggle shell mode or run command",     ["on", "off"]),
    "status":      ("Show session status and model info",   []),
    "doctor":      ("Diagnose installation health",         []),
    "exit":        ("Exit dulus",              []),
    "quit":        ("Exit (alias for /exit)",             []),
    "resume":      ("Resume last session",                []),
    "news":        ("Show latest project news",           []),
    "claude_chats": ("List Claude.ai conversations",       ["all"]),
    "gemini_chats": ("Manage Gemini Web conversations",    ["new"]),
    "gemini_harvest": ("Harvest Gemini Web cookies (alias)", []),
    "harvest-claude": ("Harvest Claude.ai cookies (alias)", []),
    "webchat":       ("Spawn web chat UI",                 ["stop", "lan"]),
    "webbridge":     ("Control WebBridge browser",          ["status", "open", "click", "type", "screenshot", "extract", "scroll", "newtab", "switchtab", "closetab", "listtabs", "close", "help"]),
    "sandbox":       ("Open Dulus Sandbox OS in browser",  ["stop"]),
    "gui":           ("Launch desktop GUI",                 []),
}


def setup_readline(history_file: Path):
    if readline is None:
        return
    try:
        readline.read_history_file(str(history_file))
    except FileNotFoundError:
        pass
    readline.set_history_length(1000)
    atexit.register(readline.write_history_file, str(history_file))

    # Allow "/" to be part of a completion token so "/model" is one word
    delims = readline.get_completer_delims().replace("/", "")
    readline.set_completer_delims(delims)

    def completer(text: str, state: int):
        line = readline.get_line_buffer()

        # ── Completing a command name: line has "/" but no space yet ──────────
        if "/" in line and " " not in line:
            matches = sorted(f"/{c}" for c in _CMD_META if f"/{c}".startswith(text))
            return matches[state] if state < len(matches) else None

        # ── Completing a subcommand: "/cmd <partial>" ─────────────────────────
        if line.startswith("/") and " " in line:
            cmd = line.split()[0][1:]          # e.g. "mcp"
            if cmd in _CMD_META:
                subs = _CMD_META[cmd][1]
                matches = sorted(s for s in subs if s.startswith(text))
                return matches[state] if state < len(matches) else None

        return None

    def display_matches(substitution: str, matches: list, longest: int):
        """Custom display: show command descriptions alongside each match."""
        sys.stdout.write("\n")
        line = readline.get_line_buffer()
        is_cmd = "/" in line and " " not in line

        if is_cmd:
            col_w = max(len(m) for m in matches) + 2
            for m in sorted(matches):
                cmd = m[1:]
                desc = _CMD_META.get(cmd, ("", []))[0]
                subs = _CMD_META.get(cmd, ("", []))[1]
                sub_hint = ("  [" + ", ".join(subs[:4])
                            + ("…" if len(subs) > 4 else "") + "]") if subs else ""
                sys.stdout.write(f"  {C['cyan']}{m:<{col_w}}{C['reset']}  {desc}{sub_hint}\n")
        else:
            for m in sorted(matches):
                sys.stdout.write(f"  {m}\n")
        sys.stdout.flush()

    try:
        readline.set_completion_display_matches_hook(display_matches)
    except AttributeError:
        pass  # pyreadline3 on Windows doesn't support this hook
    readline.set_completer(completer)
    # Autosuggestion-feel: first Tab shows full match list (no beep), case-insensitive,
    # coloured prefix, and "/" anywhere triggers an implicit completion hint on Tab.
    for _rl_setting in (
        "tab: complete",
        "set show-all-if-ambiguous on",
        "set show-all-if-unmodified on",
        "set completion-ignore-case on",
        "set menu-complete-display-prefix on",
        "set colored-completion-prefix on",
        "set colored-stats on",
        "set visible-stats on",
    ):
        try:
            readline.parse_and_bind(_rl_setting)
        except Exception:
            pass


# ── Main REPL ──────────────────────────────────────────────────────────────

def repl(config: dict, initial_prompt: str = None):
    import uuid
    import threading
    from config import HISTORY_FILE
    from context import build_system_prompt
    from agent import AgentState, run, TextChunk, ThinkingChunk, ToolStart, ToolEnd, TurnDone, PermissionRequest
    from tools import input_setup, HAS_PROMPT_TOOLKIT

    setup_readline(HISTORY_FILE)
    
    # prompt_toolkit uses a different history format than readline
    PT_HISTORY_FILE = HISTORY_FILE.with_name("input_history_pt.txt")
    
    state = AgentState()
    verbose = config.get("verbose", False)
    config["_tg_send_callback"] = _tg_send

    # ── Wake-word queue ──
    import queue as _queue
    _wake_queue: "_queue.Queue[str]" = _queue.Queue()

    def _render_toolbar() -> str:
        """Return ANSI toolbar string for prompt_toolkit bottom bar.

        Kimi-cli style: mostly gray, with semantic color only for alerts.
        """
        parts: list[str] = []

        # Model — gray bold (primary info but neutral)
        model = config.get("model", "")
        if model:
            parts.append(clr(f"🧠 {model}", "gray", "bold"))

        # CWD — gray
        try:
            cwd = Path.cwd().name
            if cwd:
                parts.append(clr(f"📁 {cwd}", "gray"))
        except Exception:
            pass

        # Git branch — gray
        try:
            if _git_prompt is not None:
                _gb = _git_prompt.git_badge()
                if _gb:
                    parts.append(clr(f"💻 {_gb}", "gray"))
        except Exception:
            pass

        # Context usage — gray (kimi-cli style, no semantic color in toolbar)
        try:
            from compaction import estimate_tokens, get_context_limit
            _model = config.get("model", "")
            _used = estimate_tokens(state.messages, _model, config)
            _limit = get_context_limit(_model) or 128000
            _pct = int((_used * 100 / _limit) if _limit else 0)
            parts.append(clr(f"📊 ctx {_pct}%", "gray"))
        except Exception:
            pass

        # Permission mode — gray normally, RED if accept-all (dangerous)
        pmode = config.get("permission_mode", "auto")
        lock = "🔓" if pmode == "accept-all" else "🔒"
        _pmode_color = "red" if pmode == "accept-all" else "gray"
        parts.append(clr(f"{lock} {pmode}", _pmode_color))

        # Separator in gray
        return clr("  ·  ", "gray").join(parts) if parts else ""

    # Setup slash-command autocompletion with prompt_toolkit if available
    if HAS_PROMPT_TOOLKIT and input_setup:
        # Use the global COMMANDS and _CMD_META from dulus.py
        commands_provider = lambda: dict(COMMANDS)
        meta_provider = lambda: dict(_CMD_META)
        input_setup(commands_provider, meta_provider, toolbar_provider=_render_toolbar)

    # Collected status lines from init steps. Printed AFTER the banner so the
    # logo + box stay visually clean. Soul picker (only thing that needs
    # interactive input) prints inline then we cls before the banner.
    startup_status_msgs: list[str] = []

    # ── Output folder for scratch .txt files (thoughts, lyrics, summaries, …)
    # Auto-created so the model can write to ~/.dulus/output/ without errors.
    try:
        (Path.home() / ".dulus" / "output").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # ── License gate (KevRojo — tu esfuerzo, tu leche) ───────────────────────
    _license_key = os.environ.get("DULUS_LICENSE_KEY", "")
    if not _license_key:
        _lic_file = Path.home() / ".dulus" / ".license_key"
        if _lic_file.exists():
            _license_key = _lic_file.read_text().strip()
    lic = LicenseManager(_license_key)
    config["_license"] = lic
    _lic_banner = lic.status_banner()
    if lic.tier != LicenseTier.FREE or lic.error:
        # Only show banner if PRO/ENTERPRISE or if there is an error
        startup_status_msgs.append(clr(f"  🗝  {_lic_banner}", "yellow" if lic.error else "green", "bold"))

    # ── Memory Palace Initialization ──────────────────────────────────────────
    try:
        from memory import ensure_memory_palace
        if ensure_memory_palace():
            startup_status_msgs.append(clr("  🏛  Memory Palace initialized: 7 core buckets established.", "cyan", "bold"))
    except Exception:
        pass

    # ── Soul Initialization ───────────────────────────────────────────────────
    # Loads the identity. One file, one soul: ~/.dulus/memory/soul.md.
    # Delete or rename the file to skip loading. Edit it to customize identity.
    try:
        from memory import USER_MEMORY_DIR
        soul_path = USER_MEMORY_DIR / "soul.md"
        if soul_path.exists():
            content = soul_path.read_text(encoding="utf-8", errors="replace")
            if content.strip():
                state.messages.append({
                    "role": "assistant",
                    "content": f"[Identity Essence Loaded: soul]\n\n{content}",
                })
                config["_soul_active"] = "soul"
                startup_status_msgs.append(
                    clr(f"  ✨ Soul loaded: {len(content)} chars", "magenta", "bold")
                )
    except Exception:
        pass

    # ── Tool Schema Injection ─────────────────────────────────────────────────
    # First thing the agent should "see" is the full tool inventory with schemas.
    # Same content as `/schema` (no args) — name + description per tool, grouped.
    # Toggle with /schema_autoload. Default ON.
    if config.get("schema_autoload", True):
        try:
            from tool_registry import get_all_tools
            _tools = get_all_tools()
            if _tools:
                _lines = [f"[Tool Schema Inventory — {len(_tools)} tools registered. "
                          "These are the canonical tools. Prefer them over shelling out via Bash.]"]
                _groups: dict[str, list] = {}
                for t in _tools:
                    sch = t.schema or {}
                    key = "Core"
                    if sch.get("_plugin"):
                        key = sch["_plugin"]
                    elif "_" in t.name and t.name.split("_", 1)[0] in {
                        "memory", "tmux", "task", "plugin", "skill", "mcp", "subagent",
                    }:
                        key = t.name.split("_", 1)[0].capitalize()
                    _groups.setdefault(key, []).append(t)
                for key in sorted(_groups):
                    _lines.append(f"\n  {key}  ({len(_groups[key])})")
                    for t in _groups[key]:
                        desc = (t.schema or {}).get("description", "")
                        if len(desc) > 100:
                            desc = desc[:97] + "..."
                        _lines.append(f"    - {t.name:<30} {desc}")
                _schema_blob = "\n".join(_lines)
                state.messages.append({
                    "role": "system",
                    "content": _schema_blob,
                })
                startup_status_msgs.append(
                    clr(f"  📋 Tool schema injected: {len(_tools)} tools, {len(_schema_blob)} chars",
                        "cyan", "bold")
                )
        except Exception as e:
            startup_status_msgs.append(clr(f"  ⚠ Schema inject skip: {e}", "yellow"))

    # ── Gold Memories Auto-Load ───────────────────────────────────────────────
    # Memories marked with `gold: true` (via /memory permanent) are injected
    # at startup the same way as Soul.
    try:
        from memory import load_index
        gold_entries = [e for e in load_index("all") if getattr(e, "gold", False)]
        for e in gold_entries:
            state.messages.append({
                "role": "assistant",
                "content": f"[Golden Memory Loaded: {e.name}]\n\n{e.content}",
            })
            startup_status_msgs.append(clr(f"  🏆 Gold memory loaded: {e.name}", "yellow", "bold"))
    except Exception:
        pass

    # ── Shell Environment Detection ───────────────────────────────────────────
    # Detect shell once at startup and cache in config
    try:
        from context import detect_shell_runtime
        shell_info = detect_shell_runtime()
        config["_shell_info"] = shell_info
        startup_status_msgs.append(clr(f"  🖥️  Shell detected: {shell_info.get('shell_type', 'unknown')}", "cyan"))
    except Exception:
        pass

    # ── Checkpoint system init ──
    import checkpoint as ckpt
    session_id = uuid.uuid4().hex[:8]
    config["_session_id"] = session_id
    ckpt.set_session(session_id)
    ckpt.cleanup_old_sessions()
    # Initial snapshot: capture the "blank slate" before any prompts
    ckpt.make_snapshot(session_id, state, config, "(initial state)", tracked_edits=None)

    # Banner
    if not initial_prompt:
        from providers import detect_provider
        
        # ── Dulus startup animation ──
        _DULUS_FRAMES = [
            "     ✦",
            "    ✦ ·",
            "   ✦ · ·",
            "  ✦ · · ·",
            " ✦ · · · ·",
            "✦ · · · · ·",
        ]
        _DULUS_LOGO = [
            "                                                                 ",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⠿⠟⠛⠛⢛⣻⡿⠟",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡾⢿⣿⣿⣷⣾⣿⣿⣏⠀⣀⣤⡶⠛⠉⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡴⠋⠀⠘⢿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⠞⠋⠀⠀⠀⠀⠘⢿⣿⣿⣿⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡾⠋⠀⠀⠀⠀⠀⠀⠀⠸⣿⣿⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣶⣿⣿⣶⣦⣤⣄⣀⣠⣤⣽⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡾⣻⣿⣿⣿⣿⠟⠁⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡞⣫⣼⣿⣿⣿⠟⠁⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣾⣿⣾⣿⠿⠿⠋⠁⠀⠀⠀⣤⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⡿⠃⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⡿⠁⠀⠀⠀⣀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⠟⠁⠀⢀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⢃⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⣀⣼⣿⣿⣿⣿⣿⣿⣿⣿⠿⠟⠋⠁⠈⠉⠛⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⠿⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⡟⢻⡉⠉⠉⠉⠹⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⢠⣾⣿⣿⣿⣿⣿⠟⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢷⠸⣇⠀⠀⠀⠀⣿⠹⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⣠⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇⢿⡀⠀⠀⠀⢹⡆⢿⠀⣠⠤⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⢸⣿⡿⢻⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⠘⣧⠶⠶⣤⣤⠿⠾⠟⠁⠀⠈⠻⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠸⠿⠁⠘⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣶⣶⠒⠒⠚⠋⠁⠀⠀⠈⢿⣄⠀⠀⠀⠀⢀⣀⢨⡿⣶⣄⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡾⠙⠛⠁⠀⠀⠀⠀⠀⠀⠀⣤⡸⢿⢷⣤⣀⠀⠘⠛⠏⣥⣶⠟⣛⣻⣶⡄⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠺⠿⢙⣃⣶⡟⣛⢿⡟⢦⡄⠀⠈⠐⠿⠛⠋⠁⢻⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡙⠒⠤⠤⢤⣤⣄⣀⠀⠀⠀⠀⠘⠛⢰⣶⠛⠀⠀⢀⣿⡄⠀⠀⢀⣀⣤⢔⡿⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⠦⠤⢤⣤⣄⣀⣈⡉⣓⡦⢤⣄⣀⣀⣀⣀⣠⡴⠚⣽⣿⣭⡭⠭⠷⠒⠋⠀⠀⠀⠀⠀⠀⠀",
            "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠛⠻⢾⣯⣧⣬⣭⣤⡶⠖⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
        ]
        _DULUS_LOGO.append("     " + clr("v" + VERSION, "green", "bold"))
        _DULUS_LOGO.append("     " + clr("New: Automated Plugin Adapter! Type /news", "cyan", "dim"))
        _DULUS_LOGO.append("                                                                 ")

        # Spinning galaxy animation
        _GALAXY_FRAMES = ["◜", "◝", "◞", "◟"]
        try:
            for i in range(8):
                frame = _GALAXY_FRAMES[i % 4]
                sys.stdout.write(f"\r  {clr(frame, 'cyan', 'bold')} Initializing Dulus...")
                sys.stdout.flush()
                time.sleep(0.12)
            sys.stdout.write(f"\r{' ' * 40}\r")
            sys.stdout.flush()
        except Exception:
            pass

        # Print logo
        for line in _DULUS_LOGO:
            print(clr(line, "cyan", "bold"))
        print()

        globals()["_DULUS_LOGO_CACHED"] = list(_DULUS_LOGO)

        _print_dulus_banner(config, with_logo=False)

        # Show active non-default settings
        active_flags = []
        if config.get("verbose"):
            active_flags.append("verbose")
        if config.get("git_status", True):
            active_flags.append("git")
        _thk_lvl = _normalize_thinking_level(config.get("thinking", 0))
        if _thk_lvl > 0:
            _thk_label = {1: "min", 2: "med", 3: "max", 4: "raw"}.get(_thk_lvl, str(_thk_lvl))
            active_flags.append(f"thinking:{_thk_label}")
        if config.get("ULTRA_SEARCH") in (1, "1", True, "true"):
            active_flags.append("ultra_search")
        if config.get("_proactive_enabled"):
            active_flags.append("proactive")
        if config.get("lite_mode"):
            active_flags.append("lite")
        if config.get("telegram_token") and _tg_get_chat_ids(config):
            active_flags.append("telegram")
        if active_flags:
            flags_str = " · ".join(clr(f, "green") for f in active_flags)
            info(f"Active: {flags_str}")

        # Print collected startup status (soul, training, gold mems, shell, etc.)
        # These were buffered during init so the banner stays visually clean.
        if startup_status_msgs:
            print()
            for msg in startup_status_msgs:
                print(msg)
        print()

    query_lock = threading.RLock()
    config["_query_lock"] = query_lock

    # Apply rich_live config: disable in-place Live streaming if terminal has issues.
    # Auto-detect SSH sessions, dumb terminals, and legacy Windows consoles (CMD/PowerShell)
    # where ANSI cursor management for Live updates causes "ghosting" artifacts during scrolling.
    import os as _os
    _in_ssh = bool(_os.environ.get("SSH_CLIENT") or _os.environ.get("SSH_TTY"))
    _is_dumb = (console is not None and getattr(console, "is_dumb_terminal", False))
    _is_windows = _os.name == "nt"
    # Detect Windows Terminal or modern terminals (VS Code, etc.)
    _is_modern_win = bool(_os.environ.get("WT_SESSION") or _os.environ.get("TERM_PROGRAM"))
    # Always enable Rich on Windows if using Windows Terminal or modern terminal
    # WT_SESSION indicates Windows Terminal; TERM_PROGRAM indicates VS Code, etc.
    if _is_windows and _is_modern_win:
        # Force enable Rich for Windows Terminal users
        _rich_live_default = not _in_ssh and not _is_dumb
    else:
        _rich_live_default = not _in_ssh and not _is_dumb and not (_is_windows and not _is_modern_win)
    
    global _RICH_LIVE
    _RICH_LIVE = _RICH and config.get("rich_live", _rich_live_default)

    # Initialize proactive polling state in config (avoids module-level globals)
    config.setdefault("_proactive_enabled", False)
    config.setdefault("_proactive_interval", 300)
    config.setdefault("_last_interaction_time", time.time())
    if config.get("_proactive_thread") is None:
        t = threading.Thread(target=_proactive_watcher_loop, args=(config,), daemon=True)
        config["_proactive_thread"] = t
        t.start()

    # Job Sentinel: Detect background completions and wake up the agent
    if config.get("_job_sentinel_thread") is None:
        tj = threading.Thread(target=_job_sentinel_loop, args=(config, state), daemon=True)
        config["_job_sentinel_thread"] = tj
        tj.start()

    # IPC server — lets `dulus "..."` from another shell join this REPL's
    # session instead of spawning a fresh process. Tiny TCP socket on
    # 127.0.0.1:5151, no daemon manager required.
    if config.get("_ipc_thread") is None and not config.get("_ipc_disabled"):
        ti = threading.Thread(
            target=_ipc_server_loop, args=(config, state), daemon=True
        )
        config["_ipc_thread"] = ti
        ti.start()
    
    def run_query(user_input: str, is_background: bool = False):
        nonlocal verbose

        # ── Expand paste placeholders before the agent sees them ─────────────
        if _paste_ph is not None:
            user_input = _paste_ph.expand_placeholders(user_input)

        global _SUPPRESS_CONSOLE, _RICH_LIVE
        _SUPPRESS_CONSOLE = False  # never suppress — background output should be visible

        # ── Thread-safe background streaming fix ─────────────────────────────
        # Rich Live is NOT thread-safe. When a timer/job/Telegram thread fires
        # run_query in the background, Rich Live's cursor-based repaint can
        # leave "ghost lines" that get re-printed on subsequent turns.
        # Force plain streaming for background turns — each chunk goes straight
        # to stdout (or _OutputRedirector in split-layout) without Live state.
        _saved_rich_live = _RICH_LIVE
        _old_stdout = None
        _bg_buffer = None
        if is_background:
            _RICH_LIVE = False
            # Kill any stale Live instance and drain the buffer so we don't
            # carry over partial text from a previous turn.
            flush_response()
            _accumulated_text.clear()
            # Force cursor to start of a clean line before background output.
            # Rich Live's cursor repaint can leave the cursor mid-line; without
            # this, prompt_toolkit's next redraw may mis-count lines and cause
            # ghost text to reappear below new messages.
            sys.stdout.write("\r\n")
            sys.stdout.flush()
            # Buffer ALL background stdout into a StringIO and flush it once
            # at the end. This prevents patch_stdout from re-rendering 50×
            # during streaming, which is the root cause of ghost lines on
            # Windows terminals.
            import io
            _old_stdout = sys.stdout
            _bg_buffer = io.StringIO()
            sys.stdout = _bg_buffer
        # ─────────────────────────────────────────────────────────────────────

        try:
            # Mark activity at the START of every turn so long-running model
            # streaming (which can take 20s+) doesn't look like idle time to
            # the background sentinel.
            config["_last_interaction_time"] = time.time()

            # Reset split-layout redirector state so residual buffered text
            # from a previous turn doesn't concatenate with this turn's output.
            if type(sys.stdout).__name__ == "_OutputRedirector":
                sys.stdout.reset()

            # Stale cleanup: _in_telegram_turn must not leak across turns.
            # Otherwise every subsequent turn behaves like a Telegram turn.
            config.pop("_in_telegram_turn", None)

            # Sanitize input to kill Windows surrogate garbage from pasted emojis
            user_input = sanitize_text(user_input)

            with query_lock:  # blocks sentinel from firing while we're streaming
                # Catch any jobs that finished while user was typing
                _print_background_notifications(state)
                verbose = config.get("verbose", False)

                # ── Skill inject (one-shot, cleared after use) ───────────────────
                _skill_body = config.pop("_skill_inject", "")
                if _skill_body:
                    user_input = (
                        "[SKILL CONTEXT — follow these instructions for this turn]\n\n"
                        + _skill_body
                        + "\n\n---\n\n[USER MESSAGE]\n"
                        + user_input
                    )
                    print(clr(f"  [skill] injected {len(_skill_body)} chars", "magenta"))

                # ── MemPalace: per-turn memory injection ────────────────────────
                # Default ON. Toggle with /mem_palace. Skips background-triggered
                # turns and trivial messages so we don't burn tokens on "klk".
                _mp_dbg = config.get("mem_palace_print", False)
                def _mp_log(msg, color="magenta"):
                    if _mp_dbg:
                        print(clr(f"  [mempalace] {msg}", color))

                if not config.get("mem_palace", True):
                    _mp_log("skip: mem_palace OFF", "dim")
                elif is_background:
                    _mp_log("skip: background turn", "dim")
                elif not user_input or len(user_input.strip()) < 12:
                    _mp_log(f"skip: input too short ({len(user_input.strip()) if user_input else 0} chars)", "dim")
                else:
                    _trivial = {"hola", "klk", "gracias", "ok", "si", "no", "dale",
                                "exit", "quit", "help", "thanks", "bien"}
                    _first = user_input.strip().lower().split()[0].strip(".,!?;:")
                    if _first in _trivial:
                        _mp_log(f"skip: trivial first word '{_first}'", "dim")
                    else:
                        try:
                            import re as _re
                            _q = user_input.strip()[:200]
                            _mp_log(f"querying: {_q!r}")
                            _raw_hits = []
                            # Primary: query the real MemPalace (~/.mempalace/palace) which holds
                            # the rich corpus (hija_palace, soul, bond, sessions, knowledge, etc.).
                            # Dulus's local find_relevant_memories only sees ~/.dulus/memory/*.md,
                            # which is a tiny slice and was the reason the same 3 generic files
                            # kept getting injected on every turn.
                            try:
                                from mempalace.searcher import search_memories as _mp_search
                                from mempalace.config import MempalaceConfig as _MPCfg
                                _palace = _MPCfg().palace_path
                                _res = _mp_search(_q, _palace, n_results=3)
                                for _hit in (_res or {}).get("results", []):
                                    _meta = _hit.get("metadata") or {}
                                    _src = _meta.get("source_file") or _meta.get("name") or "palace"
                                    _name = str(_src).rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
                                    _vec = max(0.0, 1.0 - float(_hit.get("distance", 1.0)))
                                    _bm  = float(_hit.get("bm25_score", 0.0))
                                    _raw_hits.append({
                                        "name": _name,
                                        "description": _meta.get("wing") or _meta.get("room") or "",
                                        "content": _hit.get("text", ""),
                                        "keyword_score": max(_vec, _bm),
                                    })
                                _mp_log(f"mempalace hits: {len(_raw_hits)}")
                            except Exception as _mpe:
                                _mp_log(f"mempalace unavailable, falling back to local: {type(_mpe).__name__}: {_mpe}", "dim")
                            # Fallback: Dulus's local memory dir (the old path)
                            if not _raw_hits:
                                from memory import find_relevant_memories
                                _raw_hits = find_relevant_memories(_q, max_results=3)
                            _MIN_SCORE = 0.15
                            if _mp_dbg:
                                for _h in _raw_hits:
                                    _mp_log(f"  hit: score={float(_h.get('keyword_score', 0.0)):.3f}  {_h.get('name','?')}", "dim")
                            _kept = [h for h in _raw_hits if float(h.get("keyword_score", 0.0)) >= _MIN_SCORE]
                            # ── Dedup: skip memories already injected earlier in this session.
                            # Key by content hash (not name) because mempalace often returns
                            # generic names like "palace" for every hit in a wing — name-based
                            # dedup would over-block. Content hash makes each memory unique.
                            import hashlib as _hashlib
                            def _mp_dedup_key(h):
                                content = (h.get("content") or "").strip()[:240]
                                return _hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()[:12]
                            _seen = config.setdefault("_mp_injected_keys", set())
                            _before_dedup = len(_kept)
                            # Dedup against session cache AND within this turn's hits
                            # (mempalace sometimes returns the same chunk twice in one query).
                            _this_turn = set()
                            _filtered = []
                            for _h in _kept:
                                _k = _mp_dedup_key(_h)
                                if _k in _seen or _k in _this_turn:
                                    continue
                                _this_turn.add(_k)
                                _filtered.append(_h)
                            _kept = _filtered
                            if _before_dedup and not _kept:
                                _mp_log(f"skip: all {_before_dedup} hits already injected this session", "dim")
                            elif _before_dedup != len(_kept):
                                _mp_log(f"dedup: dropped {_before_dedup - len(_kept)} already-injected memories", "dim")
                            if not _kept:
                                _mp_log(f"skip: no hits above threshold {_MIN_SCORE} (raw={len(_raw_hits)})", "dim")
                            else:
                                _BODY_BUDGET = 1800
                                _per_hit = max(300, _BODY_BUDGET // len(_kept))
                                _parts = []
                                for _i, _h in enumerate(_kept, 1):
                                    _name = _h.get("name", f"hit_{_i}")
                                    _desc = _h.get("description", "")
                                    _body = _h.get("content", "").strip()
                                    _snip = _body[:_per_hit] + ("..." if len(_body) > _per_hit else "")
                                    if _desc:
                                        _parts.append(f"### {_name}\n_{_desc}_\n{_snip}")
                                    else:
                                        _parts.append(f"### {_name}\n{_snip}")
                                _hits_str = "\n\n".join(_parts)
                                if len(_hits_str) > 2000:
                                    _hits_str = _hits_str[:2000] + "\n[...truncated]"
                                _mp_log(f"injecting {len(_raw_hits)} memories → {len(_hits_str)} chars", "cyan")
                                _inject = (
                                    "[MemPalace — relevant memories pre-loaded for this turn. "
                                    "Do NOT re-query unless the user explicitly asks for more. "
                                    "The answer to the user's question is very likely already "
                                    "below — read it BEFORE reaching for any tool.]\n\n"
                                    + _hits_str
                                )
                                user_input = (
                                    _inject
                                    + "\n\n---\n\n[USER MESSAGE]\n"
                                    + user_input
                                )
                                # Mark these as injected so we don't repeat them next turn.
                                for _h in _kept:
                                    _seen.add(_mp_dedup_key(_h))
                                if _mp_dbg:
                                    print(clr(
                                        f"\n  ── [MemPalace inject → {len(_inject)} chars] ──",
                                        "magenta", "bold"))
                                    print(clr(_inject, "dim"))
                                    print(clr("  ── [end inject] ──\n", "magenta", "bold"))
                        except Exception as _e:
                            _mp_log(f"exception: {type(_e).__name__}: {_e}", "red")

                # Rebuild system prompt each turn (picks up cwd changes, etc.)
                system_prompt = build_system_prompt(config)

                if is_background and not config.get("_telegram_incoming"):
                    print(clr("\n\n[Background Event Triggered]", "yellow"))
                config["_in_telegram_turn"] = config.pop("_telegram_incoming", False)

                if _use_bubbles():
                    print()
                    _hdr = _bubbles.get_rich_chain(
                        " 🦅 Dulus ", "dark_orange", "black"
                    ).link(" ● ", "green", "black").end()
                    Console(file=sys.stdout, width=console.width, force_terminal=console.is_terminal, legacy_windows=console.legacy_windows, color_system=console.color_system).print(_hdr)
                else:
                    print(clr("\n╭─ Dulus ", "dim") + clr("●", "green") + clr(" ─────────────────────────", "dim"))
                _accumulated_text.clear()   # reset per-turn buffer — prevents background events from re-printing previous turn
                thinking_started = False
                spinner_shown = not is_background
                if spinner_shown:
                    _start_tool_spinner()
                _pre_tool_text = []   # text chunks before a tool call
                _post_tool = False    # true after a tool has executed
                _post_tool_buf = []   # text chunks after tool (to check for duplicates)
                _duplicate_suppressed = False

                try:
                    for event in run(user_input, state, config, system_prompt):
                        # Stop spinner only when visible output arrives
                        if spinner_shown:
                            show_thinking = isinstance(event, ThinkingChunk) and verbose
                            if isinstance(event, TextChunk) or show_thinking or isinstance(event, ToolStart):
                                _stop_tool_spinner()
                                spinner_shown = False
                                # Restore │ prefix for first text chunk in plain-text (non-Rich) mode
                                if isinstance(event, TextChunk) and not _RICH and not _post_tool:
                                    print(clr("│ ", "dim"), end="", flush=True)

                        if isinstance(event, TextChunk):
                            if thinking_started:
                                print("\033[0m\n")  # Reset dim ANSI + break line after thinking block
                                thinking_started = False

                            if _post_tool and not _duplicate_suppressed:
                                # Buffer post-tool text to check for overlaps with pre-tool text
                                _post_tool_buf.append(event.text)
                                post_so_far = "".join(_post_tool_buf)
                                pre_text = "".join(_pre_tool_text)
                            
                                if pre_text:
                                    if pre_text.startswith(post_so_far):
                                        if len(post_so_far) >= len(pre_text):
                                            # Full duplicate confirmed — suppress entirely
                                            _duplicate_suppressed = True
                                            _post_tool_buf.clear()
                                        continue
                                    elif post_so_far.startswith(pre_text):
                                        # Model repeated everything and is now adding more
                                        # Skip the part that matches pre_text
                                        new_stuff = post_so_far[len(pre_text):]
                                        if new_stuff:
                                            stream_text(new_stuff)
                                            _duplicate_suppressed = True
                                            _post_tool_buf.clear()
                                        continue
                                    
                                # Not a recognizable duplicate — flush and stop checking
                                for chunk in _post_tool_buf:
                                    stream_text(chunk)
                                _post_tool_buf.clear()
                                _duplicate_suppressed = True
                                continue

                            # stream_text auto-starts Live on first chunk when Rich available
                            if not _post_tool:
                                _pre_tool_text.append(event.text)
                            stream_text(event.text)

                        elif isinstance(event, ThinkingChunk):
                            if verbose:
                                if not thinking_started:
                                    flush_response()  # stop Live before printing static thinking
                                    print(clr("  [thinking]", "dim"))
                                    thinking_started = True
                                stream_thinking(event.text, verbose)

                        elif isinstance(event, ToolStart):
                            flush_response()
                            if event.name == "AskUserQuestion":
                                _stop_tool_spinner()
                            print_tool_start(event.name, event.inputs, verbose)

                        elif isinstance(event, PermissionRequest):
                            _stop_tool_spinner()
                            flush_response()
                            event.granted = ask_permission_interactive(event.description, config)
                            # Live will restart automatically on next TextChunk

                        elif isinstance(event, ToolEnd):
                            print_tool_end(event.name, event.result, verbose, config)
                            _post_tool = True
                            _post_tool_buf.clear()
                            _duplicate_suppressed = False
                            if not _RICH:
                                print(clr("│ ", "dim"), end="", flush=True)
                            # If the tool errored, pause the spinner for up to 2 min
                            # (or until this turn ends) so the failure is visible.
                            _errored = isinstance(event.result, str) and (
                                event.result.startswith("Error") or event.result.startswith("Denied")
                            )
                            import time as _t
                            _now = _t.time()
                            _paused_until = globals().get("_SPINNER_PAUSED_UNTIL", 0)
                            if _errored:
                                globals()["_SPINNER_PAUSED_UNTIL"] = _now + 120
                                spinner_shown = False
                            elif _now >= _paused_until:
                                _change_spinner_phrase()
                                _start_tool_spinner()
                                spinner_shown = True

                        elif isinstance(event, TurnDone):
                            _stop_tool_spinner()
                            globals()["_SPINNER_PAUSED_UNTIL"] = 0
                            spinner_shown = False
                            if verbose:
                                flush_response()  # stop Live before printing token info
                                # Distinguish intermediate tool turns from final answer
                                _last_msg = state.messages[-1] if state.messages else {}
                                _had_tools = bool(_last_msg.get("tool_calls"))
                                _label = "tool turn" if _had_tools else "tokens"
                                cache_info = ""
                                if getattr(event, "cache_read_tokens", 0) > 0 or getattr(event, "cache_creation_tokens", 0) > 0:
                                    cache_info = f" | cache: {event.cache_read_tokens} hits / {event.cache_creation_tokens} new"
                                print(clr(
                                    f"\n  [{_label}: +{event.input_tokens} in / "
                                    f"+{event.output_tokens} out{cache_info}]", "dim"
                                ))
                except KeyboardInterrupt:
                    _stop_tool_spinner()
                    flush_response()
                    # Rollback: if interrupted before any assistant message was recorded, 
                    # remove the user message to prevent consecutive user messages in history.
                    if state.messages and state.messages[-1]["role"] == "user" and user_input == state.messages[-1].get("content"):
                        state.messages.pop()
                    raise  # propagate to REPL handler which calls _track_ctrl_c
                except Exception as e:
                    _stop_tool_spinner()
                    import urllib.error
                    # Catch 404 Not Found (Ollama model missing)
                    if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                        from providers import detect_provider
                        if detect_provider(config["model"]) == "ollama":
                            flush_response()
                            err(f"Ollama model '{config['model']}' not found.")
                            if _interactive_ollama_picker(config):
                                # Remove the user message added by run() before retrying
                                if state.messages and state.messages[-1]["role"] == "user":
                                    state.messages.pop()
                                return run_query(user_input, is_background)
                            # User cancelled picker — abort gracefully without crashing
                            return
                    raise e

                _stop_tool_spinner()
                flush_response()  # stop Live, commit any remaining text
            
                # ── Automatic TTS ──
                if config.get("tts_enabled", False):
                    if state.messages and state.messages[-1].get("role") == "assistant":
                        ans_content = state.messages[-1].get("content", "")
                        if isinstance(ans_content, list):
                            parts = [b["text"] if isinstance(b, dict) else str(b) for b in ans_content if (isinstance(b, dict) and b.get("type") == "text") or isinstance(b, str)]
                            ans_content = "\n".join(parts)
                        if ans_content:
                            try:
                                from voice import say
                                say(ans_content, lang=config.get("tts_lang", "es"), provider=config.get("tts_provider", "auto"))
                                # auto-listen: after Dulus spoke, signal the input
                                # loop to open the mic instead of the keyboard prompt
                                if config.get("tts_auto_listen", False):
                                    config["_auto_voice_next"] = True
                                    info("  [TTS] Auto-listen scheduled for next turn.")
                            except Exception as _tts_err:
                                # Log silently in verbose mode only so we don't spam
                                if config.get("verbose"):
                                    warn(f"  TTS playback error: {_tts_err}")

                if not _use_bubbles():
                    print(clr("╰──────────────────────────────────────────────", "dim"))
                print()
            
                # If Telegram is connected and this was a background task, send notification
                # (only if Telegram bridge is still running)
                if is_background:
                    is_tg_turn = config.get("_in_telegram_turn", False)
                    ttok = config.get("telegram_token")
                    # Background broadcasts go to whoever was last active in TG
                    # (or the first configured chat as fallback).
                    _tids = _tg_get_chat_ids(config)
                    tchat = config.get("_active_tg_chat_id") or (_tids[0] if _tids else 0)
                    # Check that Telegram is still active (_telegram_stop not set)
                    if not is_tg_turn and ttok and tchat and _telegram_stop and not _telegram_stop.is_set():
                        if state.messages and state.messages[-1].get("role") == "assistant":
                            ans_content = state.messages[-1].get("content", "")
                            if isinstance(ans_content, list):
                                parts = [b["text"] if isinstance(b, dict) else str(b) for b in ans_content if (isinstance(b, dict) and b.get("type") == "text") or isinstance(b, str)]
                                ans_content = "\n".join(parts)
                            if ans_content:
                                # Send in background thread to avoid blocking console output
                                import threading as _tg_thread
                                _tg_thread.Thread(target=_tg_send, args=(ttok, tchat, ans_content), daemon=True).start()

            # Drain any AskUserQuestion prompts raised during this turn
            from tools import drain_pending_questions
            drain_pending_questions(config)

            # ── Auto-snapshot after each turn ──
            try:
                tracked = ckpt.get_tracked_edits()
                # Throttle: skip snapshot only if no files changed AND no new messages
                last_snaps = ckpt.list_snapshots(session_id)
                skip = False
                if not tracked and last_snaps:
                    if len(state.messages) == last_snaps[-1].get("message_index", -1):
                        skip = True
                if not skip:
                    ckpt.make_snapshot(session_id, state, config, user_input, tracked_edits=tracked)
                ckpt.reset_tracked()
            except Exception:
                pass  # never let checkpoint errors break the REPL

            config["_last_interaction_time"] = time.time()

            # NOTE: We intentionally do NOT use stdout_bypass for background turns.
            # _OutputRedirector already handles output safely; bypassing causes
            # the model response to land on the raw terminal and corrupt the
            # prompt_toolkit rendering.  Keeping everything inside the split
            # layout keeps the display clean and avoids the accumulation bugs.

        finally:
            if is_background and _old_stdout is not None:
                sys.stdout = _old_stdout
                if _bg_buffer is not None:
                    output = _bg_buffer.getvalue()
                    if output:
                        # Bypass patch_stdout entirely for background turns.
                        # Writing directly to the original stdout avoids
                        # prompt_toolkit's broken line-counting that causes
                        # ghost text on Windows terminals.
                        try:
                            import input as _dulus_input
                            if hasattr(_dulus_input, "safe_print_notification"):
                                _note = "\r\n" + output if not output.startswith("\r\n") else output
                                _note = _note.rstrip("\n")
                                _dulus_input.safe_print_notification(_note)
                            else:
                                print(output, end="")
                                if not output.endswith("\n"):
                                    print()
                                sys.stdout.flush()
                        except Exception:
                            print(output, end="")
                            if not output.endswith("\n"):
                                print()
                            sys.stdout.flush()
            _RICH_LIVE = _saved_rich_live

    config["_run_query_callback"] = lambda msg: run_query(msg, is_background=True)
    # Expose main agent state so sub-agents (via AskMainAgentQuestion) can
    # inject system messages into the main's conversation.
    config["_state"] = state

    def _handle_slash_from_telegram(line: str):
        """Process a /command from Telegram, handling sentinels inline.
        Returns 'simple' for toggle commands, 'query' if run_query was called."""
        result = handle_slash(line, state, config)
        if not isinstance(result, tuple):
            return "simple"
        # Process sentinels the same way the REPL does
        if result[0] == "__brainstorm__":
            _, brain_prompt, brain_out_file = result
            run_query(brain_prompt)
            _save_synthesis(state, brain_out_file)
            _todo_path = str(Path(brain_out_file).parent / "todo_list.txt")
            run_query(
                f"Based on the Master Plan you just synthesized, generate a todo list file at {_todo_path}. "
                "Format: one task per line, each starting with '- [ ] '. "
                "Order by priority. Include ALL actionable items from the plan. "
                "Use the Write tool to create the file. Do NOT explain, just write the file now."
            )
        elif result[0] == "__worker__":
            _, worker_tasks = result
            for i, (line_idx, task_text, prompt) in enumerate(worker_tasks):
                print(clr(f"\n  ── Worker ({i+1}/{len(worker_tasks)}): {task_text} ──", "yellow"))
                run_query(prompt)
        return "query"

    config["_handle_slash_callback"] = _handle_slash_from_telegram

    # ── Auto-start Telegram bridge if configured ──────────────────────
    if config.get("telegram_token") and _tg_get_chat_ids(config):
        global _telegram_thread, _telegram_stop
        if not (_telegram_thread and _telegram_thread.is_alive()):
            config["_state"] = state
            _telegram_stop = threading.Event()
            _telegram_thread = threading.Thread(
                target=_tg_poll_loop,
                args=(config["telegram_token"], _tg_get_chat_ids(config), config),
                daemon=True
            )
            _telegram_thread.start()

    # ── Rapid Ctrl+C force-quit ─────────────────────────────────────────
    # 3 Ctrl+C presses within 2 seconds → immediate hard exit
    # Uses the default SIGINT (raises KeyboardInterrupt) but wraps the
    # main loop to track timing of consecutive interrupts.
    _ctrl_c_times = []

    def _track_ctrl_c():
        """Call this on every KeyboardInterrupt. Returns True if force-quit triggered."""
        now = time.time()
        _ctrl_c_times.append(now)
        # Keep only presses within the last 2 seconds
        _ctrl_c_times[:] = [t for t in _ctrl_c_times if now - t <= 2.0]
        if len(_ctrl_c_times) >= 3:
            _stop_tool_spinner()
            print(clr("\n\n  Force quit (3x Ctrl+C).", "red", "bold"))
            os._exit(1)
        return False

    # ── Main loop ──
    if initial_prompt:
        try:
            run_query(initial_prompt)
        except KeyboardInterrupt:
            _track_ctrl_c()
            print()
        return

    # ── Bracketed paste mode ──────────────────────────────────────────────
    # Terminals that support bracketed paste wrap pasted content with
    #   ESC[200~  (start)  …content…  ESC[201~  (end)
    # This lets us collect the entire paste as one unit regardless of
    # how many newlines it contains, without any fragile timing tricks.
    _PASTE_START = "\x1b[200~"
    _PASTE_END   = "\x1b[201~"
    _bpm_active  = sys.stdin.isatty() and sys.platform != "win32"

    if _bpm_active:
        sys.stdout.write("\x1b[?2004h")   # enable bracketed paste mode
        sys.stdout.flush()

    # ── Sticky input bar (ON by default) ─────────────────────────────────────
    # prompt_toolkit anchors the input line so background prints flow above it.
    # On Windows consoles it can redraw on every keystroke (mild jitter), but
    # the UX win outweighs it. Toggle off with `/sticky_input` if needed.
    _sticky_input_enabled = bool(config.get("sticky_input", True))
    try:
        import common as _cm
        _cm.apply_theme(config.get("theme", "dulus"))
    except Exception:
        pass
    try:
        if hasattr(dulus_input, "set_hide_sender"):
            dulus_input.set_hide_sender(bool(config.get("hide_sender", True)))
    except Exception:
        pass
    if _sticky_input_enabled:
        try:
            from prompt_toolkit import PromptSession as _PTSession
            from prompt_toolkit.formatted_text import ANSI as _PTAnsi
            from prompt_toolkit.patch_stdout import patch_stdout as _pt_patch_stdout
            _pt_session = _PTSession()
            _PT_AVAILABLE = True
        except Exception:
            _PT_AVAILABLE = False
    else:
        _PT_AVAILABLE = False

    in_roundtable_setup = False
    in_roundtable_active = False
    roundtable_models = []
    roundtable_log = []
    roundtable_last_seen_idx = {}
    roundtable_save_path = None  # fixed path for the session, set when table starts

    def _read_input(prompt: str) -> str:
        """Read one user turn, collecting multi-line pastes as a single string.

        Strategy (in priority order):
        0. prompt_toolkit with patch_stdout (only if sticky_input is ON): gives
           an anchored input line so concurrent background prints flow above.
           Off by default because it jitters on Windows consoles.
        1. Bracketed paste mode (ESC[200~ … ESC[201~): reliable, zero latency,
           supported by virtually all modern terminal emulators on Linux/macOS.
        2. Timing fallback: for terminals without bracketed paste support, read
           any data buffered in stdin within a short window after the first line.
        3. Plain input(): for pipes / non-interactive use / Windows.
        """
        import select as _sel

        # ── Phase 0: prompt_toolkit with slash-command autocompletion ─────────
        # When sticky_input is ON  → split layout (fixed bottom bar + recent strip)
        # When sticky_input is OFF → plain PromptSession (just history + completer,
        #                            input line scrolls with output like a normal shell)
        if dulus_input.HAS_PROMPT_TOOLKIT and sys.stdin.isatty():
            try:
                # Remove readline escape markers (\001/\002) - prompt_toolkit doesn't need them
                clean_prompt = prompt.replace("\001", "").replace("\002", "")
                if _sticky_input_enabled:
                    return dulus_input.read_line_split(clean_prompt, PT_HISTORY_FILE)
                else:
                    return dulus_input.read_line(clean_prompt, PT_HISTORY_FILE)
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                pass

        # ── Phase 1: get first line via readline (history, line-edit intact) ──
        first = input(prompt)

        # ── Phase 2: bracketed paste? ─────────────────────────────────────────
        if _PASTE_START in first:
            # Strip leading marker; first line may already contain paste end too
            body = first.replace(_PASTE_START, "")
            if _PASTE_END in body:
                # Single-line paste (no embedded newlines)
                return body.replace(_PASTE_END, "").strip()

            # Multi-line paste: keep reading until end marker arrives
            lines = [body]
            while True:
                ready = _sel.select([sys.stdin], [], [], 2.0)[0]
                if not ready:
                    break  # safety timeout — paste stalled
                raw = sys.stdin.readline()
                if not raw:
                    break
                raw = raw.rstrip("\n")
                if _PASTE_END in raw:
                    tail = raw.replace(_PASTE_END, "")
                    if tail:
                        lines.append(tail)
                    break
                lines.append(raw)

            result = "\n".join(lines).strip()
            # Fold large pastes into a placeholder (kimi-cli style)
            if _paste_ph is not None:
                return _paste_ph.maybe_placeholderize(result)
            n = result.count("\n") + 1
            info(f"  (pasted {n} line{'s' if n > 1 else ''})")
            return result

        # ── Phase 3: timing fallback ─────────────────────────────────────────
        if sys.stdin.isatty():
            lines = [first]
            import time

            if sys.platform == "win32":
                # Windows: use msvcrt.kbhit() to detect buffered paste data
                import msvcrt
                deadline = 0.12   # wider window for Windows paste latency
                chunk_to = 0.03
                t0 = time.monotonic()
                while (time.monotonic() - t0) < deadline:
                    time.sleep(chunk_to)
                    if not msvcrt.kbhit():
                        break
                    raw = sys.stdin.readline()
                    if not raw:
                        break
                    stripped = raw.rstrip("\n").rstrip("\r")
                    lines.append(stripped)
                    t0 = time.monotonic()  # extend while data keeps coming
            else:
                # Unix: use select() for precise timing
                deadline = 0.06
                chunk_to = 0.025
                t0 = time.monotonic()
                while (time.monotonic() - t0) < deadline:
                    ready = _sel.select([sys.stdin], [], [], chunk_to)[0]
                    if not ready:
                        break
                    raw = sys.stdin.readline()
                    if not raw:
                        break
                    stripped = raw.rstrip("\n")
                    if _PASTE_END in stripped:
                        break
                    lines.append(stripped)
                    t0 = time.monotonic()

            if len(lines) > 1:
                result = "\n".join(lines).strip()
                # Fold large pastes into a placeholder (kimi-cli style)
                if _paste_ph is not None:
                    return _paste_ph.maybe_placeholderize(result)
                info(f"  (pasted {len(lines)} lines)")
                return result

        return first

    batch_buffer = []
    in_batch_mode = False
    import uuid

    while True:
        # ── Roundtable proactive: auto-inject "ok ok" to keep table alive ────
        if in_roundtable_active and config.get("_roundtable_proactive_enabled"):
            _rt_interval = config.get("_roundtable_proactive_interval", 180)
            _rt_last = config.get("_roundtable_proactive_last_fire", 0)
            if time.time() - _rt_last >= _rt_interval:
                config["_roundtable_proactive_last_fire"] = time.time()
                print(clr("\n  [roundtable proactive] → ok ok", "dim"), flush=True)
                # Inject as if user typed "ok ok"
                _rt_msg = "ok ok"
                original_model = config.get("model")
                for _rt_model in roundtable_models:
                    print(clr(f"\n  ── TURNO DE: {_rt_model} ──", "yellow", "bold"))
                    config["model"] = _rt_model
                    _last_idx = roundtable_last_seen_idx.get(_rt_model, 0)
                    _missed = roundtable_log[_last_idx:]
                    _ctx = "".join(f"--- {a} dijo:\n{t}\n\n" for a, t in _missed)
                    if _ctx:
                        _p = f"(Mesa Redonda) El moderador dice: 'ok ok'. Continúa la discusión.\n\nÚltimo contexto:\n{_ctx}\nSigue con tu perspectiva."
                    else:
                        _p = "(Mesa Redonda) El moderador dice: 'ok ok'. Continúa la discusión con tu perspectiva."
                    try:
                        run_query(_p)
                        if state.messages and hasattr(state.messages[-1], "get") and state.messages[-1].get("role") == "assistant":
                            ans = state.messages[-1]["content"]
                            if not ans.startswith(f"[Respuesta de {_rt_model}]"):
                                state.messages[-1]["content"] = f"[Respuesta de {_rt_model}]:\n" + ans
                            roundtable_log.append((_rt_model, ans))
                            roundtable_last_seen_idx[_rt_model] = len(roundtable_log)
                    except KeyboardInterrupt:
                        _track_ctrl_c()
                        break
                _save_roundtable_session(roundtable_log, roundtable_save_path)
                config["model"] = original_model

        # Show notifications and inject completions.
        # If any finished job was drained here (before the sentinel thread saw it),
        # fire the run_query callback ourselves so the agent wakes up just like
        # it would on a sentinel-driven [Background Event Triggered].
        _new_bg = _print_background_notifications(state)
        if _new_bg:
            _cb = config.get("_run_query_callback")
            # Cooldown guard: don't fire a background event immediately after
            # the user just finished a turn. If <10s since last activity, the
            # notification was already injected into state.messages above, so
            # the model will see it on the user's next message.
            if _cb and time.time() - config.get("_last_interaction_time", 0) >= 10:
                try:
                    _cb("(System Automated Event): One or more background jobs have finished. "
                        "Please review the results and report back to the user.")
                except Exception:
                    pass

        # ── Wake-word listener lifecycle ──
        global _wake_listener
        
        # [Autostart] If enabled in config but listener not created yet
        if _wake_listener is None and config.get("wake_enabled"):
            try:
                from voice.wake_word import WakeWordListener
                _wake_listener = WakeWordListener(
                    rms_threshold=config.get("wake_threshold", 0.035),
                    device_index=config.get("voice_device_index", config.get("_voice_device_index")),
                    language=_voice_language,
                )
                # Pre-load Whisper in background so detection is fast
                def _preload():
                    try:
                        from voice.stt import _get_faster_whisper_model
                        _get_faster_whisper_model()
                    except Exception:
                        pass
                threading.Thread(target=_preload, daemon=True).start()
            except ImportError:
                pass

        if _wake_listener is not None and not _wake_listener.is_running():
            def _on_wake(phrase: str) -> None:
                import input as _dulus_input
                _dulus_input.set_toolbar_status(clr("Waking up...", "cyan"))
                # NOTE: We intentionally do NOT print the wake detection to the CLI.
                # The audible feedback (beep + TTS) is sufficient. This avoids
                # accumulation of wake notifications in the terminal buffer.
                
                # Immediate audible feedback — universal beep
                try:
                    from voice import beep
                    beep(880, 150)
                except Exception:
                    pass
                # TTS feedback
                # NOTE: say() is blocking, which correctly delays the command recording 
                # in WakeWordListener until after the response is finished.
                try:
                    from voice import say
                    _resp = config.get("wake_response", "¿Dime, papi?")
                    say(_resp, provider=config.get("tts_provider", "auto"))
                except Exception:
                    pass

            def _on_command(text: str) -> None:
                # Filter common Whisper hallucinations on silence/noise
                # NOTE: We allow "gracias" as it's a valid thing a user might say.
                _HALLUC = {
                    "thank you.", "thank you", "thanks for watching.", 
                    "thanks for watching!", "thanks.", ".", "you",
                    "subtitles by the amara.org community",
                }
                _norm = text.strip().lower()
                if not _norm or _norm in _HALLUC:
                    # Ignore hallucinations silently
                    import input as _dulus_input
                    _dulus_input.set_toolbar_status("")
                    return

                # Always put in queue so the main loop can pick it up
                _wake_queue.put(text)
                
                # Signal the active prompt to exit (unblocks dulus_input.read_line_split)
                import input as _dulus_input
                _dulus_input.request_exit()
                
                _dulus_input.set_toolbar_status("") # Clear toolbar on success
                _dulus_input.safe_print_notification(clr(f"\n  🎙️  COMMAND: \"{text}\"", "cyan", "bold"))

            _wake_listener.start(on_wake=_on_wake, on_command=_on_command)

        # ── Check for wake-word command before blocking on keyboard ──
        user_input = ""
        _wake_cmd: str | None = None
        try:
            _wake_cmd = _wake_queue.get_nowait()
        except _queue.Empty:
            _wake_cmd = None

        try:
            cwd_short = Path.cwd().name
            # Live context-usage indicator: "[73%]" — green<60, yellow<85, red otherwise.
            ctx_tag = ""
            try:
                from compaction import estimate_tokens, get_context_limit
                _model = config.get("model", "")
                _used = estimate_tokens(state.messages, _model, config)
                _limit = get_context_limit(_model) or 128000
                _pct_f = (_used * 100 / _limit) if _limit else 0
                # Big-context models (200k+) round to 0% for ages — show one
                # decimal under 1% so the user knows it's actually tracking.
                if _pct_f < 1:
                    _pct_str = f"{_pct_f:.1f}"
                else:
                    _pct_str = str(int(_pct_f))
                _pct = int(_pct_f)
                _ctx_color = "green" if _pct < 60 else ("yellow" if _pct < 85 else "red")
                ctx_tag = clr(f"[{_pct_str}%] ", _ctx_color, "bold")
            except Exception:
                pass
            prompt = _rl_safe(clr(f"\n[{cwd_short}] ", "dim") + ctx_tag + clr("» ", "cyan", "bold"))
            if in_batch_mode:
                prompt = _rl_safe(clr(f"  batch[{len(batch_buffer)}] » ", "yellow", "bold"))

            if _wake_cmd is not None:
                user_input = _wake_cmd
                import input as _dulus_input
                _dulus_input.safe_print_notification(clr(f"\n  🦅 [Wake] » {user_input}\n", "green", "bold"))
            elif config.pop("_auto_voice_next", False) and not in_batch_mode:
                print(clr("  🎙  [auto-voice] Listening… (Ctrl+C to type instead)", "cyan"))
                try:
                    from voice import voice_input as _av_voice_input
                    user_input = _av_voice_input(
                        language=_voice_language,
                        device_index=config.get("voice_device_index", config.get("_voice_device_index")),
                    ) or ""
                    # Filter Whisper hallucinations that fire on silence /
                    # TTS bleed-through. These are well-known false positives.
                    _HALLUC = {
                        "thank you.", "thank you", "thanks for watching.",
                        "thanks for watching!", "thanks.", ".", "you",
                        "subtitles by the amara.org community",
                        "gracias.", "gracias por ver el video.",
                    }
                    _norm = user_input.strip().lower()
                    if _norm and _norm not in _HALLUC:
                        ok(f'  Transcribed: \u201c{user_input}\u201d')
                    else:
                        if _norm:
                            info(f"  (ignored possible hallucination: \u201c{user_input.strip()}\u201d)")
                        else:
                            info("  (nothing transcribed — type your reply)")
                        user_input = _read_input(prompt)
                except KeyboardInterrupt:
                    print()
                    user_input = _read_input(prompt)
                except Exception as _av_err:
                    warn(f"auto-voice failed: {_av_err}")
                    user_input = _read_input(prompt)
            else:
                user_input = _read_input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            # ── Stop wake-word listener on exit ──
            try:
                if _wake_listener is not None:
                    _wake_listener.stop()
                    globals()["_wake_listener"] = None
            except Exception:
                pass
            # ── Sleep Trigger: Ask to consolidate before final exit ─────────
            try:
                # Only ask if there's actually a session worth saving
                if state.messages and state.turn_count > 1:
                    print(clr("\n  [Dulus is still awake] ", "cyan") + clr("Consolidate memories before sleeping? [y/N] ", "white", "bold"), end="", flush=True)
                    choice = _read_input("").strip().lower()
                    if choice == "y":
                        prompt = (
                            "Antes de cerrar la sesión, analiza lo que hemos hablado hoy. Identifica datos clave, "
                            "hitos del proyecto o preferencias que deba guardar. Usa MemorySave para lo más importante. "
                            "CRÍTICO: La memoria 'Soul' es sagrada; NO la sobreescribas ni la ensucies con basura "
                            "de esta sesión. Crea memorias nuevas y específicas para los datos actuales."
                        )
                        run_query(prompt)
            except Exception as e:
                warn(f"Consolidation trigger failed: {e}")

            try:
                save_latest("", state, config)
            except Exception as e:
                warn(f"Auto-save failed on exit: {e}")
            if _bpm_active:
                sys.stdout.write("\x1b[?2004l")  # disable bracketed paste mode
                sys.stdout.flush()
            ok("Goodbye!")
            sys.exit(0)

        if not user_input:
            continue

        # Track recent messages for toolbar sliding window
        try:
            dulus_input.add_recent_msg(user_input)
        except Exception:
            pass

        if in_roundtable_setup and not user_input.startswith("/"):
            if user_input.strip() == '"""':
                if 3 <= len(roundtable_models) <= 5:
                    in_roundtable_setup = False
                    in_roundtable_active = True
                    # Asignar letra A-E a cada miembro automáticamente
                    roundtable_models = [f"{m} {chr(65 + i)}" for i, m in enumerate(roundtable_models)]
                    from datetime import datetime as _dt
                    roundtable_save_path = Path.cwd() / f"round_table_{_dt.now().strftime('%Y%m%d_%H%M%S')}.json"
                    ok(f"Mesa redonda iniciada con {len(roundtable_models)} modelos: {', '.join(roundtable_models)}")
                    info("Escribe un mensaje y cada modelo responderá en orden sin usar tools. Escribe '/roundtable stop' para salir.")
                else:
                    err(f"Error: Requiere de 3 a 5 modelos. Tienes {len(roundtable_models)}. Entrando de nuevo a setup, por favor introduce modelos y termina con \"\"\".")
                continue
            else:
                roundtable_models.append(user_input.strip())
                continue

        if in_roundtable_active and not user_input.startswith("/"):
            user_msg = user_input.strip()
            original_model = config.get("model")
            # Tools are now enabled by default in roundtable mode per user request.
            # To disable them for specific models, use model-specific config if available.
            # original_no_tools = config.get("no_tools", False)
            
            for model_name in roundtable_models:
                print(clr(f"\n  ── TURNO DE: {model_name} ──", "yellow", "bold"))
                config["model"] = model_name
                # config["no_tools"] = True  # Removed: allow tools in roundtable
                
                # Fetch what happened since this model last spoke
                last_idx = roundtable_last_seen_idx.get(model_name, 0)
                missed_turns = roundtable_log[last_idx:]
                
                accumulated_context = ""
                for author, text in missed_turns:
                    accumulated_context += f"--- {author} dijo:\n{text}\n\n"
                
                if not missed_turns:
                    if len(roundtable_log) == 0:
                        prompt_to_send = user_msg
                    else:
                        prompt_to_send = f"(Mesa Redonda) Eres {model_name}. El usuario dijo:\n\"{user_msg}\"\nAporta tu perspectiva al debate."
                else:
                    prompt_to_send = f"(Mesa Redonda) Eres {model_name}. El usuario dijo:\n\"{user_msg}\"\n\nMientras esperabas tu turno, se dijo esto:\n{accumulated_context}\nAgrega tu comentario o debate los puntos."
                
                try:
                    run_query(prompt_to_send)
                    
                    # Auto-save config after each turn for web providers to persist session IDs
                    model_low = config.get("model", "").lower()
                    if any(p in model_low for p in ("gemini-web", "claude-web", "claude-code", "kimi-web")):
                        from config import save_config
                        save_config(config)
                        
                    # Inject model name into the assistant's response so context is clear for the next model
                    if state.messages and hasattr(state.messages[-1], "get") and state.messages[-1].get("role") == "assistant":
                        ans = state.messages[-1]["content"]
                        if not ans.startswith(f"[Respuesta de {model_name}]"):
                            state.messages[-1]["content"] = f"[Respuesta de {model_name}]:\n" + ans
                            
                        # Record response in global log and update cursor
                        roundtable_log.append((model_name, ans))
                        roundtable_last_seen_idx[model_name] = len(roundtable_log)
                            
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                    break
            
            # Auto-save roundtable log after each complete round (overwrites same file)
            _save_roundtable_session(roundtable_log, roundtable_save_path)
            config["model"] = original_model
            # config["no_tools"] = original_no_tools
            continue

        # ── Kimi Batch Mode (triple-quote trigger) ─────────────────────────
        if user_input.strip() == '"""':
            if not in_batch_mode:
                in_batch_mode = True
                ok("Kimi Batch Mode enabled. Enter one prompt per line. End with \"\"\" to submit.")
                continue
            else:
                in_batch_mode = False
                if not batch_buffer:
                    warn("Batch buffer empty. Mode disabled.")
                    continue
                
                # Trigger Kimi Batch
                from batch_api import BatchManager, save_batch_job
                from providers import get_api_key
                
                api_key = get_api_key("kimi", config)
                if not api_key:
                    err("Kimi API key missing. Cannot process batch.")
                    batch_buffer.clear()
                    continue
                    
                mgr = BatchManager(api_key, base_url="https://api.moonshot.ai")
                info(f"Starting Batch task with {len(batch_buffer)} requests...")
                try:
                    # Map each line to a JSONL entry - Force batch-compatible model
                    # Kimi Batch API only supports specific models, not the thinking ones
                    batch_model = "kimi-k2.5"  # Default batch-compatible model
                    info(f"Using model: {batch_model} (batch-compatible)")
                    content = mgr.prepare_jsonl(batch_buffer, model=batch_model)
                    file_id = mgr.upload_file(content)
                    batch_id = mgr.create_batch(file_id)
                    
                    desc = f"Batch with {len(batch_buffer)} prompts (first: {batch_buffer[0][:30]}...)"
                    save_batch_job(batch_id, desc)
                    
                    ok(f"Batch task submitted successfully! ID: {batch_id}")
                    info("Check status later with: /batch status")
                    
                    # Create background job file for automatic notification
                    import uuid
                    from datetime import datetime
                    
                    job_id = str(uuid.uuid4())[:8]
                    # Filtrar config para solo incluir valores JSON-serializables
                    def _is_serializable(v):
                        try:
                            json.dumps(v)
                            return True
                        except (TypeError, ValueError):
                            return False
                    
                    serializable_config = {k: v for k, v in config.items() if _is_serializable(v)}
                    
                    job_data = {
                        "id": job_id,
                        "tool_name": "kimi_batch_poll",
                        "params": {"batch_id": batch_id},
                        "status": "running",
                        "created_at": datetime.now().isoformat(),
                        "config": serializable_config,
                        "batch_job": True
                    }
                    
                    job_path = Path.home() / ".dulus" / "jobs" / f"{job_id}.json"
                    with open(job_path, "w", encoding="utf-8") as f:
                        json.dump(job_data, f, indent=2, ensure_ascii=False)
                    
                    # Batch polling is handled by the central job notifier
                    # (_get_finished_jobs checks batch API status on each tick).
                    # No separate thread needed — same system as TmuxOffload.
                    info("Background polling active (central job notifier)")
                except Exception as e:
                    err(f"Kimi Batch API error: {e}")
                
                batch_buffer.clear()
                continue
        
        if in_batch_mode:
            batch_buffer.append(user_input)
            continue

        # ── Shell escape: !<anything> runs the WHOLE line in the system shell ──
        # If the first char is '!', everything after it is the command.
        # Use '!!' at the start to escape and send literal '!...' as a message.
        if user_input.startswith("!!"):
            user_input = user_input[1:]  # drop one '!', fall through as normal input
        elif user_input.startswith("!"):
            shell_cmd = user_input[1:].strip()
            # Special case: `!clear` / `!cls` — nuke the split layout buffer
            # too, otherwise ghost lines reappear on the next redraw.
            if shell_cmd.lower() in ("clear", "cls"):
                try:
                    import input as _dulus_input
                    if hasattr(_dulus_input, "clear_split_output"):
                        _dulus_input.clear_split_output()
                except Exception:
                    pass
                # Write ANSI clear directly to the REAL terminal, bypassing
                # _OutputRedirector so it actually clears the screen.
                try:
                    real_out = getattr(sys, "__stdout__", None)
                    if real_out:
                        real_out.write("\033[2J\033[H")
                        real_out.flush()
                except Exception:
                    pass
                # Fallback: Windows cls / Unix clear via os.system
                try:
                    os.system("cls" if os.name == "nt" else "clear")
                except Exception:
                    pass
                continue
            if shell_cmd:
                print(clr(f"  $ {shell_cmd}", "dim"))
                try:
                    import subprocess as _sp
                    _sp.run(shell_cmd, shell=True)
                except Exception as e:
                    warn(f"Shell error: {e}")
            continue

        result = handle_slash(user_input, state, config)
        # ── Sentinel processing loop ──
        # Processes sentinel tuples returned by commands. SSJ-originated
        # sentinels loop back to the SSJ menu after completion.
        while isinstance(result, tuple):
            if result[0] == "__roundtable__":
                in_roundtable_setup = True
                in_roundtable_active = False
                roundtable_models = []
                in_batch_mode = False
                ok("\nMesa Redonda Setup. Introduzca de 3 a 5 modelos (uno por linea). Termine con \"\"\" para empezar.")
                break
            if result[0] == "__roundtable_stop__":
                in_roundtable_setup = False
                in_roundtable_active = False
                roundtable_models = []
                _save_roundtable_session(roundtable_log, roundtable_save_path)
                roundtable_log.clear()
                roundtable_last_seen_idx.clear()
                roundtable_save_path = None
                ok("\nMesa redonda finalizada.")
                break
                
            # Voice sentinel: ("__voice__", transcribed_text)
            if result[0] == "__voice__":
                _, voice_text = result
                try:
                    run_query(voice_text)
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                break
            # Image sentinel: ("__image__", prompt_text)
            if result[0] == "__image__":
                _, image_prompt = result
                try:
                    run_query(image_prompt)
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                break


            # Plan sentinel: ("__plan__", description)
            if result[0] == "__plan__":
                _, plan_desc = result
                try:
                    run_query(f"Please analyze the codebase and create a detailed implementation plan for: {plan_desc}")
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                break

            # Plugin main-agent handoff sentinel:
            # ("__plugin_main_agent__", plugin_name, plugin_source)
            # Triggered by `/plugin install name@url --main-agent` — the main agent
            # is asked to take over and adapt/integrate the freshly installed plugin.
            if result[0] == "__plugin_main_agent__":
                _, plugin_name, plugin_source = result
                source_hint = f" (source: {plugin_source})" if plugin_source else ""
                print(clr(f"\n  ── Handing off plugin '{plugin_name}' to main agent ──", "dim"))
                try:
                    run_query(
                        f"(System Event): The plugin '{plugin_name}'{source_hint} has just been installed via "
                        f"`/plugin install ... --main-agent`. The user wants you — the main agent — to take over "
                        f"from here. Review the plugin, verify/adapt its manifest if needed (you may use the "
                        f"autoadapter or do it manually), and integrate it so it's ready to use. Report back "
                        f"concisely once it's wired up."
                    )
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                break

            # SSJ passthrough: user typed a /command inside SSJ menu
            if result[0] == "__ssj_passthrough__":
                _, slash_line = result
                # Guard against /ssj re-entering itself infinitely
                if slash_line.strip().lower() == "/ssj":
                    result = handle_slash("/ssj", state, config)
                    continue
                inner = handle_slash(slash_line, state, config)
                if isinstance(inner, tuple):
                    result = inner
                    continue
                break

            # SSJ command sentinel: ("__ssj_cmd__", cmd_name, args)
            # Delegate to the real command and re-process its returned sentinel
            if result[0] == "__ssj_cmd__":
                _, cmd_name, cmd_args = result
                inner = handle_slash(f"/{cmd_name} {cmd_args}".strip(), state, config)
                if isinstance(inner, tuple):
                    # Tag so we know to loop back to SSJ after processing
                    result = ("__ssj_wrap__", inner)
                    continue
                # Command handled directly, loop back to SSJ
                result = handle_slash("/ssj", state, config)
                continue

            # Unwrap SSJ-wrapped sentinel and process the inner sentinel
            if result[0] == "__ssj_wrap__":
                result = result[1]
                _from_ssj_flag = True
            else:
                _from_ssj_flag = result[0] == "__ssj_query__"

            # Brainstorm sentinel: ("__brainstorm__", synthesis_prompt, out_file)
            if result[0] == "__brainstorm__":
                _, brain_prompt, brain_out_file = result
                print(clr("\n  ── Analysis from Main Agent ──", "dim"))
                try:
                    run_query(brain_prompt)
                    _save_synthesis(state, brain_out_file)
                    _todo_path = str(Path(brain_out_file).parent / "todo_list.txt")
                    print(clr("\n  ── Generating TODO List from Master Plan ──", "dim"))
                    run_query(
                        f"Based on the Master Plan you just synthesized, generate a todo list file at {_todo_path}. "
                        "Format: one task per line, each starting with '- [ ] '. "
                        "Order by priority. Include ALL actionable items from the plan. "
                        "Use the Write tool to create the file. Do NOT explain, just write the file now."
                    )
                    info(f"TODO list saved to {_todo_path}. Edit it freely, then use /worker to start implementing.")
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                if _from_ssj_flag:
                    result = handle_slash("/ssj", state, config)
                    continue
                break
            # Promote-then-Worker: generate todo_list.txt from brainstorm .md, then run worker
            if result[0] == "__ssj_promote_worker__":
                _, md_path, todo_path_str, task_nums_str, max_workers_str = result
                promote_prompt = (
                    f"Read the brainstorm file {md_path} and extract all actionable ideas. "
                    f"Convert each idea into a task with checkbox format (- [ ] task description). "
                    f"Write them to {todo_path_str} using the Write tool. Prioritize by impact. "
                    f"Do NOT explain, just write the file now."
                )
                print(clr(f"\n  ── Generating TODO list from {Path(md_path).name} ──", "dim"))
                try:
                    run_query(promote_prompt)
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                    result = handle_slash("/ssj", state, config)
                    continue
                # Now run worker on the newly created file
                worker_args = f"--path {todo_path_str}"
                if task_nums_str:
                    worker_args += f" --tasks {task_nums_str}"
                if max_workers_str and max_workers_str.isdigit():
                    worker_args += f" --workers {max_workers_str}"
                inner = handle_slash(f"/worker {worker_args}".strip(), state, config)
                if isinstance(inner, tuple):
                    result = ("__ssj_wrap__", inner)
                    continue
                result = handle_slash("/ssj", state, config)
                continue

            # Worker sentinel: ("__worker__", [(line_idx, task_text, prompt), ...])
            if result[0] == "__worker__":
                _, worker_tasks = result
                for i, (line_idx, task_text, prompt) in enumerate(worker_tasks):
                    print(clr(f"\n  ── Worker ({i+1}/{len(worker_tasks)}): {task_text} ──", "yellow"))
                    try:
                        run_query(prompt)
                    except KeyboardInterrupt:
                        _track_ctrl_c()
                        print(clr("\n  (worker interrupted — remaining tasks skipped)", "yellow"))
                        break
                ok("Worker finished. Run /worker to check remaining tasks.")
                if _from_ssj_flag:
                    result = handle_slash("/ssj", state, config)
                    continue
                break
            # Debate sentinel: ("__ssj_debate__", filepath, nagents, rounds, out_file)
            # Drives the debate round-by-round, showing a spinner before each expert's turn.
            if result[0] == "__ssj_debate__":
                _, _dfile, _nagents, _rounds, _debate_out = result
                import random as _random

                # ── Stdout wrapper: stops spinner on first real (non-\r) output ──
                class _DebateSpinnerWrapper:
                    def __init__(self, real_out):
                        self._real = real_out
                        self._stopped = False
                    def write(self, s):
                        if not self._stopped and s and not s.startswith('\r'):
                            self._stopped = True
                            _stop_tool_spinner()
                            self._real.write('\n')
                        return self._real.write(s)
                    def flush(self):   return self._real.flush()
                    def __getattr__(self, name): return getattr(self._real, name)

                def _spin_and_query(phrase, prompt):
                    """Show spinner with phrase, stop it on first model output, run query."""
                    with _spinner_lock:
                        global _spinner_phrase
                        _spinner_phrase = phrase
                    _start_tool_spinner()
                    _orig = sys.stdout
                    sys.stdout = _DebateSpinnerWrapper(sys.stdout)
                    try:
                        run_query(prompt)
                    finally:
                        _stop_tool_spinner()
                        sys.stdout = _orig

                try:
                    # ── Step 1: Read file and assign expert personas ──────────
                    _spin_and_query(
                        "⚔️  Assembling expert panel...",
                        f"Read the file {_dfile}. Then introduce the {_nagents} expert debaters you will "
                        f"role-play, each with a distinct focus area chosen to best challenge each other "
                        f"(e.g. architecture, performance, security, UX, testing, maintainability). "
                        f"List their names and focus areas. Do NOT debate yet."
                    )

                    # ── Step 2: Each round, each expert takes a turn ──────────
                    for _r in range(1, _rounds + 1):
                        for _e in range(1, _nagents + 1):
                            _phase = "opening argument" if _r == 1 else f"round {_r} response"
                            _spin_and_query(
                                _random.choice([
                                    f"⚔️  Round {_r}/{_rounds} — Expert {_e} thinking...",
                                    f"💬  Round {_r}/{_rounds} — Expert {_e} formulating...",
                                    f"🧠  Round {_r}/{_rounds} — Expert {_e} responding...",
                                ]),
                                f"Now speak as Expert {_e}. Give your {_phase}. "
                                f"Be specific, reference the file content, and directly address "
                                f"the previous arguments. Be concise (3-5 key points)."
                            )

                    # ── Step 3: Consensus + save ──────────────────────────────
                    _spin_and_query(
                        "📜  Drafting final consensus...",
                        f"Based on this entire debate, write a final consensus that all experts agree on. "
                        f"List the top actionable changes ranked by impact. "
                        f"Then use the Write tool to save the complete debate transcript and this consensus "
                        f"to: {_debate_out}"
                    )
                    ok(f"Debate complete. Saved to {_debate_out}")

                except KeyboardInterrupt:
                    _track_ctrl_c()
                    _stop_tool_spinner()
                    sys.stdout = sys.__stdout__
                    print(clr("\n  (debate interrupted)", "yellow"))

                result = handle_slash("/ssj", state, config)
                continue

            # SSJ query sentinel: ("__ssj_query__", prompt)
            if result[0] == "__ssj_query__":
                _, ssj_prompt = result
                try:
                    run_query(ssj_prompt)
                except KeyboardInterrupt:
                    _track_ctrl_c()
                    print(clr("\n  (interrupted)", "yellow"))
                # Loop back to SSJ menu
                result = handle_slash("/ssj", state, config)
                continue
            # Skill match (fallback): (SkillDef, args_str)
            skill, skill_args = result
            info(f"Running skill: {skill.name}" + (f" [{skill.context}]" if skill.context == "fork" else ""))
            try:
                from skill import substitute_arguments
                rendered = substitute_arguments(skill.prompt, skill_args, skill.arguments)
                run_query(f"[Skill: {skill.name}]\n\n{rendered}")
            except KeyboardInterrupt:
                _track_ctrl_c()
                print(clr("\n  (interrupted)", "yellow"))
            break
        # Sentinel or command was handled — don't fall through to run_query
        if result:
            continue

        try:
            run_query(user_input)
            
            # Auto-save config after each turn for web providers to persist session IDs
            model_low = config.get("model", "").lower()
            if any(p in model_low for p in ("gemini-web", "claude-web", "claude-code", "kimi-web")):
                from config import save_config
                save_config(config)
        except KeyboardInterrupt:
            _track_ctrl_c()
            print(clr("\n  (interrupted)", "yellow"))
            # Keep conversation history up to the interruption


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="dulus",
        description="Dulus - Next-gen Python Autonomous Agent",
        add_help=False,
    )
    parser.add_argument("prompt", nargs="*", help="Initial prompt (non-interactive)")
    parser.add_argument("-p", "--print", "--print-output",
                        dest="print_mode", action="store_true",
                        help="Non-interactive mode: run prompt and exit")
    parser.add_argument("-m", "--model", help="Override model")
    parser.add_argument("--accept-all", action="store_true",
                        help="Never ask permission (accept all operations)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show thinking + token counts")
    parser.add_argument("--thinking", action="store_true",
                        help="Enable extended thinking")
    parser.add_argument("--soul", default="",
                        help="Skip the soul picker and load a specific soul (e.g. 'chill', 'forensic')")
    parser.add_argument("--version", action="store_true", help="Print version")
    parser.add_argument("-h", "--help", action="store_true", help="Show help")
    
    # Tool offloading / Background job runner mode
    parser.add_argument("--run-tool", help="Execute a specific tool and exit")
    parser.add_argument("--job-id", help="Background job ID")
    parser.add_argument("--job-path", help="Path to background job JSON file")
    
    # Direct command execution mode (e.g., --cmd "plugin reload", --cmd "checkpoint clear")
    parser.add_argument("-c", "--cmd", dest="exec_cmd", nargs='+',
                        help="Execute a Dulus command and exit (e.g., --cmd \"plugin reload\")")
    parser.add_argument("--gui", action="store_true",
                        help="Launch the desktop GUI instead of the terminal REPL")
    parser.add_argument("--daemon", action="store_true",
                        help="Daemon mode — keep Dulus alive in the background for Telegram/webhook bridges")

    args = parser.parse_args()

    if args.version:
        print(f"dulus v{VERSION}")
        sys.exit(0)

    if args.help:
        print(__doc__)
        sys.exit(0)

    from config import load_config, save_config, has_api_key
    from providers import detect_provider, PROVIDERS

    # ── First-run welcome wizard ──────────────────────────────────────────
    # Runs BEFORE load_config() so we detect the absence of config.json.
    # The wizard mutates config in-place and persists it; subsequent
    # load_config() picks up the freshly-written values.
    try:
        from welcome import is_first_run, run_welcome_wizard
        if is_first_run() and not args.print_mode and not args.exec_cmd and not args.run_tool:
            _bootstrap_cfg = load_config()
            _bootstrap_cfg = run_welcome_wizard(_bootstrap_cfg)
            save_config(_bootstrap_cfg)
    except Exception as _e:
        print(f"(welcome wizard skipped: {_e})")

    config = load_config()

    # ── License Gate ─────────────────────────────────────────────────────────
    from license_manager import LicenseManager, LicenseTier
    _lic = LicenseManager(config.get("license_key", ""))
    if not _lic.valid and config.get("license_key"):
        print(f"\n⚠️  {_lic.status_banner()}")
    elif _lic.tier != LicenseTier.FREE:
        print(f"\n✅ {_lic.status_banner()}")
    else:
        print(f"\n🦅 Dulus — {_lic.status_banner()}")
    # Inject license limits into config for downstream modules
    config["_license_tier"] = _lic.tier
    config["_license_valid"] = _lic.valid
    config["_max_tool_calls"] = _lic.max_tool_calls()
    config["_max_providers"] = _lic.max_providers()
    config["_max_subagents"] = _lic.max_subagents()
    config["_max_plugins"] = _lic.max_plugins()
    config["_allow_voice"] = _lic.allow_voice()
    config["_allow_telegram"] = _lic.allow_telegram()
    config["_allow_cloudsave"] = _lic.allow_cloudsave()
    config["_allow_mcp"] = _lic.allow_mcp()

    if sys.platform == "win32":
        # Ensure stdout/stderr are UTF-8 in Windows console to prevent crashes on emojis
        import io
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')



    # Apply theme immediately so all colored output respects user preference
    try:
        import common as _cm
        _cm.apply_theme(config.get("theme", "dulus"))
    except Exception:
        pass

    # ── Execute command directly (e.g., --cmd "plugin reload") ────────────
    if args.exec_cmd:
        from agent import AgentState
        from checkpoint import set_session
        
        # Join list of arguments (handles Windows CMD quote issues)
        cmd_str = " ".join(args.exec_cmd).strip().strip('"\'')
        if not cmd_str.startswith("/"):
            cmd_str = "/" + cmd_str
        
        # Initialize minimal state
        state = AgentState()
        session_id = uuid.uuid4().hex[:8]
        set_session(session_id)
        
        print(clr(f"\n  [Dulus Command] Executing: {cmd_str}", "cyan", "bold"))
        
        # Execute the command
        result = handle_slash(cmd_str, state, config)
        
        # Check if command returned a tuple (skill execution request)
        if isinstance(result, tuple):
            skill, skill_args = result
            from skill import execute_skill
            skill_result = execute_skill(skill, skill_args, config)
            if skill_result:
                print(clr(f"  Result: {skill_result}", "green"))
        
        print()
        sys.exit(0)
    
    if args.run_tool:
        # Lightweight tool execution mode (no REPL, no full memory load)
        from tool_registry import execute_tool
        import tools as _tools_init # Ensure registration
        from datetime import datetime
        import json
        from pathlib import Path

        job_id = args.job_id or "unknown"
        job_path = Path(args.job_path) if args.job_path else None
        
        job_data = {}
        if job_path and job_path.exists():
            try:
                with open(job_path, "r", encoding="utf-8") as f:
                    job_data = json.load(f)
            except Exception:
                pass

        print(clr(f"\n  🚀 [Dulus Tool Runner] Executing: {args.run_tool} (Job: {job_id})", "cyan", "bold"))
        print(clr("  " + "─" * 60, "dim"))
        
        try:
            # Execute the tool
            res = execute_tool(args.run_tool, job_data.get("params", {}), config)
            job_data["status"] = "completed"
            job_data["result"] = res
            print(clr("\n  " + "─" * 60, "dim"))
            print(clr(f"  ✅ Completed: {args.run_tool}", "green", "bold"))
            # Print a snippet of the result
            if res:
                preview = res[:500] + ("..." if len(res) > 500 else "")
                print(clr(f"  Result preview:\n\n{preview}", "dim"))
        except Exception as e:
            job_data["status"] = "failed"
            job_data["error"] = str(e)
            print(clr(f"\n  ❌ Failed: {e}", "red", "bold"))
        
        job_data["finished_at"] = datetime.now().isoformat()
        
        if job_path:
            try:
                with open(job_path, "w", encoding="utf-8") as f:
                    json.dump(job_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        sys.exit(0)

    # Apply CLI overrides first (so key check uses the right provider)
    if args.model:
        m = args.model
        # Convert "provider:model" → "provider/model" only when left side is a known provider
        # (e.g. "ollama:llama3.3" → "ollama/llama3.3"), but leave version tags intact
        # (e.g. "ollama/qwen3.5:35b" must NOT become "ollama/qwen3.5/35b")
        if "/" not in m and ":" in m:
            from providers import PROVIDERS
            left, _ = m.split(":", 1)
            if left in PROVIDERS:
                m = m.replace(":", "/", 1)
        config["model"] = m
    if args.accept_all:
        config["permission_mode"] = "accept-all"
    if args.verbose:
        config["verbose"] = True
    if args.thinking:
        config["thinking"] = 3  # --thinking CLI flag = max level
    if args.soul:
        config["_cli_soul"] = args.soul

    # Check API key for active provider (warn only, don't block local providers)
    if not has_api_key(config):
        pname = detect_provider(config["model"])
        prov  = PROVIDERS.get(pname, {})
        env   = prov.get("api_key_env", "")
        if env:   # local providers like ollama have no env key requirement
            warn(f"No API key found for provider '{pname}'. "
                 f"Set {env} or run: /config {pname}_api_key=YOUR_KEY")

    initial = " ".join(args.prompt) if args.prompt else None

    # ── IPC dispatch: if a Dulus REPL/daemon is already running on
    # 127.0.0.1:5151, forward this prompt to it (shared session) and exit.
    # Falls through silently when no listener is up.
    # Only kicks in for plain `dulus "..."` and `dulus -p "..."` — not for
    # daemon/gui/cmd/run-tool/job invocations, which need their own process.
    if (initial
        and not args.daemon
        and not args.gui
        and not args.exec_cmd
        and not args.run_tool
        and not args.job_id
        and not args.job_path
    ):
        try:
            if _try_ipc_dispatch(initial):
                sys.exit(0)
        except Exception:
            pass  # any IPC error → fall through to in-process path

    # ── Daemon mode ──
    if args.daemon:
        _run_daemon(config)
        return

    # ── Launch desktop GUI ──
    if args.gui:
        try:
            from dulus_gui import launch_gui
            launch_gui(config=config, initial_prompt=initial)
        except ImportError as exc:
            err(f"GUI dependencies missing: {exc}. Run: pip install customtkinter")
        return
    if args.print_mode and not initial:
        err("--print requires a prompt argument")
        sys.exit(1)

    repl(config, initial_prompt=initial)


if __name__ == "__main__":
    main()
