"""Composio plugin for Falcon - native ToolDefs.

Connects to Composio Tool Router and exposes tools natively.
"""
import sys
import json
from pathlib import Path
from typing import Any, Dict, List

PLUGIN_DIR = Path(__file__).parent.absolute()
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from tool_registry import ToolDef
from composio_plugin.session_manager import get_client, get_or_create_session, list_accounts
from composio_plugin.tool_generator import generate_tool_py, generate_plugin_tool_py


# ── Helpers ──────────────────────────────────────────────────────────────────

def _serialize_result(result) -> str:
    """Serialize Composio result to JSON string."""
    data = result.data if hasattr(result, "data") else result
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def _get_session(params: dict) -> Any:
    """Get or create session from params."""
    user_id = params.get("user_id", "dulus_user")
    toolkits = params.get("toolkits", [])
    if isinstance(toolkits, str):
        toolkits = [toolkits]
    connected_accounts = params.get("connected_accounts")
    return get_or_create_session(user_id, toolkits, connected_accounts)


# ── Tool Functions ───────────────────────────────────────────────────────────

def composio_create_session(params: dict, config: dict) -> str:
    """Create a new Composio Tool Router session."""
    user_id = params.get("user_id", "dulus_user")
    toolkits = params.get("toolkits", [])
    if isinstance(toolkits, str):
        toolkits = [toolkits]
    if not toolkits:
        return json.dumps({"error": "toolkits is required (list of toolkit slugs)"}, indent=2)

    wait = params.get("wait_for_connections", True)
    connected_accounts = params.get("connected_accounts")

    try:
        session = get_or_create_session(user_id, toolkits, connected_accounts)
        tools = session.tools()
        tool_names = []
        for t in tools:
            func = t.get("function", {})
            name = func.get("name", "")
            if name and not name.startswith("COMPOSIO_"):
                tool_names.append(name)

        return json.dumps({
            "session_id": session.session_id,
            "toolkits": toolkits,
            "tools_available": len(tools),
            "app_tools": tool_names,
            "status": "ok"
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def composio_search_tools(params: dict, config: dict) -> str:
    """Search for available Composio tools by use case."""
    user_id = params.get("user_id", "dulus_user")
    toolkits = params.get("toolkits", [])
    if isinstance(toolkits, str):
        toolkits = [toolkits]
    if not toolkits:
        toolkits = ["gmail"]

    queries = params.get("queries", [])
    if not queries:
        use_case = params.get("use_case", "")
        if use_case:
            queries = [{"use_case": use_case, "known_fields": ""}]
        else:
            return json.dumps({"error": "Provide 'queries' list or 'use_case' string"}, indent=2)

    try:
        session = get_or_create_session(user_id, toolkits)
        result = session.execute(
            tool_slug="COMPOSIO_SEARCH_TOOLS",
            arguments={"queries": queries, "session_id": session.session_id}
        )
        return _serialize_result(result)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def composio_manage_connections(params: dict, config: dict) -> str:
    """Manage connections to apps (initiate OAuth/API key auth)."""
    user_id = params.get("user_id", "dulus_user")
    toolkits = params.get("toolkits", [])
    if isinstance(toolkits, str):
        toolkits = [toolkits]
    if not toolkits:
        return json.dumps({"error": "toolkits is required"}, indent=2)

    reinitiate = params.get("reinitiate_all", False)

    try:
        session = get_or_create_session(user_id, toolkits)
        result = session.execute(
            tool_slug="COMPOSIO_MANAGE_CONNECTIONS",
            arguments={
                "toolkits": toolkits,
                "session_id": session.session_id,
                "reinitiate_all": reinitiate
            }
        )
        return _serialize_result(result)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def composio_execute_tool(params: dict, config: dict) -> str:
    """Execute a Composio tool by slug with given arguments."""
    user_id = params.get("user_id", "dulus_user")
    toolkits = params.get("toolkits", [])
    if isinstance(toolkits, str):
        toolkits = [toolkits]
    if not toolkits:
        return json.dumps({"error": "toolkits is required"}, indent=2)

    tool_slug = params.get("tool_slug", "")
    if not tool_slug:
        return json.dumps({"error": "tool_slug is required"}, indent=2)

    arguments = params.get("arguments", {})

    try:
        session = get_or_create_session(user_id, toolkits)
        result = session.execute(tool_slug=tool_slug, arguments=arguments)
        return _serialize_result(result)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def composio_list_accounts(params: dict, config: dict) -> str:
    """List all connected Composio accounts and their status."""
    try:
        accounts = list_accounts()
        return json.dumps({
            "total": len(accounts),
            "accounts": accounts
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def composio_get_tool_schemas(params: dict, config: dict) -> str:
    """Get input schemas for Composio tools by slug."""
    user_id = params.get("user_id", "dulus_user")
    toolkits = params.get("toolkits", [])
    if isinstance(toolkits, str):
        toolkits = [toolkits]
    if not toolkits:
        return json.dumps({"error": "toolkits is required"}, indent=2)

    tool_slugs = params.get("tool_slugs", [])
    if isinstance(tool_slugs, str):
        tool_slugs = [tool_slugs]
    if not tool_slugs:
        return json.dumps({"error": "tool_slugs is required"}, indent=2)

    try:
        session = get_or_create_session(user_id, toolkits)
        result = session.execute(
            tool_slug="COMPOSIO_GET_TOOL_SCHEMAS",
            arguments={"tool_slugs": tool_slugs, "session_id": session.session_id}
        )
        return _serialize_result(result)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def composio_generate_tool_py(params: dict, config: dict) -> str:
    """Generate a standalone .py file for a Composio tool.

    Creates a native Falcon tool file that wraps a Composio tool.
    """
    tool_slug = params.get("tool_slug", "")
    output_dir = params.get("output_dir", str(Path.home() / ".falcon" / "plugins" / "composio" / "generated"))
    user_id = params.get("user_id", "dulus_user")
    schema = params.get("schema")

    if not tool_slug:
        return json.dumps({"error": "tool_slug is required"}, indent=2)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        if schema:
            path = generate_tool_py(tool_slug, schema, Path(output_dir), user_id=user_id)
        else:
            # Fetch schema first
            session = get_or_create_session(user_id, ["gmail"])
            result = session.execute(
                tool_slug="COMPOSIO_GET_TOOL_SCHEMAS",
                arguments={"tool_slugs": [tool_slug], "session_id": session.session_id}
            )
            data = result.data if hasattr(result, "data") else result
            schemas = data.get("schemas", []) if isinstance(data, dict) else []
            if schemas:
                schema = schemas[0]
                path = generate_tool_py(tool_slug, schema, Path(output_dir), user_id=user_id)
            else:
                return json.dumps({"error": f"Could not fetch schema for {tool_slug}"}, indent=2)

        return json.dumps({
            "status": "ok",
            "file": str(path),
            "tool_slug": tool_slug
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def composio_generate_plugin_tool_py(params: dict, config: dict) -> str:
    """Generate a full plugin_tool.py exporting multiple Composio tools as native Falcon tools."""
    tool_slugs = params.get("tool_slugs", [])
    if isinstance(tool_slugs, str):
        tool_slugs = [tool_slugs]
    if not tool_slugs:
        return json.dumps({"error": "tool_slugs is required"}, indent=2)

    output_dir = params.get("output_dir", str(Path.home() / ".falcon" / "plugins" / "composio" / "generated"))
    user_id = params.get("user_id", "dulus_user")
    toolkits = params.get("toolkits", ["gmail"])
    if isinstance(toolkits, str):
        toolkits = [toolkits]

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        session = get_or_create_session(user_id, toolkits)
        result = session.execute(
            tool_slug="COMPOSIO_GET_TOOL_SCHEMAS",
            arguments={"tool_slugs": tool_slugs, "session_id": session.session_id}
        )
        data = result.data if hasattr(result, "data") else result
        schemas = data.get("schemas", []) if isinstance(data, dict) else []

        tool_defs = []
        for s in schemas:
            tool_defs.append({
                "slug": s.get("slug", s.get("name", "unknown")),
                "description": s.get("description", ""),
                "schema": s.get("input_schema", s.get("parameters", {}))
            })

        output_path = Path(output_dir) / "plugin_tool.py"
        generate_plugin_tool_py(tool_defs, output_path)

        return json.dumps({
            "status": "ok",
            "file": str(output_path),
            "tools_generated": len(tool_defs)
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ── Tool Definitions ─────────────────────────────────────────────────────────

create_session_tool = ToolDef(
    name="composio_create_session",
    schema={
        "name": "composio_create_session",
        "description": "Create a new Composio Tool Router session for a user with specified toolkits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User identifier", "default": "dulus_user"},
                "toolkits": {"type": "array", "items": {"type": "string"}, "description": "List of toolkit slugs (e.g., ['gmail', 'slack', 'github'])"},
                "connected_accounts": {"type": "object", "description": "Optional mapping of toolkit slug to connected account ID"},
                "wait_for_connections": {"type": "boolean", "description": "Wait for connections to become active", "default": True}
            },
            "required": ["toolkits"]
        }
    },
    func=composio_create_session
)

search_tools_tool = ToolDef(
    name="composio_search_tools",
    schema={
        "name": "composio_search_tools",
        "description": "Search for available Composio tools by use case. Returns recommended tools, execution plans, and schemas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "dulus_user"},
                "toolkits": {"type": "array", "items": {"type": "string"}, "description": "Toolkits to search within"},
                "queries": {"type": "array", "description": "List of query objects with 'use_case' and optional 'known_fields'"},
                "use_case": {"type": "string", "description": "Simple use case string (alternative to queries)"}
            },
            "required": ["toolkits"]
        }
    },
    func=composio_search_tools
)

manage_connections_tool = ToolDef(
    name="composio_manage_connections",
    schema={
        "name": "composio_manage_connections",
        "description": "Manage connections to apps. Initiates OAuth/API key auth and returns authentication links.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "dulus_user"},
                "toolkits": {"type": "array", "items": {"type": "string"}, "description": "Toolkits to connect"},
                "reinitiate_all": {"type": "boolean", "default": False}
            },
            "required": ["toolkits"]
        }
    },
    func=composio_manage_connections
)

execute_tool = ToolDef(
    name="composio_execute_tool",
    schema={
        "name": "composio_execute_tool",
        "description": "Execute a Composio tool by slug with given arguments. Use composio_search_tools first to discover valid slugs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "dulus_user"},
                "toolkits": {"type": "array", "items": {"type": "string"}, "description": "Toolkits required for execution"},
                "tool_slug": {"type": "string", "description": "Exact tool slug from search results"},
                "arguments": {"type": "object", "description": "Arguments matching the tool's input schema"}
            },
            "required": ["toolkits", "tool_slug", "arguments"]
        }
    },
    func=composio_execute_tool
)

list_accounts_tool = ToolDef(
    name="composio_list_accounts",
    schema={
        "name": "composio_list_accounts",
        "description": "List all connected Composio accounts with their status and toolkit.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    func=composio_list_accounts,
    read_only=True
)

get_schemas_tool = ToolDef(
    name="composio_get_tool_schemas",
    schema={
        "name": "composio_get_tool_schemas",
        "description": "Retrieve input schemas for Composio tools by slug. Returns complete parameter definitions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "default": "dulus_user"},
                "toolkits": {"type": "array", "items": {"type": "string"}},
                "tool_slugs": {"type": "array", "items": {"type": "string"}, "description": "List of tool slugs to get schemas for"}
            },
            "required": ["toolkits", "tool_slugs"]
        }
    },
    func=composio_get_tool_schemas,
    read_only=True
)

generate_tool_py_tool = ToolDef(
    name="composio_generate_tool_py",
    schema={
        "name": "composio_generate_tool_py",
        "description": "Generate a standalone .py file wrapping a single Composio tool as a native Falcon tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_slug": {"type": "string", "description": "Tool slug to generate wrapper for"},
                "output_dir": {"type": "string", "description": "Directory to write the file"},
                "user_id": {"type": "string", "default": "dulus_user"},
                "schema": {"type": "object", "description": "Optional pre-fetched schema"}
            },
            "required": ["tool_slug"]
        }
    },
    func=composio_generate_tool_py
)

generate_plugin_tool_py_tool = ToolDef(
    name="composio_generate_plugin_tool_py",
    schema={
        "name": "composio_generate_plugin_tool_py",
        "description": "Generate a full plugin_tool.py exporting multiple Composio tools as native Falcon tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_slugs": {"type": "array", "items": {"type": "string"}, "description": "List of tool slugs to export"},
                "output_dir": {"type": "string", "description": "Directory to write plugin_tool.py"},
                "user_id": {"type": "string", "default": "dulus_user"},
                "toolkits": {"type": "array", "items": {"type": "string"}, "default": ["gmail"]}
            },
            "required": ["tool_slugs"]
        }
    },
    func=composio_generate_plugin_tool_py
)

TOOL_DEFS = [
    create_session_tool,
    search_tools_tool,
    manage_connections_tool,
    execute_tool,
    list_accounts_tool,
    get_schemas_tool,
    generate_tool_py_tool,
    generate_plugin_tool_py_tool,
]

TOOL_SCHEMAS = [t.schema for t in TOOL_DEFS]
