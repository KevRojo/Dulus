"""Context window management: two-layer compression for long conversations."""
from __future__ import annotations

import json
import time
from pathlib import Path

import providers


# ── Compaction tuning ─────────────────────────────────────────────────────
# Number of recent conversation turns that are NEVER summarized.
# A "turn" starts at a user message and ends just before the next user message.
RECENT_TURNS_TO_PRESERVE = 20

# Fraction of tokens to aim to keep in the recent portion (as a floor).
# The turn-preservation rule is usually stricter, so this is a fallback.
DEFAULT_KEEP_RATIO = 0.55

# Maximum chars of each old message fed into the summarizer.
SUMMARY_SNIPPET_LEN = 1200

# Where to store pre-compact checkpoints for possible rollback.
CHECKPOINT_DIR = Path.home() / ".dulus" / "compaction_backups"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


# ── Token estimation ──────────────────────────────────────────────────────

def estimate_tokens(messages: list, model: str = "", config: dict | None = None) -> int:
    """Estimate token count.
    
    For Kimi/Moonshot models, uses the native Kimi API token estimation endpoint
    if API key is available. Otherwise falls back to character-based estimation.

    Args:
        messages: list of message dicts with "content" field (str or list of dicts)
        model: model string (optional, e.g., "kimi-k2.5")
        config: agent config dict (optional, for accessing API keys)
    Returns:
        approximate token count, int
    """
    # Try Kimi native API estimation if this is a Kimi/Moonshot model
    if model and (providers.detect_provider(model) in ("kimi", "moonshot")):
        api_key = ""
        if config:
            api_key = providers.get_api_key("kimi", config) or providers.get_api_key("moonshot", config)
        if api_key:
            from providers import estimate_tokens_kimi
            kimi_estimate = estimate_tokens_kimi(api_key, providers.bare_model(model), messages)
            if kimi_estimate is not None:
                return kimi_estimate
    
    # Fall back to character-based estimation.
    # Formula: chars/2.8 (tighter divisor than the naive /4, more accurate for
    # code+JSON heavy conversations) + per-message framing overhead + 10%
    # safety buffer. Overcount slightly so compaction fires before API rejects.
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
    content_tokens = int(total_chars / 2.8)
    framing_tokens = msg_count * 4      # role + delimiters overhead per msg
    return int((content_tokens + framing_tokens) * 1.1)


def get_context_limit(model: str) -> int:
    """Look up context window size for a model.

    Args:
        model: model string (e.g. "claude-opus-4-6", "ollama/llama3.3")
    Returns:
        context limit in tokens
    """
    provider_name = providers.detect_provider(model)
    prov = providers.PROVIDERS.get(provider_name, {})
    return prov.get("context_limit", 128000)


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
    # 1) Token-based split.
    total = estimate_tokens(messages, model=model, config=config)
    target = int(total * keep_ratio)
    running = 0
    token_split = 0
    for i in range(len(messages) - 1, -1, -1):
        running += estimate_tokens([messages[i]], model=model, config=config)
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


def compact_messages(messages: list, config: dict, focus: str = "") -> list:
    """Compress old messages into a summary via LLM call.

    Splits at find_split_point, summarizes old portion, returns
    [system_summary, ack, *pinned, *recent_messages].

    Guarantees:
      - The original system prompt (first message if role==system) is kept.
      - The last RECENT_TURNS_TO_PRESERVE user turns are kept verbatim.
      - Assistant/tool-call pairs are never split.
      - High-priority messages (errors, decisions, file refs) are kept.

    Args:
        messages: full message list
        config: agent config dict (must contain "model")
        focus: optional focus instructions for the summarizer
    Returns:
        new compacted message list
    """
    model = config.get("model", "")
    split = find_split_point(messages, model=model, config=config)
    if split <= 0:
        return messages

    # ── Protect the original system prompt ──
    # The very first system message carries DULUS.md / identity / capabilities.
    # We keep it verbatim and exclude it from summarization so it never gets lost.
    system_header: list[dict] = []
    if messages and messages[0].get("role") == "system":
        system_header = [messages[0]]
        # If the split was 1, we have nothing old to summarize; just return.
        if split <= 1:
            return messages
        old = messages[1:split]
    else:
        old = messages[:split]

    recent = messages[split:]

    # ── Smart separation: keep high-priority messages verbatim ──
    pinned = []
    to_summarize = []
    for m in old:
        role = m.get("role", "")
        has_tool_calls = bool(m.get("tool_calls"))

        # NEVER pin a lone tool message or a lone assistant tool-caller.
        # Those must travel with their partner to avoid API 400s.
        if role == "tool" or has_tool_calls:
            to_summarize.append(m)
        elif _score_message_priority(m) >= 3:
            pinned.append(m)
        else:
            to_summarize.append(m)

    # Build summary request. Include pinned messages in the prompt so the
    # summarizer does not duplicate or contradict them.
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

    # Call LLM for summary
    summary_text = ""
    for event in providers.stream(
        model=config["model"],
        system="You are a concise summarizer. Keep facts dense and actionable.",
        messages=[{"role": "user", "content": summary_prompt}],
        tool_schemas=[],
        config=config,
    ):
        if isinstance(event, providers.TextChunk):
            summary_text += event.text

    summary_msg = {
        "role": "system",
        "content": f"[Previous conversation summary]\n{summary_text}",
    }
    ack_msg = {
        "role": "assistant",
        "content": "Understood. I have the context from the previous conversation. Let's continue.",
    }

    # Result: optional original system + summary + ack + pinned + recent
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


# ── Main entry ────────────────────────────────────────────────────────────

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
    limit = get_context_limit(model)
    threshold = limit * 0.7

    if estimate_tokens(state.messages, model=model, config=config) <= threshold:
        return False

    # Layer 1: snip old tool results
    snip_old_tool_results(state.messages)

    if estimate_tokens(state.messages, model=model, config=config) <= threshold:
        return True

    # Layer 2: auto-compact (with checkpoint + memory recovery)
    _save_precompact_checkpoint(state, config)
    state.messages = compact_messages(state.messages, config)
    state.messages.extend(_memory_messages(_load_relevant_memories(config)))
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

    Preserves the last RECENT_TURNS_TO_PRESERVE user turns verbatim so the
    agent does not forget what it was doing.

    Returns (success, info_message).
    """
    if len(state.messages) < 4:
        return False, "Not enough messages to compact."

    model = config.get("model", "")
    before = estimate_tokens(state.messages, model=model, config=config)

    # Save a checkpoint before any mutation so /compact can be undone.
    checkpoint_path = _save_precompact_checkpoint(state, config)

    snip_old_tool_results(state.messages)
    state.messages = compact_messages(state.messages, config, focus=focus)
    state.messages.extend(_memory_messages(_load_relevant_memories(config)))
    state.messages.extend(_restore_plan_context(config))
    after = estimate_tokens(state.messages, model=model, config=config)
    saved = before - after
    info = f"Compacted: ~{before} -> ~{after} tokens (~{saved} saved)"
    if checkpoint_path:
        info += f" | checkpoint: {checkpoint_path.name}"
    return True, info
