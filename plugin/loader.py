"""Plugin loader: discover and load tools/skills/mcp from installed plugins."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def scrub_any_type(obj: Any) -> Any:
    """Recursively remove 'type': 'any' from schema dictionaries as it's not valid JSON Schema."""
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k == "type" and v == "any":
                continue
            new_obj[k] = scrub_any_type(v)
        return new_obj
    elif isinstance(obj, list):
        return [scrub_any_type(item) for item in obj]
    return obj

from .store import list_plugins
from .types import PluginEntry, PluginScope


def _active_profile_name() -> str:
    """Name of the active profile ('default' when none / on error)."""
    try:
        from profiles import active_profile
        return active_profile()
    except Exception:
        return "default"


def _origin_key(entry: PluginEntry) -> str:
    """Stable tag identifying WHERE a plugin's tools came from.

    Keyed on the resolved install directory rather than the plugin name, because
    the same name can legitimately exist in several places at once (the core
    base and one or more profiles). Two plugins sharing a name but living in
    different directories are different code and must not be conflated.
    """
    try:
        install = str(entry.install_dir.resolve()).lower()
    except Exception:
        install = str(entry.install_dir).lower()
    return f"plugin::{entry.scope.value}::{install}"


def load_all_plugins(scope: PluginScope | None = None) -> list[PluginEntry]:
    """Return enabled plugins (optionally filtered by scope)."""
    return [p for p in list_plugins(scope) if p.enabled]


def load_plugin_tools(scope: PluginScope | None = None) -> list[dict]:
    """
    Import tool modules from all enabled plugins and collect their TOOL_SCHEMAS.
    Returns combined list of tool schema dicts.
    """
    schemas: list[dict] = []
    for entry in load_all_plugins(scope):
        if not entry.manifest or not entry.manifest.tools:
            continue
        for module_name in entry.manifest.tools:
            mod = _import_plugin_module(entry, module_name)
            if mod and hasattr(mod, "TOOL_SCHEMAS"):
                schemas.extend(mod.TOOL_SCHEMAS)
    return schemas


def reload_plugins(scope: PluginScope | None = None) -> dict:
    """
    Reload all plugins and register their tools.
    Returns a dict with counts of what was reloaded.
    """
    # Clear any cached plugin modules to force re-import. Keys are namespaced by
    # scope + install-dir digest (see `_module_key`), so this still matches them
    # all while never touching unrelated modules.
    import sys
    modules_to_remove = [k for k in list(sys.modules) if k.startswith("_plugin_")]
    for mod_name in modules_to_remove:
        del sys.modules[mod_name]

    # Re-register tools (prunes tools whose plugin is no longer eligible)
    tool_count = register_plugin_tools(scope)

    return {
        "tools_registered": tool_count,
        "modules_cleared": len(modules_to_remove),
    }


def register_plugin_tools(scope: PluginScope | None = None, *, prune: bool = True) -> int:
    """
    Import tool modules from enabled plugins and register them into tool_registry.
    Returns number of tools registered.

    Atomic swap: the tools of every currently-eligible plugin are registered
    FIRST, and only afterwards are the tools of plugins that are no longer
    eligible retired. There is never a moment with an empty tool surface, and a
    profile switch can no longer leave the previous profile's tools behind.

    `prune=False` keeps the additive behaviour, for callers that intentionally
    register a single extra scope on top of what is already loaded.
    """
    from tool_registry import register_tool, unregister_origins_except

    count = 0
    live_origins: set[str] = set()
    for entry in load_all_plugins(scope):
        origin = _origin_key(entry)
        live_origins.add(origin)
        if not entry.manifest or not entry.manifest.tools:
            continue
        for module_name in entry.manifest.tools:
            mod = _import_plugin_module(entry, module_name)
            if mod is None:
                continue
            # Register each ToolDef exported by the module
            if hasattr(mod, "TOOL_DEFS"):
                for tdef in mod.TOOL_DEFS:
                    # Normalize schema: ensure input_schema and parameters are synced
                    if hasattr(tdef, "schema") and isinstance(tdef.schema, dict):
                        sch = tdef.schema
                        if "input_schema" not in sch and "parameters" in sch:
                            sch["input_schema"] = sch["parameters"]
                        elif "parameters" not in sch and "input_schema" in sch:
                            sch["parameters"] = sch["input_schema"]

                        # Scrub invalid 'any' types
                        tdef.schema = scrub_any_type(sch)

                    register_tool(tdef, origin=origin)
                    count += 1

    if prune:
        if scope is not None:
            # Scoped call: only retire origins belonging to that same scope, so
            # registering one scope never wipes the other's tools.
            prefix = f"plugin::{scope.value}::"
            try:
                from tool_registry import _registry_origin  # type: ignore
                keep = {
                    o for o in set(_registry_origin.values())
                    if o in live_origins or not o.startswith(prefix)
                }
            except Exception:
                keep = live_origins
        else:
            keep = live_origins
        unregister_origins_except(keep)

    return count


def load_plugin_skills(scope: PluginScope | None = None) -> list[Path]:
    """Return paths to skill markdown files from enabled plugins."""
    paths: list[Path] = []
    for entry in load_all_plugins(scope):
        if not entry.manifest or not entry.manifest.skills:
            continue
        for skill_rel in entry.manifest.skills:
            skill_path = entry.install_dir / skill_rel
            if skill_path.exists():
                paths.append(skill_path)
    return paths


def load_plugin_mcp_configs(scope: PluginScope | None = None) -> dict:
    """Return mcp server configs contributed by enabled plugins."""
    configs: dict = {}
    for entry in load_all_plugins(scope):
        if not entry.manifest or not entry.manifest.mcp_servers:
            continue
        for server_name, server_cfg in entry.manifest.mcp_servers.items():
            # Prefix server name with plugin name to avoid collisions
            qualified = f"{entry.name}__{server_name}"
            configs[qualified] = server_cfg
    return configs


def _module_key(entry: PluginEntry, module_name: str) -> str:
    """Collision-free sys.modules key for a plugin module.

    The key MUST encode the install directory. Keying only on the plugin name
    meant that a plugin present in both the core base and a profile resolved to
    whichever copy was imported first — permanently, for the whole process —
    so one profile silently executed another profile's code.
    """
    import hashlib
    try:
        install = str(entry.install_dir.resolve()).lower()
    except Exception:
        install = str(entry.install_dir).lower()
    digest = hashlib.sha256(install.encode("utf-8", "replace")).hexdigest()[:10]
    return f"_plugin_{entry.scope.value}_{digest}_{entry.name}_{module_name}"


def _import_plugin_module(entry: PluginEntry, module_name: str):
    """Dynamically import a module from a plugin directory."""
    unique_name = _module_key(entry, module_name)
    if unique_name in sys.modules:
        return sys.modules[unique_name]

    # Try as a file
    candidates = [
        entry.install_dir / f"{module_name}.py",
        entry.install_dir / module_name / "__init__.py",
    ]
    plugin_dir_str = str(entry.install_dir)
    for candidate in candidates:
        if candidate.exists():
            spec = importlib.util.spec_from_file_location(unique_name, candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[unique_name] = mod
                # Expose the plugin dir on sys.path ONLY while its module body
                # executes, so a sibling `import helpers` still resolves, but the
                # entry does not linger and shadow another plugin's modules for
                # the rest of the process.
                _added = plugin_dir_str not in sys.path
                if _added:
                    sys.path.insert(0, plugin_dir_str)
                try:
                    spec.loader.exec_module(mod)
                    return mod
                except Exception as e:
                    print(f"[plugin] Failed to load {module_name} from {entry.name}: {e}")
                    del sys.modules[unique_name]
                finally:
                    if _added:
                        try:
                            sys.path.remove(plugin_dir_str)
                        except ValueError:
                            pass
    return None
