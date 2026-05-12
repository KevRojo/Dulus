"""AddDirManager - Manage additional workspace directories.

Allows users to add directories *outside* the current working directory
into the workspace so that tools (file search, git, etc.) can see them.
This is the backend for the ``/add-dir`` slash command.
"""

import os
from pathlib import Path
from typing import List


class AddDirManager:
    """Manages additional directories in the workspace.

    Each added directory is stored as an absolute path and validated so
    that:

    * it actually exists and is readable,
    * it is not already inside the working directory,
    * it is not a duplicate or nested inside another added directory.
    """

    def __init__(self, work_dir: str) -> None:
        self._work_dir = os.path.abspath(work_dir)
        self._additional_dirs: List[str] = []

    # ------------------------------------------------------------------ #
    #  Add
    # ------------------------------------------------------------------ #

    def add(self, path: str) -> tuple[bool, str]:
        """Add a directory to the workspace.

        Args:
            path: Absolute or relative path.  ``~`` is expanded.

        Returns:
            ``(success, message)`` tuple.
        """
        abs_path = os.path.abspath(os.path.expanduser(path))

        if not os.path.exists(abs_path):
            return False, f"Directory does not exist: {path}"
        if not os.path.isdir(abs_path):
            return False, f"Not a directory: {path}"
        if abs_path in self._additional_dirs:
            return False, f"Directory already in workspace: {path}"
        if self._is_within_directory(abs_path, self._work_dir):
            return (
                False,
                f"Directory is already within the working directory: {path}",
            )
        for existing in self._additional_dirs:
            if self._is_within_directory(abs_path, existing):
                return (
                    False,
                    f"Directory is within an added directory `{existing}`: {path}",
                )

        # Verify we can actually list the directory
        try:
            os.listdir(abs_path)
        except OSError as exc:
            return False, f"Cannot read directory: {path} ({exc})"

        self._additional_dirs.append(abs_path)
        return True, f"Added directory to workspace: {path}"

    # ------------------------------------------------------------------ #
    #  List / Remove
    # ------------------------------------------------------------------ #

    def list(self) -> List[str]:
        """Return a shallow copy of the added directory paths."""
        return self._additional_dirs.copy()

    def remove(self, path: str) -> bool:
        """Remove a directory from the workspace.

        Args:
            path: The path to remove (will be normalised).

        Returns:
            ``True`` if the path was found and removed.
        """
        abs_path = os.path.abspath(os.path.expanduser(path))
        if abs_path in self._additional_dirs:
            self._additional_dirs.remove(abs_path)
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_within_directory(path: str, directory: str) -> bool:
        """Return ``True`` when *path* is the same as, or inside, *directory*."""
        path = os.path.abspath(path)
        directory = os.path.abspath(directory)
        return path == directory or path.startswith(directory + os.sep)

    def get_combined_file_listing(self) -> str:
        """Human-readable listing of working dir + additional dirs."""
        lines = [f"Working directory: {self._work_dir}"]
        for adir in self._additional_dirs:
            lines.append(f"Additional: {adir}")
        return "\n".join(lines)
