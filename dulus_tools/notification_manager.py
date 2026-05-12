"""NotificationManager - Notifications with deduplication, claim/ack flow, and persistence."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class NotificationEvent:
    """Represents a notification event.

    Attributes:
        id: Unique identifier for this notification.
        category: Category of the notification (e.g., "task", "approval").
        type: Specific type within the category.
        source_kind: Source type (e.g., "background_task", "agent").
        source_id: Identifier of the source entity.
        title: Short title for the notification.
        body: Full body text of the notification.
        severity: Severity level ("success", "error", "warning", "info").
        payload: Additional structured data.
        dedupe_key: Key for deduplication (empty = no dedup).
        targets: List of sink names to deliver to.
        created_at: Unix timestamp when the notification was created.
        claimed_at: Unix timestamp when claimed (0 = unclaimed).
        claimed_by: Sink name that claimed this notification.
        acked_at: Unix timestamp when acked (0 = unacked).
    """

    id: str
    category: str
    type: str
    source_kind: str
    source_id: str
    title: str
    body: str
    severity: str = "info"  # "success" | "error" | "warning" | "info"
    payload: dict = field(default_factory=dict)
    dedupe_key: str = ""  # Empty = no dedup
    targets: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    claimed_at: float = 0.0
    claimed_by: str = ""
    acked_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationEvent:
        """Deserialize from a plain dictionary."""
        # Filter to only known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class NotificationManager:
    """Manages notifications with deduplication and multi-sink delivery.

    Features:
    - Publish notifications with optional deduplication
    - Claim notifications for specific sinks
    - Acknowledge claimed notifications
    - Persist notifications to JSON files
    - Recover stale claimed notifications
    """

    def __init__(self, root: Path, config: dict | None = None) -> None:
        """Initialize the notification manager.

        Args:
            root: Base directory for notification storage.
            config: Optional configuration dict.
        """
        self._store: Path = root / "notifications"
        self._store.mkdir(parents=True, exist_ok=True)
        self._config: dict = config or {}
        self._notifications: dict[str, NotificationEvent] = {}
        self._dedupe_index: dict[str, str] = {}  # dedupe_key -> notification_id
        self._claimed: dict[str, list[str]] = {}  # sink -> [notification_ids]
        self._load_all()

    # ── ID generation ────────────────────────────────────────────────────────

    def new_id(self) -> str:
        """Generate a new unique notification ID."""
        return uuid.uuid4().hex[:12]

    # ── Publishing ───────────────────────────────────────────────────────────

    def publish(self, event: NotificationEvent) -> dict[str, Any]:
        """Publish a notification event.

        If the event has a dedupe_key and a matching notification already
        exists, the existing notification is returned instead.

        Args:
            event: The notification event to publish.

        Returns:
            A dict with "id", "status", and "deduplicated" fields.
        """
        # Check deduplication
        if event.dedupe_key and event.dedupe_key in self._dedupe_index:
            existing_id = self._dedupe_index[event.dedupe_key]
            if existing_id in self._notifications:
                existing = self._notifications[existing_id]
                return {
                    "id": existing.id,
                    "status": "existing",
                    "deduplicated": True,
                }

        # Store the notification
        if not event.id:
            event.id = self.new_id()
        self._notifications[event.id] = event

        # Update dedupe index
        if event.dedupe_key:
            self._dedupe_index[event.dedupe_key] = event.id

        # Persist to disk
        self._persist(event)

        return {
            "id": event.id,
            "status": "published",
            "deduplicated": False,
        }

    # ── Claim/Ack flow ───────────────────────────────────────────────────────

    def claim_for_sink(self, sink: str, limit: int = 8) -> list[dict[str, Any]]:
        """Claim pending notifications for a sink.

        Notifications are claimed in order of creation (oldest first).

        Args:
            sink: The sink name claiming notifications.
            limit: Maximum number of notifications to claim.

        Returns:
            List of claimed notification dicts.
        """
        claimed: list[NotificationEvent] = []

        # Get unclaimed, unacked notifications, oldest first
        pending = sorted(
            (
                n for n in self._notifications.values()
                if n.claimed_at == 0.0 and n.acked_at == 0.0
                and (not n.targets or sink in n.targets)
            ),
            key=lambda n: n.created_at,
        )

        for notification in pending[:limit]:
            notification.claimed_at = time.time()
            notification.claimed_by = sink
            claimed.append(notification)

            # Track in-memory
            if sink not in self._claimed:
                self._claimed[sink] = []
            self._claimed[sink].append(notification.id)

            # Persist
            self._persist(notification)

        return [n.to_dict() for n in claimed]

    def ack(self, sink: str, notification_id: str) -> dict[str, Any]:
        """Acknowledge a claimed notification.

        Args:
            sink: The sink name acknowledging.
            notification_id: The notification ID to ack.

        Returns:
            A dict with "id" and "status" fields.
        """
        notification = self._notifications.get(notification_id)
        if notification is None:
            return {"id": notification_id, "status": "not_found"}

        if notification.claimed_by != sink:
            return {
                "id": notification_id,
                "status": "not_claimed_by_you",
                "claimed_by": notification.claimed_by,
            }

        if notification.acked_at > 0:
            return {"id": notification_id, "status": "already_acked"}

        notification.acked_at = time.time()
        self._persist(notification)

        # Remove from claimed tracking
        if sink in self._claimed and notification_id in self._claimed[sink]:
            self._claimed[sink].remove(notification_id)

        return {"id": notification_id, "status": "acked"}

    def has_pending_for_sink(self, sink: str) -> bool:
        """Check if there are pending notifications for a sink.

        Args:
            sink: The sink name to check.

        Returns:
            True if there are pending notifications for this sink.
        """
        return any(
            n.claimed_at == 0.0 and n.acked_at == 0.0
            and (not n.targets or sink in n.targets)
            for n in self._notifications.values()
        )

    # ── Recovery ─────────────────────────────────────────────────────────────

    def recover(self, stale_seconds: float = 300.0) -> int:
        """Recover stale claimed notifications.

        Notifications that were claimed but never acked within the stale
        threshold are released back to the pending pool.

        Args:
            stale_seconds: Time in seconds after which a claim is considered stale.

        Returns:
            Number of notifications recovered.
        """
        now = time.time()
        recovered = 0

        for notification in list(self._notifications.values()):
            if (
                notification.claimed_at > 0
                and notification.acked_at == 0.0
                and (now - notification.claimed_at) > stale_seconds
            ):
                # Release the claim
                old_sink = notification.claimed_by
                notification.claimed_at = 0.0
                notification.claimed_by = ""

                # Update tracking
                if old_sink in self._claimed and notification.id in self._claimed[old_sink]:
                    self._claimed[old_sink].remove(notification.id)

                self._persist(notification)
                recovered += 1

        return recovered

    # ── Queries ──────────────────────────────────────────────────────────────

    def list_all(self) -> list[dict[str, Any]]:
        """Return all notifications as dicts."""
        return [n.to_dict() for n in self._notifications.values()]

    def list_pending(self) -> list[dict[str, Any]]:
        """Return all pending (unclaimed, unacked) notifications."""
        return [
            n.to_dict() for n in self._notifications.values()
            if n.claimed_at == 0.0 and n.acked_at == 0.0
        ]

    def get(self, notification_id: str) -> NotificationEvent | None:
        """Get a notification by ID."""
        return self._notifications.get(notification_id)

    def delete(self, notification_id: str) -> bool:
        """Delete a notification by ID.

        Returns:
            True if the notification was found and deleted.
        """
        notification = self._notifications.pop(notification_id, None)
        if notification is None:
            return False

        # Clean up dedupe index
        if notification.dedupe_key and notification.dedupe_key in self._dedupe_index:
            if self._dedupe_index[notification.dedupe_key] == notification_id:
                del self._dedupe_index[notification.dedupe_key]

        # Clean up claimed tracking
        if notification.claimed_by:
            sink = notification.claimed_by
            if sink in self._claimed and notification_id in self._claimed[sink]:
                self._claimed[sink].remove(notification_id)

        # Delete from disk
        file_path = self._file_path(notification_id)
        if file_path.exists():
            file_path.unlink()

        return True

    # ── Persistence ──────────────────────────────────────────────────────────

    def _file_path(self, notification_id: str) -> Path:
        """Get the file path for a notification."""
        return self._store / f"{notification_id}.json"

    def _persist(self, notification: NotificationEvent) -> None:
        """Save a notification to disk."""
        file_path = self._file_path(notification.id)
        file_path.write_text(json.dumps(notification.to_dict(), indent=2), encoding="utf-8")

    def _load_all(self) -> None:
        """Load all persisted notifications from disk."""
        if not self._store.exists():
            return

        for file_path in self._store.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                notification = NotificationEvent.from_dict(data)
                self._notifications[notification.id] = notification

                # Rebuild dedupe index
                if notification.dedupe_key:
                    self._dedupe_index[notification.dedupe_key] = notification.id

                # Rebuild claimed tracking
                if notification.claimed_by:
                    sink = notification.claimed_by
                    if sink not in self._claimed:
                        self._claimed[sink] = []
                    self._claimed[sink].append(notification.id)

            except (json.JSONDecodeError, KeyError, TypeError):
                # Skip corrupted files
                continue
