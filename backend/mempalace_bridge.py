"""MemPalace Bridge (#28) — connects Falcon Context Manager with real MemPalace memories.

Design: The bridge reads from a JSON cache maintained by the AI runtime.
When the AI has tool access, it refreshes the cache with real memories.
When running standalone (server.py, falcon.py), it reads the cached data.

This avoids requiring tool-injected globals inside Python subprocesses.
"""
import json
import os
import time
from pathlib import Path
from typing import Any

FALCON_DIR = Path(__file__).parent.parent
DATA_DIR = FALCON_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
MEMCACHE_FILE = DATA_DIR / "mempalace_cache.json"
MEMCACHE_TTL_SECONDS = 120  # Refresh every 2 minutes


def _parse_memory_document(doc: str) -> dict[str, Any]:
    """Parse a memory markdown document with YAML frontmatter."""
    lines = doc.strip().split("\n")
    meta: dict[str, Any] = {}
    body_lines: list[str] = []
    in_frontmatter = False
    frontmatter_delims = 0

    for line in lines:
        if line.strip() == "---":
            frontmatter_delims += 1
            in_frontmatter = frontmatter_delims == 1
            if frontmatter_delims >= 2:
                in_frontmatter = False
            continue
        if in_frontmatter:
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if len(body) > 350:
        body = body[:350] + "..."
    return {
        "name": meta.get("name", "unnamed"),
        "description": meta.get("description", ""),
        "type": meta.get("type", "unknown"),
        "hall": meta.get("hall", "general"),
        "confidence": float(meta.get("confidence", "0.8")) if meta.get("confidence") else 0.8,
        "body": body,
    }


def refresh_cache(raw_memories: list[dict[str, Any]], wings: list[str] | None = None) -> dict[str, Any]:
    """Called by the AI runtime when tools are available to refresh memory cache.

    Args:
        raw_memories: List of memory items from wakeup_context/search_memory tools.
        wings: Optional list of wing names discovered.
    """
    memories: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_memories:
        if not isinstance(item, dict):
            continue
        content = item.get("content", "")
        if not content:
            continue
        parsed = _parse_memory_document(content)
        parsed["wing"] = item.get("wing", "memory")
        parsed["source"] = item.get("source", "wakeup")
        if "relevance" in item:
            parsed["relevance"] = item["relevance"]
        key = parsed["name"]
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        memories.append(parsed)

    # Sort by confidence desc
    memories.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    data = {
        "connected": True,
        "wings": wings or ["memory", "hija_palace"],
        "count": len(memories),
        "memories": memories[:15],  # Cap to avoid bloat
        "_cached_at": time.time(),
    }
    try:
        with open(MEMCACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[MemPalace Bridge] Cache write failed: {e}")
    return data


def load_cache() -> dict[str, Any]:
    """Load memory cache from disk. Returns empty-safe dict."""
    if not MEMCACHE_FILE.exists():
        return {"connected": False, "wings": [], "count": 0, "memories": []}
    try:
        with open(MEMCACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Validate shape
        if "memories" not in data:
            data["memories"] = []
        return data
    except Exception:
        return {"connected": False, "wings": [], "count": 0, "memories": []}


def get_memories(max_items: int = 10) -> list[dict[str, Any]]:
    """Get deduplicated, ranked memories for context injection."""
    data = load_cache()
    return data.get("memories", [])[:max_items]


def _get_summary(name: str, body: str) -> str:
    """Get summary for a memory body — uses qwen if available, else truncates."""
    from backend.compressor import summarize_memory
    summary = summarize_memory(name, body)
    return summary.replace("\n", " ").strip()


def get_mempalace_compact_text(max_memories: int = 6) -> str:
    """Generate ultra-dense MemPalace context for prompt injection.

    Uses qwen2.5:3b via Ollama to summarize memory bodies when available.
    Falls back to truncation if Ollama is offline.
    """
    data = load_cache()
    if not data.get("connected") or not data.get("memories"):
        return "[MemPalace: disconnected — run refresh from AI runtime]"
    wings = data.get("wings", [])
    lines = [f"[MemPalace: {data['count']} memories | Wings: {', '.join(wings[:4])}]"]
    for m in data["memories"][:max_memories]:
        name = m.get("name", "?")
        hall = m.get("hall", "?")
        body = m.get("body", "").replace("\n", " ").strip()
        # Use qwen summarization for long bodies
        if len(body) > 120:
            body = _get_summary(name, body)
        if len(body) > 90:
            body = body[:90] + "..."
        lines.append(f"  • [{hall}] {name}: {body}")
    return "\n".join(lines)


def get_mempalace_context_block() -> dict[str, Any]:
    """Structured block for JSON context (used by build_context)."""
    data = load_cache()
    return {
        "connected": data.get("connected", False),
        "wings": data.get("wings", []),
        "count": data.get("count", 0),
        "memories": [
            {
                "name": m.get("name"),
                "hall": m.get("hall"),
                "type": m.get("type"),
                "description": m.get("description", "")[:120],
                "confidence": m.get("confidence"),
            }
            for m in data.get("memories", [])[:8]
        ],
    }


if __name__ == "__main__":
    # Show current cache status
    data = load_cache()
    print(f"[MemPalace Bridge] Connected: {data.get('connected')}")
    print(f"  Wings: {data.get('wings', [])}")
    print(f"  Memories: {data.get('count', 0)}")
    print("\nCompact text:")
    print(get_mempalace_compact_text())
