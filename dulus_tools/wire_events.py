"""Wire Protocol Events - Event system for multi-client sync."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class WireEvent:
    """Base wire event for the multi-client sync protocol.

    All wire events inherit from this base class and share common
    attributes like event_type, timestamp, payload, and event_id.
    """

    event_type: str = ""
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class TurnBeginEvent(WireEvent):
    """Signals the start of a new agent turn."""

    user_input: str = ""

    def __post_init__(self) -> None:
        self.event_type = "turn_begin"


@dataclass
class TurnEndEvent(WireEvent):
    """Signals the end of the current agent turn."""

    def __post_init__(self) -> None:
        self.event_type = "turn_end"


@dataclass
class StepBeginEvent(WireEvent):
    """Signals the start of a new agent step."""

    step_number: int = 0

    def __post_init__(self) -> None:
        self.event_type = "step_begin"


@dataclass
class StepEndEvent(WireEvent):
    """Signals the end of the current agent step."""

    step_number: int = 0

    def __post_init__(self) -> None:
        self.event_type = "step_end"


@dataclass
class ToolCallEvent(WireEvent):
    """Signals that a tool call was executed."""

    tool_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_type = "tool_call"


@dataclass
class CompactionBeginEvent(WireEvent):
    """Signals that context compaction has started."""

    def __post_init__(self) -> None:
        self.event_type = "compaction_begin"


@dataclass
class CompactionEndEvent(WireEvent):
    """Signals that context compaction has completed."""

    def __post_init__(self) -> None:
        self.event_type = "compaction_end"


class WireEventBus:
    """Event bus for wire protocol events.

    Manages event publication, subscription, and persistent logging
    for the multi-client wire protocol. Supports async subscribers,
    wildcard subscriptions, and JSONL-based event persistence.

    Example:
        bus = WireEventBus(session_dir="/tmp/session")

        def on_turn(event):
            print(f"Turn started: {event.user_input}")

        token = bus.subscribe("turn_begin", on_turn)
        await bus.publish(TurnBeginEvent(user_input="hello"))
        bus.unsubscribe(token)
    """

    def __init__(self, session_dir: Optional[str] = None) -> None:
        self._subscribers: Dict[str, List[tuple[str, Callable]]] = {}
        self._session_dir: Optional[Path] = Path(session_dir) if session_dir else None
        self._event_log: List[WireEvent] = []
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, callback: Callable) -> str:
        """Subscribe to events of a given type.

        Args:
            event_type: The event type to subscribe to, or "*" for all events.
            callback: Function or coroutine to call when events are published.

        Returns:
            A subscription token for later unsubscribe.
        """
        token = str(uuid.uuid4())[:8]
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append((token, callback))
        return token

    def unsubscribe(self, token: str) -> None:
        """Unsubscribe using the token returned from subscribe()."""
        for event_type, subs in self._subscribers.items():
            self._subscribers[event_type] = [(t, cb) for t, cb in subs if t != token]

    async def publish(self, event: WireEvent) -> None:
        """Publish an event to all subscribers and persist to disk.

        Args:
            event: The WireEvent (or subclass) to publish.
        """
        async with self._lock:
            self._event_log.append(event)

            # Notify subscribers for this specific event type
            subs = self._subscribers.get(event.event_type, [])
            for _token, callback in subs:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception:
                    # Don't let subscriber errors break the bus
                    pass

            # Notify wildcard subscribers
            wildcards = self._subscribers.get("*", [])
            for _token, callback in wildcards:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception:
                    pass

            # Persist to disk
            if self._session_dir:
                await self._persist_event(event)

    async def _persist_event(self, event: WireEvent) -> None:
        """Append a single event to the JSONL log file."""
        if not self._session_dir:
            return
        log_file = self._session_dir / "wire_events.jsonl"
        try:
            # Ensure parent directory exists
            self._session_dir.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event), default=str) + "\n")
        except Exception:
            # Silently ignore persistence failures
            pass

    def get_recent_events(
        self, event_type: Optional[str] = None, limit: int = 50
    ) -> List[WireEvent]:
        """Get recent events, optionally filtered by type.

        Args:
            event_type: Filter to this event type, or None for all.
            limit: Maximum number of events to return.

        Returns:
            List of WireEvent objects, newest last.
        """
        events = self._event_log
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def get_event_count(self) -> int:
        """Return the total number of events processed."""
        return len(self._event_log)
