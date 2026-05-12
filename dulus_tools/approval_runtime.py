"""ApprovalRuntime - Full approval system with events, subscribers, and timeout support."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ApprovalRequest:
    """Represents a request for user approval.

    Attributes:
        id: Unique identifier for this request.
        tool_call_id: The ID of the tool call being approved.
        sender: Who/what is requesting approval.
        action: The action being requested.
        description: Human-readable description of the action.
        display: Optional display blocks for rich rendering.
        source_kind: Source type ("tool_call", "background_agent", "user").
        source_id: Identifier of the source entity.
        created_at: Unix timestamp when the request was created.
    """

    id: str
    tool_call_id: str
    sender: str
    action: str
    description: str
    display: list[dict] = field(default_factory=list)
    source_kind: str = "tool_call"  # "tool_call" | "background_agent" | "user"
    source_id: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class ApprovalResponse:
    """Represents a response to an approval request.

    Attributes:
        request_id: The ID of the request being responded to.
        response: The response type ("approve" or "reject").
        feedback: Optional feedback text from the approver.
        resolved_at: Unix timestamp when the response was given.
    """

    request_id: str
    response: str  # "approve" | "reject"
    feedback: str = ""
    resolved_at: float = field(default_factory=time.time)


class ApprovalRuntime:
    """Runtime for managing approval requests with events and subscribers.

    Supports:
    - Creating and tracking approval requests
    - Waiting for responses with optional timeout
    - Event subscribers for "request_created" and "request_resolved"
    - Cancelling requests by source
    - Listing pending requests
    """

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._responses: dict[str, ApprovalResponse] = {}
        self._waiters: dict[str, asyncio.Future[ApprovalResponse]] = {}
        self._subscribers: dict[str, Callable[[str, ApprovalRequest | ApprovalResponse], None]] = {}

    # ── Request lifecycle ────────────────────────────────────────────────────

    def create_request(
        self,
        *,
        tool_call_id: str = "",
        sender: str = "",
        action: str = "",
        description: str = "",
        display: list[dict] | None = None,
        source_kind: str = "tool_call",
        source_id: str = "",
        request_id: str | None = None,
    ) -> ApprovalRequest:
        """Create a new approval request and notify subscribers.

        Args:
            tool_call_id: The ID of the tool call being approved.
            sender: Who/what is requesting approval.
            action: The action being requested.
            description: Human-readable description.
            display: Optional display blocks.
            source_kind: Source type ("tool_call", "background_agent", "user").
            source_id: Identifier of the source entity.
            request_id: Optional explicit request ID (auto-generated if None).

        Returns:
            The created ApprovalRequest.
        """
        req_id = request_id or uuid.uuid4().hex[:12]
        request = ApprovalRequest(
            id=req_id,
            tool_call_id=tool_call_id,
            sender=sender,
            action=action,
            description=description,
            display=display or [],
            source_kind=source_kind,
            source_id=source_id,
        )
        self._requests[req_id] = request
        self._notify("request_created", request)
        return request

    async def wait_for_response(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> tuple[str, str]:
        """Wait for a response to the given request.

        Args:
            request_id: The ID of the request to wait for.
            timeout: Optional timeout in seconds.

        Returns:
            A tuple of (response, feedback) where response is "approve" or "reject".

        Raises:
            TimeoutError: If the timeout expires before a response.
            KeyError: If the request_id is not found.
        """
        if request_id not in self._requests:
            raise KeyError(f"Request {request_id!r} not found")

        # If already resolved, return immediately
        if request_id in self._responses:
            resp = self._responses[request_id]
            return (resp.response, resp.feedback)

        # Create a future to wait on
        fut: asyncio.Future[ApprovalResponse] = asyncio.get_event_loop().create_future()
        self._waiters[request_id] = fut

        try:
            if timeout is not None:
                resp = await asyncio.wait_for(fut, timeout=timeout)
            else:
                resp = await fut
            return (resp.response, resp.feedback)
        except asyncio.TimeoutError:
            # Clean up the waiter on timeout
            self._waiters.pop(request_id, None)
            raise TimeoutError(f"Approval request {request_id!r} timed out after {timeout}s")

    def resolve(
        self,
        request_id: str,
        response: str,
        feedback: str = "",
    ) -> bool:
        """Resolve an approval request with a response.

        Args:
            request_id: The ID of the request to resolve.
            response: "approve" or "reject".
            feedback: Optional feedback text.

        Returns:
            True if the request was found and resolved, False otherwise.
        """
        if request_id not in self._requests:
            return False

        resp = ApprovalResponse(
            request_id=request_id,
            response=response,
            feedback=feedback,
        )
        self._responses[request_id] = resp

        # Notify any waiter
        fut = self._waiters.pop(request_id, None)
        if fut is not None and not fut.done():
            fut.set_result(resp)

        # Notify subscribers
        self._notify("request_resolved", resp)
        return True

    # ── Event system ─────────────────────────────────────────────────────────

    def subscribe(
        self,
        callback: Callable[[str, ApprovalRequest | ApprovalResponse], None],
    ) -> str:
        """Subscribe to approval events.

        The callback receives (event_type, data) where event_type is
        "request_created" or "request_resolved".

        Args:
            callback: Function to call when events occur.

        Returns:
            A token that can be used to unsubscribe.
        """
        token = uuid.uuid4().hex[:8]
        self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: str) -> None:
        """Unsubscribe from approval events.

        Args:
            token: The subscription token returned by subscribe().
        """
        self._subscribers.pop(token, None)

    def _notify(
        self,
        event_type: str,
        data: ApprovalRequest | ApprovalResponse,
    ) -> None:
        """Notify all subscribers of an event."""
        for callback in list(self._subscribers.values()):
            try:
                callback(event_type, data)
            except Exception:
                # Don't let subscriber errors break the flow
                pass

    # ── Query methods ────────────────────────────────────────────────────────

    def list_pending(self) -> list[ApprovalRequest]:
        """Return all pending (unresolved) approval requests.

        Returns:
            List of pending ApprovalRequest objects.
        """
        resolved_ids = set(self._responses.keys())
        return [req for req in self._requests.values() if req.id not in resolved_ids]

    def cancel_by_source(self, source_kind: str, source_id: str) -> int:
        """Cancel all pending requests from a given source.

        Args:
            source_kind: The source kind to match (e.g., "background_agent").
            source_id: The source ID to match.

        Returns:
            Number of requests cancelled.
        """
        cancelled = 0
        for req in list(self._requests.values()):
            if req.source_kind == source_kind and req.source_id == source_id:
                if req.id not in self._responses:
                    self.resolve(req.id, "reject", f"Cancelled: source {source_kind}/{source_id} stopped")
                    cancelled += 1
        return cancelled

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Get a request by ID.

        Args:
            request_id: The request ID.

        Returns:
            The ApprovalRequest or None if not found.
        """
        return self._requests.get(request_id)

    def clear_resolved(self) -> int:
        """Remove all resolved requests and responses from memory.

        Returns:
            Number of items cleared.
        """
        resolved_ids = set(self._responses.keys())
        for rid in resolved_ids:
            self._requests.pop(rid, None)
        count = len(self._responses)
        self._responses.clear()
        return count
