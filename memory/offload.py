"""Tmux Offload tool implementation for backgrounding heavy tasks."""
from __future__ import annotations

import json
import uuid
import os
from pathlib import Path
from datetime import datetime

from tool_registry import ToolDef, register_tool
from tmux_tools import _tmux_new_session, _tmux_send_keys, _tmux_kill_pane, tmux_available, _run

JOBS_DIR = Path.home() / ".dulus" / "jobs"

def _tmux_offload(params: dict, config: dict) -> str:
    """Implement the TmuxOffload tool."""
    if not tmux_available():
        return "Error: Tmux is not available on this system. Cannot offload."
    
    # Note: We don't care if already inside tmux - just create the session

    tool_name = params["tool_name"]
    # Accept either `tool_params` (canonical) or `tool_input` (Claude Code
    # convention). Models trained on Anthropic tool-use schemas reach for
    # `tool_input` by reflex; silently dropping it stranded jobs with empty
    # params and no error.
    tool_params = params.get("tool_params")
    if tool_params is None:
        tool_params = params.get("tool_input", {})
    if not isinstance(tool_params, dict):
        return f"Error: tool_params/tool_input must be an object, got {type(tool_params).__name__}"
    
    # Create Job ID and directory
    job_id = uuid.uuid4().hex[:8]
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_path = JOBS_DIR / f"{job_id}.json"
    
    # Save initial job state.
    # IMPORTANT: never persist the parent config here — the child process
    # calls load_config() itself, and dumping the in-memory config leaks
    # API keys, session tokens, telegram bots, etc. to ~/.dulus/jobs/*.json.
    job_data = {
        "id": job_id,
        "tool_name": tool_name,
        "params": tool_params,
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "owner_pid": os.getpid(),
    }
    
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=2, ensure_ascii=False)

    # 1. Create detached session (invisible background session)
    session_name = f"dulus_offload_{job_id}"
    
    # Note: tmux server starts automatically when creating first session
    # No need for explicit server startup on Linux
    
    # Create the tmux session
    result = _tmux_new_session({"session_name": session_name, "detached": True}, config)
    if "failed" in result.lower() or "error" in result.lower():
        # Update job to failed status
        job_data["status"] = "failed"
        job_data["error"] = f"Failed to create tmux session: {result}"
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job_data, f, indent=2, ensure_ascii=False)
        return f"❌ Failed to offload: could not create tmux session. Error: {result}"
    
    # 2. Launch worker via global dulus.py path
    dulus_script = Path(__file__).resolve().parent.parent / "dulus.py"
    job_log = JOBS_DIR / f"{job_id}.log"
    last_log = JOBS_DIR / "last_background_output.txt"
    # Use forward slashes for Windows path to avoid Git Bash conversion issues
    job_path_str = str(job_path).replace("\\", "/")
    
    # Build command with proper error handling and cleanup
    # Use '&&' to ensure kill-session only runs if command succeeds
    # Also capture errors to the job file
    import sys
    if sys.platform == "win32":
        # Windows: Use absolute path to dulus.py since tmux starts in home dir, not DULUS dir
        dulus_path_str = str(dulus_script).replace("\\", "/")
        cmd = f'python "{dulus_path_str}" --run-tool {tool_name} --job-id {job_id} --job-path "{job_path_str}" 2>&1 && echo SUCCESS || echo FAILED; tmux kill-session -t {session_name}'
    else:
        # Unix/Linux: unset PSMUX vars and use tee
        # Use sys.executable to get correct python (python3 on most Linux distros)
        python_exe = sys.executable.replace("\\", "/")
        cmd = f"unset PSMUX PSMUX_SESSION PSMUX_SOCKET 2>/dev/null; \"{python_exe}\" -u \"{dulus_script}\" --run-tool {tool_name} --job-id {job_id} --job-path \"{job_path}\" 2>&1 | tee \"{job_log}\" \"{last_log}\"; tmux kill-session -t {session_name}"
    
    send_result = _tmux_send_keys({"keys": cmd, "target": f"{session_name}:0"}, config)
    # Belt-and-suspenders: a second explicit Enter. On Windows tmux + cmd.exe the
    # implicit `Enter` arg in the first send-keys sometimes gets swallowed by the
    # cmd.exe outer parser when the keys string contains `&&` / `||` / `;`, so the
    # command sits typed but unexecuted. The second send-keys is just an Enter — no
    # special chars to fight with — and reliably submits the line.
    if sys.platform == "win32":
        _tmux_send_keys({"keys": "", "target": f"{session_name}:0", "press_enter": True}, config)
    if "failed" in send_result.lower() or "error" in send_result.lower():
        # Clean up the session since we can't send keys
        _run(f"tmux kill-session -t {session_name}", timeout=2)
        job_data["status"] = "failed"
        job_data["error"] = f"Failed to send command to tmux: {send_result}"
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job_data, f, indent=2, ensure_ascii=False)
        return f"❌ Failed to offload: could not send command to session. Error: {send_result}"
    
    # Give tmux a moment to start executing
    import time
    time.sleep(0.5)
    
    # Check if the job file was updated (meaning the process started)
    try:
        with open(job_path, "r", encoding="utf-8") as f:
            current_data = json.load(f)
        # If status changed from 'running' to something else, or we see log activity
        log_file = JOBS_DIR / f"{job_id}.log"
        if log_file.exists() and log_file.stat().st_size > 0:
            pass  # Process started writing to log
    except Exception:
        pass  # Ignore check errors, not critical
    
    # Build return message with job info (same regardless of tmux context)
    return (
        f"[OK] Tool '{tool_name}' offloaded to Tmux session\n"
        f"Job ID: {job_id}\n"
        f"Session: {session_name}\n"
        f"Session will auto-cleanup when done\n"
        f"You will be notified via (System Automated Event) when finished"
    )

# ── Registration ─────────────────────────────────────────────────────────────

def register_offload_tool():
    register_tool(ToolDef(
        name="TmuxOffload",
        schema={
            "name": "TmuxOffload",
            "description": (
                "Offload a long-running tool (e.g. SherlockSearch) to a detached Tmux session. "
                "The tool runs invisibly in the background while you continue chatting. "
                "The session auto-cleans up when finished. You will be notified via (System Automated Event) when done."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string", 
                        "description": "Name of the tool to offload (e.g. 'sherlock_search')"
                    },
                    "tool_params": {
                        "type": "object",
                        "description": "Parameters for the target tool. Alias `tool_input` is also accepted."
                    },
                    "tool_input": {
                        "type": "object",
                        "description": "Alias of tool_params for callers using Claude Code's tool-use convention."
                    },
                },
                "required": ["tool_name"],
            },
        },
        func=_tmux_offload,
        read_only=False,
        concurrent_safe=True,
    ))
