"""Tests for ShellMode (Feature 16)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Ensure the project root (parent of tests/) is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dulus_tools.shell_mode import ShellMode


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def shell() -> ShellMode:
    """Return a fresh ShellMode instance."""
    return ShellMode()


# ── State Management ──────────────────────────────────────────────────────────


class TestShellModeState:
    """Tests for shell mode state toggling."""

    def test_default_inactive(self, shell: ShellMode) -> None:
        """Shell mode should start inactive."""
        assert shell.active is False

    def test_activate(self, shell: ShellMode) -> None:
        """activate() should set active to True."""
        shell.activate()
        assert shell.active is True

    def test_deactivate(self, shell: ShellMode) -> None:
        """deactivate() should set active to False."""
        shell.activate()
        assert shell.active is True
        shell.deactivate()
        assert shell.active is False

    def test_toggle_on(self, shell: ShellMode) -> None:
        """toggle() should flip from False to True."""
        result = shell.toggle()
        assert result is True
        assert shell.active is True

    def test_toggle_off(self, shell: ShellMode) -> None:
        """toggle() should flip from True to False."""
        shell.activate()
        result = shell.toggle()
        assert result is False
        assert shell.active is False

    def test_default_shell_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Shell should default from SHELL/COMSPEC environment variable."""
        if os.name == "nt":
            monkeypatch.setenv("COMSPEC", "C:\\Windows\\cmd.exe")
            shell = ShellMode()
            assert shell._shell == "C:\\Windows\\cmd.exe"
        else:
            monkeypatch.setenv("SHELL", "/bin/zsh")
            shell = ShellMode()
            assert shell._shell == "/bin/zsh"

    def test_default_shell_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Shell should fall back to system default when SHELL/COMSPEC is unset."""
        if os.name == "nt":
            monkeypatch.delenv("COMSPEC", raising=False)
            shell = ShellMode()
            assert shell._shell == "cmd.exe"
        else:
            monkeypatch.delenv("SHELL", raising=False)
            shell = ShellMode()
            assert shell._shell == "/bin/bash"


# ── Command Execution ─────────────────────────────────────────────────────────


class TestShellModeExecution:
    """Tests for shell command execution via execute()."""

    @pytest.mark.asyncio
    async def test_execute_echo(self, shell: ShellMode) -> None:
        """execute() should run a simple echo command."""
        result = await shell.execute("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_empty_command(self, shell: ShellMode) -> None:
        """execute() should handle empty commands gracefully."""
        result = await shell.execute("")
        assert result["exit_code"] == 0
        assert "Empty command" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_whitespace_only(self, shell: ShellMode) -> None:
        """execute() should handle whitespace-only commands."""
        result = await shell.execute("   ")
        assert result["exit_code"] == 0
        assert "Empty command" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_stderr_captured(self, shell: ShellMode) -> None:
        """execute() should capture stderr in output."""
        cmd = '''python -c "import sys; sys.stderr.write('error_msg')"'''
        result = await shell.execute(cmd)
        assert result["exit_code"] == 0
        assert "[stderr]" in result["output"]
        assert "error_msg" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_nonzero_exit(self, shell: ShellMode) -> None:
        """execute() should report non-zero exit codes."""
        result = await shell.execute('python -c "import sys; sys.exit(42)"')
        assert result["exit_code"] == 42

    @pytest.mark.asyncio
    async def test_execute_timeout(self, shell: ShellMode) -> None:
        """execute() should handle command timeout."""
        result = await shell.execute('python -c "import time; time.sleep(5)"', timeout=1)
        assert result["exit_code"] == -1
        assert "timed out" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_display_metadata(self, shell: ShellMode) -> None:
        """execute() should include display metadata."""
        result = await shell.execute("echo hi")
        display = result["display"]
        assert len(display) == 1
        assert display[0]["type"] == "shell"
        assert display[0]["command"] == "echo hi"

    @pytest.mark.asyncio
    async def test_execute_cwd(self, shell: ShellMode, tmp_path: Path) -> None:
        """execute() should respect the cwd parameter."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = await shell.execute('python -c "import os; print(os.getcwd())"', cwd=str(subdir))
        assert str(subdir) in result["output"]


# ── History ───────────────────────────────────────────────────────────────────


class TestShellModeHistory:
    """Tests for command history tracking."""

    @pytest.mark.asyncio
    async def test_history_tracked(self, shell: ShellMode) -> None:
        """execute() should append commands to history."""
        await shell.execute("echo one")
        await shell.execute("echo two")
        history = shell.get_history()
        assert history == ["echo one", "echo two"]

    def test_history_is_copy(self, shell: ShellMode) -> None:
        """get_history() should return a copy, not a reference."""
        shell._history.append("manual")
        h1 = shell.get_history()
        h1.clear()
        assert shell._history == ["manual"]

    def test_history_empty_by_default(self, shell: ShellMode) -> None:
        """History should be empty for a new ShellMode."""
        assert shell.get_history() == []
