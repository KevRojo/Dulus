"""SetTodoList Tool - Persistent todo management for Dulus.

Provides a SetTodoList tool that allows the agent to manage a persistent
todo list stored in the session directory. Supports setting, getting, and
updating todo items with status tracking (pending, in_progress, done).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from tool_registry import ToolDef, register_tool


# ── Schema ────────────────────────────────────────────────────────────────────

_SET_TODO_LIST_SCHEMA = {
    "name": "SetTodoList",
    "description": (
        "Set or get the todo list. When todos are provided, updates the entire list. "
        "When omitted, returns the current todo list. Use this to track short-term "
        "tasks, action items, and progress during a session. For more complex "
        "project management with dependencies, use TaskCreate/TaskUpdate instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "List of todo items to set. Each item has a title and status.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "The todo item title (must be non-empty).",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "done"],
                            "description": "Current status of the todo item.",
                        },
                    },
                    "required": ["title", "status"],
                },
            },
        },
        "required": [],
    },
}

# ── Constants ─────────────────────────────────────────────────────────────────

_STATUS_ICONS = {
    "pending": "[ ]",
    "in_progress": "[/]",
    "done": "[x]",
}


# ── Implementation ────────────────────────────────────────────────────────────

class TodoManager:
    """Manages persistent todo list storage in the session directory."""

    def __init__(self, session_dir: str | None = None) -> None:
        """Initialize the todo manager.

        Args:
            session_dir: Directory for storing todos. Defaults to current working directory.
        """
        self._session_dir = session_dir or os.getcwd()
        self._todos_file = Path(self._session_dir) / ".dulus" / "todos.json"

    def _load_todos(self) -> list[dict]:
        """Load todos from disk.

        Returns:
            List of todo dicts, or empty list if file doesn't exist or is corrupt.
        """
        if not self._todos_file.exists():
            return []
        try:
            with open(self._todos_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except (json.JSONDecodeError, IOError, OSError):
            return []

    def _save_todos(self, todos: list[dict]) -> None:
        """Save todos to disk.

        Args:
            todos: List of todo dicts to persist.
        """
        self._todos_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._todos_file, "w", encoding="utf-8") as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)

    def read_todos(self) -> str:
        """Read todos and format for display.

        Returns:
            Formatted string of the current todo list.
        """
        todos = self._load_todos()
        if not todos:
            return "Todo list is empty."

        lines = ["Current todo list:"]
        for t in todos:
            status = t.get("status", "pending")
            icon = _STATUS_ICONS.get(status, "[ ]")
            lines.append(f"  {icon} {t.get('title', '')}")
        return "\n".join(lines)

    def write_todos(self, todos: list[dict]) -> str:
        """Update the todo list.

        Args:
            todos: New list of todo items.

        Returns:
            Confirmation message with count of updated items.
        """
        # Validate todo items
        validated = []
        for t in todos:
            title = t.get("title", "").strip()
            status = t.get("status", "pending")
            if title:
                validated.append({"title": title, "status": status})

        self._save_todos(validated)
        return f"Todo list updated with {len(validated)} item(s)."


# Module-level singleton for persistence across tool calls
_todo_manager: TodoManager | None = None


def _get_manager(session_dir: str | None = None) -> TodoManager:
    """Get or create the TodoManager singleton.

    Args:
        session_dir: Optional directory override.

    Returns:
        The shared TodoManager instance.
    """
    global _todo_manager
    if _todo_manager is None or session_dir is not None:
        _todo_manager = TodoManager(session_dir)
    return _todo_manager


def _set_todo_list(todos: list[dict] | None = None, config: dict | None = None) -> str:
    """Handle SetTodoList tool execution.

    Args:
        todos: List of todo items to set, or None to just read.
        config: Runtime configuration dict.

    Returns:
        Formatted result string.
    """
    cfg = config or {}
    # Use config's session directory if available
    session_dir = cfg.get("_session_dir") or cfg.get("workspace", os.getcwd())
    manager = _get_manager(session_dir)

    if todos is None:
        return manager.read_todos()
    return manager.write_todos(todos)


# ── Registration ──────────────────────────────────────────────────────────────

def _register() -> None:
    """Register the SetTodoList tool into the central registry."""
    register_tool(
        ToolDef(
            name="SetTodoList",
            schema=_SET_TODO_LIST_SCHEMA,
            func=lambda p, c: _set_todo_list(p.get("todos"), c),
            read_only=False,
            concurrent_safe=True,
        )
    )


_register()
