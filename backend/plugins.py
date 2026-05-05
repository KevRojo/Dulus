"""Hot-loadable plugin system for Dulus."""
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
PLUGINS_DIR.mkdir(exist_ok=True)

_hooks: dict[str, list[Callable]] = {}
_registry: dict[str, dict[str, Any]] = {}
_snapshots: dict[str, float] = {}
_watcher_thread: threading.Thread | None = None
_watcher_stop = threading.Event()
_watch_interval = 2.0


def register_hook(name: str, fn: Callable):
    _hooks.setdefault(name, []).append(fn)


def unregister_plugin_hooks(name: str):
    """Remove all hooks registered by a given plugin name."""
    mod_name = f"dulus.plugins.{name}"
    for hook_name, fns in list(_hooks.items()):
        _hooks[hook_name] = [fn for fn in fns if getattr(fn, "__module__", None) != mod_name]
        if not _hooks[hook_name]:
            del _hooks[hook_name]


def trigger_hook(name: str, *args, **kwargs) -> list[Any]:
    results = []
    for fn in _hooks.get(name, []):
        try:
            results.append(fn(*args, **kwargs))
        except Exception as e:
            results.append({"error": str(e), "plugin": getattr(fn, "__module__", "unknown")})
    return results


def discover_plugins() -> list[Path]:
    return sorted(PLUGINS_DIR.glob("*.py"))


def load_plugin(path: Path) -> dict[str, Any]:
    name = path.stem
    # If already loaded, unload first for clean hot-reload
    if name in _registry:
        unload_plugin(name)

    # Invalidate bytecode cache so edits are picked up immediately
    cache_file = importlib.util.cache_from_source(str(path))
    try:
        Path(cache_file).unlink(missing_ok=True)
    except Exception:
        pass

    spec = importlib.util.spec_from_file_location(f"dulus.plugins.{name}", path)
    if not spec or not spec.loader:
        return {"name": name, "status": "error", "error": "Cannot load spec"}
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        return {"name": name, "status": "error", "error": str(e)}

    meta = getattr(mod, "__plugin_meta__", {"name": name, "version": "0.0.1"})
    meta["status"] = "loaded"
    meta["module"] = mod
    _registry[name] = meta

    # Auto-register hooks if plugin exposes them
    hooks = getattr(mod, "__hooks__", {})
    for hook_name, fn in hooks.items():
        register_hook(hook_name, fn)

    return meta


def unload_plugin(name: str) -> bool:
    """Unload a plugin by name, removing hooks and registry entry."""
    if name not in _registry:
        return False
    unregister_plugin_hooks(name)
    mod_name = f"dulus.plugins.{name}"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    del _registry[name]
    return True


def reload_plugin(path: Path) -> dict[str, Any]:
    return load_plugin(path)


def load_all_plugins() -> list[dict[str, Any]]:
    return [load_plugin(p) for p in discover_plugins()]


def get_plugin_info() -> list[dict[str, Any]]:
    """Return serializable plugin metadata (no module objects)."""
    return [
        {"name": k, "version": v.get("version", "?"), "status": v["status"]}
        for k, v in _registry.items()
    ]


def get_plugin_registry() -> dict[str, dict[str, Any]]:
    """Return raw registry (includes module objects; not JSON-safe)."""
    return _registry


# ── Hot-Reload Watcher ──

def _take_snapshot() -> dict[str, float]:
    snaps = {}
    for p in discover_plugins():
        try:
            snaps[p.stem] = p.stat().st_mtime
        except OSError:
            pass
    return snaps


def _scan_changes() -> tuple[list[str], list[str], list[str]]:
    """Return (added, modified, removed) plugin names."""
    global _snapshots
    current = _take_snapshot()
    added = [name for name in current if name not in _snapshots]
    modified = [name for name in current if name in _snapshots and current[name] != _snapshots[name]]
    removed = [name for name in _snapshots if name not in current]
    _snapshots = current
    return added, modified, removed


def _watcher_loop(broadcast_fn: Callable | None = None):
    """Daemon thread loop: poll plugins/ dir for changes."""
    global _snapshots
    _snapshots = _take_snapshot()
    while not _watcher_stop.is_set():
        time.sleep(_watch_interval)
        added, modified, removed = _scan_changes()
        changes: list[dict] = []
        for name in added:
            path = PLUGINS_DIR / f"{name}.py"
            result = load_plugin(path)
            changes.append({"event": "added", "name": name, "status": result["status"]})
        for name in modified:
            path = PLUGINS_DIR / f"{name}.py"
            result = load_plugin(path)
            changes.append({"event": "modified", "name": name, "status": result["status"]})
        for name in removed:
            unload_plugin(name)
            changes.append({"event": "removed", "name": name, "status": "unloaded"})
        if changes and broadcast_fn:
            try:
                broadcast_fn("plugin_change", {"changes": changes})
            except Exception:
                pass


def start_watcher(broadcast_fn: Callable | None = None) -> bool:
    """Start the plugins directory watcher. Returns False if already running."""
    global _watcher_thread, _watcher_stop
    if _watcher_thread is not None and _watcher_thread.is_alive():
        return False
    _watcher_stop.clear()
    _snapshots = _take_snapshot()
    _watcher_thread = threading.Thread(
        target=_watcher_loop,
        args=(broadcast_fn,),
        daemon=True,
        name="plugin-watcher"
    )
    _watcher_thread.start()
    return True


def stop_watcher() -> bool:
    """Stop the plugins directory watcher."""
    global _watcher_thread
    if _watcher_thread is None or not _watcher_thread.is_alive():
        return False
    _watcher_stop.set()
    _watcher_thread.join(timeout=5)
    _watcher_thread = None
    return True


def watcher_status() -> dict[str, Any]:
    return {
        "running": _watcher_thread is not None and _watcher_thread.is_alive(),
        "interval": _watch_interval,
        "plugins_tracked": len(_snapshots),
    }


# Example plugin template
def create_example_plugin():
    example = PLUGINS_DIR / "example.py"
    if example.exists():
        return
    example.write_text('''"""Example Dulus Plugin."""
__plugin_meta__ = {
    "name": "example",
    "version": "1.0.0",
    "description": "Counts tasks by status",
    "author": "Dulus"
}

def count_by_status(tasks):
    from collections import Counter
    return dict(Counter(t["status"] for t in tasks))

__hooks__ = {
    "task_stats": count_by_status
}
''', encoding="utf-8")
