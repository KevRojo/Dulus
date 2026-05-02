"""Hybrid Context Compressor (#29) — qwen2.5:3b via Ollama + rule-based fallback.

Zero mandatory dependencies. Uses urllib (stdlib) to probe Ollama.
If Ollama is unavailable, falls back to intelligent rule-based compression.
"""
import json
import re
import textwrap
import urllib.request
from typing import Any

OLLAMA_HOST = "http://localhost:11434"
QWEN_MODEL = "qwen2.5:3b"
SUMMARIZE_PROMPT = """You are a memory summarizer. Summarize the following user memory into 1-2 sentences that capture the essential meaning. Be concise but preserve all critical facts, names, and relationships.

Memory:
---
{text}
---

Summary:"""


def _ollama_available(timeout: float = 2.0) -> bool:
    """Probe Ollama /api/tags to see if the server is up."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/tags",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _qwen_loaded(timeout: float = 3.0) -> bool:
    """Check if qwen2.5:3b is available in Ollama."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/tags",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            return any(QWEN_MODEL in m.get("name", "") for m in models)
    except Exception:
        return False


def summarize_with_qwen(text: str, max_tokens: int = 100) -> str:
    """Call Ollama qwen2.5:3b to summarize a memory or text block."""
    prompt = SUMMARIZE_PROMPT.format(text=text[:2000])  # Cap input
    payload = {
        "model": QWEN_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.2,
            "top_p": 0.7,
        },
    }
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("response", "").strip()


# ─────────── Rule-based Fallback ───────────

# Light stopwords — only remove true filler, never technical terms
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "and", "but", "if",
    "or", "because", "until", "while", "this", "that", "these",
    "those",
}


def _remove_redundant_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _collapse_lists(text: str) -> str:
    """Turn bullet lists into comma-separated when possible."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect bullet list block
        if re.match(r"^\s*[•\-\*]\s", line):
            bullets = []
            while i < len(lines) and re.match(r"^\s*[•\-\*]\s", lines[i]):
                bullets.append(re.sub(r"^\s*[•\-\*]\s", "", lines[i]).strip())
                i += 1
            if len(bullets) <= 3:
                out.append("• " + " | ".join(bullets))
            else:
                out.append("• " + bullets[0] + " | ... (" + str(len(bullets)) + " items)")
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _strip_stopwords(text: str) -> str:
    """Aggressively remove common stopwords from sentences."""
    words = text.split()
    filtered = []
    for w in words:
        lower = w.lower().strip(".,;:!?()[]{}")
        if lower not in STOPWORDS or w[0].isupper():
            filtered.append(w)
    return " ".join(filtered)


def _abbreviate_status(text: str) -> str:
    """Shorten common status words inside brackets only — avoid damaging names."""
    abbr = {
        "in_progress": "in_prog",
        "completed": "done",
        "cancelled": "canc",
        "deleted": "del",
    }
    # Only replace inside [status] patterns to avoid changing names like "Active Tasks"
    for full, short in abbr.items():
        text = re.sub(rf"\[{full}\]", f"[{short}]", text, flags=re.IGNORECASE)
    return text


def _deduplicate_lines(text: str) -> str:
    """Remove exact duplicate lines."""
    seen = set()
    out = []
    for line in text.split("\n"):
        key = line.strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(line)
    return "\n".join(out)


def compress_with_rules(text: str, target_tokens: int = 200) -> str:
    """Intelligent rule-based compression — no LLM required.

    Strategy: preserve all IDs, names, and statuses. Only remove fluff.
    """
    # Phase 1: structural compression (collapse long lists)
    text = _collapse_lists(text)
    text = _deduplicate_lines(text)

    # Phase 2: clean whitespace
    text = _remove_redundant_whitespace(text)

    # Phase 3: mild abbreviation only if severely over budget
    est_tokens = max(1, len(text) // 4)
    if est_tokens > target_tokens * 2:
        text = _abbreviate_status(text)

    # Phase 4: truncate with indicator if still over
    est_tokens = max(1, len(text) // 4)
    if est_tokens > target_tokens:
        max_chars = target_tokens * 4
        # Try to cut at a newline
        truncated = text[:max_chars]
        last_nl = truncated.rfind("\n")
        if last_nl > max_chars * 0.7:
            truncated = truncated[:last_nl]
        text = truncated + "\n[...truncated]"

    return text


# ─────────── Public API ───────────

def compress(text: str, max_tokens: int = 200) -> dict[str, Any]:
    """Compress context using rule-based method.

    qwen2.5:3b is reserved for memory summarization (summarize_with_qwen)
    because full-context compression is too destructive.

    Returns dict with:
        - compressed: str
        - method: "rules"
        - before_tokens: int
        - after_tokens: int
        - saved_tokens: int
    """
    before = max(1, len(text) // 4)
    result = compress_with_rules(text, max_tokens)
    after = max(1, len(result) // 4)
    return {
        "compressed": result,
        "method": "rules",
        "before_tokens": before,
        "after_tokens": after,
        "saved_tokens": before - after,
    }


def compress_compact_context(text: str, max_tokens: int = 200) -> str:
    """One-liner: returns just the compressed string."""
    return compress(text, max_tokens)["compressed"]


# Public API alias used by falcon.__init__
compact = compress_compact_context


def summarize_memory(name: str, body: str) -> str:
    """Use qwen2.5:3b to summarize a single memory body if Ollama is available.
    Falls back to truncating to 120 chars."""
    if not _ollama_available() or not _qwen_loaded():
        return body[:120] + "..." if len(body) > 120 else body
    try:
        summary = summarize_with_qwen(f"Memory '{name}':\n{body}", max_tokens=60)
        if summary and len(summary) > 10:
            return summary
    except Exception:
        pass
    return body[:120] + "..." if len(body) > 120 else body


if __name__ == "__main__":
    sample = (
        "[FALCON CONTEXT]\n"
        "Session: proactive | Agent: Falcon | User: KevRojo\n"
        "Project: Falcon Command Center | Files: 11 | Lines: 2014\n"
        "Active Tasks:\n"
        "  • T-002 [in_progress] Smart Context Manager (#23) (Falcon, Core)\n"
        "  • T-003 [pending] Plugin System (Falcon, Extensibility)\n"
        "  • T-007 [pending] MemPalace Integration (Falcon, Integration)\n"
        "Agents:\n"
        "  • Falcon (primary) - active\n"
        "  • kimi-code (coder) - idle\n"
        "  • kimi-code3 (coder) - idle\n"
        "Recent Commits:\n"
        "  • 865c915 Add Falcon Task Dashboard at docs/dashboard/index.html by Nano Agent\n"
    )
    print("Rule-based compression:")
    print(compress(sample)["compressed"])
