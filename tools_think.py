"""Think Tool - Explicit agent reasoning for Dulus.

Provides a Think tool that allows the agent to perform explicit reasoning
without taking any action. The thought is logged and displayed to the user,
helping with transparency and debugging of the agent's decision-making process.
"""
from __future__ import annotations

from tool_registry import ToolDef, register_tool


# ── Schema ────────────────────────────────────────────────────────────────────

_THINK_SCHEMA = {
    "name": "Think",
    "description": (
        "Think about something without taking action. Use this to reason through "
        "complex problems, plan your approach, or analyze information before deciding "
        "on a tool call. Your thought will be logged and displayed to the user, "
        "helping them understand your reasoning process. This tool does NOT modify "
        "any state or files."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": "A thought to think through. Be detailed and explicit in your reasoning.",
            },
        },
        "required": ["thought"],
    },
}


# ── Implementation ────────────────────────────────────────────────────────────

def _think(thought: str) -> str:
    """Log a thought and return a display-friendly result.

    Args:
        thought: The reasoning text to log.

    Returns:
        A formatted string with the thought content for display.
    """
    # The thought content is returned for display; the model can see its own thought
    # and the user can see it via the display block system
    prefix = f"[Think] ({len(thought)} characters)"
    return f"{prefix}\n\n{thought}"


# ── Registration ──────────────────────────────────────────────────────────────

def _register() -> None:
    """Register the Think tool into the central registry."""
    register_tool(
        ToolDef(
            name="Think",
            schema=_THINK_SCHEMA,
            func=lambda p, c: _think(p["thought"]),
            read_only=True,
            concurrent_safe=True,
        )
    )


_register()
