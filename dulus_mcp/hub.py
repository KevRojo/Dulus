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
    "sqlite": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite"],
        "description": "SQLite database operations.",
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
    "sentry": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sentry"],
        "description": "Sentry — error tracking and issue management. Requires SENTRY_AUTH_TOKEN.",
        "requires_args": False,
        "env": {"SENTRY_AUTH_TOKEN": ""},
        "runtime": "node",
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
        # Best-effort install hint from the repo/name
        runtime = ""
        if "npmjs.com" in url or "/npm/" in url:
            runtime = "node"
        elif "pypi.org" in url:
            runtime = "python"
        servers.append({
            "name": name, "description": desc,
            "repo_url": url, "runtime": runtime,
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
            runtime=info.get("runtime", ""),
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


def search(query: str) -> list[MCPServerEntry]:
    """Search across all sources for MCP servers matching query."""
    return list_all(query)


# ── Get single server ──────────────────────────────────────────────────────

def get_server(name: str) -> Optional[MCPServerEntry]:
    """Find an MCP server by name across all sources."""
    for entry in list_all():
        if entry.name == name or entry.config_name == name:
            return entry
    return None


# ── Install / Uninstall ────────────────────────────────────────────────────

def install(name: str, user_args: Optional[list[str]] = None, env_overrides: Optional[dict] = None) -> tuple[bool, str]:
    """0-friction install an MCP server.

    Args:
        name: Server name (e.g. "filesystem", "github")
        user_args: Optional user-provided args (e.g. ["/home/user/projects"])
        env_overrides: Optional env vars to set (e.g. {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx"})

    Returns:
        (success, message)
    """
    entry = get_server(name)
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
        # For filesystem server, args are appended
        if entry.name == "filesystem":
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


def get_status(name: str) -> dict:
    """Get connection status of an installed MCP server."""
    from .client import MCPClient, get_mcp_manager

    configs = load_mcp_configs()
    if name not in configs:
        return {"name": name, "state": "not_configured", "tools": 0, "error": "Not installed"}

    cfg = configs[name]
    client = MCPClient(cfg)
    try:
        client.connect()
        tools = client.list_tools()
        client.disconnect()
        return {
            "name": name,
            "state": "connected",
            "tools": len(tools),
            "error": "",
            "description": client._server_info.get("name", ""),
            "version": client._server_info.get("version", ""),
        }
    except Exception as e:
        return {
            "name": name,
            "state": "error",
            "tools": 0,
            "error": str(e),
        }


# ── Runtime detection ──────────────────────────────────────────────────────

def _check_runtime(runtime: str, command: str = "") -> tuple[bool, str]:
    """Check if the required runtime — and specifically the launcher command
    the entry will actually invoke — is available. Returns (ok, message).

    Why `command` matters: several curated servers tagged runtime="python"
    actually launch via `uvx` (e.g. git, fetch), not via a plain `python`
    interpreter. The old check accepted ANY of python/python3/uv/uvx being
    present as proof the "python runtime" was satisfied — so on a machine
    that has python.exe but never installed `uv`, servers needing `uvx`
    would sail through this check, get marked "installed", and then fail
    every single connection attempt with a raw FileNotFoundError/WinError 2.
    We now also require the exact launcher binary to resolve via PATH.
    """
    if command and not shutil.which(command):
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
        if shutil.which("node") or shutil.which("npx"):
            return True, ""
        return False, "Node.js is required but not found. Install from https://nodejs.org"

    if runtime == "python":
        if shutil.which("python") or shutil.which("python3") or shutil.which("uv") or shutil.which("uvx"):
            return True, ""
        return False, "Python is required but not found."

    if runtime == "docker":
        if shutil.which("docker"):
            return True, ""
        return False, "Docker is required but not found."

    return True, ""


def detect_available_runtimes() -> dict[str, bool]:
    """Detect which runtimes are available on this system."""
    return {
        "node": bool(shutil.which("node") or shutil.which("npx")),
        "python": bool(shutil.which("python") or shutil.which("python3")),
        "uv": bool(shutil.which("uv") or shutil.which("uvx")),
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
