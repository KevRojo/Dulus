"""Recognize browser-session selectors and commands saved by older public Dulus releases."""
from __future__ import annotations

_RETIRED_WEB_PROVIDERS = {
    "claude-code", "claude-web", "deepseek-web", "gemini-web", "kimi-web", "qwen-web",
}
_RETIRED_COMMANDS = {
    "/harvest", "/harvest-claude", "/claude-harvest", "/harvest-kimi",
    "/harvest-gemini", "/gemini-harvest", "/harvest-deepseek", "/deepseek-harvest",
    "/harvest-qwen", "/qwen-harvest", "/claude-chats", "/gemini-chats", "/kimi-chats",
}


def retired_web_provider(model: str) -> str | None:
    """Recognize old browser-session selectors before model-family auto-detection."""
    namespace = model.partition("/")[0].partition(":")[0].strip().lower().replace("_", "-")
    return namespace if namespace in _RETIRED_WEB_PROVIDERS else None


def retired_provider_message(provider: str) -> str:
    return (
        f"The '{provider}' browser-session provider was removed from public Dulus. "
        "For Fuel-metered models, run /login dulus and /model dulus/dulus-b-27b. "
        "Use /model to select your own provider."
    )


def retired_command_error(line: str) -> str | None:
    """Identify removed slash commands or an attempt to select a retired provider."""
    parts = line.split(maxsplit=1)
    if not parts:
        return None
    command = parts[0].lower().replace("_", "-")
    if command in _RETIRED_COMMANDS:
        return f"Unknown command: {parts[0]}  (type /help for commands)"
    if len(parts) == 2:
        value = parts[1]
        if command == "/config":
            key, _, value = value.partition("=")
            if key.strip() != "model":
                return None
        elif command != "/model":
            return None
        if removed := retired_web_provider(value):
            return retired_provider_message(removed)
    return None
