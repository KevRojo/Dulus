"""Historical session search utility."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from config import DAILY_DIR, SESSION_HIST_FILE

def search_session_history(query: str, max_results: int = 5) -> list[dict]:
    """Search for a query string across historical session logs.
    
    Checks both history.json (master) and daily/ copier directories.
    Returns list of hits: {session_id, saved_at, hits: [{role, content_snippet}]}.
    """
    query = query.lower()
    all_sessions = []

    # 1. Load history.json (master file)
    if SESSION_HIST_FILE.exists():
        try:
            data = json.loads(SESSION_HIST_FILE.read_text(encoding="utf-8", errors="replace"))
            all_sessions.extend(data.get("sessions", []))
        except Exception:
            pass
    
    # WSL Fallback: If in WSL and history is empty, check Windows home host
    import sys
    if not all_sessions and sys.platform == "linux" and Path("/mnt/c").exists():
        # Heuristic: try common Windows user paths
        # This is a bit of a hack but helpful for users running in WSL
        # who didn't symlink their .falcon folder yet.
        try:
            # Try to find a .falcon directory in any user folder on C:
            c_users = Path("/mnt/c/Users")
            for udir in c_users.iterdir():
                if not udir.is_dir(): continue
                win_hist = udir / ".falcon" / "sessions" / "history.json"
                if win_hist.exists():
                    data = json.loads(win_hist.read_text(encoding="utf-8", errors="replace"))
                    all_sessions.extend(data.get("sessions", []))
                    break
        except Exception:
            pass

    # 2. SUPPLEMENT: Scan daily folders for sessions not in history (if any)
    # This ensures we don't miss the absolute latest if history.json wasn't written yet
    known_ids = {s.get("session_id") for s in all_sessions if s.get("session_id")}
    
    if DAILY_DIR.exists():
        for day_dir in sorted(DAILY_DIR.iterdir(), reverse=True):
            if not day_dir.is_dir():
                continue
            for session_file in sorted(day_dir.glob("session_*.json"), reverse=True):
                try:
                    # Quick check: session ID is in filename session_HHMMSS_sid.json
                    sid = session_file.stem.split("_")[-1]
                    if sid in known_ids:
                        continue
                    
                    s_data = json.loads(session_file.read_text(encoding="utf-8", errors="replace"))
                    all_sessions.append(s_data)
                except Exception:
                    continue

    # 3. Perform search
    results = []
    for sess in all_sessions:
        session_id = sess.get("session_id", "unknown")
        saved_at   = sess.get("saved_at", "unknown")
        messages   = sess.get("messages", [])
        
        session_hits = []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
                
            if query in content.lower():
                # Extract snippet
                start = max(0, content.lower().find(query) - 60)
                end   = min(len(content), start + 200)
                snippet = content[start:end].replace("\n", " ")
                if start > 0: snippet = "..." + snippet
                if end < len(content): snippet += "..."
                
                session_hits.append({
                    "role": msg.get("role"),
                    "snippet": snippet
                })
        
        if session_hits:
            results.append({
                "session_id": session_id,
                "saved_at": saved_at,
                "hits": session_hits[:3] # limit hits per session to avoid bloat
            })

    # Sort sessions by recency (newest hit first)
    results.sort(key=lambda x: x["saved_at"], reverse=True)
    return results[:max_results]
