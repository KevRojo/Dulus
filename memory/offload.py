"""Tmux Offload tool implementation for backgrounding heavy tasks."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from tool_registry import ToolDef, register_tool
from tmux_tools import _tmux_new_session, _tmux_send_keys, tmux_available, _run

JOBS_DIR = Path.home() / ".dulus" / "jobs"


def _force_remain_off(session_name: str) -> None:
    """Neutralise global `remain-on-exit on` so finished panes can die."""
    try:
        _run(f"tmux set-option -t {session_name} remain-on-exit off", timeout=2)
    except Exception:
        pass
    try:
        _run(f"tmux set-option -t {session_name}:0 remain-on-exit off", timeout=2)
    except Exception:
        pass


def _write_windows_wrapper(
    *,
    job_id: str,
    session_name: str,
    tool_name: str,
    dulus_script: Path,
    job_path: Path,
) -> Path:
    """Write a .cmd that runs the tool then ALWAYS kills the tmux session.

    Why .cmd (not a PowerShell one-liner):
      Windows tmux panes default to PowerShell. PS 5.1 does NOT understand
      bash/cmd `&&` / `||`, so the trailing `tmux kill-session` in the old
      send-keys one-liner never ran — sessions leaked with an idle PS prompt
      after the job archived.

    The session is created WITH this .cmd as its main process via
    `tmux new-session -d -s NAME cmd.exe /c WRAPPER`, so:
      1. no send-keys quoting fights with PowerShell
      2. kill-session runs unconditionally after the tool
      3. when cmd.exe exits the pane dies (remain-on-exit is forced off)
    """
    wrapper = JOBS_DIR / f"{job_id}_run.cmd"
    py = sys.executable or "python"
    # cmd.exe paths: keep native backslashes, quote everything with spaces.
    body = (
        "@echo off\r\n"
        "setlocal\r\n"
        f"REM Dulus TmuxOffload wrapper - job {job_id} / session {session_name}\r\n"
        f'"{py}" "{dulus_script}" --run-tool {tool_name} '
        f'--job-id {job_id} --job-path "{job_path}"\r\n'
        "set ERR=%ERRORLEVEL%\r\n"
        f"tmux kill-session -t {session_name} >nul 2>&1\r\n"
        "exit /b %ERR%\r\n"
    )
    wrapper.write_text(body, encoding="ascii", newline="")
    return wrapper


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
        return (
            "Error: tool_params/tool_input must be an object, "
            f"got {type(tool_params).__name__}"
        )

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

    session_name = f"dulus_offload_{job_id}"
    dulus_script = Path(__file__).resolve().parent.parent / "dulus.py"
    job_log = JOBS_DIR / f"{job_id}.log"
    last_log = JOBS_DIR / "last_background_output.txt"

    if sys.platform == "win32":
        # ── Windows path ──────────────────────────────────────────────────
        # Create the session WITH cmd.exe /c wrapper.cmd as its main process.
        # Avoids PowerShell send-keys quoting hell and guarantees cleanup:
        # wrapper always runs `tmux kill-session`, then cmd exits → pane dies.
        wrapper = _write_windows_wrapper(
            job_id=job_id,
            session_name=session_name,
            tool_name=tool_name,
            dulus_script=dulus_script,
            job_path=job_path,
        )
        # Pass the command as a single argv element to tmux new-session.
        # tmux_tools._tmux_new_session on win32 uses subprocess arg list
        # (no shell), so this string is the session's shell-command argv.
        session_cmd = f'cmd.exe /c "{wrapper}"'
        result = _tmux_new_session(
            {
                "session_name": session_name,
                "detached": True,
                "command": session_cmd,
            },
            config,
        )
        if "failed" in result.lower() or "error" in result.lower():
            job_data["status"] = "failed"
            job_data["error"] = f"Failed to create tmux session: {result}"
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)
            return (
                "❌ Failed to offload: could not create tmux session. "
                f"Error: {result}"
            )

        # Belt: disable remain-on-exit so a finished pane cannot linger.
        _force_remain_off(session_name)

    else:
        # ── Unix/Linux path ───────────────────────────────────────────────
        result = _tmux_new_session(
            {"session_name": session_name, "detached": True}, config
        )
        if "failed" in result.lower() or "error" in result.lower():
            job_data["status"] = "failed"
            job_data["error"] = f"Failed to create tmux session: {result}"
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)
            return (
                "❌ Failed to offload: could not create tmux session. "
                f"Error: {result}"
            )

        _force_remain_off(session_name)

        python_exe = sys.executable.replace("\\", "/")
        cmd = (
            f"unset PSMUX PSMUX_SESSION PSMUX_SOCKET 2>/dev/null; "
            f"\"{python_exe}\" -u \"{dulus_script}\" --run-tool {tool_name} "
            f"--job-id {job_id} --job-path \"{job_path}\" 2>&1 "
            f"| tee \"{job_log}\" \"{last_log}\"; "
            f"tmux kill-session -t {session_name}"
        )
        send_result = _tmux_send_keys(
            {"keys": cmd, "target": f"{session_name}:0"}, config
        )
        if "failed" in send_result.lower() or "error" in send_result.lower():
            _run(f"tmux kill-session -t {session_name}", timeout=2)
            job_data["status"] = "failed"
            job_data["error"] = f"Failed to send command to tmux: {send_result}"
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)
            return (
                "❌ Failed to offload: could not send command to session. "
                f"Error: {send_result}"
            )

    # Give tmux a moment to start executing
    time.sleep(0.5)

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
                "Offload a long-running tool (e.g. SherlockSearch) to a "
                "detached Tmux session. The tool runs invisibly in the "
                "background while you continue chatting. The session "
                "auto-cleans up when finished. You will be notified via "
                "(System Automated Event) when done."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": (
                            "Name of the tool to offload "
                            "(e.g. 'sherlock_search')"
                        ),
                    },
                    "tool_params": {
                        "type": "object",
                        "description": (
                            "Parameters for the target tool. Alias "
                            "`tool_input` is also accepted."
                        ),
                    },
                    "tool_input": {
                        "type": "object",
                        "description": (
                            "Alias of tool_params for callers using Claude "
                            "Code's tool-use convention."
                        ),
                    },
                },
                "required": ["tool_name"],
            },
        },
        func=_tmux_offload,
        read_only=False,
        concurrent_safe=True,
    ))
