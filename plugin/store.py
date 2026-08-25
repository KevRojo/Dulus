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

USER_PLUGIN_DIR  = Path.home() / ".dulus" / "plugins"
USER_PLUGIN_CFG  = Path.home() / ".dulus" / "plugins.json"

def _project_plugin_dir() -> Path:
    return Path.cwd() / ".dulus-context" / "plugins"

def _project_plugin_cfg() -> Path:
    return Path.cwd() / ".dulus-context" / "plugins.json"


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


# ── Profile-aware USER scope ──────────────────────────────────────────────────
# `profiles.py` already gives every named profile its own plugins/ directory and
# plugins.json, but this module ignored them: every install landed in the shared
# base and every profile listed the same plugins. A profile is supposed to be a
# separate agent, so USER-scope reads and writes follow the active profile. The
# 'default' profile IS the base, so these collapse to the previous behaviour.

def _profiles_root() -> Path | None:
    try:
        from profiles import PROFILES_DIR
        return Path(PROFILES_DIR)
    except Exception:
        return None


def _rmtree_force(path: Path) -> None:
    """rmtree that survives read-only files (git pack files on Windows)."""
    def _on_error(func, p, _exc_info):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    try:
        try:
            shutil.rmtree(path, onexc=_on_error)  # type: ignore[call-arg]
        except TypeError:
            shutil.rmtree(path, onerror=_on_error)  # type: ignore[call-arg,arg-type]
    except Exception:
        pass


def _active_user_dir() -> Path:
    try:
        from profiles import profile_plugins_dir
        d = profile_plugins_dir()
        if d:
            d.mkdir(parents=True, exist_ok=True)
            return d
    except Exception:
        pass
    return USER_PLUGIN_DIR


def _active_user_cfg() -> Path:
    try:
        from profiles import profile_plugins_cfg
        c = profile_plugins_cfg()
        if c:
            return c
    except Exception:
        pass
    return USER_PLUGIN_CFG


# Plugins a NAMED profile inherits from the base. A fresh install has none, so
# the baseline is best-effort: whatever of these names is actually installed is
# carried over, and nothing is promised that is not there.
# Override via config `profile_baseline_plugins: [...]`.
_PROFILE_BASELINE_PLUGINS: set[str] = {"mempalace"}


def _baseline_plugin_names() -> set[str]:
    try:
        from config import load_config
        extra = load_config().get("profile_baseline_plugins")
        if isinstance(extra, list):
            return {str(x) for x in extra}
    except Exception:
        pass
    return set(_PROFILE_BASELINE_PLUGINS)


def installed_baseline_plugin_names() -> set[str]:
    """Baseline names that are ACTUALLY present in the base config.

    Used by the prompt builder so the agent is told what it really inherits
    instead of a hard-coded list that may not exist on this machine.
    """
    try:
        base = set(_read_cfg(USER_PLUGIN_CFG).get("plugins", {}))
    except Exception:
        base = set()
    return _baseline_plugin_names() & base


def _plugin_dir_for(scope: PluginScope) -> Path:
    return _active_user_dir() if scope == PluginScope.USER else _project_plugin_dir()


def _plugin_cfg_for(scope: PluginScope) -> Path:
    return _active_user_cfg() if scope == PluginScope.USER else _project_plugin_cfg()


# ── Ownership ─────────────────────────────────────────────────────────────────
# A named profile can SEE plugins it does not OWN (they are inherited from the
# base). Mutating one of those must not be routed through the active profile:
# uninstalling would delete the shared install directory for every profile, and
# enable/disable would write a phantom entry — pointing at the base's
# install_dir — into the profile's own plugins.json.

def _cfg_for_install_dir(install_dir: Path | str | None) -> Path | None:
    """Map an install DIRECTORY back to the plugins.json that owns it.

    The directory is the ground truth of ownership: a plugin's files live either
    in the core base (~/.dulus/plugins/<name>) or inside exactly ONE profile
    (~/.dulus/profiles/<p>/plugins/<name>). Deriving ownership from the path
    means a config write can never land in the wrong file — not on a fresh
    install (where no config lists the plugin yet, so a name lookup would fall
    through to the core) and not when repairing an entry that was already
    mis-filed. Returns None when the directory is outside both trees.
    """
    if not install_dir:
        return None
    try:
        p = Path(install_dir).resolve()
    except Exception:
        return None

    proot = _profiles_root()
    if proot is not None:
        try:
            rel = p.relative_to(proot.resolve())
            parts = rel.parts
            # <profile>/plugins/<plugin_name>[/...]
            if len(parts) >= 2 and parts[1] == "plugins":
                return proot / parts[0] / "plugins.json"
        except Exception:
            pass

    try:
        p.relative_to(USER_PLUGIN_DIR.resolve())
        return USER_PLUGIN_CFG
    except Exception:
        return None


def _all_user_cfgs() -> list[Path]:
    """Every USER-scope plugins.json on this machine: core + each profile."""
    cfgs = [USER_PLUGIN_CFG]
    proot = _profiles_root()
    if proot is not None and proot.is_dir():
        try:
            for d in proot.iterdir():
                if d.is_dir():
                    cfgs.append(d / "plugins.json")
        except Exception:
            pass
    return cfgs


def purge_misfiled_entries(name: str | None = None) -> int:
    """Drop config entries whose install_dir belongs to a DIFFERENT plugins.json.

    Self-healing for machines that already ran the buggy name-based ownership
    lookup: an install performed under a profile could register itself in the
    core config while its files lived in the profile, leaking the plugin into
    every profile and hiding it from the one that owns it. Returns the number
    of entries removed.
    """
    removed = 0
    for cfg in _all_user_cfgs():
        if not cfg.exists():
            continue
        data = _read_cfg(cfg)
        plugins = data.get("plugins", {})
        if not plugins:
            continue
        drop = [
            n for n, d in plugins.items()
            if (name is None or n == name)
            and (owner := _cfg_for_install_dir(d.get("install_dir"))) is not None
            and owner != cfg
        ]
        if drop:
            for n in drop:
                plugins.pop(n, None)
            data["plugins"] = plugins
            _write_cfg(cfg, data)
            removed += len(drop)
    return removed


def _owning_cfg(entry: PluginEntry) -> Path:
    """The plugins.json that actually declares `entry`.

    Resolved from the install PATH first. A name lookup cannot answer this
    correctly while a plugin is being installed for the first time (no config
    lists it yet, so the lookup falls through to the core and the entry gets
    written to the wrong file even though the files went into the profile).
    The path is unambiguous, so it wins; the name lookup stays as a fallback
    for entries whose directory sits outside both trees.
    """
    if entry.scope == PluginScope.PROJECT:
        return _project_plugin_cfg()
    by_path = _cfg_for_install_dir(getattr(entry, "install_dir", None))
    if by_path is not None:
        return by_path
    active = _active_user_cfg()
    if entry.name in _read_cfg(active).get("plugins", {}):
        return active
    return USER_PLUGIN_CFG


def _is_inherited(entry: PluginEntry) -> bool:
    """True if `entry` is visible only by inheritance from the base."""
    if entry.scope != PluginScope.USER:
        return False
    return _owning_cfg(entry) != _active_user_cfg()


# ── List ──────────────────────────────────────────────────────────────────────

def list_plugins(scope: PluginScope | None = None) -> list[PluginEntry]:
    """Return all installed plugins (optionally filtered by scope).

    A named profile is a LEAN agent: it yields its OWN plugins plus only the
    baseline ones from the base. A fresh install ships with no plugins, so
    inheriting the user's whole accumulated pile into every profile would defeat
    the purpose. Set `inherit_core` on the profile for full inheritance. The
    'default' profile is unchanged (it IS the base).
    """
    def _mk(data: dict) -> PluginEntry:
        e = PluginEntry.from_dict(data)
        e.manifest = PluginManifest.from_plugin_dir(e.install_dir)
        return e

    def _belongs_to(data: dict, cfg: Path) -> bool:
        """Reject registrations whose files live under a DIFFERENT config's tree.

        A mis-filed entry (e.g. the core's plugins.json pointing at
        profiles/<p>/plugins/<name>) would otherwise be advertised to every
        profile, and its tools loaded from a directory the active profile does
        not own. Entries outside both trees (bare local paths) are kept.
        """
        owner = _cfg_for_install_dir(data.get("install_dir"))
        return owner is None or owner == cfg

    entries: list[PluginEntry] = []
    seen: set[str] = set()
    scopes = [PluginScope.USER, PluginScope.PROJECT] if scope is None else [scope]
    for sc in scopes:
        primary = _plugin_cfg_for(sc)
        for name, data in _read_cfg(primary).get("plugins", {}).items():
            if name in seen:
                continue
            if sc == PluginScope.USER and not _belongs_to(data, primary):
                continue
            entries.append(_mk(data))
            seen.add(name)
        # A named profile inherits from the base: EITHER the full pile
        # (inherit_core=true) OR just the baseline (lean, the default).
        if sc == PluginScope.USER and primary != USER_PLUGIN_CFG:
            full = False
            try:
                from profiles import inherits_core
                full = inherits_core()
            except Exception:
                pass
            baseline = None if full else _baseline_plugin_names()
            for name, data in _read_cfg(USER_PLUGIN_CFG).get("plugins", {}).items():
                if name in seen:
                    continue
                if baseline is not None and name not in baseline:
                    continue
                if not _belongs_to(data, USER_PLUGIN_CFG):
                    continue
                entries.append(_mk(data))
                seen.add(name)
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

    # Heal configs left inconsistent by an earlier install before deciding
    # whether this name is taken — a mis-filed entry would otherwise report the
    # plugin as "already installed" from a config that does not own its files,
    # blocking a legitimate install in the active profile.
    try:
        purge_misfiled_entries(safe_name)
    except Exception:
        pass

    # Check if already installed. An INHERITED plugin of the same name does not
    # block the install: a profile is entitled to its own copy, which then
    # shadows the base's (list_plugins dedups with the profile winning).
    existing = get_plugin(safe_name, scope)
    if existing and _is_inherited(existing):
        existing = None
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
            _rmtree_force(plugin_dir)
        elif plugin_dir.exists():
            # No config entry claims this name (checked above) yet the files are
            # here: a leftover from an install that was interrupted, or one whose
            # registration was written into a different profile's plugins.json.
            # Clearing it is safe precisely because nothing owns it, and leaving
            # it makes the install unrecoverable — git clone refuses a non-empty
            # destination and the user gets a dead-end error on every retry.
            _rmtree_force(plugin_dir)

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
                    "Would you like Dulus to auto-adapt this repository?\n"
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
                            shutil.rmtree(plugin_dir, onexc=_force_remove)  # type: ignore[call-arg]
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

    from common import pip_install_cmd
    cmd = pip_install_cmd("--quiet", *final_args)
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
            description="Dynamically updated list of all installed Dulus plugins and their status.",
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


def _save_entry(entry: PluginEntry, cfg_path: Path | None = None) -> None:
    # Default to the config that OWNS the entry, not the active one, so updating
    # an inherited plugin never forks a phantom copy into the active profile.
    cfg_path = cfg_path or _owning_cfg(entry)
    data = _read_cfg(cfg_path)
    data.setdefault("plugins", {})[entry.name] = entry.to_dict()
    _write_cfg(cfg_path, data)
    _update_plugin_list_memory(entry.scope)


def _remove_entry(name: str, scope: PluginScope, cfg_path: Path | None = None) -> None:
    cfg_path = cfg_path or _plugin_cfg_for(scope)
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

    # Refuse to delete shared files from inside a profile that merely inherits
    # the plugin: the install directory belongs to the base and removing it
    # would silently uninstall the plugin for every other profile too.
    if _is_inherited(entry):
        return False, (
            f"'{name}' is inherited from the base, not owned by the active profile. "
            f"Switch to the default profile to uninstall it (/profile switch default)."
        )

    owning_cfg = _owning_cfg(entry)
    if not keep_data and entry.install_dir.exists():
        def _force_remove(func, path, _exc_info):
            """Handle read-only files (e.g. .git pack files on Windows)."""
            os.chmod(path, stat.S_IWRITE)
            func(path)
        if sys.version_info >= (3, 12):
            shutil.rmtree(entry.install_dir, onexc=_force_remove)
        else:
            shutil.rmtree(entry.install_dir, onerror=_force_remove)
    _remove_entry(entry.name, entry.scope, owning_cfg)
    # Drop the tools this plugin contributed instead of leaving them callable
    # against a directory that no longer exists.
    try:
        from tool_registry import unregister_origin
        from .loader import _origin_key
        unregister_origin(_origin_key(entry))
    except Exception:
        pass
    return True, f"Plugin '{name}' uninstalled."


# ── Enable / Disable ──────────────────────────────────────────────────────────

def _set_enabled(name: str, scope: PluginScope | None, enabled: bool) -> tuple[bool, str]:
    entry = get_plugin(name, scope)
    if entry is None:
        return False, f"Plugin '{name}' not found."
    inherited = _is_inherited(entry)
    entry.enabled = enabled
    # Writes to the OWNING config. Toggling an inherited plugin used to copy a
    # phantom entry into the active profile's plugins.json, pointing at the
    # base's install directory — after which the profile "owned" a plugin that
    # was never installed into it.
    _save_entry(entry, _owning_cfg(entry))
    state = "enabled" if enabled else "disabled"
    suffix = " (applies to the base: this plugin is inherited)" if inherited else ""
    return True, f"Plugin '{name}' {state}.{suffix}"


def enable_plugin(name: str, scope: PluginScope | None = None) -> tuple[bool, str]:
    return _set_enabled(name, scope, True)


def disable_plugin(name: str, scope: PluginScope | None = None) -> tuple[bool, str]:
    return _set_enabled(name, scope, False)


def disable_all_plugins(scope: PluginScope | None = None) -> tuple[bool, str]:
    entries = list_plugins(scope)
    if not entries:
        return True, "No plugins to disable."
    # Only plugins the active context OWNS. Disabling inherited ones from within
    # a profile would turn them off for the base and every other profile.
    owned = [e for e in entries if not _is_inherited(e)]
    if not owned:
        return True, "No plugins owned by the active profile to disable."
    for entry in owned:
        entry.enabled = False
        _save_entry(entry, _owning_cfg(entry))
    skipped = len(entries) - len(owned)
    note = f" ({skipped} inherited plugin(s) left untouched)" if skipped else ""
    return True, f"Disabled {len(owned)} plugin(s).{note}"


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
