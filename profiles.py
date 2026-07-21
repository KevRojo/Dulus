"""Dulus Profiles — named agents that bundle plugins, skills, persona & config.

A *profile* is a directory `~/.dulus/profiles/<name>/` holding its own
`plugins.json` + `plugins/`, `skills/`, `memory/`, and a `profile.json`
(persona + config overrides). Think of each profile as a different agent:

    /profile create trader "trading agent: TA + market news"
    /profile switch trader        # now Dulus loads trader's skills/plugins/persona

Profiles are **HYBRID**: an active profile's capabilities layer ON TOP of the
Dulus core (the base `~/.dulus`), never replacing it — so you never end up with
a "pelado" agent. The special profile name **"default"** maps to the base
`~/.dulus` itself, so existing installs are untouched and everything is 100%
backward-compatible when no profile has ever been set.

This module is the single source of truth for "where does the active profile
keep its X" — the plugin store, skill loader, and system-prompt builder all
resolve their base paths through here.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

DULUS_HOME = Path.home() / ".dulus"
PROFILES_DIR = DULUS_HOME / "profiles"
ACTIVE_FILE = DULUS_HOME / "active_profile.json"
DEFAULT = "default"


# ── Name handling ───────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    """Safe directory name: lowercase alphanumerics, dash, underscore."""
    n = re.sub(r"[^\w\-]", "-", (name or "").strip().lower()).strip("-_")
    return n or DEFAULT


# ── Active profile ──────────────────────────────────────────────────────────

def active_profile() -> str:
    """Name of the currently active profile ('default' if none set)."""
    try:
        if ACTIVE_FILE.exists():
            data = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
            name = (data.get("name") or "").strip()
            # Honor it only if the dir still exists (or it's default).
            if name and (name == DEFAULT or (PROFILES_DIR / name).is_dir()):
                return name
    except Exception:
        pass
    return DEFAULT


def is_default(name: Optional[str] = None) -> bool:
    return (name or active_profile()) == DEFAULT


# ── Path resolution (the part every subsystem calls) ───────────────────────

def profile_dir(name: Optional[str] = None) -> Optional[Path]:
    """Root dir of a profile, or None for the default (== base ~/.dulus)."""
    name = name or active_profile()
    if name == DEFAULT:
        return None
    return PROFILES_DIR / name


def profile_skills_dir(name: Optional[str] = None) -> Optional[Path]:
    d = profile_dir(name)
    return (d / "skills") if d else None


def profile_plugins_dir(name: Optional[str] = None) -> Optional[Path]:
    d = profile_dir(name)
    return (d / "plugins") if d else None


def profile_plugins_cfg(name: Optional[str] = None) -> Optional[Path]:
    d = profile_dir(name)
    return (d / "plugins.json") if d else None


def profile_memory_dir(name: Optional[str] = None) -> Optional[Path]:
    d = profile_dir(name)
    return (d / "memory") if d else None


# ── Metadata ────────────────────────────────────────────────────────────────

def _meta_path(name: str) -> Path:
    return PROFILES_DIR / name / "profile.json"


def profile_meta(name: Optional[str] = None) -> dict:
    """Return the profile.json contents (empty dict for default/missing)."""
    name = name or active_profile()
    if name == DEFAULT:
        return {"name": DEFAULT, "description": "Dulus core (base ~/.dulus)", "config": {}}
    p = _meta_path(name)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": name, "config": {}}


def inherits_core(name: Optional[str] = None) -> bool:
    """Whether the active (or named) profile inherits the FULL core base.

    True  → the profile sees ALL of the user's base plugins/skills (power mode).
    False → lean: only its own + the minimal baseline (clean-agent mode, default).
    The 'default' profile IS the base, so this is irrelevant for it.
    """
    return bool(profile_meta(name).get("inherit_core", False))


def set_inherit_core(name: str, value: bool) -> tuple[bool, str]:
    """Toggle a profile's core inheritance and persist it."""
    name = sanitize(name)
    if name == DEFAULT:
        return False, "The default profile already IS the core."
    if not (PROFILES_DIR / name).is_dir():
        return False, f"Profile '{name}' not found."
    meta = profile_meta(name)
    meta["inherit_core"] = bool(value)
    _write_meta(name, meta)
    mode = "FULL core (power)" if value else "lean (own + baseline)"
    return True, f"Profile '{name}' now inherits: {mode}."


def _write_meta(name: str, meta: dict) -> None:
    p = _meta_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _count_skills(name: str) -> int:
    d = profile_skills_dir(name)
    if not d or not d.is_dir():
        return 0
    return sum(1 for s in d.iterdir() if (s / "SKILL.md").exists())


def _count_plugins(name: str) -> int:
    cfg = profile_plugins_cfg(name)
    if not cfg or not cfg.exists():
        return 0
    try:
        return len(json.loads(cfg.read_text(encoding="utf-8")).get("plugins", {}) or {})
    except Exception:
        return 0


def list_profiles() -> list[dict]:
    """All profiles (including the implicit 'default'), with quick stats."""
    act = active_profile()
    out = [{
        "name": DEFAULT,
        "active": act == DEFAULT,
        "description": "Dulus core (base ~/.dulus)",
        "skills": 0, "plugins": 0, "created": "",
    }]
    if PROFILES_DIR.is_dir():
        for d in sorted(PROFILES_DIR.iterdir()):
            if not d.is_dir():
                continue
            meta = profile_meta(d.name)
            out.append({
                "name": d.name,
                "active": d.name == act,
                "description": meta.get("description", ""),
                "skills": _count_skills(d.name),
                "plugins": _count_plugins(d.name),
                "created": meta.get("created", ""),
            })
    return out


# ── CRUD ────────────────────────────────────────────────────────────────────

def create_profile(name: str, description: str = "", persona: Optional[str] = None,
                   model: str = "", lang: str = "",
                   system_prompt_fragment: str = "") -> tuple[bool, str]:
    """Scaffold a new profile dir + profile.json. Does NOT switch to it."""
    name = sanitize(name)
    if name == DEFAULT:
        return False, "'default' is reserved (it's the Dulus core)."
    pdir = PROFILES_DIR / name
    if pdir.exists():
        return False, f"Profile '{name}' already exists."
    try:
        (pdir / "skills").mkdir(parents=True, exist_ok=True)
        (pdir / "plugins").mkdir(parents=True, exist_ok=True)
        (pdir / "memory").mkdir(parents=True, exist_ok=True)
        (pdir / "plugins.json").write_text(json.dumps({"plugins": {}}, indent=2), encoding="utf-8")
        meta = {
            "name": name,
            "description": description,
            "persona": persona,
            # Lean by default = a clean agent (own plugins/skills + baseline).
            # Native self-improvement tools (autoadapter, MarketplaceSearch/Install,
            # mr_dulus, Skill, plugin/skill install) are ALWAYS available regardless,
            # so a lean profile can still grow itself. Set true for full inheritance.
            "inherit_core": False,
            "created": datetime.now().strftime("%Y-%m-%d"),
            "config": {
                "model": model,
                "lang": lang,
                "system_prompt_fragment": system_prompt_fragment,
            },
        }
        _write_meta(name, meta)
    except Exception as e:
        return False, f"Could not create profile: {e}"
    return True, f"Profile '{name}' created. Switch with: /profile switch {name}"


def seed_from(new_name: str, source: Optional[str] = None) -> tuple[bool, str]:
    """Make a freshly-created profile inherit the skills/plugins of `source`.

    - source == default (core): flip inherit_core=True so the new profile sees
      ALL of the core base plugins/skills — no copying needed.
    - source == a named profile: copy its skills/, plugins/ and plugins.json
      into the new profile, and carry its inherit_core flag.
    """
    new_name = sanitize(new_name)
    source = source or active_profile()
    ndir = PROFILES_DIR / new_name
    if not ndir.is_dir():
        return False, f"Profile '{new_name}' not found."

    if source == DEFAULT:
        meta = profile_meta(new_name)
        meta["inherit_core"] = True
        _write_meta(new_name, meta)
        return True, f"'{new_name}' inherits the full Dulus core (power mode)."

    sdir = PROFILES_DIR / source
    if not sdir.is_dir():
        return False, f"Source profile '{source}' not found."
    try:
        for kind in ("skills", "plugins"):
            src_sub = sdir / kind
            if src_sub.is_dir():
                for item in src_sub.iterdir():
                    dest = ndir / kind / item.name
                    if item.is_dir() and not dest.exists():
                        shutil.copytree(item, dest)
        src_cfg = sdir / "plugins.json"
        if src_cfg.exists():
            shutil.copy2(src_cfg, ndir / "plugins.json")
        meta = profile_meta(new_name)
        meta["inherit_core"] = inherits_core(source)
        _write_meta(new_name, meta)
    except Exception as e:
        return False, f"Seeded partially from '{source}': {e}"
    return True, (f"'{new_name}' inherited {_count_skills(new_name)} skill(s) / "
                  f"{_count_plugins(new_name)} plugin(s) from '{source}'.")


def switch_profile(name: str) -> tuple[bool, str]:
    """Set the active profile. 'default' returns to the Dulus core."""
    name = sanitize(name) if name != DEFAULT else DEFAULT
    if name != DEFAULT and not (PROFILES_DIR / name).is_dir():
        return False, f"Profile '{name}' not found. Create it: /profile create {name}"
    try:
        ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_FILE.write_text(
            json.dumps({"name": name, "since": datetime.now().isoformat(timespec="seconds")}, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        return False, f"Could not switch: {e}"
    return True, f"Active profile → '{name}'."


def delete_profile(name: str) -> tuple[bool, str]:
    name = sanitize(name)
    if name == DEFAULT:
        return False, "Cannot delete the default (core) profile."
    pdir = PROFILES_DIR / name
    if not pdir.is_dir():
        return False, f"Profile '{name}' not found."
    if active_profile() == name:
        switch_profile(DEFAULT)  # don't leave a dangling active pointer
    try:
        def _force(func, path, _exc):
            import os, stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(pdir, onexc=_force)  # type: ignore[call-arg]
    except Exception as e:
        return False, f"Could not delete: {e}"
    return True, f"Profile '{name}' deleted."


# ── Config / persona overlay for the runtime ───────────────────────────────

def apply_profile_config(cfg: dict, name: Optional[str] = None) -> dict:
    """Overlay the active profile's config (model/lang) onto a live config dict.

    Mutates and returns cfg. No-op for the default profile. Empty overrides are
    ignored so a profile only changes what it explicitly sets.
    """
    meta = profile_meta(name)
    pc = meta.get("config", {}) or {}
    for key in ("model", "lang"):
        val = (pc.get(key) or "").strip()
        if val:
            cfg[key] = val
    return cfg


def profile_system_fragment(name: Optional[str] = None) -> str:
    """The persona/system-prompt text for the active profile (or '').

    Resolves in order: profile.json config.system_prompt_fragment →
    referenced persona in data/personas.json → ''.
    """
    meta = profile_meta(name)
    frag = ((meta.get("config", {}) or {}).get("system_prompt_fragment") or "").strip()
    if frag:
        return frag
    persona_id = meta.get("persona")
    if persona_id:
        try:
            personas_file = Path(__file__).resolve().parent / "data" / "personas.json"
            if personas_file.exists():
                for p in json.loads(personas_file.read_text(encoding="utf-8")):
                    if p.get("id") == persona_id:
                        return (p.get("system_prompt_fragment") or "").strip()
        except Exception:
            pass
    return ""
