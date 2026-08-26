"""MCP Hub — 0-friction MCP server marketplace for Dulus.

Discover, search, and install MCP servers with one command.
Modeled after skill/clawhub.py but for MCP servers.

Sources:
  - OFFICIAL  : modelcontextprotocol/servers (official MCP servers on GitHub)
  - DULUS     : kevrojo/dulus-mcp (community MCP servers)
  - INSTALLED : ~/.dulus/mcp.json (locally configured servers)

Usage:
    from dulus_mcp.hub import list_available, search, install, uninstall, list_installed
    servers = search("git")  # search all sources
    install("filesystem")     # 0-friction install
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional

from .config import (
    USER_MCP_CONFIG,
    add_server_to_user_config,
    load_mcp_configs,
    remove_server_from_user_config,
)
from .types import MCPServerConfig, MCPTransport

# ── Paths ──────────────────────────────────────────────────────────────────

DULUS_MCP_DIR = Path.home() / ".dulus" / "mcp-servers"
MCP_CACHE_DIR = Path.home() / ".dulus" / "cache"

# ── Official MCP servers (modelcontextprotocol/servers) ─────────────────────

_OFFICIAL_REPO = "modelcontextprotocol/servers"
_OFFICIAL_BRANCH = "main"
_OFFICIAL_CACHE = MCP_CACHE_DIR / "mcp-official-servers.json"
_OFFICIAL_TTL_SEC = 6 * 3600

# Curated list of the most popular/useful MCP servers from the official repo.
# These are the ones we surface as "official" — each maps to a directory in
# modelcontextprotocol/servers/src/<name>/.
_OFFICIAL_CURATED = {
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "description": "Read and write local files. Requires path arguments.",
        "requires_args": True,
        "arg_prompt": "Enter the directories the filesystem server can access (comma-separated):",
        "runtime": "node",
    },
    "git": {
        "command": "uvx",
        "args": ["mcp-server-git"],
        "description": "Git repository operations — read commits, branches, diffs.",
        "requires_args": False,
        "runtime": "python",
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "description": "GitHub API — repos, issues, PRs, search. Requires GITHUB_PERSONAL_ACCESS_TOKEN.",
        "requires_args": False,
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
        "runtime": "node",
    },
    "postgres": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "description": "PostgreSQL database queries. Requires database URL.",
        "requires_args": True,
        "arg_prompt": "Enter your PostgreSQL connection URL (postgresql://user:pass@host/db):",
        "runtime": "node",
    },
    # NOTE: @modelcontextprotocol/server-sqlite was removed/renamed upstream —
    # confirmed 404 on the npm registry (2026-07-13). Using the actively
    # maintained community replacement (mcp-server-sqlite-npx) instead so
    # `/mcp install sqlite` doesn't hang until timeout on a dead package.
    "sqlite": {
        "command": "npx",
        "args": ["-y", "mcp-server-sqlite-npx"],
        "description": "SQLite database operations (community-maintained fork after the official package was delisted).",
        "requires_args": True,
        "arg_prompt": "Enter the path to your SQLite database file:",
        "runtime": "node",
    },
    "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "description": "Slack — read channels, send messages. Requires SLACK_BOT_TOKEN.",
        "requires_args": False,
        "env": {"SLACK_BOT_TOKEN": "", "SLACK_TEAM_ID": ""},
        "runtime": "node",
    },
    "memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Persistent memory — remembers facts across conversations.",
        "requires_args": False,
        "runtime": "node",
    },
    "fetch": {
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "description": "Fetch web pages and extract content as markdown.",
        "requires_args": False,
        "runtime": "python",
    },
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "description": "Brave Search API — web search. Requires BRAVE_API_KEY.",
        "requires_args": False,
        "env": {"BRAVE_API_KEY": ""},
        "runtime": "node",
    },
    "puppeteer": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "description": "Browser automation — screenshot, click, navigate.",
        "requires_args": False,
        "runtime": "node",
    },
    "google-maps": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-google-maps"],
        "description": "Google Maps — geocoding, directions, places. Requires GOOGLE_MAPS_API_KEY.",
        "requires_args": False,
        "env": {"GOOGLE_MAPS_API_KEY": ""},
        "runtime": "node",
    },
    # NOTE: @modelcontextprotocol/server-sentry was removed from npm (confirmed
    # 404, 2026-07-13). Sentry now maintains their own official MCP server
    # package directly — @sentry/mcp-server — actively published (last release
    # 2026-07-02 as of this fix). Switched to that instead of hanging on a
    # dead package until timeout.
    "sentry": {
        "command": "npx",
        "args": ["-y", "@sentry/mcp-server"],
        "description": "Sentry — error tracking and issue management. Requires SENTRY_AUTH_TOKEN.",
        "requires_args": False,
        "env": {"SENTRY_AUTH_TOKEN": ""},
        "runtime": "node",
    },
    # Make.com (formerly Integromat) official MCP server — @makehq/mcp-server.
    # Was previously only reachable via the "awesome" README-scraped catalog,
    # which has no real command (just name/description/repo_url), causing
    # installs to write a broken command="" entry to mcp.json. Curated here
    # with the real npm package + required env vars instead.
    "make": {
        "command": "npx",
        "args": ["-y", "@makehq/mcp-server"],
        "description": "Make.com (Integromat) — run scenarios, manage account. Requires MAKE_API_KEY.",
        "requires_args": False,
        "env": {"MAKE_API_KEY": "", "MAKE_ZONE": "", "MAKE_TEAM": ""},
        "runtime": "node",
        "repo_url": "https://github.com/integromat/make-mcp-server",
    },
    # Datadog official remote MCP server: OAuth-backed HTTP endpoint.
    # No local runtime needed; auth happens via browser during first connect.
    "datadog": {
        "command": "",
        "args": [],
        "description": "Datadog — metrics, logs, traces, monitors, dashboards, security signals. OAuth via browser.",
        "requires_args": True,
        "arg_prompt": "Enter your Datadog site (e.g. app.datadoghq.com, us3.datadoghq.com, app.datadoghq.eu, ap1.datadoghq.com, uk1.datadoghq.com):",
        "transport": "http",
        "url": "https://mcp.datadoghq.com/api/unstable/mcp-server/mcp",
        "runtime": "",
        "repo_url": "https://github.com/datadog-labs/mcp-server",
    },
}

# ── Dulus community MCP servers ────────────────────────────────────────────

_DULUS_MCP_REPO = "kevrojo/dulus-mcp"
_DULUS_MCP_BRANCH = "main"
_DULUS_MCP_CACHE = MCP_CACHE_DIR / "mcp-dulus-servers.json"
_DULUS_MCP_TTL_SEC = 6 * 3600

# Fallback curated list until the community repo grows
_DULUS_CURATED = {
    "dulus-tools": {
        "command": "python",
        "args": ["-m", "dulus_tools.mcp_server"],
        "description": "Dulus native tools exposed as MCP server.",
        "requires_args": False,
        "runtime": "python",
    },
}

# ── Official MCP Registry (registry.modelcontextprotocol.io) ────────────────
# The metaregistry backed by Anthropic, GitHub, Microsoft & PulseMCP. Machine-
# readable JSON API, paginated by cursor. Thousands of servers. No API key.
_OFFICIAL_REGISTRY_API = "https://registry.modelcontextprotocol.io/v0/servers"
_REGISTRY_CACHE = MCP_CACHE_DIR / "mcp-official-registry.json"
_REGISTRY_TTL_SEC = 6 * 3600
_REGISTRY_MAX_PAGES = 40        # safety cap (~40 * 100 = 4000 servers)
_REGISTRY_PAGE_SIZE = 100

# ── Awesome MCP servers (wong2/awesome-mcp-servers) ─────────────────────────
_AWESOME_MCP_URL = "https://raw.githubusercontent.com/wong2/awesome-mcp-servers/main/README.md"
_AWESOME_CACHE = MCP_CACHE_DIR / "mcp-awesome.json"
_AWESOME_TTL_SEC = 12 * 3600


# ── Data classes ───────────────────────────────────────────────────────────

class MCPServerEntry:
    """A marketplace entry for an MCP server."""

    def __init__(
        self,
        name: str,
        description: str,
        source: str,          # "official", "dulus", "installed"
        command: str = "",
        args: list[str] | None = None,
        env: dict | None = None,
        url: str = "",
        transport: str = "stdio",
        requires_args: bool = False,
        arg_prompt: str = "",
        runtime: str = "",
        installed: bool = False,
        config_name: str = "",  # name in mcp.json if installed
        error: str = "",
        repo_url: str = "",     # source repo (for future auditing)
        security: dict | None = None,  # {score, tier, reasons} — filled by audit layer
    ):
        self.name = name
        self.description = description
        self.source = source
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.url = url
        self.transport = transport
        self.requires_args = requires_args
        self.arg_prompt = arg_prompt
        self.runtime = runtime
        self.installed = installed
        self.config_name = config_name or name
        self.error = error
        self.repo_url = repo_url
        self.security = security

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "url": self.url,
            "transport": self.transport,
            "requires_args": self.requires_args,
            "arg_prompt": self.arg_prompt,
            "runtime": self.runtime,
            "installed": self.installed,
            "config_name": self.config_name,
            "error": self.error,
            "repo_url": self.repo_url,
            "security": self.security,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MCPServerEntry":
        return cls(**{k: v for k, v in d.items() if hasattr(cls, "__init__")})

    def to_mcp_json_entry(self) -> dict:
        """Convert to the format used in .mcp.json mcpServers dict."""
        entry: dict = {"type": self.transport}
        if self.transport == "stdio":
            entry["command"] = self.command
            if self.args:
                entry["args"] = self.args
            if self.env:
                entry["env"] = self.env
        elif self.transport in ("sse", "http"):
            entry["url"] = self.url
        return entry


# ── Listing functions ──────────────────────────────────────────────────────

def list_official(query: Optional[str] = None) -> list[MCPServerEntry]:
    """Return curated official MCP servers from modelcontextprotocol/servers."""
    q = query.lower() if query else None
    results = []
    for name, info in _OFFICIAL_CURATED.items():
        if q and q not in name.lower() and q not in info["description"].lower():
            continue
        results.append(MCPServerEntry(
            name=name,
            description=info["description"],
            source="official",
            command=info.get("command", ""),
            args=info.get("args", []),
            env=info.get("env", {}),
            requires_args=info.get("requires_args", False),
            arg_prompt=info.get("arg_prompt", ""),
            runtime=info.get("runtime", ""),
        ))
    return results


def list_dulus_community(query: Optional[str] = None) -> list[MCPServerEntry]:
    """Return Dulus community MCP servers."""
    q = query.lower() if query else None
    results = []

    # Try to fetch from the community repo
    community = _fetch_dulus_community()
    entries = community if community else _DULUS_CURATED

    for name, info in entries.items():
        if q and q not in name.lower() and q not in info.get("description", "").lower():
            continue
        results.append(MCPServerEntry(
            name=name,
            description=info.get("description", ""),
            source="dulus",
            command=info.get("command", ""),
            args=info.get("args", []),
            env=info.get("env", {}),
            requires_args=info.get("requires_args", False),
            arg_prompt=info.get("arg_prompt", ""),
            runtime=info.get("runtime", ""),
        ))
    return results


def _fetch_dulus_community() -> Optional[dict]:
    """Fetch community MCP catalog from kevrojo/dulus-mcp repo."""
    # Check cache first
    if _DULUS_MCP_CACHE.exists():
        try:
            data = json.loads(_DULUS_MCP_CACHE.read_text(encoding="utf-8"))
            if time.time() - float(data.get("fetched_at", 0)) < _DULUS_MCP_TTL_SEC:
                return data.get("servers", {})
        except Exception:
            pass

    # Fetch from GitHub
    url = f"https://raw.githubusercontent.com/{_DULUS_MCP_REPO}/{_DULUS_MCP_BRANCH}/servers.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        servers = data.get("servers", {})
        # Cache it
        MCP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _DULUS_MCP_CACHE.write_text(
            json.dumps({"fetched_at": time.time(), "servers": servers}, indent=2),
            encoding="utf-8",
        )
        return servers
    except Exception:
        return None


def _http_get(url: str, timeout: int = 12) -> Optional[bytes]:
    """GET a URL with a browser-ish UA; return bytes or None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "Dulus-MCP-Hub/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _map_registry_server(srv: dict) -> Optional[dict]:
    """Map one registry `server` object to our flat catalog dict.

    Handles both package-based (npm/pypi → stdio) and remote (http/sse) servers.
    Returns None if the entry can't be turned into something installable.
    """
    name = srv.get("name", "")
    if not name:
        return None
    desc = srv.get("description", "") or ""
    repo = ""
    repo_obj = srv.get("repository") or {}
    if isinstance(repo_obj, dict):
        repo = repo_obj.get("url", "") or ""

    # 1) Prefer a concrete package (stdio launch)
    packages = srv.get("packages") or []
    for pkg in packages:
        reg = (pkg.get("registryType") or pkg.get("registry_name") or "").lower()
        ident = pkg.get("identifier") or pkg.get("name") or ""
        if not ident:
            continue
        if reg in ("npm", "node"):
            return {
                "name": name, "description": desc, "repo_url": repo,
                "command": "npx", "args": ["-y", ident],
                "transport": "stdio", "runtime": "node",
            }
        if reg in ("pypi", "python"):
            return {
                "name": name, "description": desc, "repo_url": repo,
                "command": "uvx", "args": [ident],
                "transport": "stdio", "runtime": "python",
            }
        if reg in ("oci", "docker"):
            return {
                "name": name, "description": desc, "repo_url": repo,
                "command": "docker", "args": ["run", "-i", "--rm", ident],
                "transport": "stdio", "runtime": "docker",
            }

    # 2) Fall back to a remote endpoint (http/sse — no local runtime needed)
    remotes = srv.get("remotes") or []
    for rem in remotes:
        rtype = (rem.get("type") or "").lower()
        url = rem.get("url") or ""
        if not url:
            continue
        transport = "sse" if "sse" in rtype else "http"
        return {
            "name": name, "description": desc, "repo_url": repo,
            "url": url, "transport": transport, "runtime": "remote",
        }
    return None


def _fetch_official_registry(force: bool = False) -> list[dict]:
    """Fetch (and cache) the full curated server list from the official registry."""
    # Cache first
    if not force and _REGISTRY_CACHE.exists():
        try:
            data = json.loads(_REGISTRY_CACHE.read_text(encoding="utf-8"))
            if time.time() - float(data.get("fetched_at", 0)) < _REGISTRY_TTL_SEC:
                return data.get("servers", [])
        except Exception:
            pass

    servers: list[dict] = []
    seen: set[str] = set()
    cursor = ""
    for _ in range(_REGISTRY_MAX_PAGES):
        url = f"{_OFFICIAL_REGISTRY_API}?limit={_REGISTRY_PAGE_SIZE}"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"
        raw = _http_get(url)
        if not raw:
            break
        try:
            payload = json.loads(raw)
        except Exception:
            break
        for item in payload.get("servers", []):
            srv = item.get("server", item)
            meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
            # Only keep the latest active version of each server
            if meta and meta.get("isLatest") is False:
                continue
            mapped = _map_registry_server(srv)
            if mapped and mapped["name"] not in seen:
                seen.add(mapped["name"])
                servers.append(mapped)
        cursor = payload.get("metadata", {}).get("nextCursor", "")
        if not cursor:
            break

    if servers:
        MCP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _REGISTRY_CACHE.write_text(
            json.dumps({"fetched_at": time.time(), "servers": servers}),
            encoding="utf-8",
        )
    return servers


def list_registry(query: Optional[str] = None) -> list[MCPServerEntry]:
    """Return MCP servers from the official metaregistry (thousands, cached)."""
    q = query.lower() if query else None
    results = []
    for info in _fetch_official_registry():
        if q and q not in info["name"].lower() and q not in info.get("description", "").lower():
            continue
        results.append(MCPServerEntry(
            name=info["name"],
            description=info.get("description", ""),
            source="registry",
            command=info.get("command", ""),
            args=info.get("args", []),
            url=info.get("url", ""),
            transport=info.get("transport", "stdio"),
            runtime=info.get("runtime", ""),
            repo_url=info.get("repo_url", ""),
        ))
    return results


def _infer_mcp_entry(name: str, repo_url: str = "", description: str = "") -> dict:
    """Infer executable launcher, arguments, transport, and runtime for an MCP server.

    Resolves curated names, official repository subpackages, npm packages,
    PyPI packages, remote SSE/HTTP URLs, explicit launcher snippets in descriptions,
    and GitHub repo language indicators.
    """
    name_clean = (name or "").strip()
    target = name_clean.lower()
    desc = (description or "").strip()
    url = (repo_url or "").strip()

    # 1. Direct curated match
    if target in _OFFICIAL_CURATED:
        info = dict(_OFFICIAL_CURATED[target])
        info.setdefault("name", name_clean)
        info.setdefault("source", "official")
        return info
    if target in _DULUS_CURATED:
        info = dict(_DULUS_CURATED[target])
        info.setdefault("name", name_clean)
        info.setdefault("source", "dulus")
        return info

    import re as _re

    # 2. Check official repo subtrees: modelcontextprotocol/servers/.../src/<tool>
    if "modelcontextprotocol/servers" in url:
        m = _re.search(r"/src/([a-zA-Z0-9_\-]+)", url)
        if m:
            sub = m.group(1).lower()
            if sub in _OFFICIAL_CURATED:
                info = dict(_OFFICIAL_CURATED[sub])
                info["name"] = name_clean
                return info
            if sub in ("fetch", "git", "time", "sqlite", "gdrive"):
                return {
                    "name": name_clean, "description": desc, "repo_url": url,
                    "command": "uvx", "args": [f"mcp-server-{sub}"],
                    "transport": "stdio", "runtime": "python",
                }
            pkg_name = f"@modelcontextprotocol/server-{sub}" if sub != "sequentialthinking" else "@modelcontextprotocol/server-sequential-thinking"
            return {
                "name": name_clean, "description": desc, "repo_url": url,
                "command": "npx", "args": ["-y", pkg_name],
                "transport": "stdio", "runtime": "node",
            }

    # 3. Direct npmjs / pypi package links
    if "npmjs.com/package/" in url:
        pkg = url.split("npmjs.com/package/")[-1].strip().split("?")[0].strip("/")
        if pkg:
            return {
                "name": name_clean, "description": desc, "repo_url": url,
                "command": "npx", "args": ["-y", pkg],
                "transport": "stdio", "runtime": "node",
            }
    if "pypi.org/project/" in url:
        pkg = url.split("pypi.org/project/")[-1].strip().split("?")[0].strip("/")
        if pkg:
            return {
                "name": name_clean, "description": desc, "repo_url": url,
                "command": "uvx", "args": [pkg],
                "transport": "stdio", "runtime": "python",
            }

    # 4. Remote HTTP/SSE server URLs found in description or url (excluding repo hosts)
    if not any(h in url for h in ("github.com", "gitlab.com", "npmjs.com", "pypi.org")):
        if _re.search(r"https?://[^\s\)\"\'\`]+/(?:mcp|sse)(?:[/?#\s]|$)", url):
            transport = "sse" if "/sse" in url else "http"
            return {
                "name": name_clean, "description": desc, "repo_url": url,
                "url": url, "transport": transport, "runtime": "remote",
            }

    remote_desc = _re.search(r"https?://[^\s\)\"\'\`]+/(?:mcp|sse)(?:[/?#\s]|$)[^\s\)\"\'\`]*", desc)
    if remote_desc and not any(h in remote_desc.group(0) for h in ("github.com", "gitlab.com", "npmjs.com", "pypi.org")):
        rem_url = remote_desc.group(0).rstrip(".,;")
        transport = "sse" if "/sse" in rem_url else "http"
        return {
            "name": name_clean, "description": desc, "repo_url": url,
            "url": rem_url, "transport": transport, "runtime": "remote",
        }

    # 5. Extract command from description text (e.g., `npx -y ...`, `uvx ...`, `docker run ...`)
    npx_m = _re.search(r"(?:npx\s+(?:-y\s+)?)(@?[a-zA-Z0-9_\-\.\/]+)", desc)
    if npx_m:
        pkg = npx_m.group(1).strip()
        return {
            "name": name_clean, "description": desc, "repo_url": url,
            "command": "npx", "args": ["-y", pkg],
            "transport": "stdio", "runtime": "node",
        }
    uvx_m = _re.search(r"(?:uvx\s+|pip\s+install\s+)([a-zA-Z0-9_\-]+)", desc)
    if uvx_m:
        pkg = uvx_m.group(1).strip()
        return {
            "name": name_clean, "description": desc, "repo_url": url,
            "command": "uvx", "args": [pkg],
            "transport": "stdio", "runtime": "python",
        }

    # 6. GitHub repo inference: https://github.com/<owner>/<repo>
    gh_m = _re.search(r"github\.com/([^/]+)/([^/#\?]+)", url)
    if gh_m:
        owner, repo = gh_m.group(1), gh_m.group(2).rstrip(".git")
        repo_lower = repo.lower()
        desc_lower = desc.lower()

        is_python = any(k in desc_lower for k in ("python", "pip", "uv", "fastmcp", "pypi", "django", "flask", "pytorch")) or repo_lower.startswith("py-") or repo_lower.startswith("python-")
        is_node = any(k in desc_lower for k in ("node", "npm", "npx", "typescript", "javascript", "react", "nextjs")) or repo_lower.startswith("ts-") or repo_lower.startswith("js-")

        if is_python:
            return {
                "name": name_clean, "description": desc, "repo_url": url,
                "command": "uvx", "args": [repo],
                "transport": "stdio", "runtime": "python",
            }
        else:
            return {
                "name": name_clean, "description": desc, "repo_url": url,
                "command": "npx", "args": ["-y", repo],
                "transport": "stdio", "runtime": "node",
            }

    return {
        "name": name_clean, "description": desc, "repo_url": url,
        "command": "", "args": [], "transport": "stdio", "runtime": "",
    }


def _fetch_awesome_mcp(force: bool = False) -> list[dict]:
    """Parse the wong2/awesome-mcp-servers README into a flat catalog."""
    if not force and _AWESOME_CACHE.exists():
        try:
            data = json.loads(_AWESOME_CACHE.read_text(encoding="utf-8"))
            if time.time() - float(data.get("fetched_at", 0)) < _AWESOME_TTL_SEC:
                return data.get("servers", [])
        except Exception:
            pass

    raw = _http_get(_AWESOME_MCP_URL, timeout=15)
    if not raw:
        return []
    text = raw.decode("utf-8", errors="replace")

    import re as _re
    # Lines like:  - **[Name](url)** - description
    pattern = _re.compile(r"^\s*[-*]\s*\*\*\[([^\]]+)\]\(([^)]+)\)\*\*\s*[-–—]\s*(.+)$")
    servers: list[dict] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = pattern.match(line)
        if not m:
            continue
        name, url, desc = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        
        inferred = _infer_mcp_entry(name, url, desc)
        servers.append({
            "name": name,
            "description": desc,
            "repo_url": url,
            "command": inferred.get("command", ""),
            "args": list(inferred.get("args") or []),
            "env": dict(inferred.get("env") or {}),
            "url": inferred.get("url", ""),
            "transport": inferred.get("transport", "stdio"),
            "runtime": inferred.get("runtime", ""),
            "requires_args": bool(inferred.get("requires_args", False)),
            "arg_prompt": str(inferred.get("arg_prompt") or ""),
        })

    if servers:
        MCP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _AWESOME_CACHE.write_text(
            json.dumps({"fetched_at": time.time(), "servers": servers}),
            encoding="utf-8",
        )
    return servers


def list_awesome(query: Optional[str] = None) -> list[MCPServerEntry]:
    """Return MCP servers curated in the awesome-mcp-servers list."""
    q = query.lower() if query else None
    results = []
    for info in _fetch_awesome_mcp():
        if q and q not in info["name"].lower() and q not in info.get("description", "").lower():
            continue
        results.append(MCPServerEntry(
            name=info["name"],
            description=info.get("description", ""),
            source="awesome",
            command=info.get("command", ""),
            args=list(info.get("args") or []),
            env=dict(info.get("env") or {}),
            url=info.get("url", ""),
            transport=info.get("transport", "stdio"),
            runtime=info.get("runtime", ""),
            requires_args=bool(info.get("requires_args", False)),
            arg_prompt=info.get("arg_prompt", ""),
            repo_url=info.get("repo_url", ""),
        ))
    return results


def list_installed(query: Optional[str] = None) -> list[MCPServerEntry]:
    """Return MCP servers already configured in ~/.dulus/mcp.json."""
    configs = load_mcp_configs()
    q = query.lower() if query else None
    results = []

    for name, cfg in configs.items():
        if q and q not in name.lower():
            continue
        entry = MCPServerEntry(
            name=name,
            description=f"Configured MCP server ({cfg.transport.value})",
            source="installed",
            command=cfg.command,
            args=list(cfg.args),
            env=dict(cfg.env),
            url=cfg.url,
            transport=cfg.transport.value,
            installed=True,
            config_name=name,
        )
        results.append(entry)
    return results


def list_all(query: Optional[str] = None, sources: Optional[list[str]] = None) -> list[MCPServerEntry]:
    """Return all MCP servers across every source, deduped by name.

    Order (first wins on dedup): installed → curated official → community →
    official registry → awesome list.

    Args:
        query: optional case-insensitive filter on name/description.
        sources: optional subset of {"curated","community","registry","awesome"}.
                 None = all sources.
    """
    active = set(sources) if sources else {"curated", "community", "registry", "awesome"}
    installed_names = {e.config_name for e in list_installed()}
    results: dict[str, MCPServerEntry] = {}

    # Installed always shown first (marked)
    for entry in list_installed(query):
        entry.installed = True
        results[entry.name] = entry

    # Curated official (hand-picked, best UX with args/env prompts)
    if "curated" in active:
        for entry in list_official(query):
            if entry.name not in results:
                entry.installed = entry.name in installed_names
                results[entry.name] = entry

    # Dulus community
    if "community" in active:
        for entry in list_dulus_community(query):
            if entry.name not in results:
                entry.installed = entry.name in installed_names
                results[entry.name] = entry

    # Official metaregistry (thousands — offline-safe, cached)
    if "registry" in active:
        try:
            for entry in list_registry(query):
                if entry.name not in results:
                    entry.installed = entry.name in installed_names
                    results[entry.name] = entry
        except Exception:
            pass

    # Awesome curated list
    if "awesome" in active:
        try:
            for entry in list_awesome(query):
                if entry.name not in results:
                    entry.installed = entry.name in installed_names
                    results[entry.name] = entry
        except Exception:
            pass

    return list(results.values())


def catalog_page(
    query: Optional[str] = None,
    source: str = "all",
    page: int = 1,
    page_size: int = 30,
) -> dict:
    """Return a paginated view of the complete MCP catalog for the GUI."""
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 30), 1), 100)
    requested_source = str(source or "all").strip().lower()

    # ── ALGOLIA-FIRST (2026-08-09): índice propio dulus_mcps ───────────────
    # ~1ms vs el crawl en vivo del registry (40 páginas × 100, 10s+ → el tab
    # MCP de la GUI se quedaba colgado). Mismo shape de salida. Si Algolia
    # falla por lo que sea → cae al path live original (abajo).
    if requested_source in {"all", "registry", "awesome"}:
        try:
            from algolia_search import INDEX_MCPS, algolia_enabled, search_index

            if algolia_enabled():
                filters = {
                    "registry": "source:official-registry",
                    "awesome": "source:awesome-mcp",
                }.get(requested_source)
                res = search_index(
                    INDEX_MCPS, str(query or "").strip(),
                    page=page - 1, hits_per_page=page_size,
                    filters=filters, facets=["source"],
                )
                if res is not None:
                    src_map = {
                        "official": "official",
                        "dulus": "community",
                        "official-registry": "registry",
                        "awesome-mcp": "awesome",
                        "composio": "registry",
                    }
                    q = str(query or "").strip().lower()
                    installed_entries = list_installed()
                    installed_names = {e.name.lower() for e in installed_entries}
                    items = []
                    for hit in res["hits"]:
                        name = str(hit.get("name") or "").strip()
                        if not name:
                            continue
                        items.append({
                            "name": name,
                            "description": str(hit.get("description") or ""),
                            "source": src_map.get(str(hit.get("source") or ""), "registry"),
                            "command": str(hit.get("command") or ""),
                            "args": list(hit.get("args") or []),
                            "env": dict(hit.get("env") or {}),
                            "url": str(hit.get("url") or ""),
                            "transport": str(hit.get("transport") or "stdio"),
                            "requires_args": bool(hit.get("requires_args", False)),
                            "arg_prompt": str(hit.get("arg_prompt") or ""),
                            "runtime": str(hit.get("runtime") or ""),
                            "installed": name.lower() in installed_names,
                            "config_name": name,
                            "error": "",
                            "repo_url": str(hit.get("repo_url") or ""),
                            "security": None,
                        })

                    # ── Enrich Algolia hits with real launchers from local catalogs
                    # Algolia only indexes name/description/repo_url for many servers,
                    # so the GUI receives empty commands and Install does nothing.
                    # Overlay curated + cached registry entries so the button works.
                    _official_lookup = {n.lower(): i for n, i in _OFFICIAL_CURATED.items()}
                    _dulus_lookup = {n.lower(): i for n, i in _DULUS_CURATED.items()}
                    # Only read the already-cached registry; do NOT trigger a
                    # network crawl here or the GUI tab will hang/time out.
                    _registry_lookup: dict[str, dict] = {}
                    try:
                        if _REGISTRY_CACHE.exists():
                            data = json.loads(_REGISTRY_CACHE.read_text(encoding="utf-8"))
                            if time.time() - float(data.get("fetched_at", 0)) < _REGISTRY_TTL_SEC:
                                for info in data.get("servers", []):
                                    key = str(info.get("name") or "").strip().lower()
                                    if key:
                                        _registry_lookup[key] = info
                    except Exception:
                        pass
                    for item in items:
                        name_lower = item["name"].lower()
                        info = _official_lookup.get(name_lower) or _dulus_lookup.get(name_lower) or _registry_lookup.get(name_lower)
                        if info:
                            item["repo_url"] = info.get("repo_url", item["repo_url"])
                            if info.get("command") or info.get("url"):
                                item["command"] = info.get("command", "")
                                item["args"] = info.get("args") if info.get("args") is not None else []
                                item["env"] = info.get("env") if info.get("env") is not None else {}
                                item["url"] = info.get("url", "")
                                item["transport"] = info.get("transport", item["transport"])
                                item["runtime"] = info.get("runtime", item["runtime"])
                                item["requires_args"] = bool(info.get("requires_args", False))
                                item["arg_prompt"] = info.get("arg_prompt", "")
                        if not item.get("command") and not item.get("url"):
                            inferred = _infer_mcp_entry(item["name"], item.get("repo_url", ""), item.get("description", ""))
                            if inferred.get("command") or inferred.get("url"):
                                item["command"] = inferred.get("command", "")
                                item["args"] = list(inferred.get("args") or [])
                                item["env"] = dict(inferred.get("env") or {})
                                item["url"] = inferred.get("url", "")
                                item["transport"] = inferred.get("transport", item.get("transport", "stdio"))
                                item["runtime"] = inferred.get("runtime", item.get("runtime", ""))
                                item["requires_args"] = bool(inferred.get("requires_args", False))
                                item["arg_prompt"] = str(inferred.get("arg_prompt") or "")

                    facets = (res.get("facets") or {}).get("source", {})
                    registry_n = int(facets.get("official-registry", 0)) + int(facets.get("composio", 0))
                    awesome_n = int(facets.get("awesome-mcp", 0))
                    official_n = len(list_official(query))
                    community_n = sum(
                        1 for n, info in _DULUS_CURATED.items()
                        if not q or q in n.lower() or q in str(info.get("description", "")).lower()
                    )
                    installed_n = sum(
                        1 for e in installed_entries
                        if not q or q in e.name.lower() or q in (e.description or "").lower()
                    )
                    return {
                        "items": items,
                        "total": int(res["total"]),
                        "catalog_total": registry_n + awesome_n,
                        "page": page,
                        "page_size": page_size,
                        "pages": max(int(res["pages"]), 1),
                        "has_more": bool(res["has_more"]),
                        "source": requested_source,
                        "source_counts": {
                            "all": registry_n + awesome_n,
                            "official": official_n,
                            "registry": registry_n,
                            "awesome": awesome_n,
                            "community": community_n,
                            "installed": installed_n,
                        },
                    }
        except Exception as exc:
            # fallback live abajo. Silencioso por diseño, pero deja rastro con
            # DULUS_DEBUG=1: un ImportError aquí en un binario congelado
            # significa que algolia_search no se compiló.
            import os as _os
            import sys as _sys
            if _os.environ.get("DULUS_DEBUG"):
                print(f"[mcp.hub] algolia path unavailable: {type(exc).__name__}: {exc}",
                      file=_sys.stderr)

    all_entries = list_all()
    if query and str(query).strip():
        needle = str(query).strip().lower()
        entries = [
            entry
            for entry in all_entries
            if needle in entry.name.lower()
            or needle in (entry.description or "").lower()
        ]
    else:
        entries = all_entries
    source_counts = {
        "all": len(entries),
        "official": 0,
        "registry": 0,
        "awesome": 0,
        "community": 0,
        "installed": 0,
    }
    for entry in entries:
        if entry.installed:
            source_counts["installed"] += 1
        if entry.source == "official":
            source_counts["official"] += 1
        elif entry.source == "registry":
            source_counts["registry"] += 1
        elif entry.source == "awesome":
            source_counts["awesome"] += 1
        elif entry.source == "dulus":
            source_counts["community"] += 1

    if requested_source == "installed":
        filtered = [entry for entry in entries if entry.installed]
    elif requested_source == "community":
        filtered = [entry for entry in entries if entry.source == "dulus"]
    elif requested_source in {"official", "registry", "awesome"}:
        filtered = [entry for entry in entries if entry.source == requested_source]
    else:
        requested_source = "all"
        filtered = entries

    total = len(filtered)
    pages = max((total + page_size - 1) // page_size, 1)
    page = min(page, pages)
    start = (page - 1) * page_size
    return {
        "items": [
            entry.to_dict()
            for entry in filtered[start:start + page_size]
        ],
        "total": total,
        "catalog_total": len(all_entries),
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "has_more": page < pages,
        "source": requested_source,
        "source_counts": source_counts,
    }


def search(query: str) -> list[MCPServerEntry]:
    """Search across all sources for MCP servers matching query.

    Algolia-first: hit our hosted dulus_mcps index (~3k servers, ~1ms,
    typo-tolerant) before the live registry/awesome crawl, which walks
    thousands of entries and can take 10s+. Same MCPServerEntry shape; any
    Algolia miss or failure falls through to the full live list_all() below.
    Kill-switch: DULUS_ALGOLIA=0.
    """
    try:
        from algolia_search import INDEX_MCPS, algolia_enabled, search_index

        if algolia_enabled():
            res = search_index(
                INDEX_MCPS, str(query or "").strip(),
                page=0, hits_per_page=50,
            )
            if res is not None and res.get("hits"):
                installed_names = {e.config_name.lower() for e in list_installed()}
                src_map = {
                    "official-registry": "registry",
                    "awesome-mcp": "awesome",
                    "composio": "registry",
                }
                out: list[MCPServerEntry] = []
                for hit in res["hits"]:
                    name = str(hit.get("name") or "").strip()
                    if not name:
                        continue
                    inferred = _infer_mcp_entry(name, str(hit.get("repo_url") or hit.get("url") or ""), str(hit.get("description") or ""))
                    cmd = str(hit.get("command") or inferred.get("command") or "")
                    u = str(hit.get("url") or inferred.get("url") or "")
                    tr = str(hit.get("transport") or inferred.get("transport") or "stdio")
                    args = list(hit.get("args") or inferred.get("args") or [])
                    env = dict(hit.get("env") or inferred.get("env") or {})
                    rt = str(hit.get("runtime") or inferred.get("runtime") or "")
                    req_args = bool(hit.get("requires_args", inferred.get("requires_args", False)))
                    arg_p = str(hit.get("arg_prompt") or inferred.get("arg_prompt") or "")
                    out.append(MCPServerEntry(
                        name=name,
                        description=str(hit.get("description") or inferred.get("description") or ""),
                        source=src_map.get(str(hit.get("source") or ""), "registry"),
                        command=cmd,
                        args=args,
                        env=env,
                        url=u,
                        transport=tr,
                        requires_args=req_args,
                        arg_prompt=arg_p,
                        runtime=rt,
                        installed=name.lower() in installed_names,
                        config_name=name,
                        repo_url=str(hit.get("repo_url") or inferred.get("repo_url") or ""),
                    ))
                if out:
                    return out
    except Exception:
        pass  # fall back to the live crawl
    return list_all(query)


# ── Get single server ──────────────────────────────────────────────────────

def get_server(name: str) -> Optional[MCPServerEntry]:
    """Find an MCP server by name across all sources.

    Case-insensitive: catalog names are lowercase by convention (e.g. "make",
    "github"), but a server the GUI or a prior install wrote to mcp.json may
    be stored with a different case (e.g. "Make", "GitHub" — whatever the
    user/GUI passed at install time). Without this, `/mcp install MAKE` or
    a lookup with any case mismatch silently returned "not found" even
    though the exact same server (just different case) exists.
    """
    target = name.strip().lower()
    for entry in list_all():
        if entry.name.lower() == target or entry.config_name.lower() == target:
            return entry
    return None


# ── Install / Uninstall ────────────────────────────────────────────────────

def _resolve_installable(name: str) -> Optional[MCPServerEntry]:
    """Resolve an installable entry for ``name`` across every catalog source.

    1. Fast path: check _OFFICIAL_CURATED and _DULUS_CURATED directly (0ms).
    2. Local catalog (merged in-process catalog).
    3. Algolia lookup (if enabled) for fresh launcher properties.
    4. Official registry live by exact name.
    """
    target = (name or "").strip().lower()
    if not target:
        return None

    # Instant curated fast-path
    if target in _OFFICIAL_CURATED:
        info = _OFFICIAL_CURATED[target]
        return MCPServerEntry(
            name=target,
            description=info.get("description", ""),
            source="official",
            command=info.get("command", ""),
            args=list(info.get("args") or []),
            env=dict(info.get("env") or {}),
            url=info.get("url", ""),
            transport=info.get("transport", "stdio"),
            requires_args=bool(info.get("requires_args", False)),
            arg_prompt=info.get("arg_prompt", ""),
            runtime=info.get("runtime", ""),
            repo_url=info.get("repo_url", ""),
        )
    if target in _DULUS_CURATED:
        info = _DULUS_CURATED[target]
        return MCPServerEntry(
            name=target,
            description=info.get("description", ""),
            source="dulus",
            command=info.get("command", ""),
            args=list(info.get("args") or []),
            env=dict(info.get("env") or {}),
            url=info.get("url", ""),
            transport=info.get("transport", "stdio"),
            requires_args=bool(info.get("requires_args", False)),
            arg_prompt=info.get("arg_prompt", ""),
            runtime=info.get("runtime", ""),
            repo_url=info.get("repo_url", ""),
        )

    entry = get_server(name)
    if entry is not None and (entry.transport != "stdio" or (entry.command or "").strip()):
        return entry

    # Algolia fallback
    if entry is None or (entry.transport == "stdio" and not (entry.command or "").strip()):
        try:
            from algolia_search import INDEX_MCPS, algolia_enabled, search_index
            if algolia_enabled():
                alg_res = search_index(INDEX_MCPS, name, hits_per_page=5)
                if alg_res and alg_res.get("hits"):
                    for hit in alg_res["hits"]:
                        h_name = str(hit.get("name") or "").strip().lower()
                        if h_name == target:
                            cmd = str(hit.get("command") or "")
                            u = str(hit.get("url") or "")
                            tr = str(hit.get("transport") or "stdio")
                            if tr != "stdio" or cmd.strip():
                                return MCPServerEntry(
                                    name=str(hit.get("name") or target),
                                    description=str(hit.get("description") or ""),
                                    source=str(hit.get("source") or "registry"),
                                    command=cmd,
                                    args=list(hit.get("args") or []),
                                    env=dict(hit.get("env") or {}),
                                    url=u,
                                    transport=tr,
                                    requires_args=bool(hit.get("requires_args", False)),
                                    arg_prompt=str(hit.get("arg_prompt") or ""),
                                    runtime=str(hit.get("runtime") or ""),
                                    repo_url=str(hit.get("repo_url") or ""),
                                )
        except Exception:
            pass

    # Official registry live by exact name
    try:
        for candidate in list_registry(query=name):
            if candidate.name.lower() == target or candidate.config_name.lower() == target:
                if candidate.transport != "stdio" or (candidate.command or "").strip():
                    return candidate
    except Exception:
        pass
    if entry is None or (entry.transport == "stdio" and not (entry.command or "").strip()):
        try:
            for info in _fetch_official_registry():
                if str(info.get("name") or "").strip().lower() == target:
                    mapped = _map_registry_server(info)
                    if mapped:
                        candidate = MCPServerEntry(**mapped)
                        if candidate.transport != "stdio" or (candidate.command or "").strip():
                            return candidate
        except Exception:
            pass

    # Inferred fallback for awesome / community / generic servers
    if entry is not None and (entry.transport == "stdio" and not (entry.command or "").strip()):
        inferred = _infer_mcp_entry(entry.name, entry.repo_url, entry.description)
        if inferred.get("command") or inferred.get("url"):
            entry.command = inferred.get("command", "")
            entry.args = list(inferred.get("args") or [])
            entry.env = dict(inferred.get("env") or {})
            entry.url = inferred.get("url", "")
            entry.transport = inferred.get("transport", entry.transport)
            entry.runtime = inferred.get("runtime", entry.runtime)
            entry.requires_args = bool(inferred.get("requires_args", False))
            entry.arg_prompt = str(inferred.get("arg_prompt") or "")
            return entry
    elif entry is None:
        inferred = _infer_mcp_entry(name, "", "")
        if inferred.get("command") or inferred.get("url"):
            return MCPServerEntry(
                name=name,
                description=inferred.get("description", ""),
                source="inferred",
                command=inferred.get("command", ""),
                args=list(inferred.get("args") or []),
                env=dict(inferred.get("env") or {}),
                url=inferred.get("url", ""),
                transport=inferred.get("transport", "stdio"),
                requires_args=bool(inferred.get("requires_args", False)),
                arg_prompt=str(inferred.get("arg_prompt") or ""),
                runtime=inferred.get("runtime", ""),
                repo_url=inferred.get("repo_url", ""),
            )

    return entry


def install(name: str, user_args: Optional[list[str]] = None, env_overrides: Optional[dict] = None) -> tuple[bool, str]:
    """0-friction install an MCP server.

    Args:
        name: Server name (e.g. "filesystem", "github")
        user_args: Optional user-provided args (e.g. ["/home/user/projects"])
        env_overrides: Optional env vars to set (e.g. {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx"})

    Returns:
        (success, message)
    """
    entry = _resolve_installable(name)
    if entry is None:
        return False, f"MCP server '{name}' not found. Run '/mcp list' to see available servers."

    if entry.installed:
        return False, f"MCP server '{name}' is already installed. Run '/mcp remove {name}' to reinstall."

    # ── Guard: reject entries with no real launcher/endpoint ────────────────
    # Some catalog sources (e.g. "awesome" — scraped from a GitHub README)
    # only carry name/description/repo_url, never a real command or URL.
    # Without this guard those entries sail through and get written to
    # mcp.json with command="" (transport="stdio" default), which then
    # blows up at connect time with "has no command configured". Reject
    # them here instead, with a message pointing at the repo for manual setup.
    if entry.transport == "stdio" and not (entry.command or "").strip():
        msg = (
            f"'{name}' has no installable command/package known to Dulus "
            f"(catalog source: {entry.source})."
        )
        if entry.repo_url:
            msg += f" Check {entry.repo_url} for manual setup instructions, then use '/mcp add' with the real command."
        return False, msg
    if entry.transport in ("sse", "http") and not (entry.url or "").strip():
        msg = f"'{name}' has no endpoint URL known to Dulus (catalog source: {entry.source})."
        if entry.repo_url:
            msg += f" Check {entry.repo_url} for the correct URL."
        return False, msg

    # Check runtime availability (validates the exact launcher command too,
    # not just a loose runtime category — see _check_runtime docstring)
    runtime_ok, runtime_msg = _check_runtime(entry.runtime, entry.command)
    if not runtime_ok:
        return False, f"Cannot install '{name}': {runtime_msg}"

    # Build the config entry
    config_entry = entry.to_mcp_json_entry()

    # Apply user args if the server requires them
    if entry.requires_args and user_args:
        # Datadog remote MCP server: the argument is the Datadog site (e.g.
        # app.datadoghq.com, us3.datadoghq.com, app.datadoghq.eu). Rewrite the
        # URL to hit the regional endpoint.
        if entry.name == "datadog":
            site = (user_args[0] or "").strip().lower()
            if not site or "." not in site:
                return False, f"Invalid Datadog site: '{site}'. Expected something like app.datadoghq.com or us3.datadoghq.com."
            config_entry["url"] = f"https://mcp.{site}/api/unstable/mcp-server/mcp"
        # For filesystem server, args are appended
        elif entry.name == "filesystem":
            config_entry["args"] = entry.args + list(user_args)
        # For postgres, the DB URL replaces or is appended
        elif entry.name == "postgres":
            config_entry["args"] = entry.args + list(user_args)
        elif entry.name == "sqlite":
            config_entry["args"] = entry.args + list(user_args)

    # Apply env overrides
    if env_overrides:
        config_entry.setdefault("env", {})
        config_entry["env"].update(env_overrides)

    # Save to user config
    try:
        add_server_to_user_config(entry.config_name, config_entry)
    except Exception as e:
        return False, f"Failed to save config for '{name}': {e}"

    # Test connection
    from .client import MCPClient
    cfg = MCPServerConfig.from_dict(entry.config_name, config_entry)
    client = MCPClient(cfg)
    try:
        client.connect()
        client.list_tools()
        tool_count = len(client._tools)
        client.disconnect()
        return True, f"Installed '{name}' with {tool_count} tool(s). Ready to use!"
    except Exception as e:
        # Server installed but connection failed — still report as installed
        return True, f"Installed '{name}' but connection test failed: {e}. The server config is saved — check your credentials or runtime."


def uninstall(name: str) -> tuple[bool, str]:
    """Remove an installed MCP server."""
    configs = load_mcp_configs()
    if name not in configs:
        # Try fuzzy match
        for cfg_name in configs:
            if cfg_name.lower() == name.lower():
                name = cfg_name
                break
        else:
            return False, f"MCP server '{name}' is not installed."

    try:
        remove_server_from_user_config(name)
        return True, f"Uninstalled '{name}'."
    except Exception as e:
        return False, f"Failed to uninstall '{name}': {e}"


def get_status(name: str, connect_if_missing: bool = False) -> dict:
    """Get connection status of an installed MCP server.

    IMPORTANT: this reads the state of the ALREADY-LIVE connection held by the
    shared MCPManager singleton (the same one `dulus_mcp.tools.initialize_mcp()`
    populates on startup / after install). It does NOT spin up a brand new
    MCPClient + subprocess on every call.

    Why this matters: the GUI polls this every 5s for every installed server
    (see MCPView.tsx). The old implementation created a fresh MCPClient and
    called connect()/disconnect() on EVERY poll tick, for EVERY server — which
    meant N fresh `npx`/`uvx` subprocesses spawned every 5 seconds. On Windows
    those processes fight over the same npm/npx cache lock, causing cascading
    "the parameter is incorrect" errors and timeouts as soon as you had more
    than a couple servers installed. Reading the manager's live state is O(1)
    and touches zero subprocesses.

    Args:
        connect_if_missing: if True and the server isn't registered/connected
            yet in the manager, do a one-off connect (used by explicit
            "check status now" actions, NOT by the polling loop).
    """
    from .client import get_mcp_manager, MCPClient, MCPServerState

    configs = load_mcp_configs()
    if name not in configs:
        # Case-insensitive fallback — same reasoning as get_server(): a server
        # may be stored in mcp.json under a different case than what's passed
        # in here (GUI polling, user typing, etc.), and without this a status
        # check on e.g. "MAKE" would falsely report "not_configured" even
        # though "Make" is installed and connected.
        resolved = next((c for c in configs if c.lower() == name.lower()), None)
        if resolved is None:
            return {"name": name, "state": "not_configured", "tools": 0, "error": "Not installed"}
        name = resolved

    mgr = get_mcp_manager()
    client = next((c for c in mgr.list_servers() if c.config.name == name), None)

    if client is None:
        # Not yet registered with the manager (e.g. installed via GUI while a
        # long-lived initialize_mcp() run in a different process/session).
        if not connect_if_missing:
            return {"name": name, "state": "not_configured", "tools": 0, "error": ""}
        cfg = configs[name]
        mgr.add_server(cfg)
        client = next(c for c in mgr.list_servers() if c.config.name == name)

    if client.state == MCPServerState.CONNECTED and client.alive:
        return {
            "name": name,
            "state": "connected",
            "tools": len(client._tools),
            "error": "",
            "description": client._server_info.get("name", ""),
            "version": client._server_info.get("version", ""),
        }

    if client.state == MCPServerState.ERROR:
        return {"name": name, "state": "error", "tools": 0, "error": client._error}

    if not connect_if_missing:
        # Don't reconnect on a passive status read — just report current state.
        return {"name": name, "state": client.state.value, "tools": 0, "error": ""}

    # Explicit one-off connect requested (not part of the polling path).
    try:
        client.connect()
        tools = client.list_tools()
        return {
            "name": name,
            "state": "connected",
            "tools": len(tools),
            "error": "",
            "description": client._server_info.get("name", ""),
            "version": client._server_info.get("version", ""),
        }
    except Exception as e:
        return {"name": name, "state": "error", "tools": 0, "error": str(e)}


# ── Runtime detection ──────────────────────────────────────────────────────

def _check_runtime(runtime: str, command: str = "") -> tuple[bool, str]:
    """Check if the required runtime — and specifically the launcher command
    the entry will actually invoke — is available. Returns (ok, message).
    """
    if command:
        from .client import _resolve_launcher
        resolved = _resolve_launcher(command)
        if command in ("uvx", "uv"):
            try:
                import uv  # noqa: F401
                return True, ""
            except ImportError:
                pass
        if not (os.path.exists(resolved) or shutil.which(resolved)):
            friendly = {
                "uvx": "uv (install via https://astral.sh/uv or `pip install uv`) — needed for the 'uvx' launcher",
                "uv": "uv (install via https://astral.sh/uv or `pip install uv`)",
                "npx": "Node.js (install from https://nodejs.org) — needed for the 'npx' launcher",
                "docker": "Docker (install from https://docker.com)",
            }.get(command, f"the '{command}' command")
            return False, f"Required launcher '{command}' not found on PATH. Install {friendly}."

    if not runtime:
        return True, ""

    if runtime == "node":
        from .client import _resolve_launcher
        if shutil.which("node") or shutil.which("npx") or _resolve_launcher("npx") != "npx":
            return True, ""
        return False, "Node.js is required but not found. Install from https://nodejs.org"

    if runtime == "python":
        if shutil.which("python") or shutil.which("python3") or shutil.which("uv") or shutil.which("uvx"):
            return True, ""
        try:
            import uv  # noqa: F401
            return True, ""
        except ImportError:
            pass
        return False, "Python is required but not found."

    if runtime == "docker":
        if shutil.which("docker"):
            return True, ""
        return False, "Docker is required but not found."

    return True, ""


def detect_available_runtimes() -> dict[str, bool]:
    """Detect which runtimes are available on this system."""
    from .client import _resolve_launcher
    has_uv = False
    try:
        import uv  # noqa: F401
        has_uv = True
    except ImportError:
        pass
    has_uv = has_uv or bool(shutil.which("uv") or shutil.which("uvx") or _resolve_launcher("uvx") != "uvx")
    has_node = bool(shutil.which("node") or shutil.which("npx") or _resolve_launcher("npx") != "npx")

    return {
        "node": has_node,
        "python": bool(shutil.which("python") or shutil.which("python3") or has_uv),
        "uv": has_uv,
        "docker": bool(shutil.which("docker")),
    }


# ── Auto-install helpers ───────────────────────────────────────────────────

def auto_install_runtimes() -> list[str]:
    """Attempt to auto-install missing runtimes. Returns list of installed ones."""
    installed = []
    runtimes = detect_available_runtimes()

    # Try to install uv (fastest Python package manager) if Python is missing
    if not runtimes["uv"] and not runtimes["python"]:
        try:
            # uv installer
            import urllib.request
            url = "https://astral.sh/uv/install.sh"
            with urllib.request.urlopen(url, timeout=15) as resp:
                script = resp.read()
            result = subprocess.run(
                ["sh", "-c", script.decode("utf-8")],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                installed.append("uv")
        except Exception:
            pass

    return installed


# ── Quick install from GitHub URL ──────────────────────────────────────────

def install_from_url(name: str, url: str, transport: str = "stdio") -> tuple[bool, str]:
    """Install an MCP server from a custom URL or command.

    Args:
        name: Unique name for this server
        url: For stdio: command to run. For sse/http: the URL endpoint.
        transport: "stdio", "sse", or "http"
    """
    configs = load_mcp_configs()
    if name in configs:
        return False, f"An MCP server named '{name}' is already configured."

    if transport == "stdio":
        # URL is treated as a command string
        parts = url.split()
        if not parts:
            return False, "Command cannot be empty."
        entry = {
            "type": "stdio",
            "command": parts[0],
            "args": parts[1:] if len(parts) > 1 else [],
        }
    else:
        entry = {
            "type": transport,
            "url": url,
        }

    try:
        add_server_to_user_config(name, entry)
        return True, f"Added MCP server '{name}' ({transport})."
    except Exception as e:
        return False, f"Failed to add '{name}': {e}"
