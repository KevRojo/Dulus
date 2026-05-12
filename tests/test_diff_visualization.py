"""Tests for DiffVisualizer (Feature 19)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root (parent of tests/) is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dulus_tools.diff_visualizer import DiffVisualizer


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_diff_block() -> dict[str, str]:
    """Return a simple diff block for testing."""
    return {
        "path": "test.py",
        "old_text": "line1\nline2\nline3\n",
        "new_text": "line1\nline2_modified\nline3\n",
    }


@pytest.fixture
def empty_diff_block() -> dict[str, str]:
    """Return a diff block with identical old and new text."""
    return {
        "path": "same.py",
        "old_text": "no changes\n",
        "new_text": "no changes\n",
    }


# ── render_cli ────────────────────────────────────────────────────────────────


class TestRenderCli:
    """Tests for CLI diff rendering."""

    def test_render_cli_contains_path(self, simple_diff_block: dict[str, str]) -> None:
        """CLI output should contain the file path."""
        result = DiffVisualizer.render_cli(simple_diff_block)
        assert "test.py" in result

    def test_render_cli_contains_diff_markers(self, simple_diff_block: dict[str, str]) -> None:
        """CLI output should contain unified diff markers."""
        result = DiffVisualizer.render_cli(simple_diff_block)
        assert "--- a/test.py" in result
        assert "+++ b/test.py" in result

    def test_render_cli_ansi_colors(self, simple_diff_block: dict[str, str]) -> None:
        """CLI output should include ANSI color codes."""
        result = DiffVisualizer.render_cli(simple_diff_block)
        assert "\033[91m" in result  # Red for removed
        assert "\033[92m" in result  # Green for added

    def test_render_cli_no_changes(self, empty_diff_block: dict[str, str]) -> None:
        """CLI output should indicate no changes for identical text."""
        result = DiffVisualizer.render_cli(empty_diff_block)
        assert "(No changes)" in result

    def test_render_cli_removed_line(self, simple_diff_block: dict[str, str]) -> None:
        """CLI output should show the removed line."""
        result = DiffVisualizer.render_cli(simple_diff_block)
        assert "-line2" in result

    def test_render_cli_added_line(self, simple_diff_block: dict[str, str]) -> None:
        """CLI output should show the added line."""
        result = DiffVisualizer.render_cli(simple_diff_block)
        assert "+line2_modified" in result

    def test_render_cli_default_path(self) -> None:
        """CLI output should use 'unknown' when path is missing."""
        result = DiffVisualizer.render_cli({})
        assert "unknown" in result


# ── render_html ───────────────────────────────────────────────────────────────


class TestRenderHtml:
    """Tests for HTML diff rendering."""

    def test_render_html_contains_path(self, simple_diff_block: dict[str, str]) -> None:
        """HTML output should contain the file path."""
        result = DiffVisualizer.render_html(simple_diff_block)
        assert "test.py" in result

    def test_render_html_has_diff_block_class(self, simple_diff_block: dict[str, str]) -> None:
        """HTML output should have diff-block wrapper."""
        result = DiffVisualizer.render_html(simple_diff_block)
        assert '<div class="diff-block">' in result

    def test_render_html_has_pre_tag(self, simple_diff_block: dict[str, str]) -> None:
        """HTML output should use <pre> for diff content."""
        result = DiffVisualizer.render_html(simple_diff_block)
        assert '<pre class="diff">' in result

    def test_render_html_diff_add_class(self, simple_diff_block: dict[str, str]) -> None:
        """HTML output should mark additions with diff-add class."""
        result = DiffVisualizer.render_html(simple_diff_block)
        assert 'class="diff-add"' in result

    def test_render_html_diff_del_class(self, simple_diff_block: dict[str, str]) -> None:
        """HTML output should mark deletions with diff-del class."""
        result = DiffVisualizer.render_html(simple_diff_block)
        assert 'class="diff-del"' in result

    def test_render_html_escapes_content(self) -> None:
        """HTML output should escape special characters."""
        block = {
            "path": "<script>.py",
            "old_text": "<div>old</div>\n",
            "new_text": "<span>new</span>\n",
        }
        result = DiffVisualizer.render_html(block)
        assert "<script>" not in result  # Should be escaped
        assert "&lt;script&gt;" in result

    def test_render_html_no_changes(self, empty_diff_block: dict[str, str]) -> None:
        """HTML output should handle no changes."""
        result = DiffVisualizer.render_html(empty_diff_block)
        assert "same.py" in result


# ── render_telegram ───────────────────────────────────────────────────────────


class TestRenderTelegram:
    """Tests for Telegram diff rendering."""

    def test_render_telegram_contains_path(self, simple_diff_block: dict[str, str]) -> None:
        """Telegram output should contain the file path."""
        result = DiffVisualizer.render_telegram(simple_diff_block)
        assert "test.py" in result

    def test_render_telegram_has_file_emoji(self, simple_diff_block: dict[str, str]) -> None:
        """Telegram output should have file emoji."""
        result = DiffVisualizer.render_telegram(simple_diff_block)
        assert "📄" in result

    def test_render_telegram_line_counts(self, simple_diff_block: dict[str, str]) -> None:
        """Telegram output should report line change counts."""
        result = DiffVisualizer.render_telegram(simple_diff_block)
        assert "lines" in result

    def test_render_telegram_markdown_bold(self, simple_diff_block: dict[str, str]) -> None:
        """Telegram output should use Markdown bold for filename."""
        result = DiffVisualizer.render_telegram(simple_diff_block)
        assert "*test.py*" in result

    def test_render_telegram_empty_diff(self, empty_diff_block: dict[str, str]) -> None:
        """Telegram output should handle no-change diffs."""
        result = DiffVisualizer.render_telegram(empty_diff_block)
        assert "same.py" in result
        assert "+0 lines" in result or "lines" in result


# ── generate_unified_diff ─────────────────────────────────────────────────────


class TestGenerateUnifiedDiff:
    """Tests for generate_unified_diff."""

    def test_generate_unified_diff(self) -> None:
        """Should produce a standard unified diff."""
        result = DiffVisualizer.generate_unified_diff(
            "line1\nline2\n", "line1\nline2_modified\n", "test.py"
        )
        assert "--- a/test.py" in result
        assert "+++ b/test.py" in result
        assert "-line2" in result
        assert "+line2_modified" in result

    def test_generate_unified_diff_new_file(self) -> None:
        """Should handle new file (empty old text)."""
        result = DiffVisualizer.generate_unified_diff(
            "", "new content\n", "new.py"
        )
        assert "+new content" in result

    def test_generate_unified_diff_deleted_file(self) -> None:
        """Should handle deleted file (empty new text)."""
        result = DiffVisualizer.generate_unified_diff(
            "old content\n", "", "old.py"
        )
        assert "-old content" in result

    def test_generate_unified_diff_empty_both(self) -> None:
        """Should handle both texts being empty."""
        result = DiffVisualizer.generate_unified_diff("", "", "empty.py")
        # unified_diff of two empty strings produces no output at all
        assert result == ""

    def test_generate_unified_diff_multiline(self) -> None:
        """Should handle multi-line diffs correctly."""
        old = "a\nb\nc\nd\n"
        new = "a\nB\nc\nD\n"
        result = DiffVisualizer.generate_unified_diff(old, new, "multi.py")
        assert "-b" in result
        assert "+B" in result
        assert "-d" in result
        assert "+D" in result
