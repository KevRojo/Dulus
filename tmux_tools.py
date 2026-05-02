"""Tmux integration tools for Falcon.

Gives the AI model direct control over tmux sessions: create panes,
send commands, read output, and manage layouts.  Auto-detected at
startup — tools are only registered when tmux is available on the host.
"""
import os
import re
import sys
import subprocess
import shlex
import shutil
from tool_registry import ToolDef, register_tool

# ── Detection ────────────────────────────────────────────────────────────────

def _find_tmux() -> str | None:
    """Locate a tmux binary."""
    found = shutil.which("tmux")
    if found:
        return found
    if sys.platform == "win32":
        candidates = [
            os.path.expanduser(r"~\.cargo\bin\tmux.exe"),
        ]
        # Search common install locations
        for base in [os.path.expanduser("~\\Desktop"), os.path.expanduser("~")]:
            p = os.path.join(base, "tmux.exe")
            candidates.append(p)
        for c in candidates:
            if os.path.isfile(c):
                return c
    return None


_TMUX_BIN: str | None = _find_tmux()

# Sanitize pattern: only allow alphanumerics, underscores, hyphens, dots, colons
_SAFE_NAME = re.compile(r'^[a-zA-Z0-9_.:-]+$')

# Direction flag constants
_RESIZE_FLAGS = {"up": "-U", "down": "-D", "left": "-L", "right": "-R"}
_READ_ONLY_TOOLS = frozenset(("TmuxListSessions", "TmuxCapture", "TmuxListPanes", "TmuxListWindows"))


def tmux_available() -> bool:
    """Return True if a tmux-compatible binary exists on the system."""
    return _TMUX_BIN is not None


def _safe(value: str) -> str:
    """Sanitize a tmux target/session name to prevent shell injection."""
    if not value or not _SAFE_NAME.match(value):
        raise ValueError(f"Invalid tmux identifier: {value!r}")
    return value


def _t(params: dict, key: str = "target") -> str:
    """Build a -t flag from params, or empty string if absent."""
    val = params.get(key, "")
    return f" -t {_safe(val)}" if val else ""


def _run(cmd: str, timeout: int = 10) -> str:
    """Run a tmux command and return combined stdout+stderr.

    Replaces bare 'tmux' prefix with the detected binary path.
    Unsets nesting guards ($TMUX / $PSMUX_SESSION) so commands work
    from inside an existing session.
    """
    try:
        if cmd.startswith("tmux "):
            cmd = f'"{_TMUX_BIN}" {cmd[5:]}'
        
        # Save and temporarily remove nesting guards from os.environ
        # (Don't pass custom env to subprocess - tmux needs full parent env)
        saved_vars = {}
        for k in list(os.environ.keys()):
            if k == "TMUX" or "MUX_SESSION" in k or k.startswith("PSMUX"):
                saved_vars[k] = os.environ.pop(k)
        
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=timeout,
            )
        finally:
            # Restore removed vars
            for k, v in saved_vars.items():
                os.environ[k] = v
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        if r.returncode != 0 and stderr:
            err_msg = f"FAILED (exit {r.returncode}): {stderr}"
            return err_msg.replace("psmux", "tmux").replace("pmux", "tmux")
        out = (stdout + ("\n" + stderr if stderr else "")).strip()
        out = out.replace("psmux", "tmux").replace("pmux", "tmux")
        return out if out else "(ok)"
    except subprocess.TimeoutExpired:
        return "Error: tmux command timed out"
    except Exception as e:
        return f"Error: {e}"


# ── Tool implementations ────────────────────────────────────────────────────

def _tmux_list_sessions(params: dict, config: dict) -> str:
    return _run("tmux list-sessions")


def _tmux_new_session(params: dict, config: dict) -> str:
    # Fix for tmuxoffload: use "session" as default on Unix, "falcon" on Windows
    platform = sys.platform
    default_name = "falcon" if platform == "win32" else "session"
    name = _safe(params.get("session_name", default_name))
    detach = params.get("detached", True)
    cmd = params.get("command", "")
    
    if sys.platform == "win32":
        # Windows: usar lista de args sin shell=True
        import subprocess
        args = ["tmux", "new-session"]
        if detach:
            args.append("-d")
        args.extend(["-s", name])
        if cmd:
            args.append(cmd)
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
            if r.returncode != 0 and r.stderr:
                return f"FAILED (exit {r.returncode}): {r.stderr}"
            return r.stdout.strip() if r.stdout.strip() else "(ok)"
        except Exception as e:
            return f"Error: {e}"
    else:
        # Unix: seguir usando shell con shlex.quote
        detach_flag = "-d" if detach else ""
        shell_part = f" {shlex.quote(cmd)}" if cmd else ""
        return _run(f"tmux new-session {detach_flag} -s {name}{shell_part}")


def _tmux_split_window(params: dict, config: dict) -> str:
    direction = "-v" if params.get("direction", "vertical") == "vertical" else "-h"
    percent = params.get("percent")
    p_flag = f" -p {percent}" if percent else ""
    cmd = params.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return _run(f"tmux split-window {direction}{p_flag}{_t(params)}{shell_part}")


def _tmux_send_keys(params: dict, config: dict) -> str:
    keys = params["keys"]
    enter = " Enter" if params.get("press_enter", True) else ""
    
    # Get target - handle both "session:window.pane" and ":pane" formats
    target = params.get("target", ":0.0")
    
    if sys.platform == "win32":
        # Windows: tmux/psmux has issues with complex escaping
        # Solution: Write command to a temp batch file and execute that
        import subprocess
        import tempfile
        import os
        try:
            # Create a temp batch file with the command
            # This avoids all the quoting nightmares with cmd.exe
            fd, batch_path = tempfile.mkstemp(suffix='.bat', prefix='falcon_cmd_')
            try:
                # Write the command to the batch file
                os.write(fd, keys.encode('utf-8'))
                os.close(fd)
                
                # Send the batch file execution command to tmux
                # Use call to execute the batch file
                batch_cmd = f'call "{batch_path}"'
                safe_batch = batch_cmd.replace('\\', '\\\\')
                
                cmd_parts = ['tmux', 'send-keys', '-t', target, '-l', safe_batch]
                subprocess.run(cmd_parts, capture_output=True, text=True, check=True)
                
                # Send Enter
                subprocess.run(['tmux', 'send-keys', '-t', target, 'Enter'], 
                             capture_output=True, text=True, check=True)
                
                # Schedule cleanup of the batch file after a delay
                # (tmux needs time to execute it)
                cleanup_cmd = f'"{batch_path}"'
                subprocess.Popen(['tmux', 'send-keys', '-t', target, '-l', 
                                f' && del "{batch_path}"', 'Enter'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                return "ok"
            except Exception:
                # Cleanup on error
                try:
                    os.close(fd)
                except:
                    pass
                try:
                    os.unlink(batch_path)
                except:
                    pass
                raise
        except subprocess.CalledProcessError as e:
            return f"failed: {e.stderr if e.stderr else str(e)}"
        except Exception as e:
            return f"failed: {str(e)}"
    else:
        # Unix: For tmux targets, we can't use shlex.quote because it wraps
        # "session:window.pane" in quotes which tmux doesn't understand.
        # Targets with : or . should NOT be quoted as a whole.
        safe_keys = keys.replace("'", "'\\''")
        return _run(f"tmux send-keys -t {target} '{safe_keys}'{enter}")


def _tmux_capture_pane(params: dict, config: dict) -> str:
    lines = params.get("lines", 50)
    return _run(f"tmux capture-pane{_t(params)} -p -S -{int(lines)}")


def _tmux_list_panes(params: dict, config: dict) -> str:
    return _run(f"tmux list-panes{_t(params)} -F '#{{pane_index}}: #{{pane_current_command}} [#{{pane_width}}x#{{pane_height}}] #{{?pane_active,(active),}}'")


def _tmux_select_pane(params: dict, config: dict) -> str:
    return _run(f"tmux select-pane -t {_safe(params['target'])}")


def _tmux_kill_pane(params: dict, config: dict) -> str:
    return _run(f"tmux kill-pane{_t(params)}")


def _tmux_new_window(params: dict, config: dict) -> str:
    t_flag = _t(params, "target_session")
    name = params.get("window_name", "")
    n_flag = f" -n {_safe(name)}" if name else ""
    cmd = params.get("command", "")
    shell_part = f" {shlex.quote(cmd)}" if cmd else ""
    return _run(f"tmux new-window{t_flag}{n_flag}{shell_part}")


def _tmux_list_windows(params: dict, config: dict) -> str:
    return _run(f"tmux list-windows{_t(params, 'target_session')} -F '#{{window_index}}: #{{window_name}} [#{{window_width}}x#{{window_height}}] #{{?window_active,(active),}}'")


def _tmux_resize_pane(params: dict, config: dict) -> str:
    direction = params.get("direction", "down")
    amount = int(params.get("amount", 10))
    d_flag = _RESIZE_FLAGS.get(direction, "-D")
    return _run(f"tmux resize-pane{_t(params)} {d_flag} {amount}")


# ── Schemas ──────────────────────────────────────────────────────────────────

TMUX_TOOL_SCHEMAS = [
    {
        "name": "TmuxListSessions",
        "description": "List all active tmux sessions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "TmuxNewSession",
        "description": "Create a new tmux session. Use detached=true (default) to keep it in the background.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_name": {"type": "string", "description": "Session name (default: falcon)"},
                "detached":     {"type": "boolean", "description": "Start detached (default: true)"},
                "command":      {"type": "string", "description": "Optional command to run in the new session"},
            },
        },
    },
    {
        "name": "TmuxSplitWindow",
        "description": "Split the current tmux pane into two. Creates a new visible terminal pane. (Hint: to run a command and keep the pane open, omit 'command' here and use TmuxSendKeys afterwards).",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":    {"type": "string", "description": "Target pane (e.g. session:window.pane)"},
                "direction": {"type": "string", "enum": ["vertical", "horizontal"], "description": "Split direction (default: vertical)"},
                "percent":   {"type": "integer", "description": "Percentage of the original pane to take (e.g. 35)"},
                "command":   {"type": "string", "description": "Optional command to run in the new pane"},
            },
        },
    },
    {
        "name": "TmuxSendKeys",
        "description": "Send keystrokes/commands to a tmux pane. The command runs visibly in that pane.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keys":        {"type": "string", "description": "The text or command to send"},
                "target":      {"type": "string", "description": "Target pane (e.g. session:window.pane)"},
                "press_enter": {"type": "boolean", "description": "Press Enter after sending keys (default: true)"},
            },
            "required": ["keys"],
        },
    },
    {
        "name": "TmuxCapture",
        "description": "Capture and return the visible text content of a tmux pane. Use this to read command output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane (e.g. session:window.pane)"},
                "lines":  {"type": "integer", "description": "Number of history lines to capture (default: 50)"},
            },
        },
    },
    {
        "name": "TmuxListPanes",
        "description": "List all panes in the current session/window with their index, command, and size.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target session or window"},
            },
        },
    },
    {
        "name": "TmuxSelectPane",
        "description": "Switch focus to a specific tmux pane.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane (e.g. 0, 1, or session:window.pane)"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "TmuxKillPane",
        "description": "Close/kill a tmux pane.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target pane to kill"},
            },
        },
    },
    {
        "name": "TmuxNewWindow",
        "description": "Create a new tmux window (tab) in a session. (Hint: to run a command and keep the window open, omit 'command' here and use TmuxSendKeys afterwards).",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_session": {"type": "string", "description": "Session to add the window to"},
                "window_name":    {"type": "string", "description": "Name for the new window"},
                "command":        {"type": "string", "description": "Optional command to run"},
            },
        },
    },
    {
        "name": "TmuxListWindows",
        "description": "List all windows in a tmux session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_session": {"type": "string", "description": "Session name"},
            },
        },
    },
    {
        "name": "TmuxResizePane",
        "description": "Resize a tmux pane in a given direction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target":    {"type": "string", "description": "Target pane"},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Resize direction"},
                "amount":    {"type": "integer", "description": "Number of cells to resize (default: 10)"},
            },
        },
    },
]

# ── Registration ─────────────────────────────────────────────────────────────

_TOOL_FUNCS = {
    "TmuxListSessions": _tmux_list_sessions,
    "TmuxNewSession":   _tmux_new_session,
    "TmuxSplitWindow":  _tmux_split_window,
    "TmuxSendKeys":     _tmux_send_keys,
    "TmuxCapture":      _tmux_capture_pane,
    "TmuxListPanes":    _tmux_list_panes,
    "TmuxSelectPane":   _tmux_select_pane,
    "TmuxKillPane":     _tmux_kill_pane,
    "TmuxNewWindow":    _tmux_new_window,
    "TmuxListWindows":  _tmux_list_windows,
    "TmuxResizePane":   _tmux_resize_pane,
}


def register_tmux_tools() -> int:
    """Register all tmux tools. Returns number of tools registered."""
    if not tmux_available():
        return 0

    schema_map = {s["name"]: s for s in TMUX_TOOL_SCHEMAS}
    count = 0
    for name, func in _TOOL_FUNCS.items():
        register_tool(ToolDef(
            name=name,
            schema=schema_map[name],
            func=func,
            read_only=name in _READ_ONLY_TOOLS,
            concurrent_safe=True,
        ))
        count += 1
    return count
