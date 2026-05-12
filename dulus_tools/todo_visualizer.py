"""TodoVisualizer - Render todo lists in various formats."""

from __future__ import annotations

import html as html_module
from typing import Any, Dict, List


class TodoVisualizer:
    """Render todo lists in CLI, HTML, and Telegram formats.

    Provides rich formatting for todo items across different output
    targets: ANSI-colored terminal output, interactive HTML checkboxes
    for web clients, and emoji-based checklists for Telegram.

    Example:
        block = {
            "items": [
                {"status": "pending", "title": "Write tests"},
                {"status": "done", "title": "Setup project"},
            ]
        }
        print(TodoVisualizer.render_cli(block))
        html = TodoVisualizer.render_html(block)
        tg = TodoVisualizer.render_telegram(block)
    """

    STATUS_ICONS_CLI: Dict[str, tuple[str, str]] = {
        "pending": ("[ ]", "\033[37m"),  # White
        "in_progress": ("[/]", "\033[33m"),  # Yellow
        "done": ("[x]", "\033[32m"),  # Green
    }

    STATUS_EMOJI_TG: Dict[str, str] = {
        "pending": "⬜",
        "in_progress": "🔄",
        "done": "✅",
    }

    @staticmethod
    def render_cli(todo_block: Dict[str, Any]) -> str:
        """Render todos with rich formatting for CLI.

        Args:
            todo_block: Dict with 'items' key, each item having
                       'status' and 'title' keys.

        Returns:
            ANSI-formatted todo list string.
        """
        items: List[Dict[str, Any]] = todo_block.get("items", [])
        if not items:
            return "No todos."

        lines = ["\n📋 Todo List:", "─" * 40]
        for item in items:
            status = item.get("status", "pending")
            title = item.get("title", "Untitled")
            icon, color = TodoVisualizer.STATUS_ICONS_CLI.get(
                status, ("[?]", "\033[0m")
            )
            reset = "\033[0m"

            if status == "done":
                # Strikethrough for done items
                title = f"\033[9m{title}\033[0m"

            lines.append(f"{color}{icon} {title}{reset}")

        lines.append("─" * 40)
        return "\n".join(lines)

    @staticmethod
    def render_html(todo_block: Dict[str, Any]) -> str:
        """Render todos as interactive HTML checkboxes for WebChat.

        Args:
            todo_block: Dict with 'items' key, each item having
                       'status' and 'title' keys.

        Returns:
            HTML string with checkbox inputs and CSS classes.
        """
        items: List[Dict[str, Any]] = todo_block.get("items", [])
        if not items:
            return "<p>No todos.</p>"

        lines = [
            '<div class="todo-block"><h4>📋 Todo List</h4><ul class="todo-list">'
        ]
        for item in items:
            status = item.get("status", "pending")
            title = html_module.escape(item.get("title", "Untitled"))

            checkbox = {
                "pending": '<input type="checkbox" disabled>',
                "in_progress": '<input type="checkbox" disabled indeterminate>',
                "done": '<input type="checkbox" checked disabled>',
            }.get(status, '<input type="checkbox" disabled>')

            css_class = f"todo-{status}"
            lines.append(
                f'<li class="{css_class}">{checkbox} <span>{title}</span></li>'
            )

        lines.append("</ul></div>")
        return "\n".join(lines)

    @staticmethod
    def render_telegram(todo_block: Dict[str, Any]) -> str:
        """Render todos as emoji checklist for Telegram.

        Args:
            todo_block: Dict with 'items' key, each item having
                       'status' and 'title' keys.

        Returns:
            Markdown-formatted todo list with status emojis.
        """
        items: List[Dict[str, Any]] = todo_block.get("items", [])
        if not items:
            return "📋 *Todo List*\n_No items_"

        lines = ["📋 *Todo List*"]
        for item in items:
            status = item.get("status", "pending")
            title = item.get("title", "Untitled")
            emoji = TodoVisualizer.STATUS_EMOJI_TG.get(status, "❓")
            lines.append(f"{emoji} {title}")

        return "\n".join(lines)
