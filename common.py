import sys
import json

# ── Import slash completer helpers ──
try:
    from ui.input import (
        setup as _setup_slash_complete,
        read_line as _read_line_pt,
        reset_session as _reset_pt_session,
        HAS_PROMPT_TOOLKIT as _HAS_PT,
    )
    def setup_slash_commands(commands_provider, meta_provider):
        """Initialize slash command tab completion."""
        _setup_slash_complete(commands_provider, meta_provider)
        return _HAS_PT

    def read_slash_input(prompt):
        """Read input with slash completion."""
        return _read_line_pt(prompt, None)

    def reset_slash_session():
        """Reset the prompt_toolkit session."""
        _reset_pt_session()
except ImportError:
    def setup_slash_commands(*args, **kwargs):
        return False
    def read_slash_input(prompt):
        return input(prompt)
    def reset_slash_session():
        pass

# ── ANSI helpers ─────────────────────────────────────────────────────────────

def _rgb(hex_str: str) -> str:
    """Convert '#rrggbb' → ANSI 24-bit foreground escape."""
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


# Curated palettes — each theme defines four semantic roles:
#   accent : info / primary chrome (cyan, blue)
#   ok     : success / diff additions (green) — kept distinct from accent
#            so info() and ok() stay visually separable
#   warn   : warnings (yellow, magenta)
#   err    : errors / diff removals (red)
#   code   : Rich Markdown code-block style (any Pygments style name)
# Use {"disable_color": True, "code": "default"} to ship a colorless theme.
# Add new entries here and they show up in `/theme` automatically.
THEMES: dict = {
    "dulus":       {"accent": "#FF8700", "ok": "#00FF87", "warn": "#FFAF00", "err": "#FF5F5F", "code": "monokai"},
    "dracula":     {"accent": "#BD93F9", "ok": "#50FA7B", "warn": "#FFB86C", "err": "#FF5555", "code": "dracula"},
    "nord":        {"accent": "#88C0D0", "ok": "#A3BE8C", "warn": "#EBCB8B", "err": "#BF616A", "code": "nord"},
    "gruvbox":     {"accent": "#FABD2F", "ok": "#B8BB26", "warn": "#FE8019", "err": "#FB4934", "code": "gruvbox-dark"},
    "solarized":   {"accent": "#268BD2", "ok": "#859900", "warn": "#B58900", "err": "#DC322F", "code": "solarized-dark"},
    "tokyo-night": {"accent": "#7AA2F7", "ok": "#9ECE6A", "warn": "#E0AF68", "err": "#F7768E", "code": "one-dark"},
    "catppuccin":  {"accent": "#F5C2E7", "ok": "#A6E3A1", "warn": "#FAB387", "err": "#F38BA8", "code": "one-dark"},
    "matrix":      {"accent": "#00FF41", "ok": "#7FFF00", "warn": "#CCFF00", "err": "#FF0000", "code": "monokai"},
    "synthwave":   {"accent": "#FF00FF", "ok": "#39FF14", "warn": "#FFCC00", "err": "#FF3864", "code": "fruity"},
    "midnight":    {"accent": "#00BCD4", "ok": "#76FF03", "warn": "#FFC107", "err": "#FF1744", "code": "dracula"},
    "ocean":       {"accent": "#38BDF8", "ok": "#34D399", "warn": "#FBBF24", "err": "#F87171", "code": "nord"},
    "monokai":     {"accent": "#66D9EF", "ok": "#A6E22E", "warn": "#E6DB74", "err": "#F92672", "code": "monokai"},
    "mono":        {"accent": "#E0E0E0", "ok": "#C0C0C0", "warn": "#A0A0A0", "err": "#FFFFFF", "code": "bw"},
    "none":        {"disable_color": True, "code": "default"},
}

# Active code-block style for Rich Markdown rendering — read by dulus.py.
CODE_THEME: str = "monokai"

C = {
    "cyan":    "", "green": "", "yellow": "", "red": "",
    "blue":    "", "magenta": "", "white": "", "gray": "",
    "bold":    "\033[1m",
    "dim":     "\033[2m",
    "reset":   "\033[0m",
}


def apply_theme(name: str) -> bool:
    """Mutate the global ANSI color map in-place to a named theme.

    Themes carry 4 semantic roles (accent / ok / warn / err) that map onto
    Dulus's ANSI key set. `ok` is intentionally distinct from `accent` so
    info() (cyan-keyed) and ok() (green-keyed) stay visually separable.
    A theme with `disable_color: True` strips every escape for plain output.
    """
    global CODE_THEME
    p = THEMES.get(name)
    if not p:
        return False

    # Plain-text mode: zero out every key so clr() returns naked strings.
    if p.get("disable_color"):
        for k in list(C.keys()):
            C[k] = ""
        CODE_THEME = p.get("code", "default")
        return True

    accent = _rgb(p["accent"])
    ok_col = _rgb(p.get("ok", p["accent"]))
    warn_c = _rgb(p["warn"])
    err_c  = _rgb(p.get("err", "#FF5555"))

    C["cyan"]    = accent
    C["blue"]    = accent
    C["green"]   = ok_col
    C["yellow"]  = warn_c
    C["magenta"] = warn_c
    C["red"]     = err_c
    C["white"]   = "\033[97m"
    C["gray"]    = "\033[90m"
    C["bold"]    = "\033[1m"
    C["dim"]     = "\033[2m"
    C["reset"]   = "\033[0m"
    CODE_THEME   = p["code"]
    return True


# Default = Dulus orange (preserve previous look).
apply_theme("dulus")

def clr(text: str, *keys: str) -> str:
    # Defensive: a missing color key (theme-specific names like "accent" or
    # "orange" in palettes that don't define them) used to raise KeyError and
    # could crash callers. Skip unknown keys instead so a stale theme name
    # never takes down the daemon or REPL.
    return "".join(C.get(k, "") for k in keys) + str(text) + C.get("reset", "")

def info(msg: str):   print(clr(msg, "cyan"))
def ok(msg: str):     print(clr(msg, "green"))
def warn(msg: str):   print(clr(f"Warning: {msg}", "yellow"))
def err(msg: str):    print(clr(f"Error: {msg}", "red"), file=sys.stderr)

def stream_thinking(chunk: str, verbose: bool):
    if verbose:
        clean_chunk = chunk.replace("\n", " ")
        if clean_chunk:
            print(f"{C['dim']}{clean_chunk}", end="", flush=True)

# ── Tool Impersonation UI ────────────────────────────────────────────────────
def print_tool_start(name: str, inputs: dict):
    desc = f"{name}({', '.join(f'{k}={v}' for k, v in inputs.items())})"
    if name == "Read": desc = f"Read({inputs.get('file_path','')})"
    if name == "Write": desc = f"Write({inputs.get('file_path','')})"
    if name == "Bash": desc = f"Bash({inputs.get('command','')[:60]})"
    
    print(clr(f"  ⚙  {desc}", "dim", "cyan"), flush=True)

def print_tool_end(name: str, result: str, success: bool = True, verbose: bool = False, auto_show: bool = True):
    # For PrintToConsole, always show the full content since that's the point
    if name == "PrintToConsole":
        print(clr(f"  [PrintToConsole] {len(result)} chars displayed", "dim", "cyan"))
        print()
        # Print the actual content directly without clr() to avoid encoding issues
        try:
            print(result)
        except UnicodeEncodeError:
            # Fallback: encode then decode with error handling
            print(result.encode('utf-8', errors='replace').decode('utf-8'))
        print()
        return
    
    # For display-only tools (ASCII art, etc.), show full content like PrintToConsole if auto_show is ON
    from tool_registry import is_display_only
    is_display = is_display_only(name)

    if success:
        symbol = "[OK]"
        color = "green"
        summary = f"-> {len(result)} chars" if len(result) > 100 else f"-> {result}"
        print(clr(f"  {symbol} {summary}", "dim", color), flush=True)

        # For display-only tools, show the full content immediately if auto_show is ON
        if is_display and auto_show:
            print()
            try:
                print(result)
            except UnicodeEncodeError:
                print(result.encode('utf-8', errors='replace').decode('utf-8'))
            print()
    else:
        symbol = "[X]"
        color = "red"
        print(clr(f"  {symbol} {result[:120]}", "dim", color), flush=True)

    if verbose and success and not (is_display and auto_show):
        preview = result[:300] + ("..." if len(result) > 300 else "")
        # Replace newlines for indentation but handle encoding
        try:
            indented = preview.replace(chr(10), chr(10)+'     ')
            print(clr(f"     {indented}", "dim"))
        except UnicodeEncodeError:
            safe_preview = preview.encode('ascii', errors='replace').decode('ascii')
            print(clr(f"     {safe_preview}", "dim"))


def sanitize_text(text: str) -> str:
    """Remove invalid UTF-16 surrogates and ensure valid UTF-8.

    On Windows consoles (cp1252) pasted emojis often become stray surrogates
    (e.g. \\ud83d\\udcec) which later explode with:
        'utf-8' codec can't encode characters: surrogates not allowed
    This helper cleans them *once* at the boundary before they enter the
    conversation state or are sent to any API.
    """
    if not isinstance(text, str):
        return str(text)
    # Strip surrogate characters (U+D800-U+DFFF) — these are invalid in
    # UTF-8 and will cause encoding errors when JSON-serialised.
    return "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))
