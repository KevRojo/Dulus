"""Utility functions for managing Dulus GUI sessions."""
import json
import datetime
import uuid
from pathlib import Path
from config import SESSIONS_DIR, DAILY_DIR, MR_SESSION_DIR, SESSION_HIST_FILE

def build_title(messages: list[dict]) -> str:
    """Generate a descriptive title from the first user message."""
    for m in messages:
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, list):
                # Handle multi-modal or list content
                text = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
            else:
                text = str(content)
            
            if text.strip():
                clean = text.strip().replace("\n", " ")
                return clean[:40] + ("..." if len(clean) > 40 else "")
    return "Nueva conversación"

def scan_sessions() -> list[dict]:
    """Scan session directories and return sorted list of metadata."""
    sessions: list[dict] = []
    seen: set[str] = set()
    files: list[Path] = []

    # Daily sessions (newest first)
    if DAILY_DIR.exists():
        for day_dir in sorted(DAILY_DIR.iterdir(), reverse=True):
            if day_dir.is_dir():
                files.extend(sorted(day_dir.glob("session_*.json"), reverse=True))

    # MR sessions
    if MR_SESSION_DIR.exists():
        files.extend(
            s for s in sorted(MR_SESSION_DIR.glob("*.json"), reverse=True)
            if s.name != "session_latest.json"
        )

    # Root sessions
    if SESSIONS_DIR.exists():
        files.extend(sorted(SESSIONS_DIR.glob("session_*.json"), reverse=True))

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            sid = data.get("session_id", path.stem)
            if sid in seen:
                continue
            seen.add(sid)
            
            messages = data.get("messages", [])
            title = build_title(messages)
            
            saved_at = data.get("saved_at", "")
            if saved_at and len(saved_at) >= 19:
                # Add time prefix: "HH:MM  Title"
                title = f"{saved_at[11:16]}  {title}"
            
            sessions.append({
                "id": sid, 
                "title": title, 
                "path": str(path), 
                "messages": messages,
                "saved_at": saved_at
            })
        except Exception:
            continue

    # Sort all found sessions by saved_at DESC
    sessions.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return sessions[:50]

def save_session(state, config: dict, session_id: str | None = None) -> str:
    """Save AgentState to disk in standard Dulus format. Returns the session_id."""
    if not state.messages:
        return ""
    
    # User request: Only save if there is at least one user message
    has_user_msg = any(m.get("role") == "user" for m in state.messages)
    if not has_user_msg:
        return ""

    sid = session_id or uuid.uuid4().hex[:8]
    now = datetime.datetime.now()
    ts = now.strftime("%H%M%S")
    date_str = now.strftime("%Y-%m-%d")
    
    # 1. Build payload
    data = {
        "session_id": sid,
        "saved_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "messages": state.messages,
        "turn_count": getattr(state, "turn_count", len(state.messages) // 2),
        "total_input_tokens": getattr(state, "total_input_tokens", 0),
        "total_output_tokens": getattr(state, "total_output_tokens", 0),
    }
    payload = json.dumps(data, indent=2, default=str)

    # 2. Save latest for /resume
    MR_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    (MR_SESSION_DIR / "session_latest.json").write_text(payload, encoding="utf-8")

    # 3. Save to daily folder
    day_dir = DAILY_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    
    # Prune old copies for this session ID
    for old_copy in day_dir.glob(f"session_*_{sid}.json"):
        try:
            old_copy.unlink()
        except: pass

    daily_path = day_dir / f"session_{ts}_{sid}.json"
    daily_path.write_text(payload, encoding="utf-8")

    # 4. Update history.json
    try:
        hist = {"total_turns": 0, "sessions": []}
        if SESSION_HIST_FILE.exists():
            try:
                hist = json.loads(SESSION_HIST_FILE.read_text())
            except Exception:
                pass
        
        # Update or append
        existing_idx = -1
        for i, s in enumerate(hist.get("sessions", [])):
            if s.get("session_id") == sid:
                existing_idx = i
                break
        
        if existing_idx >= 0:
            hist["sessions"][existing_idx] = data
        else:
            hist["sessions"].append(data)
            
        # Prune history (keep 200)
        limit = config.get("session_history_limit", 200)
        if len(hist["sessions"]) > limit:
            hist["sessions"] = hist["sessions"][-limit:]
            
        SESSION_HIST_FILE.write_text(json.dumps(hist, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass # Don't crash UI if history.json fails

    return sid

def delete_session(session_id: str) -> bool:
    """Delete all session files related to the given ID. Returns True if any deleted."""
    if not session_id:
        return False

    deleted = False
    
    # 1. Scan and delete in MR_SESSION_DIR (except latest maybe?)
    if MR_SESSION_DIR.exists():
        for p in MR_SESSION_DIR.glob(f"*{session_id}*"):
            try:
                p.unlink()
                deleted = True
            except: pass

    # 2. Daily sessions
    if DAILY_DIR.exists():
        for d in DAILY_DIR.iterdir():
            if d.is_dir():
                for p in d.glob(f"*{session_id}*"):
                    try:
                        p.unlink()
                        deleted = True
                    except: pass

    # 3. Root sessions
    if SESSIONS_DIR.exists():
        for p in SESSIONS_DIR.glob(f"*{session_id}*"):
            try:
                p.unlink()
                deleted = True
            except: pass

    # 4. Update history.json
    if SESSION_HIST_FILE.exists():
        try:
            hist = json.loads(SESSION_HIST_FILE.read_text())
            original_len = len(hist.get("sessions", []))
            hist["sessions"] = [s for s in hist.get("sessions", []) if s.get("session_id") != session_id]
            if len(hist["sessions"]) < original_len:
                SESSION_HIST_FILE.write_text(json.dumps(hist, indent=2, default=str), encoding="utf-8")
                deleted = True
        except: pass

    return deleted
