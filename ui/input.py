"""prompt_toolkit-based REPL input with typing-time slash-command autosuggest.

Optional dependency: when prompt_toolkit is not installed, HAS_PROMPT_TOOLKIT
is False and callers should fall through to readline-based input.

Dependency-injected: callers register command/meta providers via setup()
before calling read_line(). This module never imports Falcon core — keeping
the dependency one-way and eliminating any circular-import risk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.styles import Style
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


# ── Injected providers ───────────────────────────────────────────────────────
# Callers (Falcon REPL) must call setup() before read_line().
_commands_provider: Optional[Callable[[], dict]] = None
_meta_provider: Optional[Callable[[], dict]] = None


def setup(
    commands_provider: Callable[[], dict],
    meta_provider: Callable[[], dict],
) -> None:
    """Register providers for the live command registry and metadata.

    `commands_provider` returns the dispatcher's COMMANDS dict.
    `meta_provider` returns the _CMD_META dict (descriptions + subcommands).
    """
    global _commands_provider, _meta_provider
    _commands_provider = commands_provider
    _meta_provider = meta_provider


# ── Completer ────────────────────────────────────────────────────────────────
if HAS_PROMPT_TOOLKIT:

    class SlashCompleter(Completer):
        """Two-level completer for slash commands.

        Level 1: /partial  (no space)  → command names.
        Level 2: /cmd partial           → subcommands listed in the meta dict.

        Providers default to the module-level ones registered via setup(),
        but can be injected via the constructor for testing.
        """

        def __init__(
            self,
            commands_provider: Optional[Callable[[], dict]] = None,
            meta_provider: Optional[Callable[[], dict]] = None,
        ):
            self._commands_override = commands_provider
            self._meta_override = meta_provider
            self._cache_key: Optional[tuple] = None
            self._cache_names: list[str] = []

        def _get_commands(self) -> dict:
            provider = self._commands_override or _commands_provider
            return (provider() if provider else {}) or {}

        def _get_meta(self) -> dict:
            provider = self._meta_override or _meta_provider
            return (provider() if provider else {}) or {}

        def _live_command_names(self) -> list[str]:
            keys = sorted(set(self._get_commands().keys()) | set(self._get_meta().keys()))
            sig = tuple(keys)
            if self._cache_key == sig:
                return self._cache_names
            self._cache_key = sig
            self._cache_names = keys
            return keys

        def get_completions(self, document, complete_event):  # type: ignore[override]
            text = document.text_before_cursor
            if not text.startswith("/"):
                return

            meta = self._get_meta()

            if " " not in text:
                word = text[1:]
                for name in self._live_command_names():
                    if not name.startswith(word):
                        continue
                    desc, subs = meta.get(name, ("", []))
                    hint = ""
                    if subs:
                        head = ", ".join(subs[:3])
                        more = "…" if len(subs) > 3 else ""
                        hint = f"  [{head}{more}]"
                    yield Completion(
                        "/" + name,
                        start_position=-len(text),
                        display=ANSI(f"\x1b[36m/{name}\x1b[0m"),
                        display_meta=(desc + hint) if desc else hint.strip(),
                    )
                return

            head, _, tail = text.partition(" ")
            cmd = head[1:]
            meta_entry = meta.get(cmd)
            if not meta_entry:
                return
            subs = meta_entry[1]
            if not subs:
                return
            partial = tail.rsplit(" ", 1)[-1]
            for sub in subs:
                if sub.startswith(partial):
                    yield Completion(
                        sub,
                        start_position=-len(partial),
                        display_meta=f"{cmd} subcommand",
                    )

else:  # pragma: no cover — unreachable when prompt_toolkit is installed
    class SlashCompleter:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("prompt_toolkit is not installed")


# ── Session cache ────────────────────────────────────────────────────────────
_SESSION = None
_SESSION_HISTORY_PATH: Optional[Path] = None


def reset_session() -> None:
    """Drop the cached session so the next read_line() rebuilds from scratch."""
    global _SESSION, _SESSION_HISTORY_PATH
    _SESSION = None
    _SESSION_HISTORY_PATH = None


def _build_session(history_path: Optional[Path]):
    if not HAS_PROMPT_TOOLKIT:
        raise RuntimeError("prompt_toolkit is not installed")
    completer = SlashCompleter()
    history = FileHistory(str(history_path)) if history_path else InMemoryHistory()
    style = Style.from_dict({
        "completion-menu.completion":              "bg:#222222 #cccccc",
        "completion-menu.completion.current":      "bg:#005f87 #ffffff bold",
        "completion-menu.meta.completion":         "bg:#222222 #808080",
        "completion-menu.meta.completion.current": "bg:#005f87 #eeeeee",
        "auto-suggestion":                         "#606060 italic",
    })
    return PromptSession(
        history=history,
        completer=completer,
        auto_suggest=AutoSuggestFromHistory(),
        complete_while_typing=True,
        enable_history_search=False,
        mouse_support=False,
        style=style,
    )


def read_line(prompt_ansi: str, history_path: Optional[Path] = None) -> str:
    """Read one line of input via prompt_toolkit; caches the session across calls.

    The history file passed here MUST NOT be the readline history file — the
    two line-editors use incompatible formats. See Falcon REPL for the
    dedicated PT_HISTORY_FILE.
    """
    global _SESSION, _SESSION_HISTORY_PATH, _notification_callback
    
    # Drain any pending background notifications before showing prompt
    notifications = drain_notifications()
    for note in notifications:
        if _notification_callback:
            _notification_callback(note)
        else:
            safe_print_notification(note)
    
    if _SESSION is not None and _SESSION_HISTORY_PATH != history_path:
        _SESSION = None
    if _SESSION is None:
        _SESSION = _build_session(history_path)
        _SESSION_HISTORY_PATH = history_path
    with patch_stdout(raw=True):
        return _SESSION.prompt(ANSI(prompt_ansi))


# ── Split Layout Mode (Kimi/Claude style) ────────────────────────────────────
# Fixed bottom input bar with scrollable output area above

_split_app: Optional[Any] = None
_split_buffer: Optional[Any] = None
_output_buffer: list[str] = []
_original_stdout = None


class _OutputRedirector:
    """Redirects stdout to the split layout output buffer."""
    def __init__(self, original):
        self._original = original
        self._buffer = ""
    
    def write(self, text: str) -> None:
        if not text:
            return
        self._buffer += text
        if "\n" in text:
            lines = self._buffer.split("\n")
            for line in lines[:-1]:
                if line.strip():
                    append_output(line)
            self._buffer = lines[-1]
        # Also write to original for compatibility
        self._original.write(text)
    
    def flush(self) -> None:
        if self._buffer:
            if self._buffer.strip():
                append_output(self._buffer)
            self._buffer = ""
        self._original.flush()
    
    def isatty(self) -> bool:
        return self._original.isatty()


def read_line_split(prompt: str = "> ", history_path: Optional[Path] = None) -> str:
    """Read input with split layout - fixed bottom bar, scrollable output above.
    
    Similar to Kimi Code and Claude Code interfaces.
    """
    global _split_app, _split_buffer, _output_buffer, _original_stdout, _notification_callback
    
    # Drain any pending background notifications before showing prompt
    notifications = drain_notifications()
    for note in notifications:
        if _notification_callback:
            _notification_callback(note)
        else:
            safe_print_notification(note)
    
    if not HAS_PROMPT_TOOLKIT:
        raise RuntimeError("prompt_toolkit is not installed")
    
    import sys
    # Save and redirect stdout
    _original_stdout = sys.stdout
    sys.stdout = _OutputRedirector(_original_stdout)
    
    from prompt_toolkit import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout import HSplit, Layout, Window, ConditionalContainer
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.layout.processors import BeforeInput
    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.filters import has_completions
    
    # Output area (upper pane) - shows accumulated output with ANSI support
    def get_output_text():
        """Get formatted output text with ANSI codes parsed."""
        text = "\n".join(_output_buffer[-1000:])
        return ANSI(text) if text else ""
    
    output_control = FormattedTextControl(
        text=get_output_text,
        focusable=False,
        show_cursor=False,
    )
    output_window = Window(
        content=output_control,
        wrap_lines=True,
        allow_scroll_beyond_bottom=True,
    )
    
    # Input buffer with completer
    history = FileHistory(str(history_path)) if history_path else InMemoryHistory()
    completer = SlashCompleter()
    
    _split_buffer = Buffer(
        history=history,
        completer=completer,
        auto_suggest=AutoSuggestFromHistory(),
        complete_while_typing=True,
        enable_history_search=False,
        multiline=False,
    )
    
    # Input control with prompt
    input_control = BufferControl(
        buffer=_split_buffer,
        input_processors=[BeforeInput(prompt, style="class:prompt")],
    )
    input_window = Window(
        content=input_control,
        height=1,
        wrap_lines=False,
        always_hide_cursor=False,
    )
    
    # Completions menu (floating)
    completions_menu = ConditionalContainer(
        content=CompletionsMenu(
            max_height=8,
            scroll_offset=1,
            extra_filter=has_completions,
        ),
        filter=has_completions,
    )
    
    # Key bindings
    kb = KeyBindings()
    
    @kb.add("enter")
    def submit(event):
        """Submit input."""
        event.app.exit(result=_split_buffer.text)
    
    @kb.add("c-c")
    @kb.add("c-d")
    def cancel(event):
        """Cancel/exit."""
        event.app.exit(result=None)
    
    @kb.add("c-l")
    def clear(event):
        """Clear output buffer."""
        _output_buffer.clear()
        output_control.text = ""
    
    # Build layout: output on top, separator, input at bottom
    root_container = HSplit([
        output_window,  # Flexible height for output
        Window(height=1, char="─", style="class:separator"),
        input_window,   # Fixed height for input
        completions_menu,  # Floating completions
    ])
    
    style = Style.from_dict({
        "completion-menu.completion":              "bg:#222222 #cccccc",
        "completion-menu.completion.current":      "bg:#005f87 #ffffff bold",
        "completion-menu.meta.completion":         "bg:#222222 #808080",
        "completion-menu.meta.completion.current": "bg:#005f87 #eeeeee",
        "auto-suggestion":                         "#606060 italic",
        "prompt":                                  "#00aa00 bold",
        "separator":                               "#444444",
    })
    
    layout = Layout(root_container, focused_element=input_window)
    
    _split_app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        mouse_support=False,
        full_screen=False,
    )
    
    result = _split_app.run()
    
    # Restore stdout
    sys.stdout = _original_stdout
    _original_stdout = None
    
    # Reset buffer for next use
    if _split_buffer:
        _split_buffer.reset()
    
    return result if result else ""


def append_output(text: str) -> None:
    """Append text to the output buffer (for split layout mode).
    
    Use this to display messages without interrupting the input bar.
    """
    global _output_buffer, _split_app
    _output_buffer.append(text)
    # Keep last 1000 lines
    if len(_output_buffer) > 1000:
        _output_buffer = _output_buffer[-1000:]
    # Refresh display if app is running
    if _split_app:
        _split_app.invalidate()


def clear_split_output() -> None:
    """Clear the split layout output buffer."""
    global _output_buffer
    _output_buffer.clear()


# ── Background Notification Queue ────────────────────────────────────────────
# Thread-safe queue for notifications that need to be displayed without
# corrupting the prompt_toolkit input rendering.

import queue
_notification_queue: queue.Queue = queue.Queue()
_notification_callback: Optional[Callable[[str], None]] = None


def set_notification_callback(callback: Callable[[str], None]) -> None:
    """Register a callback to handle background notifications.
    
    The callback will be called with the notification text when it's safe
    to display (during the next input cycle or when input is not active).
    """
    global _notification_callback
    _notification_callback = callback


def queue_notification(text: str) -> None:
    """Queue a notification to be displayed safely.
    
    This should be used by background threads (timers, jobs, etc.) to
    display messages without corrupting the prompt_toolkit input bar.
    """
    _notification_queue.put(text)


def drain_notifications() -> list[str]:
    """Drain all pending notifications from the queue.
    
    Returns a list of notification texts. Should be called when it's
    safe to display output (e.g., before showing a new prompt).
    """
    notifications = []
    while not _notification_queue.empty():
        try:
            notifications.append(_notification_queue.get_nowait())
        except queue.Empty:
            break
    return notifications


def safe_print_notification(text: str) -> None:
    """Print a notification in a prompt_toolkit-safe way.
    
    If split layout is active, uses append_output.
    Otherwise prints directly (which may cause display issues in sticky mode).
    """
    global _split_app, _original_stdout
    
    if _split_app:
        # Split layout mode - use the safe append_output
        append_output(text)
    elif _original_stdout:
        # We're in some form of redirected stdout
        _original_stdout.write(text + "\n")
        _original_stdout.flush()
    else:
        # Fallback to regular print (may have issues with sticky input)
        print(text)
