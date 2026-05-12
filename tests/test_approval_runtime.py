"""Tests for ApprovalRuntime."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path for dulus.* imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from dulus_tools.approval_runtime import ApprovalRequest, ApprovalResponse, ApprovalRuntime


# ── ApprovalRequest Tests ────────────────────────────────────────────────────


class TestApprovalRequest:
    """Test suite for ApprovalRequest dataclass."""

    def test_create_minimal(self):
        """Create a minimal ApprovalRequest."""
        req = ApprovalRequest(
            id="test-1",
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file",
        )
        assert req.id == "test-1"
        assert req.tool_call_id == "tc-1"
        assert req.sender == "agent"
        assert req.action == "Write"
        assert req.description == "Write to file"
        assert req.display == []
        assert req.source_kind == "tool_call"
        assert req.source_id == ""

    def test_create_full(self):
        """Create an ApprovalRequest with all fields."""
        req = ApprovalRequest(
            id="test-2",
            tool_call_id="tc-2",
            sender="bg-agent",
            action="Bash",
            description="Run command",
            display=[{"type": "shell", "command": "ls"}],
            source_kind="background_agent",
            source_id="bg-1",
        )
        assert req.source_kind == "background_agent"
        assert req.source_id == "bg-1"
        assert len(req.display) == 1

    def test_default_created_at(self):
        """created_at should have a default value."""
        import time
        before = time.time()
        req = ApprovalRequest(id="t", tool_call_id="t", sender="s", action="a", description="d")
        after = time.time()
        assert before <= req.created_at <= after


# ── ApprovalResponse Tests ───────────────────────────────────────────────────


class TestApprovalResponse:
    """Test suite for ApprovalResponse dataclass."""

    def test_create(self):
        """Create an ApprovalResponse."""
        resp = ApprovalResponse(
            request_id="req-1",
            response="approve",
            feedback="Looks good",
        )
        assert resp.request_id == "req-1"
        assert resp.response == "approve"
        assert resp.feedback == "Looks good"


# ── ApprovalRuntime Tests ────────────────────────────────────────────────────


class TestApprovalRuntime:
    """Test suite for ApprovalRuntime."""

    def test_create_request(self):
        """Create a request and verify it's stored."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        assert req.id is not None
        assert req.action == "Write"
        assert len(runtime.list_pending()) == 1

    def test_create_request_with_explicit_id(self):
        """Create a request with an explicit ID."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            request_id="my-custom-id",
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        assert req.id == "my-custom-id"

    def test_list_pending_empty(self):
        """list_pending should return empty list when no requests."""
        runtime = ApprovalRuntime()
        assert runtime.list_pending() == []

    def test_list_pending_after_resolve(self):
        """Resolved requests should not appear in list_pending."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        assert len(runtime.list_pending()) == 1
        runtime.resolve(req.id, "approve")
        assert len(runtime.list_pending()) == 0

    def test_resolve_approve(self):
        """Resolve a request with approve."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        result = runtime.resolve(req.id, "approve")
        assert result is True

    def test_resolve_reject(self):
        """Resolve a request with reject."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        result = runtime.resolve(req.id, "reject", "Not allowed")
        assert result is True

    def test_resolve_nonexistent(self):
        """Resolving a nonexistent request should return False."""
        runtime = ApprovalRuntime()
        result = runtime.resolve("nonexistent", "approve")
        assert result is False

    def test_get_request(self):
        """Get a request by ID."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        fetched = runtime.get_request(req.id)
        assert fetched is not None
        assert fetched.id == req.id

    def test_get_request_nonexistent(self):
        """Get a nonexistent request should return None."""
        runtime = ApprovalRuntime()
        assert runtime.get_request("nonexistent") is None

    def test_subscribe_and_notify(self):
        """Subscribe to events and receive notifications."""
        runtime = ApprovalRuntime()
        events: list[tuple[str, ApprovalRequest | ApprovalResponse]] = []

        def callback(event_type: str, data: ApprovalRequest | ApprovalResponse) -> None:
            events.append((event_type, data))

        token = runtime.subscribe(callback)
        assert token is not None

        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        runtime.resolve(req.id, "approve")

        assert len(events) == 2
        assert events[0][0] == "request_created"
        assert events[1][0] == "request_resolved"

    def test_unsubscribe(self):
        """Unsubscribe should stop receiving events."""
        runtime = ApprovalRuntime()
        events: list[tuple[str, ApprovalRequest | ApprovalResponse]] = []

        def callback(event_type: str, data: ApprovalRequest | ApprovalResponse) -> None:
            events.append((event_type, data))

        token = runtime.subscribe(callback)
        runtime.unsubscribe(token)

        runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        assert len(events) == 0

    def test_cancel_by_source(self):
        """Cancel requests by source."""
        runtime = ApprovalRuntime()

        # Create requests from different sources
        req1 = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write file",
            source_kind="background_agent",
            source_id="bg-1",
        )
        req2 = runtime.create_request(
            tool_call_id="tc-2",
            sender="agent",
            action="Read",
            description="Read file",
            source_kind="background_agent",
            source_id="bg-1",
        )
        req3 = runtime.create_request(
            tool_call_id="tc-3",
            sender="agent",
            action="Bash",
            description="Run command",
            source_kind="background_agent",
            source_id="bg-2",
        )

        assert len(runtime.list_pending()) == 3
        cancelled = runtime.cancel_by_source("background_agent", "bg-1")
        assert cancelled == 2
        assert len(runtime.list_pending()) == 1

    def test_cancel_by_source_no_match(self):
        """Cancel with no matching source should return 0."""
        runtime = ApprovalRuntime()
        runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write file",
            source_kind="tool_call",
            source_id="tc-1",
        )
        cancelled = runtime.cancel_by_source("background_agent", "bg-1")
        assert cancelled == 0

    def test_clear_resolved(self):
        """Clear resolved requests from memory."""
        runtime = ApprovalRuntime()
        req1 = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write file",
        )
        runtime.create_request(
            tool_call_id="tc-2",
            sender="agent",
            action="Read",
            description="Read file",
        )
        runtime.resolve(req1.id, "approve")
        assert len(runtime.list_pending()) == 1
        cleared = runtime.clear_resolved()
        assert cleared == 1


# ── Async Tests ──────────────────────────────────────────────────────────────


class TestApprovalRuntimeAsync:
    """Async test suite for ApprovalRuntime."""

    @pytest.mark.asyncio
    async def test_wait_for_response(self):
        """Wait for a response and receive it."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )

        # Resolve in the background after a short delay
        async def resolve_later():
            await asyncio.sleep(0.05)
            runtime.resolve(req.id, "approve", "Good to go")

        asyncio.create_task(resolve_later())
        response, feedback = await runtime.wait_for_response(req.id)
        assert response == "approve"
        assert feedback == "Good to go"

    @pytest.mark.asyncio
    async def test_wait_for_response_already_resolved(self):
        """Wait for an already-resolved request should return immediately."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )
        runtime.resolve(req.id, "reject", "Not allowed")
        response, feedback = await runtime.wait_for_response(req.id)
        assert response == "reject"
        assert feedback == "Not allowed"

    @pytest.mark.asyncio
    async def test_wait_for_response_timeout(self):
        """Wait with a timeout that expires should raise TimeoutError."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )

        with pytest.raises(TimeoutError):
            await runtime.wait_for_response(req.id, timeout=0.05)

    @pytest.mark.asyncio
    async def test_wait_for_response_not_found(self):
        """Wait for a nonexistent request should raise KeyError."""
        runtime = ApprovalRuntime()
        with pytest.raises(KeyError):
            await runtime.wait_for_response("nonexistent")

    @pytest.mark.asyncio
    async def test_wait_for_response_with_reject(self):
        """Wait for a response that is rejected."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Bash",
            description="Run rm -rf /",
        )

        async def reject_later():
            await asyncio.sleep(0.05)
            runtime.resolve(req.id, "reject", "Too dangerous")

        asyncio.create_task(reject_later())
        response, feedback = await runtime.wait_for_response(req.id)
        assert response == "reject"
        assert feedback == "Too dangerous"

    @pytest.mark.asyncio
    async def test_multiple_waiters_not_supported(self):
        """Only one waiter per request is supported; first gets the result."""
        runtime = ApprovalRuntime()
        req = runtime.create_request(
            tool_call_id="tc-1",
            sender="agent",
            action="Write",
            description="Write to file.txt",
        )

        async def resolve_later():
            await asyncio.sleep(0.05)
            runtime.resolve(req.id, "approve")

        asyncio.create_task(resolve_later())
        response, _ = await runtime.wait_for_response(req.id)
        assert response == "approve"
