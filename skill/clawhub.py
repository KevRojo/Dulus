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


# ── AWESOME (live, no install required) ──────────────────────────────────
# Fetches the alirezarezvani/claude-skills catalog directly from GitHub so
# users who don't have Claude Code installed (no ~/.claude/plugins/) still
# see the ~235 awesome skills. Tree call costs 1 GitHub API hit; per-skill
# SKILL.md fetches go through raw.githubusercontent.com (no rate limit).
# Result is cached in ~/.dulus/cache/awesome-skills.json for 24h.

_AWESOME_REPO = "alirezarezvani/claude-skills"
_AWESOME_BRANCH = "main"
_AWESOME_CACHE = Path.home() / ".dulus" / "cache" / "awesome-skills.json"
_AWESOME_TTL_SEC = 24 * 3600

_AWESOME_EXCLUDE_REMOTE = {
    "docs", "documentation", "tests", "scripts",
    "templates", "standards", "eval-workspace",
}


def _fetch_awesome_remote(with_descriptions: bool = False) -> list[dict]:
    """Hit the GitHub tree API to list awesome skills.

    Default (with_descriptions=False): ONE API call, instant, no descriptions.
    Returns 235 entries with name + url ready in <1s.

    with_descriptions=True: also pulls each SKILL.md's frontmatter via
    raw.githubusercontent.com — done with a thread pool so it stays under ~5s.
    """
    import time
    tree_url = (
        f"https://api.github.com/repos/{_AWESOME_REPO}/git/trees/"
        f"{_AWESOME_BRANCH}?recursive=1"
    )
    try:
        with urllib.request.urlopen(tree_url, timeout=15) as resp:
            tree = json.loads(resp.read())
    except Exception:
        return []

    skill_paths = []
    for entry in tree.get("tree", []):
        path = entry.get("path", "")
        if not path.endswith("/SKILL.md"):
            continue
        parts = path.split("/")
        if any(p.startswith(".") for p in parts):
            continue
        if _AWESOME_EXCLUDE_REMOTE.intersection(parts):
            continue
        skill_paths.append(path)

    # Build the skill list from paths alone — instant, no per-file fetch.
    skills = []
    for path in skill_paths:
        rel_dir = "/".join(path.split("/")[:-1])
        skill_name = path.split("/")[-2]
        raw_url = (
            f"https://raw.githubusercontent.com/{_AWESOME_REPO}/"
            f"{_AWESOME_BRANCH}/{path}"
        )
        skills.append({
            "id": f"awesome/{rel_dir}",
            "plugin": "awesome",
            "skill": skill_name,
            "description": "",  # filled in below if with_descriptions
            "path": raw_url,
            "source": "awesome-remote",
            "_remote_dir": rel_dir,
        })

    if with_descriptions and skills:
        # Pull frontmatter in parallel via raw.githubusercontent.com (no
        # rate limit). 12 workers keeps GitHub happy and 235 fetches done
        # in 3-5 seconds instead of the original 50-120 seconds.
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _fetch_one(s):
            try:
                with urllib.request.urlopen(s["path"], timeout=8) as r:
                    raw = r.read().decode("utf-8", errors="ignore")
                meta = _parse_frontmatter(raw)
                s["description"] = meta.get("description", "")
            except Exception:
                pass
            return s

        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(_fetch_one, skills))

    _AWESOME_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        _AWESOME_CACHE.write_text(
            json.dumps({
                "fetched_at": time.time(),
                "with_descriptions": with_descriptions,
                "skills": skills,
            }, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    return skills


def list_awesome_remote(query: Optional[str] = None, force_refresh: bool = False, with_descriptions: bool = False) -> list[dict]:
    """Return the awesome-skills catalog (cached).

    Default: one GitHub tree call (~1s, no descriptions), cached 24h.
    with_descriptions=True: also fetches each SKILL.md frontmatter in parallel.
    """
    import time
    skills: list[dict] = []
    cache_has_descriptions = False
    if not force_refresh and _AWESOME_CACHE.exists():
        try:
            data = json.loads(_AWESOME_CACHE.read_text(encoding="utf-8"))
            if time.time() - float(data.get("fetched_at", 0)) < _AWESOME_TTL_SEC:
                skills = data.get("skills", [])
                cache_has_descriptions = bool(data.get("with_descriptions"))
        except Exception:
            skills = []
    # Refetch if no cache, or if user wants descriptions but cache doesn't have them.
    if not skills or (with_descriptions and not cache_has_descriptions):
        skills = _fetch_awesome_remote(with_descriptions=with_descriptions)

    if query:
        q = query.lower()
        skills = [
            s for s in skills
            if q in s.get("id", "").lower() or q in s.get("description", "").lower()
        ]
    return skills


# ── COMPOSIO (live API listing of toolkits) ───────────────────────────────
# The composio backend exposes a public toolkit list — we surface it as
# pseudo-skills so users can browse `gmail`, `slack`, etc. and create a
# Composio session from the same /skill UI.

_COMPOSIO_TOOLKITS_URL = "https://backend.composio.dev/api/v3/toolkits?cursor=&limit=500"
_COMPOSIO_CACHE = Path.home() / ".dulus" / "cache" / "composio-toolkits.json"


# Curated fallback list — used when no Composio API key is available so the
# /skill list composio command still shows something useful instead of an
# empty result. ~30 of the most-requested toolkits.
_COMPOSIO_FALLBACK = [
    ("gmail", "Gmail email — read, send, label, search messages."),
    ("googlecalendar", "Google Calendar — events, attendees, schedules."),
    ("googledrive", "Google Drive — files, folders, sharing."),
    ("googlesheets", "Google Sheets — read/write spreadsheets."),
    ("googledocs", "Google Docs — create and edit documents."),
    ("slack", "Slack — messages, channels, files, search."),
    ("github", "GitHub — repos, issues, PRs, releases, branches."),
    ("gitlab", "GitLab — projects, issues, merge requests."),
    ("notion", "Notion — pages, databases, blocks."),
    ("linear", "Linear — issues, projects, cycles, teams."),
    ("asana", "Asana — tasks, projects, sections."),
    ("trello", "Trello — boards, cards, lists."),
    ("clickup", "ClickUp — tasks, lists, spaces."),
    ("jira", "Jira — issues, sprints, projects."),
    ("confluence", "Confluence — pages, spaces, content."),
    ("discord", "Discord — guilds, channels, messages."),
    ("telegram", "Telegram bot API — messages, files."),
    ("twitter", "Twitter/X — tweets, search, profiles."),
    ("reddit", "Reddit — posts, comments, subreddits."),
    ("hackernews", "Hacker News — stories, comments, search."),
    ("youtube", "YouTube — videos, channels, comments, captions."),
    ("spotify", "Spotify — playlists, search, playback."),
    ("hubspot", "HubSpot — contacts, deals, companies."),
    ("salesforce", "Salesforce — leads, accounts, opportunities."),
    ("shopify", "Shopify — products, orders, customers."),
    ("stripe", "Stripe — payments, customers, subscriptions."),
    ("airtable", "Airtable — bases, tables, records."),
    ("firebase", "Firebase — Firestore, Realtime DB, Auth."),
    ("supabase", "Supabase — Postgres, auth, storage."),
    ("perplexity", "Perplexity — AI-powered web search."),
    ("firecrawl", "Firecrawl — scrape & crawl websites to markdown."),
    ("exa", "Exa — semantic web search."),
]


def _load_composio_api_key() -> str:
    """Load API key from env, ~/.dulus/config.json, or ~/.falcon/config.json."""
    import os as _os
    key = _os.environ.get("COMPOSIO_API_KEY", "").strip()
    if key:
        return key
    for cfg_path in (Path.home() / ".dulus" / "config.json",
                     Path.home() / ".falcon" / "config.json"):
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                k = cfg.get("composio_api_key", "")
                if k:
                    return k
            except Exception:
                continue
    return ""


def list_composio_toolkits(query: Optional[str] = None, force_refresh: bool = False) -> list[dict]:
    """Return Composio toolkits as skill-like dicts. Cached 24h.

    Authenticated path (API key set): hit the live `/api/v3/toolkits` endpoint.
    Unauthenticated path: return the curated _COMPOSIO_FALLBACK list so the
    /skill list composio UI still shows something useful.
    """
    import time
    items: list[dict] = []
    if not force_refresh and _COMPOSIO_CACHE.exists():
        try:
            data = json.loads(_COMPOSIO_CACHE.read_text(encoding="utf-8"))
            if time.time() - float(data.get("fetched_at", 0)) < _AWESOME_TTL_SEC:
                items = data.get("items", [])
        except Exception:
            items = []
    if not items:
        api_key = _load_composio_api_key()
        if api_key:
            req = urllib.request.Request(
                _COMPOSIO_TOOLKITS_URL,
                headers={"x-api-key": api_key, "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    payload = json.loads(resp.read())
                for tk in payload.get("items", payload.get("data", [])):
                    slug = tk.get("slug") or tk.get("name", "")
                    if not slug:
                        continue
                    items.append({
                        "id": f"composio/{slug}",
                        "plugin": "composio",
                        "skill": slug,
                        "description": tk.get("description") or tk.get("meta", {}).get("description", ""),
                        "path": f"https://composio.dev/apps/{slug}",
                        "source": "composio",
                    })
            except Exception:
                pass  # fall through to fallback list below

        # Fallback: no key, or auth call failed — show the curated list so the
        # user still has something to browse / use as session toolkits.
        if not items:
            for slug, desc in _COMPOSIO_FALLBACK:
                items.append({
                    "id": f"composio/{slug}",
                    "plugin": "composio",
                    "skill": slug,
                    "description": desc + ("" if api_key else "  [curated fallback — set COMPOSIO_API_KEY for the full live catalog]"),
                    "path": f"https://composio.dev/apps/{slug}",
                    "source": "composio-fallback" if not api_key else "composio",
                })

        _COMPOSIO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        try:
            _COMPOSIO_CACHE.write_text(
                json.dumps({"fetched_at": time.time(), "items": items}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    if query:
        q = query.lower()
        items = [
            t for t in items
            if q in t.get("id", "").lower() or q in t.get("description", "").lower()
        ]
    return items


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
