"""Tests for WireEventBus and WireEvent classes (Feature 17)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Ensure the project root (parent of tests/) is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dulus_tools.wire_events import (
    CompactionBeginEvent,
    CompactionEndEvent,
    StepBeginEvent,
    StepEndEvent,
    ToolCallEvent,
    TurnBeginEvent,
    TurnEndEvent,
    WireEvent,
    WireEventBus,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def bus(tmp_path: Path) -> WireEventBus:
    """Return a WireEventBus with a temporary session directory."""
    return WireEventBus(session_dir=str(tmp_path / "session"))


# ── Event Dataclasses ─────────────────────────────────────────────────────────


class TestWireEventTypes:
    """Tests for individual event type constructors."""

    def test_base_wire_event_defaults(self) -> None:
        """WireEvent should have sensible defaults."""
        event = WireEvent(event_type="test")
        assert event.event_type == "test"
        assert event.timestamp > 0
        assert event.payload == {}
        assert len(event.event_id) == 8

    def test_turn_begin_event(self) -> None:
        """TurnBeginEvent should set event_type and store user_input."""
        event = TurnBeginEvent(user_input="hello")
        assert event.event_type == "turn_begin"
        assert event.user_input == "hello"

    def test_turn_end_event(self) -> None:
        """TurnEndEvent should set event_type."""
        event = TurnEndEvent()
        assert event.event_type == "turn_end"

    def test_step_begin_event(self) -> None:
        """StepBeginEvent should set event_type and step_number."""
        event = StepBeginEvent(step_number=3)
        assert event.event_type == "step_begin"
        assert event.step_number == 3

    def test_step_end_event(self) -> None:
        """StepEndEvent should set event_type and step_number."""
        event = StepEndEvent(step_number=3)
        assert event.event_type == "step_end"
        assert event.step_number == 3

    def test_tool_call_event(self) -> None:
        """ToolCallEvent should set event_type and tool details."""
        event = ToolCallEvent(
            tool_name="read_file", params={"path": "test.py"}, result={"ok": True}
        )
        assert event.event_type == "tool_call"
        assert event.tool_name == "read_file"
        assert event.params == {"path": "test.py"}
        assert event.result == {"ok": True}

    def test_compaction_begin_event(self) -> None:
        """CompactionBeginEvent should set event_type."""
        event = CompactionBeginEvent()
        assert event.event_type == "compaction_begin"

    def test_compaction_end_event(self) -> None:
        """CompactionEndEvent should set event_type."""
        event = CompactionEndEvent()
        assert event.event_type == "compaction_end"


# ── EventBus ──────────────────────────────────────────────────────────────────


class TestWireEventBus:
    """Tests for the WireEventBus."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, bus: WireEventBus) -> None:
        """Subscribers should receive published events."""
        received: list[WireEvent] = []

        def handler(event: WireEvent) -> None:
            received.append(event)

        bus.subscribe("turn_begin", handler)
        event = TurnBeginEvent(user_input="hi")
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].event_type == "turn_begin"
        assert received[0].user_input == "hi"

    @pytest.mark.asyncio
    async def test_unsubscribe(self, bus: WireEventBus) -> None:
        """Unsubscribed handlers should not receive events."""
        received: list[WireEvent] = []

        def handler(event: WireEvent) -> None:
            received.append(event)

        token = bus.subscribe("turn_begin", handler)
        bus.unsubscribe(token)
        await bus.publish(TurnBeginEvent(user_input="hi"))

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_wildcard_subscribe(self, bus: WireEventBus) -> None:
        """Wildcard subscribers should receive all event types."""
        received: list[WireEvent] = []

        def handler(event: WireEvent) -> None:
            received.append(event)

        bus.subscribe("*", handler)
        await bus.publish(TurnBeginEvent(user_input="a"))
        await bus.publish(TurnEndEvent())
        await bus.publish(StepBeginEvent(step_number=1))

        assert len(received) == 3

    @pytest.mark.asyncio
    async def test_async_subscriber(self, bus: WireEventBus) -> None:
        """Async subscriber coroutines should be awaited."""
        received: list[WireEvent] = []

        async def handler(event: WireEvent) -> None:
            received.append(event)

        bus.subscribe("turn_begin", handler)
        await bus.publish(TurnBeginEvent(user_input="async"))

        assert len(received) == 1
        assert received[0].user_input == "async"

    @pytest.mark.asyncio
    async def test_subscriber_error_isolated(self, bus: WireEventBus) -> None:
        """Errors in one subscriber should not affect others."""
        received: list[WireEvent] = []

        def bad_handler(_event: WireEvent) -> None:
            raise RuntimeError("boom")

        def good_handler(event: WireEvent) -> None:
            received.append(event)

        bus.subscribe("turn_begin", bad_handler)
        bus.subscribe("turn_begin", good_handler)
        await bus.publish(TurnBeginEvent(user_input="test"))

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_event_count(self, bus: WireEventBus) -> None:
        """get_event_count should track total published events."""
        assert bus.get_event_count() == 0
        await bus.publish(TurnBeginEvent())
        await bus.publish(TurnEndEvent())
        assert bus.get_event_count() == 2

    @pytest.mark.asyncio
    async def test_get_recent_events(self, bus: WireEventBus) -> None:
        """get_recent_events should return recent events."""
        for i in range(5):
            await bus.publish(TurnBeginEvent(user_input=f"msg{i}"))

        events = bus.get_recent_events(limit=3)
        assert len(events) == 3
        assert events[-1].user_input == "msg4"

    @pytest.mark.asyncio
    async def test_get_recent_events_by_type(self, bus: WireEventBus) -> None:
        """get_recent_events should filter by event type."""
        await bus.publish(TurnBeginEvent(user_input="a"))
        await bus.publish(TurnEndEvent())
        await bus.publish(TurnBeginEvent(user_input="b"))

        events = bus.get_recent_events(event_type="turn_begin")
        assert len(events) == 2
        assert all(e.event_type == "turn_begin" for e in events)

    @pytest.mark.asyncio
    async def test_persistence(self, bus: WireEventBus, tmp_path: Path) -> None:
        """Events should be persisted to JSONL file."""
        await bus.publish(TurnBeginEvent(user_input="persisted"))

        log_file = tmp_path / "session" / "wire_events.jsonl"
        assert log_file.exists()

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "turn_begin"
        assert data["user_input"] == "persisted"

    @pytest.mark.asyncio
    async def test_persistence_no_session_dir(self, tmp_path: Path) -> None:
        """Publishing without a session dir should not error."""
        bus_no_dir = WireEventBus(session_dir=None)
        await bus_no_dir.publish(TurnBeginEvent(user_input="no_dir"))
        assert bus_no_dir.get_event_count() == 1

    @pytest.mark.asyncio
    async def test_concurrent_publish(self, bus: WireEventBus) -> None:
        """Concurrent publishes should not corrupt the event log."""

        async def pub(i: int) -> None:
            await bus.publish(TurnBeginEvent(user_input=f"msg{i}"))

        await asyncio.gather(*(pub(i) for i in range(20)))
        assert bus.get_event_count() == 20

    def test_subscribe_returns_token(self, bus: WireEventBus) -> None:
        """subscribe() should return a string token."""

        def handler(_event: WireEvent) -> None:
            pass

        token = bus.subscribe("test", handler)
        assert isinstance(token, str)
        assert len(token) == 8
