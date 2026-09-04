"""Context window management: two-layer compression for long conversations."""
from __future__ import annotations

import json
import time
from pathlib import Path

import providers
try:
    import token_budget
except ImportError:  # public wheel may omit it
    token_budget = None  # type: ignore


# ── Compaction tuning ─────────────────────────────────────────────────────
# Number of recent conversation turns that are NEVER summarized.
# A "turn" starts at a user message and ends just before the next user message.
# Soft cap: if the chat has fewer turns than this, we still leave headroom so
# /compact can actually compress something (see find_split_point).
RECENT_TURNS_TO_PRESERVE = 8

# Absolute floor of recent turns kept even on aggressive compact (lookback OFF).
MIN_RECENT_TURNS = 3

# Fraction of tokens to aim to keep in the recent portion (as a floor).
# The turn-preservation rule is usually stricter, so this is a fallback.
DEFAULT_KEEP_RATIO = 0.40

# ── Lookback-aware compact (aggressive) ──────────────────────────────────
# When lookback is ON the full archive already lives locally for Loopback.
# Compact should leave the LIVE context near-empty and point the model at
# the loopback archive file — not keep 8 fat turns + pinned dumps.
LOOKBACK_RECENT_TURNS = 1          # only the active turn stays verbatim
LOOKBACK_MIN_RECENT_TURNS = 1
LOOKBACK_KEEP_RATIO = 0.02         # ~nothing from the old side by tokens
LOOKBACK_SUMMARY_SNIPPET = 400     # denser, shorter snippets into summarizer
LOOKBACK_SUMMARY_MAX_CHARS = 1200  # hard cap on the summary card itself

# Durable full-archive store so Loopback still works after compact rewrites
# state.messages. Sibling of compaction_backups.
# LOOPBACK_ARCHIVE_DIR set below with CHECKPOINT_DIR (CONFIG_DIR-safe)

# Maximum chars of each old message fed into the summarizer.
SUMMARY_SNIPPET_LEN = 1200

# Hard wall-clock cap on the summarizer LLM call. A /compact used to hang
# FOREVER when providers.stream() stalled (slow/unreachable model on a
# Raspberry Pi, flaky network, local model still loading): the stream never
# yields and never raises, so it just blocks. We now run it on a daemon thread
# and give up after this many seconds, falling back to a trivial summary so
# /compact always returns. Override with env DULUS_COMPACT_TIMEOUT.
try:
    import os as _os
    SUMMARY_TIMEOUT_SECONDS = max(10, int(_os.environ.get("DULUS_COMPACT_TIMEOUT", "180")))
except Exception:
    SUMMARY_TIMEOUT_SECONDS = 180


# Local/on-device backends: a slow summary here is the user's hardware, not a
# network hang. We must NOT cut these off — an old Raspberry Pi running Ollama
# can legitimately take minutes, and we don't know the user's patience. So the
# timeout applies ONLY to cloud providers (where a stall means a dead socket).
_LOCAL_PROVIDERS = {"ollama", "lmstudio", "llamacpp", "edge", "local"}


def _is_local_model(config: dict) -> bool:
    try:
        return providers.detect_provider(config.get("model", "")) in _LOCAL_PROVIDERS
    except Exception:
        return False


def _run_summarizer(system: str, summary_prompt: str, config: dict,
                    timeout: float = SUMMARY_TIMEOUT_SECONDS) -> tuple[str, bool]:
    """Stream a summary from the model with a HARD timeout — for CLOUD models.

    Returns ``(text, timed_out)``. ``text`` is whatever streamed before the
    deadline (possibly empty); ``timed_out`` is True when the model did not
    finish in time or the stream raised. The worker runs on a daemon thread so
    a permanently-stalled provider call can never freeze /compact — the thread
    is simply abandoned and the process can still exit cleanly.

    For LOCAL models (Ollama, LM Studio, llama.cpp, Dulus Edge) there is no
    timeout at all: a slow local summary is the user's hardware, not a hang,
    and we won't truncate it. It streams to completion like before.
    """
    import threading

    # Local backend → block until done, no wall-clock cap.
    effective_timeout = None if _is_local_model(config) else timeout

    chunks: list[str] = []
    done = threading.Event()
    err_box: list[str] = []

    def _worker():
        try:
            for event in providers.stream(
                model=config["model"],
                system=system,
                messages=[{"role": "user", "content": summary_prompt}],
                tool_schemas=[],
                config=config,
            ):
                if isinstance(event, providers.TextChunk):
                    chunks.append(event.text)
        except Exception as exc:  # noqa: BLE001 — any provider error → fallback
            err_box.append(str(exc))
        finally:
            done.set()

    t = threading.Thread(target=_worker, daemon=True, name="compact-summarizer")
    t.start()
    finished = done.wait(effective_timeout)   # None ⇒ wait forever (local)
    text = "".join(chunks).strip()
    if not finished:
        return text, True          # stalled — abandon the daemon thread
    if err_box and not text:
        return "", True            # provider error with nothing usable
    return text, False

# Where to store pre-compact checkpoints for possible rollback.
# Derive from config.CONFIG_DIR (resolved once to a writable location) instead
# of hardcoding ~/.dulus: on OEM/multi-user Windows boxes Path.home() points at
# a profile the process can't write, and this mkdir runs at IMPORT time — an
# unguarded call crashed the whole app on startup (WinError 5 / 3).
from config import CONFIG_DIR

CHECKPOINT_DIR = CONFIG_DIR / "compaction_backups"
LOOPBACK_ARCHIVE_DIR = CONFIG_DIR / "loopback_archives"

# System/user markers that previous compact runs re-inject. Must be stripped
# before compacting or every /compact STACKS another copy (net token growth).
_REINJECT_MARKERS = (
    "[Relevant memories recovered after compaction]",
    "[Plan file restored after compaction:",
    "[Conversation summary",
    "[Compacted conversation summary",
    "[Previous conversation summarized",
    "[Previous conversation summary]",
    "[LOOKBACK COMPACT]",
    "[Lookback compact]",
)
for _d in (CHECKPOINT_DIR, LOOPBACK_ARCHIVE_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Checkpoint / archive writes are already wrapped — missing dir just
        # disables rollback/archive, never fatal at import.
        pass

# Keep module-level alias used by save_loopback_archive when CONFIG_DIR differs
# from Path.home()/.dulus (Windows). Already set above.



# ── Token estimation ──────────────────────────────────────────────────────

# Kimi native-API estimation guards. The estimate endpoint is a NETWORK call,
# and estimate_tokens() is invoked from hot paths (toolbar refresh, prompt
# render, per-message split loops). Without these guards a slow/invalid key
# turns the whole REPL into an infinite-request hang:
#   * _KIMI_EST_CACHE      — memoize by (msg_count, total_chars) fingerprint so
#                            repeated calls on an unchanged history are free.
#   * _KIMI_EST_DISABLED_UNTIL — circuit breaker: after ONE failure (bad key,
#                            network down, timeout) stop trying for 10 minutes
#                            and use the char-based fallback instead.
_KIMI_EST_CACHE: dict = {"fp": None, "val": 0}
_KIMI_EST_DISABLED_UNTIL: float = 0.0
_KIMI_EST_COOLDOWN_S = 600.0


def _char_stats(messages: list) -> tuple[int, int]:
    """Return (total_chars, msg_count) across a message list. Cheap, local."""
    total_chars = 0
    msg_count = 0
    for m in messages:
        msg_count += 1
        content = m.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    # Sum all string values in the block
                    for v in block.values():
                        if isinstance(v, str):
                            total_chars += len(v)
        # Also count tool_calls if present
        for tc in m.get("tool_calls", []):
            if isinstance(tc, dict):
                for v in tc.values():
                    if isinstance(v, str):
                        total_chars += len(v)
        # ── Images / videos (2026-07-13 fix) ──────────────────────────────
        # agent.py attaches /image and /video payloads as sibling keys
        # user_msg["images"] / user_msg["videos"] (base64 strings), NOT
        # inside "content". This loop used to never look at them, so a
        # single video attachment (often 200-800k+ base64 chars) was
        # completely invisible to the token estimate. Result: maybe_compact()
        # thought the conversation was small and never fired auto-compact,
        # while Kimi (which DOES receive and pay for that payload) silently
        # ballooned past its real context window and degraded. Count them
        # the same way as any other content so compaction can actually see
        # the true size of the conversation.
        for key in ("images", "videos"):
            items = m.get(key)
            if not items:
                continue
            for item in items:
                if isinstance(item, str):
                    total_chars += len(item)
                elif isinstance(item, dict):
                    data = item.get("data", "")
                    if isinstance(data, str):
                        total_chars += len(data)
    return total_chars, msg_count


def estimate_tokens(messages: list, model: str = "", config: dict | None = None,
                    fast: bool = False) -> int:
    """Estimate token count.

    For Kimi/Moonshot models, uses the native Kimi API token estimation endpoint
    if API key is available (memoized + circuit-broken — see guards above).
    Otherwise falls back to character-based estimation.

    Args:
        messages: list of message dicts with "content" field (str or list of dicts)
        model: model string (optional, e.g., "kimi-k2.5")
        config: agent config dict (optional, for accessing API keys)
        fast: if True, NEVER hit the network — char-based estimation only.
              Use this from UI hot paths (toolbar, prompt render, tight loops).
    Returns:
        approximate token count, int
    """
    global _KIMI_EST_DISABLED_UNTIL
    total_chars, msg_count = _char_stats(messages)

    # Try Kimi native API estimation if this is a Kimi/Moonshot model.
    # Skipped when: fast mode, circuit breaker open, or no key configured.
    if (not fast and model
            and providers.detect_provider(model) in ("kimi", "moonshot")
            and time.time() >= _KIMI_EST_DISABLED_UNTIL):
        api_key = ""
        if config:
            api_key = providers.get_api_key("kimi", config) or providers.get_api_key("moonshot", config)
        if api_key:
            fp = (msg_count, total_chars)
            if fp == _KIMI_EST_CACHE["fp"]:
                return _KIMI_EST_CACHE["val"]
            from providers import estimate_tokens_kimi
            kimi_estimate = estimate_tokens_kimi(api_key, providers.bare_model(model), messages)
            if kimi_estimate is not None:
                _KIMI_EST_CACHE["fp"] = fp
                _KIMI_EST_CACHE["val"] = kimi_estimate
                return kimi_estimate
            # Endpoint failed (invalid key / network down / timeout). Open the
            # circuit breaker so hot paths don't hammer the API and freeze the
            # terminal; fall through to the char-based estimate below.
            _KIMI_EST_DISABLED_UNTIL = time.time() + _KIMI_EST_COOLDOWN_S

    # Fall back to character-based estimation.
    # Formula: chars/2.8 (tighter divisor than the naive /4, more accurate for
    # code+JSON heavy conversations) + per-message framing overhead + 10%
    # safety buffer. Overcount slightly so compaction fires before API rejects.
    content_tokens = int(total_chars / 2.8)
    framing_tokens = msg_count * 4      # role + delimiters overhead per msg
    return int((content_tokens + framing_tokens) * 1.1)


def get_context_limit(model: str, config: dict | None = None) -> int:
    """Look up context window size for a model.

    This is the model's INPUT window (how much history fits before we compact) —
    it is NOT the output cap. `max_tokens` is the output/completion cap and must
    NOT be used here, or setting a small max_tokens would make Dulus think every
    model (Claude 200k, Gemini 1M, …) has a tiny context and compact far too early.

    Resolution lives in token_budget so the compaction threshold and the number
    actually sent on the wire can never disagree: config["context_limit"] is the
    user's ceiling (0 = auto) and is clamped to the model's real window, because
    believing a 32k model holds 128k means compaction never fires and the
    provider rejects the request instead.
    Args:
        model: model string (e.g. "claude-opus-4-6", "ollama/llama3.3")
        config: optional agent config dict
    Returns:
        context limit in tokens
    """
    if token_budget is not None:
        return token_budget.context_window(model, config)
    # Fallback when token_budget is not shipped (older public layouts)
    if config:
        try:
            n = int(config.get("context_limit") or 0)
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass
    return 128_000


# ── Layer 1: Snip old tool results ────────────────────────────────────────

def snip_old_tool_results(
    messages: list,
    max_chars: int = 2000,
    preserve_last_n_turns: int = 6,
) -> list:
    """Truncate tool-role messages older than preserve_last_n_turns from end.

    For old tool messages whose content exceeds max_chars, keep the first half
    and last quarter, inserting '[... N chars snipped ...]' in between.
    Mutates in place and returns the same list.

    Args:
        messages: list of message dicts (mutated in place)
        max_chars: maximum character length before truncation
        preserve_last_n_turns: number of messages from end to preserve
    Returns:
        the same messages list (mutated)
    """
    cutoff = max(0, len(messages) - preserve_last_n_turns)
    for i in range(cutoff):
        m = messages[i]
        if m.get("role") != "tool":
            continue
        content = m.get("content", "")
        if not isinstance(content, str) or len(content) <= max_chars:
            continue
        first_half = content[: max_chars // 2]
        last_quarter = content[-(max_chars // 4):]
        snipped = len(content) - len(first_half) - len(last_quarter)
        m["content"] = f"{first_half}\n[... {snipped} chars snipped ...]\n{last_quarter}"
    return messages


# ── Layer 1b: Strip stale injected context from old user messages ─────────
# MemPalace pre-loads (~2KB each) and [SYSTEM REMINDER — TRUNCATED OUTPUT]
# notices are prepended/appended to user messages and then live in the
# conversation FOREVER. They were only useful for the turn they landed on;
# on old turns they're pure token dead-weight re-sent with every request.

import re
import re as _re

_MEMPALACE_RE = _re.compile(
    r"\[MemPalace — relevant memories pre-loaded for this turn\..*?"
    r"\n\n---\n\n\[USER MESSAGE\]\n",
    _re.DOTALL,
)
_SYS_REMINDER_RE = _re.compile(
    r"\[SYSTEM REMINDER — TRUNCATED OUTPUT\].*?(?=\n\n\S|\Z)",
    _re.DOTALL,
)


def strip_stale_injections(
    messages: list,
    preserve_last_n_turns: int = 6,
) -> list:
    """Remove MemPalace pre-loads and truncation reminders from OLD user
    messages (older than preserve_last_n_turns from the end). The original
    user text is kept intact. Mutates in place and returns the same list."""
    cutoff = max(0, len(messages) - preserve_last_n_turns)
    for i in range(cutoff):
        m = messages[i]
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if not isinstance(content, str):
            continue
        new = content
        if "[MemPalace — relevant memories pre-loaded" in new:
            new = _MEMPALACE_RE.sub("", new)
        if "[SYSTEM REMINDER — TRUNCATED OUTPUT]" in new:
            new = _SYS_REMINDER_RE.sub("[stale truncation notice removed]", new)
        if new != content:
            m["content"] = new.strip() or "(context injection removed)"
    return messages


def strip_compact_reinjections(messages: list) -> list:
    """Drop system/user/assistant pairs that previous /compact runs re-injected.

    Without this, every compact appends another
    ``[Relevant memories recovered after compaction]`` block. Checkpoints
    from 2026-07-15 showed 17→22 stacked copies and net token *growth*.

    Mutates the list in place and returns it.
    """
    if not messages:
        return messages

    cleaned: list = []
    i = 0
    n = len(messages)
    while i < n:
        m = messages[i]
        role = m.get("role")
        content = m.get("content", "")
        text = content if isinstance(content, str) else ""

        # Drop memory reinjection system blobs entirely.
        if role == "system" and any(marker in text for marker in _REINJECT_MARKERS):
            i += 1
            continue

        # Drop plan-restore user+assistant pair.
        if (
            role == "user"
            and "[Plan file restored after compaction:" in text
        ):
            i += 1
            if i < n and messages[i].get("role") == "assistant":
                i += 1
            continue

        cleaned.append(m)
        i += 1

    messages[:] = cleaned
    return messages


# ── Smart priority scoring for compaction ─────────────────────────────────

# Keywords that indicate high-value content we should preserve
_HIGH_VALUE_KEYWORDS = (
    "error", "exception", "traceback", "failed", "failure", "bug",
    "fix", "resolved", "solution", "workaround", "broken",
    "decidí", "decidi", "voy a", "plan:", "decision:", "conclusion:",
    "next step", "action:", "todo:", "resolved:", "completed:",
    "created file", "modified file", "deleted file", "moved file",
    "root cause", "solution:", "approach:",
)

# File extensions that indicate code references
_CODE_EXTENSIONS = (
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".sh", ".json", ".yml",
    ".yaml", ".toml", ".md", ".txt", ".sql", ".html", ".css",
    ".scss", ".dockerfile", ".ini", ".cfg",
)


def _score_message_priority(message: dict) -> int:
    """Score a message by importance (higher = more important to preserve).

    Returns an integer priority score. Messages with score >= 3 are
    considered 'high priority' and should be preserved during compaction.

    NOTE: system messages are NOT penalized here. The original system prompt
    is protected separately by compact_messages(); injected system hints have
    variable value so we score them neutrally.
    """
    score = 0
    content = message.get("content", "")
    role = message.get("role", "")

    text = _message_text(message) or ""
    text_lower = text.lower()

    # Errors / tracebacks are critical (preserve at all costs)
    if any(k in text_lower for k in ("traceback", "exception", "error:", "failed", "failure")):
        score += 4

    # Decisions / plans are high value
    if any(k in text_lower for k in _HIGH_VALUE_KEYWORDS):
        score += 2

    # File references indicate code context
    if any(ext in text_lower for ext in _CODE_EXTENSIONS):
        score += 1

    # Tool results that contain actual data (not just "no output")
    if role == "tool" and len(text) > 100:
        score += 1

    # User messages are slightly more important than assistant fluff
    if role == "user":
        score += 1

    # Assistant messages that invoked tools carry intent/context
    if role == "assistant" and message.get("tool_calls"):
        score += 1

    return max(0, score)


def _message_text(message: dict) -> str:
    """Extract plain text from a message for scoring / summarization.

    Handles string content and Anthropic-style list content. Does NOT
    reconstruct tool schemas — only human-readable text.
    """
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block.get("content"), str):
                    parts.append(block["content"])
        return "\n".join(parts)
    return str(content) if content is not None else ""


def _collect_tool_call_ids(message: dict) -> set[str]:
    """Return the set of tool_call_ids referenced by an assistant message."""
    ids: set[str] = set()
    for tc in message.get("tool_calls", []) or []:
        if isinstance(tc, dict):
            tid = tc.get("id") or tc.get("call_id")
            if tid:
                ids.add(str(tid))
    return ids


def _is_safe_split(messages: list, idx: int) -> bool:
    """A split is safe only if messages[idx] is not a `tool` message
    (which would be orphaned from its assistant tool_calls partner)."""
    if idx <= 0 or idx >= len(messages):
        return True
    return messages[idx].get("role") != "tool"


def _find_turn_aware_split(messages: list, min_recent_turns: int) -> int:
    """Return the earliest index that preserves at least `min_recent_turns` turns.

    A turn starts at a user message. The result guarantees that the recent
    portion contains complete turns and does NOT start inside a tool-call
    sequence.
    """
    if not messages or min_recent_turns <= 0:
        return 0

    # Walk backwards counting user-message starts.
    turns_seen = 0
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            turns_seen += 1
            last_user_idx = i
            if turns_seen >= min_recent_turns:
                break

    if last_user_idx is None:
        return 0

    # Make sure we don't start the recent portion with an orphaned tool result.
    split = last_user_idx
    while split < len(messages) and messages[split].get("role") == "tool":
        split += 1
    return split


def _effective_recent_turns(
    messages: list,
    requested: int,
    *,
    floor: int | None = None,
) -> int:
    """Clamp preserved turns so compact always has something to summarize.

    If the chat has 12 user turns and we ask to preserve 20, the old logic
    kept *everything* (split at first user) → /compact became a no-op that
    only re-injected memories (net growth). We always leave at least ~40%
    of turns (or 2 turns) eligible for summarization when possible.

    ``floor`` defaults to MIN_RECENT_TURNS (classic). Lookback compact passes
    LOOKBACK_MIN_RECENT_TURNS (1) so the live window can shrink near-zero.
    """
    floor = MIN_RECENT_TURNS if floor is None else max(1, int(floor))
    user_turns = sum(1 for m in messages if m.get("role") == "user")
    if user_turns <= floor:
        return max(1, user_turns)
    # Leave at least 2 turns (or 40% of turns) for the "old" side —
    # except when floor==1 (lookback): leave at least 1 old turn if possible.
    leave_old = max(1 if floor <= 1 else 2, user_turns * 2 // 5)
    max_preserve = max(floor, user_turns - leave_old)
    return max(floor, min(requested, max_preserve))


def find_split_point(
    messages: list,
    keep_ratio: float = DEFAULT_KEEP_RATIO,
    model: str = "",
    config: dict | None = None,
    min_recent_turns: int = RECENT_TURNS_TO_PRESERVE,
) -> int:
    """Find index that splits messages so the recent portion is preserved.

    The split is the MOST CONSERVATIVE of:
      - token-based split (~keep_ratio of tokens)
      - turn-based split (at least `min_recent_turns` complete turns)

    ``min_recent_turns`` is clamped via ``_effective_recent_turns`` so a short
    chat cannot force a no-op compact.

    This ensures `/compact` never summarizes the last N turns, which is what
    keeps Dulus aware of what the user is currently doing.

    Args:
        messages: list of message dicts
        keep_ratio: fraction of tokens to keep in the recent portion
        model: model string (optional, for provider-specific estimation)
        config: agent config dict (optional)
        min_recent_turns: minimum complete user-turns to preserve verbatim
    Returns:
        split index (messages[:idx] = old, messages[idx:] = recent).
        Always returns an index that does not orphan a tool message from
        its assistant tool_calls partner.
    """
    # Clamp so short chats still free room for the summarizer.
    # When caller asks for 1 (lookback aggressive), honor that floor.
    floor = LOOKBACK_MIN_RECENT_TURNS if min_recent_turns <= LOOKBACK_MIN_RECENT_TURNS else MIN_RECENT_TURNS
    min_recent_turns = _effective_recent_turns(messages, min_recent_turns, floor=floor)

    # 1) Token-based split.
    total = estimate_tokens(messages, model=model, config=config)
    target = int(total * keep_ratio)
    running = 0
    token_split = 0
    for i in range(len(messages) - 1, -1, -1):
        # fast=True: NEVER hit the Kimi estimate endpoint per-message — this
        # loop would otherwise fire one network request per history message.
        running += estimate_tokens([messages[i]], model=model, config=config, fast=True)
        if running >= target:
            token_split = i
            break

    # 2) Turn-based split (never summarize recent turns).
    turn_split = _find_turn_aware_split(messages, min_recent_turns)

    # If we have enough turns, the turn rule wins: it guarantees the last N
    # user turns stay verbatim. Only when there are too few turns do we fall
    # back to the token ratio.
    if turn_split > 0:
        split = turn_split
    else:
        split = token_split

    # Ensure we do not split inside a tool-call block. If the split lands on
    # a tool result, walk back to the user message that started that turn so
    # the entire assistant+tools block stays together in the recent portion.
    if 0 < split < len(messages) and messages[split].get("role") == "tool":
        tool_call_id = messages[split].get("tool_call_id")
        owner_idx = None
        for j in range(split - 1, -1, -1):
            if messages[j].get("role") != "assistant":
                continue
            ids = _collect_tool_call_ids(messages[j])
            if tool_call_id in ids or ids:
                owner_idx = j
                break
        if owner_idx is not None:
            # Walk back further to the user message that began this turn.
            for k in range(owner_idx - 1, -1, -1):
                if messages[k].get("role") == "user":
                    split = k
                    break
            else:
                split = 0

    # Final safety: if the recent portion would start with an orphaned tool
    # result (no owner found), advance instead.
    while split < len(messages) and messages[split].get("role") == "tool":
        split += 1
    return split



def _lookback_mode(config: dict | None) -> bool:
    """True when lookback is ON — compact may go aggressive + archive to disk."""
    if not config:
        return False
    try:
        from lookback import lookback_enabled
        return bool(lookback_enabled(config))
    except Exception:
        # Fallback: same truthy keys lookback.py uses
        v = config.get("lookback")
        if v is None:
            v = config.get("lookback_turns")
        if v is True:
            return True
        if isinstance(v, (int, float)) and int(v) > 0:
            return True
        if isinstance(v, str) and v.strip().lower() in {"1", "true", "on", "yes"}:
            return True
        return False


def _session_key(state, config: dict | None) -> str:
    sid = ""
    if state is not None:
        sid = str(getattr(state, "session_id", "") or "")
    if not sid and config:
        sid = str(config.get("session_id") or config.get("session") or "")
    sid = re.sub(r"[^A-Za-z0-9._-]+", "_", sid)[:80]
    return sid or "default"



def enable_lookback_after_compact(config: dict | None, *, reason: str = "compact") -> bool:
    """Force lookback ON for this session after a compact rewrote live context.

    Quality rule (KevRojo): once we collapse live messages to a hint card +
    last turn, the agent MUST have lookback/Loopback or it will invent the past
    and quality tanks. Even if the user had lookback OFF, we flip it ON for the
    rest of the session and persist via save_config when available.

    Returns True if lookback was newly enabled (or already on).
    """
    if not isinstance(config, dict):
        return False
    already = bool(config.get("lookback"))
    config["lookback"] = True
    # Sensible window if unset / zero
    try:
        n = int(config.get("lookback_turns") or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 2:
        config["lookback_turns"] = 20
    # Session-scoped flag so UI / /context can explain why it flipped
    config["_lookback_forced_by_compact"] = True
    config["_lookback_forced_reason"] = reason
    # Clear stale anchors — message indices changed after rewrite
    try:
        from lookback import LOOKBACK_ANCHOR_KEY, LOOKBACK_ANCHOR_SIG_KEY
        config.pop(LOOKBACK_ANCHOR_KEY, None)
        config.pop(LOOKBACK_ANCHOR_SIG_KEY, None)
    except Exception:
        config.pop("_lookback_anchor", None)
        config.pop("_lookback_anchor_sig", None)
    # Persist so restart of same config keeps lookback ON
    try:
        from config import save_config
        save_config(config)
    except Exception:
        pass
    return True if not already else True


def save_loopback_archive(messages: list, state=None, config: dict | None = None) -> Path | None:
    """Persist the FULL pre-compact archive so Loopback still has it.

    Writes ~/.dulus/loopback_archives/archive_<session>.json and binds
    config["_loopback_archive_path"] + config["_loopback_archive"] (in-memory
    copy) for the Loopback tool. Returns the path or None on failure.

    CRITICAL — second-/Nth-compact guard:
    A later ``/compact`` runs against an *already slimmed* ``state.messages``.
    Naively rewriting the archive would overwrite the original full history
    with the post-compact crumbs. We NEVER shrink a durable archive: if an
    in-memory or on-disk copy is longer than ``messages``, keep the longer one
    and only refresh the binding.
    """
    if not messages:
        return None
    try:
        LOOPBACK_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        sid = _session_key(state, config)
        path = LOOPBACK_ARCHIVE_DIR / f"archive_{sid}.json"

        # Resolve the longest known full archive for this session.
        prev: list = []
        if isinstance(config, dict):
            live = config.get("_loopback_archive")
            if isinstance(live, list) and live:
                prev = live
        if not prev and path.exists():
            try:
                disk = json.loads(path.read_text(encoding="utf-8"))
                disk_msgs = disk.get("messages") if isinstance(disk, dict) else None
                if isinstance(disk_msgs, list) and disk_msgs:
                    prev = disk_msgs
            except Exception:
                prev = []

        if prev and len(prev) > len(messages):
            # Refuse to shrink. Keep the fuller archive as the durable source.
            if isinstance(config, dict):
                config["_loopback_archive"] = prev
                config["_loopback_archive_path"] = str(path)
            return path

        payload = {
            "session_id": sid,
            "timestamp": time.strftime("%Y%m%d_%H%M%S"),
            "message_count": len(messages),
            "messages": messages,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        # Keep only newest 20 archives (disk hygiene).
        existing = sorted(
            LOOPBACK_ARCHIVE_DIR.glob("archive_*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        for old in existing[:-20]:
            try:
                old.unlink(missing_ok=True)
            except Exception:
                pass
        if config is not None:
            config["_loopback_archive_path"] = str(path)
            # Hold a live copy so Loopback does not re-read disk every call.
            config["_loopback_archive"] = list(messages)
        return path
    except Exception:
        return None


def load_loopback_archive(config: dict | None = None) -> list:
    """Return the durable full archive for Loopback (memory or disk)."""
    if not config:
        return []
    live = config.get("_loopback_archive")
    if isinstance(live, list) and live:
        return live
    path = config.get("_loopback_archive_path") or ""
    if not path:
        # Fall back to newest archive for this session id
        sid = _session_key(None, config)
        candidate = LOOPBACK_ARCHIVE_DIR / f"archive_{sid}.json"
        path = str(candidate) if candidate.exists() else ""
    if not path:
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        msgs = data.get("messages") if isinstance(data, dict) else None
        if isinstance(msgs, list):
            config["_loopback_archive"] = msgs
            config["_loopback_archive_path"] = path
            return msgs
    except Exception:
        return []
    return []


def compact_messages(messages: list, config: dict, focus: str = "") -> list:
    """Compress old messages into a summary via LLM call.

    Splits at find_split_point, summarizes old portion, returns a slim list.

    Lookback OFF (classic):
      - Keep original system prompt.
      - Keep last RECENT_TURNS_TO_PRESERVE user turns verbatim.
      - Pin high-priority messages; summarize the rest.

    Lookback ON (aggressive — the interesting case):
      - Caller should have already saved the FULL archive via
        ``save_loopback_archive`` so Loopback still has everything.
      - Keep system header + ONE dense [LOOKBACK COMPACT] hint card +
        last LOOKBACK_RECENT_TURNS turn(s) only.
      - No pinned bulk, no fat summary essay — context aims near-zero.
      - Card tells the model to use Loopback(action=search|show|head|status).

    Guarantees always:
      - Assistant/tool-call pairs are never split.
      - Original system prompt (first message if role==system) is kept.
    """
    model = config.get("model", "")
    lb = _lookback_mode(config)

    if lb:
        split = find_split_point(
            messages,
            keep_ratio=LOOKBACK_KEEP_RATIO,
            model=model,
            config=config,
            min_recent_turns=LOOKBACK_RECENT_TURNS,
        )
        # Force floor of 1 recent turn when possible
        split = max(split, 0)
    else:
        split = find_split_point(messages, model=model, config=config)

    if split <= 0:
        return messages

    # ── Protect the original system prompt ──
    system_header: list[dict] = []
    if messages and messages[0].get("role") == "system":
        system_header = [messages[0]]
        if split <= 1:
            return messages
        old = messages[1:split]
    else:
        old = messages[:split]

    recent = messages[split:]

    # ── LOOKBACK PATH: tiny card, no pinned bulk ──
    if lb:
        snippet = LOOKBACK_SUMMARY_SNIPPET
        old_text = ""
        for m in old:
            # Skip pure tool noise in the summarizer feed — keep signal dense
            role = m.get("role", "?")
            if role == "tool":
                text = _message_text(m)[: min(200, snippet)]
            else:
                text = _message_text(m)[:snippet]
            if text.strip():
                old_text += f"[{role}]: {text}\n"

        archive_path = (config or {}).get("_loopback_archive_path") or str(
            LOOPBACK_ARCHIVE_DIR / f"archive_{_session_key(None, config)}.json"
        )
        archive_n = len(messages)
        try:
            from lookback import count_user_turns
            archive_u = count_user_turns(messages)
        except Exception:
            archive_u = sum(1 for m in messages if m.get("role") == "user")

        summary_prompt = (
            "You are writing a TINY recovery card for an agent that has Lookback ON.\n"
            "The FULL conversation is already saved locally for the Loopback tool — "
            "do NOT rewrite the history. Emit ONLY dense bullet facts the agent needs "
            "to continue RIGHT NOW (paths, decisions, IDs, blockers).\n"
            "Hard limit: ~15 short bullets, no prose, no tool dumps, no code blocks.\n"
            f"Archive size: {archive_n} messages / {archive_u} user turns.\n"
        )
        if focus:
            summary_prompt += f"Focus especially on: {focus}\n"
        summary_prompt += "\nOLDER MESSAGES (snippets only):\n" + old_text

        summary_text, timed_out = _run_summarizer(
            "Dense fact extractor. Output bullets only. "
            "No preamble. No restating that lookback exists.",
            summary_prompt,
            config,
        )
        if timed_out and not summary_text:
            # Summarizer stalled/failed — DON'T hang /compact. The full archive
            # is already on disk for Loopback, so a placeholder card is fine.
            summary_text = "(summary skipped — model was slow; full history is on Loopback)"
        if len(summary_text) > LOOKBACK_SUMMARY_MAX_CHARS:
            summary_text = summary_text[: LOOKBACK_SUMMARY_MAX_CHARS - 1] + "…"

        card = (
            "[LOOKBACK COMPACT]\n"
            f"Live context was collapsed. FULL archive is local "
            f"({archive_n} msgs / {archive_u} user turns).\n"
            f"Archive file: {archive_path}\n"
            "Retrieve anything you need with the Loopback tool — do NOT invent past events, "
            "do NOT ask the user to run /loopback:\n"
            "  Loopback(action='search', query='...')\n"
            "  Loopback(action='show', limit=30)\n"
            "  Loopback(action='head', limit=20)\n"
            "  Loopback(action='status')\n"
            "Key facts:\n"
            f"{summary_text or '(no extra facts — use Loopback if needed)'}"
        )
        summary_msg = {"role": "system", "content": card}
        ack_msg = {
            "role": "assistant",
            "content": (
                "Understood. Live context is compact; full archive is on Loopback. "
                "I will Loopback(search/show) if I need older facts. Let's continue."
            ),
        }
        result = list(system_header)
        result.append(summary_msg)
        result.append(ack_msg)
        result.extend(recent)
        return result

    # ── CLASSIC PATH (lookback OFF) ──
    pinned = []
    to_summarize = []
    for m in old:
        role = m.get("role", "")
        has_tool_calls = bool(m.get("tool_calls"))
        if role == "tool" or has_tool_calls:
            to_summarize.append(m)
        elif _score_message_priority(m) >= 3:
            pinned.append(m)
        else:
            to_summarize.append(m)

    old_text = ""
    for m in to_summarize:
        role = m.get("role", "?")
        text = _message_text(m)[:SUMMARY_SNIPPET_LEN]
        old_text += f"[{role}]: {text}\n"

    summary_prompt = (
        "Summarize the following OLDER conversation history concisely. "
        "Preserve key decisions, file paths, tool results, and context "
        "needed to continue the current conversation."
    )
    if focus:
        summary_prompt += f"\n\nFocus especially on: {focus}"
    if pinned:
        summary_prompt += (
            f"\n\nThe following {len(pinned)} high-priority messages will be "
            f"preserved verbatim after your summary, so do NOT repeat them; "
            f"just note their existence if relevant:\n"
        )
        for m in pinned:
            summary_prompt += f"[{m.get('role', '?')}]: {_message_text(m)[:300]}\n"
    summary_prompt += "\n\nOLDER MESSAGES TO SUMMARIZE:\n" + old_text

    summary_text, timed_out = _run_summarizer(
        "You are a concise summarizer. Keep facts dense and actionable.",
        summary_prompt,
        config,
    )
    if timed_out and not summary_text:
        # Summarizer stalled/failed. Rather than hang /compact forever, keep the
        # messages we were going to summarize verbatim — no data loss, just no
        # compression this round.
        summary_text = "(summary skipped — model was slow or unreachable; recent history preserved below)"

    summary_msg = {
        "role": "system",
        "content": f"[Previous conversation summary]\n{summary_text}",
    }
    ack_msg = {
        "role": "assistant",
        "content": "Understood. I have the context from the previous conversation. Let's continue.",
    }

    result = list(system_header)
    result.append(summary_msg)
    result.append(ack_msg)
    if pinned:
        result.append({
            "role": "system",
            "content": f"[Preserved context: {len(pinned)} high-priority messages follow]",
        })
        result.extend(pinned)
    result.extend(recent)
    return result


def maybe_compact(state, config: dict) -> bool:
    """Check if context window is getting full and compress if needed.

    Runs snip_old_tool_results first, then auto-compact if still over threshold.

    Args:
        state: AgentState with .messages list
        config: agent config dict (must contain "model")
    Returns:
        True if compaction was performed
    """
    model = config.get("model", "")
    limit = get_context_limit(model, config)
    threshold = limit * 0.7

    # Fast pre-check (startup-latency fix, 2026-07-06): the precise path can
    # hit the Kimi token-estimation ENDPOINT — a blocking network round-trip
    # that sits directly on the submit→dispatch critical path of EVERY turn,
    # including the very first one where the conversation is obviously tiny.
    # The char-based estimate deliberately overcounts (~10% buffer), so if
    # even IT says we're under half the threshold, no network call can
    # change the verdict. Skip straight to dispatch.
    if estimate_tokens(state.messages, model=model, config=config, fast=True) <= threshold * 0.5:
        return False

    if estimate_tokens(state.messages, model=model, config=config) <= threshold:
        return False

    # Layer 1: snip old tool results + strip stale injected context
    snip_old_tool_results(state.messages)
    strip_stale_injections(state.messages)
    strip_compact_reinjections(state.messages)

    if estimate_tokens(state.messages, model=model, config=config) <= threshold:
        return True

    # Layer 2: auto-compact — always lookback-aggressive + force lookback ON
    _save_precompact_checkpoint(state, config)
    save_loopback_archive(list(state.messages), state=state, config=config)
    config["lookback"] = True
    if not int(config.get("lookback_turns") or 0):
        config["lookback_turns"] = 20
    state.messages = compact_messages(state.messages, config)
    enable_lookback_after_compact(config, reason="auto_compact")

    # No fat memory reinject; restore plan context only
    has_plan = any(
        isinstance(m.get("content"), str)
        and "[Plan file restored after compaction:" in m["content"]
        for m in state.messages
    )
    if not has_plan:
        state.messages.extend(_restore_plan_context(config))
    return True


# ── Checkpoint / rollback ─────────────────────────────────────────────────

def _save_precompact_checkpoint(state, config: dict) -> Path | None:
    """Persist the current message list before compaction so the user can
    roll back if the compact loses too much context."""
    try:
        session_id = getattr(state, "session_id", "") or config.get("session_id", "default")
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = CHECKPOINT_DIR / f"precompact_{session_id}_{ts}.json"
        path.write_text(
            json.dumps(
                {"messages": state.messages, "timestamp": ts},
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        # Keep only the newest 10 checkpoints to avoid disk bloat.
        existing = sorted(CHECKPOINT_DIR.glob("precompact_*.json"), key=lambda p: p.stat().st_mtime)
        for old in existing[:-10]:
            old.unlink(missing_ok=True)
        return path
    except Exception:
        return None


def rollback_compact(config: dict, state=None) -> tuple[bool, str]:
    """Restore the most recent pre-compact checkpoint if available."""
    try:
        existing = sorted(CHECKPOINT_DIR.glob("precompact_*.json"), key=lambda p: p.stat().st_mtime)
        if not existing:
            return False, "No compaction checkpoint found."
        latest = existing[-1]
        data = json.loads(latest.read_text(encoding="utf-8"))
        msgs = data.get("messages", [])
        if state is not None:
            state.messages = msgs
        return True, f"Rolled back to checkpoint: {latest.name} ({len(msgs)} messages)"
    except Exception as e:
        return False, f"Rollback failed: {e}"


# ── Memory context restoration ────────────────────────────────────────────

def _load_relevant_memories(config: dict) -> list[dict]:
    """Fetch memories relevant to the current task after compaction.

    This helps compensate for any context lost during summarization.
    """
    try:
        from memory.context import find_relevant_memories
        query = config.get("_last_user_input", "") or "current task context"
        return find_relevant_memories(query, max_results=5, use_ai=False, config=config)
    except Exception:
        return []


def _memory_messages(memories: list[dict]) -> list[dict]:
    """Turn relevant memory records into system context messages."""
    if not memories:
        return []
    lines = ["[Relevant memories recovered after compaction]"]
    for m in memories:
        name = m.get("name", "unknown")
        desc = (m.get("description") or "").strip()
        content = (m.get("content") or "").strip()
        scope = m.get("scope", "user")
        part = f"- {name} ({scope})"
        if desc:
            part += f": {desc}"
        if content:
            part += f"\n  {content[:400]}"
        lines.append(part)
    return [{"role": "system", "content": "\n".join(lines)}]


# ── Plan context restoration ─────────────────────────────────────────────

def _restore_plan_context(config: dict) -> list:
    """If in plan mode, return messages that restore plan file context."""
    from pathlib import Path
    plan_file = config.get("_plan_file", "")
    if not plan_file or config.get("permission_mode") != "plan":
        return []
    p = Path(plan_file)
    if not p.exists():
        return []
    content = p.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [
        {"role": "user", "content": f"[Plan file restored after compaction: {plan_file}]\n\n{content}"},
        {"role": "assistant", "content": "I have the plan context. Let's continue."},
    ]


# ── Manual compact ───────────────────────────────────────────────────────

def manual_compact(state, config: dict, focus: str = "") -> tuple[bool, str]:
    """User-triggered compaction via /compact. Not gated by threshold.

    Preserves the last RECENT_TURNS_TO_PRESERVE user turns (clamped) so the
    agent does not forget what it was doing. Strips prior compact reinjections
    so repeated /compact cannot grow the context.

    Returns (success, info_message).
    """
    if len(state.messages) < 4:
        return False, "Not enough messages to compact."

    model = config.get("model", "")
    before = estimate_tokens(state.messages, model=model, config=config)

    # Save a checkpoint before any mutation so /compact can be undone.
    checkpoint_path = _save_precompact_checkpoint(state, config)

    snip_old_tool_results(state.messages)
    strip_stale_injections(state.messages)
    # Critical: drop stacked memory/plan reinjections from previous /compacts.
    strip_compact_reinjections(state.messages)

    # Compact ALWAYS goes lookback-aggressive for quality:
    # 1) dump full archive to disk for Loopback
    # 2) collapse live context
    # 3) force lookback ON for the rest of this session (even if it was OFF)
    was_lb = _lookback_mode(config)
    archive_path = save_loopback_archive(
        list(state.messages), state=state, config=config
    )
    # Pretend lookback ON during compact_messages so we get the tiny card path
    config["lookback"] = True
    if not int(config.get("lookback_turns") or 0):
        config["lookback_turns"] = 20

    state.messages = compact_messages(state.messages, config, focus=focus)

    enable_lookback_after_compact(config, reason="manual_compact")

    # No fat memory reinject — archive lives on Loopback now
    has_plan = any(
        isinstance(m.get("content"), str)
        and "[Plan file restored after compaction:" in m["content"]
        for m in state.messages
    )
    if not has_plan:
        state.messages.extend(_restore_plan_context(config))

    after = estimate_tokens(state.messages, model=model, config=config)
    saved = before - after
    mode = "lookback-aggressive"
    forced = "" if was_lb else " | lookback FORCED ON for this session"
    if saved >= 0:
        info = f"Compacted ({mode}): ~{before} -> ~{after} tokens (~{saved} saved){forced}"
    else:
        info = (
            f"Compacted ({mode}): ~{before} -> ~{after} tokens "
            f"(~{abs(saved)} GREW — check summarizer / reinjections){forced}"
        )
    if checkpoint_path:
        info += f" | checkpoint: {checkpoint_path.name}"
    if archive_path:
        info += f" | loopback archive: {Path(archive_path).name}"
    return True, info
