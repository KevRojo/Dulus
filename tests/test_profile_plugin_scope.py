"""Plugin ownership must follow the install PATH, not the active profile.

Regression tests for the bug where installing a plugin under a named profile
registered it in the CORE `~/.dulus/plugins.json` while the files landed in
`~/.dulus/profiles/<p>/plugins/<name>`. The plugin was then advertised to every
profile, loaded from a directory the active profile did not own, and — because
the name now looked "already installed" — could never be reinstalled: git clone
refused the leftover non-empty destination on every retry.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated ~/.dulus with one named profile active."""
    import profiles
    import plugin.store as st

    home = tmp_path / "home"
    dulus = home / ".dulus"
    prof_root = dulus / "profiles"
    name = "making_it"

    (prof_root / name / "plugins").mkdir(parents=True)
    (dulus / "plugins").mkdir(parents=True)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(profiles, "DULUS_HOME", dulus)
    monkeypatch.setattr(profiles, "PROFILES_DIR", prof_root)
    monkeypatch.setattr(profiles, "ACTIVE_FILE", dulus / "active_profile.json")
    monkeypatch.setattr(st, "USER_PLUGIN_DIR", dulus / "plugins")
    monkeypatch.setattr(st, "USER_PLUGIN_CFG", dulus / "plugins.json")

    def activate(p: str) -> None:
        (dulus / "active_profile.json").write_text(json.dumps({"name": p}), encoding="utf-8")

    activate(name)
    assert profiles.active_profile() == name

    class Env:
        store = st
        profile = name
        core_dir = dulus / "plugins"
        core_cfg = dulus / "plugins.json"
        prof_dir = prof_root / name / "plugins"
        prof_cfg = prof_root / name / "plugins.json"
        use_profile = staticmethod(lambda: activate(name))
        use_default = staticmethod(lambda: activate("default"))

    Env.prof_cfg.write_text(json.dumps({"plugins": {}}), encoding="utf-8")
    Env.core_cfg.write_text(json.dumps({"plugins": {}}), encoding="utf-8")
    return Env


def _src(tmp_path: Path, name: str) -> Path:
    """A minimal local plugin source with a valid manifest."""
    d = tmp_path / f"src_{name}"
    d.mkdir()
    (d / "plugin.json").write_text(
        json.dumps({"name": name, "version": "1.0", "description": "test", "tools": []}),
        encoding="utf-8",
    )
    return d


def _cfg_names(cfg: Path) -> set[str]:
    return set(json.loads(cfg.read_text(encoding="utf-8")).get("plugins", {}))


def _entry(st, name: str, install_dir: Path):
    return st.PluginEntry.from_dict({
        "name": name, "scope": "user", "source": "git",
        "install_dir": str(install_dir), "enabled": True,
    })


def test_ownership_follows_install_path(env):
    st = env.store
    assert st._owning_cfg(_entry(st, "sherlock", env.prof_dir / "sherlock")) == env.prof_cfg
    assert st._owning_cfg(_entry(st, "art", env.core_dir / "art")) == env.core_cfg


def test_core_cfg_does_not_advertise_a_profile_install(env):
    """A mis-filed entry must not leak the plugin into other profiles."""
    st = env.store
    env.core_cfg.write_text(json.dumps({"plugins": {
        "sherlock": {"name": "sherlock", "scope": "user", "source": "git",
                     "install_dir": str(env.prof_dir / "sherlock"), "enabled": True},
    }}), encoding="utf-8")

    assert [p.name for p in st.list_plugins(st.PluginScope.USER)] == []


def test_purge_removes_only_misfiled_entries_and_keeps_files(env):
    st = env.store
    env.core_cfg.write_text(json.dumps({"plugins": {
        "sherlock": {"name": "sherlock", "scope": "user", "source": "git",
                     "install_dir": str(env.prof_dir / "sherlock"), "enabled": True},
        "art": {"name": "art", "scope": "user", "source": "git",
                "install_dir": str(env.core_dir / "art"), "enabled": True},
    }}), encoding="utf-8")
    (env.prof_dir / "sherlock").mkdir(parents=True)

    assert st.purge_misfiled_entries() == 1
    assert _cfg_names(env.core_cfg) == {"art"}
    assert (env.prof_dir / "sherlock").exists(), "purge must never delete files"


def test_install_under_profile_stays_out_of_core(env, tmp_path):
    st = env.store
    ok, msg = st.install_plugin(f"demo@{_src(tmp_path, 'demo')}")

    assert ok, msg
    assert (env.prof_dir / "demo").exists()
    assert not (env.core_dir / "demo").exists()
    assert _cfg_names(env.prof_cfg) == {"demo"}
    assert _cfg_names(env.core_cfg) == set()


def test_orphan_directory_does_not_dead_end_the_install(env, tmp_path):
    """Leftover files from an interrupted install must not block a retry."""
    st = env.store
    orphan = env.prof_dir / "demo"
    orphan.mkdir(parents=True)
    (orphan / "stale.txt").write_text("leftover", encoding="utf-8")

    ok, msg = st.install_plugin(f"demo@{_src(tmp_path, 'demo')}")

    assert ok, msg
    assert not (orphan / "stale.txt").exists()


def test_default_profile_is_unaffected(env, tmp_path):
    st = env.store
    st.install_plugin(f"only_in_profile@{_src(tmp_path, 'only_in_profile')}")

    env.use_default()
    ok, msg = st.install_plugin(f"core_one@{_src(tmp_path, 'core_one')}")

    assert ok, msg
    assert (env.core_dir / "core_one").exists()
    assert _cfg_names(env.core_cfg) == {"core_one"}
    names = [p.name for p in st.list_plugins(st.PluginScope.USER)]
    assert "core_one" in names
    assert "only_in_profile" not in names


def test_uninstall_in_profile_leaves_core_alone(env, tmp_path):
    st = env.store
    st.install_plugin(f"demo@{_src(tmp_path, 'demo')}")
    env.use_default()
    st.install_plugin(f"keep@{_src(tmp_path, 'keep')}")
    env.use_profile()

    ok, msg = st.uninstall_plugin("demo")

    assert ok, msg
    assert not (env.prof_dir / "demo").exists()
    assert (env.core_dir / "keep").exists()
    assert _cfg_names(env.core_cfg) == {"keep"}
