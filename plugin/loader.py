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
    # Clear any cached plugin modules to force re-import
    import sys
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith("_plugin_")]
    for mod_name in modules_to_remove:
        del sys.modules[mod_name]
    
    # Re-register tools
    tool_count = register_plugin_tools(scope)
    
    return {
        "tools_registered": tool_count,
        "modules_cleared": len(modules_to_remove),
    }


def register_plugin_tools(scope: PluginScope | None = None) -> int:
    """
    Import tool modules from enabled plugins and register them into tool_registry.
    Returns number of tools registered.
    """
    from tool_registry import register_tool, ToolDef
    count = 0
    for entry in load_all_plugins(scope):
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
                    
                    register_tool(tdef)
                    count += 1
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


def _import_plugin_module(entry: PluginEntry, module_name: str):
    """Dynamically import a module from a plugin directory."""
    # Ensure plugin dir is on sys.path
    plugin_dir_str = str(entry.install_dir)
    if plugin_dir_str not in sys.path:
        sys.path.insert(0, plugin_dir_str)

    # Build a unique module name to avoid collisions
    unique_name = f"_plugin_{entry.name}_{module_name}"
    if unique_name in sys.modules:
        return sys.modules[unique_name]

    # Try as a file
    candidates = [
        entry.install_dir / f"{module_name}.py",
        entry.install_dir / module_name / "__init__.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            spec = importlib.util.spec_from_file_location(unique_name, candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[unique_name] = mod
                try:
                    spec.loader.exec_module(mod)
                    return mod
                except Exception as e:
                    print(f"[plugin] Failed to load {module_name} from {entry.name}: {e}")
                    del sys.modules[unique_name]
    return None
