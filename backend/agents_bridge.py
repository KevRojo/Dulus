"""Agent info bridge — transforms personas / sub-agent tasks into AgentInfo format."""
from __future__ import annotations

# We deliberately AVOID importing backend.context.build_context here —
# it walks the entire source tree with rglob() and tries to git/write into
# the package directory, both of which break when Dulus is pip-installed
# (the package lives in read-only site-packages, not a git repo). Calling
# the lighter get_personas_for_context directly gives the AgentMonitor app
# what it needs without the rglob/git crash.


def build_agent_info_list() -> list[dict]:
    """Return agents in AgentInfo format for the sandbox AgentMonitor.

    Tries real SubAgentManager tasks first, then falls back to personas
    so the UI always has something to show.
    """
    agents: list[dict] = []

    # 1. Real sub-agent tasks (if running in the same process)
    try:
        from multi_agent.tools import get_agent_manager
        mgr = get_agent_manager()
        for task in mgr.list_tasks():
            status_map = {"pending": "idle", "running": "running", "completed": "completed", "failed": "error"}
            agents.append({
                "id": task.task_id,
                "name": task.name or task.task_id,
                "status": status_map.get(task.status, "idle"),
                "type": task.subagent_type or "sub-agent",
                "model": getattr(task, "agent_def", None) and task.agent_def.model or "",
                "start_time": getattr(task, "start_time", None),
                "last_activity": getattr(task, "end_time", None),
                "progress": 100 if task.status == "completed" else (0 if task.status == "pending" else 50),
                "task_count": 1,
                "logs": getattr(task, "logs", []) or [],
                "metadata": {
                    "source": "subagent",
                    "cancelled": getattr(task, "_cancel_flag", False),
                    "result_preview": str(task.result)[:200] if task.result else "",
                },
            })
    except Exception:
        pass

    # 2. Fallback / supplement with personas so the UI isn't empty
    try:
        from backend.personas import get_personas_for_context
        persona_agents = get_personas_for_context()
        existing_ids = {a["id"] for a in agents}
        for p in persona_agents:
            pid = p.get("name", "unknown").lower().replace(" ", "-")
            if pid in existing_ids:
                continue
            raw_status = p.get("status", "idle")
            # Map persona statuses to AgentInfo statuses
            status_map = {"active": "running", "idle": "idle"}
            mapped_status = status_map.get(raw_status, raw_status if raw_status in ("running", "paused", "completed", "error") else "idle")
            agents.append({
                "id": pid,
                "name": p.get("name", "Unknown"),
                "status": mapped_status,
                "type": p.get("role", "assistant"),
                "model": "",
                "start_time": None,
                "last_activity": None,
                "progress": None,
                "task_count": 0,
                "logs": [],
                "metadata": {
                    "source": "persona",
                    "color": p.get("color", "#ccc"),
                    "avatar": p.get("avatar", "🤖"),
                    "active": p.get("active", False),
                },
            })
    except Exception:
        pass

    return agents
