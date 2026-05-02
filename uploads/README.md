# Falcon

**Falcon** is a lightweight Python reimplementation of Claude Code that supports **any model** — Claude, GPT, Gemini, DeepSeek, Qwen, MiniMax, Kimi, Zhipu, and local models via Ollama.

~12K lines of readable Python. No build step. Just `pip install` and run.

### 🚀 News
- Apr 09, 2026 (**v1.01.20**): **Automated Plugin Adapter System, Premium UI, and Hot-Reloading**
  - **Automated Plugin Adapter** — Intelligently onboard any Python repo without a manual manifest.
  - **Hot-Reloading** — Newly adapted plugins registered and available in the current session immediately.
  - **Premium UI** — Real-time thinking spinners and refined visual feedback.

---

<div align="center">
  <img src="docs/logo-5.png" alt="Logo" width="280">
</div>

<div align="center">
  <img src="https://github.com/SafeRL-Lab/clawspring/blob/main/docs/demo.gif" width="850"/>
  <p>Task Execution</p>
</div>

---

<div align="center">
  <img src="https://github.com/SafeRL-Lab/clawspring/blob/main/docs/brainstorm_demo.gif" width="850"/>
  <p>Brainstorm Mode: Multi-Agent Brainstorm</p>
</div>

---

<div align="center">
  <img src="https://github.com/SafeRL-Lab/clawspring/blob/main/docs/proactive_demo.gif" width="850"/>
  <p>Proactive Mode: Autonomous Agent</p>
</div>

---

<div align="center">
  <img src="https://github.com/SafeRL-Lab/clawspring/blob/main/docs/ssj_demo.gif" width="850"/>
  <p>SSJ Developer Mode: Power Menu Workflow</p>
</div>

---

<div align="center">
  <img src="https://github.com/SafeRL-Lab/clawspring/blob/main/docs/telegram_demo.gif" width="850"/>
  <p>Telegram Bridge: Control Falcon from Your Phone</p>
</div>

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/KevRojo/Falcon
cd Falcon

# Option A: global install with uv
uv tool install .

# Option B: run directly
pip install -r requirements.txt
python falcon.py
```

Set an API key and go:

```bash
export ANTHROPIC_API_KEY=sk-ant-...    # or OPENAI_API_KEY, GEMINI_API_KEY, etc.
falcon --model claude-sonnet-4-6
```

For local models (no API key needed):

```bash
ollama pull qwen2.5-coder
falcon --model ollama/qwen2.5-coder
```

---

## Features

| Feature | Details |
|---|---|
| Multi-provider | Anthropic, OpenAI, Gemini, Kimi, Qwen, Zhipu, DeepSeek, MiniMax, Ollama, LM Studio, custom endpoints |
| 27 built-in tools | Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, NotebookEdit, GetDiagnostics, Memory, Tasks, Agents, Skills, and more |
| MCP integration | Connect any MCP server (stdio/SSE/HTTP), tools auto-registered |
| Plugin system | Auto-Adapter: intelligently onboard any Python repo without a manual manifest |
| Sub-agents | Spawn typed agents (coder/reviewer/researcher/tester) with optional git worktree isolation |
| Voice input | Offline STT via Whisper — no API key required |
| Brainstorm | Multi-persona AI debate with auto-generated expert roles |
| SSJ Developer Mode | Power menu with 10 workflow shortcuts |
| Telegram bridge | Control Falcon from your phone |
| Checkpoints | Auto-snapshot conversation + files; rewind to any point |
| Plan mode | Read-only analysis phase before implementation |
| Context compression | Auto-compact long conversations to stay within model limits |
| tmux tools | 11 tools for the AI to control tmux sessions |
| Persistent memory | Dual-scope (user + project) with confidence, recency ranking |
| Session management | Autosave, daily archives, cloud sync via GitHub Gist |

---

## Supported Models

### Cloud APIs

| Provider | Models | API Key Env |
|---|---|---|
| **Anthropic** | `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `o3-mini`, `o1` | `OPENAI_API_KEY` |
| **Google** | `gemini-2.5-pro-preview-03-25`, `gemini-2.0-flash`, `gemini-1.5-pro` | `GEMINI_API_KEY` |
| **DeepSeek** | `deepseek-chat`, `deepseek-reasoner` | `DEEPSEEK_API_KEY` |
| **Qwen** | `qwen-max`, `qwen-plus`, `qwen-turbo`, `qwq-32b` | `DASHSCOPE_API_KEY` |
| **Kimi** | `moonshot-v1-8k/32k/128k` | `MOONSHOT_API_KEY` |
| **Zhipu** | `glm-4-plus`, `glm-4`, `glm-4-flash` | `ZHIPU_API_KEY` |
| **MiniMax** | `MiniMax-Text-01`, `MiniMax-VL-01`, `abab6.5s-chat` | `MINIMAX_API_KEY` |

### Local Models (Ollama)

Recommended for coding: `qwen2.5-coder`, `llama3.3`, `mistral`, `phi4`. Vision: `llava`, `llama3.2-vision`.

```bash
ollama pull qwen2.5-coder
falcon --model ollama/qwen2.5-coder
```

Also works with **LM Studio** (`lmstudio/<model>`) and any **OpenAI-compatible server** (`custom/<model>` + `CUSTOM_BASE_URL`).

---

## Usage

```bash
falcon                              # interactive REPL (default model)
falcon --model gpt-4o               # choose model
falcon -p "explain this code"       # non-interactive mode
falcon --accept-all -p "init project"  # no permission prompts (CI)
falcon --thinking --verbose         # extended thinking (Claude)
```

### Model name format

```bash
falcon --model gpt-4o                    # auto-detected
falcon --model ollama/qwen2.5-coder      # explicit provider/model
falcon --model kimi:moonshot-v1-32k      # colon syntax also works
```

### API keys

Set via environment variables, `/config` in the REPL, or edit `~/.falcon/config.json` directly.

---

## Slash Commands

Type `/` + Tab to see all commands. Key commands:

| Command | Description |
|---|---|
| `/model [name]` | Show/switch model |
| `/config [key=val]` | Show/set config |
| `/save` `/load` `/resume` | Session management |
| `/memory [query]` | Persistent memory |
| `/skills` `/agents` | List skills/agents |
| `/voice` | Voice input (offline Whisper) |
| `/image` `/img` | Send clipboard image to vision model |
| `/brainstorm [topic]` | Multi-persona AI debate |
| `/ssj` | SSJ Developer Mode power menu |
| `/worker [tasks]` | Auto-implement TODO tasks |
| `/telegram [token] [chat_id]` | Telegram bot bridge |
| `/checkpoint [id]` | List/rewind checkpoints |
| `/plan [desc]` | Enter/exit plan mode |
| `/compact [focus]` | Manual context compression |
| `/mcp` | MCP server management |
| `/plugin` | Plugin management |
| `/cost` | Token usage and cost estimate |
| `/cloudsave` | Cloud sync via GitHub Gist |
| `/status` | Version, model, provider info |
| `/doctor` | Diagnose installation health |
| `/init` | Create CLAUDE.md template |
| `/export` | Export conversation |
| `/copy` | Copy last response to clipboard |
| `/news` | Show latest project updates and features |
| `/help` | Show all commands |

---

## Permission System

| Mode | Behavior |
|---|---|
| `auto` (default) | Reads always allowed. Prompts before writes and shell commands. |
| `accept-all` | No prompts. Everything auto-approved. |
| `manual` | Prompts for every operation. |
| `plan` | Read-only. Only the plan file is writable. |

---

## Built-in Tools

**Core:** Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch
**Notebook/Diagnostics:** NotebookEdit, GetDiagnostics
**Memory:** MemorySave, MemoryDelete, MemorySearch, MemoryList
**Agents:** Agent, SendMessage, CheckAgentResult, ListAgentTasks, ListAgentTypes
**Tasks:** TaskCreate, TaskUpdate, TaskGet, TaskList
**Skills:** Skill, SkillList
**Other:** AskUserQuestion, SleepTimer, EnterPlanMode, ExitPlanMode

MCP tools are auto-registered as `mcp__<server>__<tool>`.

---

## MCP (Model Context Protocol)

Add a `.mcp.json` to your project or `~/.falcon/mcp.json` for user-wide config:

```json
{
  "mcpServers": {
    "git": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-git"]
    }
  }
}
```

Manage in the REPL: `/mcp`, `/mcp reload`, `/mcp add <name> <cmd> [args]`, `/mcp remove <name>`.

---

## Plugin System

```bash
/plugin install my-plugin@https://github.com/user/my-plugin
/plugin                    # list installed
/plugin enable/disable     # toggle
/plugin update/uninstall   # manage
/plugin recommend          # auto-detect useful plugins
```

---

## Memory

Persistent memories stored as markdown files in two scopes:

| Scope | Path |
|---|---|
| User | `~/.falcon/memory/` |
| Project | `.falcon/memory/` |

Types: `user`, `feedback`, `project`, `reference`. Search is ranked by confidence x recency.

---

## Skills

Built-in: `/commit` (git commit helper), `/review` (code review).

Custom skills: create markdown files in `~/.falcon/skills/` or `.falcon/skills/`.

---

## Voice Input

```bash
pip install sounddevice faster-whisper numpy
```

Then `/voice` in the REPL. Works fully offline. Supports `/voice lang <code>` and `/voice device` for mic selection.

---

## Telegram Bridge

```bash
/telegram <bot_token> <chat_id>
```

Auto-starts on next launch. Supports slash commands, vision, and voice from Telegram.

---

## CLAUDE.md

Place a `CLAUDE.md` in your project root to give the model persistent context about your codebase. Auto-injected into the system prompt.

---

## Project Structure

```
falcon/
├── falcon.py             # Entry point: REPL, slash commands, SSJ, Telegram
├── agent.py              # Agent loop: streaming, tool dispatch, compaction
├── providers.py          # Multi-provider streaming
├── tools.py              # Core tools + registry wiring
├── tool_registry.py      # Tool plugin registry
├── compaction.py         # Context compression
├── context.py            # System prompt builder
├── config.py             # Config management
├── cloudsave.py          # GitHub Gist sync
├── multi_agent/          # Sub-agent system
├── memory/               # Persistent memory
├── skill/                # Skill system
├── mcp/                  # MCP client
├── voice/                # Voice input
├── checkpoint/           # Checkpoint/rewind system
├── plugin/               # Plugin system
├── task/                 # Task management
└── tests/                # 263+ unit tests
```

---

## FAQ

**Tool calls don't work with my local model?**
Use a model that supports function calling: `qwen2.5-coder`, `llama3.3`, `mistral`, `phi4`.

**How to connect to a remote GPU server?**
```
/config custom_base_url=http://your-server:8000/v1
/model custom/your-model-name
```

**How to check API cost?**
`/cost`

**Voice transcribes coding terms wrong?**
Add terms to `.falcon/voice_keyterms.txt` (one per line).

**Can I pipe input?**
```bash
echo "Explain this" | falcon -p --accept-all
```
