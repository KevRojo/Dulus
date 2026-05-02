"""Smart Context Manager (#23 + #28) — generates optimized context for LLM sessions."""
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from backend.compressor import compress
from backend.mempalace_bridge import get_mempalace_compact_text, get_mempalace_context_block
from backend.personas import get_personas_for_context, get_active_persona, get_persona_compact_text
from backend.tasks import load_tasks

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CONTEXT_FILE = DATA_DIR / "context.json"


def run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git"] + args, cwd=Path(__file__).parent.parent, stderr=subprocess.DEVNULL, text=True
        )
    except Exception:
        return ""


def get_recent_commits(n: int = 5) -> list[dict[str, str]]:
    out = run_git(["log", f"-{n}", "--pretty=format:%h|%s|%an|%ad", "--date=short"])
    commits = []
    for line in out.strip().split("\n"):
        if "|" in line:
            h, s, a, d = line.split("|", 3)
            commits.append({"hash": h, "subject": s, "author": a, "date": d})
    return commits


def get_changed_files() -> list[str]:
    out = run_git(["diff", "--name-only", "HEAD~1"])
    return [f for f in out.strip().split("\n") if f]


def get_repo_stats() -> dict[str, Any]:
    root = Path(__file__).parent.parent
    stats = {"files": 0, "lines": 0, "languages": {}}
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts:
            stats["files"] += 1
            ext = path.suffix or "no_ext"
            try:
                lc = sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
                stats["lines"] += lc
                stats["languages"][ext] = stats["languages"].get(ext, 0) + lc
            except Exception:
                pass
    return stats


def get_active_tasks_summary() -> list[dict[str, Any]]:
    tasks = load_tasks()
    return [
        {"id": t["id"], "subject": t["subject"], "status": t["status"], "owner": t["owner"], "phase": t.get("metadata", {}).get("phase", "")}
        for t in tasks if t["status"] in ("pending", "in_progress")
    ]


def build_context() -> dict[str, Any]:
    """Build comprehensive session context with real MemPalace memories."""
    active = get_active_persona()
    context = {
        "session": {
            "mode": "proactive",
            "agent": active["name"],
            "agent_id": active["id"],
            "user": "KevRojo",
            "location": "RD"
        },
        "project": {
            "name": "Falcon Command Center",
            "repo_stats": get_repo_stats(),
            "recent_commits": get_recent_commits(),
            "recent_changes": get_changed_files()
        },
        "tasks": {
            "active": get_active_tasks_summary(),
            "total": len(get_active_tasks_summary())
        },
        "agents": get_personas_for_context(),
        "persona": {
            "id": active["id"],
            "name": active["name"],
            "role": active["role"],
            "color": active["color"],
            "avatar": active.get("avatar", "🤖"),
            "tone": active["tone"],
        },
        "memory": get_mempalace_context_block()
    }
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2, ensure_ascii=False)
    return context


def load_context() -> dict[str, Any]:
    if CONTEXT_FILE.exists():
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return build_context()


# ─────────── Token & Smart Context Management ───────────

def get_user_max_tokens() -> int:
    try:
        config_file = Path.home() / ".falcon" / "config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.loads(f.read())
                return int(data.get("max_tokens", 8000))
    except Exception:
        pass
    return 8000

MAX_CONTEXT_TOKENS = get_user_max_tokens()
COMPACT_THRESHOLD = 0.75
EMERGENCY_THRESHOLD = 0.90
COMPACTION_HISTORY: list[dict[str, Any]] = []


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for English/code."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def get_context_mode(token_pct: float) -> str:
    if token_pct >= EMERGENCY_THRESHOLD:
        return "emergency"
    if token_pct >= COMPACT_THRESHOLD:
        return "compact"
    return "normal"


def record_compaction(reason: str, before_tokens: int, after_tokens: int) -> None:
    COMPACTION_HISTORY.append({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reason": reason,
        "before_tokens": before_tokens,
        "after_tokens": after_tokens,
        "saved_tokens": before_tokens - after_tokens,
    })
    # Keep last 20
    while len(COMPACTION_HISTORY) > 20:
        COMPACTION_HISTORY.pop(0)


def build_smart_context() -> dict[str, Any]:
    """Build context with token estimation and mode detection.

    When mode is compact or emergency, applies rule-based compression
    to keep context under budget. qwen2.5:3b is used for memory
    summarization via mempalace_bridge, not for full-context compression.
    """
    ctx = build_context()
    compact_text = get_compact_context()
    tokens = estimate_tokens(compact_text)
    
    try:
        import sys
        if "webchat_server" in sys.modules:
            from webchat_server import STATE
            if STATE and hasattr(STATE, "messages"):
                for msg in STATE.messages:
                    tokens += estimate_tokens(str(msg))
    except Exception:
        pass

    pct = round(tokens / MAX_CONTEXT_TOKENS, 4)
    mode = get_context_mode(pct)

    compressed_text = compact_text
    compressor_method = "none"

    if mode in ("compact", "emergency"):
        target = 400 if mode == "compact" else 200
        result = compress(compact_text, max_tokens=target)
        compressed_text = result["compressed"]
        compressor_method = result["method"]
        record_compaction(
            reason=f"auto-{mode}",
            before_tokens=result["before_tokens"],
            after_tokens=result["after_tokens"],
        )

    ctx["smart_context"] = {
        "tokens_used": estimate_tokens(compressed_text),
        "tokens_max": MAX_CONTEXT_TOKENS,
        "usage_percent": pct,
        "mode": mode,
        "thresholds": {
            "compact": COMPACT_THRESHOLD,
            "emergency": EMERGENCY_THRESHOLD,
        },
        "compact_text": compressed_text,
        "compressor_method": compressor_method,
        "compaction_history": COMPACTION_HISTORY,
    }

    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False)
    return ctx


def force_compaction() -> dict[str, Any]:
    """Manually force compression of the context."""
    ctx = build_context()
    compact_text = get_compact_context()
    result = compress(compact_text, max_tokens=200)
    compressed_text = result["compressed"]
    compressor_method = result["method"]
    record_compaction(
        reason="manual-force",
        before_tokens=result["before_tokens"],
        after_tokens=result["after_tokens"],
    )
    
    # Actually trim the STATE.messages array so live token count decreases
    try:
        import sys
        if "webchat_server" in sys.modules:
            from webchat_server import STATE
            if STATE and hasattr(STATE, "messages") and len(STATE.messages) > 10:
                # Keep system block (first message) and the last ~6 messages
                new_msgs = [STATE.messages[0]]
                
                # Add a system message notifying of the compaction
                new_msgs.append({
                    "role": "system",
                    "content": "[SYSTEM EVENT: Conversation history was forcefully compacted by the user. Older messages were purged.]"
                })
                
                # Handle the remaining messages carefully to avoid breaking API tool_call parity
                raw_kept = STATE.messages[-6:]
                sanitized_kept = []
                for m in raw_kept:
                    # Drop tool responses entirely to avoid orphaned IDs
                    if m.get("role") == "tool":
                        continue
                        
                    sm = dict(m)
                    # Strip any outgoing tool_calls from assistant messages
                    if "tool_calls" in sm:
                        del sm["tool_calls"]
                    if "tool_call_id" in sm:
                        del sm["tool_call_id"]
                        
                    # If this leaves an assistant message with NO content, drop it too
                    if sm.get("role") == "assistant" and not sm.get("content"):
                        continue
                        
                    # Ensure content is stringified if it was a list of chunks
                    if isinstance(sm.get("content"), list):
                        sm["content"] = "\n".join(
                            c.get("text", "") for c in sm["content"] if c.get("type", "") == "text"
                        )
                        
                    sanitized_kept.append(sm)
                    
                new_msgs.extend(sanitized_kept)
                STATE.messages = new_msgs
                import webchat_server
                webchat_server.broadcast_event("chat_cleared", {}) # Force UI refresh if needed
    except Exception as e:
        print("Compaction physical trim error:", e)
    
    tokens = estimate_tokens(compressed_text)
    
    try:
        import sys
        if "webchat_server" in sys.modules:
            from webchat_server import STATE
            if STATE and hasattr(STATE, "messages"):
                for msg in STATE.messages:
                    tokens += estimate_tokens(str(msg))
    except Exception:
        pass

    pct = round(tokens / MAX_CONTEXT_TOKENS, 4)
    mode = get_context_mode(pct)
    
    ctx["smart_context"] = {
        "tokens_used": tokens,
        "tokens_max": MAX_CONTEXT_TOKENS,
        "usage_percent": pct,
        "mode": "compact",
        "thresholds": {"compact": COMPACT_THRESHOLD, "emergency": EMERGENCY_THRESHOLD},
        "compact_text": compressed_text,
        "compressor_method": compressor_method,
        "compaction_history": COMPACTION_HISTORY,
    }
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=2, ensure_ascii=False)
    return ctx


def get_compact_context(max_tokens_estimate: int = 800) -> str:
    """Generate ultra-dense text context for LLM prompt injection."""
    ctx = build_context()
    lines = [
        "[FALCON CONTEXT]",
        f"Session: {ctx['session']['mode']} | Agent: {ctx['session']['agent']} | User: {ctx['session']['user']}",
        f"Project: {ctx['project']['name']} | Files: {ctx['project']['repo_stats']['files']} | Lines: {ctx['project']['repo_stats']['lines']}",
        "Active Tasks:"
    ]
    for t in ctx["tasks"]["active"][:5]:
        lines.append(f"  • {t['id']} [{t['status']}] {t['subject']} ({t['owner']}, {t['phase']})")
    lines.append("Agents:")
    for a in ctx["agents"]:
        marker = " [ACTIVE]" if a.get("active") else ""
        lines.append(f"  • {a.get('avatar', '🤖')} {a['name']} ({a['role']}) - {a['status']}{marker}")
    lines.append("Recent Commits:")
    for c in ctx["project"]["recent_commits"][:3]:
        lines.append(f"  • {c['hash']} {c['subject']} by {c['author']}")
    # ── Persona activa (#19/#22) ──
    lines.append(get_persona_compact_text())
    # ── MemPalace real memories (#28) ──
    lines.append(get_mempalace_compact_text())
    return "\n".join(lines)
