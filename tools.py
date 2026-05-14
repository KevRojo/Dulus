"""Tool definitions and implementations for Dulus."""
import json
import os
import re
import glob as _glob
import difflib
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

from tool_registry import ToolDef, register_tool
from tool_registry import execute_tool as _registry_execute

# Import input.py for slash command autocompletion
try:
    from input import setup as input_setup, HAS_PROMPT_TOOLKIT, read_line
    # Expose setup for backwards compatibility (Dulus uses input.setup())
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    input_setup = None
    read_line = None

# Import dulus's COMMANDS and _CMD_META for autocompletion
try:
    from dulus import COMMANDS, _CMD_META
except ImportError:
    COMMANDS = {}
    _CMD_META = {}
try:
    from config import load_config
except ImportError:
    load_config = None
try:
    from common import clr
except ImportError:
    def clr(text, *keys):
        return str(text)

# ── AskUserQuestion state ──────────────────────────────────────────────────────
# The main REPL loop drains _pending_questions and fills _question_answers.
_pending_questions: list[dict] = []   # [{id, question, options, allow_freetext, event, result_holder}]
_ask_lock = threading.Lock()

# ── Telegram turn detection (thread-local) ─────────────────────────────────
# Using thread-local storage instead of a shared config key prevents race
# conditions when slash commands run in their own daemon threads while the
# Telegram poll loop and the main REPL loop continue on other threads.
_tg_thread_local = threading.local()


def _is_in_tg_turn(config: dict) -> bool:
    """Return True if the *current thread* is handling a Telegram interaction.

    Checks the thread-local flag first (set by the slash-command runner thread),
    then falls back to the config key (set by the main REPL for _bg_runner turns).
    """
    return getattr(_tg_thread_local, "active", False) or bool(config.get("_in_telegram_turn", False))

# ── Tool JSON schemas (sent to Claude API) ─────────────────────────────────

_LAUNCH_SANDBOX_SCHEMA = {
    "name": "LaunchSandbox",
    "description": "Start the Dulus Sandbox (mini-OS) web interface in the browser. "
                   "Provides a visual desktop experience with integrated Dulus Terminal.",
    "input_schema": {
        "type": "object",
        "properties": {
            "stop": {"type": "boolean", "description": "If true, stop the server instead of starting it."}
        },
    },
}

TOOL_SCHEMAS = [
    _LAUNCH_SANDBOX_SCHEMA,
    {
        "name": "Read",
        "description": (
            "Read a file's contents. Returns content with line numbers "
            "(format: 'N\\tline'). Use limit/offset to read large files in chunks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute file path"},
                "limit":     {"type": "integer", "description": "Max lines to read"},
                "offset":    {"type": "integer", "description": "Start line (0-indexed)"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "Write",
        "description": "Write content to a file. DO NOT use this for temporary results or data that should simply be printed to the user - use PrintToConsole for that. Only use Write for persistent code or documentation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content":   {"type": "string"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "Edit",
        "description": (
            "Replace exact text in a file. old_string must match exactly (including whitespace). "
            "If old_string appears multiple times, use replace_all=true or add more context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path":   {"type": "string"},
                "old_string":  {"type": "string", "description": "Exact text to replace"},
                "new_string":  {"type": "string", "description": "Replacement text"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    {
        "name": "Bash",
        "description": "Execute a shell command. Returns stdout+stderr. Stateless (no cd persistence).",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "description": "Seconds before timeout (default 30). Use 120-300 for package installs (npm, pip, npx), builds, and long-running commands."},
            },
            "required": ["command"],
        },
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern. Returns sorted list of matching paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern e.g. **/*.py"},
                "path":    {"type": "string", "description": "Base directory (default: cwd)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "Grep",
        "description": "Search file contents with regex using ripgrep (falls back to grep).",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern":      {"type": "string", "description": "Regex pattern"},
                "path":         {"type": "string", "description": "File or directory to search"},
                "glob":         {"type": "string", "description": "File filter e.g. *.py"},
                "output_mode":  {
                    "type": "string",
                    "enum": ["content", "files_with_matches", "count"],
                    "description": "content=matching lines, files_with_matches=file paths, count=match counts",
                },
                "case_insensitive": {"type": "boolean"},
                "context":      {"type": "integer", "description": "Lines of context around matches"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "WebFetch",
        "description": (
            "Fetch a URL and return its text content (HTML stripped). "
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url":       {"type": "string", "description": "URL to fetch or file:// path"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "WebSearch",
        "description": "Search the web (via Brave or DuckDuckGo). DO NOT save search results to files - just process them or use PrintToConsole to show them to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "LineCount",
        "description": "Rapidly count the number of lines in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute file path"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "SearchLastOutput",
        "description": (
            "Search or summarize the tool outputs accumulated during this turn. "
            "Use this to find specific data across one or more tool results that were truncated. "
            "With no pattern: returns a summary of the whole accumulation. "
            "With a pattern: returns only matching lines with context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for (case-insensitive). Omit to get a summary.",
                },
                "context": {
                    "type": "integer",
                    "description": "Lines of context around each match (default 2)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "PrintLastOutput",
        "description": (
            "Print the raw content of the last tool output file directly to terminal. "
            "Use this for ASCII art, tables, or large outputs that shouldn't be rewritten by the model. "
            "Returns the raw file content for direct display without processing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # ── Task tools (schemas also listed here for Claude's tool list) ──────────
    {
        "name": "TaskCreate",
        "description": (
            "Create a new task in the task list. "
            "Use this to track work items, to-dos, and multi-step plans."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject":     {"type": "string", "description": "Brief title"},
                "description": {"type": "string", "description": "What needs to be done"},
                "active_form": {"type": "string", "description": "Present-continuous label while in_progress"},
                "metadata":    {"type": "object", "description": "Arbitrary metadata"},
            },
            "required": ["subject", "description"],
        },
    },
    {
        "name": "TaskUpdate",
        "description": (
            "Update a task: change status, subject, description, owner, "
            "dependency edges, or metadata. "
            "Set status='deleted' to remove. "
            "Statuses: pending, in_progress, completed, cancelled, deleted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id":       {"type": "string"},
                "subject":       {"type": "string"},
                "description":   {"type": "string"},
                "status":        {"type": "string", "enum": ["pending","in_progress","completed","cancelled","deleted"]},
                "active_form":   {"type": "string"},
                "owner":         {"type": "string"},
                "add_blocks":    {"type": "array", "items": {"type": "string"}},
                "add_blocked_by":{"type": "array", "items": {"type": "string"}},
                "metadata":      {"type": "object"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "TaskGet",
        "description": "Retrieve full details of a single task by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to retrieve"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "TaskList",
        "description": "List all tasks with their status, owner, and pending blockers.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "NotebookEdit",
        "description": (
            "Edit a Jupyter notebook (.ipynb) cell. "
            "Supports replace (modify existing cell), insert (add new cell after cell_id), "
            "and delete (remove cell) operations. "
            "Read the notebook with the Read tool first to see cell IDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Absolute path to the .ipynb notebook file",
                },
                "new_source": {
                    "type": "string",
                    "description": "New source code/text for the cell",
                },
                "cell_id": {
                    "type": "string",
                    "description": (
                        "ID of the cell to edit. For insert, the new cell is inserted after this cell "
                        "(or at the beginning if omitted). Use 'cell-N' (0-indexed) if no IDs are set."
                    ),
                },
                "cell_type": {
                    "type": "string",
                    "enum": ["code", "markdown"],
                    "description": "Cell type. Required for insert; defaults to current type for replace.",
                },
                "edit_mode": {
                    "type": "string",
                    "enum": ["replace", "insert", "delete"],
                    "description": "replace (default) / insert / delete",
                },
            },
            "required": ["notebook_path", "new_source"],
        },
    },
    {
        "name": "GetDiagnostics",
        "description": (
            "Get LSP-style diagnostics (errors, warnings, hints) for a source file. "
            "Uses pyright/mypy/flake8 for Python, tsc for TypeScript/JavaScript, "
            "and shellcheck for shell scripts. Returns structured diagnostic output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to diagnose",
                },
                "language": {
                    "type": "string",
                    "description": (
                        "Override auto-detected language: python, javascript, typescript, "
                        "shellscript. Omit to auto-detect from file extension."
                    ),
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "AskUserQuestion",
        "description": (
            "Pause execution and ask the user a clarifying question. "
            "Use this when you need a decision from the user before proceeding. "
            "Returns the user's answer as a string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user.",
                },
                "options": {
                    "type": "array",
                    "description": "Optional list of choices. Each item: {label, description}.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label":       {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["label"],
                    },
                },
                "allow_freetext": {
                    "type": "boolean",
                    "description": "If true (default), user may type a free-text answer instead of selecting an option.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "Reminder",
        "description": (
            "Schedule a background reminder. When the duration elapses, a (System Automated Event) notification is injected "
            "so you can wake up and execute deferred monitoring tasks or checks. "
            "Use ONLY for genuine deferred wake-ups (e.g. 'remind me in 10 minutes to check the deploy'). "
            "For pausing BETWEEN tool calls in the same turn, use `Bash('sleep N')` instead — "
            "the Reminder countdown starts immediately and you should END the turn after calling it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "description": "Number of seconds to sleep before waking up."}
            },
            "required": ["seconds"],
        },
    },
    {
        "name": "PrintToConsole",
        "description": (
            "Display text to the USER in the chat console WITHOUT using response tokens. "
            "WARNING: This tool CANNOT save files. The 'file_path' parameter is for READING existing files only. "
            "DO NOT try to use this to 'store' results. Use the 'content' parameter to show results to the user. "
            "Perfect for: progress updates, step-by-step logs, lengthy explanations, debug info. "
            "The content appears in the chat immediately as the tool result. "
            "CRITICAL: After using PrintToConsole, DO NOT repeat the same content in your response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Text to display to the user. Supports newlines and formatting. This appears in the chat console.",
                },
                "style": {
                    "type": "string",
                    "enum": ["normal", "success", "info", "warning", "error"],
                    "description": "Visual style prefix: success=[OK], info=[i], warning=[!], error=[X], normal=none",
                    "default": "normal",
                },
                "prefix": {
                    "type": "string",
                    "description": "Optional source prefix like '[TOOL]' shown before the content",
                    "default": "",
                },
                "from_line": {
                    "type": "integer",
                    "description": "Extract content starting from this line number (1-indexed). Use with to_line to show specific range.",
                    "minimum": 1,
                },
                "to_line": {
                    "type": "integer",
                    "description": "Extract content up to this line number (inclusive). Use with from_line to show specific range.",
                    "minimum": 1,
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to a file to read and display. If provided, reads this file instead of using content parameter. Useful for job files, logs, etc.",
                },
            },
            "required": [],
        },
    },
]

# ── Safe bash commands (never ask permission) ───────────────────────────────

_SAFE_PREFIXES = (
    "ls", "cat", "head", "tail", "wc", "pwd", "echo", "printf", "date",
    "which", "type", "env", "printenv", "uname", "whoami", "id",
    "git log", "git status", "git diff", "git show", "git branch",
    "git remote", "git stash list", "git tag",
    "find ", "grep ", "rg ", "ag ", "fd ",
    "python ", "python3 ", "node ", "ruby ", "perl ",
    "pip show", "pip list", "npm list", "cargo metadata",
    "df ", "du ", "free ", "top -bn", "ps ",
    "curl -I", "curl --head",
)

def _is_safe_bash(cmd: str) -> bool:
    c = cmd.strip()
    return any(c.startswith(p) for p in _SAFE_PREFIXES)


# ── Diff helpers ──────────────────────────────────────────────────────────

def generate_unified_diff(old, new, filename, context_lines=3):
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines,
        fromfile=f"a/{filename}", tofile=f"b/{filename}", n=context_lines)
    return "".join(diff)

def maybe_truncate_diff(diff_text, max_lines=80):
    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text
    shown = lines[:max_lines]
    remaining = len(lines) - max_lines
    return "\n".join(shown) + f"\n\n[... {remaining} more lines ...]"


# ── Tool implementations ───────────────────────────────────────────────────

_DEFAULT_READ_LIMIT = 1000  # kimi-cli default


def _read(file_path: str, limit: int = None, offset: int = None) -> str:
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        return f"Error: file not found: {p}"
    if p.is_dir():
        return f"Error: {p} is a directory"
    try:
        # Default limit so the model doesn't accidentally swallow multi-MB files.
        effective_limit = limit if limit is not None else _DEFAULT_READ_LIMIT

        # For small files, we can just read everything. For large files, we should iterate.
        # Threshold for "large" file: 10MB
        size = p.stat().st_size
        if size < 10 * 1024 * 1024:
            lines = p.read_text(encoding="utf-8", errors="replace", newline="").splitlines(keepends=True)
            total = len(lines)
            start = offset or 0
            chunk = lines[start:start + effective_limit]
        else:
            # Memory efficient reading for large files
            total = 0
            chunk = []
            start = offset or 0
            end = start + effective_limit

            with p.open("r", encoding="utf-8", errors="replace", newline="") as f:
                for i, line in enumerate(f):
                    total += 1
                    if i >= start and i < end:
                        chunk.append(line)

        if not chunk and total > 0:
            return f"(offset {start} >= total lines {total})"
        if not chunk:
            return "(empty file)"

        header = f"[File: {file_path} | Total lines: {total} | Reading: {start+1} to {start+len(chunk)}]\n"
        if limit is None and total > effective_limit:
            header += f"[TRUNCATED — default limit of {effective_limit} lines applied. Use offset + limit to read more.]\n"
        content = "".join(f"{start + i + 1:6}\t{l}" for i, l in enumerate(chunk))
        return header + content
    except Exception as e:
        return f"Error: {e}"


def _line_count(file_path: str) -> str:
    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"
    try:
        count = 0
        with p.open("rb") as f:
            for line in f:
                count += 1
        return f"File: {file_path}\nTotal lines: {count}"
    except Exception as e:
        return f"Error: {e}"


def _print_last_output() -> str:
    """Print the full content of the last tool output directly.
    
    Use this to display large outputs (ASCII art, logs, etc.) without re-writing them.
    """
    out_file = Path.home() / ".dulus" / "last_tool_output.txt"
    if not out_file.exists():
        return "No saved tool output available."
    try:
        content = out_file.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            return "Last tool output is empty."
        return content
    except Exception as e:
        return f"Error reading saved output: {e}"


def _search_last_output(pattern: str = None, context: int = 2) -> str:
    """Search or summarize the tool outputs accumulated during this turn."""
    out_file = Path.home() / ".dulus" / "last_tool_output.txt"
    if not out_file.exists():
        return "No saved tool output available. No tool has produced truncated output yet."
    try:
        lines = out_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return f"Error reading saved output: {e}"

    total = len(lines)
    if total == 0:
        return "Saved tool output is empty."

    # No pattern → summary mode
    if not pattern:
        preview_n = 30
        head = lines[:preview_n]
        tail = lines[-preview_n:] if total > preview_n * 2 else []
        parts = [f"[Last tool output: {total} lines]"]
        parts.append("── First {0} lines ──".format(min(preview_n, total)))
        for i, l in enumerate(head):
            parts.append(f"{i + 1:6}\t{l}")
        if tail:
            parts.append(f"\n── Last {preview_n} lines ──")
            start = total - preview_n
            for i, l in enumerate(tail):
                parts.append(f"{start + i + 1:6}\t{l}")
        return "\n".join(parts)

    # Pattern mode → search with context
    import re as _re
    try:
        rx = _re.compile(pattern, _re.IGNORECASE)
    except _re.error as e:
        return f"Invalid regex: {e}"

    matches = []
    for i, line in enumerate(lines):
        if rx.search(line):
            start = max(0, i - context)
            end = min(total, i + context + 1)
            block = []
            for j in range(start, end):
                marker = ">>>" if j == i else "   "
                block.append(f"{marker} {j + 1:6}\t{lines[j]}")
            matches.append("\n".join(block))

    if not matches:
        return f"No matches for '{pattern}' in {total} lines of saved output."

    header = f"[Found {len(matches)} match(es) in {total} lines]"
    # Cap output to avoid blowing up context
    result = header + "\n\n" + "\n---\n".join(matches)
    if len(result) > 16000:
        result = result[:16000] + f"\n\n... (output capped — {len(matches)} total matches, refine your pattern)"
    
    # SAVE filtered result as new last_output so PrintLastOutput can display it
    try:
        out_file.write_text(result, encoding="utf-8")
    except Exception:
        pass  # Silently fail if can't write
    
    return result


def _write(file_path: str, content: str) -> str:
    p = Path(file_path)
    try:
        is_new = not p.exists()
        # Ensure utf-8 and newline="" for reading existing content to generate diff
        old_content = "" if is_new else p.read_text(encoding="utf-8", errors="replace", newline="")
        p.parent.mkdir(parents=True, exist_ok=True)
        # Always write as utf-8 with newline="" to prevent double CRLF on Windows
        p.write_text(content, encoding="utf-8", newline="")
        if is_new:
            lc = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            return f"Created {file_path} ({lc} lines)"
        filename = p.name
        diff = generate_unified_diff(old_content, content, filename)
        if not diff:
            return f"No changes in {file_path}"
        truncated = maybe_truncate_diff(diff)
        return f"File updated — {file_path}:\n\n{truncated}"
    except Exception as e:
        return f"Error: {e}"


def _edit(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"
    try:
        # Read with newline="" to get original line endings
        content = p.read_text(encoding="utf-8", errors="replace", newline="")
        
        # Detect original line endings: only treat as pure CRLF if every \n is part of \r\n
        crlf_count = content.count("\r\n")
        lf_count = content.count("\n")
        is_pure_crlf = crlf_count > 0 and crlf_count == lf_count

        # Normalize line endings to avoid \r\n vs \n mismatch during matching
        content_norm = content.replace("\r\n", "\n")
        old_norm = old_string.replace("\r\n", "\n")
        new_norm = new_string.replace("\r\n", "\n")

        count = content_norm.count(old_norm)
        if count == 0:
            return "Error: old_string not found in file. Please ensure EXACT match, including all exact leading spaces/indentation and trailing newlines."
        if count > 1 and not replace_all:
            return (f"Error: old_string appears {count} times. "
                    "Provide more context to make it unique, or use replace_all=true.")

        old_content_norm = content_norm
        new_content_norm = content_norm.replace(old_norm, new_norm) if replace_all else \
                           content_norm.replace(old_norm, new_norm, 1)

        # Restore CRLF only for pure-CRLF files; mixed or LF-only files stay as LF
        if is_pure_crlf:
            final_content = new_content_norm.replace("\n", "\r\n")
            old_content_final = content
        else:
            final_content = new_content_norm
            old_content_final = content_norm
                      
        # Write with newline="" to prevent double CRLF translation on Windows
        p.write_text(final_content, encoding="utf-8", newline="")
        filename = p.name
        diff = generate_unified_diff(old_content_final, final_content, filename)
        return f"Changes applied to {filename}:\n\n{diff}"
    except Exception as e:
        return f"Error: {e}"


def _kill_proc_tree(pid: int):
    """Kill a process and all its children."""
    import sys as _sys
    if _sys.platform == "win32":
        # taskkill /T kills the entire process tree on Windows
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _find_windows_bash():
    """Return (kind, path) for the best bash available on Windows, or None."""
    import shutil
    if not hasattr(_find_windows_bash, "_cache"):
        result = None
        # 1. bash already in PATH (Git for Windows added to PATH, MSYS2, etc.)
        bash_in_path = shutil.which("bash")
        if bash_in_path:
            # Skip WSL bash stub disguised as native bash
            if "system32" not in bash_in_path.lower() and "sysnative" not in bash_in_path.lower() and "syswow64" not in bash_in_path.lower():
                result = ("gitbash", bash_in_path)
        # 2. Git Bash at default install locations
        if result is None:
            for candidate in [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
            ]:
                if Path(candidate).exists():
                    result = ("gitbash", candidate)
                    break
        # 3. WSL
        if result is None:
            wsl = shutil.which("wsl")
            if wsl:
                try:
                    r = subprocess.run(["wsl", "echo", "ok"],
                                       capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        result = ("wsl", wsl)
                except Exception:
                    pass
        _find_windows_bash._cache = result
    return _find_windows_bash._cache


def _find_shell_by_type(shell_type: str, forced_path: str = ""):
    """Find a specific shell type on Windows. Returns (kind, path) or None."""
    import shutil

    # Handle custom shell with forced path
    if shell_type == "custom" and forced_path and Path(forced_path).exists():
        return ("custom", forced_path)

    if shell_type == "gitbash":
        # Try bash in PATH first (but not WSL stub)
        bash_in_path = shutil.which("bash")
        if bash_in_path:
            if "system32" not in bash_in_path.lower() and "sysnative" not in bash_in_path.lower() and "syswow64" not in bash_in_path.lower():
                return ("gitbash", bash_in_path)
        # Try default Git locations
        for candidate in [
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ]:
            if Path(candidate).exists():
                return ("gitbash", candidate)

    elif shell_type == "wsl":
        wsl = shutil.which("wsl")
        if wsl:
            try:
                r = subprocess.run(["wsl", "echo", "ok"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return ("wsl", wsl)
            except Exception:
                pass

    elif shell_type == "powershell":
        # Try PowerShell Core first, then Windows PowerShell
        candidates = [
            shutil.which("pwsh"),  # PowerShell Core
            shutil.which("powershell"),
            r"C:\Program Files\PowerShell\7\pwsh.exe",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return ("powershell", candidate)

    elif shell_type == "cmd":
        cmd = shutil.which("cmd") or r"C:\Windows\System32\cmd.exe"
        if Path(cmd).exists():
            return ("cmd", cmd)

    return None


def _win_to_posix(path_str: str, wsl: bool = False) -> str:
    """Convert a Windows path string to POSIX for bash/WSL.
    C:\\Users\\foo  →  /c/Users/foo  (gitbash)
    C:\\Users\\foo  →  /mnt/c/Users/foo  (wsl)
    """
    import re
    def _replace(m):
        drive = m.group(1).lower()
        rest  = m.group(2).replace("\\", "/")
        prefix = f"/mnt/{drive}" if wsl else f"/{drive}"
        return prefix + "/" + rest
    return re.sub(r"(?<![A-Za-z])([A-Za-z]):[\\/]([^'\";\n]*)", _replace, path_str)


# ── Bash sandbox: blocked dangerous command patterns ─────────────────────
_BASH_BLOCKED_PATTERNS: list[str] = [
    # rm -rf targeting system / home
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+/(?:\s*;|\s*&&|\s*\|\||\s*$)",
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+/\*",
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+~",
    # Disk destruction
    r"dd\s+.*of=/dev/[sh]d[a-z]",
    r"dd\s+.*of=/dev/nvme",
    r"dd\s+.*of=/dev/mmcblk",
    r">\s*/dev/[sh]d[a-z]",
    r">\s*/dev/nvme",
    # Formatters
    r"mkfs\.\w+\s+/dev/",
    r"mkfs\s+/dev/",
    r"fdisk\s+/dev/",
    r"parted\s+/dev/",
    # Permission destruction
    r"chmod\s+-[a-zA-Z]*R[a-zA-Z]*\s+777\s+/",
    # Fork bomb
    r":\s*\(\s*\)\s*\{\s*:\s*\|:\s*&\s*\}\s*;\s*:",
    # Curl/wget pipe-to-shell
    r"curl\s+.*\|\s*(?:bash|sh|zsh|fish)",
    r"wget\s+.*\|\s*(?:bash|sh|zsh|fish)",
    # Sensitive file reads
    r"cat\s+.*(?:/etc/shadow|/etc/gshadow|/etc/master\.passwd)",
    # Data exfiltration via curl
    r"curl\s+.*(?:--data|@-|-d\s+@)",
    r"curl\s+.*-T\s+\S+",
    # Backdoor-ish one-liners
    r"bash\s+-i\s+>&\s*/dev/tcp/",
    r"sh\s+-i\s+>&\s*/dev/tcp/",
    r"python\s+-c\s+.*socket.*subprocess",
    r"python3\s+-c\s+.*socket.*subprocess",
    # System-wide kills
    r"kill\s+-9\s+-1",
    r"killall\s+-9",
    r"pkill\s+-9",
    # Mount manipulation
    r"mount\s+-o\s+remount",
    r"umount\s+/",
    # History wiping
    r"history\s+-c",
    r"cat\s+/dev/null\s*>\s*~/\.bash_history",
    r">\s*~/\.bash_history",
]


def _is_bash_safe(command: str) -> tuple[bool, str]:
    """Check if a bash command passes the safety filter.

    Returns (is_safe, reason_if_unsafe).
    """
    cmd_lower = command.lower().strip()
    for pattern in _BASH_BLOCKED_PATTERNS:
        if re.search(pattern, cmd_lower):
            return False, f"Blocked dangerous pattern: {pattern[:60]}..."
    return True, ""


# ── RTK (Rust Token Killer) integration ──────────────────────────────────
# Transparently rewrites covered commands (ls, grep, git, find, diff, read…)
# via `rtk rewrite` so model-issued commands always emit token-optimized
# output. Soft-fallback: missing binary, disabled flag, or rewrite failure
# all leave the command unchanged.

_rtk_binary_cache: Optional[str] = None
_rtk_binary_resolved = False


def _rtk_binary() -> Optional[str]:
    global _rtk_binary_cache, _rtk_binary_resolved
    if _rtk_binary_resolved:
        return _rtk_binary_cache

    import sys as _sys
    import shutil as _shutil

    here = Path(__file__).resolve().parent
    name = "rtk.exe" if _sys.platform == "win32" else "rtk"
    candidates = [here / "rtk" / name]
    candidates.append(Path.home() / ".local" / "bin" / name)

    for c in candidates:
        if c.exists() and c.is_file():
            _rtk_binary_cache = str(c)
            _rtk_binary_resolved = True
            return _rtk_binary_cache

    _rtk_binary_cache = _shutil.which(name)
    _rtk_binary_resolved = True
    return _rtk_binary_cache


def _rtk_enabled() -> bool:
    if not load_config:
        return False
    try:
        return bool(load_config().get("rtk_enabled", False))
    except Exception:
        return False


def _ensure_rtk_in_path() -> None:
    """Add the bundled rtk binary's directory to PATH so subshells resolve `rtk`.

    Idempotent: re-checks PATH each call (flag may flip at runtime).
    """
    if not _rtk_enabled():
        return
    binary = _rtk_binary()
    if not binary:
        return
    rtk_dir = str(Path(binary).parent)
    current = os.environ.get("PATH", "")
    if rtk_dir not in current.split(os.pathsep):
        os.environ["PATH"] = rtk_dir + os.pathsep + current


def _rtk_wrap_cmd(cmd: list) -> list:
    """Prepend the rtk binary so a subprocess argv list runs through rtk.

    Used by tools that shell out directly via subprocess (GitStatus/Log/Diff,
    Grep). For RTK-supported subcommands (git, grep, ls, find, diff, log, …)
    this gets you token-optimized output; unsupported commands pass through.
    Soft-fallback: returns cmd unchanged when rtk is disabled or missing.
    """
    if not _rtk_enabled() or not cmd:
        return cmd
    binary = _rtk_binary()
    if not binary:
        return cmd
    return [binary, *cmd]


def _maybe_rewrite_with_rtk(command: str) -> str:
    if not _rtk_enabled():
        return command
    binary = _rtk_binary()
    if not binary:
        return command
    try:
        r = subprocess.run(
            [binary, "rewrite", command],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5,
        )
        rewritten = (r.stdout or "").strip()
        if rewritten:
            return rewritten
    except Exception:
        pass
    return command


def _bash(command: str, timeout: int = 30) -> str:
    import sys as _sys
    import shutil

    # ── Sandbox check ──
    safe, reason = _is_bash_safe(command)
    if not safe:
        return f"[SANDBOX BLOCKED] {reason}\n\nCommand: {command[:200]}"

    # ── RTK transparent rewrite (token-optimized output) ──
    _ensure_rtk_in_path()
    command = _maybe_rewrite_with_rtk(command)



    # Load shell configuration
    shell_cfg = {"type": "auto", "path": ""}
    if load_config:
        try:
            cfg = load_config()
            shell_cfg.update(cfg.get("shell", {}))
        except Exception:
            pass

    cwd = os.getcwd()

    if _sys.platform == "win32":
        shell_type = shell_cfg.get("type", "auto")
        forced_path = shell_cfg.get("path", "")

        # Determine shell to use
        if shell_type == "auto":
            shell_info = _find_windows_bash()
        elif shell_type == "custom" and forced_path and Path(forced_path).exists():
            # Custom shell with explicit path
            shell_info = ("custom", forced_path)
        elif forced_path and Path(forced_path).exists():
            # User forced a specific shell path with known type
            shell_info = (shell_type, forced_path)
        else:
            # Try to find the specified shell type
            shell_info = _find_shell_by_type(shell_type, forced_path)

        if shell_info:
            kind, path = shell_info
            import time; time.sleep(0.5)  # Small stabilization delay for Windows shells
            if kind == "gitbash":
                posix_cwd  = _win_to_posix(cwd)
                args = [path, "-c", f"cd {posix_cwd!r} && {command}"]
                kwargs = dict(shell=False, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              encoding='utf-8', errors='replace')
            elif kind == "wsl":
                posix_cwd = _win_to_posix(cwd, wsl=True)
                args = ["wsl", "--", "bash", "-c",
                        f"cd {posix_cwd!r} && {command}"]
                kwargs = dict(shell=False, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              encoding='utf-8', errors='replace')
            elif kind == "powershell":
                # PowerShell execution
                args = [path, "-NoProfile", "-Command", f"cd '{cwd}'; {command}"]
                kwargs = dict(shell=False, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              encoding='utf-8', errors='replace')
            elif kind == "cmd":
                # CMD execution
                args = [path, "/c", f"cd /d {cwd} && {command}"]
                kwargs = dict(shell=False, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              encoding='utf-8', errors='replace')
            elif kind == "custom":
                # Custom shell - try to be smart about the command format
                # Most shells accept -c for commands, but we'll try different approaches
                cmd_lower = command.lower().strip()
                # Check if it looks like a Windows command (uses Windows paths, backslashes, etc.)
                looks_like_windows = (
                    '\\' in command or
                    'dir ' in cmd_lower or
                    'echo %' in cmd_lower or
                    '.exe' in cmd_lower or
                    'C:' in command or
                    'D:' in command
                )
                if looks_like_windows:
                    # Treat as Windows command - pass to shell's -c
                    args = [path, "-c", command]
                else:
                    # Treat as Unix-style command
                    args = [path, "-c", command]
                kwargs = dict(shell=False, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, 
                              encoding='utf-8', errors='replace', cwd=cwd)
            else:
                # Fallback to shell=True with system default
                args = command
                kwargs = dict(shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, 
                              encoding='utf-8', errors='replace', cwd=cwd)
        else:
            # No shell found, use system default
            args = command
            kwargs = dict(shell=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, 
                          encoding='utf-8', errors='replace', cwd=cwd)
    else:
        # Unix/Linux/Mac - use configured shell or default
        forced_path = shell_cfg.get("path", "")
        if forced_path and Path(forced_path).exists():
            args = [forced_path, "-c", command]
            kwargs = dict(shell=False, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, 
                          encoding='utf-8', errors='replace', cwd=cwd)
        else:
            args = command
            kwargs = dict(shell=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True,
                          encoding='utf-8', errors='replace',
                          cwd=cwd, start_new_session=True)

    try:
        proc = subprocess.Popen(args, **kwargs)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_proc_tree(proc.pid)
            proc.wait()
            return f"Error: timed out after {timeout}s (process killed)"
        out = stdout
        if stderr:
            # Strip rtk hook-status warnings (noise — already rate-limited by rtk to 1x/day)
            stderr = "\n".join(
                ln for ln in stderr.splitlines()
                if "[rtk]" not in ln or "hook" not in ln.lower()
            ).strip()
            if stderr:
                out += ("\n" if out else "") + "[stderr]\n" + stderr
        return out.strip() or "(no output)"
    except Exception as e:
        return f"Error: {e}"


def _glob(pattern: str, path: str = None) -> str:
    # pathlib's Path.glob() rejects absolute patterns ("Non-relative patterns
    # are unsupported"). If the model passes an absolute pattern, split it
    # into the longest non-glob prefix (base) + the rest (relative pattern).
    p = Path(pattern)
    if p.is_absolute() or any(c in pattern for c in (":\\", ":/")):
        parts = p.parts
        split_idx = len(parts)
        for i, part in enumerate(parts):
            if any(ch in part for ch in "*?["):
                split_idx = i
                break
        base = Path(*parts[:split_idx]) if split_idx > 0 else Path(p.anchor)
        rel_pattern = str(Path(*parts[split_idx:])) if split_idx < len(parts) else "*"
        if path:
            base = Path(path)
    else:
        base = Path(path) if path else Path.cwd()
        rel_pattern = pattern
    try:
        matches = sorted(base.glob(rel_pattern))
        if not matches:
            return "No files matched"
        return "\n".join(str(m) for m in matches[:500])
    except Exception as e:
        return f"Error: {e}"


def _has_rg() -> bool:
    try:
        subprocess.run(["rg", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _grep_python_pure(pattern: str, search_path: Path, glob_pat: str = None,
                      output_mode: str = "files_with_matches",
                      case_insensitive: bool = False, context: int = 0) -> str:
    """Pure-Python grep fallback for Windows or when grep/rg misbehave."""
    import re, fnmatch
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return f"Error: invalid regex pattern: {e}"

    results = []
    files_to_search = []

    if search_path.is_file():
        files_to_search.append(search_path)
    elif search_path.is_dir():
        for root, _dirs, files in os.walk(search_path):
            for fname in files:
                if glob_pat and not fnmatch.fnmatch(fname, glob_pat):
                    continue
                files_to_search.append(Path(root) / fname)
    else:
        return f"Error: path not found: {search_path}"

    for fp in files_to_search:
        try:
            text = fp.read_text("utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        file_results = []
        for i, line in enumerate(lines, start=1):
            if compiled.search(line):
                if output_mode == "files_with_matches":
                    results.append(str(fp))
                    break
                elif output_mode == "count":
                    file_results.append(1)
                else:
                    # content mode with optional context
                    start_ctx = max(0, i - context - 1)
                    end_ctx = min(len(lines), i + context)
                    ctx_lines = lines[start_ctx:end_ctx]
                    ctx_nums = list(range(start_ctx + 1, end_ctx + 1))
                    for ln_num, ln_text in zip(ctx_nums, ctx_lines):
                        marker = ":" if ln_num == i else "-"
                        file_results.append(f"{fp}:{ln_num}{marker}{ln_text}")
        if output_mode == "count" and file_results:
            results.append(f"{fp}:{len(file_results)}")
        elif output_mode == "content" and file_results:
            results.extend(file_results)

    if not results:
        return "No matches found"
    out = "\n".join(results)
    return out[:20000]


def _grep(pattern: str, path: str = None, glob: str = None,
          output_mode: str = "files_with_matches",
          case_insensitive: bool = False, context: int = 0) -> str:
    # Guard against empty pattern (model sometimes passes it by mistake)
    if not pattern or not pattern.strip():
        return "Error: pattern is required and cannot be empty."

    search_path = Path(path) if path else Path.cwd()
    if not search_path.exists():
        return f"Error: path not found: {search_path}"

    use_rg = _has_rg()
    # On Windows without ripgrep, use pure Python to avoid path/quote hell
    if not use_rg and os.name == "nt":
        return _grep_python_pure(pattern, search_path, glob, output_mode, case_insensitive, context)

    cmd = ["rg" if use_rg else "grep"]
    if use_rg:
        cmd.append("--no-heading")
    if case_insensitive:
        cmd.append("-i")
    if output_mode == "files_with_matches":
        cmd.append("-l")
    elif output_mode == "count":
        cmd.append("-c")
    else:
        cmd.append("-n")
        if context:
            cmd += ["-C", str(context)]
    if glob:
        cmd += (["--glob", glob] if use_rg else ["--include", glob])
    # grep needs -r for directories (rg handles both automatically)
    if not use_rg and search_path.is_dir():
        cmd.append("-r")
    cmd.append(pattern)
    cmd.append(str(search_path))
    try:
        r = subprocess.run(_rtk_wrap_cmd(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if r.returncode != 0 and r.returncode != 1:
            err = r.stderr.strip() if r.stderr else f"exit code {r.returncode}"
            # If grep choked on path/regex, fall back to pure Python
            if "No such file" in err or "Is a directory" in err or "invalid regular expression" in err.lower():
                return _grep_python_pure(pattern, search_path, glob, output_mode, case_insensitive, context)
            return f"Error: {err}"
        out = r.stdout.strip()
        return out[:20000] if out else "No matches found"
    except Exception as e:
        return _grep_python_pure(pattern, search_path, glob, output_mode, case_insensitive, context)




def _libretranslate_host() -> str:
    """Return the best LibreTranslate host URL.
    In WSL2, localhost points to the WSL VM — use the Windows host IP instead
    (read from /etc/resolv.conf nameserver line).
    Falls back to localhost if not in WSL or can't parse."""
    try:
        from pathlib import Path as _P
        resolv = _P("/etc/resolv.conf")
        if resolv.exists():
            for line in resolv.read_text().splitlines():
                if line.startswith("nameserver"):
                    ip = line.split()[1].strip()
                    return f"http://{ip}:5000"
    except Exception:
        pass
    return "http://localhost:5000"


def _clean_html(html: str) -> str:
    """Extract content text from HTML — only meaningful tags, strips noise."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove noise tags entirely
        for junk in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
            junk.decompose()
            
        # Get all remaining text content
        text = soup.get_text(separator=" ")
        
        # Clean up horizontal whitespace but preserve double newlines for structure
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)
    except Exception:
        return html[:5000] # Fallback to raw-ish if soup fails


def _libretranslate(text: str, source: str, target: str,
                    host: str = None) -> str | None:
    """Translate via LibreTranslate (local). Returns None if unavailable.
    Splits into 800-char chunks to stay within API limits."""
    host = host or _libretranslate_host()
    try:
        import httpx
        chunks, out = [], []
        for i in range(0, len(text), 800):
            chunks.append(text[i:i+800])
        for chunk in chunks:
            # LibreTranslate expects multipart/form-data, not JSON
            payload = {"q": chunk, "source": source, "target": target,
                       "format": "text"}
            _lt_key = os.environ.get("LIBRETRANSLATE_API_KEY")
            if _lt_key:
                payload["api_key"] = _lt_key
            r = httpx.post(f"{host}/translate", data=payload, timeout=15)
            if r.status_code != 200:
                return None
            out.append(r.json().get("translatedText", chunk))
        return "".join(out)
    except Exception:
        return None


def _libretranslate_available() -> bool:
    host = _libretranslate_host()
    try:
        import httpx
        r = httpx.get(f"{host}/languages", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _webfetch(url: str) -> str:
    """Fetch URL → plain text.
    """
    try:
        from pathlib import Path

        # ── Fetch ──────────────────────────────────────────────────────────
        if url.startswith("file://"):
            fp = Path(url[7:])
            if not fp.exists():
                return f"Error: Local file not found: {url[7:]}"
            text = fp.read_text(encoding="utf-8", errors="replace")
        else:
            import requests
            r = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }, timeout=30, allow_redirects=True)
            r.raise_for_status()
            
            # Ensure proper encoding
            if r.encoding is None or r.encoding == 'ISO-8859-1':
                r.encoding = r.apparent_encoding
                
            text = r.text
            ct = r.headers.get("content-type", "").lower()
            if "html" in ct:
                text = _clean_html(text)


        # ── Normal path ────────────────────────────────────────────────────
        return text[:25000]

    except ImportError:
        return "Error: httpx not installed — run: pip install httpx"
    except Exception as e:
        return f"Error: {e}"


def _bravesearch(query: str, api_key: str, country: str = None) -> str:
    """Search using Brave Search API."""
    try:
        import requests
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key
        }
        params = {"q": query}
        if country:
            params["country"] = country.strip().lower()
            
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code != 200:
            return f"Error: Brave Search API returned {r.status_code}: {r.text[:200]}"
        
        data = r.json()
        results = []
        # Brave Search API returns results in 'web.results'
        for res in data.get("web", {}).get("results", [])[:10]:
            title = res.get("title", "")
            href = res.get("url", "")
            desc = res.get("description", "")
            if title and href:
                results.append(f"{title}\n{href}\n{desc}")
        
        return "\n\n".join(results[:8]) if results else "No results found"
    except Exception as e:
        return f"Error: Brave Search failed: {e}"


def _websearch(query: str, config: dict = None, region: str = None) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import unquote, urlparse, parse_qs

        # Determine region (priority: tool call param > config > None)
        active_region = region or (config.get("search_region") if config else None)

        # ── Brave Search Fallback ───────────────────────────────────────────────
        if config and config.get("brave_search_enabled") and config.get("brave_search_key"):
            # Brave uses 2-letter country code (e.g. 'do', 'us', 'mx')
            cc = active_region.split("-")[0] if active_region else None
            return _bravesearch(query, config["brave_search_key"], country='ALL')

        # User-provided stealth headers (Firefox 150 style)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "DNT": "1",
        }

        # Try HTML POST version first
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query}
        if active_region:
            data["kl"] = active_region # DDG uses codes like 'do-es', 'us-en'
            
        r = requests.post(url, headers=headers, data=data, timeout=30)
        
        # If challenged (202), fallback to Lite GET version
        if r.status_code == 202:
            lite_url = f"https://duckduckgo.com/lite/?q={requests.utils.quote(query)}"
            if active_region:
                lite_url += f"&kl={active_region}"
            r = requests.get(lite_url, headers=headers, timeout=30)

        if r.status_code != 200:
            return f"Error: HTTP {r.status_code}"

        soup = BeautifulSoup(r.text, "html.parser")
        results = []

        # Parse results (selectors differ slightly between html and lite, but .result__a is common)
        for link in soup.select("a.result__a")[:10]:
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not href or not title or len(title) < 3:
                continue

            if "uddg=" in href:
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                real_urls = qs.get("uddg", [])
                if real_urls:
                    href = unquote(real_urls[0])

            if "duckduckgo.com" in href and "uddg" not in href:
                continue

            results.append(f"{title}\n{href}")

        return "\n\n".join(results[:8]) if results else "No results found"
    except ImportError as e:
        return f"Error: {e} — run: pip install requests beautifulsoup4"
    except Exception as e:
        return f"Error: {e}"


# ── NotebookEdit implementation ────────────────────────────────────────────

def _parse_cell_id(cell_id: str) -> int | None:
    """Convert 'cell-N' shorthand to integer index; return None if not that form."""
    m = re.fullmatch(r"cell-(\d+)", cell_id)
    return int(m.group(1)) if m else None


def _notebook_edit(
    notebook_path: str,
    new_source: str,
    cell_id: str = None,
    cell_type: str = None,
    edit_mode: str = "replace",
) -> str:
    p = Path(notebook_path)
    if p.suffix != ".ipynb":
        return "Error: file must be a Jupyter notebook (.ipynb)"
    if not p.exists():
        return f"Error: notebook not found: {notebook_path}"

    try:
        nb = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return f"Error: notebook is not valid JSON: {e}"

    cells = nb.get("cells", [])

    # Resolve cell index
    def _resolve_index(cid: str) -> int | None:
        # Try exact id match first
        for i, c in enumerate(cells):
            if c.get("id") == cid:
                return i
        # Fallback: cell-N
        idx = _parse_cell_id(cid)
        if idx is not None and 0 <= idx < len(cells):
            return idx
        return None

    if edit_mode == "replace":
        if not cell_id:
            return "Error: cell_id is required for replace"
        idx = _resolve_index(cell_id)
        if idx is None:
            return f"Error: cell '{cell_id}' not found"
        target = cells[idx]
        target["source"] = new_source
        if cell_type and cell_type != target.get("cell_type"):
            target["cell_type"] = cell_type
        if target.get("cell_type") == "code":
            target["execution_count"] = None
            target["outputs"] = []

    elif edit_mode == "insert":
        if not cell_type:
            return "Error: cell_type is required for insert ('code' or 'markdown')"
        # Determine nb format for cell ids
        nbformat = nb.get("nbformat", 4)
        nbformat_minor = nb.get("nbformat_minor", 0)
        use_ids = nbformat > 4 or (nbformat == 4 and nbformat_minor >= 5)
        new_id = None
        if use_ids:
            import random, string
            new_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

        if cell_type == "markdown":
            new_cell = {"cell_type": "markdown", "source": new_source, "metadata": {}}
        else:
            new_cell = {
                "cell_type": "code",
                "source": new_source,
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            }
        if use_ids and new_id:
            new_cell["id"] = new_id

        if cell_id:
            idx = _resolve_index(cell_id)
            if idx is None:
                return f"Error: cell '{cell_id}' not found"
            cells.insert(idx + 1, new_cell)
        else:
            cells.insert(0, new_cell)
        nb["cells"] = cells
        cell_id = new_id or cell_id

    elif edit_mode == "delete":
        if not cell_id:
            return "Error: cell_id is required for delete"
        idx = _resolve_index(cell_id)
        if idx is None:
            return f"Error: cell '{cell_id}' not found"
        cells.pop(idx)
        nb["cells"] = cells
        p.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
        return f"Deleted cell '{cell_id}' from {notebook_path}"
    else:
        return f"Error: unknown edit_mode '{edit_mode}' — use replace, insert, or delete"

    nb["cells"] = cells
    p.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    return f"NotebookEdit({edit_mode}) applied to cell '{cell_id}' in {notebook_path}"


# ── GetDiagnostics implementation ──────────────────────────────────────────

def _detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {
        ".py":   "python",
        ".js":   "javascript",
        ".mjs":  "javascript",
        ".cjs":  "javascript",
        ".ts":   "typescript",
        ".tsx":  "typescript",
        ".sh":   "shellscript",
        ".bash": "shellscript",
        ".zsh":  "shellscript",
    }.get(ext, "unknown")


def _run_quietly(cmd: list[str], cwd: str | None = None, timeout: int = 30) -> tuple[int, str]:
    """Run a command, return (returncode, combined_output)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=cwd or os.getcwd(),
        )
        out = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip()
        return r.returncode, out
    except FileNotFoundError:
        return -1, f"(command not found: {cmd[0]})"
    except subprocess.TimeoutExpired:
        return -1, f"(timed out after {timeout}s)"
    except Exception as e:
        return -1, f"(error: {e})"


def _get_diagnostics(file_path: str, language: str = None) -> str:
    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"

    lang = language or _detect_language(file_path)
    abs_path = str(p.resolve())
    results: list[str] = []

    if lang == "python":
        # Try pyright first (most comprehensive)
        rc, out = _run_quietly(["pyright", "--outputjson", abs_path])
        if rc != -1:
            try:
                data = json.loads(out)
                diags = data.get("generalDiagnostics", [])
                if not diags:
                    results.append("pyright: no diagnostics")
                else:
                    lines = [f"pyright ({len(diags)} issue(s)):"]
                    for d in diags[:50]:
                        rng = d.get("range", {}).get("start", {})
                        ln = rng.get("line", 0) + 1
                        ch = rng.get("character", 0) + 1
                        sev = d.get("severity", "error")
                        msg = d.get("message", "")
                        rule = d.get("rule", "")
                        lines.append(f"  {ln}:{ch} [{sev}] {msg}" + (f" ({rule})" if rule else ""))
                    results.append("\n".join(lines))
            except json.JSONDecodeError:
                if out:
                    results.append(f"pyright:\n{out[:3000]}")
        else:
            # Try mypy
            rc2, out2 = _run_quietly(["mypy", "--no-error-summary", abs_path])
            if rc2 != -1:
                results.append(f"mypy:\n{out2[:3000]}" if out2 else "mypy: no diagnostics")
            else:
                # Fall back to flake8
                rc3, out3 = _run_quietly(["flake8", abs_path])
                if rc3 != -1:
                    results.append(f"flake8:\n{out3[:3000]}" if out3 else "flake8: no diagnostics")
                else:
                    # Last resort: py_compile syntax check
                    rc4, out4 = _run_quietly(["python3", "-m", "py_compile", abs_path])
                    if out4:
                        results.append(f"py_compile (syntax check):\n{out4}")
                    else:
                        results.append("py_compile: syntax OK (no further tools available)")

    elif lang in ("javascript", "typescript"):
        # Try tsc
        rc, out = _run_quietly(["tsc", "--noEmit", "--strict", abs_path])
        if rc != -1:
            results.append(f"tsc:\n{out[:3000]}" if out else "tsc: no errors")
        else:
            # Try eslint
            rc2, out2 = _run_quietly(["eslint", abs_path])
            if rc2 != -1:
                results.append(f"eslint:\n{out2[:3000]}" if out2 else "eslint: no issues")
            else:
                results.append("No TypeScript/JavaScript checker found (install tsc or eslint)")

    elif lang == "shellscript":
        rc, out = _run_quietly(["shellcheck", abs_path])
        if rc != -1:
            results.append(f"shellcheck:\n{out[:3000]}" if out else "shellcheck: no issues")
        else:
            # Basic bash syntax check
            rc2, out2 = _run_quietly(["bash", "-n", abs_path])
            results.append(f"bash -n (syntax check):\n{out2}" if out2 else "bash -n: syntax OK")

    else:
        results.append(f"No diagnostic tool available for language: {lang or 'unknown'} (ext: {Path(file_path).suffix})")

    return "\n\n".join(results) if results else "(no diagnostics output)"


# ── AskUserQuestion implementation ────────────────────────────────────────

def _ask_user_question(
    question: str,
    options: list[dict] | None = None,
    allow_freetext: bool = True,
    config: dict = None,
) -> str:
    """
    Block the agent loop and surface a question to the user in the terminal.
    """
    event = threading.Event()
    result_holder: list[str] = []
    entry = {
        "question": question,
        "options": options or [],
        "allow_freetext": allow_freetext,
        "event": event,
        "result": result_holder,
    }
    with _ask_lock:
        _pending_questions.append(entry)

    if threading.current_thread() is threading.main_thread() or _is_in_tg_turn(config or {}):
        # Prevent deadlock: we are blocking the main loop generator, 
        # so we must drain it ourselves synchronously!
        drain_pending_questions(config or {})
        return result_holder[0] if result_holder else "(no answer)"

    # Block until the REPL answers us (for background agents)
    event.wait(timeout=300)  # 5-minute max wait

    if result_holder:
        return result_holder[0]
    return "(no answer - timeout)"


def ask_input_interactive(prompt: str, config: dict, menu_text: str = None) -> str:
    """Prompt the user for input, routing to Telegram if in a Telegram turn.
    If menu_text is provided, it is sent ahead of the prompt."""
    is_tg = _is_in_tg_turn(config)
    if is_tg and "_tg_send_callback" in config:
        token = config.get("telegram_token")
        # Reply to the user who triggered the current TG turn (multi-user support).
        chat_id = config.get("_active_tg_chat_id") or config.get("telegram_chat_id")
        import re, threading
        clean_prompt = re.sub(r'\x1b\[[0-9;]*m', '', prompt).strip()

        payload = ""
        if menu_text:
            clean_menu = re.sub(r'\x1b\[[0-9;]*m', '', menu_text).strip()
            payload += f"{clean_menu}\n\n"
        payload += f"*Input Required*\n{clean_prompt}"

        evt = threading.Event()
        config["_tg_input_event"] = evt

        config["_tg_send_callback"](token, chat_id, payload)

        config["_tg_pause_typing"] = True
        evt.wait()
        config["_tg_pause_typing"] = False

        text = config.pop("_tg_input_value", "").strip()
        config.pop("_tg_input_event", None)
        return text
    else:
        try:
            # Use prompt_toolkit with autocomplete if available, otherwise fall back to input()
            if HAS_PROMPT_TOOLKIT and input_setup:
                # Setup input with command and metadata autocomplete providers
                # Providers must be CALLABLES that return dicts (not the dicts themselves!)
                commands_provider = lambda: dict(COMMANDS)
                meta_provider = lambda: dict(_CMD_META)
                input_setup(commands_provider, meta_provider)
                
                # Call the read_line function from input module (not readline)
                # prompt_toolkit handles ANSI escapes natively, no need for \001/\002 markers
                if read_line:
                    return read_line(prompt)
                else:
                    # Fallback to input() if read_line is not available
                    import re as _re
                    safe = _re.sub(r'(\033\[[0-9;]*m)', r'\001\1\002', prompt)
                    return input(safe)
            else:
                # Fallback to standard input()
                import re as _re
                safe = _re.sub(r'(\033\[[0-9;]*m)', r'\001\1\002', prompt)
                return input(safe)
        except (KeyboardInterrupt, EOFError):
            print()
            return ""

def drain_pending_questions(config: dict) -> bool:
    """
    Called by the REPL loop after each streaming turn.
    Renders pending questions and collects user input.
    Returns True if any questions were answered.
    """
    with _ask_lock:
        pending = list(_pending_questions)
        _pending_questions.clear()

    if not pending:
        return False

    # Temporarily restore the real stdout/stderr for the entire drain so that
    # both print() and input() (used by ask_input_interactive) go to the
    # terminal and not into any redirect_stdout() buffer from execute_tool.
    import sys as _sys
    _saved_out = _sys.stdout
    _saved_err = _sys.stderr
    _sys.stdout = _sys.__stdout__
    _sys.stderr = _sys.__stderr__

    for entry in pending:
        question = entry["question"]
        options  = entry["options"]
        allow_ft = entry["allow_freetext"]
        event    = entry["event"]
        result   = entry["result"]

        print()
        print(clr("Question from assistant:", "magenta", "bold"))
        print(f"   {question}")

        if options:
            menu_lines = [question, ""]
            for i, opt in enumerate(options, 1):
                label = opt.get("label", "")
                desc  = opt.get("description", "")
                line  = f"[{i}] {label}"
                if desc:
                    line += f" — {desc}"
                menu_lines.append(line)
                print(f"  {line}")
            if allow_ft:
                menu_lines.append("[0] Type a custom answer")
                print("  [0] Type a custom answer")
            print()
            menu_text = "\n".join(menu_lines)

            while True:
                raw = ask_input_interactive("  ❯ ", config, menu_text=menu_text).strip()
                if not raw:
                    break

                if raw.isdigit():
                    idx = int(raw)
                    if 1 <= idx <= len(options):
                        raw = options[idx - 1]["label"]
                        break
                    elif idx == 0 and allow_ft:
                        raw = ask_input_interactive("  ❯ ", config, menu_text=question).strip()
                        break
                    else:
                        print(f"Invalid option: {idx}")
                        raw = ""
                        continue
                elif allow_ft:
                    break  # accept free text directly
        else:
            # Free-text only
            print()
            raw = ask_input_interactive("  ❯ ", config, menu_text=question).strip()

        result.append(raw)
        event.set()


    _sys.stdout = _saved_out
    _sys.stderr = _saved_err

    return True


def _sleeptimer(seconds: int, config: dict) -> str:
    # Fire-and-forget background timer. Countdown starts NOW. If the model
    # needs to pause mid-tool-chain (e.g. between two bash calls), it should
    # use `Bash('sleep N')` inside the command instead — Reminder is meant
    # for scheduling a deferred wake-up notification (e.g. "remind me in
    # 10 minutes to check the deploy"), not for pacing tool execution.
    import threading
    cb = config.get("_run_query_callback")
    if not cb:
        return "Error: Internal callback missing, dulus did not provide _run_query_callback"

    def worker():
        import time
        time.sleep(seconds)
        cb("(System Automated Event): The reminder has fired. Please wake up, perform any pending monitoring checks and report to the user now.")

    threading.Thread(target=worker, daemon=True, name=f"reminder-{seconds}s").start()
    return f"Reminder scheduled for {seconds}s. End your turn silently and wait for the system wake-up — do NOT keep calling tools. If you needed a short pause BETWEEN tools, use Bash('sleep N') instead."


def _print_to_console(content: str = "", style: str = "normal", prefix: str = "", from_line: int = None, to_line: int = None, file_path: str = None, config: dict = None) -> str:
    """Print content to the user's console.
    
    This tool displays text to the user WITHOUT consuming output tokens.
    The content is shown immediately in the chat console.
    If the conversation started via Telegram, also sends to Telegram.
    
    Args:
        content: Text to display (or use file_path to read from file)
        style: Visual style (normal, success, info, warning, error)
        prefix: Optional prefix to identify the source
        from_line: Extract content starting from this line (1-indexed)
        to_line: Extract content up to this line (inclusive)
        file_path: Path to file to read and display (alternative to content)
        config: Optional config dict for Telegram integration
    
    Returns:
        The formatted content that was displayed (possibly extracted to specific lines)
    """
    import sys
    from pathlib import Path
    
    # If file_path provided, read from file
    if file_path:
        try:
            fp = Path(file_path)
            # Special case: last_tool_output.txt is usually in the app config dir (~/.dulus)
            if file_path == "last_tool_output.txt" and not fp.exists():
                # Cross-platform home directory resolution
                fp = Path.home() / ".dulus" / "last_tool_output.txt"
                
            if not fp.exists():
                return f"[ERROR] File not found: {file_path}"
            content = fp.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return f"[ERROR] Could not read file: {e}"
    
    # Extract specific lines if requested
    if from_line is not None or to_line is not None:
        lines = content.split('\n')
        total_lines = len(lines)
        
        # Default values
        start = (from_line - 1) if from_line else 0  # Convert to 0-indexed
        end = to_line if to_line else total_lines
        
        # Clamp to valid range
        start = max(0, min(start, total_lines))
        end = max(0, min(end, total_lines))
        
        # Extract lines
        if start < end:
            extracted = lines[start:end]
            content = '\n'.join(extracted)
            # Add info about extraction
            prefix_info = f"[LINES {start+1}-{end} of {total_lines}] "
        else:
            content = "[No lines in specified range]"
            prefix_info = ""
    else:
        prefix_info = ""
    
    # Build styled output (ASCII-friendly para Windows)
    style_prefixes = {
        "success": "[OK] ",
        "info": "[i] ",
        "warning": "[!] ",
        "error": "[X] ",
        "normal": "",
    }
    
    # Build output
    style_indicator = style_prefixes.get(style, "")
    
    # Add user-provided prefix
    full_prefix = f"[{prefix}] " if prefix else ""
    
    # Build the visible output with extraction info if applicable
    output = f"{prefix_info}{full_prefix}{style_indicator}{content}"
    
    # ALSO print to server log for debugging
    print(f"[PrintToConsole] {len(content)} chars displayed")
    
    # If in Telegram turn, also send to Telegram
    if config and _is_in_tg_turn(config):
        token = config.get("telegram_token")
        chat_id = config.get("_active_tg_chat_id") or config.get("telegram_chat_id")
        if token and chat_id and "_tg_send_callback" in config:
            import re
            # Clean ANSI codes and send
            clean_output = re.sub(r'\x1b\[[0-9;]*m', '', output).strip()
            if clean_output:
                try:
                    config["_tg_send_callback"](token, chat_id, clean_output)
                except Exception:
                    pass  # Fail silently if Telegram send fails
    
    # Return the content so it shows in the tool result to the user
    return output


# ── Dispatcher (backward-compatible wrapper) ──────────────────────────────

def execute_tool(
    name: str,
    inputs: dict,
    permission_mode: str = "auto",
    ask_permission: Optional[Callable[[str], bool]] = None,
    config: dict = None,
) -> str:
    """Dispatch tool execution; ask permission for write/destructive ops.

    Permission checking is done here, then delegation goes to the registry.
    The config dict is forwarded to tool functions so they can access
    runtime context like _depth, _system_prompt, model, etc.
    """
    cfg = config or {}

    def _check(desc: str) -> bool:
        """Return True if action is allowed."""
        if permission_mode == "accept-all":
            return True
        if ask_permission:
            return ask_permission(desc)
        return True  # headless: allow everything

    # --- permission gate ---
    if name == "Write":
        if not _check(f"Write to {inputs['file_path']}"):
            return "Denied: user rejected write operation"
    elif name == "Edit":
        fp = inputs.get("file_path", inputs.get("filePath", "<unknown>"))
        if not _check(f"Edit {fp}"):
            return "Denied: user rejected edit operation"
    elif name == "Bash":
        cmd = inputs["command"]
        if permission_mode != "accept-all" and not _is_safe_bash(cmd):
            if not _check(f"Bash: {cmd}"):
                return "Denied: user rejected bash command"
    elif name == "NotebookEdit":
        if not _check(f"Edit notebook {inputs['notebook_path']}"):
            return "Denied: user rejected notebook edit operation"

    return _registry_execute(name, inputs, cfg, max_output=cfg.get("max_tool_output", 2500))


# ── Register built-in tools with the plugin registry ─────────────────────

def _register_builtins() -> None:
    """Register all built-in tools into the central registry."""
    # Use a name → schema map so ordering changes in TOOL_SCHEMAS never break this.
    _schemas = {s["name"]: s for s in TOOL_SCHEMAS}

    _tool_defs = [
        ToolDef(
            name="Read",
            schema=_schemas["Read"],
            func=lambda p, c: _read(**p),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="Write",
            schema=_schemas["Write"],
            func=lambda p, c: _write(**p),
            read_only=False,
            concurrent_safe=False,
        ),
        ToolDef(
            name="Edit",
            schema=_schemas["Edit"],
            func=lambda p, c: _edit(**p),
            read_only=False,
            concurrent_safe=False,
        ),
        ToolDef(
            name="Bash",
            schema=_schemas["Bash"],
            func=lambda p, c: _bash(p["command"], p.get("timeout", 30)),
            read_only=False,
            concurrent_safe=False,
        ),
        ToolDef(
            name="Glob",
            schema=_schemas["Glob"],
            func=lambda p, c: _glob(p["pattern"], p.get("path")),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="Grep",
            schema=_schemas["Grep"],
            func=lambda p, c: _grep(
                p["pattern"], p.get("path"), p.get("glob"),
                p.get("output_mode", "files_with_matches"),
                p.get("case_insensitive", False),
                p.get("context", 0),
            ),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="WebFetch",
            schema=_schemas["WebFetch"],
            func=lambda p, c: _webfetch(p["url"]),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="WebSearch",
            schema=_schemas["WebSearch"],
            func=lambda p, c: _websearch(p["query"], c, region=p.get("region")),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="NotebookEdit",
            schema=_schemas["NotebookEdit"],
            func=lambda p, c: _notebook_edit(
                p["notebook_path"],
                p["new_source"],
                p.get("cell_id"),
                p.get("cell_type"),
                p.get("edit_mode", "replace"),
            ),
            read_only=False,
            concurrent_safe=False,
        ),
        ToolDef(
            name="GetDiagnostics",
            schema=_schemas["GetDiagnostics"],
            func=lambda p, c: _get_diagnostics(
                p["file_path"],
                p.get("language"),
            ),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="LineCount",
            schema=_schemas["LineCount"],
            func=lambda p, c: _line_count(p["file_path"]),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="AskUserQuestion",
            schema=_schemas["AskUserQuestion"],
            func=lambda p, c: _ask_user_question(
                p["question"],
                p.get("options"),
                p.get("allow_freetext", True),
                c,
            ),
            read_only=True,
            concurrent_safe=False,
        ),
        ToolDef(
            name="Reminder",
            schema=_schemas["Reminder"],
            func=lambda p, c: _sleeptimer(p["seconds"], c),
            read_only=False,
            concurrent_safe=True,
        ),
        ToolDef(
            name="SearchLastOutput",
            schema=_schemas["SearchLastOutput"],
            func=lambda p, c: _search_last_output(
                p.get("pattern"), p.get("context", 2),
            ),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="PrintLastOutput",
            schema=_schemas["PrintLastOutput"],
            func=lambda p, c: _print_last_output(),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="PrintToConsole",
            schema=_schemas["PrintToConsole"],
            func=lambda p, c: _print_to_console(
                p.get("content", ""),
                p.get("style", "normal"),
                p.get("prefix", ""),
                p.get("from_line"),
                p.get("to_line"),
                p.get("file_path"),
                c,  # Pass config for Telegram integration
            ),
            read_only=True,
            concurrent_safe=True,
            display_only=True,  # NO TRUNCATION - prints directly to console
        ),
    ]
    for td in _tool_defs:
        register_tool(td)


_register_builtins()

# ── Tmux tools (auto-detected: only registered when tmux is on the system) ───
try:
    from tmux_tools import register_tmux_tools, tmux_available
    _tmux_count = register_tmux_tools()
except ImportError:
    _tmux_count = 0

# ── Memory tools (MemorySave, MemoryDelete, MemorySearch, MemoryList) ────────
# Defined in memory/tools.py; importing registers them automatically.
import memory.tools as _memory_tools  # noqa: F401
from memory.offload import register_offload_tool
register_offload_tool()



# ── Multi-agent tools (Agent, SendMessage, CheckAgentResult, ListAgentTasks, ListAgentTypes) ──
# Defined in multi_agent/tools.py; importing registers them automatically.
import multi_agent.tools as _multiagent_tools  # noqa: F401

# Expose get_agent_manager at module level for backward compatibility
from multi_agent.tools import get_agent_manager as _get_agent_manager  # noqa: F401


# ── Skill tools (Skill, SkillList) ────────────────────────────────────────
# Defined in skill/tools.py; importing registers them automatically.
import skill.tools as _skill_tools  # noqa: F401


# ── MCP tools ─────────────────────────────────────────────────────────────────
# mcp/tools.py connects to configured MCP servers and registers their tools.
# Connection happens in a background thread so startup is not blocked.
import dulus_mcp.tools as _mcp_tools  # noqa: F401


# ── Plugin tools ───────────────────────────────────────────────────────────────
# Load tools contributed by installed+enabled plugins.
try:
    from plugin.loader import register_plugin_tools as _reg_plugin_tools
    _reg_plugin_tools()
except Exception as _plugin_err:
    pass  # Plugin loading is best-effort; never crash startup


# ── Task tools (TaskCreate, TaskUpdate, TaskGet, TaskList) ─────────────────────
# task/tools.py registers all four tools into the central registry on import.
import task.tools as _task_tools  # noqa: F401

# ── WebBridge tools (browser automation via Playwright) ────────────────────────
# webbridge/tools.py registers WebBridgeNavigate, WebBridgeClick, etc.
try:
    import webbridge.tools as _webbridge_tools  # noqa: F401
except Exception:
    pass  # Playwright may not be installed; skip gracefully


# ── Checkpoint hooks (backup files before Write/Edit/NotebookEdit) ───────────
from checkpoint.hooks import install_hooks as _install_checkpoint_hooks
_install_checkpoint_hooks()


# ── Plan mode tools (EnterPlanMode / ExitPlanMode) ──────────────────────────

def _enter_plan_mode(params: dict, config: dict) -> str:
    """Enter plan mode: read-only except plan file."""
    if config.get("permission_mode") == "plan":
        return "Already in plan mode. Write your plan to the plan file, then call ExitPlanMode."

    session_id = config.get("_session_id", "default")
    plans_dir = Path.cwd() / ".dulus-context" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{session_id}.md"

    task_desc = params.get("task_description", "")
    if not plan_path.exists() or plan_path.stat().st_size == 0:
        header = f"# Plan: {task_desc}\n\n" if task_desc else "# Plan\n\n"
        plan_path.write_text(header, encoding="utf-8")

    config["_prev_permission_mode"] = config.get("permission_mode", "auto")
    config["permission_mode"] = "plan"
    config["_plan_file"] = str(plan_path)

    return (
        f"Plan mode activated. You are now in read-only mode.\n"
        f"Plan file: {plan_path}\n\n"
        f"Instructions:\n"
        f"1. Analyze the codebase using Read, Glob, Grep, WebSearch\n"
        f"2. Write your detailed implementation plan to the plan file using Write or Edit\n"
        f"3. When the plan is ready, call ExitPlanMode to request user approval\n"
        f"4. Do NOT attempt to write to any other files — they will be blocked"
    )


def _exit_plan_mode(params: dict, config: dict) -> str:
    """Exit plan mode and present plan for user approval."""
    if config.get("permission_mode") != "plan":
        return "Not in plan mode. Use EnterPlanMode first."

    plan_file = config.get("_plan_file", "")
    plan_content = ""
    if plan_file:
        p = Path(plan_file)
        if p.exists():
            plan_content = p.read_text(encoding="utf-8").strip()

    if not plan_content or plan_content == "# Plan":
        return "Plan file is empty. Write your plan to the plan file before calling ExitPlanMode."

    # Restore permissions
    prev = config.pop("_prev_permission_mode", "auto")
    config["permission_mode"] = prev

    return (
        f"Plan mode exited. Permission mode restored to: {prev}\n"
        f"Plan file: {plan_file}\n\n"
        f"The plan is ready for the user to review. "
        f"Wait for the user to approve before starting implementation.\n\n"
        f"--- Plan Content ---\n{plan_content}"
    )


_PLAN_MODE_SCHEMAS = [
    {
        "name": "EnterPlanMode",
        "description": (
            "Enter plan mode to analyze the codebase and create an implementation plan "
            "before writing code. Use this for complex, multi-file tasks. "
            "In plan mode, only the plan file is writable; all other writes are blocked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Brief description of the task to plan for",
                },
            },
            "required": [],
        },
    },
    {
        "name": "ExitPlanMode",
        "description": (
            "Exit plan mode and present the plan for user approval. "
            "Call this after writing your implementation plan to the plan file. "
            "The user must approve the plan before you begin implementation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

register_tool(ToolDef(
    name="EnterPlanMode",
    schema=_PLAN_MODE_SCHEMAS[0],
    func=_enter_plan_mode,
    read_only=False,
    concurrent_safe=False,
))

register_tool(ToolDef(
    name="ExitPlanMode",
    schema=_PLAN_MODE_SCHEMAS[1],
    func=_exit_plan_mode,
    read_only=False,
    concurrent_safe=False,
))

def _plugin_list(params: dict, config: dict) -> str:
    """Implement the PluginList tool to query installed tools dynamically."""
    try:
        from plugin.store import list_plugins, PluginScope
        plugins = []
        # get both scopes and filter out duplicates if needed, or just list all
        plugins.extend(list_plugins(PluginScope.USER))
        plugins.extend(list_plugins(PluginScope.PROJECT))
        
        # Deduplicate by name and scope
        seen = set()
        unique = []
        for p in plugins:
            uid = f"{p.name}_{p.scope}"
            if uid not in seen:
                seen.add(uid)
                unique.append(p)
                
        names = []
        for p in unique:
            if p.manifest:
                status = "disabled" if not p.enabled else "enabled"
                names.append(f"- {p.name} ({p.scope.value}, {status}): {p.manifest.description}")
        return "Installed Plugins:\n" + ("\n".join(names) if names else "No plugins currently installed.")
    except ImportError:
        return "Error: plugin system not available."
    except Exception as e:
        return f"Error: {e}"

_PLUGIN_LIST_SCHEMA = {
    "name": "PluginList",
    "description": "List all currently installed Dulus plugins, their scopes, and their status (enabled/disabled). Use this if you need to recall which plugins you have available.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# Append to TOOL_SCHEMAS so it gets sent in the system prompt alongside core tools
TOOL_SCHEMAS.append(_PLUGIN_LIST_SCHEMA)

register_tool(ToolDef(
    name="PluginList",
    schema=_PLUGIN_LIST_SCHEMA,
    func=_plugin_list,
    read_only=True,
    concurrent_safe=True,
))


def _plugin_tools_list(params: dict, config: dict) -> str:
    """List all tools exposed by installed plugins."""
    try:
        from plugin.loader import load_all_plugins
        from plugin.types import PluginScope
        import importlib.util
        import sys
        
        plugins = load_all_plugins()
        
        if not plugins:
            return "No plugins installed. Use /plugin install to add plugins."
        
        lines = ["Plugin Tools:", ""]
        total_tools = 0
        
        for entry in plugins:
            if not entry.enabled or not entry.manifest or not entry.manifest.tools:
                continue
                
            plugin_tools = []
            for module_name in entry.manifest.tools:
                # Import the module to get its tools
                plugin_dir_str = str(entry.install_dir)
                if plugin_dir_str not in sys.path:
                    sys.path.insert(0, plugin_dir_str)
                
                unique_name = f"_plugin_{entry.name}_{module_name}"
                try:
                    if unique_name in sys.modules:
                        mod = sys.modules[unique_name]
                    else:
                        candidate = entry.install_dir / f"{module_name}.py"
                        if not candidate.exists():
                            continue
                        spec = importlib.util.spec_from_file_location(unique_name, candidate)
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[unique_name] = mod
                        spec.loader.exec_module(mod)
                    
                    if hasattr(mod, "TOOL_DEFS"):
                        for tdef in mod.TOOL_DEFS:
                            if hasattr(tdef, 'schema'):
                                plugin_tools.append({
                                    "name": tdef.schema.get("name", "unknown"),
                                    "desc": tdef.schema.get("description", "No description")[:60] + "..."
                                })
                except Exception:
                    continue
            
            if plugin_tools:
                lines.append(f"[{entry.name}]")
                for tool in plugin_tools:
                    lines.append(f"  - {tool['name']}: {tool['desc']}")
                lines.append("")
                total_tools += len(plugin_tools)
        
        lines.insert(0, f"Plugin Tools ({total_tools} total from installed plugins):")
        
        return "\n".join(lines) if total_tools > 0 else "No tools available from installed plugins."
    except ImportError:
        return "Error: plugin system not available."
    except Exception as e:
        return f"Error: {e}"


_PLUGIN_TOOLS_LIST_SCHEMA = {
    "name": "PluginToolsList",
    "description": "List all tools exposed by installed Dulus plugins. Returns each plugin's name and the tools it provides with brief descriptions. Use this to discover what plugin tools are available without searching files.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# Append to TOOL_SCHEMAS
TOOL_SCHEMAS.append(_PLUGIN_TOOLS_LIST_SCHEMA)

register_tool(ToolDef(
    name="PluginToolsList",
    schema=_PLUGIN_TOOLS_LIST_SCHEMA,
    func=_plugin_tools_list,
    read_only=True,
    concurrent_safe=True,
))

# ── Auto-register plugin tools on module load ─────────────────────────────────
def _read_job(params: dict, config: dict) -> str:
    """Read a job result by its ID. Simple way to get TmuxOffload results."""
    job_id = params.get("job_id", "").strip()
    pattern = params.get("pattern", "").strip()
    max_lines = params.get("max_lines", 0)  # 0 = no limit
    if not job_id:
        return "Error: job_id is required"
    
    try:
        from pathlib import Path
        import re
        jobs_dir = Path.home() / ".dulus" / "jobs"
        job_file = jobs_dir / f"{job_id}.json"
        
        if not job_file.exists():
            # Try listing available jobs
            available = [f.stem for f in jobs_dir.glob("*.json")] if jobs_dir.exists() else []
            available_str = ", ".join(available[:10]) if available else "No jobs found"
            return f"Error: Job '{job_id}' not found.\nAvailable jobs: {available_str}"
        
        content = json.loads(job_file.read_text(encoding="utf-8"))
        
        # Format the response nicely
        status = content.get("status", "unknown")
        tool_name = content.get("tool_name", "unknown")
        created = content.get("created_at", "unknown")
        result = content.get("result", "")
        
        # Apply max_lines limit FIRST (before pattern filter)
        if max_lines > 0 and result:
            lines = result.splitlines()
            total = len(lines)
            if total > max_lines:
                lines = lines[:max_lines]
                result = "\n".join(lines)
                result = f"[TRUNCATED to first {max_lines}/{total} lines]\n\n" + result
        
        # Apply pattern filter if specified (TOKEN OPTIMIZATION)
        if pattern and result:
            try:
                lines = result.splitlines()
                filtered = []
                regex = re.compile(pattern, re.IGNORECASE)
                for i, line in enumerate(lines):
                    if regex.search(line):
                        # Include context: 2 lines before and after
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        for j in range(start, end):
                            if lines[j] not in filtered:
                                filtered.append(lines[j])
                if filtered:
                    result = "\n".join(filtered)
                    result = f"[FILTERED with pattern '{pattern}' - {len(filtered)}/{len(lines)} lines]\n\n" + result
                else:
                    result = f"[Pattern '{pattern}' matched 0 lines. Showing first 50 chars of result]\n{result[:50]}..."
            except re.error:
                return f"Error: Invalid regex pattern '{pattern}'"
        
        lines = [
            f"Job: {job_id}",
            f"Tool: {tool_name}",
            f"Status: {status}",
            f"Created: {created}",
            "-" * 40,
        ]
        
        if result:
            lines.append("Result:")
            lines.append(result)
        else:
            lines.append("(No result available)")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error reading job: {e}"

_READ_JOB_SCHEMA = {
    "name": "ReadJob",
    "description": "Read a job result by its ID. Use this to get results from TmuxOffload or background tasks. CRITICAL: For large outputs, use 'max_lines' (e.g., 100) or 'pattern' to avoid loading 20K+ chars into context. ReadJob does NOT replace last_tool_output, so you can safely use it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "The job ID (e.g., '4ef7350f' from TmuxOffload)"},
            "pattern": {"type": "string", "description": "Optional regex pattern to filter results. HIGHLY RECOMMENDED for large outputs. Example: 'claimed|site_name' or 'username|profile'"},
            "max_lines": {"type": "integer", "description": "Maximum lines to return. CRITICAL for huge outputs (Sherlock: use 50-100). 0 = no limit. This is applied BEFORE pattern filter."},
        },
        "required": ["job_id"],
    },
}

TOOL_SCHEMAS.append(_READ_JOB_SCHEMA)

register_tool(ToolDef(
    name="ReadJob",
    schema=_READ_JOB_SCHEMA,
    func=_read_job,
    read_only=True,
    concurrent_safe=True,
))


# ── Git Tools ─────────────────────────────────────────────────────────────

_GIT_DIFF_SCHEMA = {
    "name": "GitDiff",
    "description": "Show git diff for a file or the entire repo. Optionally specify commit range.",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Optional file path to diff"},
            "commit": {"type": "string", "description": "Optional commit hash or range (e.g. HEAD~1)"},
        },
    },
}

_GIT_STATUS_SCHEMA = {
    "name": "GitStatus",
    "description": "Show git status: modified, staged, untracked files in the repo.",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

_GIT_LOG_SCHEMA = {
    "name": "GitLog",
    "description": "Show recent git commit history. Optionally filter by file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Optional file to filter history"},
            "n": {"type": "integer", "description": "Number of commits (default 10)"},
        },
    },
}


def _git_diff(params: dict, _config: dict) -> str:
    file_path = params.get("file_path", "")
    commit = params.get("commit", "")
    cmd = ["git", "diff"]
    if commit:
        cmd += commit.split()
    if file_path:
        cmd.append(file_path)
    try:
        r = subprocess.run(_rtk_wrap_cmd(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return r.stdout.strip() or "(no changes)"
    except Exception as e:
        return f"Error: {e}"


def _git_status(_params: dict, _config: dict) -> str:
    try:
        r = subprocess.run(_rtk_wrap_cmd(["git", "status", "-sb"]), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        return r.stdout.strip() or "(no changes)"
    except Exception as e:
        return f"Error: {e}"


def _git_log(params: dict, _config: dict) -> str:
    file_path = params.get("file_path", "")
    n = params.get("n", 10)
    cmd = ["git", "log", f"--max-count={n}", "--oneline", "--decorate"]
    if file_path:
        cmd += ["--", file_path]
    try:
        r = subprocess.run(_rtk_wrap_cmd(cmd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        return r.stdout.strip() or "(no commits)"
    except Exception as e:
        return f"Error: {e}"


TOOL_SCHEMAS.extend([_GIT_DIFF_SCHEMA, _GIT_STATUS_SCHEMA, _GIT_LOG_SCHEMA])

register_tool(ToolDef(name="GitDiff", schema=_GIT_DIFF_SCHEMA, func=_git_diff, read_only=True, concurrent_safe=True))
register_tool(ToolDef(name="GitStatus", schema=_GIT_STATUS_SCHEMA, func=_git_status, read_only=True, concurrent_safe=True))
register_tool(ToolDef(name="GitLog", schema=_GIT_LOG_SCHEMA, func=_git_log, read_only=True, concurrent_safe=True))


def _launch_sandbox(params: dict, config: dict) -> str:
    # Use the existing command handler from dulus.py
    try:
        from dulus import COMMANDS
        handler = COMMANDS.get("sandbox")
        if not handler:
            return "Error: /sandbox command not found in Dulus."
        
        stop = params.get("stop", False)
        args = "stop" if stop else ""
        
        state = config.get("_state")
        if not state:
            return "Error: Dulus session state not available to tool."
            
        handler(args, state, config)
        return "Dulus Sandbox OS opened in browser." if not stop else "Sandbox stopped."
    except Exception as e:
        return f"Error launching sandbox: {e}"


register_tool(ToolDef(name="LaunchSandbox", schema=_LAUNCH_SANDBOX_SCHEMA, func=_launch_sandbox))


# Plugins are loaded once when Dulus starts (not on every reload to avoid overhead)
try:
    from plugin.loader import register_plugin_tools
    # First-launch bootstrap: copy bundled plugins (composio, etc) shipped
    # inside the wheel into ~/.dulus/plugins/ so they're available out of
    # the box. Idempotent — only copies what's not already installed.
    try:
        from plugin.store import bootstrap_bundled_plugins
        bootstrap_bundled_plugins()
    except Exception:
        pass
    _plugin_count = register_plugin_tools()
    # Silent registration - plugins are now available as tools
except Exception:
    # If plugin system fails, continue with core tools only
    _plugin_count = 0


# ── WebBridge tool schemas (append to TOOL_SCHEMAS so AI sees them) ──────────
try:
    from webbridge.tools import _TOOL_SCHEMAS as _WEBBRIDGE_SCHEMAS
    TOOL_SCHEMAS.extend(_WEBBRIDGE_SCHEMAS)
except Exception:
    pass  # Playwright not installed; skip gracefully


