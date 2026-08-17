"""Isolation guarantees between profiles, workspaces, plugins and skills.

Each test pins one concrete leak that used to be possible:

* tools of a profile surviving a switch to another profile,
* two same-named plugins resolving to a single cached module,
* project-scoped plugins never being loaded because the cwd moved after import,
* a profile deleting or toggling a plugin it only inherited,
* every profile writing into one shared memory directory,
* a lean profile searching the base skills directory.
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import profiles as P  # noqa: E402
import tool_registry  # noqa: E402
from plugin import store as pstore  # noqa: E402
from plugin import loader as ploader  # noqa: E402
from plugin.types import PluginEntry, PluginScope  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def dulus_home(tmp_path, monkeypatch):
    """An isolated ~/.dulus with profiles, plugins and memory."""
    home = tmp_path / ".dulus"
    (home / "plugins").mkdir(parents=True)
    (home / "memory").mkdir(parents=True)
    (home / "skills").mkdir(parents=True)
    (home / "plugins.json").write_text(json.dumps({"plugins": {}}), encoding="utf-8")

    monkeypatch.setattr(P, "DULUS_HOME", home)
    monkeypatch.setattr(P, "PROFILES_DIR", home / "profiles")
    monkeypatch.setattr(P, "ACTIVE_FILE", home / "active_profile.json")
    monkeypatch.setattr(pstore, "USER_PLUGIN_DIR", home / "plugins")
    monkeypatch.setattr(pstore, "USER_PLUGIN_CFG", home / "plugins.json")

    with _empty_registry():
        yield home


@contextmanager
def _empty_registry():
    """Run with an empty tool registry, then put the real one back.

    The registry is module-level state populated when `tools` is imported, and
    nothing re-populates it afterwards, so clearing it without restoring would
    strip the core tools from every test that runs later in the session.
    """
    saved = dict(tool_registry._registry)
    saved_origin = dict(tool_registry._registry_origin)
    tool_registry._registry.clear()
    tool_registry._registry_origin.clear()
    try:
        yield
    finally:
        tool_registry._registry.clear()
        tool_registry._registry.update(saved)
        tool_registry._registry_origin.clear()
        tool_registry._registry_origin.update(saved_origin)


def _write_plugin(root: Path, name: str, tool_name: str, marker: str) -> Path:
    """Create a minimal plugin exporting exactly one tool."""
    pdir = root / name
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "plugin.json").write_text(json.dumps({
        "name": name,
        "version": "1.0.0",
        "description": f"test plugin {name}",
        "tools": ["plugin_tool"],
    }), encoding="utf-8")
    (pdir / "plugin_tool.py").write_text(
        "from tool_registry import ToolDef\n"
        f"MARKER = {marker!r}\n"
        "TOOL_DEFS = [ToolDef(\n"
        f"    name={tool_name!r},\n"
        f"    schema={{'name': {tool_name!r}, 'description': 'x',\n"
        "             'input_schema': {'type': 'object', 'properties': {}}},\n"
        f"    func=lambda params, config: {marker!r},\n"
        ")]\n",
        encoding="utf-8",
    )
    return pdir


def _register(cfg: Path, name: str, install_dir: Path, scope: str = "user") -> None:
    data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {"plugins": {}}
    data.setdefault("plugins", {})[name] = {
        "name": name,
        "scope": scope,
        "source": str(install_dir),
        "install_dir": str(install_dir),
        "enabled": True,
    }
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Registry provenance ─────────────────────────────────────────────────────

def test_registry_can_retire_tools_by_origin():
  with _empty_registry():
    tdef = tool_registry.ToolDef(name="T", schema={"name": "T"}, func=lambda p, c: "")
    tool_registry.register_tool(tdef, origin="A")
    assert tool_registry.get_tool("T") is not None
    assert tool_registry.unregister_origin("A") == 1
    assert tool_registry.get_tool("T") is None


def test_core_tools_are_never_retired():
  with _empty_registry():
    core = tool_registry.ToolDef(name="Core", schema={"name": "Core"}, func=lambda p, c: "")
    plug = tool_registry.ToolDef(name="Plug", schema={"name": "Plug"}, func=lambda p, c: "")
    tool_registry.register_tool(core)                 # no origin → core
    tool_registry.register_tool(plug, origin="p1")
    tool_registry.unregister_origins_except(set())
    assert tool_registry.get_tool("Core") is not None
    assert tool_registry.get_tool("Plug") is None


# ── BUG 1: tools surviving a profile switch ─────────────────────────────────

def test_switching_profile_retires_the_previous_profiles_tools(dulus_home, monkeypatch):
    P.create_profile("alpha")
    P.create_profile("beta")
    _write_plugin(P.PROFILES_DIR / "alpha" / "plugins", "alpha_p", "AlphaTool", "alpha")
    _write_plugin(P.PROFILES_DIR / "beta" / "plugins", "beta_p", "BetaTool", "beta")
    _register(P.PROFILES_DIR / "alpha" / "plugins.json", "alpha_p",
              P.PROFILES_DIR / "alpha" / "plugins" / "alpha_p")
    _register(P.PROFILES_DIR / "beta" / "plugins.json", "beta_p",
              P.PROFILES_DIR / "beta" / "plugins" / "beta_p")

    P.switch_profile("alpha")
    ploader.reload_plugins()
    assert tool_registry.get_tool("AlphaTool") is not None

    P.switch_profile("beta")
    ploader.reload_plugins()
    assert tool_registry.get_tool("BetaTool") is not None
    assert tool_registry.get_tool("AlphaTool") is None, \
        "alpha's tool survived the switch into beta"


# ── BUG 2: same name, different code ────────────────────────────────────────

def test_same_named_plugins_do_not_share_a_module(dulus_home):
    core = _write_plugin(dulus_home / "plugins", "dup", "DupTool", "from-core")
    P.create_profile("gamma")
    prof = _write_plugin(P.PROFILES_DIR / "gamma" / "plugins", "dup", "DupTool", "from-profile")

    e_core = PluginEntry(name="dup", scope=PluginScope.USER, source="", install_dir=core)
    e_prof = PluginEntry(name="dup", scope=PluginScope.USER, source="", install_dir=prof)

    assert ploader._module_key(e_core, "plugin_tool") != ploader._module_key(e_prof, "plugin_tool")

    m1 = ploader._import_plugin_module(e_core, "plugin_tool")
    m2 = ploader._import_plugin_module(e_prof, "plugin_tool")
    assert m1.MARKER == "from-core"
    assert m2.MARKER == "from-profile", "the profile executed the core's copy"


def test_origin_key_distinguishes_install_dirs(dulus_home):
    a = PluginEntry(name="x", scope=PluginScope.USER, source="", install_dir=dulus_home / "plugins" / "x")
    b = PluginEntry(name="x", scope=PluginScope.USER, source="", install_dir=dulus_home / "other" / "x")
    assert ploader._origin_key(a) != ploader._origin_key(b)


def test_import_does_not_leak_into_sys_path(dulus_home):
    pdir = _write_plugin(dulus_home / "plugins", "pathy", "PathyTool", "pathy")
    before = list(sys.path)
    entry = PluginEntry(name="pathy", scope=PluginScope.USER, source="", install_dir=pdir)
    ploader._import_plugin_module(entry, "plugin_tool")
    assert str(pdir) not in sys.path, "plugin dir stayed on sys.path after import"
    assert sys.path == before


# ── BUG 3: project scope resolves against the live cwd ──────────────────────

def test_project_plugins_follow_the_working_directory(dulus_home, tmp_path, monkeypatch):
    ws = tmp_path / "workspace_a"
    pdir = _write_plugin(ws / ".dulus-context" / "plugins", "wsp", "WsTool", "ws")
    _register(ws / ".dulus-context" / "plugins.json", "wsp", pdir, scope="project")

    monkeypatch.chdir(tmp_path)
    ploader.register_plugin_tools(PluginScope.PROJECT)
    assert tool_registry.get_tool("WsTool") is None

    monkeypatch.chdir(ws)
    ploader.register_plugin_tools(PluginScope.PROJECT)
    assert tool_registry.get_tool("WsTool") is not None, \
        "workspace plugin was advertised but never loaded"

    monkeypatch.chdir(tmp_path)
    ploader.register_plugin_tools(PluginScope.PROJECT)
    assert tool_registry.get_tool("WsTool") is None, \
        "workspace plugin stayed loaded after leaving the workspace"


def test_scoped_registration_does_not_wipe_the_other_scope(dulus_home, tmp_path, monkeypatch):
    core = _write_plugin(dulus_home / "plugins", "userp", "UserTool", "user")
    _register(dulus_home / "plugins.json", "userp", core)
    monkeypatch.chdir(tmp_path)

    ploader.register_plugin_tools(PluginScope.USER)
    assert tool_registry.get_tool("UserTool") is not None
    ploader.register_plugin_tools(PluginScope.PROJECT)
    assert tool_registry.get_tool("UserTool") is not None, \
        "registering the project scope retired the user scope"


# ── BUG 5 / 6 / 11: ownership ───────────────────────────────────────────────

def test_profile_cannot_uninstall_an_inherited_plugin(dulus_home):
    core = _write_plugin(dulus_home / "plugins", "mempalace", "BaseTool", "base")
    _register(dulus_home / "plugins.json", "mempalace", core)
    P.create_profile("delta")
    P.switch_profile("delta")

    ok, msg = pstore.uninstall_plugin("mempalace")
    assert not ok
    assert "inherited" in msg.lower()
    assert core.exists(), "the core plugin directory was deleted from inside a profile"


def test_toggling_an_inherited_plugin_writes_to_the_core(dulus_home):
    core = _write_plugin(dulus_home / "plugins", "mempalace", "BaseTool", "base")
    _register(dulus_home / "plugins.json", "mempalace", core)
    P.create_profile("epsilon")
    P.switch_profile("epsilon")

    ok, _ = pstore.disable_plugin("mempalace")
    assert ok
    prof_cfg = json.loads((P.PROFILES_DIR / "epsilon" / "plugins.json").read_text(encoding="utf-8"))
    assert "mempalace" not in prof_cfg.get("plugins", {}), \
        "a phantom entry was forked into the profile config"
    core_cfg = json.loads((dulus_home / "plugins.json").read_text(encoding="utf-8"))
    assert core_cfg["plugins"]["mempalace"]["enabled"] is False


def test_disable_all_leaves_inherited_plugins_alone(dulus_home):
    core = _write_plugin(dulus_home / "plugins", "mempalace", "BaseTool", "base")
    _register(dulus_home / "plugins.json", "mempalace", core)
    P.create_profile("zeta")
    P.switch_profile("zeta")

    pstore.disable_all_plugins()
    core_cfg = json.loads((dulus_home / "plugins.json").read_text(encoding="utf-8"))
    assert core_cfg["plugins"]["mempalace"]["enabled"] is True, \
        "disable_all reached into the core from inside a profile"


# ── BUG 7: memory per profile ───────────────────────────────────────────────

def test_memory_writes_land_in_the_active_profile(dulus_home, monkeypatch):
    from memory import store as mstore
    monkeypatch.setattr(mstore, "_user_memory_dir", lambda: dulus_home / "memory")

    assert mstore.get_memory_dir("user") == dulus_home / "memory"

    P.create_profile("eta")
    P.switch_profile("eta")
    assert mstore.get_memory_dir("user") == P.PROFILES_DIR / "eta" / "memory"


def test_lean_profile_does_not_read_core_memory(dulus_home, monkeypatch):
    from memory import store as mstore
    monkeypatch.setattr(mstore, "_user_memory_dir", lambda: dulus_home / "memory")

    P.create_profile("theta")
    P.switch_profile("theta")
    assert mstore.get_memory_read_dirs("user") == [P.PROFILES_DIR / "theta" / "memory"]

    P.set_inherit_core("theta", True)
    assert dulus_home / "memory" in mstore.get_memory_read_dirs("user")


# ── BUG 10: the prompt must not promise plugins that are absent ─────────────

def test_baseline_only_reports_installed_plugins(dulus_home):
    assert pstore.installed_baseline_plugin_names() == set()
    core = _write_plugin(dulus_home / "plugins", "mempalace", "BaseTool", "base")
    _register(dulus_home / "plugins.json", "mempalace", core)
    assert pstore.installed_baseline_plugin_names() == {"mempalace"}


# ── Skills follow the active profile ────────────────────────────────────────

def test_lean_profile_does_not_search_base_skills(dulus_home, tmp_path, monkeypatch):
    from skill import loader as sloader
    monkeypatch.chdir(tmp_path)

    base_skills = Path.home() / ".dulus" / "skills"
    assert base_skills in sloader._get_skill_paths()

    P.create_profile("iota")
    P.switch_profile("iota")
    paths = sloader._get_skill_paths()
    assert P.PROFILES_DIR / "iota" / "skills" in paths
    assert base_skills not in paths, "a lean profile searched the base skills"

    P.set_inherit_core("iota", True)
    assert base_skills in sloader._get_skill_paths()
