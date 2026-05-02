"""Audit trail for Falcon RTK — logs all tool operations."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

AUDIT_FILE = Path.home() / ".falcon" / "audit.log"
_MAX_AUDIT_LINES = 5000


def _ensure_dir() -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)


def log_operation(tool_name: str, params: Dict[str, Any], result_preview: str = "") -> None:
    """Log a tool operation with timestamp."""
    _ensure_dir()
    entry = {
        "t": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tool": tool_name,
        "params": {k: str(v)[:200] for k, v in params.items()},
        "result": result_preview[:300],
    }
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    _trim_audit()


def _trim_audit() -> None:
    """Keep audit file under max lines."""
    try:
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_AUDIT_LINES:
            trimmed = lines[-_MAX_AUDIT_LINES:]
            AUDIT_FILE.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
    except Exception:
        pass


def get_recent(n: int = 50) -> list[dict]:
    """Return last N audit entries."""
    try:
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-n:] if line.strip()]
    except Exception:
        return []
