"""Display Blocks System - Visual representations of agent actions.

Provides a structured way to represent agent actions visually across multiple
frontends: CLI (dulus.py), WebChat (webchat_server.py), and Telegram.

Display blocks are dict-based and can be rendered in various formats.
"""
from __future__ import annotations

import difflib
import html
from typing import Literal


# ── Display block type hints ─────────────────────────────────────────────────

# These are the supported display block types
DisplayBlockType = Literal[
    "diff",
    "todo",
    "shell",
    "background_task",
    "think",
    "code",
    "table",
    "error",
]


# ── CLI Renderer ─────────────────────────────────────────────────────────────


class DisplayBlockRenderer:
    """Render display blocks in various formats for different frontends.

    Supports CLI (terminal), HTML (WebChat), and Telegram (Markdown) output formats.
    Each render method takes a display block dict and returns a formatted string.
    """

    # ── Public API ──────────────────────────────────────────────────────────

    @staticmethod
    def render_cli(block: dict) -> str:
        """Render a display block for CLI (terminal) output.

        Args:
            block: Display block dict with at least a 'type' key.

        Returns:
            Formatted string suitable for terminal display.
        """
        block_type = block.get("type", "unknown")
        renderer = _CLI_RENDERERS.get(block_type, _CLI_RENDERERS["unknown"])
        return renderer(block)

    @staticmethod
    def render_html(block: dict) -> str:
        """Render a display block as HTML for WebChat.

        Args:
            block: Display block dict with at least a 'type' key.

        Returns:
            HTML string suitable for web display.
        """
        block_type = block.get("type", "unknown")
        renderer = _HTML_RENDERERS.get(block_type, _HTML_RENDERERS["unknown"])
        return renderer(block)

    @staticmethod
    def render_telegram(block: dict) -> str:
        """Render a display block for Telegram (Markdown V2).

        Args:
            block: Display block dict with at least a 'type' key.

        Returns:
            Formatted string using Telegram Markdown V2 syntax.
        """
        block_type = block.get("type", "unknown")
        renderer = _TG_RENDERERS.get(block_type, _TG_RENDERERS["unknown"])
        return renderer(block)

    @staticmethod
    def render(block: dict, format: Literal["cli", "html", "telegram"] = "cli") -> str:
        """Render a display block in the specified format.

        Args:
            block: Display block dict with at least a 'type' key.
            format: Target format - "cli", "html", or "telegram".

        Returns:
            Formatted string in the requested format.
        """
        if format == "cli":
            return DisplayBlockRenderer.render_cli(block)
        elif format == "html":
            return DisplayBlockRenderer.render_html(block)
        elif format == "telegram":
            return DisplayBlockRenderer.render_telegram(block)
        return str(block)


# ── CLI Renderers ────────────────────────────────────────────────────────────


def _render_diff_cli(block: dict) -> str:
    """Render a diff display block for CLI.

    Shows a unified diff between old and new text.
    """
    path = block.get("path", "<unknown>")
    old_text = block.get("old_text", "")
    new_text = block.get("new_text", "")
    old_start = block.get("old_start", 1)
    new_start = block.get("new_start", 1)
    is_summary = block.get("is_summary", False)

    if is_summary:
        return f"[Diff: {path}] (summary)"

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    # Generate unified diff
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    diff_text = "\n".join(diff)

    if not diff_text:
        return f"[Diff: {path}] No changes"

    return f"[Diff: {path}]\n{diff_text}"


def _render_todo_cli(block: dict) -> str:
    """Render a todo display block for CLI."""
    items = block.get("items", [])
    if not items:
        return "[Todo] No items"

    lines = ["Todo List:"]
    icons = {"pending": "[ ]", "in_progress": "[/]", "done": "[x]"}
    for item in items:
        status = item.get("status", "pending")
        icon = icons.get(status, "[ ]")
        lines.append(f"  {icon} {item.get('title', '')}")
    return "\n".join(lines)


def _render_shell_cli(block: dict) -> str:
    """Render a shell command display block for CLI."""
    command = block.get("command", "")
    language = block.get("language", "bash")
    return f"$ {command}"


def _render_bg_task_cli(block: dict) -> str:
    """Render a background task display block for CLI."""
    task_id = block.get("task_id", "?")
    kind = block.get("kind", "?")
    status = block.get("status", "?")
    description = block.get("description", "")

    icons = {
        "running": "●",
        "completed": "✓",
        "failed": "✗",
        "stopped": "■",
    }
    icon = icons.get(status, "?")
    return f"{icon} [{task_id}] {description} ({kind}, {status})"


def _render_think_cli(block: dict) -> str:
    """Render a think display block for CLI."""
    thought = block.get("thought", "")
    lines = thought.splitlines()
    # Indent thought content for visual distinction
    indented = "\n".join(f"  | {line}" for line in lines)
    return f"[Thinking...]\n{indented}"


def _render_code_cli(block: dict) -> str:
    """Render a code display block for CLI."""
    code = block.get("code", "")
    language = block.get("language", "")
    header = f"```{language}" if language else "```"
    return f"{header}\n{code}\n```"


def _render_table_cli(block: dict) -> str:
    """Render a table display block for CLI."""
    headers = block.get("headers", [])
    rows = block.get("rows", [])
    if not headers and not rows:
        return "[Table] Empty"

    # Simple text table rendering
    all_rows = [headers] + rows if headers else rows
    # Calculate column widths
    col_count = max(len(r) for r in all_rows) if all_rows else 0
    widths = [0] * col_count
    for row in all_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def _fmt_row(row: list) -> str:
        cells = [str(cell).ljust(widths[i]) for i, cell in enumerate(row)]
        return " | ".join(cells)

    lines = []
    if headers:
        lines.append(_fmt_row(headers))
        lines.append("-" * (sum(widths) + 3 * (col_count - 1)))
    for row in rows:
        lines.append(_fmt_row(row))
    return "\n".join(lines)


def _render_error_cli(block: dict) -> str:
    """Render an error display block for CLI."""
    message = block.get("message", "Unknown error")
    return f"[Error] {message}"


def _render_unknown_cli(block: dict) -> str:
    """Render an unknown display block type for CLI."""
    return f"[Display Block: {block.get('type', 'unknown')}]\n{str(block)}"


_CLI_RENDERERS: dict[str, callable] = {
    "diff": _render_diff_cli,
    "todo": _render_todo_cli,
    "shell": _render_shell_cli,
    "background_task": _render_bg_task_cli,
    "think": _render_think_cli,
    "code": _render_code_cli,
    "table": _render_table_cli,
    "error": _render_error_cli,
    "unknown": _render_unknown_cli,
}


# ── HTML Renderers ───────────────────────────────────────────────────────────


def _render_diff_html(block: dict) -> str:
    """Render a diff display block as HTML."""
    path = html.escape(block.get("path", "<unknown>"))
    old_text = html.escape(block.get("old_text", ""))
    new_text = html.escape(block.get("new_text", ""))

    return (
        f'<div class="display-block diff-block">\n'
        f'  <div class="diff-header">{path}</div>\n'
        f'  <pre class="diff-old"><code>{old_text}</code></pre>\n'
        f'  <pre class="diff-new"><code>{new_text}</code></pre>\n'
        f"</div>"
    )


def _render_todo_html(block: dict) -> str:
    """Render a todo display block as HTML."""
    items = block.get("items", [])
    if not items:
        return '<div class="display-block todo-block"><p>No items</p></div>'

    lines = ['<div class="display-block todo-block"><ul>']
    icons = {
        "pending": "⬜",
        "in_progress": "🔄",
        "done": "✅",
    }
    for item in items:
        status = item.get("status", "pending")
        icon = icons.get(status, "⬜")
        title = html.escape(item.get("title", ""))
        css_class = f"todo-{status}"
        lines.append(f'  <li class="{css_class}">{icon} {title}</li>')
    lines.append("</ul></div>")
    return "\n".join(lines)


def _render_shell_html(block: dict) -> str:
    """Render a shell command display block as HTML."""
    command = html.escape(block.get("command", ""))
    language = html.escape(block.get("language", "bash"))
    return (
        f'<div class="display-block shell-block">\n'
        f'  <pre><code class="language-{language}">${command}</code></pre>\n'
        f"</div>"
    )


def _render_bg_task_html(block: dict) -> str:
    """Render a background task display block as HTML."""
    task_id = html.escape(block.get("task_id", "?"))
    kind = html.escape(block.get("kind", "?"))
    status = html.escape(block.get("status", "?"))
    description = html.escape(block.get("description", ""))

    status_colors = {
        "running": "#2196F3",
        "completed": "#4CAF50",
        "failed": "#f44336",
        "stopped": "#FF9800",
    }
    color = status_colors.get(status, "#9E9E9E")

    return (
        f'<div class="display-block bg-task-block">\n'
        f'  <span class="task-id">[{task_id}]</span>\n'
        f'  <span class="task-desc">{description}</span>\n'
        f'  <span class="task-kind">({kind})</span>\n'
        f'  <span class="task-status" style="color: {color};">{status}</span>\n'
        f"</div>"
    )


def _render_think_html(block: dict) -> str:
    """Render a think display block as HTML."""
    thought = html.escape(block.get("thought", ""))
    return (
        f'<div class="display-block think-block">\n'
        f'  <div class="think-header">💭 Thinking</div>\n'
        f'  <pre class="think-content">{thought}</pre>\n'
        f"</div>"
    )


def _render_code_html(block: dict) -> str:
    """Render a code display block as HTML."""
    code = html.escape(block.get("code", ""))
    language = html.escape(block.get("language", ""))
    return (
        f'<div class="display-block code-block">\n'
        f'  <pre><code class="language-{language}">{code}</code></pre>\n'
        f"</div>"
    )


def _render_table_html(block: dict) -> str:
    """Render a table display block as HTML."""
    headers = block.get("headers", [])
    rows = block.get("rows", [])
    if not headers and not rows:
        return '<div class="display-block table-block"><p>Empty table</p></div>'

    lines = ['<div class="display-block table-block">', "<table>"]
    if headers:
        lines.append("  <tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in headers) + "</tr>")
    for row in rows:
        lines.append("  <tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>")
    lines.extend(["</table>", "</div>"])
    return "\n".join(lines)


def _render_error_html(block: dict) -> str:
    """Render an error display block as HTML."""
    message = html.escape(block.get("message", "Unknown error"))
    return (
        f'<div class="display-block error-block" style="color: #f44336;">\n'
        f'  <strong>Error:</strong> {message}\n'
        f"</div>"
    )


def _render_unknown_html(block: dict) -> str:
    """Render an unknown display block type as HTML."""
    content = html.escape(str(block))
    return f'<div class="display-block unknown-block"><pre>{content}</pre></div>'


_HTML_RENDERERS: dict[str, callable] = {
    "diff": _render_diff_html,
    "todo": _render_todo_html,
    "shell": _render_shell_html,
    "background_task": _render_bg_task_html,
    "think": _render_think_html,
    "code": _render_code_html,
    "table": _render_table_html,
    "error": _render_error_html,
    "unknown": _render_unknown_html,
}


# ── Telegram Renderers ───────────────────────────────────────────────────────


def _render_diff_telegram(block: dict) -> str:
    """Render a diff display block for Telegram (Markdown V2).

    Note: Telegram has limited formatting for diffs, so we keep it simple.
    """
    path = block.get("path", "<unknown>")
    old_text = block.get("old_text", "")
    new_text = block.get("new_text", "")

    # Escape Telegram Markdown V2 special chars
    def _esc(text: str) -> str:
        for c in "_[]()~`>#+-=|{}.!":
            text = text.replace(c, f"\\{c}")
        return text

    return f"📝 *{_esc(path)}*\n```diff\n- {_esc('Old')}\n+ {_esc('New')}\n```"


def _render_todo_telegram(block: dict) -> str:
    """Render a todo display block for Telegram (Markdown V2)."""
    items = block.get("items", [])
    if not items:
        return "📋 *Todo List:* Empty"

    def _esc(text: str) -> str:
        for c in "_[]()~`>#+-=|{}.!":
            text = text.replace(c, f"\\{c}")
        return text

    icons = {
        "pending": "⬜",
        "in_progress": "🔄",
        "done": "✅",
    }
    lines = ["📋 *Todo List:*"]
    for item in items:
        status = item.get("status", "pending")
        icon = icons.get(status, "⬜")
        title = _esc(item.get("title", ""))
        lines.append(f"{icon} {title}")
    return "\n".join(lines)


def _render_shell_telegram(block: dict) -> str:
    """Render a shell command display block for Telegram."""
    command = block.get("command", "")
    return f"```bash\n$ {command}\n```"


def _render_bg_task_telegram(block: dict) -> str:
    """Render a background task display block for Telegram."""
    task_id = block.get("task_id", "?")
    kind = block.get("kind", "?")
    status = block.get("status", "?")
    description = block.get("description", "")

    icons = {
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
        "stopped": "🛑",
    }
    icon = icons.get(status, "❓")

    def _esc(text: str) -> str:
        for c in "_[]()~`>#+-=|{}.!":
            text = text.replace(c, f"\\{c}")
        return text

    return f"{icon} *Task `{task_id}`*\n{_esc(description)}\n({_esc(kind)}, {_esc(status)})"


def _render_think_telegram(block: dict) -> str:
    """Render a think display block for Telegram."""
    thought = block.get("thought", "")
    return f"💭 *Thinking*\n```\n{thought[:3000]}\n```"


def _render_code_telegram(block: dict) -> str:
    """Render a code display block for Telegram."""
    code = block.get("code", "")
    language = block.get("language", "")
    return f"```{language}\n{code[:3000]}\n```"


def _render_table_telegram(block: dict) -> str:
    """Render a table display block for Telegram."""
    headers = block.get("headers", [])
    rows = block.get("rows", [])
    if not headers and not rows:
        return "📊 *Table:* Empty"

    def _esc(text: str) -> str:
        for c in "_[]()~`>#+-=|{}.!":
            text = text.replace(c, f"\\{c}")
        return text

    lines = []
    if headers:
        lines.append(" | ".join(_esc(str(h)) for h in headers))
        lines.append("—" * 20)
    for row in rows:
        lines.append(" | ".join(_esc(str(c)) for c in row))
    return "\n".join(lines)


def _render_error_telegram(block: dict) -> str:
    """Render an error display block for Telegram."""
    message = block.get("message", "Unknown error")

    def _esc(text: str) -> str:
        for c in "_[]()~`>#+-=|{}.!":
            text = text.replace(c, f"\\{c}")
        return text

    return f"❌ *Error:* {_esc(message)}"


def _render_unknown_telegram(block: dict) -> str:
    """Render an unknown display block type for Telegram."""
    return f"```\n{str(block)[:1000]}\n```"


_TG_RENDERERS: dict[str, callable] = {
    "diff": _render_diff_telegram,
    "todo": _render_todo_telegram,
    "shell": _render_shell_telegram,
    "background_task": _render_bg_task_telegram,
    "think": _render_think_telegram,
    "code": _render_code_telegram,
    "table": _render_table_telegram,
    "error": _render_error_telegram,
    "unknown": _render_unknown_telegram,
}
