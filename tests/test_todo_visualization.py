"""Tests for TodoVisualizer (Feature 20)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root (parent of tests/) is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dulus_tools.todo_visualizer import TodoVisualizer


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_todos() -> dict:
    """Return a todo block with items in various states."""
    return {
        "items": [
            {"status": "pending", "title": "Write tests"},
            {"status": "in_progress", "title": "Implement feature"},
            {"status": "done", "title": "Setup project"},
        ]
    }


@pytest.fixture
def empty_todos() -> dict:
    """Return a todo block with no items."""
    return {"items": []}


@pytest.fixture
def single_todo() -> dict:
    """Return a todo block with a single item."""
    return {"items": [{"status": "pending", "title": "One task"}]}


# ── render_cli ────────────────────────────────────────────────────────────────


class TestRenderCli:
    """Tests for CLI todo rendering."""

    def test_render_cli_header(self, sample_todos: dict) -> None:
        """CLI output should have a header."""
        result = TodoVisualizer.render_cli(sample_todos)
        assert "Todo List" in result

    def test_render_cli_pending_icon(self, sample_todos: dict) -> None:
        """CLI output should show pending items with [ ] icon."""
        result = TodoVisualizer.render_cli(sample_todos)
        assert "[ ] Write tests" in result

    def test_render_cli_in_progress_icon(self, sample_todos: dict) -> None:
        """CLI output should show in_progress items with [/] icon."""
        result = TodoVisualizer.render_cli(sample_todos)
        assert "[/] Implement feature" in result

    def test_render_cli_done_icon(self, sample_todos: dict) -> None:
        """CLI output should show done items with [x] icon and strikethrough."""
        result = TodoVisualizer.render_cli(sample_todos)
        # The done item has [x] icon plus ANSI strikethrough on the title
        assert "[x]" in result
        assert "Setup project" in result
        # Verify it's the green (done) color code near the [x]
        assert "\033[32m[x]" in result

    def test_render_cli_strikethrough_done(self, sample_todos: dict) -> None:
        """CLI output should apply strikethrough to done items."""
        result = TodoVisualizer.render_cli(sample_todos)
        assert "\033[9m" in result  # ANSI strikethrough

    def test_render_cli_empty(self, empty_todos: dict) -> None:
        """CLI output should handle empty todo lists."""
        result = TodoVisualizer.render_cli(empty_todos)
        assert "No todos" in result

    def test_render_cli_unknown_status(self) -> None:
        """CLI output should handle unknown status gracefully."""
        todos = {"items": [{"status": "weird", "title": "Unknown"}]}
        result = TodoVisualizer.render_cli(todos)
        assert "Unknown" in result
        assert "[?]" in result

    def test_render_cli_default_title(self) -> None:
        """CLI output should use 'Untitled' when title is missing."""
        todos = {"items": [{"status": "pending"}]}
        result = TodoVisualizer.render_cli(todos)
        assert "Untitled" in result

    def test_render_cli_separator_lines(self, sample_todos: dict) -> None:
        """CLI output should have separator lines."""
        result = TodoVisualizer.render_cli(sample_todos)
        assert "─" in result

    def test_render_cli_ansi_codes(self, sample_todos: dict) -> None:
        """CLI output should include ANSI color codes."""
        result = TodoVisualizer.render_cli(sample_todos)
        assert "\033[" in result  # ANSI escape sequences


# ── render_html ───────────────────────────────────────────────────────────────


class TestRenderHtml:
    """Tests for HTML todo rendering."""

    def test_render_html_has_todo_block(self, sample_todos: dict) -> None:
        """HTML output should have todo-block wrapper."""
        result = TodoVisualizer.render_html(sample_todos)
        assert '<div class="todo-block">' in result

    def test_render_html_has_list(self, sample_todos: dict) -> None:
        """HTML output should use a <ul> list."""
        result = TodoVisualizer.render_html(sample_todos)
        assert '<ul class="todo-list">' in result

    def test_render_html_pending_checkbox(self, sample_todos: dict) -> None:
        """HTML output should have unchecked box for pending."""
        result = TodoVisualizer.render_html(sample_todos)
        assert '<input type="checkbox" disabled>' in result

    def test_render_html_done_checkbox(self, sample_todos: dict) -> None:
        """HTML output should have checked box for done."""
        result = TodoVisualizer.render_html(sample_todos)
        assert '<input type="checkbox" checked disabled>' in result

    def test_render_html_status_classes(self, sample_todos: dict) -> None:
        """HTML output should apply CSS classes per status."""
        result = TodoVisualizer.render_html(sample_todos)
        assert 'class="todo-pending"' in result
        assert 'class="todo-in_progress"' in result
        assert 'class="todo-done"' in result

    def test_render_html_escapes_titles(self) -> None:
        """HTML output should escape special characters in titles."""
        todos = {"items": [{"status": "pending", "title": "<script>alert(1)</script>"}]}
        result = TodoVisualizer.render_html(todos)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_render_html_empty(self, empty_todos: dict) -> None:
        """HTML output should handle empty todo lists."""
        result = TodoVisualizer.render_html(empty_todos)
        assert "<p>No todos.</p>" in result

    def test_render_html_contains_titles(self, sample_todos: dict) -> None:
        """HTML output should contain all todo titles."""
        result = TodoVisualizer.render_html(sample_todos)
        assert "Write tests" in result
        assert "Implement feature" in result
        assert "Setup project" in result


# ── render_telegram ───────────────────────────────────────────────────────────


class TestRenderTelegram:
    """Tests for Telegram todo rendering."""

    def test_render_telegram_header(self, sample_todos: dict) -> None:
        """Telegram output should have a header."""
        result = TodoVisualizer.render_telegram(sample_todos)
        assert "*Todo List*" in result

    def test_render_telegram_pending_emoji(self, sample_todos: dict) -> None:
        """Telegram output should use white square for pending."""
        result = TodoVisualizer.render_telegram(sample_todos)
        assert "⬜ Write tests" in result

    def test_render_telegram_in_progress_emoji(self, sample_todos: dict) -> None:
        """Telegram output should use refresh emoji for in_progress."""
        result = TodoVisualizer.render_telegram(sample_todos)
        assert "🔄 Implement feature" in result

    def test_render_telegram_done_emoji(self, sample_todos: dict) -> None:
        """Telegram output should use checkmark for done."""
        result = TodoVisualizer.render_telegram(sample_todos)
        assert "✅ Setup project" in result

    def test_render_telegram_empty(self, empty_todos: dict) -> None:
        """Telegram output should handle empty lists."""
        result = TodoVisualizer.render_telegram(empty_todos)
        assert "_No items_" in result

    def test_render_telegram_unknown_status(self) -> None:
        """Telegram output should use question mark for unknown status."""
        todos = {"items": [{"status": "weird", "title": "Unknown"}]}
        result = TodoVisualizer.render_telegram(todos)
        assert "❓ Unknown" in result

    def test_render_telegram_markdown_bold(self, sample_todos: dict) -> None:
        """Telegram output should use Markdown bold for header."""
        result = TodoVisualizer.render_telegram(sample_todos)
        assert "*Todo List*" in result


# ── Status icon dictionaries ──────────────────────────────────────────────────


class TestStatusIcons:
    """Tests for the status icon mappings."""

    def test_cli_status_icons_complete(self) -> None:
        """STATUS_ICONS_CLI should have all three statuses."""
        assert "pending" in TodoVisualizer.STATUS_ICONS_CLI
        assert "in_progress" in TodoVisualizer.STATUS_ICONS_CLI
        assert "done" in TodoVisualizer.STATUS_ICONS_CLI

    def test_cli_status_icon_values(self) -> None:
        """STATUS_ICONS_CLI should return icon and ANSI color."""
        icon, color = TodoVisualizer.STATUS_ICONS_CLI["done"]
        assert icon == "[x]"
        assert "\033[" in color  # ANSI escape

    def test_telegram_status_emojis_complete(self) -> None:
        """STATUS_EMOJI_TG should have all three statuses."""
        assert "pending" in TodoVisualizer.STATUS_EMOJI_TG
        assert "in_progress" in TodoVisualizer.STATUS_EMOJI_TG
        assert "done" in TodoVisualizer.STATUS_EMOJI_TG

    def test_telegram_status_emoji_values(self) -> None:
        """STATUS_EMOJI_TG should return emoji characters."""
        assert TodoVisualizer.STATUS_EMOJI_TG["pending"] == "⬜"
        assert TodoVisualizer.STATUS_EMOJI_TG["done"] == "✅"
