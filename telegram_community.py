"""Telegram Community Bot — Dulus-specific glue for the dashboard bridge.

This module sits between ``dulus.py`` and ``telegram_dashboard.py``:
  - Provides the shared ``_make_run_query_callback`` (DRY, was duplicated)
  - Gates dashboard access behind ``dev_mode``
  - Exposes simple ``start`` / ``stop`` / ``status`` API for dulus.py

Architecture:
    dulus.py  →  telegram_community.py  →  telegram_dashboard.py
    (thin cmd)   (glue + dev gate)         (bridge, store, web UI)
"""

from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional

# ── Dev-mode gate ────────────────────────────────────────────────────────────

def is_dev_mode(config: dict) -> bool:
    """Check if dashboard features are enabled (dev_mode or DULUS_DEV=1)."""
    return bool(config.get("dev_mode")) or os.environ.get("DULUS_DEV") == "1"


# ── Shared callback factory ─────────────────────────────────────────────────

def _make_run_query_callback(config: dict) -> Callable[[str, int, Callable[[str], None]], None]:
    """Build the ``run_query`` callback that the dashboard bridge needs.

    This was copy-pasted in ``_run_daemon`` and ``cmd_telegram`` — now it
    lives in one place.

    The callback signature is:  (text, chat_id, on_complete) → None
    where ``on_complete(response_str)`` is called when Dulus finishes.
    """
    def _dashboard_run_query(text: str, chat_id: int, on_complete: Callable[[str], None]) -> None:
        cb = config.get("_run_query_callback")
        if not cb:
            on_complete("⚠️ Dulus daemon callback not ready yet.")
            return

        config["_telegram_incoming"] = True
        config["_active_tg_chat_id"] = chat_id

        # Snapshot message count BEFORE the call so we only read NEW messages
        st = config.get("_state")
        msgs_before = len(st.messages) if st and st.messages else 0

        try:
            cb(text)
        except Exception as e:
            config["_telegram_incoming"] = False
            on_complete(f"⚠️ Error: {e}")
            return
        finally:
            config["_telegram_incoming"] = False

        # Extract the first NEW assistant message added after this call
        if st and st.messages:
            new_messages = st.messages[msgs_before:]
            for m in reversed(new_messages):
                if m.get("role") == "assistant":
                    content = m.get("content", "")
                    if isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                parts.append(block["text"])
                            elif isinstance(block, str):
                                parts.append(block)
                        content = "\n".join(parts)
                    on_complete(content or "⚠️ No content in response.")
                    return
        on_complete("⚠️ No response from Dulus.")

    return _dashboard_run_query


# ── Start / Stop / Status ────────────────────────────────────────────────────

def start(config: dict, chat_ids: list[int], token: str) -> Any:
    """Start the community dashboard bridge. Returns the bridge instance.

    Raises RuntimeError if dev_mode is not active.
    """
    if not is_dev_mode(config):
        raise RuntimeError(
            "Dashboard mode requires dev_mode. "
            "Set it with:  /config dev_mode=true  or  DULUS_DEV=1"
        )

    from telegram_dashboard import start_dashboard_bridge

    admin_id = chat_ids[0]
    bridge = start_dashboard_bridge(
        token=token,
        admin_chat_id=admin_id,
        config=config,
        dashboard_host=config.get("telegram_dashboard_host", "127.0.0.1"),
        dashboard_port=config.get("telegram_dashboard_port", 9876),
        run_query_callback=_make_run_query_callback(config),
    )
    return bridge

def start_group_bot(config: dict, token: str) -> Any:
    """Start the Group Community Bot (Rose-style). Returns the bridge instance.
    Requires telegram_group_bot.py to be present in the same directory.
    """
    import importlib.util, os
    _here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(_here, "telegram_group_bot.py")):
        raise RuntimeError(
            "telegram_group_bot.py not found. "
            "This feature is not included in the public release."
        )

    from telegram_group_bot import TelegramGroupBotBridge

    level = config.get("telegram_group_permission", 1)
    hammer = config.get("telegram_group_hammer", 2)
    bridge = TelegramGroupBotBridge(
        token=token,
        config=config,
        run_query_callback=_make_run_query_callback(config),
        permission_level=level,
        hammer_tolerance=hammer,
    )
    bridge.start()
    return bridge


def stop(bridge: Any) -> None:
    """Stop the community dashboard bridge gracefully."""
    if bridge is not None:
        try:
            bridge.stop()
        except Exception:
            pass


def status(bridge: Any, config: dict, chat_ids: list[int]) -> str:
    """Return a human-readable status string for the dashboard."""
    if bridge is not None:
        url = getattr(bridge, "dashboard_url", "")
        admin = chat_ids[0] if chat_ids else "none"
        return f"✅ Telegram dashboard is running. Admin: {admin}  →  {url}"
    return ""


# ── Standalone CLI (Info Only) ───────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🦅 DULUS TELEGRAM COMMUNITY GLUE 🦅".center(60))
    print("="*60 + "\n")
    print("  Este archivo es código 'pegamento' interno de Dulus.")
    print("  No hace nada por sí solo.\n")
    print("  Para usar sus funciones (Dashboard o Bot de Grupo), usa Dulus:\n")
    print("  * Dashboard Privado:  /telegram dashboard <token> <admin_id>")
    print("  * Bot de Grupos:      /telegram group <token>\n")
    print("="*60 + "\n")

