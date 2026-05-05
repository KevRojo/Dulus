"""Task storage with JSON persistence."""
import json
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
TASKS_FILE = DATA_DIR / "tasks.json"

DEFAULT_TASKS = [
    {
        "id": "T-001",
        "subject": "Setup Dulus Backend",
        "status": "completed",
        "owner": "Dulus",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Infrastructure",
            "priority": "high",
            "blocked_by": [],
            "tags": ["backend", "api", "server"],
            "description": "Create Python backend to serve dashboard and manage tasks."
        }
    },
    {
        "id": "T-002",
        "subject": "Smart Context Manager (#23)",
        "status": "completed",
        "owner": "Dulus",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Core",
            "priority": "high",
            "blocked_by": [],
            "tags": ["context", "llm", "memory"],
            "description": "Build intelligent context generator for multi-agent sessions."
        }
    },
    {
        "id": "T-003",
        "subject": "Plugin System",
        "status": "completed",
        "owner": "Dulus",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Extensibility",
            "priority": "medium",
            "blocked_by": [],
            "tags": ["plugins", "extensions"],
            "description": "Hot-loadable plugin architecture for custom tools."
        }
    },
    {
        "id": "T-004",
        "subject": "Command Center HTML Dashboard",
        "status": "completed",
        "owner": "kimi-code",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "UI",
            "priority": "high",
            "blocked_by": [],
            "tags": ["ui", "dashboard", "html"],
            "description": "Standalone premium HTML dashboard with 4 functional tabs."
        }
    },
    {
        "id": "T-005",
        "subject": "Theme Pack Premium",
        "status": "completed",
        "owner": "kimi-code",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "UI",
            "priority": "medium",
            "blocked_by": [],
            "tags": ["ui", "themes", "customtkinter"],
            "description": "4 premium themes mapped per agent for GUI integration."
        }
    },
    {
        "id": "T-006",
        "subject": "API Docs Generator",
        "status": "completed",
        "owner": "kimi-code3",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Docs",
            "priority": "medium",
            "blocked_by": [],
            "tags": ["docs", "api", "automation"],
            "description": "Auto-scan 167 modules and generate docs/api.html with dependency graph."
        }
    },
    {
        "id": "T-007",
        "subject": "MemPalace Integration",
        "status": "completed",
        "owner": "Dulus",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Integration",
            "priority": "high",
            "blocked_by": [],
            "tags": ["memory", "mempalace", "persistence"],
            "description": "Wire Smart Context into MemPalace for infinite agent memory."
        }
    },
    {
        "id": "T-008",
        "subject": "Hybrid Compressor (qwen + rule-based)",
        "status": "completed",
        "owner": "kimi-code2",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Core",
            "priority": "high",
            "blocked_by": [],
            "tags": ["compression", "ollama", "qwen", "context"],
            "description": "Context compressor with local LLM fallback and rule-based engine."
        }
    },
    {
        "id": "T-009",
        "subject": "Test Coverage Expansion",
        "status": "in_progress",
        "owner": "kimi-code",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Quality",
            "priority": "medium",
            "blocked_by": [],
            "tags": ["pytest", "coverage", "testing"],
            "description": "Backfill tests for context, tasks, githook, and compressor modules."
        }
    },
    {
        "id": "T-010",
        "subject": "Multi-Agent Mesa Redonda",
        "status": "in_progress",
        "owner": "Dulus",
        "created_at": "2026-04-26",
        "updated_at": "2026-04-26",
        "metadata": {
            "phase": "Core",
            "priority": "high",
            "blocked_by": [],
            "tags": ["multi-agent", "collaboration", "orchestration"],
            "description": "Round-table mode for parallel agent collaboration with proactive work loops."
        }
    }
]


def load_tasks() -> list[dict[str, Any]]:
    if TASKS_FILE.exists():
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    save_tasks(DEFAULT_TASKS)
    return DEFAULT_TASKS.copy()


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def get_task(tid: str) -> dict[str, Any] | None:
    for t in load_tasks():
        if t["id"] == tid:
            return t
    return None


def update_task(tid: str, data: dict[str, Any]) -> dict[str, Any] | None:
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t["id"] == tid:
            tasks[i].update(data)
            tasks[i]["updated_at"] = time.strftime("%Y-%m-%d")
            save_tasks(tasks)
            return tasks[i]
    return None


def create_task(data: dict[str, Any]) -> dict[str, Any]:
    tasks = load_tasks()
    new_id = f"T-{len(tasks)+1:03d}"
    task = {
        "id": new_id,
        "subject": data.get("subject", "New Task"),
        "status": data.get("status", "pending"),
        "owner": data.get("owner", "Unassigned"),
        "created_at": time.strftime("%Y-%m-%d"),
        "updated_at": time.strftime("%Y-%m-%d"),
        "metadata": data.get("metadata", {})
    }
    tasks.append(task)
    save_tasks(tasks)
    return task
