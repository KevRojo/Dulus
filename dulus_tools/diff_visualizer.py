"""DiffVisualizer - Render diffs in various formats."""

from __future__ import annotations

import difflib
import html
from typing import Dict, List


class DiffVisualizer:
    """Render display blocks in CLI, HTML, and Telegram formats.

    Provides multiple renderers for code diffs, supporting ANSI-colored
    terminal output, styled HTML for web clients, and compact summaries
    for Telegram. Also generates standard unified diff text.

    Example:
        block = {"path": "test.py", "old_text": "x=1\\n", "new_text": "x=2\\n"}
        print(DiffVisualizer.render_cli(block))
        html = DiffVisualizer.render_html(block)
        tg = DiffVisualizer.render_telegram(block)
    """

    @staticmethod
    def render_cli(diff_block: Dict[str, str]) -> str:
        """Render diff for CLI output with ANSI colors.

        Args:
            diff_block: Dict with keys 'path', 'old_text', 'new_text'.

        Returns:
            ANSI-colored diff string for terminal display.
        """
        path = diff_block.get("path", "unknown")
        old_text = diff_block.get("old_text", "")
        new_text = diff_block.get("new_text", "")

        lines = [f"\n{'=' * 60}", f"Diff: {path}", f"{'=' * 60}"]

        diff = list(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )

        if not diff:
            lines.append("(No changes)")
        else:
            for line in diff:
                if line.startswith("+"):
                    lines.append(f"\033[92m{line}\033[0m")  # Green
                elif line.startswith("-"):
                    lines.append(f"\033[91m{line}\033[0m")  # Red
                elif line.startswith("^"):
                    lines.append(f"\033[94m{line}\033[0m")  # Blue
                else:
                    lines.append(line)

        lines.append(f"{'=' * 60}\n")
        return "\n".join(lines)

    @staticmethod
    def render_html(diff_block: Dict[str, str]) -> str:
        """Render diff as HTML for WebChat.

        Args:
            diff_block: Dict with keys 'path', 'old_text', 'new_text'.

        Returns:
            HTML string with styled diff spans.
        """
        path = html.escape(diff_block.get("path", "unknown"))
        old_text = diff_block.get("old_text", "")
        new_text = diff_block.get("new_text", "")

        diff = list(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )

        lines = [f'<div class="diff-block"><h4>{path}</h4><pre class="diff">']
        for line in diff:
            escaped = html.escape(line)
            if line.startswith("+"):
                lines.append(f'<span class="diff-add">{escaped}</span>')
            elif line.startswith("-"):
                lines.append(f'<span class="diff-del">{escaped}</span>')
            elif line.startswith("@"):
                lines.append(f'<span class="diff-hunk">{escaped}</span>')
            else:
                lines.append(f'<span class="diff-line">{escaped}</span>')
        lines.append("</pre></div>")
        return "\n".join(lines)

    @staticmethod
    def render_telegram(diff_block: Dict[str, str]) -> str:
        """Render diff summary for Telegram.

        Args:
            diff_block: Dict with keys 'path', 'old_text', 'new_text'.

        Returns:
            Compact diff summary with emoji indicators.
        """
        path = diff_block.get("path", "unknown")
        lines = [f"📄 *{path}*"]

        old_lines = diff_block.get("old_text", "").splitlines()
        new_lines = diff_block.get("new_text", "").splitlines()

        # Show a summary
        added = sum(1 for line in new_lines if line not in old_lines)
        removed = sum(1 for line in old_lines if line not in new_lines)
        lines.append(f"📊 +{added} lines, -{removed} lines")

        return "\n".join(lines)

    @staticmethod
    def generate_unified_diff(old_text: str, new_text: str, path: str) -> str:
        """Generate unified diff format text.

        Args:
            old_text: Original file content.
            new_text: Modified file content.
            path: File path to display in the diff header.

        Returns:
            Unified diff as a multi-line string.
        """
        return "\n".join(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
