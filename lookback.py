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

# Companion key: a byte-signature of the message AT the anchor index. The raw
# index is meaningless after maybe_compact() rewrites/shrinks state.messages —
# it can silently point at a *different* user turn, misaligning the window. We
# only reuse the anchor when the message still living there matches the sig;
# otherwise we re-anchor from scratch. Guards the compaction edge.
LOOKBACK_ANCHOR_SIG_KEY = "_lookback_anchor_sig"

# Default cache-aware gate: front-truncation busts the prompt-cache prefix, so
# it only pays off when the HIDDEN head is much larger than the kept window
# (the tokens we stop sending must outweigh losing the ~0.1x cached-read
# discount on the full archive). Below this head:window size ratio we send the
# full archive and let the cache absorb it. Override via config
# ["lookback_min_hidden_ratio"]; set 0 to disable the gate (providers with no
# prompt cache — lookback always helps there).
DEFAULT_MIN_HIDDEN_RATIO = 2.0


def _anchor_slack(n: int) -> int:
    """User turns the window may grow past ``n`` before re-anchoring.

    Block re-anchoring: we let the window drift a full ``n`` extra user turns
    (window grows n → 2n) before jumping the anchor back to n. Re-anchoring is
    the *only* cache-busting event (it rewrites the conversation prefix), so
    doing it every ~n turns — instead of the old n//4 — cuts the prefix
    rewrites ~4x. Each rewrite carries more tokens, but under prefix caching a
    few big writes amortize far better than many small ones.
    """
    return max(MIN_LOOKBACK_TURNS, n)


def _msg_sig(m: dict) -> str:
    """Cheap identity signature of an anchored message (role + content head).

    Not a hash for security — just enough to detect that the message at a
    stored index changed (e.g. after compaction) so we don't reuse a stale
    anchor that now points at a different turn.
    """
    role = str(m.get("role", ""))
    content = m.get("content")
    if not isinstance(content, str):
        content = str(content)
    return f"{role}:{len(content)}:{content[:64]}"


def _approx_size(messages: list) -> int:
    """Rough char-count proxy for token weight of a message slice."""
    total = 0
    for m in messages or []:
        c = m.get("content")
        if isinstance(c, str):
            total += len(c)
        elif c is not None:
            total += len(str(c))
        tc = m.get("tool_calls")
        if tc:
            total += len(str(tc))
    return total


def _clear_anchor(config: dict | None) -> None:
    if isinstance(config, dict):
        config.pop(LOOKBACK_ANCHOR_KEY, None)
        config.pop(LOOKBACK_ANCHOR_SIG_KEY, None)


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



def _strip_baseline_display(messages: list) -> list:
    """Drop soul/gold/welcome GUI display blobs from an API window.

    Those ride in the system prompt now (see memory.gold_system_fragment /
    soul_system_fragment). Keeping them as role:assistant in the API payload
    made web-history consolidate treat gold as "last assistant reply".
    """
    if not messages:
        return messages
    try:
        from memory import is_baseline_display_message
    except Exception:
        return messages
    out = [m for m in messages if not is_baseline_display_message(m)]
    # Preserve identity when nothing was stripped (callers/tests rely on it).
    return messages if len(out) == len(messages) else out


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

    Baseline display blobs (soul/gold/welcome) are always stripped from the
    returned API window — they live in the system prompt, not chat turns.
    """
    msgs = messages or []
    on = lookback_enabled(config) if enabled is None else bool(enabled)
    n = lookback_turns(config) if turns is None else max(MIN_LOOKBACK_TURNS, min(MAX_LOOKBACK_TURNS, int(turns)))
    total = len(msgs)
    total_user = count_user_turns(msgs)
    slack = _anchor_slack(n)
    meta: dict[str, Any] = {
        "enabled": on,
        "turns": n,
        "slack": slack,
        "archive_messages": total,
        "archive_user_turns": total_user,
        "window_messages": total,
        "window_user_turns": total_user,
        "truncated": False,
        "gated": False,
        "start_index": 0,
        "hidden_messages": 0,
    }
    def _api_window(window: list, meta: dict[str, Any]) -> tuple[list, dict[str, Any]]:
        """Strip baseline display blobs and refresh window counts."""
        cleaned = _strip_baseline_display(window)
        if cleaned is window:
            return window, meta
        meta = dict(meta)
        meta["window_messages"] = len(cleaned)
        meta["window_user_turns"] = count_user_turns(cleaned)
        meta["baseline_stripped"] = len(window) - len(cleaned)
        return cleaned, meta

    if not on or total == 0:
        _clear_anchor(config)
        return _api_window(msgs, meta)

    # Hysteresis: reuse the previous start (anchor) while its window still
    # holds n..n+slack user turns. The API prefix then stays append-only
    # between jumps, so provider prompt caches keep hitting; we re-anchor
    # (one cache miss) only every ~slack user turns instead of every turn.
    # The anchor is only trusted when the message still at that index matches
    # the stored signature — otherwise compaction moved things and we re-anchor.
    start: int | None = None
    if isinstance(config, dict):
        anchor = config.get(LOOKBACK_ANCHOR_KEY)
        sig = config.get(LOOKBACK_ANCHOR_SIG_KEY)
        if (isinstance(anchor, int) and 0 < anchor < total
                and _is_real_user(msgs[anchor])
                and (sig is None or sig == _msg_sig(msgs[anchor]))):
            w = count_user_turns(msgs[anchor:])
            if n <= w <= n + slack:
                start = anchor
    if start is None:
        start = find_lookback_start(msgs, n)

    if start <= 0:
        _clear_anchor(config)
        return _api_window(msgs, meta)

    # Cache-aware gate: only truncate when the head we'd hide is meaningfully
    # bigger than the window we'd keep. Otherwise dropping the front busts the
    # prompt-cache prefix for a saving smaller than the lost cached-read
    # discount — a net loss. When gated we send the full archive (cache-friendly)
    # and drop the anchor so we retry cleanly once the archive outgrows the gate.
    try:
        ratio = float(config.get("lookback_min_hidden_ratio", DEFAULT_MIN_HIDDEN_RATIO)) if isinstance(config, dict) else DEFAULT_MIN_HIDDEN_RATIO
    except (TypeError, ValueError):
        ratio = DEFAULT_MIN_HIDDEN_RATIO
    if ratio > 0:
        head_size = _approx_size(msgs[:start])
        win_size = _approx_size(msgs[start:]) or 1
        if head_size < ratio * win_size:
            _clear_anchor(config)
            meta["gated"] = True
            return msgs, meta

    if isinstance(config, dict):
        config[LOOKBACK_ANCHOR_KEY] = start
        config[LOOKBACK_ANCHOR_SIG_KEY] = _msg_sig(msgs[start])

    window = msgs[start:]
    meta.update({
        "truncated": True,
        "start_index": start,
        "window_messages": len(window),
        "window_user_turns": count_user_turns(window),
        "hidden_messages": start,
    })
    return _api_window(window, meta)


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
    """Resolve the full conversation archive for tools / slash commands.

    Order of preference:
      1. ``config['_loopback_archive']`` — full pre-compact snapshot (in memory)
      2. ``config['_loopback_archive_path']`` on disk (after lookback-aggressive compact)
      3. ``config['_state'].messages`` — live archive when never compacted

    After a lookback compact, live ``state.messages`` is intentionally tiny
    (hint card + last turn). Loopback MUST still see the full history, so we
    prefer the durable archive whenever it is present and longer.
    """
    if not config:
        return []

    # 1–2 durable archive (lookback compact)
    durable: list = []
    live_archive = config.get("_loopback_archive")
    if isinstance(live_archive, list) and live_archive:
        durable = live_archive
    else:
        path = config.get("_loopback_archive_path") or ""
        if path:
            try:
                import json
                from pathlib import Path as _P
                data = json.loads(_P(path).read_text(encoding="utf-8"))
                msgs = data.get("messages") if isinstance(data, dict) else None
                if isinstance(msgs, list) and msgs:
                    durable = msgs
                    config["_loopback_archive"] = msgs
            except Exception:
                durable = []
        if not durable:
            try:
                from compaction import load_loopback_archive
                durable = load_loopback_archive(config) or []
            except Exception:
                durable = []

    # 3 live state
    state = config.get("_state")
    live: list = []
    if state is not None:
        msgs = getattr(state, "messages", None)
        if msgs is None and isinstance(state, dict):
            msgs = state.get("messages")
        if isinstance(msgs, list):
            live = msgs

    # Prefer the longer full archive. If durable exists and is longer (or live
    # is a post-compact stub), return durable so Loopback still works.
    if durable and (not live or len(durable) >= len(live)):
        return durable
    return live if isinstance(live, list) else []


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
    "DEFAULT_MIN_HIDDEN_RATIO",
    "LOOKBACK_ANCHOR_KEY",
    "LOOKBACK_ANCHOR_SIG_KEY",
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
