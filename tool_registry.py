"""Tool plugin registry for falcon.

Provides a central registry for tool definitions, lookup, schema export,
and dispatch with output truncation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolDef:
    """Definition of a single tool plugin.

    Attributes:
        name: unique tool identifier
        schema: JSON-schema dict sent to the API (name, description, input_schema)
        func: callable(params: dict, config: dict) -> str
        read_only: True if the tool never mutates state
        concurrent_safe: True if safe to run in parallel with other tools
        display_only: True if output is visual/display only and should NOT be read back
                   (saves tokens - use for ASCII art, charts, visual output)
    """
    name: str
    schema: Dict[str, Any]
    func: Callable[[Dict[str, Any], Dict[str, Any]], str]
    read_only: bool = False
    concurrent_safe: bool = False
    display_only: bool = False  # NEW: visual output, don't read back


# --------------- internal state ---------------

_registry: Dict[str, ToolDef] = {}
_last_seen_turn: int = -1


# --------------- public API ---------------

def register_tool(tool_def: ToolDef) -> None:
    """Register a tool, overwriting any existing tool with the same name."""
    _registry[tool_def.name] = tool_def


def get_tool(name: str) -> Optional[ToolDef]:
    """Look up a tool by name. Returns None if not found."""
    return _registry.get(name)


def get_all_tools() -> List[ToolDef]:
    """Return all registered tools (insertion order)."""
    return list(_registry.values())


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return the schemas of all registered tools (for API tool parameter)."""
    return [t.schema for t in _registry.values()]


def is_display_only(name: str) -> bool:
    """Check if a tool is display-only (visual output, don't read back).
    
    Returns True if the tool's output should not be fed back to the model,
    typically for ASCII art, visual charts, or display-only content.
    """
    tool = get_tool(name)
    return tool.display_only if tool else False


def execute_tool(
    name: str,
    params: Dict[str, Any],
    config: Dict[str, Any],
    max_output: int = 2500,
) -> str:
    """Dispatch a tool call by name.

    Args:
        name: tool name
        params: tool input parameters dict
        config: runtime configuration dict
        max_output: maximum allowed output length in characters.
            Default 2500 — applies uniformly to built-ins AND plugins.
            Tools that need more MUST paginate explicitly (Read with offset/limit, etc).
            Callers can override via config["max_tool_output"] (see tools.execute_tool).
            This prevents context bloat from 0.5% → 7% on large outputs.

    Returns:
        Tool result string, possibly truncated with navigation hints.
    """
    tool = get_tool(name)
    if tool is None:
        return f"Error: tool '{name}' not found."

    import io
    from contextlib import redirect_stdout, redirect_stderr

    f_stdout = io.StringIO()
    f_stderr = io.StringIO()

    try:
        with redirect_stdout(f_stdout), redirect_stderr(f_stderr):
            result = tool.func(params, config)
    except Exception as e:
        out = f_stdout.getvalue()
        err = f_stderr.getvalue()
        msg = f"Error executing {name}: {e}"
        if out: msg += f"\nSTDOUT:\n{out}"
        if err: msg += f"\nSTDERR:\n{err}"

        # Add a heuristic hint if a plugin tool crashes
        _mod = getattr(tool.func, "__module__", "")
        if _mod.startswith("_plugin_"):
            parts = _mod.split("_")
            p_name = parts[2] if len(parts) > 2 else "unknown"
            msg += f"\n\n💡 Hint: This plugin tool failed. Do not guess the fix. Use Read/Bash to view ~/.falcon/plugins/{p_name}/plugin_tool.py and its documentation to understand the correct API usage."

        return msg

    out = f_stdout.getvalue()
    err = f_stderr.getvalue()

    if result is None:
        result = ""

    if not isinstance(result, str):
        result = json.dumps(result, ensure_ascii=False, default=str)

    # Merge captured output with return value
    final_parts = []
    if out.strip():
        final_parts.append(out.strip())
    if err.strip():
        final_parts.append(f"--- STDERR ---\n{err.strip()}")
    
    r_strip = result.strip()
    if r_strip:
        if final_parts:
            # If the function printed something AND returned something, distinguish them
            final_parts.append(f"--- RESULT ---\n{r_strip}")
        else:
            final_parts.append(r_strip)

    result = "\n\n".join(final_parts) if final_parts else "(ok)"
    total_lines = result.count("\n") + 1 if result else 0

    # ── Audit trail: log all mutating tool operations ──
    try:
        if name in ("Write", "Edit", "Bash"):
            from memory.audit import log_operation
            log_operation(name, params, result[:200])
    except Exception:
        pass

    # Save full un-truncated output for persistent access.
    # Shield: tools that only READ the saved output must never overwrite it.
    _read_only_tools = ("Read", "LineCount", "SearchLastOutput")
    is_exploring_persistence = (
        name == "Grep"
        and "last_tool_output.txt" in params.get("path", "")
    )

    if name not in _read_only_tools and not is_exploring_persistence and not tool.display_only:
        try:
            global _last_seen_turn
            curr_turn = config.get("_turn_count", -1)
            out_file = Path.home() / ".falcon" / "last_tool_output.txt"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            
            # If this is a new TURN (assistant turn) and it's NOT a diagnostic search,
            # we overwrite to start fresh. Within the same turn, we append.
            mode = "w" if curr_turn != _last_seen_turn else "a"
            _last_seen_turn = curr_turn

            with out_file.open(mode, encoding="utf-8", errors="replace") as f:
                if mode == "a":
                    f.write(f"\n\n--- [TOOL CALL: {name}] ---\n")
                f.write(result)
                if mode == "a":
                    f.write("\n")
        except Exception:
            pass

    # NO TRUNCATION for display-only tools (PrintToConsole, etc.)
    # These tools output directly to console and don't consume context tokens
    if not tool.display_only and len(result) > max_output:
        total_lines = result.count("\n") + 1
        first_chunk = max_output // 3  # Less upfront, force pagination
        last_chunk = max_output // 6   # Even smaller tail
        
        # Show small preview + force explicit pagination pattern
        result = (
            result[:first_chunk]+" >>>>>> THE RESULT WAS TRUNCATED TO AVOID TOKEN WASTE,Read last_tool_output.txt file if complete output needed <<<<<<<  "+result[-last_chunk:]
        )

    return result


def clear_last_output() -> None:
    """Reset the last_tool_output.txt file. Should be called at turn start."""
    try:
        out_file = Path.home() / ".falcon" / "last_tool_output.txt"
        if out_file.exists():
            out_file.unlink()
    except Exception:
        pass


def clear_registry() -> None:
    """Remove all registered tools. Intended for testing."""
    _registry.clear()
