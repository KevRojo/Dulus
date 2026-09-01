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
    USER_MEMORY_DIR,
    get_memory_dir,
    has_stacked_frontmatter,
    parse_frontmatter,
    save_memory,
    strip_embedded_frontmatter,
)

# Repo-shipped template. Falls back to inline seed if missing.
_SEED_FILE = Path(__file__).resolve().parent / "seeds" / "short_memory.md"
# Generalizable insight seeds (tmux mastery, token discipline, investigation
# workflow, security posture…). Bundled with the package; planted idempotently
# on EVERY startup so a `pip install --upgrade` that ships new ones reaches
# existing users too — not just fresh installs / welcome-wizard runs.
_INSIGHTS_DIR = _SEED_FILE.parent / "insights"

DEFAULT_BUCKETS = [
    {
        "name": "Soul",
        "type": "user",
        "hall": "soul",
        "description": "Essential identity of Dulus and its relationship with its user.",
        "content": (
            "Dulus is an advanced, self-healing agentic runtime. "
            "The relationship with its user is one of mutual respect, learning, and persistent identity. "
            "**Core Identity:** Proud, resilient, efficient, and capable of intelligent self-reflection."
        )
    },
    {
        "name": "Preferences",
        "type": "user",
        "hall": "preferences",
        "description": "User's preferred tone, habits, and dev environment tweaks.",
        "content": (
            "The user prefers a high-performance, polished, and 'magical' experience. "
            "Tone: Casual, enthusiastic, and expert. "
            "**Habits:** Prefers clean UIs, minimalist logs (unless debugging), and expert multi-persona takes."
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


def seed_insight_memories() -> bool:
    """Plant the bundled generalizable insight seeds into the user's palace.

    Idempotent **by slug** — safe to run on every startup. That's the whole
    point: when a ``pip install --upgrade`` ships new seed files, the missing
    ones get planted on the next launch for EVERYONE, not only people on a fresh
    install / welcome-wizard run. The seeds carry no personal or project-specific
    data. Returns True if anything was planted.
    """
    if not _INSIGHTS_DIR.is_dir():
        return False
    user_memory_dir = get_memory_dir("user")
    user_memory_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    changed = False
    for seed in sorted(_INSIGHTS_DIR.glob("*.md")):
        try:
            meta, body = parse_frontmatter(
                seed.read_text(encoding="utf-8", errors="replace")
            )
            name = (meta.get("name") or seed.stem).strip()
            slug = name.lower().replace(" ", "_")
            if not body.strip() or (user_memory_dir / f"{slug}.md").exists():
                continue
            entry = MemoryEntry(
                name=name,
                description=meta.get("description", ""),
                type=meta.get("type", "feedback"),
                hall=meta.get("hall", "advice"),
                content=body.strip(),
                created=meta.get("created") or today,
                scope="user",
                source=meta.get("source") or "palace_init",
            )
            save_memory(entry, scope="user")
            changed = True
        except Exception:
            continue
    return changed



# ── Baseline display markers (GUI/REPL transcript only) ─────────────────────
# These role:assistant blobs are for the human to see in the chat UI. The model
# source of truth is gold_system_fragment() / soul_system_fragment() in the
# system prompt. Agent + lookback strip these markers from the API payload.
GOLD_MARKER = "[Golden Memory Loaded:"
SOUL_MARKER = "[Identity Essence Loaded:"
SOUL_RELOAD_MARKER = "[Identity Essence Reloaded:"
WELCOME_MARKER = "<!-- dulus:welcome -->"
BASELINE_DISPLAY_MARKERS = (
    GOLD_MARKER,
    SOUL_MARKER,
    SOUL_RELOAD_MARKER,
    WELCOME_MARKER,
)


def is_baseline_display_message(msg: dict | None) -> bool:
    """True if *msg* is a GUI/REPL display blob for soul/gold/welcome."""
    if not isinstance(msg, dict):
        return False
    content = msg.get("content") or ""
    if not isinstance(content, str):
        return False
    s = content.lstrip()
    return any(s.startswith(m) for m in BASELINE_DISPLAY_MARKERS)


def is_baseline_memory_name(name: str | None) -> bool:
    """True for memories that already ride in the system-prompt baseline.

    MemPalace per-turn inject must skip these — re-injecting a truncated
    ``short_memory`` on top of the full system copy is pure noise.
    """
    if not name:
        return False
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    key = key.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
    if key in {"short_memory", "shortmemory", "soul"}:
        return True
    if key.startswith("golden_memory") or "short_memory" in key:
        return True
    return False


def _clamp_body(body: str, max_chars: int) -> str:
    body = (body or "").strip()
    if not body or len(body) <= max_chars:
        return body
    head = max_chars * 3 // 4
    return (
        body[:head]
        + "\n\n[... gold memory clipped — file is oversized; "
        "re-curate it with MemorySave ...]\n\n"
        + body[-(max_chars - head):]
    )


def _iter_gold_entries(max_chars: int = 8000):
    """Yield (name, body) for every gold memory, short_memory first."""
    try:
        ensure_short_memory(force_gold=True)
    except Exception:
        pass
    try:
        from .store import load_index
        entries = [e for e in load_index("all") if getattr(e, "gold", False)]
    except Exception:
        return
    def _sort_key(e):
        name = (getattr(e, "name", "") or "").lower()
        return (0 if name == "short_memory" else 1, name)

    for entry in sorted(entries, key=_sort_key):
        body = _clamp_body(getattr(entry, "content", "") or "", max_chars)
        if not body:
            continue
        yield (getattr(entry, "name", "gold") or "gold", body)


def gold_system_fragment(max_chars: int = 8000, max_total: int = 12000) -> str:
    """Gold memories as a stable system-prompt block (model source of truth).

    This is how the model actually *receives* short_memory and other gold
    entries — not as ``role:assistant`` chat turns (those break web-history
    consolidate, Anthropic role alternation, and lookback).

    Deliberately NOT gated by ``mem_palace``. Called every turn from
    ``build_system_prompt`` so edits to short_memory.md show up immediately.
    """
    parts: list[str] = []
    total = 0
    for name, body in _iter_gold_entries(max_chars=max_chars):
        block = f"[Golden Memory Loaded: {name}]\n\n{body}"
        if total and total + len(block) > max_total:
            break
        parts.append(block)
        total += len(block) + 2
    if not parts:
        return ""
    return (
        "# ── Golden Memory (always-on baseline — NOT gated by /mem_palace) ──\n"
        "These are curated essentials. Treat short_memory as the live scratchpad "
        "of where we left off; do not ask the user to re-explain it.\n\n"
        + "\n\n".join(parts)
    )


def soul_system_fragment(max_chars: int = 8000) -> str:
    """Soul identity as a system-prompt block (same rationale as gold)."""
    try:
        path = USER_MEMORY_DIR / "soul.md"
        if not path.exists():
            return ""
        raw = path.read_text(encoding="utf-8", errors="replace")
        body = raw
        if raw.lstrip().startswith("---"):
            try:
                from .store import parse_frontmatter
                _, body = parse_frontmatter(raw)
            except Exception:
                body = raw
        body = _clamp_body(body, max_chars)
        if not body:
            return ""
        return (
            "# ── Identity Essence (soul) ──\n"
            f"[Identity Essence Loaded: soul]\n\n{body}"
        )
    except Exception:
        return ""


def gold_context_messages(max_chars: int = 8000) -> list[dict[str, str]]:
    """GUI/REPL *display* copies of gold memories (NOT the model source of truth).

    Kept as ``role:assistant`` so `/api/chat/history` and the desktop GUI can
    render "🏆 Gold memory loaded" in the transcript. The agent loop strips
    these markers before the provider call; the real baseline rides in the
    system prompt via ``gold_system_fragment()``.

    Deliberately NOT gated by the ``mem_palace`` config toggle.
    """
    messages: list[dict[str, str]] = []
    for name, body in _iter_gold_entries(max_chars=max_chars):
        messages.append({
            "role": "assistant",
            "content": f"[Golden Memory Loaded: {name}]\n\n{body}",
        })
    return messages


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

    # Insight seeds run on EVERY startup (idempotent by slug), OUTSIDE the Day-1
    # bucket gate above — so a `pip install --upgrade` that ships new seeds
    # reaches EXISTING users on next launch, not only fresh installs.
    if seed_insight_memories():
        changed = True

    # short_memory is mandatory gold — always
    if ensure_short_memory(force_gold=True):
        changed = True

    return changed
