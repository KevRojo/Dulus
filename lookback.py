"""Lookback mode — present-window API, full-archive local.

Genius idea (KevRojo):
  - Full conversation always lives in ``state.messages`` (the archive / loopback).
  - When lookback is ON, only the last N *user turns* are sent to the model API.
  - short_memory (system) keeps the essential past beside the model without
    replaying every old tool dump.
  - ``/loopback`` is how you re-open the full archive on demand.

Naming:
  lookback  → sliding window for the API (saves tokens)
  loopback  → full history still saved; retrieve / inspect / search it

Safety:
  Window cuts only on user-turn boundaries so assistant tool_calls are never
  separated from their tool results (providers reject broken chains).
"""
from __future__ import annotations

from typing import Any


DEFAULT_LOOKBACK_TURNS = 20
MIN_LOOKBACK_TURNS = 2
MAX_LOOKBACK_TURNS = 250

# Runtime key (in config) holding the anchored window start. The anchor gives
# the window hysteresis: without it the start slides forward on every user
# turn, which rewrites the API prefix and busts provider prompt caches each
# call — costing more than lookback saves.
LOOKBACK_ANCHOR_KEY = "_lookback_anchor"


def _anchor_slack(n: int) -> int:
    """Extra user turns the window may grow before re-anchoring."""
    return max(2, n // 4)


def _is_real_user(m: dict) -> bool:
    if m.get("role") != "user":
        return False
    content = m.get("content") or ""
    return not (isinstance(content, str) and content.lstrip().startswith("[SYSTEM"))


def lookback_enabled(config: dict | None) -> bool:
    if not config:
        return False
    return bool(config.get("lookback", False))


def lookback_turns(config: dict | None) -> int:
    if not config:
        return DEFAULT_LOOKBACK_TURNS
    try:
        n = int(config.get("lookback_turns", DEFAULT_LOOKBACK_TURNS))
    except (TypeError, ValueError):
        n = DEFAULT_LOOKBACK_TURNS
    return max(MIN_LOOKBACK_TURNS, min(MAX_LOOKBACK_TURNS, n))


def count_user_turns(messages: list) -> int:
    """Count user turns, ignoring synthetic system-reminder user messages."""
    n = 0
    for m in messages or []:
        if m.get("role") != "user":
            continue
        content = m.get("content") or ""
        if isinstance(content, str) and content.lstrip().startswith("[SYSTEM"):
            continue
        n += 1
    return n


def find_lookback_start(messages: list, turns: int) -> int:
    """Index of the first message to keep for the last ``turns`` user turns.

    Returns 0 if the whole list fits or lookback is wide enough.
    Never splits mid tool-chain: start is always a real user message (or 0).
    """
    if not messages or turns <= 0:
        return 0
    remaining = turns
    start = 0
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.get("role") != "user":
            continue
        content = m.get("content") or ""
        if isinstance(content, str) and content.lstrip().startswith("[SYSTEM"):
            continue
        remaining -= 1
        start = i
        if remaining <= 0:
            break
    return start


def apply_lookback_window(
    messages: list,
    config: dict | None = None,
    *,
    enabled: bool | None = None,
    turns: int | None = None,
) -> tuple[list, dict[str, Any]]:
    """Return (api_messages, meta) for the next provider call.

    Full ``messages`` is never mutated. When disabled or small enough, the
    original list is returned (same object) with meta.truncated=False.
    """
    msgs = messages or []
    on = lookback_enabled(config) if enabled is None else bool(enabled)
    n = lookback_turns(config) if turns is None else max(MIN_LOOKBACK_TURNS, min(MAX_LOOKBACK_TURNS, int(turns)))
    total = len(msgs)
    total_user = count_user_turns(msgs)
    meta: dict[str, Any] = {
        "enabled": on,
        "turns": n,
        "archive_messages": total,
        "archive_user_turns": total_user,
        "window_messages": total,
        "window_user_turns": total_user,
        "truncated": False,
        "start_index": 0,
        "hidden_messages": 0,
    }
    if not on or total == 0:
        if isinstance(config, dict):
            config.pop(LOOKBACK_ANCHOR_KEY, None)
        return msgs, meta

    # Hysteresis: reuse the previous start (anchor) while its window still
    # holds n..n+slack user turns. The API prefix then stays append-only
    # between jumps, so provider prompt caches keep hitting; we re-anchor
    # (one cache miss) only every ~slack user turns instead of every turn.
    slack = _anchor_slack(n)
    start: int | None = None
    if isinstance(config, dict):
        anchor = config.get(LOOKBACK_ANCHOR_KEY)
        if (isinstance(anchor, int) and 0 < anchor < total
                and _is_real_user(msgs[anchor])):
            w = count_user_turns(msgs[anchor:])
            if n <= w <= n + slack:
                start = anchor
    if start is None:
        start = find_lookback_start(msgs, n)
        if isinstance(config, dict):
            config[LOOKBACK_ANCHOR_KEY] = start

    if start <= 0:
        return msgs, meta

    window = msgs[start:]
    meta.update({
        "truncated": True,
        "start_index": start,
        "window_messages": len(window),
        "window_user_turns": count_user_turns(window),
        "hidden_messages": start,
        "slack": slack,
    })
    return window, meta


def lookback_system_note(meta: dict[str, Any]) -> str:
    """Short system addendum so the model knows the archive exists.

    BYTE-STABLE BY DESIGN: the note must never embed live counters. Message
    counts change on every tool turn, and any change to the system prompt
    invalidates the provider prompt cache for the system block AND the whole
    conversation after it — re-writing the full context at write price every
    call, which costs far more than lookback saves. Live numbers belong in
    Loopback(action='status'). Empty when the window isn't truncated: an
    informational note is not worth a cache bust.

    Critical DX: the agent can call the Loopback *tool* itself. Never tell the
    user to run /loopback just because a fact is outside the present window.
    """
    if not meta.get("enabled") or not meta.get("truncated"):
        return ""
    turns = meta.get("turns", DEFAULT_LOOKBACK_TURNS)
    return (
        "\n\n[LOOKBACK ACTIVE — you are in the PRESENT window only.\n"
        f"The API window holds roughly the last {turns} user turns; older "
        "messages are hidden from you but fully preserved locally (loopback).\n"
        "Essential durable facts live in short_memory / MemorySearch.\n"
        "If you need a detail from outside this window, YOU call the Loopback tool:\n"
        "  Loopback(action='search', query='...')\n"
        "  Loopback(action='show', limit=30)   # last N archive messages\n"
        "  Loopback(action='head', limit=20)   # first N archive messages\n"
        "  Loopback(action='status')           # live archive/window counts\n"
        "Do NOT invent older events. Do NOT ask the user to run /loopback — "
        "you can retrieve the archive yourself.]\n"
    )


def get_archive_from_config(config: dict | None) -> list:
    """Resolve the live conversation archive for tools / slash commands.

    Prefer ``config['_state'].messages`` (bound by the agent/REPL). Returns []
    when no live state is available — never invents history.
    """
    if not config:
        return []
    state = config.get("_state")
    if state is None:
        return []
    msgs = getattr(state, "messages", None)
    if msgs is None and isinstance(state, dict):
        msgs = state.get("messages")
    if not isinstance(msgs, list):
        return []
    return msgs


def format_message_preview(m: dict, max_len: int = 160) -> str:
    role = m.get("role", "?")
    content = m.get("content") or ""
    if not isinstance(content, str):
        content = str(content)
    content = content.replace("\n", " ").strip()
    if m.get("tool_calls"):
        names = []
        for tc in m.get("tool_calls") or []:
            if isinstance(tc, dict):
                names.append(tc.get("name") or "?")
            else:
                names.append(getattr(tc, "name", "?"))
        extra = f" [tools: {', '.join(names)}]" if names else " [tools]"
    elif role == "tool":
        extra = f" [tool_result: {m.get('name', '?')}]"
    else:
        extra = ""
    if len(content) > max_len:
        content = content[: max_len - 1] + "…"
    return f"{role}{extra}: {content}"


def search_archive(messages: list, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Simple case-insensitive token search over the full archive."""
    q = (query or "").strip().lower()
    if not q:
        return []
    tokens = [t for t in q.split() if t]
    hits: list[dict[str, Any]] = []
    for i, m in enumerate(messages or []):
        blob_parts = [
            str(m.get("role", "")),
            str(m.get("name", "")),
            str(m.get("content", "")),
        ]
        if m.get("tool_calls"):
            blob_parts.append(str(m.get("tool_calls")))
        blob = " ".join(blob_parts).lower()
        if tokens and all(t in blob for t in tokens):
            hits.append({
                "index": i,
                "role": m.get("role"),
                "preview": format_message_preview(m, 220),
            })
            if len(hits) >= limit:
                break
    return hits


def format_loopback_status(messages: list, config: dict | None = None) -> str:
    """Human/agent-readable status of the full archive + lookback window."""
    archive = messages or []
    archive_n = len(archive)
    archive_u = count_user_turns(archive)
    lines = [
        f"Loopback archive: {archive_n} messages / {archive_u} user turns (full, local)",
    ]
    if lookback_enabled(config):
        _, meta = apply_lookback_window(archive, config)
        lines.append(
            f"Lookback window:  last {lookback_turns(config)} user turns "
            f"({meta.get('window_messages', 0)} msgs to API, "
            f"{meta.get('hidden_messages', 0)} hidden)"
        )
        lines.append(
            f"truncated={meta.get('truncated')} start_index={meta.get('start_index', 0)}"
        )
    else:
        lines.append("Lookback:         OFF — API currently receives the full archive")
    lines.append(
        "Agent tool: Loopback(action=status|show|head|search, query=..., limit=N)"
    )
    return "\n".join(lines)


def format_loopback_slice(
    messages: list,
    *,
    which: str = "show",
    limit: int = 30,
    max_preview: int = 220,
) -> str:
    """Format head/tail of the archive for the Loopback tool."""
    archive = messages or []
    archive_n = len(archive)
    n = max(1, min(int(limit or 30), 200))
    which = (which or "show").lower()
    if which in ("head", "first"):
        end = min(n, archive_n)
        start = 0
        label = f"Loopback head — first {end} of {archive_n} messages"
    else:
        start = max(0, archive_n - n)
        end = archive_n
        label = (
            f"Loopback show — last {min(n, archive_n)} of {archive_n} messages "
            f"(indices {start}..{end - 1 if end else 0})"
        )
    lines = [label + ":"]
    if archive_n == 0:
        lines.append("(archive empty)")
        return "\n".join(lines)
    for i in range(start, end):
        lines.append(f"  [{i}] {format_message_preview(archive[i], max_preview)}")
    return "\n".join(lines)


def format_loopback_search(
    messages: list,
    query: str,
    *,
    limit: int = 20,
) -> str:
    """Format search hits for the Loopback tool."""
    q = (query or "").strip()
    if not q:
        return "Error: Loopback search requires query=..."
    lim = max(1, min(int(limit or 20), 100))
    hits = search_archive(messages or [], q, limit=lim)
    if not hits:
        return f"No loopback hits for: {q!r} (archive={len(messages or [])} messages)"
    lines = [f"Loopback search — {len(hits)} hit(s) for {q!r}:"]
    for h in hits:
        lines.append(f"  [{h['index']}] {h['preview']}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_LOOKBACK_TURNS",
    "MIN_LOOKBACK_TURNS",
    "MAX_LOOKBACK_TURNS",
    "LOOKBACK_ANCHOR_KEY",
    "apply_lookback_window",
    "count_user_turns",
    "find_lookback_start",
    "format_loopback_search",
    "format_loopback_slice",
    "format_loopback_status",
    "format_message_preview",
    "get_archive_from_config",
    "lookback_enabled",
    "lookback_system_note",
    "lookback_turns",
    "search_archive",
]
