"""Context window management: two-layer compression for long conversations."""
from __future__ import annotations

import providers


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
    """
    score = 0
    content = message.get("content", "")
    role = message.get("role", "")

    if not isinstance(content, str):
        content = str(content) if content else ""
    text_lower = content.lower()

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
    if role == "tool" and len(content) > 100:
        score += 1

    # User messages are slightly more important than assistant fluff
    if role == "user":
        score += 1

    # System messages are least important (except the first one)
    if role == "system":
        score -= 2

    return max(0, score)


def _is_safe_split(messages: list, idx: int) -> bool:
    """A split is safe only if messages[idx] is not a `tool` message
    (which would be orphaned from its assistant tool_calls partner)."""
    if idx <= 0 or idx >= len(messages):
        return True
    return messages[idx].get("role") != "tool"


def find_split_point(messages: list, keep_ratio: float = 0.3, model: str = "", config: dict | None = None) -> int:
    """Find index that splits messages so ~keep_ratio of tokens are in the recent portion.

    Walks backwards from end, accumulating token estimates, and returns the
    index where the recent portion reaches ~keep_ratio of total tokens.

    Args:
        messages: list of message dicts
        keep_ratio: fraction of tokens to keep in the recent portion
        model: model string (optional, for provider-specific estimation)
        config: agent config dict (optional)
    Returns:
        split index (messages[:idx] = old, messages[idx:] = recent).
        Always returns an index that does not orphan a tool message from
        its assistant tool_calls partner.
    """
    total = estimate_tokens(messages, model=model, config=config)
    target = int(total * keep_ratio)
    running = 0
    split = 0
    for i in range(len(messages) - 1, -1, -1):
        running += estimate_tokens([messages[i]], model=model, config=config)
        if running >= target:
            split = i
            break
    # Walk forward until we land on a non-tool message, so the recent
    # portion never starts with an orphaned tool result.
    while split < len(messages) and messages[split].get("role") == "tool":
        split += 1
    return split


def compact_messages(messages: list, config: dict, focus: str = "") -> list:
    """Compress old messages into a summary via LLM call.

    Splits at find_split_point, summarizes old portion, returns
    [summary_msg, ack_msg, *recent_messages].

    Smart behavior: messages with high priority score (errors, decisions,
    file references) are preserved verbatim instead of being summarized away.

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

    old = messages[:split]
    recent = messages[split:]

    # ── Smart separation: keep high-priority messages verbatim ──
    # Skip `tool` messages and `assistant` messages with tool_calls — pinning
    # either alone orphans the pair and triggers
    # `tool_call_id is not found` (HTTP 400) on the next API call.
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

    # Build summary request from non-pinned messages only
    old_text = ""
    for m in to_summarize:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, str):
            old_text += f"[{role}]: {content[:500]}\n"
        elif isinstance(content, list):
            old_text += f"[{role}]: (structured content)\n"

    summary_prompt = (
        "Summarize the following conversation history concisely. "
        "Preserve key decisions, file paths, tool results, and context "
        "needed to continue the conversation."
    )
    if focus:
        summary_prompt += f"\n\nFocus especially on: {focus}"
    if pinned:
        summary_prompt += (
            f"\n\nNote: {len(pinned)} high-priority messages (errors, "
            f"decisions, file references) will be preserved verbatim."
        )
    summary_prompt += "\n\n" + old_text

    # Call LLM for summary
    summary_text = ""
    for event in providers.stream(
        model=config["model"],
        system="You are a concise summarizer.",
        messages=[{"role": "user", "content": summary_prompt}],
        tool_schemas=[],
        config=config,
    ):
        if isinstance(event, providers.TextChunk):
            summary_text += event.text

    summary_msg = {
        "role": "user",
        "content": f"[Previous conversation summary]\n{summary_text}",
    }
    ack_msg = {
        "role": "assistant",
        "content": "Understood. I have the context from the previous conversation. Let's continue.",
    }

    # Result: summary + ack + pinned high-priority old messages + recent
    result = [summary_msg, ack_msg]
    if pinned:
        result.append({
            "role": "user",
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

    # Layer 2: auto-compact
    state.messages = compact_messages(state.messages, config)
    state.messages.extend(_restore_plan_context(config))
    return True


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

    Returns (success, info_message).
    """
    if len(state.messages) < 4:
        return False, "Not enough messages to compact."

    model = config.get("model", "")
    before = estimate_tokens(state.messages, model=model, config=config)
    snip_old_tool_results(state.messages)
    state.messages = compact_messages(state.messages, config, focus=focus)
    state.messages.extend(_restore_plan_context(config))
    after = estimate_tokens(state.messages, model=model, config=config)
    saved = before - after
    return True, f"Compacted: ~{before} → ~{after} tokens (~{saved} saved)"
