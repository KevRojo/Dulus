import sys
import json

# ── Import slash completer helpers ──
try:
    from backend.ui.input import (
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


# Curated palettes (hex per semantic role). `cyan/green/blue` collapse to the
# theme's accent color since Falcon uses them all for primary chrome.
# Add new ones here and they show up in `/theme` automatically.
THEMES: dict = {
    "falcon":      {"accent": "#FF8700", "warn": "#FFAF00", "code": "monokai"},
    "dracula":     {"accent": "#BD93F9", "warn": "#FFB86C", "code": "dracula"},
    "nord":        {"accent": "#88C0D0", "warn": "#EBCB8B", "code": "nord"},
    "gruvbox":     {"accent": "#FABD2F", "warn": "#FE8019", "code": "gruvbox-dark"},
    "solarized":   {"accent": "#268BD2", "warn": "#B58900", "code": "solarized-dark"},
    "tokyo-night": {"accent": "#7AA2F7", "warn": "#E0AF68", "code": "one-dark"},
    "catppuccin":  {"accent": "#F5C2E7", "warn": "#FAB387", "code": "one-dark"},
    "matrix":      {"accent": "#00FF41", "warn": "#CCFF00", "code": "monokai"},
    "synthwave":   {"accent": "#FF00FF", "warn": "#FFCC00", "code": "fruity"},
    "midnight":    {"accent": "#00BCD4", "warn": "#FFC107", "code": "dracula"},
    "ocean":       {"accent": "#38bdf8", "warn": "#fbbf24", "code": "nord"},
    "monokai":     {"accent": "#a6e22e", "warn": "#e6db74", "code": "monokai"},
    "mono":        {"accent": "#E0E0E0", "warn": "#A0A0A0", "code": "bw"},
    "none":        {"accent": "#FFFFFF", "warn": "#FFFFFF", "code": "default"},
}

# Active code-block style for Rich Markdown rendering — read by falcon.py.
CODE_THEME: str = "monokai"

C = {
    "cyan":    "", "green": "", "yellow": "", "red": "",
    "blue":    "", "magenta": "", "white": "", "gray": "",
    "bold":    "\033[1m",
    "dim":     "\033[2m",
    "reset":   "\033[0m",
}


def apply_theme(name: str) -> bool:
    """Mutate the global ANSI color map in-place to a named theme."""
    global CODE_THEME
    p = THEMES.get(name)
    if not p:
        return False
    accent = _rgb(p["accent"])
    warn   = _rgb(p["warn"])
    C["cyan"] = C["green"] = C["blue"] = accent
    C["yellow"] = C["magenta"] = warn
    C["red"]    = "\033[38;5;196m"   # errors stay red across all themes
    C["white"]  = "\033[97m"
    C["gray"]   = "\033[90m"
    CODE_THEME  = p["code"]
    return True


# Default = Falcon orange (preserve previous look).
apply_theme("falcon")

def clr(text: str, *keys: str) -> str:
    return "".join(C[k] for k in keys) + str(text) + C["reset"]

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
