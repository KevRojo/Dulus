"""YOLO Mode - Auto-approve ALL actions without prompts."""
from dataclasses import dataclass, field


@dataclass
class YOLOMode:
    """YOLO mode state manager.

    When enabled, auto-approves ALL actions without any prompts.
    This is more aggressive than --accept-all and is independent from AFK mode.
    Use with extreme caution.
    """

    _enabled: bool = field(default=False, repr=False)

    @property
    def enabled(self) -> bool:
        """Return whether YOLO mode is currently enabled."""
        return self._enabled

    def toggle(self) -> bool:
        """Toggle YOLO mode on/off. Returns the new state."""
        self._enabled = not self._enabled
        return self._enabled

    def enable(self) -> None:
        """Enable YOLO mode."""
        self._enabled = True

    def disable(self) -> None:
        """Disable YOLO mode."""
        self._enabled = False

    def __repr__(self) -> str:
        return f"YOLOMode(enabled={self._enabled})"
