"""FS Compass — SmartTree + ResolvePath: the model sees the world like the human does.

Solves the classic "model gets lost in OneDrive/symlink/junction mazes" problem.
Windows moves Desktop/Documents/etc. under OneDrive (e.g. OneDrive\\Desktop)
and models burn 5-10 turns doing blind `ls`/`dir` hops trying to find them.

FS Compass gives the model:
  1. SmartTree   — a pruned, depth-limited tree with KNOWN FOLDERS pre-resolved
                   (reads the Windows registry "User Shell Folders" = the truth
                   of where OneDrive actually put Desktop/Documents/Downloads).
  2. ResolvePath — fuzzy human-speak → real absolute path ("onedrive desktop
                   my-project" → C:\\...\\OneDrive\\Desktop\\my-project)
                   in ONE call, zero exploration.

Lean: stdlib only, no deps.
"""
from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tool_registry import ToolDef, register_tool

# ── noise pruning ─────────────────────────────────────────────────────────────
_NOISE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", ".next", ".nuxt",
    ".cache", ".tox", "site-packages", ".idea", ".vscode", "$RECYCLE.BIN",
    "System Volume Information", ".Trash", "AppData",
}

_MAX_ENTRIES_PER_DIR = 40  # keep output lean


# ── known-folder resolution (the OneDrive fix) ────────────────────────────────

@lru_cache(maxsize=1)
def _known_folders() -> Dict[str, str]:
    """Map friendly names → REAL paths, honoring OneDrive redirection.

    On Windows, reads HKCU "User Shell Folders" — the single source of truth
    for where Desktop/Documents/etc. actually live (OneDrive rewrites these).
    On other OSes, falls back to XDG-ish defaults.
    """
    home = Path.home()
    folders: Dict[str, str] = {"home": str(home)}

    if sys.platform == "win32":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            name_map = {
                "Desktop": "desktop",
                "Personal": "documents",
                "{374DE290-123F-4565-9164-39C4925E467B}": "downloads",
                "My Pictures": "pictures",
                "My Music": "music",
                "My Video": "videos",
            }
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        i += 1
                    except OSError:
                        break
                    friendly = name_map.get(name)
                    if friendly:
                        folders[friendly] = os.path.expandvars(value)
        except Exception:
            pass
        # OneDrive roots (env vars are authoritative)
        for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            val = os.environ.get(var)
            if val:
                folders.setdefault("onedrive", val)

    # portable fallbacks for anything not resolved
    for name in ("desktop", "documents", "downloads", "pictures", "music", "videos"):
        folders.setdefault(name, str(home / name.capitalize()))

    return folders


def _alias_banner() -> str:
    """Human-readable known-folder map, shown at top of SmartTree output."""
    kf = _known_folders()
    lines = ["[Known folders — pre-resolved, use these directly]"]
    for name in ("desktop", "documents", "downloads", "onedrive", "home", "pictures"):
        if name in kf and Path(kf[name]).exists():
            lines.append(f"  {name:<10} -> {kf[name]}")
    return "\n".join(lines)


# ── SmartTree ─────────────────────────────────────────────────────────────────

def _tree(root: Path, depth: int, prefix: str = "", _level: int = 0) -> List[str]:
    if _level >= depth:
        return []
    try:
        entries = sorted(
            root.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
    except (PermissionError, OSError):
        return [f"{prefix}[access denied]"]

    dirs = [e for e in entries if e.is_dir() and e.name not in _NOISE_DIRS
            and not e.name.startswith(("~", "."))]
    files = [e for e in entries if e.is_file()]
    shown = dirs + files
    hidden = len(entries) - len(shown)
    out: List[str] = []
    for i, entry in enumerate(shown[:_MAX_ENTRIES_PER_DIR]):
        last = i == min(len(shown), _MAX_ENTRIES_PER_DIR) - 1
        branch = "└── " if last else "├── "
        cont = "    " if last else "│   "
        if entry.is_dir():
            out.append(f"{prefix}{branch}{entry.name}/")
            out.extend(_tree(entry, depth, prefix + cont, _level + 1))
        else:
            out.append(f"{prefix}{branch}{entry.name}")
    overflow = len(shown) - _MAX_ENTRIES_PER_DIR
    if overflow > 0:
        out.append(f"{prefix}└── … +{overflow} more")
    elif hidden > 0 and _level == 0:
        out.append(f"{prefix}    ({hidden} noise/hidden entries pruned)")
    return out


def _smart_tree(params: dict, config: dict) -> str:
    raw = (params.get("path") or "").strip()
    depth = max(1, min(int(params.get("depth", 2)), 5))

    if not raw or raw.lower() in ("~", "home"):
        target = Path.home()
    else:
        resolved = _resolve(raw)
        if resolved is None:
            return (f"Could not resolve '{raw}'.\n\n{_alias_banner()}\n\n"
                    f"Tip: try ResolvePath with looser words, or pass an absolute path.")
        target = Path(resolved)

    if not target.exists():
        return f"Path does not exist: {target}\n\n{_alias_banner()}"

    lines = [_alias_banner(), "", f"{target}  (depth={depth})"]
    lines.extend(_tree(target, depth))
    return "\n".join(lines)


# ── ResolvePath (fuzzy human-speak → absolute path) ───────────────────────────

def _score_candidate(tokens: List[str], path_str: str) -> int:
    low = path_str.lower()
    return sum(1 for t in tokens if t in low)


def _resolve(query: str) -> Optional[str]:
    """Resolve human-speak like 'onedrive desktop my-project' to a real path."""
    q = query.strip().strip('"').strip("'")
    # already a valid path?
    if Path(q).expanduser().exists():
        return str(Path(q).expanduser().resolve())

    tokens = [t for t in re.split(r"[\s/\\]+", q.lower()) if t]
    if not tokens:
        return None

    kf = _known_folders()
    # direct alias hit ("desktop", "downloads"...)
    if len(tokens) == 1 and tokens[0] in kf:
        return kf[tokens[0]]

    # anchor: the deepest known folder mentioned in the query
    anchor: Optional[Path] = None
    remaining = list(tokens)
    for name, p in sorted(kf.items(), key=lambda kv: -len(kv[1])):
        if name in remaining and Path(p).exists():
            anchor = Path(p)
            remaining.remove(name)
            # 'onedrive desktop x' → prefer the desktop INSIDE onedrive if both hit
            for name2, p2 in kf.items():
                if name2 in remaining and Path(p2).exists() and str(p2).lower().startswith(str(p).lower()):
                    anchor = Path(p2)
                    remaining.remove(name2)
                    break
            break
    anchored = anchor is not None
    if anchor is None:
        anchor = Path.home()

    # walk down: at each level pick the best-matching child for leading tokens
    current = anchor
    matched_any = anchored
    while remaining:
        try:
            children = [c for c in current.iterdir() if c.is_dir()  # type: ignore[union-attr]
                        and c.name not in _NOISE_DIRS]  # type: ignore[union-attr]
        except (PermissionError, OSError):
            break
        best: Tuple[int, Optional[Path]] = (0, None)
        for child in children:
            s = _score_candidate(remaining, child.name.lower())  # type: ignore[union-attr]
            if s > best[0]:
                best = (s, child)
        if best[1] is None:
            # try one level deeper (BFS-lite, bounded)
            deeper_best: Tuple[int, Optional[Path]] = (0, None)
            for child in children[:60]:
                try:
                    for gchild in child.iterdir():  # type: ignore[union-attr]
                        if gchild.is_dir() and gchild.name not in _NOISE_DIRS:  # type: ignore[union-attr]
                            s = _score_candidate(remaining, gchild.name.lower())  # type: ignore[union-attr]
                            if s > deeper_best[0]:
                                deeper_best = (s, gchild)
                except (PermissionError, OSError):
                    continue
            if deeper_best[1] is None:
                break
            best = deeper_best
        current = best[1]
        matched = [t for t in remaining if t in current.name.lower()]  # type: ignore[union-attr]
        for t in matched:
            remaining.remove(t)
            matched_any = True
        if not matched:
            break

    return str(current) if matched_any else None


def _resolve_path_tool(params: dict, config: dict) -> str:
    query = params.get("query", "")
    result = _resolve(query)
    if result and Path(result).exists():
        kind = "dir" if Path(result).is_dir() else "file"
        return f"{result}  [{kind}]"
    return (f"No confident match for '{query}'.\n\n{_alias_banner()}\n\n"
            f"Try adding a distinctive folder-name fragment.")


# ── schemas + registration ────────────────────────────────────────────────────

_SMART_TREE_SCHEMA = {
    "name": "SmartTree",
    "description": (
        "Show a clean, pruned directory tree with Windows known folders "
        "(Desktop/Documents/Downloads) PRE-RESOLVED through OneDrive redirection. "
        "Use this INSTEAD of blind `dir`/`ls` hopping — one call shows the real map. "
        "Accepts aliases ('desktop'), fuzzy names ('onedrive desktop my-project'), or "
        "absolute paths. Noise dirs (node_modules, .git, caches) are pruned."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string",
                     "description": "Alias, fuzzy description, or absolute path. Empty = home."},
            "depth": {"type": "integer",
                      "description": "Tree depth 1-5 (default 2). Keep small; go deeper only if needed."},
        },
    },
}

_RESOLVE_PATH_SCHEMA = {
    "name": "ResolvePath",
    "description": (
        "Turn human-speak into a real absolute path in ONE call. "
        "E.g. 'onedrive desktop my-project' -> C:\\...\\OneDrive\\Desktop\\my-project. "
        "Understands OneDrive-redirected known folders (Desktop, Documents, Downloads). "
        "ALWAYS try this before exploring with dir/ls when the user names a location loosely."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string",
                      "description": "Loose location description (e.g. 'desktop', 'onedrive desktop my-project')"},
        },
        "required": ["query"],
    },
}


def register_fs_compass() -> int:
    register_tool(ToolDef(
        name="SmartTree", schema=_SMART_TREE_SCHEMA, func=_smart_tree,
        read_only=True, concurrent_safe=True,
    ))
    register_tool(ToolDef(
        name="ResolvePath", schema=_RESOLVE_PATH_SCHEMA, func=_resolve_path_tool,
        read_only=True, concurrent_safe=True,
    ))
    return 2
