"""Tests for the dulus.background_tasks module (Features 14-15).

Covers BackgroundTaskStore, BackgroundTaskManager, BackgroundAgentRunner,
and all utility functions.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# The module lives at dulus_tools/background_tasks.py
from dulus_tools.background_tasks import (
    BackgroundAgentRunner,
    BackgroundTaskManager,
    BackgroundTaskStore,
    TaskOutputChunk,
    TaskRuntime,
    TaskSpec,
    TaskView,
    DEFAULT_MANAGER_CONFIG,
    TERMINAL_STATUSES,
    NON_TERMINAL_STATUSES,
    format_task,
    format_task_list,
    generate_task_id,
    is_terminal_status,
    list_task_views,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_store(tmp_path: Path) -> BackgroundTaskStore:
    """Return a fresh BackgroundTaskStore backed by a temp directory."""
    return BackgroundTaskStore(tmp_path / "task_store")


@pytest.fixture
def tmp_manager(tmp_path: Path) -> BackgroundTaskManager:
    """Return a fresh BackgroundTaskManager with a temp session directory."""
    return BackgroundTaskManager(str(tmp_path / "session"))


@pytest.fixture
def sample_spec() -> TaskSpec:
    """Return a sample TaskSpec for testing."""
    return TaskSpec(
        id="bash-abc12345",
        kind="bash",
        session_id="test-session",
        description="A sample task",
        command="echo hello",
        timeout_s=60,
    )


# ── Utility function tests ────────────────────────────────────────────────────


class TestUtilityFunctions:
    """Tests for module-level helper functions."""

    def test_is_terminal_status_true(self) -> None:
        for status in TERMINAL_STATUSES:
            assert is_terminal_status(status) is True

    def test_is_terminal_status_false(self) -> None:
        for status in NON_TERMINAL_STATUSES:
            assert is_terminal_status(status) is False

    def test_generate_task_id_format(self) -> None:
        tid = generate_task_id("bash")
        assert tid.startswith("bash-")
        assert len(tid) == len("bash-") + 8  # 8 hex chars

    def test_generate_task_id_unique(self) -> None:
        ids = {generate_task_id("bash") for _ in range(100)}
        assert len(ids) == 100

    def test_format_task_basic(self) -> None:
        view = TaskView(
            spec=TaskSpec(id="bash-123", kind="bash", session_id="s", description="d"),
            runtime=TaskRuntime(status="running"),
        )
        text = format_task(view)
        assert "bash-123" in text
        assert "running" in text
        assert "d" in text
        assert "command" not in text

    def test_format_task_with_command(self) -> None:
        view = TaskView(
            spec=TaskSpec(
                id="bash-123", kind="bash", session_id="s",
                description="d", command="echo hi",
            ),
            runtime=TaskRuntime(status="running"),
        )
        text = format_task(view, include_command=True)
        assert "echo hi" in text

    def test_format_task_list_empty(self) -> None:
        assert format_task_list([]) == "No background tasks."

    def test_format_task_list_with_items(self) -> None:
        views = [
            TaskView(
                spec=TaskSpec(id=f"bash-{i:02d}", kind="bash", session_id="s", description=f"task {i}"),
                runtime=TaskRuntime(status=status),
            )
            for i, status in enumerate(["running", "completed", "failed"])
        ]
        text = format_task_list(views, active_only=True)
        assert "bash-00" in text
        assert "▶" in text
        assert "✓" in text
        assert "✗" in text


# ── BackgroundTaskStore tests ─────────────────────────────────────────────────


class TestBackgroundTaskStore:
    """Tests for BackgroundTaskStore persistence layer."""

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        root = tmp_path / "new_store"
        assert not root.exists()
        store = BackgroundTaskStore(root)
        assert root.is_dir()

    def test_task_dir(self, tmp_store: BackgroundTaskStore) -> None:
        d = tmp_store.task_dir("foo")
        assert d.name == "foo"
        assert d.parent == tmp_store._root

    def test_create_task_writes_files(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        task_dir = tmp_store.task_dir(sample_spec.id)
        assert (task_dir / "spec.json").exists()
        assert (task_dir / "runtime.json").exists()
        assert (task_dir / "output.log").exists()

    def test_create_task_runtime_defaults(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        runtime = tmp_store.read_runtime(sample_spec.id)
        assert runtime.status == "created"
        assert runtime.worker_pid is None

    def test_read_spec_roundtrip(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        spec = tmp_store.read_spec(sample_spec.id)
        assert spec.id == sample_spec.id
        assert spec.kind == sample_spec.kind
        assert spec.command == sample_spec.command

    def test_write_runtime_and_read_back(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        runtime = tmp_store.read_runtime(sample_spec.id)
        runtime.status = "running"
        runtime.worker_pid = 12345
        tmp_store.write_runtime(sample_spec.id, runtime)

        runtime2 = tmp_store.read_runtime(sample_spec.id)
        assert runtime2.status == "running"
        assert runtime2.worker_pid == 12345

    def test_read_output_empty(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        chunk = tmp_store.read_output(sample_spec.id)
        assert chunk.text == ""
        assert chunk.offset == 0
        assert chunk.next_offset == 0

    def test_read_output_with_content(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        log_path = tmp_store.output_path(sample_spec.id)
        log_path.write_text("line1\nline2\n", encoding="utf-8")

        chunk = tmp_store.read_output(sample_spec.id, offset=0, max_bytes=1024)
        assert "line1" in chunk.text
        assert "line2" in chunk.text
        assert chunk.offset == 0
        assert chunk.next_offset > 0

    def test_read_output_offset_pagination(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        log_path = tmp_store.output_path(sample_spec.id)
        log_path.write_text("Hello, world!", encoding="utf-8")

        chunk1 = tmp_store.read_output(sample_spec.id, offset=0, max_bytes=5)
        assert chunk1.text == "Hello"
        assert chunk1.next_offset == 5

        chunk2 = tmp_store.read_output(sample_spec.id, offset=chunk1.next_offset, max_bytes=10)
        assert ", world!" in chunk2.text

    def test_tail_output_basic(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        log_path = tmp_store.output_path(sample_spec.id)
        log_path.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")

        tail = tmp_store.tail_output(sample_spec.id, max_lines=3)
        assert "c" in tail
        assert "d" in tail
        assert "e" in tail
        assert "a" not in tail

    def test_tail_output_exceeds_max_bytes(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        log_path = tmp_store.output_path(sample_spec.id)
        # Write a large line
        log_path.write_text("x" * 100_000 + "\nLAST_LINE\n", encoding="utf-8")

        tail = tmp_store.tail_output(sample_spec.id, max_bytes=1000, max_lines=10)
        assert "x" not in tail  # Should be skipped due to max_bytes window
        assert "LAST_LINE" in tail

    def test_tail_output_missing_file(self, tmp_store: BackgroundTaskStore) -> None:
        # Task directory doesn't exist
        result = tmp_store.tail_output("nonexistent")
        assert result == ""

    def test_list_task_ids(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        ids = tmp_store.list_task_ids()
        assert sample_spec.id in ids

    def test_list_views(self, tmp_store: BackgroundTaskStore) -> None:
        spec1 = TaskSpec(id="bash-111", kind="bash", session_id="s", description="first")
        spec2 = TaskSpec(id="bash-222", kind="bash", session_id="s", description="second")
        tmp_store.create_task(spec1)
        tmp_store.create_task(spec2)

        views = tmp_store.list_views()
        assert len(views) == 2
        # Should be sorted newest first
        assert views[0].spec.created_at >= views[1].spec.created_at

    def test_list_views_skips_corrupted(self, tmp_store: BackgroundTaskStore) -> None:
        # Create a task dir with corrupted runtime.json
        task_dir = tmp_store.task_dir("corrupted-task")
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "spec.json").write_text("{}", encoding="utf-8")
        (task_dir / "runtime.json").write_text("not-json{{{", encoding="utf-8")

        views = tmp_store.list_views()
        assert len(views) == 0  # Skips corrupted entry

    def test_merged_view(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        tmp_store.create_task(sample_spec)
        view = tmp_store.merged_view(sample_spec.id)
        assert view.spec.id == sample_spec.id
        assert view.runtime.status == "created"

    def test_merged_view_not_found(self, tmp_store: BackgroundTaskStore) -> None:
        with pytest.raises(FileNotFoundError):
            tmp_store.merged_view("nonexistent")

    def test_output_path(self, tmp_store: BackgroundTaskStore) -> None:
        path = tmp_store.output_path("my-task")
        assert path.name == "output.log"
        assert path.parent.name == "my-task"

    def test_kind_payload_roundtrip(self, tmp_store: BackgroundTaskStore) -> None:
        spec = TaskSpec(
            id="bash-kp", kind="bash", session_id="s", description="d",
            kind_payload={"shell_name": "zsh", "shell_path": "/usr/bin/zsh", "cwd": "/tmp"},
        )
        tmp_store.create_task(spec)
        spec2 = tmp_store.read_spec(spec.id)
        assert spec2.kind_payload["shell_name"] == "zsh"
        assert spec2.kind_payload["cwd"] == "/tmp"


# ── BackgroundTaskManager tests ───────────────────────────────────────────────


class TestBackgroundTaskManager:
    """Tests for BackgroundTaskManager lifecycle and operations."""

    def test_init_creates_store(self, tmp_path: Path) -> None:
        session = tmp_path / "session"
        mgr = BackgroundTaskManager(str(session))
        assert mgr.store is not None
        assert (session / "tasks").is_dir()

    def test_default_config(self, tmp_manager: BackgroundTaskManager) -> None:
        for key, value in DEFAULT_MANAGER_CONFIG.items():
            assert tmp_manager._config[key] == value

    def test_custom_config_override(self, tmp_path: Path) -> None:
        mgr = BackgroundTaskManager(str(tmp_path / "session"), config={"max_running_tasks": 10})
        assert mgr._config["max_running_tasks"] == 10
        assert mgr._config["agent_task_timeout_s"] == DEFAULT_MANAGER_CONFIG["agent_task_timeout_s"]

    def test_has_active_tasks_empty(self, tmp_manager: BackgroundTaskManager) -> None:
        assert tmp_manager.has_active_tasks() is False

    def test_create_bash_task_returns_view(self, tmp_manager: BackgroundTaskManager) -> None:
        # Mock _launch_worker to avoid actually spawning a process
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hello", "Say hello")

        assert view.spec.id.startswith("bash-")
        assert view.spec.kind == "bash"
        assert view.spec.command == "echo hello"
        assert view.spec.description == "Say hello"
        assert view.runtime.status == "starting"
        assert view.runtime.worker_pid == 12345

    def test_create_bash_task_persists(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hello", "Say hello")

        # Verify on disk
        view2 = tmp_manager.get_task(view.spec.id)
        assert view2 is not None
        assert view2.spec.command == "echo hello"

    def test_create_bash_task_max_limit(self, tmp_manager: BackgroundTaskManager) -> None:
        tmp_manager._config["max_running_tasks"] = 2

        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            tmp_manager.create_bash_task("echo 1", "task 1")
            tmp_manager.create_bash_task("echo 2", "task 2")

            # Third task should fail
            with pytest.raises(RuntimeError, match="Too many background tasks"):
                tmp_manager.create_bash_task("echo 3", "task 3")

    def test_create_bash_task_launch_failure(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", side_effect=OSError("fork failed")):
            with pytest.raises(OSError, match="fork failed"):
                tmp_manager.create_bash_task("echo hello", "Say hello")

        # Task should be marked as failed
        views = tmp_manager.list_tasks(active_only=False)
        assert len(views) == 1
        assert views[0].runtime.status == "failed"
        assert "fork failed" in views[0].runtime.failure_reason

    def test_get_task_found(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hi", "hi")

        fetched = tmp_manager.get_task(view.spec.id)
        assert fetched is not None
        assert fetched.spec.id == view.spec.id

    def test_get_task_not_found(self, tmp_manager: BackgroundTaskManager) -> None:
        assert tmp_manager.get_task("nonexistent") is None

    def test_list_tasks_active_only(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            v1 = tmp_manager.create_bash_task("echo 1", "task 1")
            v2 = tmp_manager.create_bash_task("echo 2", "task 2")

        # Mark one as completed
        runtime = tmp_manager.store.read_runtime(v1.spec.id)
        runtime.status = "completed"
        runtime.finished_at = time.time()
        tmp_manager.store.write_runtime(v1.spec.id, runtime)

        active = tmp_manager.list_tasks(active_only=True)
        assert len(active) == 1
        assert active[0].spec.id == v2.spec.id

    def test_list_tasks_all(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            v1 = tmp_manager.create_bash_task("echo 1", "task 1")

        # Mark as completed
        runtime = tmp_manager.store.read_runtime(v1.spec.id)
        runtime.status = "completed"
        runtime.finished_at = time.time()
        tmp_manager.store.write_runtime(v1.spec.id, runtime)

        all_tasks = tmp_manager.list_tasks(active_only=False)
        assert len(all_tasks) == 1

    def test_list_tasks_limit(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            for i in range(5):
                tmp_manager.create_bash_task(f"echo {i}", f"task {i}")

        results = tmp_manager.list_tasks(active_only=True, limit=3)
        assert len(results) == 3

    def test_kill_existing_task(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("sleep 10", "long task")

        if os.name == "nt":
            with patch("subprocess.run") as mock_run:
                killed = tmp_manager.kill(view.spec.id, reason="Test kill")
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "taskkill" in args
            assert "/PID" in args
            assert "12345" in args
        else:
            with patch("os.kill") as mock_kill:
                killed = tmp_manager.kill(view.spec.id, reason="Test kill")
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)

        assert killed.runtime.status == "killed"
        assert killed.runtime.interrupted is True
        assert killed.runtime.failure_reason == "Test kill"
        assert killed.runtime.finished_at is not None

    def test_kill_already_terminal(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hi", "hi")

        # Mark as completed
        runtime = tmp_manager.store.read_runtime(view.spec.id)
        runtime.status = "completed"
        tmp_manager.store.write_runtime(view.spec.id, runtime)

        # Kill should be a no-op
        result = tmp_manager.kill(view.spec.id)
        assert result.runtime.status == "completed"

    def test_kill_missing_process(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("sleep 10", "long task")

        with patch("os.kill", side_effect=ProcessLookupError("No such process")):
            killed = tmp_manager.kill(view.spec.id)

        assert killed.runtime.status == "killed"

    def test_kill_all_active(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            v1 = tmp_manager.create_bash_task("sleep 10", "task 1")
            v2 = tmp_manager.create_bash_task("sleep 10", "task 2")

        with patch("os.kill"):
            killed_ids = tmp_manager.kill_all_active(reason="Cleanup")

        assert len(killed_ids) == 2
        assert v1.spec.id in killed_ids
        assert v2.spec.id in killed_ids

    @pytest.mark.asyncio
    async def test_wait_reaches_terminal(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hi", "hi")

        # Simulate task completing in background
        async def complete_task():
            await asyncio.sleep(0.1)
            runtime = tmp_manager.store.read_runtime(view.spec.id)
            runtime.status = "completed"
            runtime.finished_at = time.time()
            tmp_manager.store.write_runtime(view.spec.id, runtime)

        asyncio.create_task(complete_task())
        result = await tmp_manager.wait(view.spec.id, timeout_s=5.0)
        assert result.runtime.status == "completed"

    @pytest.mark.asyncio
    async def test_wait_times_out(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("sleep 100", "long task")

        # Task never completes, wait should timeout
        result = await tmp_manager.wait(view.spec.id, timeout_s=0.1)
        # Should still be starting/running
        assert not is_terminal_status(result.runtime.status)

    def test_read_output(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hello", "Say hello")

        log_path = tmp_manager.resolve_output_path(view.spec.id)
        log_path.write_text("output line 1\noutput line 2\n", encoding="utf-8")

        chunk = tmp_manager.read_output(view.spec.id, offset=0)
        assert "output line 1" in chunk.text
        assert chunk.next_offset > 0

    def test_tail_output(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hello", "Say hello")

        log_path = tmp_manager.resolve_output_path(view.spec.id)
        log_path.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")

        tail = tmp_manager.tail_output(view.spec.id, max_lines=2)
        assert "d" in tail
        assert "e" in tail
        assert "a" not in tail

    def test_resolve_output_path(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hi", "hi")

        path = tmp_manager.resolve_output_path(view.spec.id)
        assert path.name == "output.log"
        assert path.exists()

    def test_launch_worker_creates_subprocess(self, tmp_manager: BackgroundTaskManager) -> None:
        # Actually test subprocess creation (will create a real process)
        view = tmp_manager.create_bash_task("echo 'HELLO_FROM_TEST'", "test echo")
        assert view.runtime.worker_pid is not None
        assert view.runtime.worker_pid > 0

        # Wait a bit for the process to complete
        time.sleep(0.5)

        # Check output
        chunk = tmp_manager.read_output(view.spec.id)
        assert "HELLO_FROM_TEST" in chunk.text

    def test_launch_worker_with_cwd(self, tmp_manager: BackgroundTaskManager, tmp_path: Path) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        view = tmp_manager.create_bash_task("pwd", "test cwd", cwd=str(subdir))
        time.sleep(0.5)

        chunk = tmp_manager.read_output(view.spec.id)
        assert str(subdir) in chunk.text

    def test_recovery_marks_stale_tasks(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("sleep 100", "stale task")

        # Make the task look old by setting created_at far in the past
        # and also updating runtime.updated_at
        spec = tmp_manager.store.read_spec(view.spec.id)
        spec.created_at = time.time() - 99999  # Very old
        task_dir = tmp_manager.store.task_dir(view.spec.id)
        with open(task_dir / "spec.json", "w", encoding="utf-8") as fh:
            json.dump(spec.__dict__, fh, indent=2, default=str)

        runtime = tmp_manager.store.read_runtime(view.spec.id)
        runtime.updated_at = time.time() - 99999  # Also very old
        tmp_manager.store.write_runtime(view.spec.id, runtime)

        tmp_manager.recover()

        recovered = tmp_manager.get_task(view.spec.id)
        assert recovered.runtime.status == "lost"
        assert "heartbeat expired" in recovered.runtime.failure_reason

    def test_recovery_skips_fresh_tasks(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("sleep 100", "fresh task")

        tmp_manager.recover()

        recovered = tmp_manager.get_task(view.spec.id)
        # Should still be starting (not marked as lost)
        assert recovered.runtime.status == "starting"

    def test_recovery_respects_interrupted(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("sleep 100", "interrupted task")

        # Make it look old and interrupted
        spec = tmp_manager.store.read_spec(view.spec.id)
        spec.created_at = time.time() - 99999
        task_dir = tmp_manager.store.task_dir(view.spec.id)
        with open(task_dir / "spec.json", "w", encoding="utf-8") as fh:
            json.dump(spec.__dict__, fh, indent=2, default=str)

        runtime = tmp_manager.store.read_runtime(view.spec.id)
        runtime.interrupted = True
        runtime.updated_at = time.time() - 99999  # Also very old
        tmp_manager.store.write_runtime(view.spec.id, runtime)

        tmp_manager.recover()

        recovered = tmp_manager.get_task(view.spec.id)
        assert recovered.runtime.status == "killed"

    def test_reconcile_returns_terminal_ids(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("echo hi", "hi")

        # Mark as completed
        runtime = tmp_manager.store.read_runtime(view.spec.id)
        runtime.status = "completed"
        tmp_manager.store.write_runtime(view.spec.id, runtime)

        published = tmp_manager.reconcile()
        assert view.spec.id in published

    def test_list_task_views_wrapper(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            tmp_manager.create_bash_task("echo 1", "task 1")

        views = list_task_views(tmp_manager, active_only=True)
        assert len(views) == 1

    def test_kill_on_windows_fallback(self, tmp_manager: BackgroundTaskManager) -> None:
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            view = tmp_manager.create_bash_task("sleep 10", "task")

        with patch("os.name", "nt"):
            with patch("subprocess.run") as mock_run:
                tmp_manager.kill(view.spec.id)

        # On Windows, subprocess.run with taskkill should be called
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert "taskkill" in str(args)


# ── BackgroundAgentRunner tests ───────────────────────────────────────────────


class TestBackgroundAgentRunner:
    """Tests for BackgroundAgentRunner async task execution."""

    @pytest.mark.asyncio
    async def test_run_no_store_is_noop(self) -> None:
        runner = BackgroundAgentRunner("agent-1", "Do something", session_dir=None)
        await runner.run()  # Should not raise

    @pytest.mark.asyncio
    async def test_run_completes_successfully(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "session"
        store = BackgroundTaskStore(session_dir / "tasks")

        spec = TaskSpec(
            id="agent-123", kind="agent", session_id="test",
            description="Test agent task",
        )
        store.create_task(spec)

        runner = BackgroundAgentRunner(
            "agent-123", "Test prompt", session_dir=str(session_dir)
        )
        await runner.run()

        runtime = store.read_runtime("agent-123")
        assert runtime.status == "completed"
        assert runtime.exit_code == 0
        assert runtime.finished_at is not None

    @pytest.mark.asyncio
    async def test_run_writes_output(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "session"
        store = BackgroundTaskStore(session_dir / "tasks")

        spec = TaskSpec(
            id="agent-456", kind="agent", session_id="test",
            description="Test agent task",
        )
        store.create_task(spec)

        runner = BackgroundAgentRunner(
            "agent-456", "Test prompt", session_dir=str(session_dir)
        )
        await runner.run()

        output = store.tail_output("agent-456")
        assert "Task completed" in output

    @pytest.mark.asyncio
    async def test_run_timeout(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "session"
        store = BackgroundTaskStore(session_dir / "tasks")

        spec = TaskSpec(
            id="agent-789", kind="agent", session_id="test",
            description="Slow task",
        )
        store.create_task(spec)

        runner = BackgroundAgentRunner(
            "agent-789", "Slow prompt", timeout_s=0, session_dir=str(session_dir)
        )

        # Override _execute_agent to sleep longer than timeout
        async def slow_agent():
            await asyncio.sleep(10)
            return "too late"

        runner._execute_agent = slow_agent  # type: ignore[method-assign]

        await runner.run()

        runtime = store.read_runtime("agent-789")
        assert runtime.status == "failed"
        assert runtime.timed_out is True
        assert "timed out" in runtime.failure_reason

    @pytest.mark.asyncio
    async def test_run_exception_in_agent(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "session"
        store = BackgroundTaskStore(session_dir / "tasks")

        spec = TaskSpec(
            id="agent-err", kind="agent", session_id="test",
            description="Error task",
        )
        store.create_task(spec)

        runner = BackgroundAgentRunner(
            "agent-err", "Bad prompt", session_dir=str(session_dir)
        )

        async def failing_agent():
            raise ValueError("Simulated agent failure")

        runner._execute_agent = failing_agent  # type: ignore[method-assign]

        await runner.run()

        runtime = store.read_runtime("agent-err")
        assert runtime.status == "failed"
        assert "Simulated agent failure" in runtime.failure_reason

    @pytest.mark.asyncio
    async def test_run_marks_running(self, tmp_path: Path) -> None:
        session_dir = tmp_path / "session"
        store = BackgroundTaskStore(session_dir / "tasks")

        spec = TaskSpec(
            id="agent-run", kind="agent", session_id="test",
            description="Running state task",
        )
        store.create_task(spec)

        runner = BackgroundAgentRunner(
            "agent-run", "Test", session_dir=str(session_dir)
        )

        # Check that it transitions to running
        await runner.run()

        runtime = store.read_runtime("agent-run")
        assert runtime.started_at is not None
        assert runtime.status == "completed"


# ── Integration / edge-case tests ─────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_concurrent_task_count(self, tmp_manager: BackgroundTaskManager) -> None:
        """Verify that active task count is accurate with multiple tasks."""
        with patch.object(tmp_manager, "_launch_worker", return_value=12345):
            for i in range(3):
                tmp_manager.create_bash_task(f"echo {i}", f"task {i}")

        assert tmp_manager._active_task_count() == 3

        # Mark one as completed
        views = tmp_manager.list_tasks(active_only=True)
        runtime = tmp_manager.store.read_runtime(views[0].spec.id)
        runtime.status = "completed"
        runtime.finished_at = time.time()
        tmp_manager.store.write_runtime(views[0].spec.id, runtime)

        assert tmp_manager._active_task_count() == 2
        assert tmp_manager.has_active_tasks() is True

    def test_task_sort_order(self, tmp_store: BackgroundTaskStore) -> None:
        """Tasks should be listed newest first."""
        import time

        for i in range(5):
            spec = TaskSpec(
                id=f"bash-{i:02d}", kind="bash",
                session_id="s", description=f"task {i}",
            )
            spec.created_at = time.time() + i  # Ensure different timestamps
            tmp_store.create_task(spec)

        views = tmp_store.list_views()
        for i in range(len(views) - 1):
            assert views[i].spec.created_at >= views[i + 1].spec.created_at

    def test_empty_store_list_views(self, tmp_store: BackgroundTaskStore) -> None:
        """An empty store should return an empty list of views."""
        assert tmp_store.list_views() == []

    def test_empty_store_list_task_ids(self, tmp_store: BackgroundTaskStore) -> None:
        """An empty store should return an empty list of task IDs."""
        assert tmp_store.list_task_ids() == []

    def test_read_output_beyond_eof(self, tmp_store: BackgroundTaskStore, sample_spec: TaskSpec) -> None:
        """Reading beyond EOF should return empty text with same offset."""
        tmp_store.create_task(sample_spec)
        tmp_store.output_path(sample_spec.id).write_text("hi", encoding="utf-8")

        chunk = tmp_store.read_output(sample_spec.id, offset=1000, max_bytes=1024)
        assert chunk.text == ""
        assert chunk.offset == 1000
        assert chunk.next_offset == 1000

    def test_kill_all_active_with_no_active(self, tmp_manager: BackgroundTaskManager) -> None:
        """kill_all_active with no active tasks should return empty list."""
        result = tmp_manager.kill_all_active()
        assert result == []

    def test_wait_on_nonexistent_task(self, tmp_manager: BackgroundTaskManager) -> None:
        """Waiting on a nonexistent task should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            asyncio.run(tmp_manager.wait("nonexistent"))

    def test_task_id_prefix(self) -> None:
        """Generated task IDs should have the correct kind prefix."""
        bash_id = generate_task_id("bash")
        assert bash_id.startswith("bash-")

        agent_id = generate_task_id("agent")
        assert agent_id.startswith("agent-")

    def test_terminal_statuses_are_mutually_exclusive(self) -> None:
        """A status should not be both terminal and non-terminal."""
        intersection = TERMINAL_STATUSES & NON_TERMINAL_STATUSES
        assert intersection == set()

    def test_config_defaults_complete(self) -> None:
        """All config keys should have default values."""
        expected_keys = {
            "max_running_tasks",
            "agent_task_timeout_s",
            "worker_heartbeat_interval_ms",
            "wait_poll_interval_ms",
            "kill_grace_period_ms",
            "worker_stale_after_ms",
            "read_max_bytes",
            "notification_tail_lines",
        }
        assert set(DEFAULT_MANAGER_CONFIG.keys()) == expected_keys
