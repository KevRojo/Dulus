"""Tests for the Think tool (tools_think.py)."""
from __future__ import annotations

import pytest

from tool_registry import get_tool, clear_registry

# Importing registers the tool
import tools_think


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset registry before each test."""
    clear_registry()
    # Re-register the tool
    tools_think._register()
    yield
    clear_registry()


class TestThinkTool:
    """Test suite for the Think tool."""

    def test_tool_is_registered(self):
        """Think tool must be registered in the tool registry."""
        tool = get_tool("Think")
        assert tool is not None
        assert tool.name == "Think"

    def test_tool_is_read_only(self):
        """Think tool should be read-only (doesn't mutate state)."""
        tool = get_tool("Think")
        assert tool.read_only is True

    def test_tool_is_concurrent_safe(self):
        """Think tool should be safe to run concurrently."""
        tool = get_tool("Think")
        assert tool.concurrent_safe is True

    def test_think_execution(self):
        """Think tool should execute and return the thought."""
        tool = get_tool("Think")
        thought_text = "I need to analyze the problem carefully before choosing a tool."
        result = tool.func({"thought": thought_text}, {})

        assert "Think" in result
        assert thought_text in result
        assert str(len(thought_text)) in result

    def test_think_with_empty_string(self):
        """Think tool should handle empty string thoughts."""
        tool = get_tool("Think")
        result = tool.func({"thought": ""}, {})
        assert "Think" in result

    def test_think_with_long_thought(self):
        """Think tool should handle very long thoughts."""
        tool = get_tool("Think")
        long_thought = "Step 1: analyze. " * 100
        result = tool.func({"thought": long_thought}, {})

        assert "Think" in result
        assert str(len(long_thought)) in result
        assert long_thought in result

    def test_think_schema_has_required_thought(self):
        """The schema should require the 'thought' parameter."""
        tool = get_tool("Think")
        schema = tool.schema
        assert "thought" in schema["input_schema"]["properties"]
        assert "thought" in schema["input_schema"]["required"]

    def test_think_description_is_meaningful(self):
        """The tool description should explain its purpose."""
        tool = get_tool("Think")
        desc = tool.schema["description"].lower()
        assert "think" in desc
        assert "reason" in desc or "action" in desc or "without" in desc

    def test_think_execution_returns_string(self):
        """Think tool should always return a string."""
        tool = get_tool("Think")
        result = tool.func({"thought": "Test"}, {})
        assert isinstance(result, str)

    def test_think_with_multiline_thought(self):
        """Think tool should handle multiline thoughts."""
        tool = get_tool("Think")
        multiline = "Line 1\nLine 2\nLine 3"
        result = tool.func({"thought": multiline}, {})
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
