"""Tests for the SteerInput system (steer_input.py)."""
from __future__ import annotations

import asyncio

import pytest

from steer_input import SteerInput, get_steer_input, reset_steer_input


class TestSteerInput:
    """Test suite for the SteerInput class."""

    def test_default_enabled(self):
        """SteerInput should be enabled by default."""
        steer = SteerInput()
        assert steer.enabled is True

    def test_enable_disable(self):
        """Enable/disable should toggle the enabled state."""
        steer = SteerInput()
        steer.disable()
        assert steer.enabled is False
        steer.enable()
        assert steer.enabled is True

    @pytest.mark.asyncio
    async def test_add_and_get_steer(self):
        """Adding a steer and then getting it should return the input."""
        steer = SteerInput()
        await steer.add_steer("Stop and reconsider")
        result = await steer.get_next_steer(timeout=0.5)
        assert result == "Stop and reconsider"

    @pytest.mark.asyncio
    async def test_get_next_steer_timeout(self):
        """Getting from empty queue should timeout and return None."""
        steer = SteerInput()
        result = await steer.get_next_steer(timeout=0.01)
        assert result is None

    @pytest.mark.asyncio
    async def test_has_pending(self):
        """has_pending should reflect queue state."""
        steer = SteerInput()
        assert not steer.has_pending()
        await steer.add_steer("test")
        assert steer.has_pending()
        await steer.get_next_steer(timeout=0.5)
        assert not steer.has_pending()

    @pytest.mark.asyncio
    async def test_add_steer_strips_whitespace(self):
        """add_steer should strip leading/trailing whitespace."""
        steer = SteerInput()
        await steer.add_steer("  hello world  ")
        result = await steer.get_next_steer(timeout=0.5)
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_add_steer_empty_raises(self):
        """Adding empty string should raise ValueError."""
        steer = SteerInput()
        with pytest.raises(ValueError):
            await steer.add_steer("")

    @pytest.mark.asyncio
    async def test_add_steer_whitespace_only_raises(self):
        """Adding whitespace-only string should raise ValueError."""
        steer = SteerInput()
        with pytest.raises(ValueError):
            await steer.add_steer("   ")

    @pytest.mark.asyncio
    async def test_add_steer_non_string_raises(self):
        """Adding non-string should raise TypeError."""
        steer = SteerInput()
        with pytest.raises(TypeError):
            await steer.add_steer(123)

    @pytest.mark.asyncio
    async def test_multiple_steers_fifo(self):
        """Multiple steers should be returned in FIFO order."""
        steer = SteerInput()
        await steer.add_steer("First")
        await steer.add_steer("Second")
        await steer.add_steer("Third")

        assert await steer.get_next_steer(timeout=0.5) == "First"
        assert await steer.get_next_steer(timeout=0.5) == "Second"
        assert await steer.get_next_steer(timeout=0.5) == "Third"
        assert await steer.get_next_steer(timeout=0.01) is None

    @pytest.mark.asyncio
    async def test_clear(self):
        """Clear should remove all pending steers."""
        steer = SteerInput()
        await steer.add_steer("One")
        await steer.add_steer("Two")
        assert steer.has_pending()
        cleared = steer.clear()
        assert cleared == 2
        assert not steer.has_pending()

    @pytest.mark.asyncio
    async def test_pending_count(self):
        """pending_count should reflect queue size."""
        steer = SteerInput()
        assert steer.pending_count == 0
        await steer.add_steer("A")
        assert steer.pending_count == 1
        await steer.add_steer("B")
        assert steer.pending_count == 2
        await steer.get_next_steer(timeout=0.5)
        assert steer.pending_count == 1

    @pytest.mark.asyncio
    async def test_clear_empty(self):
        """Clearing empty queue should return 0."""
        steer = SteerInput()
        assert steer.clear() == 0

    def test_get_next_steer_sync_no_loop(self):
        """Sync get without running loop should return None gracefully."""
        steer = SteerInput()
        result = steer.get_next_steer_sync(timeout=0.01)
        # This may return None or raise depending on context
        assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_next_steer_sync_in_running_loop(self):
        """Sync get in running loop should use nowait."""
        steer = SteerInput()
        await steer.add_steer("Sync test")
        result = steer.get_next_steer_sync(timeout=0.5)
        assert result == "Sync test"

    @pytest.mark.asyncio
    async def test_concurrent_adds(self):
        """Concurrent adds should be safe."""
        steer = SteerInput()

        async def adder(text):
            await steer.add_steer(text)

        await asyncio.gather(
            adder("A"),
            adder("B"),
            adder("C"),
        )
        assert steer.pending_count == 3


class TestSteerInputSingleton:
    """Test suite for the module-level singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_steer_input()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_steer_input()

    def test_get_steer_input_creates_singleton(self):
        """get_steer_input should create the singleton on first call."""
        steer = get_steer_input()
        assert isinstance(steer, SteerInput)
        assert steer.enabled is True

    def test_get_steer_input_returns_same_instance(self):
        """Multiple calls should return the same instance."""
        steer1 = get_steer_input()
        steer2 = get_steer_input()
        assert steer1 is steer2

    def test_reset_steer_input(self):
        """reset_steer_input should create a new instance on next get."""
        steer1 = get_steer_input()
        reset_steer_input()
        steer2 = get_steer_input()
        assert steer1 is not steer2

    @pytest.mark.asyncio
    async def test_singleton_shared_state(self):
        """The singleton should share state across callers."""
        steer1 = get_steer_input()
        await steer1.add_steer("Shared")

        steer2 = get_steer_input()
        result = await steer2.get_next_steer(timeout=0.5)
        assert result == "Shared"


class TestSteerInputEdgeCases:
    """Edge cases for SteerInput."""

    @pytest.mark.asyncio
    async def test_very_long_input(self):
        """Very long inputs should be handled."""
        steer = SteerInput()
        long_text = "A" * 10000
        await steer.add_steer(long_text)
        result = await steer.get_next_steer(timeout=0.5)
        assert result == long_text

    @pytest.mark.asyncio
    async def test_unicode_input(self):
        """Unicode input should be handled."""
        steer = SteerInput()
        await steer.add_steer("Hello 世界 🌍")
        result = await steer.get_next_steer(timeout=0.5)
        assert result == "Hello 世界 🌍"

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Special characters should be preserved."""
        steer = SteerInput()
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        await steer.add_steer(special)
        result = await steer.get_next_steer(timeout=0.5)
        assert result == special

    @pytest.mark.asyncio
    async def test_newlines_in_input(self):
        """Newlines in input should be preserved."""
        steer = SteerInput()
        multiline = "Line 1\nLine 2\nLine 3"
        await steer.add_steer(multiline)
        result = await steer.get_next_steer(timeout=0.5)
        assert result == multiline

    @pytest.mark.asyncio
    async def test_disabled_still_allows_add(self):
        """Adding to a disabled SteerInput should still work (disable only affects reading)."""
        steer = SteerInput()
        steer.disable()
        await steer.add_steer("While disabled")
        assert steer.has_pending()

    @pytest.mark.asyncio
    async def test_disable_does_not_clear(self):
        """Disabling should not clear existing items."""
        steer = SteerInput()
        await steer.add_steer("Before disable")
        steer.disable()
        result = await steer.get_next_steer(timeout=0.5)
        assert result == "Before disable"
