# Dulus Architecture Guide

> For developers who want to understand, modify, or extend Dulus. This document is the technical deep-dive.

---

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Module Reference](#module-reference)
- [Data Flow](#data-flow)
- [MemPalace Deep Dive](#mempalace-deep-dive)
- [Plugin System](#plugin-system)
- [Context Pipeline](#context-pipeline)
- [Security Model](#security-model)
- [Scalability](#scalability)

---

## High-Level Overview

Dulus is a ~31K-line Python autonomous agent with a flat module layout designed for readability and extensibility. The architecture follows a single invariant: **dependencies flow downward. No circular imports.**

```
User Input
    |
    v
+-------------+     +-------------+     +-------------+
|  dulus.py   |---->|  agent.py   |---->| providers.py|
|  (REPL)     |     |  (loop)     |     | (streaming) |
+-------------+     +------+------+     +-------------+
                           |
           +---------------+---------------+
           |               |               |
           v               v               v
    +-------------+ +-------------+ +-------------+
    | tool_registry | | compaction  | |multi_agent/ |
    |  + tools.py   | |  (context)  | | (flock)    |
    +-------------+ +-------------+ +-------------+
           |
           v
    +-------------+
    |  context.py |----> memory/ (MemPalace)
    | (sys prompt)|      skill/  (skills)
    +-------------+      plugin/ (Auto-Adapter)
                         voice/  (STT/TTS)
                         checkpoint/ (snapshots)
                         task/   (task mgmt)
                         webbridge/ (Playwright)
                         dulus_mcp/ (MCP client)
```

### Key Design Decisions

1. **Flat layout** — Every module is importable from the top level. No deep package hierarchies.
2. **Neutral message format** — Provider-independent: `{"role": "user", "content": "..."}`
3. **Generator-based streaming** — The agent loop yields events as they happen, enabling real-time UI updates.
4. **Threading, not asyncio** — The entire codebase uses synchronous generators. Threading via `concurrent.futures` keeps things simple and Ctrl+C-friendly.
5. **Graceful degradation** — Every optional dependency (voice, MemPalace, Playwright) fails softly. The CLI always boots and chats.

---

## Module Reference

### `dulus.py` — Entry Point (~11,800 lines)

The heart of Dulus. Contains:
- **REPL** — Read-eval-print loop with `prompt_toolkit` for autocompletion and history
- **Slash commands** — 30+ commands (`/model`, `/memory`, `/voice`, `/brainstorm`, etc.)
- **SSJ mode** — 10 workflow shortcuts (plan, worker, review, commit, ship)
- **Telegram bridge** — Multi-user bot integration
- **GUI integration** — tkinter desktop GUI launcher
- **Event rendering** — ANSI-colored output for tool calls, diffs, spinners

### `agent.py` — Core Agent Loop (~420 lines)

The agent's brain. `run()` is a generator that yields events:

```python
def run(user_message, state, config, system_prompt, depth=0, cancel_check=None):
    # 1. Append user message
    # 2. While True:
    #    a. maybe_compact(state, config) — compress if near limit
    #    b. Stream from provider → yield TextChunk / ThinkingChunk
    #    c. Record assistant message
    #    d. If no tool_calls → break
    #    e. For each tool_call:
    #       - Permission check (_check_permission)
#       - Execute tool → yield ToolStart / ToolEnd
    #       - Append tool result
    #    g. Loop (model sees tool results and responds)
```

**Event types:**

| Event | Fields | When |
|---|---|---|
| `TextChunk` | `text` | Streaming text delta |
| `ThinkingChunk` | `text` | Extended thinking block |
| `ToolStart` | `name, inputs` | Before tool execution |
| `ToolEnd` | `name, result, permitted` | After tool execution |
| `PermissionRequest` | `description, granted` | Needs user approval |
| `TurnDone` | `input_tokens, output_tokens` | End of one API turn |

### `providers.py` — Multi-Provider Streaming (~4,500 lines)

Two streaming adapters cover all providers:

| Adapter | Providers |
|---|---|
| `stream_anthropic()` | Anthropic (native SDK) |
| `stream_openai_compat()` | OpenAI, Gemini, Kimi, Qwen, Zhipu, DeepSeek, Ollama, LM Studio, Custom |

**Provider resilience:** Exponential backoff + jitter retry on timeouts, rate limits (429), and server errors (5xx). Does NOT retry on 4xx client errors.

**Neutral message format** (provider-independent):
```python
{"role": "user", "content": "..."}
{"role": "assistant", "content": "...", "tool_calls": [...]}
{"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}
```

### `tool_registry.py` — Tool Plugin System (~215 lines)

Central registry that all tools register into.

```python
@dataclass
class ToolDef:
    name: str               # unique identifier
    schema: dict            # JSON schema for LLM API
    func: Callable          # (params, config) -> str
    read_only: bool         # auto-approve in 'auto' mode
    concurrent_safe: bool   # safe for parallel execution
```

**Public API:**
- `register_tool(tool_def)` — Add a tool
- `get_tool(name)` — Look up by name
- `get_all_tools()` — List all registered tools
- `get_tool_schemas()` — Return schemas for API calls
- `execute_tool(name, params, config, max_output=32000)` — Execute with truncation

**Output truncation:** If a tool returns more than `max_output` chars, the result is truncated to `first_half + [... N chars truncated ...] + last_quarter`. Prevents a single tool call from blowing up the context window.

### `tools.py` — Built-in Tool Implementations (~2,940 lines)

Contains 30+ core tools:

**File:** Read, Write, Edit, Glob, Grep
**Shell:** Bash (with `_is_safe_bash` whitelist)
**Web:** WebFetch, WebSearch
**Notebook:** NotebookEdit, GetDiagnostics
**Memory:** MemorySave, MemoryDelete, MemorySearch, MemoryList
**Agents:** Agent, SendMessage, CheckAgentResult, ListAgentTasks, ListAgentTypes
**Tasks:** TaskCreate, TaskUpdate, TaskGet, TaskList
**Skills:** Skill, SkillList
**Voice:** VoiceRecord, VoiceSpeak
**Other:** AskUserQuestion, SleepTimer, EnterPlanMode, ExitPlanMode, LaunchSandbox
**OCR:** ExtractTextFromImage

### `compaction.py` — Context Window Management (~375 lines)

Two-layer compression system:

**Layer 1: Snip** (`snip_old_tool_results`)
- Rule-based, no API cost
- Truncates tool-role messages older than `preserve_last_n_turns` (default 6)
- Keeps first half + last quarter of content

**Layer 2: Auto-Compact** (`compact_messages`)
- Model-driven: calls the current model to summarize old messages
- Splits messages into [old | recent] at ~70/30 ratio
- Replaces old messages with a summary + acknowledgment

**Trigger:** `maybe_compact()` checks `estimate_tokens(messages) > context_limit * 0.7`.

**Token estimation:** `len(content) / 3.5` — simple heuristic that works for most models.

### `context.py` — System Prompt Builder (~360 lines)

Assembles the system prompt from:
1. Base template (role, date, cwd, platform)
2. Git info (branch, status, recent commits)
3. CLAUDE.md content (project-level + global)
4. Memory index (from `memory.get_memory_context()`)
5. Soul file (`~/.dulus/memory/soul.md`)

### `config.py` — Configuration (~185 lines)

- Config stored in `~/.dulus/config.json`
- Simple XOR + base64 encryption for API keys (no external deps)
- Environment variable bridging (config-stored keys → `os.environ`)
- Backward compatibility handling for legacy config formats

### `governance.py` — Budget & Permission Governance (~275 lines)

Opt-in governance layer:
- **Capability policies** — Restrict which tools the agent can use
- **Token budgets** — Hard/soft limits on tokens and tool calls
- **Hooks** — `pre_tool` and `post_tool` for audit, notify, metrics
- **Ledger** — Tracks consumption across dimensions

---

## Data Flow

### Example: "Read config.py and change max_tokens to 16384"

```
1. dulus.py captures input
2. agent.run() appends user message, calls maybe_compact()
3. providers.stream() sends to API with 30+ tool schemas
4. Model responds: text + tool_call[Read(config.py)]
5. agent.py checks permission (Read = read_only -> auto-approve)
6. tool_registry.execute_tool("Read", ...) -> file content
7. Tool result appended to messages, loop back to step 3
8. Model responds: text + tool_call[Edit(config.py, "8192", "16384")]
9. agent.py checks permission (Edit = not read_only -> ask user)
10. User approves -> tools.py._edit() runs, generates diff
11. dulus.py renders diff with ANSI colors (red/green)
12. Tool result appended, loop back to step 3
13. Model responds: "Done, max_tokens changed to 16384"
14. No tool_calls -> loop ends, TurnDone yielded
```

---

## MemPalace Deep Dive

MemPalace is Dulus's semantic memory system built on ChromaDB. It gives your companion the ability to remember across sessions.

### Architecture

```
User Query
    |
    v
+-------------+     +-------------+     +-------------+
|  Embedding  |---->|  ChromaDB   |---->|  Ranked     |
|  (sentence  |     |  (vector    |     |  Results    |
|   transformer|     |   store)    |     |  (confidence|
+-------------+     +-------------+     |   x recency)|
                                        +------+------+
                                               |
                                               v
                                        +-------------+
                                        |  Injected   |
                                        |  into sys   |
                                        |  prompt     |
                                        +-------------+
```

### Storage

- **User scope:** `~/.dulus/memory/`
- **Project scope:** `.dulus/memory/`
- **Format:** Markdown files with YAML frontmatter
- **Types:** `user`, `feedback`, `project`, `reference`
- **Index:** `MEMORY.md` — one line per memory entry

### Memory File Format

```markdown
---
name: user preferences
description: coding style preferences
type: feedback
created: 2026-04-02
---

User prefers 4-space indentation and type hints.
```

### Search

Search is ranked by **confidence x recency**. Mark a memory as "gold" to pin it to the top.

```python
/memory search jwt          # fuzzy ranked search
/memory load 1,2,3          # inject multiple into context
/memory consolidate         # distill session into long-term insights
/memory purge               # nuclear option (keeps Soul)
```

---

## Plugin System (Auto-Adapter)

Dulus's Auto-Adapter reads any Python repository and generates tool adapters — no `plugin.yaml` required.

### How It Works

1. User runs `/plugin install my-plugin@https://github.com/user/repo`
2. Auto-Adapter clones the repo, analyzes its structure
3. Generates adapter code mapping repo functions to ToolDef schemas
4. Registers tools live — no restart required
5. New tools appear as `plugin__<name>__<function>`

### Adding a Tool Manually

```python
from tool_registry import ToolDef, register_tool

def my_tool(params, config):
    return f"Hello, {params['name']}!"

register_tool(ToolDef(
    name="MyTool",
    schema={
        "name": "MyTool",
        "description": "A greeting tool",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    func=my_tool,
    read_only=True,
    concurrent_safe=True,
))
```

---

## Context Pipeline

The system prompt is assembled fresh every turn:

```
Base Template (role, date, cwd, platform)
    +
Git Info (branch, status, recent commits)
    +
CLAUDE.md (project conventions)
    +
Soul File (~/.dulus/memory/soul.md)
    +
Memory Index (ranked by confidence x recency)
    +
Active Skill (if any)
    |
    v
System Prompt (injected into every API call)
```

This ensures Dulus always has the full context: who you are, what project you're working on, your preferences, and relevant memories.

---

## Security Model

### Permission Modes

| Mode | Behavior |
|---|---|
| `auto` | Reads always allowed. Prompt before writes/shell. |
| `accept-all` | No prompts. Everything auto-approved. |
| `manual` | Prompt for every operation. |
| `plan` | Read-only. Only the plan file is writable. |

### Safe Bash Whitelist

The `_is_safe_bash()` function in `tools.py` maintains a whitelist of safe commands that can auto-approve in `auto` mode: `ls`, `cat`, `grep`, `find`, `git status`, `git log`, etc. Destructive commands (`rm`, `dd`, `mkfs`, etc.) always require explicit approval.

### Config Encryption

API keys stored in `~/.dulus/config.json` are encrypted with XOR + base64 using a secret derived from `DULUS_SECRET` environment variable (falls back to a default). Not military-grade, but protects against casual snooping.

### Governance Layer

The optional governance system (`governance.py`) provides:
- **Capability policies** — Restrict available tools per session
- **Token budgets** — Hard limits to protect your wallet
- **Audit hooks** — `pre_tool` and `post_tool` for logging

### Sandbox

The `sandbox/` directory contains Dulus OS — a browser-based mini-OS for isolated tool execution. Runs entirely client-side. Experimental but actively developed.

---

## Scalability

### Single-User (Local)

Dulus is designed for personal use on a single machine. The threading model handles concurrent sub-agents naturally via `ThreadPoolExecutor`.

### Multi-User (Telegram)

The Telegram bridge supports multi-user mode where each authorized chat gets its own message context. Dulus tracks who sent each message and routes responses back correctly.

### Server (WebChat)

The WebChat server (`webchat_server.py`) runs as a Flask app with SSE streaming. Supports:
- Multiple concurrent sessions (each with isolated state)
- Permission requests via WebSocket-like SSE
- Model switching without restart

### Future: Distributed Flock

The sub-agent architecture is designed to be network-transparent. Future versions may support:
- Remote agent execution over SSH
- Distributed flock across multiple machines
- Kubernetes deployment for enterprise use

---

## Testing

```bash
# Run the complete 780+ test suite
python -m pytest tests/ -v

# Run specific module tests
python -m pytest tests/test_tool_registry.py -v
python -m pytest tests/test_compaction.py -v
python -m pytest tests/test_memory.py -v
python -m pytest tests/test_subagent.py -v
python -m pytest tests/test_skills.py -v
```

Tests use `monkeypatch` and `tmp_path` fixtures to avoid side effects. Sub-agent tests mock `_agent_run` to avoid real API calls.

---

> *Named after the bird, not the rocket. We keep flying.*
