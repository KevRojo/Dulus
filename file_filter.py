"""Lightweight file-listing utilities for @-mention path completion.

Provides two strategies:
  - ``list_files_git`` — fast, uses ``git ls-files`` when inside a repo.
  - ``list_files_walk`` — fallback, walks the directory tree manually.
  - ``detect_git`` — returns True if *root* is inside a git work-tree.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional

# Directories to always skip during manual walk
_SKIP_DIRS = frozenset((
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".tox", "dist", "build",
    ".eggs", "*.egg-info",
))


def detect_git(root: Path | str) -> bool:
    """Return True if *root* is inside a Git work-tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def list_files_git(root: Path | str, scope: Optional[str] = None) -> List[str]:
    """List tracked files via ``git ls-files``.

    *scope* optionally restricts to a sub-directory (relative to *root*).
    """
    cmd = ["git", "ls-files"]
    if scope:
        cmd.append(scope)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line]
    except Exception:
        return []


def list_files_walk(
    root: Path | str,
    scope: Optional[str] = None,
    *,
    limit: int = 1000,
) -> List[str]:
    """Walk the directory tree and return relative paths (up to *limit*)."""
    base = Path(root)
    if scope:
        base = base / scope
    if not base.is_dir():
        return []

    paths: List[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        # Prune skipped directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.endswith(".egg-info")
        ]
        for fname in filenames:
            full = Path(dirpath) / fname
            try:
                rel = str(full.relative_to(root))
            except ValueError:
                rel = str(full)
            paths.append(rel.replace("\\", "/"))
            if len(paths) >= limit:
                return paths
    return paths
