"""Core agent loop: neutral message format, multi-provider streaming."""
from __future__ import annotations

import os
import queue
import threading
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Generator

from tool_registry import get_tool_schemas, clear_last_output
from tools import execute_tool
import tools as _tools_init  # ensure built-in tools are registered on import
from providers import stream, AssistantTurn, TextChunk, ThinkingChunk, detect_provider
from compaction import maybe_compact

_SENTINEL = object()

def _interruptible_stream(gen):
    """Run a generator in a daemon thread, yield events via Queue.
    Ctrl+C (KeyboardInterrupt) is always deliverable because the main
    thread only blocks on queue.get(timeout=0.1) — never on a raw socket.
    """
    q: queue.Queue = queue.Queue(maxsize=64)

    def _producer():
        try:
            for event in gen:
                q.put(event)
        except Exception as exc:
            q.put(exc)
        finally:
            q.put(_SENTINEL)

    t = threading.Thread(target=_producer, daemon=True)
    t.start()
    while True:
        try:
            item = q.get(timeout=0.1)
        except queue.Empty:
            continue
        if item is _SENTINEL:
            break
        if isinstance(item, BaseException):
            raise item
        yield item

# ── Re-export event types (used by dulus) ─────────────────────────────────
__all__ = [
    "AgentState", "run",
    "TextChunk", "ThinkingChunk",
    "ToolStart", "ToolEnd", "TurnDone", "PermissionRequest",
]


@dataclass
class AgentState:
    """Mutable session state. messages use the neutral provider-independent format."""
    messages: list = field(default_factory=list)
    total_input_tokens:  int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    turn_count: int = 0


@dataclass
class ToolStart:
    name:   str
    inputs: dict

@dataclass
class ToolEnd:
    name:      str
    result:    str
    permitted: bool = True

@dataclass
class TurnDone:
    input_tokens:  int
    output_tokens: int
    cache_read_tokens:     int = 0
    cache_creation_tokens: int = 0

@dataclass
class PermissionRequest:
    description: str
    granted: bool = False


# ── Agent loop ─────────────────────────────────────────────────────────────

def run(
    user_message: str,
    state: AgentState,
    config: dict,
    system_prompt: str,
    depth: int = 0,
    cancel_check=None,
) -> Generator:
    """
    Multi-turn agent loop (generator).
    Yields: TextChunk | ThinkingChunk | ToolStart | ToolEnd |
            PermissionRequest | TurnDone

    Args:
        depth: sub-agent nesting depth, 0 for top-level
        cancel_check: callable returning True to abort the loop early
    """
    from common import sanitize_text
    # Append user turn in neutral format (sanitize to kill Windows surrogates)
    user_msg = {"role": "user", "content": sanitize_text(user_message)}
    # Attach pending image from /image command if present
    pending_img = config.pop("_pending_image", None)
    if pending_img:
        user_msg["images"] = [pending_img]
    
    initial_msg_count = len(state.messages)
    state.messages.append(user_msg)

    # Inject runtime metadata into config so tools (e.g. Agent) can access it
    config.update({"_depth": depth, "_system_prompt": system_prompt})

    while True:
        if cancel_check and cancel_check():
            return
        state.turn_count += 1
        assistant_turn: AssistantTurn | None = None

        # Compact context if approaching window limit
        maybe_compact(state, config)

        # Sanitize message contents before sending to API (surrogate safety)
        _safe_messages = []
        for m in state.messages:
            _m = dict(m)
            _c = _m.get("content")
            if isinstance(_c, str):
                _m["content"] = sanitize_text(_c)
            _safe_messages.append(_m)

        # Stream from provider — wrapped so Ctrl+C always fires
        for event in _interruptible_stream(stream(
            model=config["model"],
            system=system_prompt,
            messages=_safe_messages,
            tool_schemas=get_tool_schemas(),
            config=config,
        )):
            if isinstance(event, (TextChunk, ThinkingChunk)):
                yield event
            elif isinstance(event, AssistantTurn):
                assistant_turn = event

        if assistant_turn is None:
            break

        if assistant_turn.error:
            # Rollback: remove anything added during this turn sequence to prevent corrupted history
            while len(state.messages) > initial_msg_count:
                state.messages.pop()
            break

        # Record assistant turn in neutral format
        state.messages.append({
            "role":       "assistant",
            "content":    sanitize_text(assistant_turn.text),
            "thinking":   sanitize_text(assistant_turn.thinking) if assistant_turn.thinking else "",
            "tool_calls": assistant_turn.tool_calls,
        })

        state.total_input_tokens  += assistant_turn.in_tokens
        state.total_output_tokens += assistant_turn.out_tokens
        c_read = getattr(assistant_turn, "cache_read_tokens", 0)
        c_create = getattr(assistant_turn, "cache_creation_tokens", 0)
        state.total_cache_read_tokens += c_read
        state.total_cache_creation_tokens += c_create
        yield TurnDone(
            assistant_turn.in_tokens,
            assistant_turn.out_tokens,
            cache_read_tokens=c_read,
            cache_creation_tokens=c_create,
        )

        if not assistant_turn.tool_calls:
            break   # No tools → conversation turn complete

        # ── Execute tools ────────────────────────────────────────────────
        for tc in assistant_turn.tool_calls:
            yield ToolStart(tc["name"], tc["input"])

            # Permission gate
            permitted = _check_permission(tc, config)
            if not permitted:
                if config.get("permission_mode") == "plan":
                    # Plan mode: silently deny writes (no user prompt)
                    permitted = False
                else:
                    req = PermissionRequest(description=_permission_desc(tc))
                    yield req
                    permitted = req.granted

            if not permitted:
                if config.get("permission_mode") == "plan":
                    plan_file = config.get("_plan_file", "")
                    result = (
                        f"[Plan mode] Write operations are blocked except to the plan file: {plan_file}\n"
                        "Finish your analysis and write the plan to the plan file. "
                        "The user will run /plan done to exit plan mode and begin implementation."
                    )
                else:
                    result = "Denied: user rejected this operation"
            else:
                config["_turn_count"] = state.turn_count
                result = execute_tool(
                    tc["name"], tc["input"],
                    permission_mode="accept-all",  # already gate-checked above
                    config=config,
                )
                # time.sleep(1) # Removed delay as requested

            yield ToolEnd(tc["name"], result, permitted)

            # Determine what the USER actually saw rendered, based on tool type +
            # auto_show + verbose. Inject a SYSTEM HINT when user saw nothing useful,
            # so the model can decide whether to PrintToConsole the content.
            from tool_registry import is_display_only
            display = is_display_only(tc["name"])
            auto_show_on = config.get("auto_show", True) if config else True
            verbose_on   = config.get("verbose",   False) if config else False

            # User-visibility rules (must match dulus.py print_tool_end logic):
            #   display tool   → user saw full output IF auto_show ON
            #   other tool     → user saw 500-char preview IF verbose ON
            if display:
                user_saw = auto_show_on
            else:
                user_saw = verbose_on

            if display and user_saw:
                # Display-only tool the user already saw: replace with placeholder to save tokens.
                result_summary = f"[Display output shown to user: {len(result)} characters]"
            else:
                result_summary = result

            # Inject the hint when (a) user did not see the content, (b) it's not a
            # purely internal tool, and (c) the call did not error out.
            _internal_tools = {
                "SearchLastOutput", "ReadJob", "TmuxOffload", "MemorySearch",
                "PrintToConsole", "AskUserQuestion", "Write", "Edit",
            }
            if (not user_saw
                    and tc["name"] not in _internal_tools
                    and not result.startswith(("Error", "Denied"))):
                state_desc = []
                if not auto_show_on: state_desc.append("auto_show OFF")
                if not verbose_on:   state_desc.append("verbose OFF")
                state_str = " + ".join(state_desc) or "user-display suppressed"
                result_summary = (
                    f"{result_summary}\n\n"
                    f"[SYSTEM HINT — {state_str}]\n"
                    "The user did NOT see this output rendered (only a brief [OK] line). "
                    "If this content is meant for the user (Bash output they asked for, file "
                    "they wanted to read, ASCII art they requested), call "
                    "PrintToConsole(content=...) or PrintToConsole(file_path=...) NOW to "
                    "show it. If this was just internal investigation, ignore this hint."
                )

            # Record tool result in neutral format
            state.messages.append({
                "role":         "tool",
                "tool_call_id": tc["id"],
                "name":         tc["name"],
                "content":      sanitize_text(result_summary),
            })

            # ── Truncation Awareness Reminder ────────────────────────────────
            # If the tool output was truncated, the model only saw a fragment.
            # Inject a hard reminder so it cannot honestly claim "X is missing"
            # without first using SearchLastOutput to actually search the file.
            # Skip this check for SearchLastOutput itself to avoid loops.
            if (tc["name"] != "SearchLastOutput"
                    and "[TRUNCATED" in result):
                try:
                    path = Path.home() / ".dulus" / "last_tool_output.txt"
                    if path.exists():
                        full_size = path.stat().st_size
                        seen_size = len(result)
                        if full_size > seen_size:
                            with path.open("rb") as _f:
                                full_lines = sum(1 for _ in _f)
                            state.messages.append({
                                "role": "user",
                                "content": (
                                    "[SYSTEM REMINDER — TRUNCATED OUTPUT]\n"
                                    f"The previous tool result was TRUNCATED. You only saw "
                                    f"~{seen_size} characters out of {full_size} total "
                                    f"({full_lines} lines). The full output is saved.\n\n"
                                    "RULE: You CANNOT claim that any item, font, key, name, "
                                    "match, or piece of data is missing, absent, or does not "
                                    "exist based on what you just saw. You only have a fragment.\n\n"
                                    "BEFORE answering the user's question, you MUST call:\n"
                                    "  SearchLastOutput(pattern=\"<the thing the user asked about>\")\n"
                                    "to verify against the full saved output. If the user asked "
                                    "about a specific name, search for that exact name. If they "
                                    "asked for a count or a list, use SearchLastOutput() with no "
                                    "pattern to get the full summary.\n\n"
                                    "Do not answer from memory or guess. Search first."
                                ),
                            })
                except Exception:
                    pass


# ── Helpers ───────────────────────────────────────────────────────────────

def _check_permission(tc: dict, config: dict) -> bool:
    """Return True if operation is auto-approved (no need to ask user)."""
    perm_mode = config.get("permission_mode", "auto")
    name = tc["name"]

    # Plan mode tools are always auto-approved
    if name in ("EnterPlanMode", "ExitPlanMode"):
        return True

    if perm_mode == "accept-all":
        return True
    if perm_mode == "manual":
        return False   # always ask

    if perm_mode == "plan":
        # Allow writes ONLY to the plan file
        if name in ("Write", "Edit"):
            plan_file = config.get("_plan_file", "")
            target = tc["input"].get("file_path", "")
            if plan_file and target and \
               os.path.normpath(target) == os.path.normpath(plan_file):
                return True
            return False
        if name == "NotebookEdit":
            return False
        if name == "Bash":
            from tools import _is_safe_bash
            return _is_safe_bash(tc["input"].get("command", ""))
        return True  # reads are fine

    # "auto" mode: only ask for writes and non-safe bash
    if name in ("Read", "Glob", "Grep", "WebFetch", "WebSearch"):
        return True
    if name == "Bash":
        from tools import _is_safe_bash
        return _is_safe_bash(tc["input"].get("command", ""))
    return False   # Write, Edit → ask


def _permission_desc(tc: dict) -> str:
    name = tc["name"]
    inp  = tc["input"]
    if name == "Bash":   return f"Run: {inp.get('command', '')}"
    if name == "Write":  return f"Write to: {inp.get('file_path', '')}"
    if name == "Edit":   return f"Edit: {inp.get('file_path', '')}"
    return f"{name}({list(inp.values())[:1]})"
