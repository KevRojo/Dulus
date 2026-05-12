"""Background Task Tools - Manage background tasks for Dulus.

Provides tools for listing, retrieving output from, and stopping background
tasks. These tools integrate with the agent's background task execution system
to give visibility into async operations.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from tool_registry import ToolDef, register_tool


# ── Schemas ───────────────────────────────────────────────────────────────────

_BG_TASK_LIST_SCHEMA = {
    "name": "BgTaskList",
    "description": (
        "List all currently running and recently completed background tasks. "
        "Returns task IDs, descriptions, status, and start times. "
        "Use this to monitor async operations started by the agent."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

_BG_TASK_OUTPUT_SCHEMA = {
    "name": "BgTaskOutput",
    "description": (
        "Get the output (stdout/stderr) of a background task by its ID. "
        "Use block=true to wait for the task to complete and return full output. "
        "Use block=false (default) to get current output without waiting."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The unique ID of the background task.",
            },
            "block": {
                "type": "boolean",
                "description": "If true, block until the task completes before returning.",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum seconds to wait when block=true (default: 60).",
                "default": 60,
            },
        },
        "required": ["task_id"],
    },
}

_BG_TASK_STOP_SCHEMA = {
    "name": "BgTaskStop",
    "description": (
        "Stop a running background task by its ID. This requires user approval "
        "unless the task was started by the current agent session. Use with caution "
        "as stopping a task may leave operations in an incomplete state."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The unique ID of the background task to stop.",
            },
            "force": {
                "type": "boolean",
                "description": "If true, forcefully terminate the task (SIGKILL).",
                "default": False,
            },
        },
        "required": ["task_id"],
    },
}


# ── Background Task Store ─────────────────────────────────────────────────────

@dataclass
class BackgroundTask:
    """Represents a single background task."""

    task_id: str
    description: str
    kind: str  # e.g., "bash", "python", "subagent"
    status: str  # "running", "completed", "failed", "stopped"
    thread: threading.Thread | None = None
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    exit_code: int | None = None
    _stop_event: threading.Event = field(default_factory=threading.Event)

    @property
    def duration(self) -> float:
        """Return elapsed seconds since start."""
        end = self.end_time or time.time()
        return end - self.start_time

    def is_running(self) -> bool:
        """Check if the task is still running."""
        if self.thread is not None:
            return self.thread.is_alive()
        return self.status == "running"

    def stop(self, force: bool = False) -> None:
        """Signal the task to stop."""
        self._stop_event.set()
        if force and self.thread is not None and self.thread.is_alive():
            # We can't truly kill a thread in Python, but we record the intent
            self.status = "stopped"
            self.end_time = time.time()

    def append_output(self, line: str, is_stderr: bool = False) -> None:
        """Append an output line."""
        if is_stderr:
            self.stderr_lines.append(line)
        else:
            self.stdout_lines.append(line)

    def to_dict(self) -> dict:
        """Serialize to dict for display."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "kind": self.kind,
            "status": self.status,
            "duration": round(self.duration, 1),
            "start_time": self.start_time,
        }


class BackgroundTaskStore:
    """In-memory store for background tasks."""

    def __init__(self) -> None:
        """Initialize an empty task store."""
        self._tasks: dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()

    def add_task(self, task: BackgroundTask) -> None:
        """Add a task to the store.

        Args:
            task: The BackgroundTask to store.
        """
        with self._lock:
            self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> BackgroundTask | None:
        """Retrieve a task by ID.

        Args:
            task_id: The task's unique ID.

        Returns:
            The BackgroundTask or None if not found.
        """
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> list[BackgroundTask]:
        """List all tasks, most recent first.

        Returns:
            List of BackgroundTask objects.
        """
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.start_time, reverse=True)

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the store.

        Args:
            task_id: The task's unique ID.

        Returns:
            True if the task was removed, False if not found.
        """
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def update_status(self, task_id: str, status: str, exit_code: int | None = None) -> None:
        """Update a task's status.

        Args:
            task_id: The task's unique ID.
            status: New status string.
            exit_code: Optional exit code.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = status
                if exit_code is not None:
                    task.exit_code = exit_code
                if status in ("completed", "failed", "stopped"):
                    task.end_time = time.time()


# Module-level singleton
_task_store: BackgroundTaskStore | None = None
_store_lock = threading.Lock()


def get_task_store() -> BackgroundTaskStore:
    """Get the global BackgroundTaskStore singleton.

    Returns:
        The shared BackgroundTaskStore instance.
    """
    global _task_store
    if _task_store is None:
        with _store_lock:
            if _task_store is None:
                _task_store = BackgroundTaskStore()
    return _task_store


def create_background_task(
    description: str,
    kind: str,
    target: Callable,
    args: tuple = (),
    kwargs: dict | None = None,
) -> BackgroundTask:
    """Create and start a new background task.

    Args:
        description: Human-readable description of the task.
        kind: Type of task (e.g., "bash", "python", "subagent").
        target: Callable to run in the background thread.
        args: Positional arguments for the target.
        kwargs: Keyword arguments for the target.

    Returns:
        The created BackgroundTask.
    """
    task_id = str(uuid.uuid4())[:8]
    task = BackgroundTask(
        task_id=task_id,
        description=description,
        kind=kind,
        status="running",
    )

    def _wrapped_target() -> None:
        """Wrapper that captures completion."""
        try:
            target(*args, **(kwargs or {}))
            task.status = "completed"
        except Exception as exc:
            task.status = "failed"
            task.append_output(f"Error: {exc}", is_stderr=True)
        finally:
            task.end_time = time.time()

    thread = threading.Thread(target=_wrapped_target, daemon=True)
    task.thread = thread
    thread.start()

    get_task_store().add_task(task)
    return task


# ── Tool implementations ──────────────────────────────────────────────────────

def _bg_task_list() -> str:
    """List all background tasks.

    Returns:
        Formatted string listing all tasks.
    """
    store = get_task_store()
    tasks = store.list_tasks()

    if not tasks:
        return "No background tasks."

    lines = [f"Background tasks ({len(tasks)} total):", ""]
    for task in tasks:
        status_icon = {
            "running": "●",
            "completed": "✓",
            "failed": "✗",
            "stopped": "■",
        }.get(task.status, "?")
        duration = task.duration
        duration_str = f"{duration:.1f}s" if duration < 60 else f"{duration / 60:.1f}m"
        lines.append(
            f"  {status_icon} [{task.task_id}] {task.description} "
            f"({task.kind}, {task.status}, {duration_str})"
        )
    return "\n".join(lines)


def _bg_task_output(task_id: str, block: bool = False, timeout: int = 60) -> str:
    """Get output from a background task.

    Args:
        task_id: The task's unique ID.
        block: If True, wait for task completion.
        timeout: Max seconds to wait when blocking.

    Returns:
        The task's output or an error message.
    """
    store = get_task_store()
    task = store.get_task(task_id)

    if task is None:
        return f"Error: Background task '{task_id}' not found."

    # If blocking, wait for completion
    if block:
        if task.is_running() and task.thread is not None:
            task.thread.join(timeout=timeout)
            if task.is_running():
                return (
                    f"Task {task_id} is still running after {timeout}s timeout.\n\n"
                    f"Current output:\n{''.join(task.stdout_lines[-100:])}"
                )

    # Build output
    output_parts = []
    if task.stdout_lines:
        output_parts.append("".join(task.stdout_lines))
    if task.stderr_lines:
        output_parts.append("--- STDERR ---\n" + "".join(task.stderr_lines))

    status_line = f"[{task.task_id}] Status: {task.status}, Duration: {task.duration:.1f}s"
    if task.exit_code is not None:
        status_line += f", Exit code: {task.exit_code}"

    if output_parts:
        return status_line + "\n\n" + "\n\n".join(output_parts)
    return status_line + "\n(no output yet)"


def _bg_task_stop(task_id: str, force: bool = False) -> str:
    """Stop a background task.

    Args:
        task_id: The task's unique ID.
        force: If True, forcefully terminate.

    Returns:
        Confirmation or error message.
    """
    store = get_task_store()
    task = store.get_task(task_id)

    if task is None:
        return f"Error: Background task '{task_id}' not found."

    if not task.is_running():
        return f"Task {task_id} is not running (status: {task.status})."

    task.stop(force=force)
    store.update_status(task_id, "stopped")

    force_str = "forcefully " if force else ""
    return f"Task {task_id} ({task.description}) {force_str}stopped."


# ── Registration ──────────────────────────────────────────────────────────────

def _register() -> None:
    """Register all background task tools into the central registry."""
    defs = [
        ToolDef(
            name="BgTaskList",
            schema=_BG_TASK_LIST_SCHEMA,
            func=lambda p, c: _bg_task_list(),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="BgTaskOutput",
            schema=_BG_TASK_OUTPUT_SCHEMA,
            func=lambda p, c: _bg_task_output(
                p["task_id"],
                p.get("block", False),
                p.get("timeout", 60),
            ),
            read_only=True,
            concurrent_safe=True,
        ),
        ToolDef(
            name="BgTaskStop",
            schema=_BG_TASK_STOP_SCHEMA,
            func=lambda p, c: _bg_task_stop(p["task_id"], p.get("force", False)),
            read_only=False,
            concurrent_safe=False,
        ),
    ]
    for td in defs:
        register_tool(td)


_register()
