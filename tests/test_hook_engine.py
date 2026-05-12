"""Tests for HookEngine."""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

# Ensure project root is on path for dulus.* imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from dulus_tools.hook_engine import HookDef, HookEngine, HookResult


# ── HookDef Tests ────────────────────────────────────────────────────────────


class TestHookDef:
    """Test suite for HookDef dataclass."""

    def test_create_minimal(self):
        """Create a minimal HookDef."""
        hook = HookDef(event="tool_call")
        assert hook.event == "tool_call"
        assert hook.matcher == ""
        assert hook.command == ""
        assert hook.timeout == 30

    def test_create_full(self):
        """Create a HookDef with all fields."""
        hook = HookDef(
            event="tool_call",
            matcher="Write|Edit",
            command="echo '{target}'",
            timeout=10,
        )
        assert hook.event == "tool_call"
        assert hook.matcher == "Write|Edit"
        assert hook.command == "echo '{target}'"
        assert hook.timeout == 10

    def test_compiled_matcher_valid(self):
        """A valid regex should compile."""
        hook = HookDef(event="tool_call", matcher="Write|Edit")
        pattern = hook.compiled_matcher
        assert pattern is not None
        assert pattern.search("Write")
        assert pattern.search("Edit")

    def test_compiled_matcher_empty(self):
        """An empty matcher should return None."""
        hook = HookDef(event="tool_call", matcher="")
        assert hook.compiled_matcher is None

    def test_compiled_matcher_invalid(self):
        """An invalid regex should return None."""
        hook = HookDef(event="tool_call", matcher="[invalid(")
        assert hook.compiled_matcher is None


# ── HookResult Tests ─────────────────────────────────────────────────────────


class TestHookResult:
    """Test suite for HookResult dataclass."""

    def test_create(self):
        """Create a HookResult."""
        hook = HookDef(event="tool_call")
        result = HookResult(hook=hook, matched=True, returncode=0)
        assert result.matched is True
        assert result.returncode == 0


# ── HookEngine Tests ─────────────────────────────────────────────────────────


class TestHookEngine:
    """Test suite for HookEngine."""

    def test_init_empty(self):
        """Create an empty HookEngine."""
        engine = HookEngine()
        assert engine.list_hooks() == []

    def test_init_with_hooks(self):
        """Create a HookEngine with hooks."""
        hooks = [
            HookDef(event="tool_call", matcher="Write"),
            HookDef(event="approval_request"),
        ]
        engine = HookEngine(hooks=hooks)
        assert len(engine.list_hooks()) == 2

    def test_add_hook(self):
        """Add a hook to the engine."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call"))
        assert len(engine.list_hooks()) == 1

    def test_remove_hook(self):
        """Remove hooks by event type."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call"))
        engine.add_hook(HookDef(event="tool_call"))
        engine.add_hook(HookDef(event="approval_request"))
        removed = engine.remove_hook("tool_call")
        assert removed == 2
        assert len(engine.list_hooks()) == 1

    def test_remove_hook_no_match(self):
        """Remove hooks with no match should return 0."""
        engine = HookEngine()
        removed = engine.remove_hook("nonexistent")
        assert removed == 0

    @pytest.mark.asyncio
    async def test_trigger_no_match(self):
        """Trigger with no matching hooks should return empty."""
        engine = HookEngine()
        results = await engine.trigger("tool_call", "Read")
        assert results == []

    @pytest.mark.asyncio
    async def test_trigger_event_mismatch(self):
        """Trigger with matching event type."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="Write", command="echo 'hello'"))
        results = await engine.trigger("different_event", "Write")
        assert results == []

    @pytest.mark.asyncio
    async def test_trigger_matcher_match(self):
        """Trigger with matching regex."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="Write|Edit", command="echo 'matched'"))
        results = await engine.trigger("tool_call", "Write")
        assert len(results) == 1
        assert results[0]["matched"] is True

    @pytest.mark.asyncio
    async def test_trigger_matcher_no_match(self):
        """Trigger with non-matching regex."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="Write|Edit", command="echo 'matched'"))
        results = await engine.trigger("tool_call", "Read")
        assert results == []

    @pytest.mark.asyncio
    async def test_trigger_empty_matcher(self):
        """Trigger with empty matcher should match any target."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="", command="echo 'any'"))
        results = await engine.trigger("tool_call", "Anything")
        assert len(results) == 1
        assert results[0]["matched"] is True

    @pytest.mark.asyncio
    async def test_trigger_command_execution(self):
        """Trigger should execute the command."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="Write", command="echo hello world"))
        results = await engine.trigger("tool_call", "Write")
        assert len(results) == 1
        assert results[0]["returncode"] == 0
        assert "hello world" in results[0]["stdout"]

    @pytest.mark.asyncio
    async def test_trigger_template_substitution(self):
        """Trigger should substitute template variables."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="MyFile", command="echo {target}"))
        results = await engine.trigger("tool_call", "MyFile")
        assert len(results) == 1
        assert "MyFile" in results[0]["stdout"]

    @pytest.mark.asyncio
    async def test_trigger_context_substitution(self):
        """Trigger should substitute context variables."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", command="echo {extra}"))
        results = await engine.trigger("tool_call", "Write", extra="bonus")
        assert len(results) == 1
        assert "bonus" in results[0]["stdout"]

    @pytest.mark.asyncio
    async def test_trigger_timeout(self):
        """Trigger should respect timeout."""
        engine = HookEngine()
        engine.add_hook(HookDef(
            event="tool_call",
            command='python -c "import time; time.sleep(10)"',
            timeout=1,  # Very short timeout
        ))
        results = await engine.trigger("tool_call", "Write")
        assert len(results) == 1
        assert results[0]["timed_out"] is True

    @pytest.mark.asyncio
    async def test_trigger_no_command(self):
        """Trigger with no command should still report match."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="Write"))
        results = await engine.trigger("tool_call", "Write")
        assert len(results) == 1
        assert results[0]["matched"] is True
        assert results[0]["command"] == ""


# ── Config Loading Tests ─────────────────────────────────────────────────────


class TestHookEngineConfig:
    """Test suite for HookEngine config loading."""

    def test_from_config_nonexistent(self):
        """Loading from nonexistent config should return empty engine."""
        engine = HookEngine.from_config("/nonexistent/path/hooks.toml")
        assert engine.list_hooks() == []

    def test_from_config_valid_toml(self, tmp_path: Path):
        """Loading from a valid TOML config."""
        config_path = tmp_path / "hooks.toml"
        config_path.write_text("""
[[hooks]]
event = "tool_call"
matcher = "Write|Edit"
command = "echo 'File modified: {target}'"
timeout = 10

[[hooks]]
event = "approval_request"
matcher = ""
command = "echo 'Approval needed'"
timeout = 5
""")
        engine = HookEngine.from_config(config_path)
        hooks = engine.list_hooks()
        assert len(hooks) == 2
        assert hooks[0].event == "tool_call"
        assert hooks[0].matcher == "Write|Edit"
        assert hooks[0].timeout == 10
        assert hooks[1].event == "approval_request"
        assert hooks[1].timeout == 5

    def test_from_config_invalid_toml(self, tmp_path: Path):
        """Loading from an invalid TOML should return empty engine."""
        config_path = tmp_path / "hooks.toml"
        config_path.write_text("not valid toml at all!!!")
        engine = HookEngine.from_config(config_path)
        assert engine.list_hooks() == []

    def test_parse_hooks_toml_simple(self):
        """Test the simple TOML parser fallback."""
        toml_text = """
[[hooks]]
event = "tool_call"
matcher = "Write"
command = "echo 'hello'"
timeout = 15

[[hooks]]
event = "approval_request"
matcher = ""
command = "echo 'approve'"
timeout = 5
"""
        hooks = HookEngine._parse_hooks_toml_simple(toml_text)
        assert len(hooks) == 2
        assert hooks[0].event == "tool_call"
        assert hooks[0].matcher == "Write"
        assert hooks[0].command == "echo 'hello'"
        assert hooks[0].timeout == 15
        assert hooks[1].event == "approval_request"
        assert hooks[1].timeout == 5

    def test_parse_hooks_toml_simple_empty(self):
        """Test parsing empty TOML."""
        hooks = HookEngine._parse_hooks_toml_simple("")
        assert hooks == []

    def test_parse_hooks_toml_simple_no_hooks(self):
        """Test parsing TOML without hooks."""
        toml_text = "[other_section]\nkey = 'value'"
        hooks = HookEngine._parse_hooks_toml_simple(toml_text)
        assert hooks == []

    def test_ensure_default_config(self, tmp_path: Path):
        """ensure_default_config should create a default config file."""
        # Mock the home directory
        original_home = Path.home
        try:
            Path.home = lambda: tmp_path  # type: ignore[method-assign]
            engine = HookEngine()
            engine.ensure_default_config()
            config_path = tmp_path / ".dulus" / "hooks.toml"
            assert config_path.exists()
            content = config_path.read_text(encoding="utf-8")
            assert "hooks" in content
        finally:
            Path.home = original_home  # type: ignore[method-assign]

    def test_ensure_default_config_no_overwrite(self, tmp_path: Path):
        """ensure_default_config should not overwrite existing config."""
        original_home = Path.home
        try:
            Path.home = lambda: tmp_path  # type: ignore[method-assign]
            config_dir = tmp_path / ".dulus"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "hooks.toml"
            config_path.write_text("existing content", encoding="utf-8")

            engine = HookEngine()
            engine.ensure_default_config()
            content = config_path.read_text(encoding="utf-8")
            assert content == "existing content"
        finally:
            Path.home = original_home  # type: ignore[method-assign]


# ── Edge Case Tests ──────────────────────────────────────────────────────────


class TestHookEngineEdgeCases:
    """Edge case tests for HookEngine."""

    @pytest.mark.asyncio
    async def test_trigger_with_failing_command(self):
        """Trigger with a command that returns non-zero exit code."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", command="exit 1"))
        results = await engine.trigger("tool_call", "Write")
        assert len(results) == 1
        assert results[0]["returncode"] == 1

    @pytest.mark.asyncio
    async def test_trigger_with_invalid_command(self):
        """Trigger with an invalid command."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", command="not_a_real_command_12345"))
        results = await engine.trigger("tool_call", "Write")
        assert len(results) == 1
        assert results[0]["returncode"] != 0

    @pytest.mark.asyncio
    async def test_trigger_multiple_hooks(self):
        """Trigger should execute all matching hooks."""
        engine = HookEngine()
        engine.add_hook(HookDef(event="tool_call", matcher="Write", command="echo first"))
        engine.add_hook(HookDef(event="tool_call", matcher="Write", command="echo second"))
        engine.add_hook(HookDef(event="tool_call", matcher="Read", command="echo third"))
        results = await engine.trigger("tool_call", "Write")
        assert len(results) == 2
        outputs = [r["stdout"].strip() for r in results]
        assert "first" in outputs
        assert "second" in outputs

    @pytest.mark.asyncio
    async def test_trigger_cwd(self):
        """Trigger should execute in the specified working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = HookEngine(cwd=tmpdir)
            engine.add_hook(HookDef(event="tool_call", command='python -c "import os; print(os.getcwd())"'))
            results = await engine.trigger("tool_call", "Write")
            assert len(results) == 1
            assert tmpdir in results[0]["stdout"]
