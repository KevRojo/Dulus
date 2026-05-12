"""BackgroundTaskManager - Manage background tasks with persistence and recovery.

Features 14-15: Background Tasks (BackgroundTaskManager, BackgroundAgentRunner)

This module provides:
    - BackgroundTaskStore: Persistent on-disk storage for task specs, runtime state,
      and output logs.
    - BackgroundTaskManager: Create, monitor, kill, and recover background bash/agent
      tasks with configurable limits and heartbeats.
    - BackgroundAgentRunner: Async runner for sub-agent tasks in the background.
    - Utility functions: Status helpers, formatting, ID generation.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

TERMINAL_STATUSES: set[str] = {"completed", "failed", "killed", "lost"}
NON_TERMINAL_STATUSES: set[str] = {"created", "starting", "running", "awaiting_approval"}

# Default configuration for BackgroundTaskManager
DEFAULT_MANAGER_CONFIG: dict[str, int] = {
    "max_running_tasks": 5,
    "agent_task_timeout_s": 300,
    "worker_heartbeat_interval_ms": 5000,
    "wait_poll_interval_ms": 1000,
    "kill_grace_period_ms": 30000,
    "worker_stale_after_ms": 30000,
    "read_max_bytes": 32768,
    "notification_tail_lines": 50,
}


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class TaskSpec:
    """Static specification for a background task.

    Attributes:
        id: Unique task identifier (e.g. ``bash-a1b2c3d4``).
        kind: Task kind — ``"bash"`` or ``"agent"``.
        session_id: Session directory name this task belongs to.
        description: Human-readable description of the task.
        command: Shell command to execute (for bash tasks).
        timeout_s: Maximum allowed execution time in seconds.
        created_at: Unix timestamp of task creation.
        tool_call_id: Optional tool call identifier that triggered this task.
        owner_role: Role that owns the task (default ``"root"``).
        kind_payload: Additional kind-specific metadata (shell name/path, cwd, etc.).
    """

    id: str
    kind: str
    session_id: str
    description: str
    command: str = ""
    timeout_s: int = 300
    created_at: float = field(default_factory=time.time)
    tool_call_id: str = ""
    owner_role: str = "root"
    kind_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRuntime:
    """Mutable runtime state for a background task.

    Attributes:
        status: Current lifecycle status.
        worker_pid: OS PID of the worker process.
        child_pid: OS PID of the child process (if different from worker).
        child_pgid: Process group ID of the child.
        started_at: Unix timestamp when execution began.
        finished_at: Unix timestamp when execution finished.
        heartbeat_at: Unix timestamp of last worker heartbeat.
        updated_at: Unix timestamp of last state update.
        exit_code: Shell exit code (``0`` on success).
        failure_reason: Human-readable failure explanation.
        interrupted: Whether the task was interrupted/killed.
        timed_out: Whether the task exceeded its timeout.
    """

    status: str = "created"
    worker_pid: int | None = None
    child_pid: int | None = None
    child_pgid: int | None = None
    started_at: float | None = None
    finished_at: float | None = None
    heartbeat_at: float | None = None
    updated_at: float = field(default_factory=time.time)
    exit_code: int | None = None
    failure_reason: str = ""
    interrupted: bool = False
    timed_out: bool = False


@dataclass
class TaskView:
    """Combined read-only view of a task's spec and runtime."""

    spec: TaskSpec
    runtime: TaskRuntime


@dataclass
class TaskOutputChunk:
    """A chunk of task output read from the log file.

    Attributes:
        text: The output text content.
        offset: Byte offset where this chunk starts.
        next_offset: Byte offset where the next chunk should start.
    """

    text: str
    offset: int
    next_offset: int


# ── Persistent store ──────────────────────────────────────────────────────────


class BackgroundTaskStore:
    """Persistent store for background tasks.

    Each task gets its own directory under *root* containing:

    - ``spec.json``   – frozen :class:`TaskSpec`
    - ``runtime.json`` – mutable :class:`TaskRuntime` (rewritten on every state change)
    - ``output.log``   – combined stdout/stderr from the worker

    Parameters:
        root: Base directory where task sub-directories are created.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    # -- directory layout ----------------------------------------------------

    def task_dir(self, task_id: str) -> Path:
        """Return the directory path for *task_id*."""
        return self._root / task_id

    # -- CRUD ----------------------------------------------------------------

    def create_task(self, spec: TaskSpec) -> None:
        """Create a new task directory with initial spec, runtime, and empty log."""
        task_dir = self.task_dir(spec.id)
        task_dir.mkdir(parents=True, exist_ok=True)

        with open(task_dir / "spec.json", "w", encoding="utf-8") as fh:
            json.dump(asdict(spec), fh, indent=2, default=str)

        runtime = TaskRuntime(status="created")
        with open(task_dir / "runtime.json", "w", encoding="utf-8") as fh:
            json.dump(asdict(runtime), fh, indent=2, default=str)

        # Create empty output log
        (task_dir / "output.log").touch()

    def read_spec(self, task_id: str) -> TaskSpec:
        """Load the :class:`TaskSpec` for *task_id*."""
        path = self.task_dir(task_id) / "spec.json"
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return TaskSpec(**data)

    def read_runtime(self, task_id: str) -> TaskRuntime:
        """Load the :class:`TaskRuntime` for *task_id*."""
        path = self.task_dir(task_id) / "runtime.json"
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return TaskRuntime(**data)

    def write_runtime(self, task_id: str, runtime: TaskRuntime) -> None:
        """Persist updated :class:`TaskRuntime` for *task_id*."""
        path = self.task_dir(task_id) / "runtime.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(runtime), fh, indent=2, default=str)

    # -- output reading ------------------------------------------------------

    def read_output(
        self,
        task_id: str,
        offset: int = 0,
        max_bytes: int = 32 * 1024,
    ) -> TaskOutputChunk:
        """Read up to *max_bytes* of output starting at *offset*.

        Returns:
            A :class:`TaskOutputChunk` with the text and next offset.
        """
        path = self.task_dir(task_id) / "output.log"
        if not path.exists():
            return TaskOutputChunk(text="", offset=0, next_offset=0)

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            text = fh.read(max_bytes)
            next_offset = fh.tell()

        return TaskOutputChunk(text=text, offset=offset, next_offset=next_offset)

    def tail_output(
        self,
        task_id: str,
        max_bytes: int = 32 * 1024,
        max_lines: int = 50,
    ) -> str:
        """Return the last *max_lines* lines of output, bounded by *max_bytes*.

        This is useful for notifications where only the tail is relevant.
        """
        path = self.task_dir(task_id) / "output.log"
        if not path.exists():
            return ""

        try:
            size = path.stat().st_size
        except OSError:
            return ""

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                # Discard the first (likely partial) line
                fh.readline()

            lines: list[str] = []
            for line in fh:
                lines.append(line.rstrip("\n"))

        # Return the last *max_lines* lines
        if len(lines) > max_lines:
            lines = lines[-max_lines:]

        return "\n".join(lines)

    # -- paths ---------------------------------------------------------------

    def output_path(self, task_id: str) -> Path:
        """Return the :class:`Path` to the output log for *task_id*."""
        return self.task_dir(task_id) / "output.log"

    # -- listing / views -----------------------------------------------------

    def list_task_ids(self) -> list[str]:
        """Return all task IDs stored on disk."""
        if not self._root.exists():
            return []
        return [d.name for d in self._root.iterdir() if d.is_dir()]

    def list_views(self) -> list[TaskView]:
        """Return a list of :class:`TaskView` for all tasks, sorted newest first."""
        views: list[TaskView] = []
        for task_id in self.list_task_ids():
            try:
                spec = self.read_spec(task_id)
                runtime = self.read_runtime(task_id)
                views.append(TaskView(spec=spec, runtime=runtime))
            except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
                # Skip corrupted / partially-written task directories
                continue
        views.sort(key=lambda v: v.spec.created_at, reverse=True)
        return views

    def merged_view(self, task_id: str) -> TaskView:
        """Return a :class:`TaskView` for *task_id*.

        Raises:
            FileNotFoundError: If the task does not exist.
        """
        spec = self.read_spec(task_id)
        runtime = self.read_runtime(task_id)
        return TaskView(spec=spec, runtime=runtime)


# ── Utility functions ─────────────────────────────────────────────────────────


def is_terminal_status(status: str) -> bool:
    """Return ``True`` if *status* is a terminal (finished) state."""
    return status in TERMINAL_STATUSES


def generate_task_id(kind: str) -> str:
    """Generate a short unique task ID like ``bash-a1b2c3d4``."""
    return f"{kind}-{uuid.uuid4().hex[:8]}"


def format_task(view: TaskView, *, include_command: bool = False) -> str:
    """Format a single task view as a human-readable string.

    Parameters:
        view: The task view to format.
        include_command: Whether to include the shell command line.
    """
    lines = [
        f"task_id: {view.spec.id}",
        f"kind: {view.spec.kind}",
        f"status: {view.runtime.status}",
        f"description: {view.spec.description}",
    ]
    if include_command and view.spec.command:
        lines.append(f"command: {view.spec.command}")
    return "\n".join(lines)


def format_task_list(
    views: list[TaskView],
    *,
    active_only: bool = True,
) -> str:
    """Format a list of task views as a human-readable string.

    Parameters:
        views: List of task views to format.
        active_only: Whether the list contains only active tasks (affects header).
    """
    if not views:
        return "No background tasks."

    lines = [f"Background tasks ({'active' if active_only else 'all'}):"]
    status_icon: dict[str, str] = {
        "running": "▶",
        "starting": "⟳",
        "created": "○",
        "completed": "✓",
        "failed": "✗",
        "killed": "■",
        "lost": "?",
    }
    for view in views:
        icon = status_icon.get(view.runtime.status, "?")
        lines.append(
            f"  {icon} {view.spec.id} [{view.spec.kind}] {view.spec.description}"
        )
    return "\n".join(lines)


def list_task_views(
    manager: BackgroundTaskManager,
    *,
    active_only: bool = True,
    limit: int = 20,
) -> list[TaskView]:
    """Convenience wrapper to list task views from a manager.

    Parameters:
        manager: The :class:`BackgroundTaskManager` instance.
        active_only: If ``True``, only return non-terminal tasks.
        limit: Maximum number of tasks to return.
    """
    return manager.list_tasks(active_only=active_only, limit=limit)


# ── BackgroundTaskManager ─────────────────────────────────────────────────────


class BackgroundTaskManager:
    """Manages background tasks with persistence and recovery.

    Parameters:
        session_dir: Root directory for the current session.  Task data is
            stored in ``<session_dir>/tasks/``.
        config: Optional override for default configuration values.
        notifications: Optional callback/queue for terminal notifications.
    """

    def __init__(
        self,
        session_dir: str,
        config: dict[str, int] | None = None,
        notifications: Any | None = None,
    ) -> None:
        self._session_dir = Path(session_dir)
        self._store = BackgroundTaskStore(self._session_dir / "tasks")
        self._config = {**DEFAULT_MANAGER_CONFIG, **(config or {})}
        self._notifications = notifications
        self._live_tasks: dict[str, asyncio.Task] = {}
        self._completion_event = asyncio.Event()

    # -- properties ----------------------------------------------------------

    @property
    def store(self) -> BackgroundTaskStore:
        """The underlying :class:`BackgroundTaskStore`."""
        return self._store

    @property
    def completion_event(self) -> asyncio.Event:
        """Event that is set whenever a task reaches a terminal state."""
        return self._completion_event

    # -- internal helpers ----------------------------------------------------

    def _active_task_count(self) -> int:
        return sum(
            1
            for view in self._store.list_views()
            if not is_terminal_status(view.runtime.status)
        )

    def has_active_tasks(self) -> bool:
        """Return ``True`` if any non-terminal tasks exist."""
        return self._active_task_count() > 0

    # -- task creation -------------------------------------------------------

    def create_bash_task(
        self,
        command: str,
        description: str,
        *,
        timeout_s: int = 300,
        tool_call_id: str = "",
        shell_name: str = "bash",
        shell_path: str = "/bin/bash",
        cwd: str | None = None,
    ) -> TaskView:
        """Create and launch a background bash task.

        Parameters:
            command: Shell command to execute.
            description: Human-readable description.
            timeout_s: Maximum execution time in seconds.
            tool_call_id: Optional triggering tool call ID.
            shell_name: Display name for the shell.
            shell_path: Absolute path to the shell binary.
            cwd: Working directory (defaults to ``os.getcwd()``).

        Returns:
            The :class:`TaskView` of the newly created task.

        Raises:
            RuntimeError: If the number of active tasks already exceeds
                ``max_running_tasks``.
        """
        if self._active_task_count() >= self._config["max_running_tasks"]:
            raise RuntimeError("Too many background tasks are already running.")

        task_id = generate_task_id("bash")
        spec = TaskSpec(
            id=task_id,
            kind="bash",
            session_id=str(self._session_dir.name),
            description=description,
            command=command,
            timeout_s=timeout_s,
            tool_call_id=tool_call_id,
            kind_payload={
                "shell_name": shell_name,
                "shell_path": shell_path,
                "cwd": cwd or str(os.getcwd()),
            },
        )
        self._store.create_task(spec)

        # Launch worker process
        task_dir = self._store.task_dir(task_id)
        try:
            worker_pid = self._launch_worker(
                task_dir, command, cwd or str(os.getcwd()), timeout_s
            )
        except Exception as exc:
            runtime = self._store.read_runtime(task_id)
            runtime.status = "failed"
            runtime.failure_reason = f"Failed to launch worker: {exc}"
            runtime.finished_at = time.time()
            runtime.updated_at = runtime.finished_at
            self._store.write_runtime(task_id, runtime)
            raise

        runtime = self._store.read_runtime(task_id)
        runtime.status = "starting"
        runtime.worker_pid = worker_pid
        runtime.updated_at = time.time()
        self._store.write_runtime(task_id, runtime)

        return self._store.merged_view(task_id)

    def _launch_worker(
        self,
        task_dir: Path,
        command: str,
        cwd: str,
        timeout_s: int,
    ) -> int:
        """Launch a worker subprocess and return its PID.

        The worker runs the command via the current Python interpreter so that
        environment variables (``DULUS_BG_TASK``, ``DULUS_BG_TIMEOUT``) are
        injected and the process can be tracked.
        """
        env = os.environ.copy()
        env["DULUS_BG_TASK"] = "1"
        env["DULUS_BG_TIMEOUT"] = str(timeout_s)

        # Escape single quotes in the command to avoid breaking the wrapper
        safe_command = command.replace("'", "'\"'\"'")
        script = f"cd '{cwd}' && {safe_command}"

        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": open(task_dir / "output.log", "w", encoding="utf-8"),
            "stderr": subprocess.STDOUT,
            "cwd": cwd,
            "env": env,
        }

        if os.name != "nt":
            kwargs["start_new_session"] = True

        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"import subprocess, sys; sys.exit(subprocess.call('{script}', shell=True))",
            ],
            **kwargs,
        )
        return process.pid

    # -- task queries --------------------------------------------------------

    def list_tasks(
        self,
        *,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[TaskView]:
        """List task views.

        Parameters:
            active_only: If ``True``, filter out terminal-status tasks.
            limit: Maximum number of results.

        Returns:
            Sorted list of :class:`TaskView` (newest first).
        """
        views = self._store.list_views()
        if active_only:
            views = [v for v in views if not is_terminal_status(v.runtime.status)]
        return views[:limit]

    def get_task(self, task_id: str) -> TaskView | None:
        """Return the :class:`TaskView` for *task_id*, or ``None`` if not found."""
        try:
            return self._store.merged_view(task_id)
        except (FileNotFoundError, ValueError):
            return None

    # -- task control --------------------------------------------------------

    def kill(self, task_id: str, *, reason: str = "Killed by user") -> TaskView:
        """Kill a running task and mark it as ``killed``.

        Parameters:
            task_id: The task to kill.
            reason: Human-readable reason for the kill.

        Returns:
            Updated :class:`TaskView` after the kill operation.
        """
        view = self._store.merged_view(task_id)
        if is_terminal_status(view.runtime.status):
            return view

        if view.runtime.worker_pid:
            try:
                if os.name == "nt":
                    subprocess.run(
                        [
                            "taskkill",
                            "/PID",
                            str(view.runtime.worker_pid),
                            "/T",
                            "/F",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    os.kill(view.runtime.worker_pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass  # Process already gone

        runtime = view.runtime
        runtime.status = "killed"
        runtime.finished_at = time.time()
        runtime.updated_at = runtime.finished_at
        runtime.interrupted = True
        runtime.failure_reason = reason
        self._store.write_runtime(task_id, runtime)

        return self._store.merged_view(task_id)

    def kill_all_active(self, *, reason: str = "Session ended") -> list[str]:
        """Kill all tasks that are not in a terminal state.

        Parameters:
            reason: Human-readable reason for the mass kill.

        Returns:
            List of task IDs that were killed.
        """
        killed: list[str] = []
        for view in self._store.list_views():
            if not is_terminal_status(view.runtime.status):
                try:
                    self.kill(view.spec.id, reason=reason)
                    killed.append(view.spec.id)
                except Exception:
                    pass
        return killed

    # -- async waiting -------------------------------------------------------

    async def wait(self, task_id: str, *, timeout_s: float = 30.0) -> TaskView:
        """Poll until *task_id* reaches a terminal status or *timeout_s* elapses.

        Parameters:
            task_id: Task to wait for.
            timeout_s: Maximum seconds to wait.

        Returns:
            The :class:`TaskView` at the time of return (may still be active
            if the timeout was hit).
        """
        end_time = time.monotonic() + timeout_s
        poll_interval = self._config["wait_poll_interval_ms"] / 1000

        while True:
            view = self._store.merged_view(task_id)
            if is_terminal_status(view.runtime.status):
                return view
            if time.monotonic() >= end_time:
                return view
            await asyncio.sleep(poll_interval)

    # -- output access -------------------------------------------------------

    def read_output(
        self,
        task_id: str,
        offset: int = 0,
        max_bytes: int | None = None,
    ) -> TaskOutputChunk:
        """Read task output starting at *offset*."""
        max_b = max_bytes if max_bytes is not None else self._config["read_max_bytes"]
        return self._store.read_output(task_id, offset, max_b)

    def tail_output(
        self,
        task_id: str,
        max_bytes: int | None = None,
        max_lines: int | None = None,
    ) -> str:
        """Return the tail of the task output log."""
        max_b = max_bytes if max_bytes is not None else self._config["read_max_bytes"]
        max_l = max_lines if max_lines is not None else self._config["notification_tail_lines"]
        return self._store.tail_output(task_id, max_bytes=max_b, max_lines=max_l)

    def resolve_output_path(self, task_id: str) -> Path:
        """Return the filesystem path to the output log for *task_id*."""
        return self._store.output_path(task_id)

    # -- recovery / reconciliation -------------------------------------------

    def recover(self) -> None:
        """Mark stale non-terminal tasks as ``lost``.

        A task is considered stale when no heartbeat (or start/update) has
        been seen for longer than ``worker_stale_after_ms``.
        """
        now = time.time()
        stale_after = self._config["worker_stale_after_ms"] / 1000

        for view in self._store.list_views():
            if is_terminal_status(view.runtime.status):
                continue

            last_progress = (
                view.runtime.heartbeat_at
                or view.runtime.started_at
                or view.runtime.updated_at
                or view.spec.created_at
            )
            if last_progress is None:
                last_progress = view.spec.created_at

            if now - last_progress <= stale_after:
                continue

            runtime = view.runtime
            runtime.finished_at = now
            runtime.updated_at = now
            if runtime.interrupted:
                runtime.status = "killed"
            else:
                runtime.status = "lost"
                runtime.failure_reason = "Background worker heartbeat expired"
            self._store.write_runtime(view.spec.id, runtime)

    def reconcile(self) -> list[str]:
        """Run recovery and publish terminal notifications.

        Returns:
            List of task IDs that were published as terminal.
        """
        self.recover()
        return self._publish_terminal_notifications()

    def _publish_terminal_notifications(self) -> list[str]:
        """Signal the completion event for all terminal tasks."""
        published: list[str] = []
        for view in self._store.list_views():
            if not is_terminal_status(view.runtime.status):
                continue
            published.append(view.spec.id)
            self._completion_event.set()
        return published


# ── BackgroundAgentRunner ─────────────────────────────────────────────────────


class BackgroundAgentRunner:
    """Runs a sub-agent task in the background.

    This class encapsulates the lifecycle of an agent-type background task:
    marking it as running, executing the agent, and recording the result.

    The :meth:`_execute_agent` method is a placeholder that should be
    overridden or replaced with a real agent invocation in production.

    Parameters:
        task_id: Unique task identifier.
        prompt: The prompt / instruction to send to the sub-agent.
        model: Optional model override.
        timeout_s: Maximum execution time in seconds.
        session_dir: Session directory (used to locate the task store).
    """

    def __init__(
        self,
        task_id: str,
        prompt: str,
        model: str | None = None,
        timeout_s: int = 300,
        session_dir: str | None = None,
    ) -> None:
        self._task_id = task_id
        self._prompt = prompt
        self._model = model
        self._timeout_s = timeout_s
        self._session_dir = session_dir
        self._store = (
            BackgroundTaskStore(Path(session_dir) / "tasks")
            if session_dir
            else None
        )

    async def run(self) -> None:
        """Run the background agent task.

        This coroutine:
        1. Marks the task as ``running``.
        2. Calls :meth:`_execute_agent` (with timeout).
        3. Marks the task as ``completed`` or ``failed``.

        If the store is not available, this is a no-op.
        """
        if self._store is None:
            return

        # Mark as running
        runtime = self._store.read_runtime(self._task_id)
        runtime.status = "running"
        runtime.started_at = time.time()
        runtime.updated_at = runtime.started_at
        self._store.write_runtime(self._task_id, runtime)

        try:
            result = await asyncio.wait_for(
                self._execute_agent(),
                timeout=self._timeout_s,
            )

            # Write result to output log
            output_path = self._store.output_path(self._task_id)
            with open(output_path, "a", encoding="utf-8") as fh:
                fh.write(f"\n{result}\n")

            # Mark as completed
            runtime = self._store.read_runtime(self._task_id)
            runtime.status = "completed"
            runtime.finished_at = time.time()
            runtime.updated_at = runtime.finished_at
            runtime.exit_code = 0
            self._store.write_runtime(self._task_id, runtime)

        except asyncio.TimeoutError:
            runtime = self._store.read_runtime(self._task_id)
            runtime.status = "failed"
            runtime.finished_at = time.time()
            runtime.timed_out = True
            runtime.failure_reason = f"Task timed out after {self._timeout_s}s"
            self._store.write_runtime(self._task_id, runtime)

        except Exception as exc:
            runtime = self._store.read_runtime(self._task_id)
            runtime.status = "failed"
            runtime.finished_at = time.time()
            runtime.failure_reason = str(exc)
            self._store.write_runtime(self._task_id, runtime)

    async def _execute_agent(self) -> str:
        """Execute the agent with the prompt.

        .. note::
            This is a **placeholder** — override or monkey-patch with a real
            agent call for production use.

        Returns:
            A string result from the agent.
        """
        await asyncio.sleep(0.01)  # Minimal yield to simulate async work
        return f"Task completed: {self._prompt[:50]}..."
