"""Plugin store: install/uninstall/enable/disable/update + config persistence."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from .types import PluginEntry, PluginManifest, PluginScope, parse_plugin_identifier, sanitize_plugin_name

# ── Config paths ──────────────────────────────────────────────────────────────

USER_PLUGIN_DIR  = Path.home() / ".falcon" / "plugins"
USER_PLUGIN_CFG  = Path.home() / ".falcon" / "plugins.json"

def _project_plugin_dir() -> Path:
    return Path.cwd() / ".falcon-context" / "plugins"

def _project_plugin_cfg() -> Path:
    return Path.cwd() / ".falcon-context" / "plugins.json"


# ── Config read/write ─────────────────────────────────────────────────────────

def _read_cfg(cfg_path: Path) -> dict:
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"plugins": {}}


def _write_cfg(cfg_path: Path, data: dict) -> None:
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _plugin_dir_for(scope: PluginScope) -> Path:
    return USER_PLUGIN_DIR if scope == PluginScope.USER else _project_plugin_dir()


def _plugin_cfg_for(scope: PluginScope) -> Path:
    return USER_PLUGIN_CFG if scope == PluginScope.USER else _project_plugin_cfg()


# ── List ──────────────────────────────────────────────────────────────────────

def list_plugins(scope: PluginScope | None = None) -> list[PluginEntry]:
    """Return all installed plugins (optionally filtered by scope)."""
    entries: list[PluginEntry] = []
    scopes = [PluginScope.USER, PluginScope.PROJECT] if scope is None else [scope]
    for sc in scopes:
        cfg = _read_cfg(_plugin_cfg_for(sc))
        for name, data in cfg.get("plugins", {}).items():
            entry = PluginEntry.from_dict(data)
            entry.manifest = PluginManifest.from_plugin_dir(entry.install_dir)
            entries.append(entry)
    return entries


def get_plugin(name: str, scope: PluginScope | None = None) -> PluginEntry | None:
    for entry in list_plugins(scope):
        if entry.name == name:
            return entry
    return None


# ── Install ───────────────────────────────────────────────────────────────────

def install_plugin(
    identifier: str,
    scope: PluginScope = PluginScope.USER,
    force: bool = False,
) -> tuple[bool, str]:
    """
    Install a plugin. identifier = 'name' | 'name@git_url' | 'name@local_path'.
    Returns (success, message).
    """
    name, source = parse_plugin_identifier(identifier)
    safe_name = sanitize_plugin_name(name)

    # Check if already installed
    existing = get_plugin(safe_name, scope)
    if existing and not force:
        return False, f"Plugin '{safe_name}' is already installed in {scope.value} scope. Use --force to reinstall."

    plugin_dir = _plugin_dir_for(scope) / safe_name
    deps_to_install = []

    try:
        if source is None:
            # No source → treat name as a local path if it exists, else error
            local = Path(name)
            if local.exists() and local.is_dir():
                source = str(local.resolve())
            else:
                return False, (
                    f"No source specified for '{name}'. "
                    "Provide 'name@git_url' or 'name@/local/path'."
                )

        # Install from local path or git
        if plugin_dir.exists() and force:
            shutil.rmtree(plugin_dir)

        if _is_git_url(source):
            ok, msg = _clone_plugin(source, plugin_dir)
            if not ok:
                return False, msg
        else:
            local_src = Path(source)
            if not local_src.exists():
                return False, f"Local path not found: {source}"
            shutil.copytree(str(local_src), str(plugin_dir))

        # Load and validate manifest
        manifest = PluginManifest.from_plugin_dir(plugin_dir)
        if manifest is None:
            # No plugin.json / PLUGIN.md — ask user before auto-adapting
            print()
            try:
                answer = input(
                    "No plugin manifest found. "
                    "Would you like Falcon to auto-adapt this repository?\n"
                    "This uses AI to analyze the repo and generate a plugin manifest.\n"
                    "It may take a few minutes. [Y/n] "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"

            if answer in ("", "y", "yes"):
                from .autoadapter import autoadapt_if_needed
                from config import load_config
                adapted_ok = autoadapt_if_needed(plugin_dir, safe_name, load_config())
                if not adapted_ok:
                    print()
                    try:
                        keep = input(f"Auto-adaptation for '{safe_name}' failed. Keep partially adapted files for manual fixing? [y/N] ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        keep = "n"
                    
                    if keep not in ("y", "yes"):
                        # Clean up the cloned repo
                        def _force_remove(func, path, _exc_info):
                            os.chmod(path, stat.S_IWRITE)
                            func(path)
                        try:
                            shutil.rmtree(plugin_dir, onexc=_force_remove)
                        except Exception:
                            pass
                        return False, f"Auto-adaptation failed for '{safe_name}'. Plugin directory removed."
                    else:
                        return False, f"Auto-adaptation failed for '{safe_name}'. Files kept in {plugin_dir}. Set enabled=true in plugin.json manually if you fix it."
                manifest = PluginManifest.from_plugin_dir(plugin_dir)
            else:
                print("Skipping auto-adaptation.")

        if manifest is None:
            manifest = PluginManifest(name=safe_name, description="(no manifest)")
        
        if manifest.dependencies:
            deps_to_install.extend(manifest.dependencies)

        if not deps_to_install:
            # Fallback: Recursive requirements search
            req_files = list(plugin_dir.rglob("*requirements*.txt"))
            for rf in req_files:
                # Skip if in ignored dir
                if any(x in str(rf.parents) for x in [".git", "venv", "__pycache__"]):
                    continue
                try:
                    for line in rf.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("-r"):
                            deps_to_install.append(line)
                except Exception:
                    continue
            deps_to_install = list(dict.fromkeys(deps_to_install))

        if deps_to_install:
            print(f"Installing {len(deps_to_install)} dependencies for '{safe_name}'...")
            dep_ok, dep_msg = _install_dependencies(deps_to_install, cwd=plugin_dir)
            if dep_ok:
                print(f"Dependencies installed for '{safe_name}'.")
            else:
                return False, dep_msg

        # Persist to config
        entry = PluginEntry(
            name=safe_name,
            scope=scope,
            source=source,
            install_dir=plugin_dir,
            enabled=True,
            manifest=manifest,
        )
        _save_entry(entry)

        # Hot-reload tools into registry
        try:
            from .loader import register_plugin_tools
            register_plugin_tools(scope)
        except Exception:
            pass

        return True, f"Plugin '{safe_name}' installed successfully ({scope.value} scope)."

    except Exception as e:
        return False, f"Install failed: {e}"


def _is_git_url(source: str) -> bool:
    return (
        source.startswith("https://")
        or source.startswith("git@")
        or source.startswith("http://")
        or source.endswith(".git")
    )


def _clone_plugin(url: str, dest: Path) -> tuple[bool, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", url, str(dest)]
    # Use a hidden config check or just check sys.argv if needed, 
    # but store.py doesn't have easy access to 'config' in this function.
    # However, we can use the 'info' function if we import it.
    from common import info
    # We'll assume verbose intent if specifically triggered via /plugin
    info(f"    Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, f"git clone failed: {result.stderr.strip()}"
    return True, "cloned"


def _install_dependencies(deps: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    final_args = []
    for d in deps:
        d = d.strip()
        if d.startswith("-r"):
            # Aggressive split: remove -r, then strip the rest
            path_part = d[2:].strip()
            if path_part:
                final_args.extend(["-r", path_part])
        else:
            final_args.append(d)

    cmd = [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + final_args
    from common import info
    info(f"    Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        cwd=str(cwd) if cwd else None
    )
    if result.returncode != 0:
        return False, f"pip install failed: {result.stderr.strip()}"
    return True, "deps installed"


def _update_plugin_list_memory(scope: PluginScope) -> None:
    try:
        from datetime import datetime
        from memory.store import MemoryEntry, save_memory
        plugins = list_plugins(scope)
        names = [f"- {p.name}{' (disabled)' if not p.enabled else ''}: {p.manifest.description}" for p in plugins if p.manifest]
        content = "Currently installed plugins:\n" + "\n".join(names) if names else "No plugins currently installed."
        mem_scope = "project" if scope == PluginScope.PROJECT else "user"
        mem = MemoryEntry(
            name="installed_plugins_list",
            description="Dynamically updated list of all installed Falcon plugins and their status.",
            type=mem_scope,
            content=content,
            hall="facts",
            created=datetime.now().strftime("%Y-%m-%d"),
            scope=mem_scope,
            source="tool",
        )
        save_memory(mem, scope=mem_scope)
    except Exception:
        pass


def _save_entry(entry: PluginEntry) -> None:
    cfg_path = _plugin_cfg_for(entry.scope)
    data = _read_cfg(cfg_path)
    data.setdefault("plugins", {})[entry.name] = entry.to_dict()
    _write_cfg(cfg_path, data)
    _update_plugin_list_memory(entry.scope)


def _remove_entry(name: str, scope: PluginScope) -> None:
    cfg_path = _plugin_cfg_for(scope)
    data = _read_cfg(cfg_path)
    data.get("plugins", {}).pop(name, None)
    _write_cfg(cfg_path, data)
    _update_plugin_list_memory(scope)


# ── Uninstall ─────────────────────────────────────────────────────────────────

def uninstall_plugin(
    name: str,
    scope: PluginScope | None = None,
    keep_data: bool = False,
) -> tuple[bool, str]:
    entry = get_plugin(name, scope)
    if entry is None:
        return False, f"Plugin '{name}' not found."
    if not keep_data and entry.install_dir.exists():
        def _force_remove(func, path, _exc_info):
            """Handle read-only files (e.g. .git pack files on Windows)."""
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(entry.install_dir, onexc=_force_remove)
    _remove_entry(entry.name, entry.scope)
    return True, f"Plugin '{name}' uninstalled."


# ── Enable / Disable ──────────────────────────────────────────────────────────

def _set_enabled(name: str, scope: PluginScope | None, enabled: bool) -> tuple[bool, str]:
    entry = get_plugin(name, scope)
    if entry is None:
        return False, f"Plugin '{name}' not found."
    entry.enabled = enabled
    _save_entry(entry)
    state = "enabled" if enabled else "disabled"
    return True, f"Plugin '{name}' {state}."


def enable_plugin(name: str, scope: PluginScope | None = None) -> tuple[bool, str]:
    return _set_enabled(name, scope, True)


def disable_plugin(name: str, scope: PluginScope | None = None) -> tuple[bool, str]:
    return _set_enabled(name, scope, False)


def disable_all_plugins(scope: PluginScope | None = None) -> tuple[bool, str]:
    entries = list_plugins(scope)
    if not entries:
        return True, "No plugins to disable."
    for entry in entries:
        entry.enabled = False
        _save_entry(entry)
    return True, f"Disabled {len(entries)} plugin(s)."


# ── Update ────────────────────────────────────────────────────────────────────

def update_plugin(name: str, scope: PluginScope | None = None) -> tuple[bool, str]:
    entry = get_plugin(name, scope)
    if entry is None:
        return False, f"Plugin '{name}' not found."
    if not _is_git_url(entry.source):
        return False, f"Plugin '{name}' was installed from a local path; cannot auto-update."
    if not entry.install_dir.exists():
        return False, f"Install directory missing: {entry.install_dir}"
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=str(entry.install_dir),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, f"git pull failed: {result.stderr.strip()}"
    # Re-install dependencies if manifest changed
    manifest = PluginManifest.from_plugin_dir(entry.install_dir)
    if manifest and manifest.dependencies:
        _install_dependencies(manifest.dependencies)
        # Hot-reload tools
        try:
            from .loader import register_plugin_tools
            register_plugin_tools(entry.scope)
        except Exception:
            pass

    return True, f"Plugin '{name}' updated. {result.stdout.strip()}"
