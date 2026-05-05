"""ClawHub + local Anthropic skill importer for Dulus.

Sources:
  - LOCAL      : ~/.claude/plugins/marketplaces/claude-plugins-official/  (Anthropic, on-disk)
  - AWESOME    : ~/.claude/plugins/marketplaces/alireza-claude-skills/    (alirezarezvani/claude-skills, ~235 skills across 9 domains)
  - CLAWHUB    : https://clawhub.ai  (community, 52k+ skills, via API)
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────

DULUS_SKILLS_DIR = Path.home() / ".dulus" / "skills"
ANTHROPIC_PLUGINS = (
    Path.home() / ".claude" / "plugins" / "marketplaces" / "claude-plugins-official"
)
AWESOME_SKILLS = (
    Path.home() / ".claude" / "plugins" / "marketplaces" / "alireza-claude-skills"
)

# ── ClawHub API (Convex HTTP) ──────────────────────────────────────────────
# TODO: reverse-engineer exact endpoint from clawhub.ai/openclaw/clawhub repo
CLAWHUB_API_BASE = "https://clawhub.ai"          # placeholder
CLAWHUB_SEARCH   = f"{CLAWHUB_API_BASE}/api/search"  # placeholder
CLAWHUB_GET      = f"{CLAWHUB_API_BASE}/api/skill"   # placeholder — /api/skill/<slug>


# ── LOCAL (Anthropic marketplace on disk) ─────────────────────────────────

def list_local(query: Optional[str] = None) -> list[dict]:
    """Return all SKILL.md entries from local marketplaces (Anthropic + Awesome Skills)."""
    skills = []
    q = query.lower() if query else None

    # Anthropic: .../plugins/<plugin>/skills/<skill>/SKILL.md
    plugins_dir = ANTHROPIC_PLUGINS / "plugins"
    external_dir = ANTHROPIC_PLUGINS / "external_plugins"
    for base, prefix in [(plugins_dir, ""), (external_dir, "external/")]:
        if not base.exists():
            continue
        for skill_md in sorted(base.glob("*/skills/*/SKILL.md")):
            parts = skill_md.parts
            plugin = parts[-4]
            skill  = parts[-2]
            meta   = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            desc   = meta.get("description", "")
            id_str = f"{prefix}{plugin}/{skill}"
            
            if q and q not in id_str.lower() and q not in desc.lower():
                continue

            skills.append({
                "id":          id_str,
                "plugin":      plugin,
                "skill":       skill,
                "description": desc,
                "path":        str(skill_md),
                "source":      "anthropic",
            })

    # alirezarezvani/claude-skills — ~235 skills nested under domain folders
    # (engineering/, marketing-skill/, product-team/, etc.). Skip top-level
    # docs / scaffolding folders that aren't real skills.
    _AWESOME_EXCLUDE = {"docs", "documentation", "tests", "scripts", "templates", "standards", "eval-workspace"}
    if AWESOME_SKILLS.exists():
        for skill_md in sorted(AWESOME_SKILLS.glob("**/SKILL.md")):
            # Look only at parts RELATIVE to the marketplace root, otherwise
            # the home dir component ".claude" trips the dot-prefix filter.
            try:
                rel_parts = skill_md.relative_to(AWESOME_SKILLS).parts
            except ValueError:
                continue
            # Skip dot-prefixed folders (.gemini/, .claude/, .codex/, etc. — tool configs that
            # mirror the canonical skills) and excluded scaffolding folders.
            if any(p.startswith(".") for p in rel_parts):
                continue
            if _AWESOME_EXCLUDE.intersection(rel_parts):
                continue

            skill = skill_md.parent.name
            try:
                raw = skill_md.read_text(encoding="utf-8")
            except (FileNotFoundError, OSError):
                continue
            meta  = _parse_frontmatter(raw)
            desc  = meta.get("description", "")
            # Encode the domain path (e.g. "engineering/foo") so skills with
            # the same name in different domains don't collide.
            try:
                rel = skill_md.parent.relative_to(AWESOME_SKILLS).as_posix()
            except ValueError:
                rel = skill
            id_str = f"awesome/{rel}"

            if q and q not in id_str.lower() and q not in desc.lower():
                continue

            skills.append({
                "id":          id_str,
                "plugin":      "awesome",
                "skill":       skill,
                "description": desc,
                "path":        str(skill_md),
                "source":      "awesome",
            })


    return skills


def get_local(slug: str) -> Optional[dict]:
    """Find a local skill by its id (plugin/skill or external/plugin/skill)."""
    for s in list_local():
        if s["id"] == slug or s["skill"] == slug:
            return s
    return None


def install_local(slug: str) -> tuple[bool, str]:
    """Copy a local Anthropic skill (SKILL.md + all support files) into ~/.dulus/skills/<name>/"""
    import shutil
    entry = get_local(slug)
    if not entry:
        return False, f"Skill '{slug}' not found in local marketplaces (Anthropic / Awesome)."

    skill_dir = Path(entry["path"]).parent  # dir containing SKILL.md + support files
    name = entry["skill"]
    dest_dir = DULUS_SKILLS_DIR / name
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy all files from the skill directory
    copied = []
    for src in skill_dir.rglob("*"):
        if src.is_file():
            rel = src.relative_to(skill_dir)
            dst = dest_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(str(rel))

    # Rewrite SKILL.md with Dulus frontmatter prepended
    skill_md = dest_dir / "SKILL.md"
    if skill_md.exists():
        raw = skill_md.read_text(encoding="utf-8")
        body = _strip_frontmatter(raw)
        skill_md.write_text(_dulus_frontmatter(entry) + body, encoding="utf-8")

    return True, f"Installed '{name}' → {dest_dir}  ({len(copied)} files: {', '.join(copied[:5])}{'...' if len(copied)>5 else ''})"


# ── CLAWHUB (remote) ───────────────────────────────────────────────────────

def search_clawhub(query: str, limit: int = 10) -> list[dict]:
    """Search ClawHub for skills matching query.
    TODO: fill in real Convex endpoint once reversed.
    """
    # PLACEHOLDER — returns empty until endpoint is confirmed
    _ = query, limit
    return []


def install_clawhub(slug: str) -> tuple[bool, str]:
    """Download a skill from ClawHub by slug and save to ~/.dulus/skills/.
    TODO: fill in real endpoint.
    """
    # PLACEHOLDER
    return False, f"ClawHub API endpoint not yet mapped. Try: /skill get local/{slug}"


# ── Installed skills ───────────────────────────────────────────────────────

def list_installed(query: Optional[str] = None) -> list[dict]:
    """Return skills already saved in ~/.dulus/skills/."""
    DULUS_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skills = []
    seen = set()
    q = query.lower() if query else None

    # New format: subdirs with SKILL.md
    for f in sorted(DULUS_SKILLS_DIR.glob("*/SKILL.md")):
        name = f.parent.name
        meta = _parse_frontmatter(f.read_text(encoding="utf-8"))
        desc = meta.get("description", "")
        
        if q and q not in name.lower() and q not in desc.lower():
            continue

        files = list(f.parent.rglob("*"))
        skills.append({
            "name":        name,
            "description": desc,
            "source":      meta.get("clawhub_source", "unknown"),
            "path":        str(f.parent),
            "files":       len([x for x in files if x.is_file()]),
        })
        seen.add(name)

    # Old format: flat .md files
    for f in sorted(DULUS_SKILLS_DIR.glob("*.md")):
        name = f.stem
        if name not in seen:
            meta = _parse_frontmatter(f.read_text(encoding="utf-8"))
            desc = meta.get("description", "")

            if q and q not in name.lower() and q not in desc.lower():
                continue

            skills.append({
                "name":        name,
                "description": desc,
                "source":      meta.get("clawhub_source", "unknown"),
                "path":        str(f),
                "files":       1,
            })
    return skills


def read_skill(name: str) -> Optional[str]:
    """Return the body (no frontmatter) of an installed skill."""
    # New format: subdirectory with SKILL.md
    subdir = DULUS_SKILLS_DIR / name / "SKILL.md"
    if subdir.exists():
        raw = subdir.read_text(encoding="utf-8")
        return _strip_frontmatter(raw)
    # Old format: flat .md file
    path = DULUS_SKILLS_DIR / f"{name}.md"
    if path.exists():
        raw = path.read_text(encoding="utf-8")
        return _strip_frontmatter(raw)
    # Fuzzy match
    matches = list(DULUS_SKILLS_DIR.glob(f"*{name}*/SKILL.md")) + list(DULUS_SKILLS_DIR.glob(f"*{name}*.md"))
    if not matches:
        return None
    raw = matches[0].read_text(encoding="utf-8")
    return _strip_frontmatter(raw)


# ── Helpers ───────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n?", "", text, count=1, flags=re.DOTALL).strip()


def _dulus_frontmatter(entry: dict) -> str:
    return (
        f"---\n"
        f"name: {entry['skill']}\n"
        f"description: {entry.get('description', '')}\n"
        f"clawhub_source: {entry.get('source', 'anthropic')}\n"
        f"triggers: [/{entry['skill']}]\n"
        f"---\n\n"
    )
