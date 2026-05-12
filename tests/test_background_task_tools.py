"""Tests for the Background Task tools (tools_background.py)."""
from __future__ import annotations

import threading
import time

import pytest

from tool_registry import get_tool, clear_registry

import tools_background


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset registry and task store before each test."""
    clear_registry()
    tools_background._register()
    # Reset the task store
    tools_background._task_store = None
    yield
    clear_registry()


class TestBgTaskListTool:
    """Test suite for the BgTaskList tool."""

    def test_tool_is_registered(self):
        """BgTaskList tool must be registered."""
        tool = get_tool("BgTaskList")
        assert tool is not None
        assert tool.name == "BgTaskList"

    def test_tool_is_read_only(self):
        """BgTaskList should be read-only."""
        tool = get_tool("BgTaskList")
        assert tool.read_only is True

    def test_tool_is_concurrent_safe(self):
        """BgTaskList should be safe to run concurrently."""
        tool = get_tool("BgTaskList")
        assert tool.concurrent_safe is True

    def test_empty_list(self):
        """Listing with no tasks should return empty message."""
        tool = get_tool("BgTaskList")
        result = tool.func({}, {})
        assert "no background tasks" in result.lower()

    def test_list_shows_tasks(self):
        """Listing should show added tasks."""
        store = tools_background.get_task_store()
        task = tools_background.BackgroundTask(
            task_id="abc123",
            description="Test task",
            kind="bash",
            status="running",
        )
        store.add_task(task)

        tool = get_tool("BgTaskList")
        result = tool.func({}, {})
        assert "abc123" in result
        assert "Test task" in result
        assert "bash" in result


class TestBgTaskOutputTool:
    """Test suite for the BgTaskOutput tool."""

    def test_tool_is_registered(self):
        """BgTaskOutput tool must be registered."""
        tool = get_tool("BgTaskOutput")
        assert tool is not None
        assert tool.name == "BgTaskOutput"

    def test_tool_is_read_only(self):
        """BgTaskOutput should be read-only."""
        tool = get_tool("BgTaskOutput")
        assert tool.read_only is True

    def test_output_for_missing_task(self):
        """Getting output for missing task should return error."""
        tool = get_tool("BgTaskOutput")
        result = tool.func({"task_id": "nonexistent"}, {})
        assert "error" in result.lower()
        assert "not found" in result.lower()

    def test_output_with_content(self):
        """Getting output should include stdout content."""
        store = tools_background.get_task_store()
        task = tools_background.BackgroundTask(
            task_id="task01",
            description="Output test",
            kind="python",
            status="running",
        )
        task.stdout_lines.append("Line 1\n")
        task.stdout_lines.append("Line 2\n")
        store.add_task(task)

        tool = get_tool("BgTaskOutput")
        result = tool.func({"task_id": "task01", "block": False}, {})
        assert "Line 1" in result
        assert "Line 2" in result

    def test_output_with_stderr(self):
        """Getting output should include stderr content."""
        store = tools_background.get_task_store()
        task = tools_background.BackgroundTask(
            task_id="task02",
            description="Stderr test",
            kind="bash",
            status="running",
        )
        task.stderr_lines.append("Error message\n")
        store.add_task(task)

        tool = get_tool("BgTaskOutput")
        result = tool.func({"task_id": "task02"}, {})
        assert "STDERR" in result
        assert "Error message" in result

    def test_output_no_block(self):
        """Non-blocking output should not wait."""
        store = tools_background.get_task_store()
        task = tools_background.BackgroundTask(
            task_id="task03",
            description="Running task",
            kind="bash",
            status="running",
        )
        store.add_task(task)

        tool = get_tool("BgTaskOutput")
        result = tool.func({"task_id": "task03", "block": False}, {})
        assert "running" in result.lower()

    def test_schema_has_task_id_required(self):
        """The schema should require 'task_id'."""
        tool = get_tool("BgTaskOutput")
        schema = tool.schema
        assert "task_id" in schema["input_schema"]["required"]
        assert "block" not in schema["input_schema"]["required"]


class TestBgTaskStopTool:
    """Test suite for the BgTaskStop tool."""

    def test_tool_is_registered(self):
        """BgTaskStop tool must be registered."""
        tool = get_tool("BgTaskStop")
        assert tool is not None
        assert tool.name == "BgTaskStop"

    def test_tool_is_not_read_only(self):
        """BgTaskStop should NOT be read-only (it stops tasks)."""
        tool = get_tool("BgTaskStop")
        assert tool.read_only is False

    def test_tool_is_not_concurrent_safe(self):
        """BgTaskStop should NOT be marked concurrent-safe."""
        tool = get_tool("BgTaskStop")
        assert tool.concurrent_safe is False

    def test_stop_missing_task(self):
        """Stopping a missing task should return error."""
        tool = get_tool("BgTaskStop")
        result = tool.func({"task_id": "nonexistent"}, {})
        assert "error" in result.lower()
        assert "not found" in result.lower()

    def test_stop_non_running_task(self):
        """Stopping a non-running task should report it's not running."""
        store = tools_background.get_task_store()
        task = tools_background.BackgroundTask(
            task_id="done01",
            description="Completed task",
            kind="bash",
            status="completed",
        )
        store.add_task(task)

        tool = get_tool("BgTaskStop")
        result = tool.func({"task_id": "done01"}, {})
        assert "not running" in result.lower()

    def test_stop_running_task(self):
        """Stopping a running task should succeed."""
        store = tools_background.get_task_store()
        task = tools_background.BackgroundTask(
            task_id="run01",
            description="Running task",
            kind="python",
            status="running",
        )
        store.add_task(task)

        tool = get_tool("BgTaskStop")
        result = tool.func({"task_id": "run01"}, {})
        assert "stopped" in result.lower()

    def test_force_stop(self):
        """Force stopping a task should report forceful stop."""
        store = tools_background.get_task_store()
        task = tools_background.BackgroundTask(
            task_id="force01",
            description="Force stop task",
            kind="bash",
            status="running",
        )
        store.add_task(task)

        tool = get_tool("BgTaskStop")
        result = tool.func({"task_id": "force01", "force": True}, {})
        assert "stopped" in result.lower()
        assert "forcefully" in result.lower()


class TestBackgroundTaskStore:
    """Test suite for the BackgroundTaskStore class."""

    def test_empty_store(self):
        """A new store should have no tasks."""
        store = tools_background.BackgroundTaskStore()
        assert store.list_tasks() == []
        assert store.get_task("anything") is None

    def test_add_and_get_task(self):
        """Adding and retrieving a task should work."""
        store = tools_background.BackgroundTaskStore()
        task = tools_background.BackgroundTask(
            task_id="t1",
            description="Test",
            kind="bash",
            status="running",
        )
        store.add_task(task)
        retrieved = store.get_task("t1")
        assert retrieved is task

    def test_list_tasks_order(self):
        """Tasks should be listed most recent first."""
        store = tools_background.BackgroundTaskStore()
        t1 = tools_background.BackgroundTask(
            task_id="old", description="Old", kind="bash", status="running",
        )
        time.sleep(0.01)
        t2 = tools_background.BackgroundTask(
            task_id="new", description="New", kind="bash", status="running",
        )
        store.add_task(t1)
        store.add_task(t2)
        listed = store.list_tasks()
        assert listed[0].task_id == "new"
        assert listed[1].task_id == "old"

    def test_remove_task(self):
        """Removing a task should delete it."""
        store = tools_background.BackgroundTaskStore()
        task = tools_background.BackgroundTask(
            task_id="rem", description="Remove me", kind="bash", status="running",
        )
        store.add_task(task)
        assert store.remove_task("rem") is True
        assert store.get_task("rem") is None
        assert store.remove_task("rem") is False

    def test_update_status(self):
        """Updating status should work."""
        store = tools_background.BackgroundTaskStore()
        task = tools_background.BackgroundTask(
            task_id="upd", description="Update", kind="bash", status="running",
        )
        store.add_task(task)
        store.update_status("upd", "completed", exit_code=0)
        updated = store.get_task("upd")
        assert updated.status == "completed"
        assert updated.exit_code == 0

    def test_thread_safety(self):
        """Concurrent operations should be safe."""
        store = tools_background.BackgroundTaskStore()
        errors = []

        def worker(i):
            try:
                task = tools_background.BackgroundTask(
                    task_id=f"t{i}",
                    description=f"Task {i}",
                    kind="bash",
                    status="running",
                )
                store.add_task(task)
                store.get_task(f"t{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert not errors
        assert len(store.list_tasks()) == 20


class TestBackgroundTask:
    """Test suite for the BackgroundTask dataclass."""

    def test_task_creation(self):
        """Creating a task should set all fields."""
        task = tools_background.BackgroundTask(
            task_id="abc",
            description="Test task",
            kind="bash",
            status="running",
        )
        assert task.task_id == "abc"
        assert task.description == "Test task"
        assert task.kind == "bash"
        assert task.status == "running"

    def test_task_duration(self):
        """Duration should be positive after a small delay."""
        task = tools_background.BackgroundTask(
            task_id="d1", description="Duration test", kind="bash", status="running",
        )
        time.sleep(0.05)
        assert task.duration > 0

    def test_task_is_running_without_thread(self):
        """A task without a thread should not appear running if status is not running."""
        task = tools_background.BackgroundTask(
            task_id="r1", description="Not running", kind="bash", status="completed",
        )
        assert not task.is_running()

    def test_task_append_output(self):
        """Appending output should add to the correct list."""
        task = tools_background.BackgroundTask(
            task_id="o1", description="Output", kind="bash", status="running",
        )
        task.append_output("stdout line\n")
        task.append_output("stderr line\n", is_stderr=True)
        assert len(task.stdout_lines) == 1
        assert len(task.stderr_lines) == 1
        assert task.stdout_lines[0] == "stdout line\n"

    def test_task_to_dict(self):
        """to_dict should serialize key fields."""
        task = tools_background.BackgroundTask(
            task_id="dict1", description="Dict test", kind="python", status="running",
        )
        d = task.to_dict()
        assert d["task_id"] == "dict1"
        assert d["description"] == "Dict test"
        assert d["kind"] == "python"
        assert d["status"] == "running"
        assert "duration" in d

    def test_task_stop(self):
        """Stopping a task should set the stop event."""
        task = tools_background.BackgroundTask(
            task_id="s1", description="Stop", kind="bash", status="running",
        )
        assert not task._stop_event.is_set()
        task.stop()
        assert task._stop_event.is_set()

    def test_force_stop_sets_status(self):
        """Force stopping should set status to stopped when thread is alive."""
        task = tools_background.BackgroundTask(
            task_id="s1", description="Force Stop", kind="bash", status="running",
        )
        # Simulate an alive thread
        task.thread = threading.Thread(target=lambda: None)
        task.thread.start()
        task.thread.join()  # Let it finish
        # Create a mock alive thread
        class FakeThread:
            def is_alive(self): return True
            def join(self, timeout=None): pass
        task.thread = FakeThread()
        task.stop(force=True)
        assert task._stop_event.is_set()
        assert task.status == "stopped"


class TestCreateBackgroundTask:
    """Test suite for the create_background_task helper."""

    def test_create_task(self):
        """Creating a background task should return a task with an ID."""

        def dummy():
            pass

        task = tools_background.create_background_task(
            description="Test",
            kind="bash",
            target=dummy,
        )
        assert task.task_id is not None
        assert len(task.task_id) > 0
        assert task.description == "Test"

    def test_task_actually_runs(self):
        """The background task should actually execute."""
        result_holder = []

        def target():
            result_holder.append("executed")

        task = tools_background.create_background_task(
            description="Run test",
            kind="python",
            target=target,
        )
        # Wait for the task to complete
        if task.thread:
            task.thread.join(timeout=5)
        assert "executed" in result_holder

    def test_task_with_args(self):
        """The background task should pass arguments."""
        result_holder = []

        def target(a, b):
            result_holder.append(a + b)

        task = tools_background.create_background_task(
            description="Args test",
            kind="python",
            target=target,
            args=(1, 2),
        )
        if task.thread:
            task.thread.join(timeout=5)
        assert 3 in result_holder

    def test_task_error_handling(self):
        """The background task should handle errors gracefully."""

        def failing_target():
            raise ValueError("Test error")

        task = tools_background.create_background_task(
            description="Failing task",
            kind="python",
            target=failing_target,
        )
        if task.thread:
            task.thread.join(timeout=5)
        assert task.status == "failed"
