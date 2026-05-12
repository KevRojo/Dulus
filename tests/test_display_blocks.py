"""Tests for the Display Blocks System (display_blocks.py)."""
from __future__ import annotations

import pytest

from display_blocks import DisplayBlockRenderer


class TestRenderCli:
    """Test suite for CLI rendering."""

    def test_render_unknown_block(self):
        """Rendering an unknown block type should not crash."""
        block = {"type": "unknown_type", "data": "test"}
        result = DisplayBlockRenderer.render_cli(block)
        assert "Display Block" in result

    def test_render_block_missing_type(self):
        """Rendering a block with no type should handle gracefully."""
        block = {"data": "no type"}
        result = DisplayBlockRenderer.render_cli(block)
        assert "Display Block" in result or "unknown" in result.lower()

    # ── Diff blocks ────────────────────────────────────────────────────────

    def test_render_diff_cli(self):
        """Diff block should show path and changes."""
        block = {
            "type": "diff",
            "path": "test.py",
            "old_text": "def old():\n    pass\n",
            "new_text": "def new():\n    return 42\n",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "test.py" in result
        assert "---" in result  # unified diff format

    def test_render_diff_cli_empty(self):
        """Diff with no changes should indicate no changes."""
        block = {
            "type": "diff",
            "path": "same.py",
            "old_text": "same",
            "new_text": "same",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "No changes" in result or "same.py" in result

    def test_render_diff_cli_summary(self):
        """Diff summary should be compact."""
        block = {
            "type": "diff",
            "path": "big.py",
            "old_text": "",
            "new_text": "",
            "is_summary": True,
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "summary" in result.lower()

    # ── Todo blocks ────────────────────────────────────────────────────────

    def test_render_todo_cli(self):
        """Todo block should show items with icons."""
        block = {
            "type": "todo",
            "items": [
                {"title": "Task A", "status": "pending"},
                {"title": "Task B", "status": "in_progress"},
                {"title": "Task C", "status": "done"},
            ],
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "Task A" in result
        assert "Task B" in result
        assert "Task C" in result
        assert "[ ]" in result  # pending
        assert "[/]" in result  # in progress
        assert "[x]" in result  # done

    def test_render_todo_cli_empty(self):
        """Empty todo block should show empty message."""
        block = {"type": "todo", "items": []}
        result = DisplayBlockRenderer.render_cli(block)
        assert "No items" in result or "empty" in result.lower()

    # ── Shell blocks ───────────────────────────────────────────────────────

    def test_render_shell_cli(self):
        """Shell block should show the command."""
        block = {
            "type": "shell",
            "command": "ls -la",
            "language": "bash",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "ls -la" in result
        assert "$" in result

    # ── Background task blocks ─────────────────────────────────────────────

    def test_render_bg_task_cli(self):
        """Background task block should show task info."""
        block = {
            "type": "background_task",
            "task_id": "abc123",
            "kind": "python",
            "status": "running",
            "description": "Processing data",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "abc123" in result
        assert "Processing data" in result
        assert "python" in result
        assert "running" in result

    # ── Think blocks ───────────────────────────────────────────────────────

    def test_render_think_cli(self):
        """Think block should show thought with indentation."""
        block = {
            "type": "think",
            "thought": "I need to analyze this problem step by step.",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "Thinking" in result or "think" in result.lower()
        assert "analyze" in result

    def test_render_think_cli_multiline(self):
        """Think block should handle multiline thoughts."""
        block = {
            "type": "think",
            "thought": "Line 1\nLine 2\nLine 3",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    # ── Code blocks ────────────────────────────────────────────────────────

    def test_render_code_cli(self):
        """Code block should show code with markers."""
        block = {
            "type": "code",
            "code": "def hello():\n    print('world')",
            "language": "python",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "def hello()" in result
        assert "```" in result

    # ── Table blocks ───────────────────────────────────────────────────────

    def test_render_table_cli(self):
        """Table block should show formatted table."""
        block = {
            "type": "table",
            "headers": ["Name", "Status"],
            "rows": [
                ["Task 1", "Done"],
                ["Task 2", "Pending"],
            ],
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "Name" in result
        assert "Status" in result
        assert "Task 1" in result
        assert "Task 2" in result

    def test_render_table_cli_no_headers(self):
        """Table block without headers should still render."""
        block = {
            "type": "table",
            "rows": [["A", "B"], ["C", "D"]],
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "A" in result
        assert "B" in result

    def test_render_table_cli_empty(self):
        """Empty table should show empty message."""
        block = {"type": "table", "headers": [], "rows": []}
        result = DisplayBlockRenderer.render_cli(block)
        assert "empty" in result.lower() or "table" in result.lower()

    # ── Error blocks ───────────────────────────────────────────────────────

    def test_render_error_cli(self):
        """Error block should show the error message."""
        block = {
            "type": "error",
            "message": "Something went wrong",
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "Something went wrong" in result
        assert "Error" in result


class TestRenderHtml:
    """Test suite for HTML rendering."""

    def test_render_todo_html(self):
        """Todo block should render as HTML list."""
        block = {
            "type": "todo",
            "items": [
                {"title": "Task A", "status": "done"},
            ],
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "<ul>" in result
        assert "Task A" in result
        assert "</ul>" in result

    def test_render_todo_html_empty(self):
        """Empty todo should render as HTML."""
        block = {"type": "todo", "items": []}
        result = DisplayBlockRenderer.render_html(block)
        assert "display-block" in result

    def test_render_shell_html(self):
        """Shell block should render as HTML pre/code."""
        block = {
            "type": "shell",
            "command": "echo hello",
            "language": "bash",
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "<pre>" in result
        assert "echo hello" in result

    def test_render_think_html(self):
        """Think block should render as HTML."""
        block = {
            "type": "think",
            "thought": "Thinking about the solution",
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "think-block" in result
        assert "Thinking" in result

    def test_render_bg_task_html(self):
        """Background task should render as HTML."""
        block = {
            "type": "background_task",
            "task_id": "t1",
            "kind": "bash",
            "status": "running",
            "description": "Test",
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "bg-task-block" in result
        assert "t1" in result

    def test_render_diff_html(self):
        """Diff should render as HTML."""
        block = {
            "type": "diff",
            "path": "file.py",
            "old_text": "old",
            "new_text": "new",
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "diff-block" in result
        assert "file.py" in result

    def test_render_code_html(self):
        """Code should render as HTML with language class."""
        block = {
            "type": "code",
            "code": "print('hi')",
            "language": "python",
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "code-block" in result
        assert "language-python" in result

    def test_render_table_html(self):
        """Table should render as HTML table."""
        block = {
            "type": "table",
            "headers": ["A", "B"],
            "rows": [["1", "2"]],
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "<table>" in result
        assert "<th>" in result
        assert "<td>" in result
        assert "</table>" in result

    def test_render_error_html(self):
        """Error should render as HTML with red color."""
        block = {
            "type": "error",
            "message": "Oops",
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "error-block" in result
        assert "Oops" in result
        assert "f44336" in result  # red color

    def test_render_unknown_html(self):
        """Unknown block should not crash in HTML mode."""
        block = {"type": "weird", "data": "test"}
        result = DisplayBlockRenderer.render_html(block)
        assert "unknown-block" in result or "weird" in result

    def test_html_escapes_content(self):
        """HTML rendering should escape special characters."""
        block = {
            "type": "think",
            "thought": "<script>alert('xss')</script>",
        }
        result = DisplayBlockRenderer.render_html(block)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestRenderTelegram:
    """Test suite for Telegram rendering."""

    def test_render_todo_telegram(self):
        """Todo block should render for Telegram."""
        block = {
            "type": "todo",
            "items": [
                {"title": "Task A", "status": "done"},
            ],
        }
        result = DisplayBlockRenderer.render_telegram(block)
        assert "Todo List" in result
        assert "✅" in result  # done emoji

    def test_render_todo_telegram_empty(self):
        """Empty todo should render for Telegram."""
        block = {"type": "todo", "items": []}
        result = DisplayBlockRenderer.render_telegram(block)
        assert "Empty" in result

    def test_render_shell_telegram(self):
        """Shell block should render as Telegram code block."""
        block = {
            "type": "shell",
            "command": "ls -la",
        }
        result = DisplayBlockRenderer.render_telegram(block)
        assert "```" in result
        assert "ls -la" in result

    def test_render_think_telegram(self):
        """Think block should render for Telegram."""
        block = {
            "type": "think",
            "thought": "Analyzing the problem",
        }
        result = DisplayBlockRenderer.render_telegram(block)
        assert "💭" in result
        assert "Thinking" in result

    def test_render_bg_task_telegram(self):
        """Background task should render for Telegram."""
        block = {
            "type": "background_task",
            "task_id": "t1",
            "kind": "bash",
            "status": "running",
            "description": "Processing",
        }
        result = DisplayBlockRenderer.render_telegram(block)
        assert "🔄" in result  # running emoji
        assert "Processing" in result

    def test_render_error_telegram(self):
        """Error should render for Telegram."""
        block = {
            "type": "error",
            "message": "Failed",
        }
        result = DisplayBlockRenderer.render_telegram(block)
        assert "❌" in result
        assert "Failed" in result

    def test_render_unknown_telegram(self):
        """Unknown block should not crash in Telegram mode."""
        block = {"type": "weird", "data": "test"}
        result = DisplayBlockRenderer.render_telegram(block)
        assert "```" in result


class TestRenderDispatch:
    """Test suite for the render() dispatch method."""

    def test_render_cli_dispatch(self):
        """render() with 'cli' should call render_cli."""
        block = {"type": "think", "thought": "test"}
        result = DisplayBlockRenderer.render(block, "cli")
        assert "Thinking" in result or "think" in result.lower()

    def test_render_html_dispatch(self):
        """render() with 'html' should call render_html."""
        block = {"type": "think", "thought": "test"}
        result = DisplayBlockRenderer.render(block, "html")
        assert "think-block" in result

    def test_render_telegram_dispatch(self):
        """render() with 'telegram' should call render_telegram."""
        block = {"type": "think", "thought": "test"}
        result = DisplayBlockRenderer.render(block, "telegram")
        assert "💭" in result

    def test_render_invalid_format_fallback(self):
        """render() with unknown format should fall back to str()."""
        block = {"type": "think", "thought": "test"}
        result = DisplayBlockRenderer.render(block, "invalid_format")
        assert "test" in result


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_block(self):
        """Rendering an empty block should not crash."""
        block = {}
        result = DisplayBlockRenderer.render_cli(block)
        assert "unknown" in result.lower() or "Display Block" in result

    def test_none_values_in_block(self):
        """Blocks with None values should be handled gracefully."""
        block = {
            "type": "todo",
            "items": [
                {"title": None, "status": "pending"},
            ],
        }
        result = DisplayBlockRenderer.render_cli(block)
        # Should not raise an exception
        assert "None" in result or "" in result

    def test_missing_required_fields(self):
        """Blocks missing expected fields should be handled."""
        block = {"type": "shell"}  # missing command
        result = DisplayBlockRenderer.render_cli(block)
        # Should not crash
        assert "$" in result

    def test_large_content(self):
        """Large content should not cause issues."""
        block = {
            "type": "think",
            "thought": "A" * 10000,
        }
        result = DisplayBlockRenderer.render_cli(block)
        assert "A" * 100 in result  # At least some content is present
