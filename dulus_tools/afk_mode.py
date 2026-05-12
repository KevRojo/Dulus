"""AFK Mode - Auto-dismiss AskUserQuestion and auto-approve tool calls."""
from dataclasses import dataclass, field


@dataclass
class AFKMode:
    """AFK mode state manager.

    When enabled, auto-dismisses AskUserQuestion prompts and auto-approves
    tool calls, allowing the agent to run unattended.
    """

    _enabled: bool = field(default=False, repr=False)

    @property
    def enabled(self) -> bool:
        """Return whether AFK mode is currently enabled."""
        return self._enabled

    def toggle(self) -> bool:
        """Toggle AFK mode on/off. Returns the new state."""
        self._enabled = not self._enabled
        return self._enabled

    def enable(self) -> None:
        """Enable AFK mode."""
        self._enabled = True

    def disable(self) -> None:
        """Disable AFK mode."""
        self._enabled = False

    def __repr__(self) -> str:
        return f"AFKMode(enabled={self._enabled})"
