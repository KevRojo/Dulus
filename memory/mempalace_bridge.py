"""MemPalace bridge for Dulus memory.

Naming (do not mix these up):
  - mempalace  → the real package/CLI: ``python -m mempalace mine|init|status``
  - mem_palace → Dulus config toggle only (config["mem_palace"] = True/False)

This module owns the auto-mine path so MemorySave, consolidator, and /exit
all index user memory .md files the same way — including on Windows.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional


# Coalesce rapid successive mines (MemorySave spam, consolidate batch, etc.)
_MINE_LOCK = threading.Lock()
_LAST_MINE_TS = 0.0
_MIN_MINE_GAP_S = 2.0
_PENDING_WAITERS: list[subprocess.Popen] = []
_PENDING_LOCK = threading.Lock()


def _dulus_home() -> Path:
    """Mutable Dulus state root (``DULUS_HOME`` or ``~/.dulus``)."""
    return Path(os.environ.get("DULUS_HOME") or (Path.home() / ".dulus")).expanduser()


def user_memory_dir() -> Path:
    """Canonical user memory directory (respects DULUS_HOME)."""
    return _dulus_home() / "memory"


def mempalace_log_path() -> Path:
    log_dir = _dulus_home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "mempalace_mine.log"


def mempalace_env() -> dict:
    """UTF-8-safe env for Windows consoles + child processes."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    env.setdefault("DULUS_HOME", str(_dulus_home()))
    return env


def is_mempalace_initialized() -> bool:
    """True if mempalace has a global config (package already set up)."""
    try:
        return (Path.home() / ".mempalace" / "config.json").exists()
    except Exception:
        return False


def _popen_kwargs() -> dict:
    """Platform-safe Popen kwargs so the mine can outlive the parent.

    On Windows CREATE_NO_WINDOW alone keeps the child in the same console job,
    so os._exit / closing the terminal kills the mine silently. Detach it.
    """
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        # CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        flags = 0
        for name, bit in (
            ("CREATE_NO_WINDOW", 0x08000000),
            ("DETACHED_PROCESS", 0x00000008),
            ("CREATE_NEW_PROCESS_GROUP", 0x00000200),
        ):
            flags |= getattr(subprocess, name, bit)
        kwargs["creationflags"] = flags
        # Avoid inheriting handles that pin the parent console
        kwargs["close_fds"] = False
    else:
        # Start a new session so SIGHUP from parent exit doesn't kill the mine
        kwargs["start_new_session"] = True
    return kwargs


def _log(line: str) -> None:
    try:
        path = mempalace_log_path()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")
    except Exception:
        pass


def ensure_mempalace_initialized(mem_dir: Optional[Path] = None) -> bool:
    """Best-effort ``mempalace init`` if never set up. Returns True if ready."""
    if is_mempalace_initialized():
        return True
    mem_dir = Path(mem_dir) if mem_dir else user_memory_dir()
    mem_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_kw: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "env": mempalace_env(),
            "timeout": 120,
        }
        if sys.platform == "win32":
            run_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(
            [
                sys.executable, "-X", "utf8", "-m", "mempalace", "init",
                str(mem_dir), "--yes", "--no-llm",
            ],
            **run_kw,
        )
        _log(f"init exit={r.returncode} out={(r.stdout or '')[:400]}")
        return is_mempalace_initialized() or r.returncode == 0
    except Exception as e:
        _log(f"init failed: {e!r}")
        return False


def mempalace_available() -> bool:
    """True if the mempalace package can be imported / run as a module."""
    try:
        import importlib.util
        return importlib.util.find_spec("mempalace") is not None
    except Exception:
        return False


def schedule_mempalace_mine(
    config: Optional[dict] = None,
    *,
    mem_dir: Optional[Path] = None,
    wing: str = "memory",
    agent: str = "dulus",
    wait: bool = False,
    wait_timeout_s: float = 45.0,
    reason: str = "",
) -> bool:
    """Fire-and-forget (or optional wait) ``mempalace mine`` on the user memory dir.

    Returns True if a mine was launched (or coalesced into a recent launch).
    Never raises — memory saves must not break on mine failures.
    """
    cfg = config or {}
    # Dulus toggle only — package name is still mempalace
    if not cfg.get("mem_palace", True):
        _log(f"skip mine (mem_palace OFF) reason={reason!r}")
        return False

    if not mempalace_available():
        _log(f"skip mine (mempalace package missing) reason={reason!r}")
        return False

    mem_dir = Path(mem_dir) if mem_dir else user_memory_dir()
    try:
        mem_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _log(f"skip mine (cannot mkdir {mem_dir}): {e!r}")
        return False

    global _LAST_MINE_TS
    with _MINE_LOCK:
        now = time.time()
        if not wait and (now - _LAST_MINE_TS) < _MIN_MINE_GAP_S:
            _log(f"coalesce mine (gap) reason={reason!r} dir={mem_dir}")
            return True
        _LAST_MINE_TS = now

    ensure_mempalace_initialized(mem_dir)

    log_path = mempalace_log_path()
    cmd = [
        sys.executable, "-X", "utf8", "-m", "mempalace", "mine",
        str(mem_dir), "--wing", wing, "--agent", agent,
    ]
    try:
        # Append child stdout/stderr to our log so Windows silent deaths are visible
        log_fh = open(log_path, "a", encoding="utf-8")
        log_fh.write(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"launch mine reason={reason!r} wait={wait} cmd={' '.join(cmd)}\n"
        )
        log_fh.flush()
        popen_kw = _popen_kwargs()
        popen_kw["stdout"] = log_fh
        popen_kw["stderr"] = subprocess.STDOUT
        proc = subprocess.Popen(cmd, env=mempalace_env(), **popen_kw)
        with _PENDING_LOCK:
            _PENDING_WAITERS.append(proc)
        _log(f"mine pid={proc.pid} reason={reason!r}")

        if wait:
            try:
                rc = proc.wait(timeout=wait_timeout_s)
                _log(f"mine pid={proc.pid} finished rc={rc}")
            except subprocess.TimeoutExpired:
                _log(
                    f"mine pid={proc.pid} still running after "
                    f"{wait_timeout_s}s (leaving detached)"
                )
            finally:
                try:
                    log_fh.close()
                except Exception:
                    pass
                with _PENDING_LOCK:
                    if proc in _PENDING_WAITERS:
                        _PENDING_WAITERS.remove(proc)
        else:
            def _reap():
                try:
                    proc.wait(timeout=300)
                    _log(f"mine pid={proc.pid} reaped rc={proc.returncode}")
                except Exception as e:
                    _log(f"mine pid={proc.pid} reap: {e!r}")
                finally:
                    try:
                        log_fh.close()
                    except Exception:
                        pass
                    with _PENDING_LOCK:
                        if proc in _PENDING_WAITERS:
                            _PENDING_WAITERS.remove(proc)

            threading.Thread(
                target=_reap, name="mempalace-mine-reap", daemon=True
            ).start()
        return True
    except Exception as e:
        _log(f"mine launch failed reason={reason!r}: {e!r}")
        return False


def wait_pending_mines(timeout_s: float = 20.0) -> None:
    """Best-effort wait for in-flight mines before hard process exit."""
    deadline = time.time() + max(0.0, timeout_s)
    with _PENDING_LOCK:
        procs = list(_PENDING_WAITERS)
    for proc in procs:
        remaining = deadline - time.time()
        if remaining <= 0:
            _log(f"wait_pending timeout; leaving pid={getattr(proc, 'pid', '?')}")
            break
        try:
            rc = proc.wait(timeout=remaining)
            _log(f"wait_pending pid={proc.pid} rc={rc}")
        except Exception as e:
            _log(f"wait_pending pid={getattr(proc, 'pid', '?')}: {e!r}")


__all__ = [
    "ensure_mempalace_initialized",
    "is_mempalace_initialized",
    "mempalace_available",
    "mempalace_env",
    "mempalace_log_path",
    "schedule_mempalace_mine",
    "user_memory_dir",
    "wait_pending_mines",
]
