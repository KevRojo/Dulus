"""prompt_toolkit-based REPL input with typing-time slash-command autosuggest.

Optional dependency: when prompt_toolkit is not installed, HAS_PROMPT_TOOLKIT
is False and callers should fall through to readline-based input.

Dependency-injected: callers register command/meta providers via setup()
before calling read_line(). This module never imports Dulus core — keeping
the dependency one-way and eliminating any circular-import risk.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from prompt_toolkit import PromptSession, Application
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import (
        Completer, Completion, FuzzyCompleter, WordCompleter, merge_completers,
    )
    from prompt_toolkit.document import Document
    from prompt_toolkit.completion.base import CompleteEvent
    from prompt_toolkit.formatted_text import ANSI, is_formatted_text
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.styles import Style
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

try:
    import paste_placeholders as _paste_ph
except ImportError:
    _paste_ph = None  # type: ignore[assignment]

try:
    from common import C
except ImportError:
    C = {"cyan": "\x1b[36m", "bold": "\x1b[1m", "reset": "\x1b[0m", "gray": "\x1b[90m", "dim": "\x1b[2m"}


# ── Injected providers ───────────────────────────────────────────────────────
# Callers (Dulus REPL) must call setup() before read_line().
_commands_provider: Optional[Callable[[], dict]] = None
_meta_provider: Optional[Callable[[], dict]] = None
_toolbar_provider: Optional[Callable[[], str]] = None
_toolbar_status: str = ""  # Background status (e.g. wake energy bar)
_active_app: Optional["Application"] = None  # Track currently running prompt-toolkit app


_TOOLBAR_SENTINEL = object()

def setup(
    commands_provider: Callable[[], dict],
    meta_provider: Callable[[], dict],
    toolbar_provider: Optional[Callable[[], str]] = _TOOLBAR_SENTINEL,  # type: ignore[assignment]
) -> None:
    """Register providers for the live command registry and metadata.

    `commands_provider` returns the dispatcher's COMMANDS dict.
    `meta_provider` returns the _CMD_META dict (descriptions + subcommands).
    `toolbar_provider` returns an ANSI toolbar string (or "" to hide).
    Pass None explicitly to clear a previously-registered toolbar.
    """
    global _commands_provider, _meta_provider, _toolbar_provider
    _commands_provider = commands_provider
    _meta_provider = meta_provider
    if toolbar_provider is not _TOOLBAR_SENTINEL:
        _toolbar_provider = toolbar_provider  # type: ignore[assignment]


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
                        display=ANSI(f"{C['cyan']}/{name}{C['reset']}"),
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


if HAS_PROMPT_TOOLKIT:
    class FileMentionCompleter(Completer):
        """Fuzzy ``@`` path completion using file_filter from kimi-cli."""

        _FRAGMENT_PATTERN = re.compile(r"[^\s@]+")
        _TRIGGER_GUARDS = frozenset((".", "-", "_", "`", "'", '"', ":", "@", "#", "~"))

        def __init__(self, root: Path | None = None, *, limit: int = 1000) -> None:
            self._root = root or Path.cwd()
            self._limit = limit
            self._cache_time: float = 0.0
            self._cached_paths: list[str] = []
            self._fragment_hint: str | None = None

            self._word_completer = WordCompleter(
                self._get_paths,
                WORD=False,
                pattern=self._FRAGMENT_PATTERN,
            )
            self._fuzzy = FuzzyCompleter(
                self._word_completer,
                WORD=False,
                pattern=r"^[^\s@]*",
            )

        def _get_paths(self) -> list[str]:
            try:
                from file_filter import list_files_git, list_files_walk, detect_git
            except Exception:
                return []
            fragment = self._fragment_hint or ""
            scope: str | None = None
            if "/" in fragment:
                scope = fragment.rsplit("/", 1)[0]
            now = time.monotonic()
            if now - self._cache_time <= 2.0:
                return self._cached_paths
            try:
                if detect_git(self._root):
                    paths = list_files_git(self._root, scope)
                else:
                    paths = list_files_walk(self._root, scope, limit=self._limit)
            except Exception:
                paths = []
            self._cached_paths = paths or []
            self._cache_time = now
            return self._cached_paths

        @staticmethod
        def _extract_fragment(text: str) -> str | None:
            index = text.rfind("@")
            if index == -1:
                return None
            if index > 0:
                prev = text[index - 1]
                if prev.isalnum() or prev in FileMentionCompleter._TRIGGER_GUARDS:
                    return None
            fragment = text[index + 1 :]
            if not fragment:
                return ""
            if any(ch.isspace() for ch in fragment):
                return None
            return fragment

        def get_completions(self, document, complete_event):  # type: ignore[override]
            fragment = self._extract_fragment(document.text_before_cursor)
            if fragment is None:
                return
            mention_doc = Document(text=fragment, cursor_position=len(fragment))
            self._fragment_hint = fragment
            try:
                candidates = list(self._fuzzy.get_completions(mention_doc, complete_event))
                frag_lower = fragment.lower()

                def _rank(c: Completion) -> tuple[int, ...]:
                    path = c.text
                    base = path.rstrip("/").split("/")[-1].lower()
                    if base.startswith(frag_lower):
                        return (0,)
                    elif frag_lower in base:
                        return (1,)
                    return (2,)

                candidates.sort(key=_rank)
                yield from candidates
            finally:
                self._fragment_hint = None

else:
    class FileMentionCompleter:
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
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.application.current import get_app
    completer = merge_completers([
        SlashCompleter(),
        FileMentionCompleter(),
    ])
    history = FileHistory(str(history_path)) if history_path else InMemoryHistory()
    style = Style.from_dict({
        "completion-menu.completion":              "bg:#222222 #cccccc",
        "completion-menu.completion.current":      "bg:#005f87 #ffffff bold",
        "completion-menu.meta.completion":         "bg:#222222 #808080",
        "completion-menu.meta.completion.current": "bg:#005f87 #eeeeee",
        "auto-suggestion":                         "#606060 italic",
        "bottom-toolbar":                          "",
        "bottom-toolbar.text":                     "",
    })

    # Only bind Tab to accept suggestion — right/ctrl-f/ctrl-e are already
    # handled by PromptSession's built-in load_auto_suggest_bindings().
    # Adding our own right/ctrl-f bindings without filters caused double-fire.
    @Condition
    def _suggestion_available():
        try:
            app = get_app()
            buf = app.current_buffer
            return (
                buf.suggestion is not None
                and len(buf.suggestion.text) > 0
                and buf.document.is_cursor_at_the_end
            )
        except Exception:
            return False

    kb = KeyBindings()

    @kb.add("tab", filter=_suggestion_available)
    def _tab_accept(event):
        """Tab accepts ghost suggestion when one is available."""
        buf = event.app.current_buffer
        if buf.suggestion:
            buf.insert_text(buf.suggestion.text)

    # ── Paste accumulation (kimi-cli style) ────────────────────────────────
    if _paste_ph is not None:
        @kb.add(Keys.BracketedPaste, eager=True)
        def _on_bracketed_paste(event):
            """Fold large pastes into a placeholder instead of flooding the buffer."""
            text = event.data
            token = _paste_ph.maybe_placeholderize(text)
            event.current_buffer.insert_text(token)

        # Fallback for terminals without bracketed-paste support (Windows conhost, etc.)
        @kb.add("c-v")
        def _ctrl_v_paste(event):
            """Ctrl+V reads clipboard via pyperclip and inserts as placeholder."""
            try:
                import pyperclip
                text = pyperclip.paste()
            except Exception:
                return
            if text:
                token = _paste_ph.maybe_placeholderize(text)
                event.current_buffer.insert_text(token)

    def _bottom_toolbar():
        provider = _toolbar_provider
        text = ""
        if provider is not None:
            try:
                text = provider()
            except Exception:
                pass
        
        # Inject status (e.g. energy bar) after the main toolbar text
        status = _toolbar_status
        if status:
            if text:
                text += " | " + status
            else:
                text = status
        
        return ANSI(text) if text else ""

    return PromptSession(
        history=history,
        completer=completer,
        auto_suggest=AutoSuggestFromHistory(),
        complete_while_typing=True,
        enable_history_search=False,
        mouse_support=False,
        style=style,
        key_bindings=kb,
        bottom_toolbar=_bottom_toolbar,
    )


def read_line(prompt_ansi: str, history_path: Optional[Path] = None) -> str:
    """Read one line of input via prompt_toolkit; caches the session across calls.

    The history file passed here MUST NOT be the readline history file — the
    two line-editors use incompatible formats. See Dulus REPL for the
    dedicated PT_HISTORY_FILE.
    """
    global _SESSION, _SESSION_HISTORY_PATH, _notification_callback, _active_app
    
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

    # ── Recent-message strip (sliding window above the prompt) ────────────
    # Recent-strip: pre-print last N msgs, erase them + prompt after Enter.
    # Use VT100 DEC save/restore (\0337/\0338) — separate register from
    # ANSI \033[s/\033[u which prompt_toolkit uses internally and would
    # clobber our saved position.
    import sys as _sys
    recent = _RECENT_USER_MSGS[-_RECENT_MAX:] if _RECENT_USER_MSGS else []

    _sys.stdout.write("\0337")           # DEC save cursor (ESC 7)
    for msg in recent:
        _sys.stdout.write(f"\033[2m» {msg}\033[0m\n")
    _sys.stdout.flush()

    with patch_stdout(raw=True):
        try:
            _active_app = _SESSION.app
            result = _SESSION.prompt(ANSI(prompt_ansi))
        finally:
            _active_app = None

    _sys.stdout.write("\0338\033[J")     # DEC restore cursor (ESC 8) → erase to end
    _sys.stdout.flush()

    return result


# ── Split Layout Mode (Kimi/Claude style) ────────────────────────────────────
# Fixed bottom input bar with scrollable output area above

_split_app: Optional[Any] = None
_split_buffer: Optional[Any] = None
_output_buffer: list[str] = []
_original_stdout = None

# When True, the user's typed message is NOT echoed into the main output area
# on Enter; instead it goes into the in-bar recent strip below.
_HIDE_SENDER: bool = True

# Last N user messages shown inside the sticky bar (above the input line).
_RECENT_USER_MSGS: list[str] = []
_RECENT_MAX = 5


def set_hide_sender(enabled: bool) -> None:
    """Toggle whether the typed message gets echoed above the sticky bar."""
    global _HIDE_SENDER
    _HIDE_SENDER = bool(enabled)


def _count_deduped_recent() -> int:
    """Count non-consecutive-duplicate entries in _RECENT_USER_MSGS (same key as render)."""
    def _k(s: str) -> str:
        return s.replace("\n", " ").strip().casefold()
    n = 0
    last = None
    for m in _RECENT_USER_MSGS:
        k = _k(m)
        if k and k != last:
            n += 1
            last = k
    return n


def add_recent_msg(text: str) -> None:
    """Push a user message into the recent-history strip (sliding window)."""
    global _RECENT_USER_MSGS
    stripped = text.strip()
    if not stripped:
        return
    _RECENT_USER_MSGS.append(stripped)
    # Keep only the last N — oldest slides off
    del _RECENT_USER_MSGS[:-_RECENT_MAX]


class _OutputRedirector:
    """Redirects stdout to the split layout output buffer.
    
    Thread-safe: multiple threads (main REPL, Telegram bg runner, sentinel)
    may write concurrently. A lock prevents buffer corruption.
    
    CRITICAL: Strips cursor-movement ANSI sequences (\033[A, \033[2K, etc.)
    before storing. These sequences come from Rich Live, spinners, and other
    terminal apps, but they are meaningless in a static split-layout buffer
    and cause "ghost lines" that reappear on every redraw.
    Color/style sequences (\033[31m, \033[1m) are preserved.
    """
    def __init__(self, original):
        self._original = original
        self._buffer = ""
        self._lock = threading.Lock()
        # True when the last operation left an "open" line (no newline).
        # Used by flush() to decide whether to concat or create a new line.
        self._last_line_open = False
    
    @staticmethod
    def _strip_cursor_ansi(text: str) -> str:
        """Remove cursor-control ANSI sequences; keep color/style ones."""
        import re as _re
        # Matches CSI sequences for cursor move, erase, scroll, save/restore.
        # Preserves 'm' suffix (SGR color/style) and other harmless codes.
        return _re.sub(
            r'\x1b\['
            r'(?:\d*[ABCDEGHJKSTfnsu]|\d+;\d+[Hf]|\?[\d;]*[hl])',
            '',
            text,
        )
    
    def write(self, text: str) -> None:
        if not text:
            return
        # When a background turn is running (_SUPPRESS_CONSOLE=True), discard
        # all writes so we don't call append_output() → _split_app.invalidate()
        # which would cause the split layout to flash/redraw mid-background-turn.
        try:
            import sys as _sys
            _dulus_mod = _sys.modules.get('dulus') or _sys.modules.get('__main__')
            if _dulus_mod and getattr(_dulus_mod, "_SUPPRESS_CONSOLE", False):
                return
        except Exception:
            pass
        # Sanitize: kill cursor-control ANSI sequences before they poison
        # the split-layout buffer with ghost lines.
        text = self._strip_cursor_ansi(text)
        if not text:
            return
        with self._lock:
            # Accumulate text to avoid character-by-character fragmentation
            self._buffer += text
            
            # Only process if we have complete lines OR buffer is getting large
            if "\n" in self._buffer or len(self._buffer) > 200:
                lines = self._buffer.split("\n")
                # Process all complete lines
                for line in lines[:-1]:
                    # Strip carriage returns (\r → ^M) from each line before display
                    clean = line.replace("\r", "")
                    if clean.strip():
                        append_output(clean)
                        self._last_line_open = False
                # Keep incomplete last line in buffer (strip \r too)
                self._buffer = lines[-1].replace("\r", "")
    
    def flush(self) -> None:
        # Flush any remaining buffered content.
        # When the buffer has no newline, we treat it as a continuation of the
        # same logical line — this prevents word-by-word fragmentation from
        # streaming prints (e.g. thinking chunks with flush=True).
        with self._lock:
            if self._buffer:
                clean = self._strip_cursor_ansi(self._buffer).replace("\r", "")
                if clean.strip():
                    global _output_buffer
                    if _output_buffer and self._last_line_open and not clean.startswith("\n"):
                        # Continuation of the previous open line
                        _output_buffer[-1] += clean
                    else:
                        append_output(clean)
                        self._last_line_open = True
                self._buffer = ""
        # Rate-limit invalidations here too — each streaming chunk calls
        # flush(), and without throttling the split layout redraws 20-30×/s,
        # causing the input bar to flicker and "lose" the user's typed text.
        global _invalidate_pending, _split_app, _last_invalidate_time
        if _split_app:
            now = time.monotonic()
            if _invalidate_pending and now - _last_invalidate_time >= 0.05:
                _last_invalidate_time = now
                _invalidate_pending = False
                _split_app.invalidate()
    
    def reset(self) -> None:
        """Clear internal buffer and line-open state.
        
        Call at the start of each turn to prevent residual buffered text
        from concatenating with the new turn's output.
        """
        with self._lock:
            self._buffer = ""
            self._last_line_open = False
    
    def isatty(self) -> bool:
        return False  # Pretend we're not a tty to prevent echo


def read_line_split(prompt: str = "> ", history_path: Optional[Path] = None) -> str:
    """Read input with split layout - fixed bottom bar, scrollable output above.
    
    Similar to Kimi Code and Claude Code interfaces.
    """
    global _split_app, _split_buffer, _output_buffer, _original_stdout, _notification_callback, _active_app
    
    # Drain any pending background notifications before showing prompt
    # Drain notifications but don't display yet - we'll add them after creating the app
    _pending_notes = drain_notifications()
    
    if not HAS_PROMPT_TOOLKIT:
        # No prompt_toolkit - print notifications directly
        for note in _pending_notes:
            if _notification_callback:
                _notification_callback(note)
            else:
                print(note)
        raise RuntimeError("prompt_toolkit is not installed")
    
    import sys
    # Save and redirect stdout
    _original_stdout = sys.stdout
    sys.stdout = _OutputRedirector(_original_stdout)
    
    from prompt_toolkit import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout import HSplit, Layout, Window, ConditionalContainer
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.layout.processors import BeforeInput, AppendAutoSuggestion
    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
    from prompt_toolkit.key_binding.bindings.emacs import load_emacs_bindings
    from prompt_toolkit.filters import has_completions, Condition
    
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
    completer = merge_completers([
        SlashCompleter(),
        FileMentionCompleter(),
    ])

    _split_buffer = Buffer(
        history=history,
        completer=completer,
        auto_suggest=AutoSuggestFromHistory(),
        complete_while_typing=True,
        enable_history_search=False,
        multiline=False,
    )
    
    # Input control with prompt
    # Handle ANSI codes in prompt (e.g., from shell PS1)
    # Filter out screen-clearing codes (J, K, etc.) but keep colors
    import re
    clean_prompt = prompt
    if isinstance(prompt, str):
        # Remove clear-screen codes: ESC[J, ESC[2J, ESC[K, ESC[0K, ESC[1K, ESC[2K
        clean_prompt = re.sub(r'\x1b\[[0-9]*[JK]', '', prompt)
        # Strip newlines (\n → ^J in split layout single-line input window)
        clean_prompt = clean_prompt.replace('\n', ' ').strip()
        # Parse remaining ANSI codes (colors)
        if '\x1b[' in clean_prompt:
            formatted_prompt = ANSI(clean_prompt)
        else:
            formatted_prompt = clean_prompt
    else:
        formatted_prompt = prompt
    
    input_control = BufferControl(
        buffer=_split_buffer,
        # AppendAutoSuggestion renders the dim ghost text from history that
        # PromptSession shows for free — bare BufferControl doesn't add it.
        input_processors=[
            BeforeInput(formatted_prompt, style="class:prompt"),
            AppendAutoSuggestion(),
        ],
    )
    input_window = Window(
        content=input_control,
        height=1,
        wrap_lines=False,
        always_hide_cursor=False,
    )

    # Recent-messages strip (inside the sticky bar, above the input line).
    # Shows up to _RECENT_MAX most-recent user submissions, oldest at top.
    def _get_recent_text():
        if not _RECENT_USER_MSGS:
            return ""
        # Collapse consecutive duplicates (compare stripped+normalised to
        # ignore trailing whitespace/newline differences).
        def _key(s: str) -> str:
            return s.replace("\n", " ").strip().casefold()
        deduped: list[str] = []
        last_key = None
        for m in _RECENT_USER_MSGS:
            k = _key(m)
            if k and k != last_key:
                deduped.append(m)
                last_key = k
        lines = []
        for m in deduped[-_RECENT_MAX:]:
            line = m.replace("\n", " ").strip()
            if len(line) > 200:
                line = line[:197] + "..."
            lines.append(f"{C['bold']}{C['cyan']}» {C['reset']}{C['gray']}{line}{C['reset']}")
        return ANSI("\n".join(lines))

    recent_control = FormattedTextControl(
        text=_get_recent_text,
        focusable=False,
        show_cursor=False,
    )
    recent_window = ConditionalContainer(
        content=Window(
            content=recent_control,
            height=lambda: max(1, min(_count_deduped_recent(), _RECENT_MAX)) if _RECENT_USER_MSGS else 0,
            wrap_lines=False,
        ),
        filter=Condition(lambda: bool(_HIDE_SENDER and _RECENT_USER_MSGS)),
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

    # ── Paste accumulation (kimi-cli style) ────────────────────────────────
    if _paste_ph is not None:
        @kb.add(Keys.BracketedPaste, eager=True)
        def _on_bracketed_paste_split(event):
            """Fold large pastes into a placeholder instead of flooding the buffer."""
            text = event.data
            token = _paste_ph.maybe_placeholderize(text)
            event.current_buffer.insert_text(token)

        # Fallback for terminals without bracketed-paste support (Windows conhost, etc.)
        @kb.add("c-v")
        def _ctrl_v_paste_split(event):
            """Ctrl+V reads clipboard via pyperclip and inserts as placeholder."""
            try:
                import pyperclip
                text = pyperclip.paste()
            except Exception:
                return
            if text:
                token = _paste_ph.maybe_placeholderize(text)
                event.current_buffer.insert_text(token)

    @kb.add("enter")
    def submit(event):
        """Submit input.
        - hide_sender ON  (default): push to in-bar recent strip (max 5).
        - hide_sender OFF: echo `» <msg>` into the main output area.
        Also persists to FileHistory so ↑/↓ recall works across sessions
        (PromptSession does this for free; raw Application doesn't)."""
        text = _split_buffer.text
        if text.strip():
            # Persist for ↑/↓ (bash-style command history).
            # Dedupe consecutive duplicates (bash HISTCONTROL=ignoredups).
            try:
                _last_hist = None
                try:
                    _strs = list(_split_buffer.history.get_strings())
                    _last_hist = _strs[-1] if _strs else None
                except Exception:
                    pass
                if _last_hist != text:
                    _split_buffer.append_to_history()
            except Exception:
                pass
            if _HIDE_SENDER:
                _norm = text.replace("\n", " ").strip().casefold()
                _last_norm = (
                    _RECENT_USER_MSGS[-1].replace("\n", " ").strip().casefold()
                    if _RECENT_USER_MSGS else None
                )
                if _norm and _norm != _last_norm:
                    _RECENT_USER_MSGS.append(text)
                    if len(_RECENT_USER_MSGS) > _RECENT_MAX:
                        del _RECENT_USER_MSGS[:-_RECENT_MAX]
            else:
                append_output(f"{C['bold']}{C['cyan']}» {C['reset']}{text}")
                # Keep only the last _RECENT_MAX `» ` echoes in the output buffer
                # so we never crawl to Narnia.
                marker = "» "
                echo_idx = [i for i, ln in enumerate(_output_buffer) if marker in ln and ln.lstrip().startswith(f"{C['bold']}{C['cyan']}»")]
                if len(echo_idx) > _RECENT_MAX:
                    drop = set(echo_idx[:-_RECENT_MAX])
                    _output_buffer[:] = [ln for i, ln in enumerate(_output_buffer) if i not in drop]
        event.app.exit(result=text)
    
    @kb.add("right")
    def _accept_suggestion(event):
        """→ accepts the ghost suggestion when cursor is at end of line.
        Otherwise moves cursor right as normal."""
        buf = event.app.current_buffer
        if (
            buf.suggestion
            and buf.suggestion.text
            and buf.document.is_cursor_at_the_end
        ):
            buf.insert_text(buf.suggestion.text)
        else:
            buf.cursor_position += 1

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

    # NOTE: Up/Down (history), Right/End (accept ghost suggestion), Ctrl+A/E,
    # word-jump etc. all come from load_emacs_bindings() merged below — DON'T
    # re-bind them here or they'll override the well-tested defaults.

    # Build layout: output on top, separator, recent-strip + input at bottom
    def _get_toolbar_text():
        # Get base text from provider
        base_text = ""
        provider = _toolbar_provider
        if provider:
            try:
                base_text = str(provider())
            except Exception:
                pass
        
        # Combine with background status (e.g. wake energy bar)
        global _toolbar_status
        status = _toolbar_status or ""
        
        # Format: [Base]  [Status]
        combined = f" {base_text}   {status}".strip()
        return ANSI(combined) if combined else ""

    toolbar_window = ConditionalContainer(
        content=Window(
            content=FormattedTextControl(text=_get_toolbar_text),
            height=1,
        ),
        filter=Condition(lambda: _toolbar_provider is not None),
    )

    root_container = HSplit([
        output_window,  # Flexible height for output
        Window(height=1, char="─", style="class:separator"),
        recent_window,  # Last N user messages (in-bar history strip)
        input_window,   # Fixed height for input
        toolbar_window, # Status toolbar (model, tokens, git)
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
        key_bindings=merge_key_bindings([load_emacs_bindings(), kb]),
        style=style,
        mouse_support=False,
        full_screen=False,
        # Erase the rendered frame on exit so the prompt-envelope ghost
        # ([cwd] [pct] » <typed>) doesn't get left behind in scrollback
        # — we already echoed a clean `» <msg>` line via append_output().
        erase_when_done=True,
    )
    
    # Now display pending notifications in the split layout
    if _pending_notes:
        for note in _pending_notes:
            if _notification_callback:
                _notification_callback(note)
            else:
                _output_buffer.append(note)
        # Refresh to show notifications
        _split_app.invalidate()
    
    # Track as active
    _active_app = _split_app
    try:
        result = _split_app.run()
    finally:
        _active_app = None
        _split_app = None
    
    # Restore stdout
    sys.stdout = _original_stdout
    _original_stdout = None
    
    # Reset buffer for next use
    if _split_buffer:
        _split_buffer.reset()
    
    return result if result else ""


# Rate-limiting state for invalidate() — prevents Windows console from
# choking on excessive redraws during high-frequency streaming.
_last_invalidate_time: float = 0.0
_invalidate_pending: bool = False

def append_output(text: str) -> None:
    """Append text to the output buffer (for split layout mode).
    
    Use this to display messages without interrupting the input bar.
    """
    global _output_buffer, _split_app, _last_invalidate_time, _invalidate_pending
    # Sanitize: strip \r and split on embedded \n so no ^M or ^J leaks
    text = text.replace("\r", "")
    for line in text.split("\n"):
        if line:
            _output_buffer.append(line)
    # Keep last 1000 lines
    if len(_output_buffer) > 1000:
        _output_buffer = _output_buffer[-1000:]
    # Refresh display if app is running — rate-limited to avoid Windows
    # console corruption when chunks arrive faster than the renderer.
    if _split_app:
        now = time.monotonic()
        if now - _last_invalidate_time >= 0.05:
            _last_invalidate_time = now
            _invalidate_pending = False
            _split_app.invalidate()
        else:
            _invalidate_pending = True


def clear_split_output() -> None:
    """Clear the split layout output buffer."""
    global _output_buffer
    _output_buffer.clear()


def get_original_stdout():
    """Return the real stdout before patch_stdout/_OutputRedirector wrapping."""
    return _original_stdout


def set_stdout_bypass(active: bool) -> None:
    """Temporarily bypass the _OutputRedirector and write directly to the real terminal.

    Call with active=True before a background turn, active=False after.
    This makes background output look identical to NOTIFICATION SYSTEM NEEDED —
    no fragmentation, no ^M/^J, because the real terminal handles \\r natively.
    """
    import sys
    if active:
        # If _OutputRedirector is active, swap back to the real stdout
        if _original_stdout is not None and isinstance(sys.stdout, _OutputRedirector):
            sys.stdout = _original_stdout
    else:
        # Restore _OutputRedirector if split app is still running
        if _original_stdout is not None and not isinstance(sys.stdout, _OutputRedirector):
            sys.stdout = _OutputRedirector(_original_stdout)


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


def safe_print_notification(text: str, end: str = "\n", flush: bool = False) -> None:
    """Print a notification in a prompt_toolkit-safe way.
    
    If split layout is active, uses append_output.
    Otherwise prints directly (which may cause display issues in sticky mode).
    """
    global _split_app, _original_stdout
    
    # We only strip if not using specific 'end' (to maintain tail control)
    if end == "\n":
        text = text.strip('\r\n')
    
    if _split_app and getattr(_split_app, "is_running", False):
        from prompt_toolkit.application.run_in_terminal import run_in_terminal
        import asyncio
        
        def _target():
            if _original_stdout:
                _original_stdout.write(text + end)
                if flush:
                    _original_stdout.flush()
            else:
                import sys
                sys.stdout.write(text + end)
                if flush:
                    sys.stdout.flush()
                
        def _schedule():
            try:
                # run_in_terminal temporarily suspends the UI bar,
                # prints our text, then restores the bar.
                task = run_in_terminal(_target)
                if asyncio.iscoroutine(task):
                    _split_app.create_background_task(task)
            except Exception:
                pass
                
        # Fire safely within the prompt_toolkit UI thread
        _split_app.loop.call_soon_threadsafe(_schedule)
    elif _original_stdout:
        # We're in some form of redirected stdout natively
        _original_stdout.write(text + "\n")
        _original_stdout.flush()
    else:
        # Fallback to regular print
        print(text)


def set_toolbar_status(text: str) -> None:
    """Set a short status string to be shown in the bottom toolbar.
    
    Thread-safe. Automatically invalidates the display if split layout is active.
    Pass "" to clear.
    """
    global _toolbar_status, _split_app
    _toolbar_status = text.strip().replace("\n", " ")
    if _split_app:
        # Invalidate soon via the UI thread
        try:
            _split_app.loop.call_soon_threadsafe(_split_app.invalidate)
        except Exception:
            pass
def request_exit() -> bool:
    """Signal the active prompt session to exit immediately.
    
    Returns True if successfully signaled, False if no prompt is active.
    Thread-safe.
    """
    global _active_app
    if _active_app and getattr(_active_app, "is_running", False):
        try:
            _active_app.loop.call_soon_threadsafe(_active_app.exit)
            return True
        except Exception:
            pass
    return False
