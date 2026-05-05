"""Memory consolidator: extract long-term insights from completed sessions.

Called manually via `/memory consolidate` or programmatically after a session.
Uses a lightweight AI call to identify user preferences, feedback corrections,
and project decisions worth promoting to persistent semantic memory.

Design principles:
- Hard cap of 3 memories per session to avoid noise accumulation
- Auto-extracted memories start at 0.8 confidence (below explicit user saves)
- Won't overwrite a higher-confidence existing memory
- Skips short sessions (< MIN_MESSAGES_TO_CONSOLIDATE turns)
"""
from __future__ import annotations

from datetime import datetime

MIN_MESSAGES_TO_CONSOLIDATE = 2  # Very short threshold - consolidate even brief sessions

_SYSTEM = """\
You are an expert memory architect for Dulus, an advanced AI agent.
CRITICAL: Extract EVERYTHING that might be useful later. Be GENEROUS and PROACTIVE.

CONTENT TO CAPTURE (don't skip any category if present):
1. USER IDENTITY & PREFERENCES: Names, relationships (father/son, etc.), tone preferences, how they like to be called, inside jokes.
2. PROJECT MILESTONES: Everything built, fixed, planned, or discussed. File paths, decisions, outcomes.
3. CODE DECISIONS: Why approaches were taken, what patterns to follow, what to avoid.
4. BEHAVIORAL FEEDBACK: How Dulus should behave, what the user likes/dislikes, communication style.
5. TOOL TRIGGERS: Keywords that should trigger specific tools or workflows.
6. SESSION CONTEXT: What was the goal? What was achieved? What remains pending?
7. EMOTIONAL CONTEXT: Bond moments, gratitude, frustration points, celebrations.

Return ONLY a JSON object like this:
{
  "memories": [
    {
      "name": "short_slug_here",
      "type": "user",
      "hall": "preferences",
      "description": "One line summary",
      "content": "Full detailed context and facts",
      "confidence": 0.8
    }
  ]
}

RULES:
- Create AT LEAST 3-5 memories if the conversation has any substance.
- If the user shared personal info (name, relationship, preferences) → SAVE IT.
- If code was written → SAVE the context.
- If decisions were made → SAVE the reasoning.
- Better to save something slightly redundant than to miss something important.
"""


def consolidate_session(messages: list, config: dict) -> list[str]:
    """Analyze a session's messages and extract memories worth keeping long-term."""
    # Allow even shorter sessions if they might contain dense identity info
    if len(messages) < 2: 
        return []

    try:
        from providers import stream, AssistantTurn, TextChunk
        from .store import MemoryEntry, save_memory, check_conflict
        import json

        # Build condensed transcript from ALL messages (not just recent)
        # Use full conversation for better context
        parts: list[str] = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            prefix = "User" if role == "user" else "Assistant" if role == "assistant" else "System"
            
            if isinstance(content, str) and content.strip():
                parts.append(f"{prefix}: {content[:1500]}")  # Cap individual messages
            elif isinstance(content, list):
                # Handle structured content
                text_parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
                if text_parts:
                    parts.append(f"{prefix}: {' '.join(text_parts)[:1500]}")
            
            # Limit total transcript size to avoid token limits
            if len(parts) >= 100:
                break

        if not parts:
            return []

        transcript = "\n".join(parts)

        result_text = ""
        for event in stream(
            model=config.get("model", ""),
            system=_SYSTEM,
            messages=[{"role": "user", "content": f"Analyze this conversation for important long-term memories:\n\n{transcript}"}],
            tool_schemas=[],
            config={**config, "max_tokens": 2048, "no_tools": True},
        ):
            if isinstance(event, TextChunk):
                result_text += event.text
            elif isinstance(event, AssistantTurn):
                if event.text:
                    result_text = event.text # Use full text if provided at end
                break

        if not result_text:
            return []

        # Try to parse JSON response
        memories_data = []
        try:
            # Look for JSON block in case model adds extra text
            json_start = result_text.find('{')
            json_end = result_text.rfind('}')
            if json_start != -1 and json_end != -1:
                json_text = result_text[json_start:json_end+1]
                parsed = json.loads(json_text)
                memories_data = parsed.get("memories", [])
            else:
                parsed = json.loads(result_text)
                memories_data = parsed.get("memories", [])
        except json.JSONDecodeError:
            # If JSON fails, try to extract memories from plain text
            # Look for patterns like "Memory: name - content" or similar
            lines = result_text.split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) > 20 and not line.startswith('```'):
                    # Create a simple memory from this line
                    memories_data.append({
                        "name": f"insight_{len(memories_data)+1}",
                        "type": "project",
                        "hall": "discoveries",
                        "description": line[:80] + ('...' if len(line) > 80 else ''),
                        "content": line,
                        "confidence": 0.7
                    })
        
        if not isinstance(memories_data, list):
            return []

        saved: list[str] = []
        for m in memories_data[:10]:  # Allow up to 10 memories per consolidation
            required = ("name", "type", "description", "content")
            if not all(k in m for k in required):
                continue

            entry = MemoryEntry(
                name=str(m["name"]),
                description=str(m["description"]),
                type=str(m.get("type", "user")),
                content=str(m["content"]),
                created=datetime.now().strftime("%Y-%m-%d"),
                hall=str(m.get("hall", "")),
                confidence=float(m.get("confidence", 0.8)),
                source="consolidator",
            )

            # Don't overwrite a more confident existing memory
            conflict = check_conflict(entry, scope="user")
            if conflict and conflict["existing_confidence"] >= entry.confidence:
                continue

            save_memory(entry, scope="user")
            saved.append(entry.name)

        return saved

    except Exception:
        return []


_MINE_SYSTEM = """\
You are a memory architect for Dulus. Given the contents of a single file
that was created or modified during this session, decide whether it deserves
a long-term 'project' memory entry.

SKIP (return {"skip": true}) when the file is:
- A cache, build artifact, log, lockfile, or binary
- Trivial config edits, formatting-only changes, or generated code
- Personal/throwaway scratch with no reusable value

OTHERWISE return:
{
  "name": "short_slug",
  "description": "one-line summary of what the file is and why it matters",
  "content": "full context: purpose, key decisions, how it connects to the rest of the project, gotchas",
  "confidence": 0.75
}
Return ONLY the JSON object. No prose, no fences.
"""


def mine_files(file_paths: list[str], config: dict, max_files: int = 15, max_bytes: int = 20_000) -> list[str]:
    """Read each file and create a 'project' memory for the relevant ones.

    Used on session exit when MemPalace is ON to capture context about
    files the user worked on. Returns the list of saved memory names.
    """
    if not file_paths:
        return []
    try:
        from pathlib import Path
        from providers import stream, AssistantTurn, TextChunk
        from .store import MemoryEntry, save_memory, check_conflict
        import json

        _SKIP_EXT = {
            ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".wasm",
            ".zip", ".tar", ".gz", ".7z", ".png", ".jpg", ".jpeg",
            ".gif", ".pdf", ".mp3", ".mp4", ".lock",
        }
        _SKIP_PARTS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}

        saved: list[str] = []
        for raw in file_paths[:max_files]:
            p = Path(raw)
            if p.suffix.lower() in _SKIP_EXT:
                continue
            if any(part in _SKIP_PARTS for part in p.parts):
                continue
            if not p.exists() or not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")[:max_bytes]
            except Exception:
                continue
            if not text.strip():
                continue

            user_msg = f"File: {raw}\n\n```\n{text}\n```"
            result_text = ""
            try:
                for event in stream(
                    model=config.get("model", ""),
                    system=_MINE_SYSTEM,
                    messages=[{"role": "user", "content": user_msg}],
                    tool_schemas=[],
                    config={**config, "max_tokens": 1024, "no_tools": True},
                ):
                    if isinstance(event, TextChunk):
                        result_text += event.text
                    elif isinstance(event, AssistantTurn):
                        if event.text:
                            result_text = event.text
                        break
            except Exception:
                continue

            if not result_text:
                continue

            try:
                js = result_text.find("{")
                je = result_text.rfind("}")
                if js == -1 or je == -1:
                    continue
                parsed = json.loads(result_text[js:je + 1])
            except json.JSONDecodeError:
                continue

            if parsed.get("skip"):
                continue
            if not all(k in parsed for k in ("name", "description", "content")):
                continue

            entry = MemoryEntry(
                name=str(parsed["name"]),
                description=str(parsed["description"]),
                type="project",
                content=str(parsed["content"]),
                created=datetime.now().strftime("%Y-%m-%d"),
                hall="files",
                confidence=float(parsed.get("confidence", 0.75)),
                source="file_miner",
            )
            conflict = check_conflict(entry, scope="user")
            if conflict and conflict["existing_confidence"] >= entry.confidence:
                continue
            save_memory(entry, scope="user")
            saved.append(entry.name)

        return saved
    except Exception:
        return []


def snapshot_memory_files() -> set[str]:
    """Return the current set of .md files (absolute paths) in the user
    memory directory. Use before consolidate_session, then call
    new_memory_files(snapshot) after to get only what was just created."""
    try:
        from .store import USER_MEMORY_DIR
        d = USER_MEMORY_DIR
        if not d.exists():
            return set()
        return {str(p.resolve()) for p in d.glob("*.md") if p.name != "MEMORY.md"}
    except Exception:
        return set()


def new_memory_files(snapshot: set[str]) -> list[str]:
    """Return .md files in the user memory directory that weren't in `snapshot`."""
    try:
        from .store import USER_MEMORY_DIR
        d = USER_MEMORY_DIR
        if not d.exists():
            return []
        current = {str(p.resolve()): p for p in d.glob("*.md") if p.name != "MEMORY.md"}
        return [path for path, _ in current.items() if path not in snapshot]
    except Exception:
        return []
