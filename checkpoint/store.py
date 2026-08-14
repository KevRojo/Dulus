"""Checkpoint store: file-level backup + snapshot persistence.

Directory layout:
    ~/.dulus/checkpoints/<session_id>/
        snapshots.json       # list of Snapshot metadata
        backups/
            <hash>@v<N>      # actual file copies
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .types import FileBackup, Snapshot, MAX_SNAPSHOTS

# Max file size to back up (1 MB)
_MAX_FILE_SIZE = 1 * 1024 * 1024

# Hard ceiling for the whole checkpoint store. Age-based cleanup alone cannot
# bound this: MAX_SNAPSHOTS caps snapshots *per session*, but nothing capped
# the number of sessions, so a busy machine could accumulate gigabytes long
# before the 30-day cutoff ever applied. Sentry caught exactly that in the
# wild -- ENOSPC from mkdir under ~/.dulus/checkpoints on a user's server.
_MAX_STORE_BYTES = 512 * 1024 * 1024

# Free space below which we stop writing new backups entirely. Checkpoints are
# a convenience feature; they must never be the reason a user's disk fills up
# or their session dies.
_MIN_FREE_BYTES = 256 * 1024 * 1024

# Per-file version counters (reset per session)
_file_versions: dict[str, int] = {}


def _checkpoints_root() -> Path:
    return Path.home() / ".dulus" / "checkpoints"


def _session_dir(session_id: str) -> Path:
    return _checkpoints_root() / session_id


def _safe_mkdir(path: Path) -> bool:
    """mkdir -p that never raises.

    A full disk raised OSError(ENOSPC) straight out of pathlib.mkdir and took
    the whole session down with it. Checkpointing is optional; failing to
    create its directory must degrade silently, not crash the caller.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def _backups_dir(session_id: str) -> Path:
    d = _session_dir(session_id) / "backups"
    _safe_mkdir(d)
    return d


def _snapshots_file(session_id: str) -> Path:
    d = _session_dir(session_id)
    _safe_mkdir(d)
    return d / "snapshots.json"


def _path_hash(file_path: str) -> str:
    """Deterministic short hash from file path (not content)."""
    return hashlib.sha256(file_path.encode()).hexdigest()[:16]


def _dir_size(path: Path) -> int:
    """Total bytes under path. Best-effort: unreadable entries are skipped."""
    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return total


def _free_bytes(path: Path) -> int | None:
    """Free space on the filesystem holding path, or None if undeterminable."""
    try:
        return shutil.disk_usage(str(path)).free
    except OSError:
        return None


def _has_room_for_backups() -> bool:
    """Whether it is safe to write another backup.

    Returns False when the store has grown past its ceiling or the disk is
    nearly full. Callers must degrade gracefully: losing a checkpoint is
    acceptable, killing the user's session with ENOSPC is not.
    """
    root = _checkpoints_root()
    free = _free_bytes(root if root.exists() else root.parent)
    if free is not None and free < _MIN_FREE_BYTES:
        return False
    return _dir_size(root) < _MAX_STORE_BYTES


def enforce_store_budget() -> int:
    """Evict oldest sessions until the store fits in _MAX_STORE_BYTES.

    Age-based cleanup runs on a 30-day cutoff, which is far too slow for a
    machine that opens many sessions a day. This is the size-based backstop.
    Returns the number of sessions removed.
    """
    root = _checkpoints_root()
    if not root.exists():
        return 0

    size = _dir_size(root)
    free = _free_bytes(root)
    over_budget = size > _MAX_STORE_BYTES
    low_disk = free is not None and free < _MIN_FREE_BYTES
    if not (over_budget or low_disk):
        return 0

    try:
        sessions = [d for d in root.iterdir() if d.is_dir()]
    except OSError:
        return 0

    # Oldest first, so recent (likely resumable) sessions survive.
    def _mtime(d: Path) -> float:
        try:
            return d.stat().st_mtime
        except OSError:
            return 0.0

    sessions.sort(key=_mtime)

    # When the disk itself is tight, free space aggressively rather than
    # stopping at the store ceiling.
    target = _MAX_STORE_BYTES // 2 if low_disk else _MAX_STORE_BYTES

    removed = 0
    for d in sessions:
        if size <= target:
            break
        freed = _dir_size(d)
        shutil.rmtree(str(d), ignore_errors=True)
        size -= freed
        removed += 1
    return removed


def _next_version(file_path: str) -> int:
    v = _file_versions.get(file_path, 0) + 1
    _file_versions[file_path] = v
    return v


# ── Load / save snapshots JSON ──────────────────────────────────────────────

def _load_snapshots(session_id: str) -> list[Snapshot]:
    f = _snapshots_file(session_id)
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return [Snapshot.from_dict(s) for s in data]
    except Exception:
        return []


def _save_snapshots(session_id: str, snapshots: list[Snapshot]) -> None:
    f = _snapshots_file(session_id)
    if not _safe_mkdir(f.parent):
        return
    data = [s.to_dict() for s in snapshots]
    try:
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        # ENOSPC and friends: drop the checkpoint rather than the session.
        print(f"[checkpoint] could not persist snapshots: {e}")


# ── Public API ───────────────────────────────────────────────────────────────

def track_file_edit(session_id: str, file_path: str) -> str | None:
    """Back up a file before it is edited (first-write-wins per snapshot interval).

    Returns the backup filename, or None if the file doesn't exist yet.
    """
    p = Path(file_path)
    bdir = _backups_dir(session_id)

    if not p.exists():
        # File doesn't exist — record that so restore can delete it
        return None

    # Size guard
    try:
        size = p.stat().st_size
    except OSError:
        return None
    if size > _MAX_FILE_SIZE:
        print(f"[checkpoint] skipping large file ({size} bytes): {file_path}")
        return None

    # Disk guard: never let a convenience feature fill the user's disk.
    if not _has_room_for_backups():
        enforce_store_budget()
        if not _has_room_for_backups():
            return None

    # Copy file to backups/
    version = _next_version(file_path)
    backup_name = f"{_path_hash(file_path)}@v{version}"
    backup_path = bdir / backup_name
    try:
        shutil.copy2(str(p), str(backup_path))
    except Exception as e:
        print(f"[checkpoint] backup failed for {file_path}: {e}")
        return None

    return backup_name


def make_snapshot(
    session_id: str,
    state: Any,
    config: dict,
    user_prompt: str,
    tracked_edits: dict[str, str | None] | None = None,
) -> Snapshot | None:
    """Create a snapshot after a user prompt has been processed.

    tracked_edits: dict mapping file_path → backup_filename (or None if new file).
                   Populated by hooks.py during the turn.
    """
    snapshots = _load_snapshots(session_id)

    # Build file_backups: merge previous snapshot's backups with new edits
    prev_backups: dict[str, FileBackup] = {}
    if snapshots:
        prev_backups = dict(snapshots[-1].file_backups)

    now = datetime.now().isoformat()
    new_backups: dict[str, FileBackup] = {}

    # Carry forward unchanged files from previous snapshot
    for path, fb in prev_backups.items():
        new_backups[path] = fb

    # Add/update files that were edited this turn — back up their CURRENT state
    if tracked_edits:
        for path in tracked_edits:
            p = Path(path)
            if p.exists():
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                if size > _MAX_FILE_SIZE:
                    continue
                version = _next_version(path)
                backup_name = f"{_path_hash(path)}@v{version}"
                bdir = _backups_dir(session_id)
                try:
                    shutil.copy2(str(p), str(bdir / backup_name))
                except Exception:
                    continue
                new_backups[path] = FileBackup(
                    backup_filename=backup_name,
                    version=version,
                    backup_time=now,
                )
            else:
                # File was deleted during the turn (unlikely but possible)
                new_backups[path] = FileBackup(
                    backup_filename=None,
                    version=_file_versions.get(path, 0),
                    backup_time=now,
                )

    next_id = (snapshots[-1].id + 1) if snapshots else 1

    snapshot = Snapshot(
        id=next_id,
        session_id=session_id,
        created_at=now,
        turn_count=getattr(state, "turn_count", 0),
        message_index=len(getattr(state, "messages", [])),
        user_prompt_preview=user_prompt[:80] if user_prompt else "",
        token_snapshot={
            "input": getattr(state, "total_input_tokens", 0),
            "output": getattr(state, "total_output_tokens", 0),
        },
        file_backups=new_backups,
    )

    snapshots.append(snapshot)

    # Sliding window: keep only the last MAX_SNAPSHOTS
    if len(snapshots) > MAX_SNAPSHOTS:
        snapshots = snapshots[-MAX_SNAPSHOTS:]

    _save_snapshots(session_id, snapshots)
    return snapshot


def list_snapshots(session_id: str) -> list[dict]:
    """Return lightweight summaries of all snapshots."""
    snapshots = _load_snapshots(session_id)
    result = []
    for s in snapshots:
        result.append({
            "id": s.id,
            "turn_count": s.turn_count,
            "message_index": s.message_index,
            "created_at": s.created_at,
            "user_prompt_preview": s.user_prompt_preview,
            "file_count": len(s.file_backups),
        })
    return result


def get_snapshot(session_id: str, snapshot_id: int) -> Snapshot | None:
    snapshots = _load_snapshots(session_id)
    for s in snapshots:
        if s.id == snapshot_id:
            return s
    return None


def rewind_files(session_id: str, snapshot_id: int) -> list[str]:
    """Restore files to their state at the given snapshot.

    Returns list of restored/deleted file paths.
    """
    snapshot = get_snapshot(session_id, snapshot_id)
    if snapshot is None:
        return []

    bdir = _backups_dir(session_id)
    restored: list[str] = []

    for file_path, fb in snapshot.file_backups.items():
        try:
            if fb.backup_filename is None:
                # File didn't exist at snapshot time → delete it
                p = Path(file_path)
                if p.exists():
                    p.unlink()
                    restored.append(f"deleted: {file_path}")
            else:
                # Restore from backup
                backup_path = bdir / fb.backup_filename
                if backup_path.exists():
                    p = Path(file_path)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(backup_path), str(p))
                    restored.append(f"restored: {file_path}")
                else:
                    restored.append(f"backup missing: {file_path}")
        except Exception as e:
            restored.append(f"error restoring {file_path}: {e}")

    return restored


def files_changed_since(session_id: str, snapshot_id: int) -> list[str]:
    """List files that have been changed in snapshots after the given one."""
    snapshots = _load_snapshots(session_id)
    target = None
    for s in snapshots:
        if s.id == snapshot_id:
            target = s
            break
    if target is None:
        return []

    changed: set[str] = set()
    for s in snapshots:
        if s.id <= snapshot_id:
            continue
        for path in s.file_backups:
            if path not in target.file_backups or \
               s.file_backups[path].version != target.file_backups[path].version:
                changed.add(path)
    return sorted(changed)


def delete_session_checkpoints(session_id: str) -> bool:
    """Delete all checkpoints for a session."""
    d = _session_dir(session_id)
    if d.exists():
        shutil.rmtree(str(d), ignore_errors=True)
        return True
    return False


def cleanup_old_sessions(max_age_days: int = 30) -> int:
    """Remove checkpoint sessions older than max_age_days. Returns count removed."""
    root = _checkpoints_root()
    if not root.exists():
        return 0
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    try:
        for d in root.iterdir():
            if d.is_dir():
                try:
                    mtime = d.stat().st_mtime
                    if mtime < cutoff:
                        shutil.rmtree(str(d), ignore_errors=True)
                        removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    return removed


def reset_file_versions() -> None:
    """Reset per-file version counters (for testing)."""
    _file_versions.clear()
