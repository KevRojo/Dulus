"""Dulus self-update — keep every Dulus in the world on the latest release.

The organism heals fastest when every node runs the newest code. This module
checks PyPI for a newer `dulus` release and (optionally) upgrades in place.

Design goals:
  - Zero friction: on by default, checks quietly at startup.
  - Fast & non-blocking: PyPI JSON API with a short timeout + local cache so we
    never hammer the network or slow the boot.
  - Safe: never crashes the CLI if offline / PyPI is down / pip is weird.
  - Respectful: a single config flag (`auto_update`) turns it off; a cache TTL
    avoids checking on every single launch.

Public API:
    get_installed_version() -> str
    get_latest_version(timeout=4, use_cache=True) -> str | None
    is_update_available() -> tuple[bool, str, str]   # (available, current, latest)
    perform_update(target=None) -> tuple[bool, str]  # (ok, message)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PYPI_JSON_URL = "https://pypi.org/pypi/dulus/json"
_CACHE_FILE = Path.home() / ".dulus" / "cache" / "update-check.json"
_CACHE_TTL_SEC = 6 * 3600  # only hit PyPI at most every 6h for the auto-check


# ── Version helpers ─────────────────────────────────────────────────────────

def get_installed_version() -> str:
    """Return the installed dulus version, or '0.0.0' if undeterminable."""
    try:
        from importlib.metadata import version
        return version("dulus")
    except Exception:
        # Running from source without an install — try pyproject as a fallback.
        try:
            here = Path(__file__).parent / "pyproject.toml"
            for line in here.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return "0.0.0"


def _parse(v: str) -> tuple:
    """Turn '3.9.0' into a comparable tuple (3, 9, 0). Non-numeric parts -> 0."""
    out = []
    for part in str(v).split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out)


def _is_newer(latest: str, current: str) -> bool:
    return _parse(latest) > _parse(current)


# ── PyPI query (cached) ─────────────────────────────────────────────────────

def _read_cache() -> dict | None:
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        if time.time() - float(data.get("fetched_at", 0)) < _CACHE_TTL_SEC:
            return data
    except Exception:
        pass
    return None


def _write_cache(latest: str) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps({"fetched_at": time.time(), "latest": latest}),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_latest_version(timeout: int = 4, use_cache: bool = True) -> str | None:
    """Return the newest dulus version on PyPI, or None if unreachable."""
    if use_cache:
        cached = _read_cache()
        if cached and cached.get("latest"):
            return cached["latest"]

    # truststore first so we work behind corporate TLS-intercepting proxies
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass

    try:
        req = urllib.request.Request(
            PYPI_JSON_URL, headers={"User-Agent": "Dulus-Updater/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
        latest = payload.get("info", {}).get("version")
        if latest:
            _write_cache(latest)
            return latest
    except Exception:
        return None
    return None


def is_update_available() -> tuple[bool, str, str]:
    """Return (update_available, current_version, latest_version_or_empty)."""
    current = get_installed_version()
    latest = get_latest_version()
    if not latest:
        return (False, current, "")
    return (_is_newer(latest, current), current, latest)


# ── Perform the upgrade ─────────────────────────────────────────────────────

def perform_update(target: str | None = None) -> tuple[bool, str]:
    """pip-install --upgrade dulus (optionally pinning a specific version).

    Returns (ok, message). Never raises.
    """
    pkg = f"dulus=={target}" if target else "dulus"
    # --upgrade to move forward; PEP 668 environments need --break-system-packages
    # but only add it as a fallback so we don't clobber managed installs on the
    # first, cleaner attempt.
    base = [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", pkg]
    try:
        proc = subprocess.run(base, capture_output=True, text=True, timeout=300)
        if proc.returncode == 0:
            # bust the cache so the next check reflects reality
            try:
                _CACHE_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            return (True, f"Updated to the latest dulus ({target or 'latest'}).")
        # Retry once for externally-managed (PEP 668) Pythons.
        if "externally-managed" in (proc.stderr or "") or "break-system-packages" in (proc.stderr or ""):
            proc2 = subprocess.run(
                base + ["--break-system-packages"],
                capture_output=True, text=True, timeout=300,
            )
            if proc2.returncode == 0:
                try:
                    _CACHE_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
                return (True, "Updated (PEP 668 override).")
            return (False, f"pip failed: {(proc2.stderr or proc2.stdout or '').strip()[:300]}")
        return (False, f"pip failed: {(proc.stderr or proc.stdout or '').strip()[:300]}")
    except subprocess.TimeoutExpired:
        return (False, "Update timed out after 5 minutes.")
    except Exception as e:
        return (False, f"Update error: {e}")


def startup_check_line() -> str | None:
    """Cheap check used at REPL boot. Returns a one-line notice or None.

    Uses the cache aggressively so startup stays fast. Returns None when
    up-to-date, offline, or the check is skipped.
    """
    available, current, latest = is_update_available()
    if available:
        return f"A new Dulus is available: {current} -> {latest}.  Run /update now  (auto: /update on)"
    return None
