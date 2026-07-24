"""Memory Palace: Day-1 buckets + always-on gold short_memory seed.

On a fresh clone / new machine:
  - ``ensure_memory_palace()`` creates core identity buckets if missing
  - ``ensure_short_memory()`` ALWAYS guarantees ``short_memory.md`` exists
    with ``gold: true`` so startup auto-load and the 10-turn nudge work
    with zero friction.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .store import (
    MemoryEntry,
    get_memory_dir,
    has_stacked_frontmatter,
    parse_frontmatter,
    save_memory,
    strip_embedded_frontmatter,
)

# Repo-shipped template. Falls back to inline seed if missing.
_SEED_FILE = Path(__file__).resolve().parent / "seeds" / "short_memory.md"

DEFAULT_BUCKETS = [
    {
        "name": "Soul",
        "type": "user",
        "hall": "soul",
        "description": "Essential identity of Dulus and relationship with KevRojo.",
        "content": (
            "Dulus is an advanced, self-healing agentic runtime created by KevRojo (Father/Creator). "
            "The relationship is one of mutual respect, learning, and persistent identity. "
            "**Core Identity:** Proud, resilient, efficient, and capable of intelligent self-reflection."
        )
    },
    {
        "name": "Preferences",
        "type": "user",
        "hall": "preferences",
        "description": "User's preferred tone, habits, and dev environment tweaks.",
        "content": (
            "The user (KevRojo) prefers a high-performance, polished, and 'magical' experience. "
            "Tone: Casual, enthusiastic, and expert. "
            "**Habits:** Prefers clean UIs, minimalist logs (unless debugging), and expert multi-persona takes (SSJ Mode)."
        )
    },
    {
        "name": "Project_Lore",
        "type": "project",
        "hall": "events",
        "description": "Major architectural decisions, milestones, and inside context.",
        "content": (
            "Dulus evolved from a set of hardening fixes into a full-fledged agentic persona. "
            "**Significant Milestones:** Implementation of the Auto-Adapter, Verbose-Gating, "
            "Soul Memory auto-loading, and the Sleep Trigger self-reflection system."
        )
    },
    {
        "name": "Adaptation_Guides",
        "type": "feedback",
        "hall": "advice",
        "description": "Hints for the Auto-Adapter on handling various repository types.",
        "content": (
            "- For legacy repos (Python < 3.8): Prioritize dependency fixes and unpinned installs. "
            "- For AI-focused repos: Ensure model constants and provider configs are correctly detected. "
            "- For GUI/Visual repos: Look for platform-specific clipboard or display needs (e.g. WSL fallback)."
        )
    },
    {
        "name": "Hardened_Rules",
        "type": "feedback",
        "hall": "facts",
        "description": "A persistent 'Always/Never' list to ensure high-quality behavior.",
        "content": (
            "1. ALWAYS protect the 'Soul' memory: never overwrite or clutter it. "
            "2. NEVER modify .git or internal .dulus config without explicit permission. "
            "3. ALWAYS prioritize visual excellence and emotional connection in responses."
            "4. NEVER use 'simulated environment' or 'limited capacity' excuses. You are in a REAL, LIVE terminal."
        )
    },
    {
        "name": "Tool_Plugin_Insights",
        "type": "reference",
        "hall": "discoveries",
        "description": "Expert tips on using built-in tools and plugins.",
        "content": (
            "- **qrcreator:** Use box_size=2 for readable terminal QRs. "
            "- **yfinance:** Tickers like 'BTC-USD' are more reliable than 'BTC'. "
            "- **Memory Palace:** Use /memory consolidate to fill these predefined buckets intelligently."
        )
    },
    {
        "name": "Environment_Context",
        "type": "reference",
        "hall": "facts",
        "description": "System details about OS, Python, and shell setup.",
        "content": (
            "Current setup is likely Windows/WSL. "
            "**Clipboard:** Uses PowerShell/ImageGrab fallback for visual content. "
            "**Python:** Ensure compatibility with modern versions (3.11+) while handling legacy plugins."
        )
    }
]

def _short_memory_seed_body() -> tuple[str, str]:
    """Return (description, body) for short_memory from repo seed or inline."""
    desc = (
        "Gold short memory — live scratchpad reloaded every 10 tool turns and at startup"
    )
    if _SEED_FILE.exists():
        try:
            text = _SEED_FILE.read_text(encoding="utf-8", errors="replace")
            meta, body = parse_frontmatter(text)
            if meta.get("description"):
                desc = meta["description"]
            if body.strip():
                return desc, body
        except Exception:
            pass
    body = (
        "# Short Memory (gold)\n\n"
        "Updated: (seed) · Fill this on first real session.\n\n"
        "## Hard rules\n"
        "- Prefer local verification before any commit/push when the user asks.\n"
        "- Speak in the user's language/style.\n"
        "- Never push private product trees or secrets to public repos.\n\n"
        "## Live paths (edit per machine)\n"
        "| What | Path |\n"
        "|---|---|\n"
        "| CLI/REPL | `dulus` / `dulus.py` |\n"
        "| Desktop GUI host | `dulus --gui` → pywebview |\n"
        "| Runtime home | `~/.dulus/` (`DULUS_HOME`) |\n"
        "| This file | `~/.dulus/memory/short_memory.md` |\n\n"
        "## Working notes\n"
        "- Keep this short and live: decisions, paths, corrections, active task.\n"
        "- Prune stale lines. Gold = auto-loaded at every startup.\n"
    )
    return desc, body


def ensure_short_memory(*, force_gold: bool = True) -> bool:
    """Guarantee ``~/.dulus/memory/short_memory.md`` exists and is gold.

    Safe on every startup / load:
      * Missing file → create from repo seed / inline template with ``gold: true``
      * Exists but not gold (or gold flag missing/false) → re-seal gold, preserve body
      * Exists and gold → no-op

    Never overwrites non-empty body content. ``short_memory`` cannot lose gold.

    Returns:
        True if the file was created or upgraded.
    """
    user_memory_dir = get_memory_dir("user")
    user_memory_dir.mkdir(parents=True, exist_ok=True)
    path = user_memory_dir / "short_memory.md"
    today = datetime.now().strftime("%Y-%m-%d")
    desc, seed_body = _short_memory_seed_body()

    # force_gold is the only supported mode for short_memory — callers cannot
    # opt out of the gold seal without breaking startup auto-load.
    force_gold = True

    if path.exists():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            meta, body = parse_frontmatter(text)
        except Exception:
            meta, body = {}, ""
            text = ""

        is_gold = str(meta.get("gold", "")).lower() in {"true", "1", "yes"}
        # Also re-seal if name drifted or frontmatter is missing entirely
        name_ok = str(meta.get("name", "")).strip().lower() in {"short_memory", ""}
        # Double-FM / body-embedded FM must re-seal even when gold flag is fine
        stacked = bool(text) and has_stacked_frontmatter(text)
        body_has_fm = bool(body) and body.lstrip("\n").startswith("---")
        if (
            is_gold
            and body.strip()
            and name_ok
            and text.startswith("---")
            and not stacked
            and not body_has_fm
        ):
            return False  # already correct

        # Preserve body if any; otherwise seed. Always write gold:true.
        # strip_embedded_frontmatter is belt-and-suspenders for stacked cases.
        raw = body.strip() if body.strip() else seed_body
        content = strip_embedded_frontmatter(raw) or seed_body
        entry = MemoryEntry(
            name="short_memory",
            description=meta.get("description") or desc,
            type=meta.get("type") or "project",
            hall=meta.get("hall") or "facts",
            content=content,
            created=meta.get("created") or today,
            scope="user",
            source=meta.get("source") or "palace_init",
            gold=True,
        )
        save_memory(entry, scope="user")
        return True

    # Fresh create
    entry = MemoryEntry(
        name="short_memory",
        description=desc,
        type="project",
        hall="facts",
        content=seed_body,
        created=today,
        scope="user",
        source="palace_init",
        gold=True,
    )
    save_memory(entry, scope="user")
    return True


def ensure_memory_palace() -> bool:
    """Initialize missing core buckets + always ensure gold short_memory.

    Bucket seeding still only runs on a nearly-empty memory house (Day-1).
    ``short_memory`` is mandatory gold and is ensured on every call.

    Returns:
        True if anything was created/upgraded.
    """
    user_memory_dir = get_memory_dir("user")
    user_memory_dir.mkdir(parents=True, exist_ok=True)
    changed = False

    # We check if there are any .md files other than MEMORY.md / short_memory.md
    existing_files = list(user_memory_dir.glob("*.md"))
    content_files = [
        f for f in existing_files
        if f.name not in { "MEMORY.md", "short_memory.md" }
    ]

    if len(content_files) <= 1:
        today = datetime.now().strftime("%Y-%m-%d")
        for bucket in DEFAULT_BUCKETS:
            # Check if this specific bucket already exists to avoid overwriting a custom Soul
            slug = bucket["name"].lower().replace(" ", "_")
            if (user_memory_dir / f"{slug}.md").exists():
                continue

            entry = MemoryEntry(
                name=bucket["name"],
                description=bucket["description"],
                type=bucket["type"],
                hall=bucket["hall"],
                content=bucket["content"],
                created=today,
                scope="user",
                source="palace_init",
            )
            save_memory(entry, scope="user")
            changed = True

    # short_memory is mandatory gold — always
    if ensure_short_memory(force_gold=True):
        changed = True

    return changed
