#!/usr/bin/env python3
"""
claude_code_watcher.py

Watches a Claude Code session JSONL file and extracts assistant responses
in real time. Can print to stdout or POST to a Falcon/webhook endpoint.

v2: Groups multi-part assistant turns (text + tool_use + text) into one
    complete message before sending. Fixes the bug where text after a
    tool call was sent as a separate/missing message.

Usage:
    python claude_code_watcher.py
    python claude_code_watcher.py --session <path_to.jsonl>
    python claude_code_watcher.py --post http://localhost:5000/claude_code_response
"""

import json
import sys
import time
import os
import argparse
from pathlib import Path


SESSION_DIR = Path.home() / ".claude" / "projects" / "C--Users-Admin-Desktop-FALCONV2"

# How long to wait (seconds) with no new assistant entries before flushing
# the accumulated turn as complete.
FLUSH_TIMEOUT = 2.5


def find_latest_session() -> Path | None:
    """Find the most recently modified JSONL session file."""
    files = list(SESSION_DIR.glob("*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def extract_text_blocks(entry: dict) -> list[str]:
    """Return all text strings from an assistant entry's content blocks."""
    msg = entry.get("message", {})
    if msg.get("role") != "assistant":
        return []
    content = msg.get("content", "")
    if isinstance(content, str):
        t = content.strip()
        return [t] if t else []
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text", "").strip()
                if t:
                    parts.append(t)
        return parts
    return []


def has_tool_use(entry: dict) -> bool:
    """True if this entry contains a tool_use block (mid-turn, more may follow)."""
    msg = entry.get("message", {})
    if msg.get("role") != "assistant":
        return False
    content = msg.get("content", "")
    if isinstance(content, list):
        return any(b.get("type") == "tool_use" for b in content if isinstance(b, dict))
    return False


def is_assistant(entry: dict) -> bool:
    return entry.get("message", {}).get("role") == "assistant"


def post_message(text: str, post_url: str):
    try:
        import urllib.request
        payload = json.dumps({
            "role": "assistant",
            "source": "claude-code",
            "text": text,
        }).encode("utf-8")
        req = urllib.request.Request(
            post_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[watcher] POST failed: {e}", flush=True)


def watch(session_path: Path, post_url: str | None = None, poll_interval: float = 0.5):
    """Tail the JSONL file and emit complete assistant turns."""
    print(f"[watcher] Watching: {session_path}", flush=True)
    print(f"[watcher] Post URL: {post_url or 'stdout only'}", flush=True)
    print(f"[watcher] Flush timeout: {FLUSH_TIMEOUT}s after last assistant entry", flush=True)

    seen_uuids: set = set()

    # Seed existing entries
    try:
        with open(session_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    uid = entry.get("uuid") or entry.get("id")
                    if uid:
                        seen_uuids.add(uid)
                except Exception:
                    pass
        print(f"[watcher] Seeded {len(seen_uuids)} existing entries.", flush=True)
    except Exception as e:
        print(f"[watcher] Could not seed: {e}", flush=True)

    # Accumulator for the current in-progress assistant turn
    pending_texts: list[str] = []
    pending_has_tool: bool = False
    last_assistant_time: float = 0.0

    while True:
        try:
            with open(session_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        uid = entry.get("uuid") or entry.get("id")
                        if uid in seen_uuids:
                            continue
                        seen_uuids.add(uid)

                        if not is_assistant(entry):
                            # Non-assistant entry (user / tool_result) — if we have
                            # pending text that ended with a tool_use, keep accumulating.
                            # We'll flush on timeout or when the next text-only turn arrives.
                            continue

                        texts = extract_text_blocks(entry)
                        tool = has_tool_use(entry)

                        if texts:
                            pending_texts.extend(texts)
                            last_assistant_time = time.time()

                        if tool:
                            pending_has_tool = True
                            last_assistant_time = time.time()

                        # If this entry has ONLY tool_use (no text) it means we're
                        # mid-turn — keep accumulating.
                        # If this entry has text AND no tool_use, it MIGHT be the
                        # final piece of the turn. We'll let the timeout decide.

                    except Exception:
                        pass

        except Exception as e:
            print(f"[watcher] Read error: {e}", flush=True)

        # Flush if we have accumulated text and the turn has been quiet for FLUSH_TIMEOUT
        if pending_texts and last_assistant_time > 0:
            elapsed = time.time() - last_assistant_time
            if elapsed >= FLUSH_TIMEOUT:
                full_text = "\n\n".join(pending_texts)
                print(f"\n[CLAUDE-CODE] {full_text[:300]}{'...' if len(full_text) > 300 else ''}", flush=True)

                if post_url:
                    post_message(full_text, post_url)

                # Reset accumulator
                pending_texts = []
                pending_has_tool = False
                last_assistant_time = 0.0

        time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Watch Claude Code session for new assistant messages.")
    parser.add_argument("--session", type=str, default=None, help="Path to .jsonl session file")
    parser.add_argument("--post", type=str, default=None, help="POST new messages to this URL")
    parser.add_argument("--interval", type=float, default=0.5, help="Poll interval in seconds (default 0.5)")
    parser.add_argument("--flush-timeout", type=float, default=FLUSH_TIMEOUT,
                        help=f"Seconds of silence before flushing turn (default {FLUSH_TIMEOUT})")
    args = parser.parse_args()

    global FLUSH_TIMEOUT
    FLUSH_TIMEOUT = args.flush_timeout

    if args.session:
        session_path = Path(args.session)
    else:
        session_path = find_latest_session()

    if not session_path or not session_path.exists():
        print(f"[watcher] Session file not found. Pass --session <path>")
        sys.exit(1)

    try:
        watch(session_path, post_url=args.post, poll_interval=args.interval)
    except KeyboardInterrupt:
        print("\n[watcher] Stopped.")


if __name__ == "__main__":
    main()
