"""Memory Palace: Day 1 initialization of essential long-term memory buckets."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from .store import MemoryEntry, save_memory, USER_MEMORY_DIR

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

def ensure_memory_palace() -> bool:
    """Check if the user memory directory is empty/new and initialize default buckets.
    
    Returns:
        True if initialization was performed, False otherwise.
    """
    USER_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # We check if there are any .md files other than MEMORY.md
    existing_files = list(USER_MEMORY_DIR.glob("*.md"))
    content_files = [f for f in existing_files if f.name != "MEMORY.md"]
    
    if len(content_files) > 1:
        # Palace already exists (Soul + at least one other) or migrated
        return False
    
    initialized_count = 0
    today = datetime.now().strftime("%Y-%m-%d")
    
    for bucket in DEFAULT_BUCKETS:
        # Check if this specific bucket already exists to avoid overwriting a custom Soul
        slug = bucket["name"].lower().replace(" ", "_")
        if (USER_MEMORY_DIR / f"{slug}.md").exists():
            continue
            
        entry = MemoryEntry(
            name=bucket["name"],
            description=bucket["description"],
            type=bucket["type"],
            hall=bucket["hall"],
            content=bucket["content"],
            created=today,
            scope="user",
            source="palace_init"
        )
        save_memory(entry, scope="user")
        initialized_count += 1
        
    return initialized_count > 0
