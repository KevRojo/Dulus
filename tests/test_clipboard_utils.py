"""Tests for ClipboardUtils (Feature 18)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the project root (parent of tests/) is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dulus_tools.clipboard_utils import ClipboardUtils, copy_to_clipboard, paste_from_clipboard


# ── _get_clipboard_command ────────────────────────────────────────────────────


class TestGetClipboardCommand:
    """Tests for platform-specific clipboard command detection."""

    def test_darwin_platform(self) -> None:
        """macOS should return pbcopy/pbpaste."""
        with patch("sys.platform", "darwin"):
            copy_cmd, paste_cmd = ClipboardUtils._get_clipboard_command()
            assert copy_cmd == "pbcopy"
            assert paste_cmd == "pbpaste"

    def test_win32_platform(self) -> None:
        """Windows should return clip/None."""
        with patch("sys.platform", "win32"):
            copy_cmd, paste_cmd = ClipboardUtils._get_clipboard_command()
            assert copy_cmd == "clip"
            assert paste_cmd is None

    def test_linux_no_tool(self) -> None:
        """Linux with no clipboard tool should return (None, None)."""
        with patch("sys.platform", "linux"):
            with patch(
                "subprocess.run", return_value=type("R", (), {"returncode": 1})()
            ):
                copy_cmd, paste_cmd = ClipboardUtils._get_clipboard_command()
                assert copy_cmd is None
                assert paste_cmd is None

    def test_linux_xclip_found(self) -> None:
        """Linux with xclip should return xclip commands."""
        call_count = 0

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call checks 'which xclip' — succeed
            # Subsequent calls check other tools — fail
            r = type("R", (), {"returncode": 0 if call_count == 1 else 1})()
            return r

        with patch("sys.platform", "linux"):
            with patch("subprocess.run", side_effect=fake_run):
                copy_cmd, paste_cmd = ClipboardUtils._get_clipboard_command()
                assert copy_cmd == "xclip -selection clipboard"
                assert paste_cmd == "xclip -selection clipboard -o"


# ── copy_text ─────────────────────────────────────────────────────────────────


class TestCopyText:
    """Tests for copy_text."""

    def test_copy_text_success(self) -> None:
        """copy_text should return True on success."""
        with patch.object(
            ClipboardUtils, "_get_clipboard_command", return_value=("pbcopy", "pbpaste")
        ):
            with patch("subprocess.run", return_value=None) as mock_run:
                result = ClipboardUtils.copy_text("hello")
                assert result is True
                mock_run.assert_called_once()

    def test_copy_text_no_tool(self) -> None:
        """copy_text should return False when no clipboard tool is available."""
        with patch.object(
            ClipboardUtils, "_get_clipboard_command", return_value=(None, None)
        ):
            result = ClipboardUtils.copy_text("hello")
            assert result is False

    def test_copy_text_failure(self) -> None:
        """copy_text should return False on subprocess failure."""
        with patch.object(
            ClipboardUtils, "_get_clipboard_command", return_value=("pbcopy", "pbpaste")
        ):
            with patch(
                "subprocess.run", side_effect=Exception("clipboard failed")
            ):
                result = ClipboardUtils.copy_text("hello")
                assert result is False

    def test_copy_text_windows(self) -> None:
        """copy_text should use utf-16-le encoding on Windows."""
        with patch("sys.platform", "win32"):
            with patch.object(
                ClipboardUtils,
                "_get_clipboard_command",
                return_value=("clip", None),
            ):
                with patch("subprocess.run", return_value=None) as mock_run:
                    ClipboardUtils.copy_text("hello")
                    _, kwargs = mock_run.call_args
                    assert kwargs["input"] == "hello".encode("utf-16-le")


# ── paste_text ────────────────────────────────────────────────────────────────


class TestPasteText:
    """Tests for paste_text."""

    def test_paste_text_success(self) -> None:
        """paste_text should return clipboard content."""
        fake_result = type("R", (), {"stdout": "pasted content"})()
        with patch.object(
            ClipboardUtils, "_get_clipboard_command", return_value=("pbcopy", "pbpaste")
        ):
            with patch("subprocess.run", return_value=fake_result):
                result = ClipboardUtils.paste_text()
                assert result == "pasted content"

    def test_paste_text_no_tool(self) -> None:
        """paste_text should return empty string when no tool is available."""
        with patch.object(
            ClipboardUtils, "_get_clipboard_command", return_value=(None, None)
        ):
            result = ClipboardUtils.paste_text()
            assert result == ""

    def test_paste_text_failure(self) -> None:
        """paste_text should return empty string on failure."""
        with patch.object(
            ClipboardUtils, "_get_clipboard_command", return_value=("pbcopy", "pbpaste")
        ):
            with patch(
                "subprocess.run", side_effect=Exception("paste failed")
            ):
                result = ClipboardUtils.paste_text()
                assert result == ""


# ── copy_file_content ─────────────────────────────────────────────────────────


class TestCopyFileContent:
    """Tests for copy_file_content."""

    def test_copy_full_file(self, tmp_path: Path) -> None:
        """copy_file_content should copy the entire file."""
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")

        with patch.object(ClipboardUtils, "copy_text", return_value=True) as mock_copy:
            result = ClipboardUtils.copy_file_content(str(f))
            assert result is True
            mock_copy.assert_called_once_with("line1\nline2\nline3\n")

    def test_copy_line_range(self, tmp_path: Path) -> None:
        """copy_file_content should copy a specific line range."""
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\nline4\n")

        with patch.object(ClipboardUtils, "copy_text", return_value=True) as mock_copy:
            ClipboardUtils.copy_file_content(str(f), line_start=2, line_end=3)
            mock_copy.assert_called_once_with("line2\nline3\n")

    def test_copy_missing_file(self, tmp_path: Path) -> None:
        """copy_file_content should return False for missing files."""
        result = ClipboardUtils.copy_file_content(str(tmp_path / "missing.txt"))
        assert result is False

    def test_copy_empty_file(self, tmp_path: Path) -> None:
        """copy_file_content should handle empty files."""
        f = tmp_path / "empty.txt"
        f.write_text("")

        with patch.object(ClipboardUtils, "copy_text", return_value=True) as mock_copy:
            result = ClipboardUtils.copy_file_content(str(f))
            assert result is True
            mock_copy.assert_called_once_with("")


# ── is_image_in_clipboard ─────────────────────────────────────────────────────


class TestIsImageInClipboard:
    """Tests for is_image_in_clipboard."""

    def test_darwin_png_signature(self) -> None:
        """Should detect PNG signature on macOS."""
        fake_result = type("R", (), {"stdout": b"\x89PNG\r\n\x1a\n"})()
        with patch("sys.platform", "darwin"):
            with patch("subprocess.run", return_value=fake_result):
                assert ClipboardUtils.is_image_in_clipboard() is True

    def test_darwin_jpeg_signature(self) -> None:
        """Should detect JPEG signature on macOS."""
        # Use the 3-byte prefix that the code checks for
        fake_result = type("R", (), {"stdout": b"\xff\xd8\xff"})()
        with patch("sys.platform", "darwin"):
            with patch("subprocess.run", return_value=fake_result):
                assert ClipboardUtils.is_image_in_clipboard() is True

    def test_darwin_gif_signature(self) -> None:
        """Should detect GIF signature on macOS."""
        fake_result = type("R", (), {"stdout": b"GIF8"})()
        with patch("sys.platform", "darwin"):
            with patch("subprocess.run", return_value=fake_result):
                assert ClipboardUtils.is_image_in_clipboard() is True

    def test_darwin_text_not_image(self) -> None:
        """Should return False for text on macOS."""
        fake_result = type("R", (), {"stdout": b"just text"})()
        with patch("sys.platform", "darwin"):
            with patch("subprocess.run", return_value=fake_result):
                assert ClipboardUtils.is_image_in_clipboard() is False

    def test_non_darwin_platform(self) -> None:
        """Should return False on non-macOS platforms (simplified)."""
        with patch("sys.platform", "linux"):
            assert ClipboardUtils.is_image_in_clipboard() is False

    def test_is_image_error(self) -> None:
        """Should return False on exception."""
        with patch("sys.platform", "darwin"):
            with patch(
                "subprocess.run", side_effect=Exception("clipboard error")
            ):
                assert ClipboardUtils.is_image_in_clipboard() is False


# ── Module-level convenience functions ────────────────────────────────────────


class TestConvenienceFunctions:
    """Tests for copy_to_clipboard and paste_from_clipboard."""

    def test_copy_to_clipboard(self) -> None:
        """copy_to_clipboard should delegate to ClipboardUtils.copy_text."""
        with patch.object(ClipboardUtils, "copy_text", return_value=True) as mock:
            result = copy_to_clipboard("test text")
            assert result is True
            mock.assert_called_once_with("test text")

    def test_paste_from_clipboard(self) -> None:
        """paste_from_clipboard should delegate to ClipboardUtils.paste_text."""
        with patch.object(ClipboardUtils, "paste_text", return_value="pasted") as mock:
            result = paste_from_clipboard()
            assert result == "pasted"
            mock.assert_called_once_with()
