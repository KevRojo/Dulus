"""TreeLs — simple, cross-platform directory tree listing.

Provides one native Dulus tool:

* TreeLs: render a clean directory tree for a given path.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from tool_registry import ToolDef, register_tool


# Directories that add noise and should be skipped by default.
_NOISE_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".dulus",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", "dist", "build",
    ".next", ".nuxt", ".svelte-kit", "coverage", ".coverage", "htmlcov",
    "target", "out", ".output",
})


def _is_noise(name: str) -> bool:
    """Return True if a directory name should be skipped while traversing."""
    if name in _NOISE_DIRS:
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def _resolve_path(path: str) -> Path:
    """Resolve a user-supplied path to an absolute Path."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return Path.cwd() / candidate


def build_tree(path: str | Path, depth: int = 2) -> str:
    """Render a clean directory tree.

    Args:
        path: Absolute or relative path to render.
        depth: How many levels deep to show (1-5, default 2).

    Returns:
        A string with the rendered tree, or an error message.
    """
    resolved = _resolve_path(str(path))

    if not resolved.exists():
        return f"Path not found: {resolved}"
    if not resolved.is_dir():
        return f"Not a directory: {resolved}"

    resolved = resolved.resolve()
    depth = max(1, min(5, int(depth)))

    lines: list[str] = [f"{resolved}  (depth={depth})"]
    _walk(resolved, 0, depth, "", lines)
    return "\n".join(lines)


def _walk(root: Path, level: int, max_depth: int, prefix: str, lines: list[str]) -> None:
    """Recursively append tree entries to *lines*."""
    if level >= max_depth:
        return

    try:
        entries = list(os.scandir(root))
    except PermissionError:
        lines.append(f"{prefix}[permission denied]")
        return
    except OSError as exc:
        lines.append(f"{prefix}[error: {exc}]")
        return

    dirs: list[os.DirEntry] = []
    files: list[os.DirEntry] = []
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            if _is_noise(entry.name):
                continue
            dirs.append(entry)
        else:
            files.append(entry)

    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())

    max_files = 25 if level == 0 else 10
    visible_files = files[:max_files]

    items = dirs + visible_files
    count = len(items)

    for i, entry in enumerate(items):
        is_last = i == count - 1
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

        if entry.is_dir(follow_symlinks=False):
            lines.append(f"{prefix}{connector}{entry.name}/")
            _walk(Path(entry.path), level + 1, max_depth, child_prefix, lines)
        else:
            lines.append(f"{prefix}{connector}{entry.name}")

    if len(files) > max_files:
        lines.append(f"{prefix}└── … +{len(files) - max_files} more files")


# ── Tool schema & registration ─────────────────────────────────────────────

_TREE_LS_SCHEMA = {
    "name": "TreeLs",
    "description": (
        "Render a clean directory tree for a given path. "
        "Skips noisy directories like .git, node_modules, __pycache__, etc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to list. Defaults to the current working directory.",
            },
            "depth": {
                "type": "integer",
                "description": "Tree depth 1-5 (default 2).",
                "minimum": 1,
                "maximum": 5,
            },
        },
        "required": ["path"],
    },
}


def _tree_ls_tool(params: dict, _config: dict) -> str:
    path = params.get("path", ".")
    depth = params.get("depth", 2)
    return build_tree(path, depth)


register_tool(
    ToolDef(
        name="TreeLs",
        schema=_TREE_LS_SCHEMA,
        func=_tree_ls_tool,
        read_only=True,
        concurrent_safe=True,
    )
)
