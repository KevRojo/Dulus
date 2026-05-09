"""Session manager for Composio integration."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_composio_client = None


def _load_api_key() -> str:
    """Load Composio API key from Dulus config (with Falcon fallback) or env."""
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        for cfg_path in (Path.home() / ".dulus" / "config.json",
                         Path.home() / ".falcon" / "config.json"):
            if cfg_path.exists():
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    api_key = config.get("composio_api_key", "")
                    if api_key:
                        break
                except Exception:
                    pass
    return api_key


def get_client():
    """Get or create Composio client."""
    global _composio_client
    if _composio_client is not None:
        return _composio_client

    api_key = _load_api_key()
    if not api_key:
        raise RuntimeError("COMPOSIO_API_KEY not found. Set it in ~/.falcon/config.json or env.")

    os.environ["COMPOSIO_API_KEY"] = api_key

    from composio import Composio
    _composio_client = Composio()
    return _composio_client


def get_or_create_session(user_id: str, toolkits: List[str], connected_accounts: Optional[Dict[str, str]] = None):
    """Create a Composio session with given toolkits."""
    client = get_client()
    kwargs = {
        "user_id": user_id,
        "toolkits": toolkits,
        "manage_connections": {"wait_for_connections": True},
    }
    if connected_accounts:
        kwargs["connected_accounts"] = connected_accounts
    return client.create(**kwargs)


def list_accounts() -> List[Dict[str, Any]]:
    """List all connected accounts."""
    client = get_client()
    accounts = client.connected_accounts.list()
    result = []
    for acc in accounts.items:
        result.append({
            "id": getattr(acc, "id", "N/A"),
            "app": getattr(acc, "appName", getattr(acc, "app_name", "N/A")),
            "status": getattr(acc, "status", "N/A"),
            "toolkit": acc.dict().get("toolkit", {}).get("slug", "N/A") if hasattr(acc, "dict") else "N/A",
            "auth_scheme": getattr(acc, "authScheme", "N/A"),
        })
    return result
