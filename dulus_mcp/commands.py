"""MCP command handler for Dulus CLI.

Commands:
    /mcp list [query]       — List available MCP servers
    /mcp installed          — List installed MCP servers
    /mcp install <name>     — Install an MCP server (0-friction)
    /mcp remove <name>      — Uninstall an MCP server
    /mcp status [name]      — Check MCP server status
    /mcp search <query>     — Search for MCP servers
    /mcp runtimes           — Show available runtimes
"""
from __future__ import annotations

from .hub import (
    MCPServerEntry,
    detect_available_runtimes,
    get_server,
    get_status,
    install,
    list_all,
    list_installed,
    search,
    uninstall,
)


def handle_mcp_command(args: list[str]) -> str:
    """Handle /mcp commands. Returns a formatted string response."""
    if not args:
        return _help_text()

    cmd = args[0].lower()
    rest = args[1:] if len(args) > 1 else []

    if cmd in ("list", "ls"):
        return _cmd_list(rest[0] if rest else None)
    if cmd == "installed":
        return _cmd_installed()
    if cmd in ("install", "add"):
        return _cmd_install(rest)
    if cmd in ("remove", "rm", "uninstall"):
        return _cmd_remove(rest[0] if rest else "")
    if cmd == "status":
        return _cmd_status(rest[0] if rest else None)
    if cmd in ("search", "find", "s"):
        return _cmd_search(rest[0] if rest else "")
    if cmd == "runtimes":
        return _cmd_runtimes()
    if cmd in ("help", "h", "?"):
        return _help_text()

    return f"Unknown MCP command: '{cmd}'. Type /mcp help for usage."


def _help_text() -> str:
    return """🛠️ MCP Marketplace Commands

  /mcp list [query]      — Browse available MCP servers
  /mcp installed         — List your installed MCP servers
  /mcp install <name>    — Install an MCP server (0-friction!)
  /mcp remove <name>     — Uninstall an MCP server
  /mcp status [name]     — Check connection status
  /mcp search <query>    — Search for MCP servers
  /mcp runtimes          — Check available runtimes

💡 Popular: /mcp install filesystem  |  /mcp install github  |  /mcp install fetch
"""


def _cmd_list(query: str | None) -> str:
    servers = list_all(query)
    if not servers:
        return "No MCP servers found." + (f" (query: '{query}')" if query else "")

    lines = [f"📦 Available MCP Servers{' (filtered)' if query else ''}:", ""]
    for s in servers:
        icon = "✅" if s.installed else "⬜"
        source_icon = {"official": "🌟", "dulus": "🏠", "installed": "📌"}.get(s.source, "📦")
        runtime = f" [{s.runtime}]" if s.runtime else ""
        lines.append(f"  {icon} {source_icon} {s.name}{runtime} — {s.description}")
    lines.append("")
    lines.append(f"Total: {len(servers)} servers. Install with /mcp install <name>")
    return "\n".join(lines)


def _cmd_installed() -> str:
    servers = list_installed()
    if not servers:
        return "📭 No MCP servers installed. Run /mcp list to browse available servers."

    lines = ["📌 Installed MCP Servers:", ""]
    for s in servers:
        status = get_status(s.config_name)
        state_icon = {"connected": "🟢", "error": "🔴", "not_configured": "⚪"}.get(status["state"], "⚪")
        tools = f" ({status['tools']} tools)" if status["tools"] > 0 else ""
        lines.append(f"  {state_icon} {s.config_name}{tools} — {s.description}")
        if status.get("error"):
            lines.append(f"     ⚠️ {status['error']}")
    return "\n".join(lines)


def _cmd_install(args: list[str]) -> str:
    if not args:
        return "Usage: /mcp install <name>"

    name = args[0]
    user_args = args[1:] if len(args) > 1 else None

    # Check if server exists
    entry = get_server(name)
    if entry is None:
        available = [s.name for s in list_all()]
        did_you_mean = _fuzzy_match(name, available)
        msg = f"❌ MCP server '{name}' not found."
        if did_you_mean:
            msg += f" Did you mean: {', '.join(did_you_mean)}?"
        msg += "\nRun /mcp list to see available servers."
        return msg

    # Check if it requires args
    if entry.requires_args and not user_args:
        return f"⚠️ '{name}' requires arguments: {entry.arg_prompt}\nUsage: /mcp install {name} <args>"

    success, message = install(name, user_args=user_args)
    icon = "✅" if success else "❌"
    return f"{icon} {message}"


def _cmd_remove(name: str) -> str:
    if not name:
        return "Usage: /mcp remove <name>"
    success, message = uninstall(name)
    icon = "✅" if success else "❌"
    return f"{icon} {message}"


def _cmd_status(name: str | None) -> str:
    if name:
        status = get_status(name)
        state_icon = {"connected": "🟢", "error": "🔴", "not_configured": "⚪"}.get(status["state"], "⚪")
        lines = [f"{state_icon} {status['name']}: {status['state']}"]
        if status["tools"] > 0:
            lines.append(f"   Tools: {status['tools']}")
        if status.get("description"):
            lines.append(f"   Server: {status['description']} v{status.get('version', '?')}")
        if status.get("error"):
            lines.append(f"   ⚠️ Error: {status['error']}")
        return "\n".join(lines)

    # Status for all installed
    return _cmd_installed()


def _cmd_search(query: str) -> str:
    if not query:
        return "Usage: /mcp search <query>"
    results = search(query)
    if not results:
        return f"🔍 No results for '{query}'."

    lines = [f"🔍 Search results for '{query}':", ""]
    for s in results:
        icon = "✅" if s.installed else "⬜"
        lines.append(f"  {icon} {s.name} — {s.description}")
    return "\n".join(lines)


def _cmd_runtimes() -> str:
    runtimes = detect_available_runtimes()
    lines = ["🔧 Available Runtimes:", ""]
    for name, available in runtimes.items():
        icon = "✅" if available else "❌"
        lines.append(f"  {icon} {name}")
    lines.append("")
    lines.append("MCP servers need their runtime to be available.")
    return "\n".join(lines)


def _fuzzy_match(query: str, candidates: list[str], max_results: int = 3) -> list[str]:
    """Find close matches for a query string."""
    from difflib import get_close_matches
    return get_close_matches(query.lower(), [c.lower() for c in candidates], n=max_results, cutoff=0.5)
