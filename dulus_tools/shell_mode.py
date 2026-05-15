"""ShellMode - Toggle between shell commands and agent mode."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional


def _default_shell() -> str:
    if os.name == "nt":
        return os.environ.get("COMSPEC", "cmd.exe")
    return os.environ.get("SHELL", "/bin/bash")


def _default_shell_name() -> str:
    return "cmd" if os.name == "nt" else "bash"


@dataclass
class ShellMode:
    """Shell mode for Dulus - execute commands directly.

    Provides a toggleable shell execution mode that allows the agent
    to run shell commands directly via subprocess. Tracks command
    history and supports configurable shell executable and timeouts.

    Example:
        shell = ShellMode()
        shell.activate()
        result = await shell.execute("ls -la")
        print(result["output"])
        shell.deactivate()
    """

    _active: bool = False
    _shell: str = field(default_factory=_default_shell)
    _shell_name: str = field(default_factory=_default_shell_name)
    _history: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        """Whether shell mode is currently active."""
        return self._active

    def toggle(self) -> bool:
        """Toggle shell mode on/off. Returns the new state."""
        self._active = not self._active
        return self._active

    def activate(self) -> None:
        """Activate shell mode."""
        self._active = True

    def deactivate(self) -> None:
        """Deactivate shell mode."""
        self._active = False

    async def execute(
        self, command: str, cwd: Optional[str] = None, timeout: int = 60
    ) -> dict[str, object]:
        """Execute a shell command directly.

        Args:
            command: The shell command to execute.
            cwd: Working directory for the command. None uses current dir.
            timeout: Maximum seconds to wait for command completion.

        Returns:
            Dict with keys: output (str), message (str), exit_code (int),
            and display (list of display metadata dicts).
        """
        if not command.strip():
            return {"output": "", "message": "Empty command", "exit_code": 0}

        self._history.append(command)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                # Force UTF-8 + replace — Windows defaults to cp1252 for
                # text mode pipes, which crashes the reader thread with a
                # UnicodeDecodeError the moment anything emits an emoji or
                # accented byte (very common on Spanish dev boxes). Issue
                # report by KevRojo, 2026-05-14.
                encoding="utf-8",
                errors="replace",
                cwd=cwd,
                timeout=timeout,
                executable=self._shell,
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            return {
                "output": output,
                "message": f"Command exited with code {result.returncode}",
                "exit_code": result.returncode,
                "display": [
                    {"type": "shell", "language": self._shell_name, "command": command}
                ],
            }
        except subprocess.TimeoutExpired:
            return {
                "output": "",
                "message": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "display": [
                    {"type": "shell", "language": self._shell_name, "command": command}
                ],
            }
        except Exception as e:
            return {
                "output": "",
                "message": f"Error: {e}",
                "exit_code": -1,
                "display": [
                    {"type": "shell", "language": self._shell_name, "command": command}
                ],
            }

    def get_history(self) -> list[str]:
        """Return a copy of the command history."""
        return self._history.copy()
