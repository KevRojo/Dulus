"""Tests for the SetTodoList tool (tools_todo.py)."""
from __future__ import annotations

import json
import os

import pytest

from tool_registry import get_tool, clear_registry

import tools_todo


@pytest.fixture(autouse=True)
def _clean_registry(tmp_path, monkeypatch):
    """Reset registry and todo state before each test."""
    clear_registry()
    tools_todo._register()
    # Use tmp_path for todo storage
    monkeypatch.chdir(tmp_path)
    # Reset the singleton manager
    tools_todo._todo_manager = None
    yield
    clear_registry()


class TestSetTodoListTool:
    """Test suite for the SetTodoList tool."""

    def test_tool_is_registered(self):
        """SetTodoList tool must be registered."""
        tool = get_tool("SetTodoList")
        assert tool is not None
        assert tool.name == "SetTodoList"

    def test_tool_is_not_read_only(self):
        """SetTodoList should NOT be read-only (it writes todos to disk)."""
        tool = get_tool("SetTodoList")
        assert tool.read_only is False

    def test_tool_is_concurrent_safe(self):
        """SetTodoList should be safe to run concurrently."""
        tool = get_tool("SetTodoList")
        assert tool.concurrent_safe is True

    def test_get_empty_todo_list(self):
        """Getting todos when none exist should return empty message."""
        tool = get_tool("SetTodoList")
        result = tool.func({}, {})
        assert "empty" in result.lower()

    def test_set_todo_list(self):
        """Setting todos should persist them."""
        tool = get_tool("SetTodoList")
        todos = [
            {"title": "Write tests", "status": "pending"},
            {"title": "Run linter", "status": "in_progress"},
            {"title": "Deploy", "status": "done"},
        ]
        result = tool.func({"todos": todos}, {})
        assert "updated" in result.lower()
        assert "3" in result

    def test_set_and_get_todo_list(self):
        """Setting todos then getting them should return the list."""
        tool = get_tool("SetTodoList")
        todos = [
            {"title": "Write tests", "status": "pending"},
            {"title": "Run linter", "status": "done"},
        ]
        tool.func({"todos": todos}, {})

        result = tool.func({}, {})
        assert "Write tests" in result
        assert "Run linter" in result
        assert "[ ]" in result  # pending icon
        assert "[x]" in result  # done icon

    def test_todo_list_persistence(self):
        """Todos should persist to disk and be reloadable."""
        tool = get_tool("SetTodoList")
        todos = [{"title": "Persisted task", "status": "pending"}]
        tool.func({"todos": todos}, {})

        # Verify file exists
        todos_file = os.path.join(os.getcwd(), ".dulus", "todos.json")
        assert os.path.exists(todos_file)

        # Verify file content
        with open(todos_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["title"] == "Persisted task"
        assert data[0]["status"] == "pending"

    def test_todo_list_overwrite(self):
        """Setting new todos should replace old ones."""
        tool = get_tool("SetTodoList")
        tool.func({"todos": [{"title": "Old task", "status": "done"}]}, {})
        tool.func({"todos": [{"title": "New task", "status": "pending"}]}, {})

        result = tool.func({}, {})
        assert "New task" in result
        assert "Old task" not in result

    def test_empty_todo_array(self):
        """Setting an empty array should clear todos."""
        tool = get_tool("SetTodoList")
        tool.func({"todos": [{"title": "Task", "status": "pending"}]}, {})
        tool.func({"todos": []}, {})

        result = tool.func({}, {})
        assert "empty" in result.lower()

    def test_todo_with_empty_title_is_filtered(self):
        """Todos with empty titles should be filtered out."""
        tool = get_tool("SetTodoList")
        todos = [
            {"title": "Valid task", "status": "pending"},
            {"title": "", "status": "done"},
            {"title": "   ", "status": "in_progress"},
        ]
        result = tool.func({"todos": todos}, {})
        assert "1" in result  # Only 1 valid item

    def test_todo_status_icons(self):
        """Each status should have the correct icon in output."""
        tool = get_tool("SetTodoList")
        todos = [
            {"title": "Pending task", "status": "pending"},
            {"title": "In-progress task", "status": "in_progress"},
            {"title": "Done task", "status": "done"},
        ]
        tool.func({"todos": todos}, {})

        result = tool.func({}, {})
        assert "[ ] Pending task" in result
        assert "[/] In-progress task" in result
        assert "[x] Done task" in result

    def test_todo_invalid_status(self):
        """Invalid statuses should use the default icon."""
        tool = get_tool("SetTodoList")
        # The tool stores whatever status is given; display handles unknown
        todos = [{"title": "Weird status", "status": "unknown_status"}]
        result = tool.func({"todos": todos}, {})
        assert "updated" in result.lower()

    def test_schema_has_todos_property(self):
        """The schema should have a 'todos' property."""
        tool = get_tool("SetTodoList")
        schema = tool.schema
        assert "todos" in schema["input_schema"]["properties"]
        # 'todos' should NOT be in required (it's optional)
        assert "todos" not in schema["input_schema"]["required"]


class TestTodoManager:
    """Test suite for the TodoManager class directly."""

    def test_manager_init_default_dir(self):
        """TodoManager should default to cwd."""
        manager = tools_todo.TodoManager()
        assert manager._session_dir == os.getcwd()

    def test_manager_init_custom_dir(self, tmp_path):
        """TodoManager should accept custom session dir."""
        manager = tools_todo.TodoManager(str(tmp_path))
        assert manager._session_dir == str(tmp_path)

    def test_load_todos_missing_file(self, tmp_path):
        """Loading todos when file doesn't exist should return empty list."""
        manager = tools_todo.TodoManager(str(tmp_path))
        todos = manager._load_todos()
        assert todos == []

    def test_load_todos_corrupt_file(self, tmp_path):
        """Loading todos from corrupt file should return empty list."""
        manager = tools_todo.TodoManager(str(tmp_path))
        dulus_dir = tmp_path / ".dulus"
        dulus_dir.mkdir(parents=True, exist_ok=True)
        (dulus_dir / "todos.json").write_text("not valid json{", encoding="utf-8")
        todos = manager._load_todos()
        assert todos == []

    def test_read_todos_empty(self, tmp_path):
        """Reading empty todos should return empty message."""
        manager = tools_todo.TodoManager(str(tmp_path))
        result = manager.read_todos()
        assert "empty" in result.lower()

    def test_write_and_read_todos(self, tmp_path):
        """Writing then reading todos should preserve data."""
        manager = tools_todo.TodoManager(str(tmp_path))
        todos = [
            {"title": "First", "status": "pending"},
            {"title": "Second", "status": "done"},
        ]
        manager.write_todos(todos)
        result = manager.read_todos()
        assert "First" in result
        assert "Second" in result

    def test_save_creates_directories(self, tmp_path):
        """Saving todos should create the .dulus directory if needed."""
        deep_path = tmp_path / "sub" / "dir"
        manager = tools_todo.TodoManager(str(deep_path))
        manager._save_todos([{"title": "Test", "status": "pending"}])
        assert (deep_path / ".dulus" / "todos.json").exists()

    def test_write_todos_filters_empty_titles(self, tmp_path):
        """write_todos should filter out empty titles."""
        manager = tools_todo.TodoManager(str(tmp_path))
        todos = [
            {"title": "Valid", "status": "pending"},
            {"title": "", "status": "done"},
            {"title": "   ", "status": "in_progress"},
        ]
        result = manager.write_todos(todos)
        loaded = manager._load_todos()
        assert len(loaded) == 1
        assert loaded[0]["title"] == "Valid"
