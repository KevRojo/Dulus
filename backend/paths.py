"""Filesystem locations that survive a read-only install.

site-packages is very often not writable: a container running as a non-root
user (the correct way to run one), a system-wide install, a locked-down
Windows profile. Creating a data directory there at *import* time raises
PermissionError while the package is still loading, which takes Dulus down
before it can print anything useful.

So every location resolves to the first candidate that actually accepts a
mkdir — the bundled directory first, so installs that ship data keep finding
it, then the user's own Dulus dir, then temp — and never raises.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def user_dulus_dir() -> Path:
    """The user's Dulus directory, honouring $DULUS_CONFIG_DIR."""
    base = os.environ.get("DULUS_CONFIG_DIR", "").strip()
    if base:
        return Path(base)
    try:
        return Path.home() / ".dulus"
    except Exception:
        return Path(tempfile.gettempdir()) / "dulus"


def resolve_writable_dir(bundled: Path, name: str) -> Path:
    """Return the first of bundled / user / temp that accepts a mkdir."""
    candidates = (
        bundled,
        user_dulus_dir() / name,
        Path(tempfile.gettempdir()) / f"dulus-{name}",
    )
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    # Nothing writable. Hand back the bundled path: readers already tolerate a
    # missing directory, and this keeps the import alive.
    return bundled
