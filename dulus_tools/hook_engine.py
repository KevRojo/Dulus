"""HookEngine - Configurable hook engine with event matching and shell execution."""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HookDef:
    """Hook definition that matches events and executes commands.

    Attributes:
        event: Event type to match (e.g., "tool_call", "approval_request").
        matcher: Regex pattern for matching against the target.
        command: Shell command to execute (supports {target} and {event} placeholders).
        timeout: Timeout in seconds for command execution.
    """

    event: str
    matcher: str = ""
    command: str = ""
    timeout: int = 30

    @property
    def compiled_matcher(self) -> re.Pattern[str] | None:
        """Return the compiled regex pattern, or None if empty."""
        if not self.matcher:
            return None
        try:
            return re.compile(self.matcher)
        except re.error:
            return None


@dataclass
class HookResult:
    """Result of executing a hook.

    Attributes:
        hook: The hook definition that was executed.
        matched: Whether the hook matched the event/target.
        returncode: Exit code of the command (None if not executed).
        stdout: Standard output from the command.
        stderr: Standard error from the command.
        elapsed: Time elapsed during execution in seconds.
        timed_out: Whether the execution timed out.
    """

    hook: HookDef
    matched: bool = False
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed: float = 0.0
    timed_out: bool = False


class HookEngine:
    """Hook engine that loads and executes matching hooks.

    Supports:
    - Loading hooks from TOML config file (~/.dulus/hooks.toml)
    - Event matching with regex patterns
    - Shell command execution with timeout
    - Template substitution ({target}, {event})
    """

    def __init__(self, hooks: list[HookDef] | None = None, cwd: str | None = None) -> None:
        """Initialize the hook engine.

        Args:
            hooks: Optional list of hook definitions.
            cwd: Working directory for command execution.
        """
        self._hooks: list[HookDef] = hooks or []
        self._cwd: str = cwd or os.getcwd()

    # ── Hook management ──────────────────────────────────────────────────────

    def add_hook(self, hook: HookDef) -> None:
        """Add a hook definition."""
        self._hooks.append(hook)

    def remove_hook(self, event: str) -> int:
        """Remove all hooks matching an event type.

        Args:
            event: The event type to remove hooks for.

        Returns:
            Number of hooks removed.
        """
        original_len = len(self._hooks)
        self._hooks = [h for h in self._hooks if h.event != event]
        return original_len - len(self._hooks)

    def list_hooks(self) -> list[HookDef]:
        """Return all registered hook definitions."""
        return list(self._hooks)

    # ── Trigger / Execution ──────────────────────────────────────────────────

    async def trigger(self, event: str, target: str, **context: Any) -> list[dict[str, Any]]:
        """Trigger hooks matching the event and target.

        Args:
            event: The event type that occurred.
            target: The target string to match against (e.g., tool name).
            **context: Additional context variables for template substitution.

        Returns:
            List of result dicts for each matching hook.
        """
        results: list[dict[str, Any]] = []

        for hook in self._hooks:
            if hook.event != event:
                continue

            # Check matcher
            if hook.compiled_matcher is not None:
                if not hook.compiled_matcher.search(target):
                    continue
            elif hook.matcher:
                # Literal match if regex compilation failed
                if hook.matcher not in target:
                    continue

            # Execute the hook command
            result = await self._execute_hook(hook, event, target, **context)
            results.append({
                "event": event,
                "target": target,
                "matched": result.matched,
                "command": hook.command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "elapsed": result.elapsed,
                "timed_out": result.timed_out,
            })

        return results

    async def _execute_hook(
        self,
        hook: HookDef,
        event: str,
        target: str,
        **context: Any,
    ) -> HookResult:
        """Execute a single hook's command."""
        result = HookResult(hook=hook, matched=True)

        if not hook.command:
            return result

        # Substitute template variables
        command = hook.command
        command = command.replace("{target}", target)
        command = command.replace("{event}", event)
        for key, value in context.items():
            command = command.replace(f"{{{key}}}", str(value))

        start = time.time()
        try:
            if os.name == "nt":
                # On Windows use subprocess.run via executor (asyncio subprocess
                # can hang on some Windows environments)
                import subprocess as _sp
                import concurrent.futures as _cf
                loop = asyncio.get_event_loop()
                with _cf.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        _sp.run,
                        command,
                        shell=True,
                        capture_output=True,
                        cwd=self._cwd,
                        timeout=hook.timeout,
                    )
                    try:
                        proc_result = await asyncio.wait_for(
                            loop.run_in_executor(None, future.result),
                            timeout=hook.timeout,
                        )
                        result.stdout = proc_result.stdout.decode("utf-8", errors="replace") if proc_result.stdout else ""
                        result.stderr = proc_result.stderr.decode("utf-8", errors="replace") if proc_result.stderr else ""
                        result.returncode = proc_result.returncode
                    except asyncio.TimeoutError:
                        result.timed_out = True
                        result.returncode = -1
                        future.cancel()
            else:
                shell = shutil.which("bash") or shutil.which("sh") or "/bin/sh"
                proc = await asyncio.create_subprocess_exec(
                    shell,
                    "-c",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self._cwd,
                )
                try:
                    stdout_data, stderr_data = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=hook.timeout,
                    )
                    result.stdout = stdout_data.decode("utf-8", errors="replace")
                    result.stderr = stderr_data.decode("utf-8", errors="replace")
                    result.returncode = proc.returncode or 0
                except asyncio.TimeoutError:
                    result.timed_out = True
                    result.returncode = -1
                    try:
                        proc.kill()
                        await proc.wait()
                    except Exception:
                        pass
        except Exception as e:
            result.returncode = -1
            result.stderr = str(e)

        result.elapsed = time.time() - start
        return result

    # ── Config loading ───────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: str | Path | None = None) -> HookEngine:
        """Load hooks from a TOML config file.

        Args:
            config_path: Path to the hooks.toml file.
                        Defaults to ~/.dulus/hooks.toml

        Returns:
            A HookEngine with loaded hooks.
        """
        if config_path is None:
            config_path = Path.home() / ".dulus" / "hooks.toml"
        else:
            config_path = Path(config_path)

        hooks: list[HookDef] = []

        if not config_path.exists():
            return cls(hooks=hooks)

        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                # Fallback: simple TOML parser for [[hooks]] tables
                hooks = cls._parse_hooks_toml_simple(config_path.read_text(encoding="utf-8"))
                return cls(hooks=hooks)

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return cls(hooks=hooks)

        for hook_data in data.get("hooks", []):
            try:
                hooks.append(HookDef(
                    event=hook_data.get("event", ""),
                    matcher=hook_data.get("matcher", ""),
                    command=hook_data.get("command", ""),
                    timeout=hook_data.get("timeout", 30),
                ))
            except Exception:
                continue

        return cls(hooks=hooks)

    @classmethod
    def _parse_hooks_toml_simple(cls, text: str) -> list[HookDef]:
        """Simple TOML parser for [[hooks]] tables (fallback).

        Handles basic TOML syntax for hooks definitions without
        requiring external dependencies.
        """
        hooks: list[HookDef] = []
        current: dict[str, Any] = {}
        in_hooks_table = False

        for line in text.splitlines():
            stripped = line.strip()

            if stripped == "[[hooks]]":
                if current:
                    hooks.append(cls._make_hook_from_dict(current))
                current = {}
                in_hooks_table = True
                continue

            if stripped.startswith("[") and stripped != "[[hooks]]":
                if current and in_hooks_table:
                    hooks.append(cls._make_hook_from_dict(current))
                    current = {}
                in_hooks_table = False
                continue

            if in_hooks_table and "=" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip matching outer quotes only
                if len(value) >= 2:
                    if value[0] == '"' and value[-1] == '"':
                        value = value[1:-1]
                    elif value[0] == "'" and value[-1] == "'":
                        value = value[1:-1]
                # Handle integers
                if key == "timeout" and value.isdigit():
                    value = int(value)
                current[key] = value

        if current and in_hooks_table:
            hooks.append(cls._make_hook_from_dict(current))

        return hooks

    @classmethod
    def _make_hook_from_dict(cls, data: dict[str, Any]) -> HookDef:
        """Create a HookDef from a parsed dict, with safe defaults."""
        return HookDef(
            event=data.get("event", ""),
            matcher=data.get("matcher", ""),
            command=data.get("command", ""),
            timeout=data.get("timeout", 30),
        )

    def ensure_default_config(self) -> None:
        """Create a default hooks.toml config if it doesn't exist."""
        config_dir = Path.home() / ".dulus"
        config_path = config_dir / "hooks.toml"

        if config_path.exists():
            return

        config_dir.mkdir(parents=True, exist_ok=True)
        default_content = '''# Dulus Hook Configuration
# Hooks are triggered when events match the specified pattern.
#
# Available events:
#   - tool_call      : Triggered when a tool is called
#   - approval_request : Triggered when approval is requested
#   - turn_begin     : Triggered at the start of a turn
#   - turn_end       : Triggered at the end of a turn
#
# Template variables:
#   {target}  - The target of the event (e.g., tool name)
#   {event}   - The event type

# Example: Log file modifications
# [[hooks]]
# event = "tool_call"
# matcher = "Write|Edit"
# command = "echo \"File modified: {target}\" >> ~/.dulus/audit.log"
# timeout = 10

# Example: Desktop notification for approvals
# [[hooks]]
# event = "approval_request"
# matcher = ""
# command = "notify-send \"Dulus Approval\" \"Action requires approval\""
# timeout = 5
'''
        config_path.write_text(default_content, encoding="utf-8")
