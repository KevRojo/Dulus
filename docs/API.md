# Dulus API Reference

> For developers integrating Dulus programmatically or building on top of it.

---

## Table of Contents

- [Agent API (Python)](#agent-api-python)
- [WebChat Server](#webchat-server)
- [WebSocket Events](#websocket-events)
- [Batch Processor](#batch-processor)
- [MCP Bridge](#mcp-bridge)
- [Error Codes](#error-codes)

---

## Agent API (Python)

The core agent loop is exposed as a Python generator.

### `agent.run()`

```python
from agent import run, AgentState, TextChunk, ToolStart, ToolEnd, TurnDone

state = AgentState()
config = {"model": "ollama/gemma4:latest", "max_tokens": 128000}
system_prompt = "You are Dulus, a helpful coding assistant."

for event in run("Hello, world!", state, config, system_prompt):
    if isinstance(event, TextChunk):
        print(event.text, end="")
    elif isinstance(event, ToolStart):
        print(f"\n[Tool: {event.name}]")
    elif isinstance(event, ToolEnd):
        print(f"\n[Result: {event.result[:100]}]")
    elif isinstance(event, TurnDone):
        print(f"\n[Tokens: {event.input_tokens} in, {event.output_tokens} out]")
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `user_message` | `str` | required | The user's input message |
| `state` | `AgentState` | required | Mutable session state (messages, tokens) |
| `config` | `dict` | required | Configuration (model, permissions, etc.) |
| `system_prompt` | `str` | required | System prompt injected into every call |
| `depth` | `int` | `0` | Sub-agent nesting depth |
| `cancel_check` | `Callable` | `None` | Returns `True` to abort the loop |

### Event Types

```python
@dataclass
class TextChunk:
    text: str           # Streaming text delta

@dataclass
class ThinkingChunk:
    text: str           # Extended thinking/reasoning block

@dataclass
class ToolStart:
    name: str           # Tool name being executed
    inputs: dict        # Tool parameters

@dataclass
class ToolEnd:
    name: str           # Tool name that was executed
    result: str         # Tool output (may be truncated)
    permitted: bool     # Whether the operation was approved

@dataclass
class TurnDone:
    input_tokens: int           # Input tokens this turn
    output_tokens: int          # Output tokens this turn
    cache_read_tokens: int      # Cache read (Anthropic)
    cache_creation_tokens: int  # Cache write (Anthropic)

@dataclass
class PermissionRequest:
    description: str    # Human-readable operation description
    granted: bool       # Set to True to approve
```

### `AgentState`

```python
@dataclass
class AgentState:
    messages: list = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    turn_count: int = 0
```

The `messages` list uses the neutral format:
```python
{"role": "user", "content": "..."}
{"role": "assistant", "content": "...", "tool_calls": [...]}
{"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}
```

---

## WebChat Server

The WebChat server provides a REST API + SSE streaming endpoint.

### Endpoints

#### `GET /`

Returns the WebChat HTML UI.

**Response:** `text/html`

---

#### `GET /state`

Returns current conversation state.

**Response:**
```json
{
  "model": "ollama/gemma4:latest",
  "history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!", "thinking": ""},
    {"role": "tool", "tool_call_id": "...", "name": "Bash", "content": "..."}
  ]
}
```

---

#### `POST /chat`

Send a message to the agent. Returns SSE stream.

**Request:**
```json
{"message": "Hello, Dulus!"}
```

**Response:** `text/event-stream`

Each line is a Server-Sent Event:
```
data: {"type": "text", "text": "Hello"}
data: {"type": "thinking", "text": "Let me think..."}
data: {"type": "tool_start", "name": "Bash", "inputs": {"command": "ls"}}
data: {"type": "tool_end", "name": "Bash", "result": "file1.py\nfile2.py", "permitted": true}
data: {"type": "turn_done", "in": 42, "out": 128}
data: {"type": "done"}
```

**Event Types:**

| Type | Fields | Description |
|---|---|---|
| `start` | — | Stream begins |
| `text` | `text` | Streaming text chunk |
| `thinking` | `text` | Thinking/reasoning block |
| `tool_start` | `name`, `inputs` | Tool execution started |
| `tool_end` | `name`, `result`, `permitted` | Tool execution completed |
| `turn_done` | `in`, `out` | Turn completed with token counts |
| `permission` | `id`, `description` | Permission request (see below) |
| `error` | `message` | Error occurred |
| `done` | — | Stream complete |

---

#### `POST /permission`

Approve or deny a pending permission request.

**Request:**
```json
{"id": "uuid-here", "granted": true}
```

**Response:**
```json
{"ok": true}
```

When a permission request is sent via SSE:
```
data: {"type": "permission", "id": "abc-123", "description": "Run: rm -rf /tmp"}
```

The client must POST to `/permission` with the same `id` to approve or deny.

---

#### `POST /clear`

Clear the conversation history.

**Response:**
```json
{"ok": true}
```

---

### Running the Server

```python
from webchat import create_app

app = create_app()
app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
```

Or via CLI:
```bash
dulus-webchat --port 5000 --host 0.0.0.0 --open
```

Or from the REPL:
```
/webchat
```

---

## Batch Processor

Dulus includes a batch API for processing multiple inputs.

### `batch_api.py`

```python
from batch_api import BatchProcessor

processor = BatchProcessor(config={"model": "gpt-4o"})
results = processor.process([
    "Summarize this: ...",
    "Translate this: ...",
    "Code review: ...",
])
for result in results:
    print(result.output)
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
```

---

## MCP Bridge

Dulus implements the Model Context Protocol (MCP) for connecting external tool servers.

### Configuration

Create `.mcp.json` in your project root (or `~/.dulus/mcp.json`):

```json
{
  "mcpServers": {
    "git": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-git"]
    },
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@playwright/mcp"]
    },
    "slack": {
      "type": "sse",
      "url": "http://localhost:3001/sse"
    }
  }
}
```

### Supported Types

| Type | Description | Example |
|---|---|---|
| `stdio` | Local command via stdin/stdout | `mcp-server-git` |
| `sse` | Server-Sent Events over HTTP | `@playwright/mcp` |
| `http` | Direct HTTP API | Custom servers |

### REPL Commands

```
/mcp                        # list connected servers
/mcp reload                 # reload configuration
/mcp add <name> <cmd> [args]  # add a server
/mcp remove <name>          # remove a server
```

### Tool Registration

MCP tools are auto-registered as `mcp__<server>__<tool>`:

```
mcp__git__status            # git status via MCP
mcp__playwright__navigate   # browser navigation via MCP
mcp__slack__send_message    # Slack message via MCP
```

---

## Error Codes

### Agent Errors

| Code | Meaning | Resolution |
|---|---|---|
| `PROVIDER_ERROR` | API provider returned error | Check API key, model name, rate limits |
| `TOOL_NOT_FOUND` | Requested tool not in registry | Check tool name, ensure module imported |
| `PERMISSION_DENIED` | User rejected operation | Approve the operation or switch mode |
| `CONTEXT_OVERFLOW` | Messages exceed context limit | Run `/compact` or start new session |
| `RATE_LIMITED` | Provider rate limit hit | Wait or switch model with `/model` |
| `BASH_TIMEOUT` | Shell command timed out | Increase timeout or simplify command |
| `BASH_ERROR` | Shell command returned non-zero | Check command syntax and arguments |
| `FILE_NOT_FOUND` | Read/Glob target doesn't exist | Check file path |
| `PLUGIN_ERROR` | Plugin adapter failed | Check plugin URL, run `/plugin reload` |
| `MCP_ERROR` | MCP server connection failed | Check server config, restart server |
| `VOICE_ERROR` | STT/TTS engine failed | Check microphone, audio drivers |
| `MEMORY_ERROR` | MemPalace query failed | Check ChromaDB installation |

### WebChat HTTP Errors

| Status | Meaning |
|---|---|
| `400` | Empty message or invalid JSON |
| `404` | Permission ID not found |
| `500` | Internal agent error |

---

> *Named after the bird, not the rocket. We keep flying.*
