"""Memory tool registrations: MemorySave, MemoryDelete, MemorySearch.

Importing this module registers the three tools into the central registry.
"""
from __future__ import annotations

from datetime import datetime

from tool_registry import ToolDef, register_tool
from .store import MemoryEntry, save_memory, delete_memory, load_index, check_conflict, touch_last_used
from .context import find_relevant_memories
from .scan import scan_all_memories, format_memory_manifest
from .sessions import search_session_history


# ── Tool implementations ───────────────────────────────────────────────────

def _memory_save(params: dict, config: dict) -> str:
    """Save or update a persistent memory entry, with conflict detection."""
    scope = params.get("scope", "user")
    entry = MemoryEntry(
        name=params["name"],
        description=params["description"],
        type=params["type"],
        content=params["content"],
        created=datetime.now().strftime("%Y-%m-%d"),
        hall=params.get("hall", ""),
        confidence=float(params.get("confidence", 1.0)),
        source=params.get("source", "user"),
        conflict_group=params.get("conflict_group", ""),
    )

    conflict = check_conflict(entry, scope=scope)
    save_memory(entry, scope=scope)

    # ── Auto-mine into MemPalace (fire-and-forget) ──
    # mempalace skips already-filed files, so only the new MD gets indexed.
    if config.get("mem_palace", True) and scope == "user":
        try:
            import subprocess as _sp, sys as _sys, os as _os
            from pathlib import Path as _Path
            _mem_dir = _Path.home() / ".dulus" / "memory"
            _env = {**_os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            _sp.Popen(
                [_sys.executable, "-X", "utf8", "-m", "mempalace", "mine",
                 str(_mem_dir), "--wing", "memory", "--agent", "dulus"],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                env=_env,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass  # never block save on mining failure

    scope_label = "project" if scope == "project" else "user"
    hall_label = f"/{entry.hall}" if entry.hall else ""
    msg = f"Memory saved: '{entry.name}' [{entry.type}{hall_label}/{scope_label}]"
    if entry.confidence < 1.0:
        msg += f" (confidence: {entry.confidence:.0%})"
    if conflict:
        msg += (
            f"\n⚠ Replaced conflicting memory"
            f" (was {conflict['existing_source']}-sourced, {conflict['existing_confidence']:.0%} confidence,"
            f" written {conflict['existing_created'] or 'unknown date'})."
            f" Old content: {conflict['existing_content'][:120]}"
            f"{'...' if len(conflict['existing_content']) > 120 else ''}"
        )
    return msg


def _memory_delete(params: dict, config: dict) -> str:
    """Delete a persistent memory entry by name."""
    name = params["name"]
    scope = params.get("scope", "user")
    delete_memory(name, scope=scope)
    return f"Memory deleted: '{name}' (scope: {scope})"


def _memory_search(params: dict, config: dict) -> str:
    """Search memories by keyword query with optional AI relevance filtering.

    Results are ranked by: confidence × recency (30-day exponential decay).
    """
    import math, time as _time
    query = params["query"]
    use_ai = params.get("use_ai", False)
    
    if config.get("ULTRA_SEARCH") in (1, "1", True, "true"):
        params["include_sessions"] = True
        max_results = max(params.get("max_results", 5), 100)
    else:
        max_results = params.get("max_results", 5)

    results = find_relevant_memories(
        query, max_results=max_results * 3, use_ai=use_ai, config=config
    )

    if not results:
        return f"No memories found matching '{query}'."

    # Re-rank by confidence × recency score
    now = _time.time()
    for r in results:
        age_days = max(0, (now - r["mtime_s"]) / 86400)
        recency = math.exp(-age_days / 30)   # half-life ≈ 21 days
        r["_rank"] = r.get("confidence", 1.0) * recency
    results.sort(key=lambda r: r["_rank"], reverse=True)
    results = results[:max_results]

    # Touch last_used_at for returned memories
    for r in results:
        if r.get("file_path"):
            touch_last_used(r["file_path"])

    lines = [f"Found {len(results)} relevant memory/memories for '{query}':", ""]
    for r in results:
        freshness = f"  ⚠ {r['freshness_text']}" if r["freshness_text"] else ""
        conf = r.get("confidence", 1.0)
        src = r.get("source", "user")
        hall_tag = f"/{r['hall']}" if r.get("hall") else ""
        meta_tag = ""
        if conf < 1.0 or src != "user":
            meta_tag = f"  [conf:{conf:.0%} src:{src}]"
        lines.append(
            f"[{r['type']}{hall_tag}/{r['scope']}] {r['name']}{meta_tag}\n"
            f"  {r['description']}\n"
            f"  {r['content'][:200]}{'...' if len(r['content']) > 200 else ''}"
            f"{freshness}"
        )

    # ── Part 2: Session history search ───────────────────────────────────
    # Heuristic: If we found few results (< 3), automatically search session history
    # unless include_sessions was explicitly False.
    should_search_sessions = params.get("include_sessions")

    if should_search_sessions:
        sess_results = search_session_history(query, max_results=max_results)
        if sess_results:
            lines.append("\n" + "─" * 40)
            lines.append(f"Historical Session Matches ({len(sess_results)} sessions):")
            for sr in sess_results:
                lines.append(f"\nSession {sr['session_id']} ({sr['saved_at']})")
                for h in sr["hits"]:
                    role_lbl = "User" if h["role"] == "user" else "Dulus"
                    lines.append(f"  [{role_lbl}] {h['snippet']}")

    # ── Part 3: Offloaded Jobs Search ────────────────────────────────────
    try:
        from pathlib import Path
        import json
        jobs_dir = Path.home() / ".dulus" / "jobs"
        if jobs_dir.is_dir():
            job_matches = []
            q_lower = query.lower()
            q_words = [w.strip() for w in q_lower.split() if w.strip()]
            for fp in jobs_dir.glob("*.json"):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        job = json.load(f)
                    job_text = json.dumps(job, ensure_ascii=False).lower()
                    # Allow fuzzy token matching across the JSON content
                    if all(w in job_text for w in q_words):
                        job_matches.append(job)
                except Exception:
                    pass
            if job_matches:
                lines.append("\n" + "─" * 40)
                lines.append(f"Offloaded Background Jobs ({len(job_matches)} matches):")
                job_matches.sort(key=lambda j: j.get("created_at", ""), reverse=True)
                for j in job_matches[:max_results]:
                    status = j.get("status", "unknown")
                    lines.append(f"\nJob {j.get('id')} - Tool: {j.get('tool_name')} ({status})")
                    if j.get("params"):
                        lines.append(f"  Params: {json.dumps(j['params'], ensure_ascii=False)}")
                    if j.get("result"):
                        res = j["result"]
                        if len(res) > 300:
                            idx = res.lower().find(q_lower)
                            if idx != -1:
                                start = max(0, idx - 100)
                                end = min(len(res), idx + 200)
                                snippet = res[start:end].replace("\n", " ")
                                lines.append(f"  Result snippet: ...{snippet}...")
                            else:
                                lines.append(f"  Result snippet: {res[:300]}...")
                        else:
                            lines.append(f"  Result: {res}")
    except Exception:
        pass

    if not params.get("include_sessions") and not should_search_sessions:
        lines.append("\n💡 Hint: No matches? Call MemorySearch again with `include_sessions=True` to search through all past session chat logs.")

    if not lines[1:]: # Ensure we don't return an empty "Found 0" without hints
        pass

    return "\n".join(lines).strip()



def _memory_list(params: dict, config: dict) -> str:
    """List all memory entries with type, scope, age, confidence, and description."""
    from .store import load_entries

    scope_filter = params.get("scope", "all")
    scopes = ["user", "project"] if scope_filter == "all" else [scope_filter]

    all_entries = []
    for s in scopes:
        all_entries.extend(load_entries(s))

    if not all_entries:
        return "No memories stored." if scope_filter == "all" else f"No {scope_filter} memories stored."

    lines = [f"{len(all_entries)} memory/memories:"]
    for e in all_entries:
        conf_tag = f" conf:{e.confidence:.0%}" if e.confidence < 1.0 else ""
        src_tag = f" src:{e.source}" if e.source and e.source != "user" else ""
        cg_tag = f" grp:{e.conflict_group}" if e.conflict_group else ""
        hall_tag = f" hall:{e.hall}" if e.hall else ""
        meta = f"{conf_tag}{src_tag}{cg_tag}{hall_tag}".strip()
        tag = f"[{e.type:9s}|{e.scope:7s}]"
        lines.append(f"  {tag} {e.name}{(' — ' + meta) if meta else ''}")
        if e.description:
            lines.append(f"    {e.description}")
    return "\n".join(lines)


# ── Tool registrations ─────────────────────────────────────────────────────

register_tool(ToolDef(
    name="MemorySave",
    schema={
        "name": "MemorySave",
        "description": (
            "Save a persistent memory entry as a markdown file with frontmatter. "
            "Use for information that should persist across conversations: "
            "user preferences, feedback/corrections, project context, or external references. "
            "Do NOT save: code patterns, architecture, git history, or task state.\n\n"
            "For feedback/project memories, structure content as: "
            "rule/fact, then **Why:** and **How to apply:** lines.\n\n"
            "Optionally categorize with a 'hall': facts (decisions), events (milestones), "
            "discoveries (insights), preferences (habits), advice (recommendations)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Human-readable name (becomes the filename slug)",
                },
                "type": {
                    "type": "string",
                    "enum": ["user", "feedback", "project", "reference"],
                    "description": (
                        "user=preferences/role, feedback=guidance on how to work, "
                        "project=ongoing work/decisions, reference=external system pointers"
                    ),
                },
                "hall": {
                    "type": "string",
                    "enum": ["facts", "events", "discoveries", "preferences", "advice"],
                    "description": (
                        "Categorize HOW this memory should be used. "
                        "facts=decisions locked in, events=milestones/timeline, "
                        "discoveries=insights/breakthroughs, preferences=habits/likes, "
                        "advice=recommendations/solutions. Optional — omit if unsure."
                    ),
                },
                "description": {
                    "type": "string",
                    "description": "Short one-line description (used for relevance decisions — be specific)",
                },
                "content": {
                    "type": "string",
                    "description": "Body text. For feedback/project: rule/fact + **Why:** + **How to apply:**",
                },
                "scope": {
                    "type": "string",
                    "enum": ["user", "project"],
                    "description": (
                        "'user' (default) = ~/.dulus/memory/ shared across projects; "
                        "'project' = .dulus/memory/ local to this project"
                    ),
                },
                "confidence": {
                    "type": "number",
                    "description": (
                        "Reliability score 0.0–1.0. Default 1.0 = explicit user statement. "
                        "Use ~0.8 for inferred preferences, ~0.6 for uncertain facts."
                    ),
                },
                "source": {
                    "type": "string",
                    "enum": ["user", "model", "tool"],
                    "description": (
                        "Origin of this memory: 'user' (default, explicit statement), "
                        "'model' (inferred by AI), 'tool' (from tool output)."
                    ),
                },
                "conflict_group": {
                    "type": "string",
                    "description": (
                        "Optional tag grouping related or potentially conflicting memories "
                        "(e.g. 'writing_style'). Helps with conflict resolution."
                    ),
                },
            },
            "required": ["name", "type", "description", "content"],
        },
    },
    func=_memory_save,
    read_only=False,
    concurrent_safe=False,
))

register_tool(ToolDef(
    name="MemoryDelete",
    schema={
        "name": "MemoryDelete",
        "description": "Delete a persistent memory entry by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the memory to delete"},
                "scope": {
                    "type": "string",
                    "enum": ["user", "project"],
                    "description": "Scope to delete from (default: 'user')",
                },
            },
            "required": ["name"],
        },
    },
    func=_memory_delete,
    read_only=False,
    concurrent_safe=False,
))

register_tool(ToolDef(
    name="MemorySearch",
    schema={
        "name": "MemorySearch",
        "description": (
            "Search persistent memories using fuzzy token matching. Returns entries ranked by "
            "relevance (name/description weighted higher) with content preview and staleness "
            "warnings. Searches are 100% case-insensitive and support partial string matches automatically "
            "- do NOT query multiple casing variations. "
            "Set use_ai=true for AI-powered re-ranking (costs a small API call). "
            "Optionally filter by hall to narrow results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (supports fuzzy matching)"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 5). 💡 CRITICAL: To search deep session history exhaustively, you MUST set this to a high number (e.g. 50 or 100), otherwise it will cap at 5 sessions!",
                },
                "use_ai": {
                    "type": "boolean",
                    "description": "Use AI relevance ranking (default: false = fuzzy match only)",
                },
                "scope": {
                    "type": "string",
                    "enum": ["user", "project", "all"],
                    "description": "Which scope to search (default: 'all')",
                },
                "hall": {
                    "type": "string",
                    "enum": ["facts", "events", "discoveries", "preferences", "advice"],
                    "description": "Optional: only search within this hall category",
                },
                "include_sessions": {
                    "type": "boolean",
                    "description": "Include matches from historical session logs and offline background jobs. REQUIRED if the user asks for exhaustive search, 'past searches', 'history', 'previous sessions', 'antiguo', 'global', 'total', 'exhaustiva', or 'histórica'. (default: false)",
                },
            },
            "required": ["query"],
        },
    },
    func=_memory_search,
    read_only=True,
    concurrent_safe=True,
))

register_tool(ToolDef(
    name="MemoryList",
    schema={
        "name": "MemoryList",
        "description": (
            "List all memory entries with type, scope, age, and description. "
            "Useful for reviewing what's been remembered before deciding to save or delete."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["user", "project", "all"],
                    "description": "Which scope to list (default: 'all')",
                },
            },
        },
    },
    func=_memory_list,
    read_only=True,
    concurrent_safe=True,
))
