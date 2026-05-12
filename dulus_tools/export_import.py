"""Import/Export System - Session import and export.

Provides exporters that convert Dulus conversation history into various
external formats (Markdown, JSON, plain text) and importers that can
read those formats back, or pull in another session's wire log.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


# --------------------------------------------------------------------------- #
#  Exporters
# --------------------------------------------------------------------------- #


class SessionExporter:
    """Export session conversation history to various file formats."""

    # -- Markdown ---------------------------------------------------------- #

    def export_markdown(
        self,
        history: List[Dict[str, Any]],
        output_path: Path,
        session_id: str = "",
        token_count: int = 0,
    ) -> Tuple[Path, int]:
        """Export conversation history to a Markdown file.

        Args:
            history: List of message dicts, each with at least ``role``
                and ``content`` keys.
            output_path: Destination file path.  Parent directories are
                created automatically.
            session_id: Optional session identifier shown in the header.
            token_count: Optional token count shown in the header.

        Returns:
            ``(output_path, message_count)`` tuple.
        """
        lines: List[str] = [
            f"# Session Export: {session_id}",
            "",
            f"- **Exported**: {datetime.now().isoformat()}",
            f"- **Messages**: {len(history)}",
            f"- **Tokens**: {token_count}",
            "",
        ]

        count = 0
        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"## {role.upper()}")
            lines.append("")
            if isinstance(content, str):
                lines.append(content)
            else:
                lines.append(json.dumps(content, indent=2, ensure_ascii=False))
            lines.append("")
            count += 1

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path, count

    # -- JSON -------------------------------------------------------------- #

    def export_json(
        self,
        history: List[Dict[str, Any]],
        output_path: Path,
        session_id: str = "",
        token_count: int = 0,
    ) -> Tuple[Path, int]:
        """Export conversation history to a JSON file.

        The JSON structure contains metadata (session_id, export time,
        message count, token count) plus the raw messages array.

        Returns:
            ``(output_path, message_count)`` tuple.
        """
        data: Dict[str, Any] = {
            "session_id": session_id,
            "exported_at": datetime.now().isoformat(),
            "message_count": len(history),
            "token_count": token_count,
            "messages": history,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path, len(history)

    # -- Plain text -------------------------------------------------------- #

    def export_text(
        self,
        history: List[Dict[str, Any]],
        output_path: Path,
    ) -> Tuple[Path, int]:
        """Export conversation history to a plain-text file.

        Each line is formatted as ``[role] content``.

        Returns:
            ``(output_path, message_count)`` tuple.
        """
        lines: List[str] = []
        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            text = content if isinstance(content, str) else json.dumps(content)
            lines.append(f"[{role}] {text}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path, len(history)


# --------------------------------------------------------------------------- #
#  Importers
# --------------------------------------------------------------------------- #


class SessionImporter:
    """Import session data from various external sources."""

    def import_from_file(
        self,
        file_path: str,
        max_context_size: Optional[int] = None,
    ) -> Tuple[str, int]:
        """Import from a file on disk.

        Supports ``.json`` (Dulus export format), ``.md`` / ``.markdown``
        and plain text files.

        Args:
            file_path: Absolute or relative path to the file.
            max_context_size: Optional byte limit; content beyond this
                is silently truncated.

        Returns:
            ``(source_description, content_length)`` tuple.
        """
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}", 0

        content = path.read_text(encoding="utf-8")

        if max_context_size is not None and len(content) > max_context_size:
            content = content[:max_context_size]

        if path.suffix == ".json":
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return f"Error: Invalid JSON in {file_path}", 0
            messages = data.get("messages", [])
            return f"file (JSON, {len(messages)} messages)", len(content)
        elif path.suffix in (".md", ".markdown"):
            return f"file (Markdown, {len(content)} chars)", len(content)
        else:
            return f"file (Text, {len(content)} chars)", len(content)

    def import_from_session_id(
        self,
        session_id: str,
        sessions_root: Optional[str] = None,
    ) -> Tuple[str, int]:
        """Import from another Dulus session's wire log.

        Args:
            session_id: The session directory name.
            sessions_root: Parent directory that contains session dirs.
                Defaults to ``~/.dulus/sessions``.

        Returns:
            ``(source_description, content_length)`` tuple.
        """
        if sessions_root is None:
            sessions_root = os.path.expanduser("~/.dulus/sessions")

        session_dir = Path(sessions_root) / session_id
        wire_path = session_dir / "wire.jsonl"

        if not wire_path.exists():
            return f"Error: Session {session_id} not found", 0

        content = wire_path.read_text(encoding="utf-8")
        lines = [ln for ln in content.split("\n") if ln.strip()]
        return f"session {session_id} ({len(lines)} lines)", len(content)
