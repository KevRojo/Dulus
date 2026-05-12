"""ClipboardUtils - Advanced clipboard operations for Dulus."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


class ClipboardUtils:
    """Advanced clipboard operations for cross-platform text handling.

    Provides methods to copy text to and paste text from the system
    clipboard, copy file contents, and detect image data in clipboard.
    Automatically detects the correct clipboard tool for the platform.

    Example:
        ClipboardUtils.copy_text("Hello, world!")
        text = ClipboardUtils.paste_text()
        ClipboardUtils.copy_file_content("/path/to/file.txt", line_start=1, line_end=10)
    """

    @staticmethod
    def _get_clipboard_command() -> tuple[Optional[str], Optional[str]]:
        """Get the appropriate clipboard command for the current platform.

        Returns:
            Tuple of (copy_command, paste_command) or (None, None) if
            no suitable clipboard tool is found.
        """
        if sys.platform == "darwin":
            return ("pbcopy", "pbpaste")
        elif sys.platform == "win32":
            return ("clip", None)  # Windows paste is more complex
        else:
            # Linux — try xclip, xsel, wl-copy in order
            for copy_cmd, paste_cmd in [
                ("xclip -selection clipboard", "xclip -selection clipboard -o"),
                ("xsel --clipboard --input", "xsel --clipboard --output"),
                ("wl-copy", "wl-paste"),
            ]:
                tool = copy_cmd.split()[0]
                result = subprocess.run(
                    ["which", tool],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result.returncode == 0:
                    return (copy_cmd, paste_cmd)
            return (None, None)

    @staticmethod
    def copy_text(text: str) -> bool:
        """Copy text to the clipboard. Cross-platform.

        Args:
            text: The text to copy.

        Returns:
            True if the copy succeeded, False otherwise.
        """
        try:
            copy_cmd, _ = ClipboardUtils._get_clipboard_command()
            if copy_cmd is None:
                return False

            if sys.platform == "win32":
                subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
            else:
                subprocess.run(copy_cmd.split(), input=text.encode("utf-8"), check=True)
            return True
        except Exception:
            return False

    @staticmethod
    def paste_text() -> str:
        """Paste text from the clipboard.

        Returns:
            The clipboard text, or empty string if unavailable.
        """
        try:
            _, paste_cmd = ClipboardUtils._get_clipboard_command()
            if paste_cmd is None:
                return ""

            result = subprocess.run(paste_cmd.split(), capture_output=True, text=True)
            return result.stdout
        except Exception:
            return ""

    @staticmethod
    def copy_file_content(
        file_path: str, line_start: int = 1, line_end: Optional[int] = None
    ) -> bool:
        """Copy a range of lines from a file to the clipboard.

        Args:
            file_path: Path to the file to read.
            line_start: First line to copy (1-indexed).
            line_end: Last line to copy (1-indexed), or None for all remaining.

        Returns:
            True if the file was read and copied successfully.
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False

            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            start = max(0, line_start - 1)
            end = line_end if line_end else len(lines)
            content = "".join(lines[start:end])

            return ClipboardUtils.copy_text(content)
        except Exception:
            return False

    @staticmethod
    def is_image_in_clipboard() -> bool:
        """Check if the clipboard contains image data.

        Performs a basic signature check on clipboard content.

        Returns:
            True if image data signatures are detected.
        """
        try:
            if sys.platform == "darwin":
                result = subprocess.run(["pbpaste"], capture_output=True)
                # Check for common image format signatures
                header = result.stdout[:4]
                return header in (b"\x89PNG", b"\xff\xd8\xff", b"GIF8")
            return False
        except Exception:
            return False


# ── Module-level convenience functions ──────────────────────────────────────


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the clipboard. Convenience wrapper.

    Args:
        text: The text to copy.

    Returns:
        True if the copy succeeded.
    """
    return ClipboardUtils.copy_text(text)


def paste_from_clipboard() -> str:
    """Paste text from the clipboard. Convenience wrapper.

    Returns:
        The clipboard text, or empty string.
    """
    return ClipboardUtils.paste_text()
