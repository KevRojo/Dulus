"""fs-compass — OneDrive-aware path resolution and clean directory trees.

Provides two native Dulus tools:

* ResolvePath: turn a loose human location description into a real absolute path.
* SmartTree: show a pruned, depth-limited directory tree with known folders
  pre-resolved through Windows OneDrive redirection.

Both tools are intentionally read-only and safe to run concurrently.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tool_registry import ToolDef, register_tool


# ── Windows known-folder helpers ─────────────────────────────────────────────

# CSIDL constants for older Windows APIs
_CSIDL_DESKTOP = 0x0010
_CSIDL_PERSONAL = 0x0005
_CSIDL_DOWNLOADS = 0x0047
_CSIDL_MYPICTURES = 0x0027

# Known folder IDs for SHGetKnownFolderPath (Vista+)
_FOLDERID_Desktop = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
_FOLDERID_Documents = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"
_FOLDERID_Downloads = "{374DE290-123F-4565-9164-39C4925E467B}"
_FOLDERID_Pictures = "{33E28130-4E1E-4676-835A-98395C3BC3BB}"
_FOLDERID_OneDrive = "{A52BBA46-E9E1-435f-B3D9-28DAA648C0F6}"


def _get_known_folder_path(folder_id: str) -> Path | None:
    """Resolve a Windows known-folder GUID to a Path, if available."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        ptr = ctypes.c_wchar_p()
        hres = ctypes.windll.shell32.SHGetKnownFolderPath(  # type: ignore[attr-defined]
            ctypes.create_string_buffer(bytes.fromhex(folder_id.replace("{", "").replace("}", "").replace("-", ""))),
            0,
            None,
            ctypes.byref(ptr),
        )
        if hres != 0:
            return None
        path = ptr.value
        ctypes.windll.ole32.CoTaskMemFree(ptr)  # type: ignore[attr-defined]
        return Path(path) if path else None
    except Exception:
        return None


def _get_csidl_path(csidl: int) -> Path | None:
    """Fallback: resolve a CSIDL to a path via SHGetFolderPathW."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_unicode_buffer(260)
        hres = ctypes.windll.shell32.SHGetFolderPathW(  # type: ignore[attr-defined]
            None, csidl, None, 0, buf
        )
        if hres != 0:
            return None
        return Path(buf.value) if buf.value else None
    except Exception:
        return None


def _desktop_path() -> Path:
    return _get_known_folder_path(_FOLDERID_Desktop) or _get_csidl_path(_CSIDL_DESKTOP) or Path.home() / "Desktop"


def _documents_path() -> Path:
    return _get_known_folder_path(_FOLDERID_Documents) or _get_csidl_path(_CSIDL_PERSONAL) or Path.home() / "Documents"


def _downloads_path() -> Path:
    return _get_known_folder_path(_FOLDERID_Downloads) or _get_csidl_path(_CSIDL_DOWNLOADS) or Path.home() / "Downloads"


def _pictures_path() -> Path:
    return _get_known_folder_path(_FOLDERID_Pictures) or _get_csidl_path(_CSIDL_MYPICTURES) or Path.home() / "Pictures"


def _onedrive_path() -> Path | None:
    """Return the OneDrive consumer root, or None if not present."""
    path = _get_known_folder_path(_FOLDERID_OneDrive)
    if path and path.exists():
        return path
    # Fallback environment variables
    for env in ("OneDrive", "ONEDRIVE", "OneDriveConsumer"):
        val = os.environ.get(env)
        if val and Path(val).exists():
            return Path(val)
    return None


# ── Known-folder index ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class _KnownFolder:
    name: str
    aliases: tuple[str, ...]
    resolver: callable


_KNOWN_FOLDERS: list[_KnownFolder] = [
    _KnownFolder("home", ("home", "homedir", "userprofile", "~"), lambda: Path.home()),
    _KnownFolder("desktop", ("desktop", "escritorio"), _desktop_path),
    _KnownFolder("documents", ("documents", "documentos", "docs"), _documents_path),
    _KnownFolder("downloads", ("downloads", "descargas"), _downloads_path),
    _KnownFolder("pictures", ("pictures", "fotos", "imagenes", "images"), _pictures_path),
    _KnownFolder("onedrive", ("onedrive", "one drive", "one-drive"), _onedrive_path),
]

# Build a flat alias -> folder lookup, longest alias first to avoid partial matches.
_ALIAS_TO_FOLDER: dict[str, _KnownFolder] = {}
for _kf in _KNOWN_FOLDERS:
    for _alias in _kf.aliases:
        _ALIAS_TO_FOLDER[_alias] = _kf


# ── Path resolution ──────────────────────────────────────────────────────────

def resolve_path(query: str) -> Path | None:
    r"""Convert a loose description into an absolute Path.

    Examples:
        "desktop" -> C:\Users\...\Desktop
        "onedrive new life desktop interant" -> C:\Users\...\OneDrive\NEW LIFE\Desktop\INTERANT-unified
        "downloads" -> C:\Users\...\Downloads
    """
    original = query
    query = query.strip()
    if not query:
        return Path.cwd()

    # Direct absolute path
    direct = Path(query).expanduser()
    if direct.is_absolute() and direct.exists():
        return direct.resolve()

    # Normalize separators and tokenize
    normalized = query.replace("\\", " ").replace("/", " ")
    tokens = normalized.lower().split()
    if not tokens:
        return Path.cwd()

    # Try to match the longest leading alias sequence.
    matched_folder: Path | None = None
    consumed = 0
    for length in range(min(4, len(tokens)), 0, -1):
        candidate = " ".join(tokens[:length])
        if candidate in _ALIAS_TO_FOLDER:
            resolved = _ALIAS_TO_FOLDER[candidate].resolver()
            if resolved is not None:
                matched_folder = resolved
                consumed = length
                break

    if matched_folder is None:
        # No known folder matched; treat as a relative path or file/folder search.
        candidate = Path(query)
        if candidate.is_absolute():
            return candidate.resolve()
        candidate = Path.cwd() / query
        if candidate.exists():
            return candidate.resolve()
        return None

    # Append remaining tokens as sub-path components, preserving original casing hints.
    remainder = original.split()[consumed:]
    path = matched_folder
    for token in remainder:
        # Expand "~" inside remainder only when it is the only token (unlikely, but safe).
        part = Path(token).expanduser()
        if str(part) == "~" and token == "~":
            continue
        path = path / part

    # If the path does not exist, try a case-insensitive fuzzy match among siblings.
    if not path.exists():
        path = _fuzzy_resolve(path)

    return path.resolve() if path.exists() else None


def _fuzzy_resolve(path: Path) -> Path:
    """Attempt to fix case mismatches by matching each component to a sibling."""
    if path.exists():
        return path
    if path.anchor and len(path.parts) <= 1:
        return path

    # Build upward from the deepest existing ancestor.
    existing = path
    missing: list[str] = []
    while not existing.exists() and existing.parent != existing:
        missing.append(existing.name)
        existing = existing.parent
    if not existing.exists():
        return path

    result = existing
    for wanted in reversed(missing):
        if not result.is_dir():
            return path
        match = _best_sibling_match(result, wanted)
        result = result / (match if match else wanted)
    return result


def _best_sibling_match(parent: Path, wanted: str) -> str | None:
    """Find the closest sibling name by case-insensitive equality, then substring."""
    wanted_lower = wanted.lower()
    try:
        siblings = [e.name for e in os.scandir(parent)]
    except OSError:
        return None

    # Exact case-insensitive match
    for name in siblings:
        if name.lower() == wanted_lower:
            return name

    # Substring match (e.g. "interant" matches "INTERANT-unified")
    for name in siblings:
        if wanted_lower in name.lower() or name.lower() in wanted_lower:
            return name

    return None


# ── Directory tree ───────────────────────────────────────────────────────────

# Directories that add noise and should be pruned by default.
_NOISE_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".dulus", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "dist", "build", "*.egg-info",
    ".next", ".nuxt", ".svelte-kit", "coverage", ".coverage", "htmlcov",
    "target",  # Rust
    "out", ".output",  # static site generators
})


def _is_noise_dir(name: str) -> bool:
    """Return True if a directory name should be skipped while traversing."""
    if name in _NOISE_DIRS:
        return True
    if name.endswith(".egg-info"):
        return True
    return False


@dataclass
class _TreeStats:
    dirs_seen: int = 0
    files_seen: int = 0
    files_omitted: int = 0
    dirs_omitted: int = 0


def build_tree(path: Path | str, depth: int = 2) -> str:
    """Render a clean, pruned directory tree.

    Args:
        path: Absolute path or loose location description.
        depth: How many levels deep to show (1-5, default 2).

    Returns:
        A string with the rendered tree.
    """
    if isinstance(path, str):
        resolved = resolve_path(path)
        if resolved is None:
            resolved = Path(path).expanduser()
            if not resolved.is_absolute():
                resolved = Path.cwd() / resolved
    else:
        resolved = path

    if not resolved.exists():
        return f"Path not found: {resolved}"

    resolved = resolved.resolve()
    depth = max(1, min(5, int(depth)))

    # Header with pre-resolved known folders for the model.
    lines: list[str] = ["[Known folders — pre-resolved, use these directly]"]
    for kf in _KNOWN_FOLDERS:
        folder = kf.resolver()
        if folder and folder.exists():
            lines.append(f"  {kf.aliases[0]:<11} -> {folder}")
    lines.append("")
    lines.append(f"{resolved}  (depth={depth})")

    stats = _TreeStats()
    if resolved.is_dir():
        _walk(resolved, 0, depth, "", lines, stats)

    # Summary if we pruned anything.
    if stats.files_omitted or stats.dirs_omitted:
        total_files = stats.files_seen + stats.files_omitted
        total_dirs = stats.dirs_seen + stats.dirs_omitted
        lines.append(
            f"\n(pruned: {stats.dirs_omitted} dirs, {stats.files_omitted} files "
            f"out of {total_dirs} dirs / {total_files} files)"
        )

    return "\n".join(lines)


def _walk(
    root: Path,
    level: int,
    max_depth: int,
    prefix: str,
    lines: list[str],
    stats: _TreeStats,
) -> None:
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

    # Split and sort entries.
    dirs: list[os.DirEntry] = []
    files: list[os.DirEntry] = []
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            stats.dirs_seen += 1
            if _is_noise_dir(entry.name):
                stats.dirs_omitted += 1
                continue
            dirs.append(entry)
        else:
            stats.files_seen += 1
            files.append(entry)

    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())

    # Cap visible files to keep output tidy.
    max_files = 25 if level == 0 else 10
    visible_files = files[:max_files]
    stats.files_omitted += len(files) - len(visible_files)

    items = dirs + visible_files
    count = len(items)

    for i, entry in enumerate(items):
        is_last = i == count - 1
        connector = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

        if entry.is_dir(follow_symlinks=False):
            lines.append(f"{prefix}{connector}{entry.name}/")
            _walk(Path(entry.path), level + 1, max_depth, child_prefix, lines, stats)
        else:
            lines.append(f"{prefix}{connector}{entry.name}")

    if len(files) > max_files:
        lines.append(f"{prefix}└── … +{len(files) - max_files} more")


# ── Tool schemas & registration ──────────────────────────────────────────────

_RESOLVE_PATH_SCHEMA = {
    "name": "ResolvePath",
    "description": (
        "Turn human-speak into a real absolute path in ONE call. "
        "E.g. 'onedrive desktop interant' -> C:\\...\\OneDrive\\NEW LIFE\\Desktop\\INTERANT-unified. "
        "Understands OneDrive-redirected known folders (Desktop, Documents, Downloads). "
        "ALWAYS try this before exploring with dir/ls when the user names a location loosely."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Loose location description (e.g. 'desktop', 'onedrive desktop interant')",
            },
        },
        "required": ["query"],
    },
}

_SMART_TREE_SCHEMA = {
    "name": "SmartTree",
    "description": (
        "Show a clean, pruned directory tree with Windows known folders "
        "(Desktop/Documents/Downloads) PRE-RESOLVED through OneDrive redirection. "
        "Use this INSTEAD of blind dir/ls hopping — one call shows the real map. "
        "Accepts aliases ('desktop'), fuzzy names ('onedrive desktop interant'), "
        "or absolute paths. Noise dirs (node_modules, .git, caches) are pruned."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Alias, fuzzy description, or absolute path. Empty = home.",
            },
            "depth": {
                "type": "integer",
                "description": "Tree depth 1-5 (default 2). Keep small; go deeper only if needed.",
                "minimum": 1,
                "maximum": 5,
            },
        },
        "required": ["path"],
    },
}


def _resolve_path_tool(params: dict, _config: dict) -> str:
    query = params.get("query", "")
    result = resolve_path(query)
    if result is None:
        return f"Could not resolve: {query}"
    return str(result)


def _smart_tree_tool(params: dict, _config: dict) -> str:
    path = params.get("path", "")
    depth = params.get("depth", 2)
    return build_tree(path, depth)


def _register() -> None:
    register_tool(
        ToolDef(
            name="ResolvePath",
            schema=_RESOLVE_PATH_SCHEMA,
            func=_resolve_path_tool,
            read_only=True,
            concurrent_safe=True,
        )
    )
    register_tool(
        ToolDef(
            name="SmartTree",
            schema=_SMART_TREE_SCHEMA,
            func=_smart_tree_tool,
            read_only=True,
            concurrent_safe=True,
        )
    )


_register()
