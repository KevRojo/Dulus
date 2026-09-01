"""Workspace Isolate — keep Write/Edit/Bash mutations inside the workspace.

When ``config["isolate"]`` is ON, Dulus may still *read* anywhere, but it must
not *modify* files outside the locked workspace root (plus any ``/add-dir``
roots the user explicitly added).

The lock root is frozen at toggle-ON time into ``config["isolate_root"]`` so a
later ``/cwd`` outside the bubble cannot silently expand the sandbox.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


_WORKSPACES_DIR = Path.home() / ".dulus" / "workspaces"

# Bash tokens that typically mutate the filesystem. Best-effort gate only —
# Write/Edit/NotebookEdit are the hard path; Bash is a second line of defense.
_MUTATING_BASH = re.compile(
    r"(?:^|[\s;|&])(?:"
    r"rm|rmdir|unlink|mv|cp|install|tee|dd|truncate|chmod|chown|chgrp|"
    r"mkdir|touch|ln|rsync|sed|perl|ruby|python|python3|node|npm|pnpm|yarn|"
    r"pip|pip3|cargo|go|make|cmake|git|docker|kubectl|helm|"
    r"sh|bash|zsh|fish|cmd|powershell|pwsh"
    r")\b",
    re.IGNORECASE,
)

# Absolute / home / drive paths appearing in a shell command.
_PATH_TOKEN = re.compile(
    r"(?P<path>"
    r"~/[^\s'\"`;|&<>]+"          # ~/foo
    r"|/[^\s'\"`;|&<>]+"          # /abs/path
    r"|[A-Za-z]:\\[^\s'\"`;|&<>]+"  # Windows drive path
    r")"
)


def is_isolate_on(config: dict | None) -> bool:
    return bool(config and config.get("isolate"))


def current_workspace_root() -> Path:
    """Best-effort workspace root for the current process cwd.

    Prefer ``~/.dulus/workspaces/<name>`` when cwd lives inside a named
    workspace; otherwise freeze on cwd itself.
    """
    cwd = Path.cwd().resolve()
    try:
        root = _WORKSPACES_DIR.resolve()
        if root == cwd or root in cwd.parents:
            rel = cwd.relative_to(root)
            if rel.parts:
                return (root / rel.parts[0]).resolve()
    except Exception:
        pass
    return cwd


def freeze_isolate_root(config: dict) -> str:
    """Set ``isolate_root`` to the current workspace (or cwd) and return it."""
    root = str(current_workspace_root())
    config["isolate_root"] = root
    return root


def isolate_root(config: dict | None) -> Path:
    """Return the locked root; fall back to live workspace if unset."""
    if config:
        raw = config.get("isolate_root")
        if raw:
            try:
                return Path(str(raw)).expanduser().resolve()
            except Exception:
                pass
    return current_workspace_root()


def _add_dir_roots(config: dict | None) -> list[Path]:
    if not config:
        return []
    roots: list[Path] = []
    mgr = config.get("_add_dir_manager")
    try:
        paths = list(mgr.list()) if mgr is not None else []
    except Exception:
        paths = []
    # Also honour a plain list if something stashed one.
    extra = config.get("isolate_extra_roots") or config.get("add_dirs") or []
    if isinstance(extra, (list, tuple)):
        paths = list(paths) + [str(p) for p in extra]
    for p in paths:
        try:
            roots.append(Path(str(p)).expanduser().resolve())
        except Exception:
            continue
    return roots


def allowed_roots(config: dict | None) -> list[Path]:
    """Roots where mutations are allowed under Isolate ON."""
    roots = [isolate_root(config)]
    roots.extend(_add_dir_roots(config))
    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
    except Exception:
        return False


def resolve_path(path: str | os.PathLike, *, cwd: str | Path | None = None) -> Path:
    """Resolve a user/tool path the same way Write/Edit would."""
    raw = os.path.expanduser(str(path))
    p = Path(raw)
    if not p.is_absolute():
        base = Path(cwd) if cwd is not None else Path.cwd()
        p = base / p
    try:
        # resolve(strict=False) follows parents that exist; for brand-new files
        # it still anchors under the real parent tree.
        return p.resolve(strict=False)
    except Exception:
        return Path(os.path.abspath(str(p)))


def path_allowed(path: str | os.PathLike, config: dict | None, *, cwd: str | Path | None = None) -> bool:
    if not is_isolate_on(config):
        return True
    target = resolve_path(path, cwd=cwd)
    return any(_is_within(target, root) for root in allowed_roots(config))


# Canonical line Dulus should relay to the user when Isolate blocks work.
_USER_HINT = (
    "tell the user (in their language): "
    "\"/isolate no me deja trabajar fuera del workspace — si quieres, escribe "
    "/isolate off y te puedo ayudar afuera. "
    "O /add-dir <path> si solo necesitas sumar esa carpeta al bubble.\""
)


def deny_message(path: str | os.PathLike, config: dict | None, *, cwd: str | Path | None = None) -> str:
    target = resolve_path(path, cwd=cwd)
    roots = ", ".join(str(r) for r in allowed_roots(config))
    return (
        f"Denied: Isolate ON — cannot modify files outside the current workspace.\n"
        f"  path:  {target}\n"
        f"  allow: {roots}\n"
        f"  tip:   /isolate off   or   /add-dir <path>\n"
        f"  YOU:   {_USER_HINT}"
    )


def check_write_path(path: str | os.PathLike, config: dict | None, *, cwd: str | Path | None = None) -> Optional[str]:
    """Return an error string if the write is blocked, else None."""
    if not is_isolate_on(config):
        return None
    if path_allowed(path, config, cwd=cwd):
        return None
    return deny_message(path, config, cwd=cwd)


def _extract_path_tokens(command: str) -> list[str]:
    return [m.group("path") for m in _PATH_TOKEN.finditer(command or "")]


def check_bash_command(command: str, config: dict | None, *, cwd: str | Path | None = None) -> Optional[str]:
    """Best-effort Bash gate under Isolate.

    Blocks commands that both (a) look mutating and (b) reference an absolute /
    home path outside the allowed roots. Relative paths stay inside cwd, which
    itself must already sit under the locked root (or the command is blocked).
    """
    if not is_isolate_on(config):
        return None
    cmd = command or ""
    if not cmd.strip():
        return None

    roots = allowed_roots(config)
    base = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()

    # cwd itself must be inside the bubble — otherwise every relative write escapes.
    if not any(_is_within(base, root) for root in roots):
        return (
            f"Denied: Isolate ON — shell cwd is outside the locked workspace.\n"
            f"  cwd:   {base}\n"
            f"  allow: {', '.join(str(r) for r in roots)}\n"
            f"  tip:   cd back into the workspace, or /isolate off\n"
            f"  YOU:   {_USER_HINT}"
        )

    # Non-mutating commands (ls, cat, rg, curl…) may touch outside paths for reads.
    looks_mutating = bool(_MUTATING_BASH.search(cmd)) or (">" in cmd)
    if not looks_mutating:
        return None

    offenders: list[str] = []
    for tok in _extract_path_tokens(cmd):
        try:
            resolved = resolve_path(tok, cwd=base)
        except Exception:
            continue
        if not any(_is_within(resolved, root) for root in roots):
            offenders.append(f"{tok} → {resolved}")

    if not offenders:
        return None

    return (
        f"Denied: Isolate ON — bash would mutate path(s) outside the workspace.\n"
        f"  cmd:   {cmd[:200]}{'…' if len(cmd) > 200 else ''}\n"
        f"  bad:   {'; '.join(offenders[:5])}\n"
        f"  allow: {', '.join(str(r) for r in roots)}\n"
        f"  tip:   /isolate off   or   /add-dir <path>\n"
        f"  YOU:   {_USER_HINT}"
    )


def status_lines(config: dict | None) -> list[str]:
    """Human-readable status block for /isolate and /help."""
    on = is_isolate_on(config)
    lines = [f"Isolate: {'ON' if on else 'OFF'}"]
    if on:
        lines.append(f"  root:  {isolate_root(config)}")
        extras = _add_dir_roots(config)
        if extras:
            lines.append("  extra: " + ", ".join(str(p) for p in extras))
        lines.append("  rule:  Write/Edit/Bash cannot modify files outside the workspace")
    else:
        lines.append("  rule:  off — Dulus can modify files anywhere the OS allows")
        lines.append("  tip:   /isolate on  → lock writes to the current workspace")
    return lines


def prompt_fragment(config: dict | None) -> str:
    """Byte-stable system-prompt line when Isolate is ON (empty when OFF)."""
    if not is_isolate_on(config):
        return ""
    root = isolate_root(config)
    extras = _add_dir_roots(config)
    extra_s = ""
    if extras:
        extra_s = " + " + ", ".join(str(p) for p in extras)
    return (
        f"# Isolate: ON — HARD RULE: you MUST NOT modify files outside the current "
        f"workspace root ({root}{extra_s}). Write/Edit/NotebookEdit/Bash mutations "
        f"outside this bubble are rejected by the runtime. Reads outside are OK. "
        f"When a tool returns Denied: Isolate ON, do NOT keep retrying outside paths — "
        f"tell the user clearly (their language): \"/isolate no me deja trabajar fuera "
        f"del workspace — si quieres, escribe /isolate off y te puedo ayudar afuera. "
        f"O /add-dir <path> si solo necesitas sumar esa carpeta.\" "
        f"Never silently work around the lock.\n"
    )
