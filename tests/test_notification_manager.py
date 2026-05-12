"""Tests for NotificationManager."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure project root is on path for dulus.* imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from dulus_tools.notification_manager import NotificationEvent, NotificationManager


# ── NotificationEvent Tests ─────────────────────────────────────────────────


class TestNotificationEvent:
    """Test suite for NotificationEvent dataclass."""

    def test_create_minimal(self):
        """Create a minimal NotificationEvent."""
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        assert event.id == "ne-1"
        assert event.category == "task"
        assert event.severity == "info"  # default
        assert event.dedupe_key == ""  # default
        assert event.targets == []  # default

    def test_create_full(self):
        """Create a NotificationEvent with all fields."""
        event = NotificationEvent(
            id="ne-2",
            category="approval",
            type="requested",
            source_kind="agent",
            source_id="a-1",
            title="Approval needed",
            body="Please approve this action",
            severity="warning",
            payload={"tool": "Bash"},
            dedupe_key="approval-bash-1",
            targets=["webchat", "telegram"],
        )
        assert event.severity == "warning"
        assert event.payload == {"tool": "Bash"}
        assert event.dedupe_key == "approval-bash-1"
        assert event.targets == ["webchat", "telegram"]

    def test_to_dict(self):
        """Serialize to dict."""
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        d = event.to_dict()
        assert d["id"] == "ne-1"
        assert d["category"] == "task"
        assert "created_at" in d

    def test_from_dict(self):
        """Deserialize from dict."""
        data = {
            "id": "ne-1",
            "category": "task",
            "type": "created",
            "source_kind": "background_task",
            "source_id": "bt-1",
            "title": "Task created",
            "body": "A new task was created",
            "severity": "info",
            "payload": {},
            "dedupe_key": "",
            "targets": [],
            "created_at": 1234567890.0,
            "claimed_at": 0.0,
            "claimed_by": "",
            "acked_at": 0.0,
        }
        event = NotificationEvent.from_dict(data)
        assert event.id == "ne-1"
        assert event.created_at == 1234567890.0

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict should ignore unknown fields."""
        data = {
            "id": "ne-1",
            "category": "task",
            "type": "created",
            "source_kind": "background_task",
            "source_id": "bt-1",
            "title": "Task created",
            "body": "A new task was created",
            "unknown_field": "should_be_ignored",
        }
        event = NotificationEvent.from_dict(data)
        assert event.id == "ne-1"


# ── NotificationManager Tests ────────────────────────────────────────────────


class TestNotificationManager:
    """Test suite for NotificationManager."""

    @pytest.fixture
    def tmp_root(self, tmp_path: Path) -> Path:
        """Create a temporary root directory."""
        return tmp_path

    def test_init_creates_store(self, tmp_root: Path):
        """Initialization should create the notifications directory."""
        mgr = NotificationManager(tmp_root)
        assert (tmp_root / "notifications").exists()
        assert (tmp_root / "notifications").is_dir()

    def test_new_id(self, tmp_root: Path):
        """new_id should generate unique IDs."""
        mgr = NotificationManager(tmp_root)
        id1 = mgr.new_id()
        id2 = mgr.new_id()
        assert id1 != id2
        assert len(id1) == 12  # uuid.hex[:12]

    def test_publish(self, tmp_root: Path):
        """Publish a notification."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        result = mgr.publish(event)
        assert result["status"] == "published"
        assert result["deduplicated"] is False
        assert result["id"] is not None

    def test_publish_with_explicit_id(self, tmp_root: Path):
        """Publish a notification with an explicit ID."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="my-id",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        result = mgr.publish(event)
        assert result["id"] == "my-id"

    def test_deduplication(self, tmp_root: Path):
        """Publishing with same dedupe_key should return existing."""
        mgr = NotificationManager(tmp_root)
        event1 = NotificationEvent(
            id="",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
            dedupe_key="task-bg-1",
        )
        result1 = mgr.publish(event1)
        assert result1["status"] == "published"
        assert result1["deduplicated"] is False

        event2 = NotificationEvent(
            id="",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created again",
            body="Duplicate",
            dedupe_key="task-bg-1",
        )
        result2 = mgr.publish(event2)
        assert result2["status"] == "existing"
        assert result2["deduplicated"] is True
        assert result2["id"] == result1["id"]

    def test_no_dedup_without_key(self, tmp_root: Path):
        """Publishing without dedupe_key should always create new."""
        mgr = NotificationManager(tmp_root)
        event1 = NotificationEvent(
            id="",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        result1 = mgr.publish(event1)
        event2 = NotificationEvent(
            id="",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        result2 = mgr.publish(event2)
        assert result1["status"] == "published"
        assert result2["status"] == "published"
        assert result1["id"] != result2["id"]

    def test_claim_for_sink(self, tmp_root: Path):
        """Claim pending notifications for a sink."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)

        claimed = mgr.claim_for_sink("webchat")
        assert len(claimed) == 1
        assert claimed[0]["id"] == "ne-1"
        assert claimed[0]["claimed_by"] == "webchat"
        assert claimed[0]["claimed_at"] > 0

    def test_claim_respects_targets(self, tmp_root: Path):
        """Claim should only return notifications targeting the sink."""
        mgr = NotificationManager(tmp_root)
        event1 = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task 1",
            body="Task 1",
            targets=["webchat"],
        )
        event2 = NotificationEvent(
            id="ne-2",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-2",
            title="Task 2",
            body="Task 2",
            targets=["telegram"],
        )
        mgr.publish(event1)
        mgr.publish(event2)

        claimed = mgr.claim_for_sink("webchat")
        assert len(claimed) == 1
        assert claimed[0]["id"] == "ne-1"

    def test_claim_empty(self, tmp_root: Path):
        """Claim with no pending notifications should return empty."""
        mgr = NotificationManager(tmp_root)
        claimed = mgr.claim_for_sink("webchat")
        assert claimed == []

    def test_claim_limit(self, tmp_root: Path):
        """Claim should respect the limit."""
        mgr = NotificationManager(tmp_root)
        for i in range(10):
            event = NotificationEvent(
                id=f"ne-{i}",
                category="task",
                type="created",
                source_kind="background_task",
                source_id=f"bt-{i}",
                title=f"Task {i}",
                body=f"Task {i}",
            )
            mgr.publish(event)

        claimed = mgr.claim_for_sink("webchat", limit=3)
        assert len(claimed) == 3

    def test_ack(self, tmp_root: Path):
        """Acknowledge a claimed notification."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)
        mgr.claim_for_sink("webchat")

        result = mgr.ack("webchat", "ne-1")
        assert result["status"] == "acked"

    def test_ack_not_found(self, tmp_root: Path):
        """Ack a nonexistent notification."""
        mgr = NotificationManager(tmp_root)
        result = mgr.ack("webchat", "nonexistent")
        assert result["status"] == "not_found"

    def test_ack_not_claimed_by_you(self, tmp_root: Path):
        """Ack a notification claimed by another sink."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)
        mgr.claim_for_sink("telegram")

        result = mgr.ack("webchat", "ne-1")
        assert result["status"] == "not_claimed_by_you"

    def test_ack_already_acked(self, tmp_root: Path):
        """Ack a notification twice should return already_acked."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)
        mgr.claim_for_sink("webchat")
        mgr.ack("webchat", "ne-1")

        result = mgr.ack("webchat", "ne-1")
        assert result["status"] == "already_acked"

    def test_has_pending_for_sink(self, tmp_root: Path):
        """Check if there are pending notifications for a sink."""
        mgr = NotificationManager(tmp_root)
        assert mgr.has_pending_for_sink("webchat") is False

        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
            targets=["webchat"],
        )
        mgr.publish(event)
        assert mgr.has_pending_for_sink("webchat") is True

    def test_recover_stale_claims(self, tmp_root: Path):
        """Recover notifications with stale claims."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)
        mgr.claim_for_sink("webchat")

        # Manually backdate the claim to make it stale
        notification = mgr.get("ne-1")
        assert notification is not None
        notification.claimed_at = time.time() - 600  # 10 minutes ago

        recovered = mgr.recover(stale_seconds=300)
        assert recovered == 1

        # Notification should be back in pending
        notification = mgr.get("ne-1")
        assert notification is not None
        assert notification.claimed_at == 0.0
        assert notification.claimed_by == ""

    def test_recover_no_stale(self, tmp_root: Path):
        """Recover with no stale claims should return 0."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)
        mgr.claim_for_sink("webchat")

        recovered = mgr.recover(stale_seconds=300)
        assert recovered == 0  # Claim is fresh

    def test_delete(self, tmp_root: Path):
        """Delete a notification."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)
        assert mgr.get("ne-1") is not None

        result = mgr.delete("ne-1")
        assert result is True
        assert mgr.get("ne-1") is None

    def test_delete_nonexistent(self, tmp_root: Path):
        """Delete a nonexistent notification should return False."""
        mgr = NotificationManager(tmp_root)
        result = mgr.delete("nonexistent")
        assert result is False

    def test_list_all(self, tmp_root: Path):
        """List all notifications."""
        mgr = NotificationManager(tmp_root)
        event1 = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task 1",
            body="Task 1",
        )
        event2 = NotificationEvent(
            id="ne-2",
            category="task",
            type="completed",
            source_kind="background_task",
            source_id="bt-1",
            title="Task 2",
            body="Task 2",
        )
        mgr.publish(event1)
        mgr.publish(event2)

        all_notifications = mgr.list_all()
        assert len(all_notifications) == 2

    def test_list_pending(self, tmp_root: Path):
        """List only pending notifications."""
        mgr = NotificationManager(tmp_root)
        event1 = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task 1",
            body="Task 1",
        )
        event2 = NotificationEvent(
            id="ne-2",
            category="task",
            type="completed",
            source_kind="background_task",
            source_id="bt-2",
            title="Task 2",
            body="Task 2",
        )
        mgr.publish(event1)
        mgr.publish(event2)
        mgr.claim_for_sink("webchat")  # Claims both
        mgr.ack("webchat", "ne-1")  # Only ack one

        pending = mgr.list_pending()
        assert len(pending) == 0  # Both are either claimed or acked

    def test_persistence(self, tmp_root: Path):
        """Notifications should be persisted to disk."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task created",
            body="A new task was created",
        )
        mgr.publish(event)

        # Check file exists
        file_path = tmp_root / "notifications" / "ne-1.json"
        assert file_path.exists()

        # Check file content
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["id"] == "ne-1"
        assert data["title"] == "Task created"

    def test_load_from_disk(self, tmp_root: Path):
        """Notifications should be loaded from disk on init."""
        # Pre-create a notification file
        store = tmp_root / "notifications"
        store.mkdir(parents=True, exist_ok=True)
        data = {
            "id": "ne-persisted",
            "category": "task",
            "type": "created",
            "source_kind": "background_task",
            "source_id": "bt-1",
            "title": "Persisted task",
            "body": "This was persisted",
            "severity": "info",
            "payload": {},
            "dedupe_key": "",
            "targets": [],
            "created_at": 1234567890.0,
            "claimed_at": 0.0,
            "claimed_by": "",
            "acked_at": 0.0,
        }
        (store / "ne-persisted.json").write_text(json.dumps(data), encoding="utf-8")

        mgr = NotificationManager(tmp_root)
        notification = mgr.get("ne-persisted")
        assert notification is not None
        assert notification.title == "Persisted task"

    def test_load_from_disk_with_dedupe(self, tmp_root: Path):
        """Deduplication index should be rebuilt from disk."""
        store = tmp_root / "notifications"
        store.mkdir(parents=True, exist_ok=True)
        data = {
            "id": "ne-dedup",
            "category": "task",
            "type": "created",
            "source_kind": "background_task",
            "source_id": "bt-1",
            "title": "Dedup task",
            "body": "This has a dedupe key",
            "severity": "info",
            "payload": {},
            "dedupe_key": "my-dedup-key",
            "targets": [],
            "created_at": 1234567890.0,
            "claimed_at": 0.0,
            "claimed_by": "",
            "acked_at": 0.0,
        }
        (store / "ne-dedup.json").write_text(json.dumps(data), encoding="utf-8")

        mgr = NotificationManager(tmp_root)
        # Publishing with same dedupe key should return existing
        event = NotificationEvent(
            id="ne-new",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="New task",
            body="New",
            dedupe_key="my-dedup-key",
        )
        result = mgr.publish(event)
        assert result["status"] == "existing"
        assert result["id"] == "ne-dedup"

    def test_delete_cleans_up_dedupe(self, tmp_root: Path):
        """Deleting a notification should clean up the dedupe index."""
        mgr = NotificationManager(tmp_root)
        event = NotificationEvent(
            id="ne-1",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task 1",
            body="Task 1",
            dedupe_key="dedup-1",
        )
        mgr.publish(event)
        mgr.delete("ne-1")

        # Publishing again should work
        event2 = NotificationEvent(
            id="ne-2",
            category="task",
            type="created",
            source_kind="background_task",
            source_id="bt-1",
            title="Task 2",
            body="Task 2",
            dedupe_key="dedup-1",
        )
        result = mgr.publish(event2)
        assert result["status"] == "published"
        assert result["deduplicated"] is False

    def test_load_skips_corrupted_files(self, tmp_root: Path):
        """Loading should skip corrupted JSON files."""
        store = tmp_root / "notifications"
        store.mkdir(parents=True, exist_ok=True)
        (store / "corrupted.json").write_text("not valid json", encoding="utf-8")

        mgr = NotificationManager(tmp_root)
        assert mgr.get("corrupted") is None
