"""SteerInput - Allow steering agent execution with follow-up input.

Provides a mechanism for users to inject follow-up input ("steer" commands)
during agent execution. This enables real-time course correction without
waiting for the current turn to complete.

The SteerInput class uses an asyncio.Queue to buffer steer inputs, which can
be consumed by the agent loop at strategic checkpoints.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SteerInput:
    """Manages steer inputs during agent execution.

    Steer inputs are user messages injected mid-execution to redirect
    the agent's course. They are stored in an asyncio.Queue and consumed
    by the agent loop at decision points.

    Attributes:
        _enabled: Whether steer input collection is active.
    """

    _queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    _enabled: bool = True

    async def add_steer(self, user_input: str) -> None:
        """Add a steer input to the queue.

        Args:
            user_input: The user's follow-up message to inject.

        Raises:
            ValueError: If user_input is empty or not a string.
        """
        if not isinstance(user_input, str):
            raise TypeError("user_input must be a string")
        if not user_input.strip():
            raise ValueError("user_input cannot be empty")
        await self._queue.put(user_input.strip())

    async def get_next_steer(self, timeout: float = 0.1) -> Optional[str]:
        """Get the next steer input if available.

        Args:
            timeout: Maximum seconds to wait for an input.

        Returns:
            The next steer input string, or None if timeout expires.
        """
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def get_next_steer_sync(self, timeout: float = 0.1) -> Optional[str]:
        """Synchronous version of get_next_steer.

        Args:
            timeout: Maximum seconds to wait for an input.

        Returns:
            The next steer input string, or None if timeout expires.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, use a different approach
                if not self._queue.empty():
                    return self._queue.get_nowait()
                return None
            return loop.run_until_complete(self.get_next_steer(timeout))
        except RuntimeError:
            # No event loop running
            return None

    def has_pending(self) -> bool:
        """Check if there are steer inputs waiting to be processed.

        Returns:
            True if the queue is not empty.
        """
        return not self._queue.empty()

    def enable(self) -> None:
        """Enable steer input collection."""
        self._enabled = True

    def disable(self) -> None:
        """Disable steer input collection."""
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """Whether steer input collection is currently enabled."""
        return self._enabled

    def clear(self) -> int:
        """Clear all pending steer inputs.

        Returns:
            Number of items cleared.
        """
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

    @property
    def pending_count(self) -> int:
        """Number of steer inputs currently queued.

        Returns:
            The queue size.
        """
        return self._queue.qsize()


# ── Module-level singleton for shared access ─────────────────────────────────

_default_steer_input: Optional[SteerInput] = None


def get_steer_input() -> SteerInput:
    """Get the default SteerInput singleton.

    Returns:
        The shared SteerInput instance, creating it if needed.
    """
    global _default_steer_input
    if _default_steer_input is None:
        _default_steer_input = SteerInput()
    return _default_steer_input


def reset_steer_input() -> None:
    """Reset the default SteerInput singleton."""
    global _default_steer_input
    _default_steer_input = None
