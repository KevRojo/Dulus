<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — The Palmchat" width="280">

<h1>DULUS</h1>

<h3>Your AI Companion. Not a Chatbot. A Friend That Flies Beside You.</h3>

<p>
  <strong>Use frontier AI without an API key. $0. No credit card. No subscription.</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="Downloads"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/license-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="License"/>
  <img src="https://img.shields.io/badge/providers-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Providers"/>
  <img src="https://img.shields.io/badge/tools-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Tools"/>
  <img src="https://img.shields.io/badge/tests-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Tests"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#quick-start"><b>Quick Start</b></a> ·
  <a href="#features"><b>Features</b></a> ·
  <a href="#providers"><b>Providers</b></a> ·
  <a href="#architecture"><b>Architecture</b></a> ·
  <a href="#token"><b>$DULUS</b></a> ·
  <a href="https://dulus.ai/"><b>Website</b></a>
</p>

</div>

---

> Named after the **Palmchat** (*Dulus dominicus*), the national bird of the Dominican Republic — a symbol of freedom, resilience, and flying together. Dulus is not a chatbot. It is your companion, your friend, your AI partner that soars beside you.

---

## Why Dulus?

| | Locked Ecosystems | Complex Frameworks | **Dulus** |
|---|---|---|---|
| **Setup time** | Hours + approvals | Days of config | **30 seconds** |
| **Cost to start** | $$$ + API keys | $$$ + infra | **$0** |
| **Model lock-in** | Single provider | Single provider | **100+ providers** |
| **Codebase** | Black box | 100K+ lines | **~12K readable lines** |
| **Voice** | Cloud-only | Not included | **Offline Whisper** |
| **Memory** | Context-only | Manual | **MemPalace semantic** |

**The problem:** AI agents today are either locked to one provider (Claude-only, GPT-only) or require a PhD in ML engineering to set up. And they all want your credit card before you can even try them.

**The solution:** Dulus. A Python autonomous agent that connects to any model — from free browser-harvested sessions (Gemini guest, Claude.ai, Kimi, Qwen, DeepSeek) to 100+ paid providers via LiteLLM, to local models on your M2 Mac. ~12K lines of readable Python. No build step. No gatekeeping. Just talons.

---

## Quick Start

### 30-Second Install

```bash
pip install dulus && dulus
```

That is it. On first run, Dulus opens a browser, captures a **Gemini guest session** (no login, no API key, no credit card), and you are chatting with frontier AI in under 30 seconds.

### One-liner Installer (recommended)

**Linux / macOS / WSL:**
```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/KevRojo/Dulus/main/install.ps1 | iex
```

### Docker (zero local setup)

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## Features

| Feature | Description |
|---|---|
| Multi-Provider | 11 native providers + 100+ via LiteLLM (OpenRouter, Groq, Together, Bedrock, Vertex, Mistral, xAI, Fireworks, Azure...) |
| Zero-API-Key | Harvest free browser sessions from Gemini (guest), Claude.ai, Kimi.com, Qwen, DeepSeek |
| 30+ Built-in Tools | Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, NotebookEdit, OCR, Voice, and more |
| Auto-Adapter | Install any Python repo as a Dulus plugin — zero manifest required. `/plugin install yfinance@https://github.com/user/repo` |
| MemPalace | Semantic memory with ChromaDB — remembers across sessions, learns your preferences |
| Voice I/O | Offline STT via Whisper. TTS via ElevenLabs, Azure, or local engines. `/voice` |
| Sub-Agents | Typed agents (coder / reviewer / tester) in isolated git worktrees — the Flock |
| Mesa Redonda | Multi-model debate — multiple AI models working the same problem simultaneously |
| Sandbox OS | Full browser-based mini-OS with 58 apps. Runs entirely in your browser |
| Telegram Bridge | Run Dulus from your phone. Multi-user, slash commands, vision, voice |
| MCP Support | Model Context Protocol — connect any MCP server (stdio / SSE / HTTP) |
| Brainstorm | AI council of ghosts — auto-generated expert personas debate and distill |
| SSJ Mode | 10 workflow shortcuts: plan, worker, review, commit, ship — chained and unattended |
| Checkpoints | Snapshot and rewind any conversation turn. Never lose work |
| Context Compression | Auto-compact long sessions. Keep the signal, drop the slop |
| Local OCR | Extract text from images without vision-model tokens. `/ocr` |
| Multi-Language | `/lang` command — 34 ISO codes + free-form voice descriptors |
| Composio | 1,000+ SaaS integrations bundled |
| WebBridge | Browser automation via Playwright — navigate, click, evaluate JS, screenshot |

---

## Providers

### Free Tier (No API Key)

| Provider | Models | Setup |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | Open browser → type "hola" → done |
| **Claude.ai** | claude-sonnet-4-6 | Your existing claude.ai session |
| **Kimi.com** | kimi-k2.5 | Your existing kimi.com session |
| **Qwen** | qwen-max, qwen-plus | Your existing qwen.ai session |
| **DeepSeek** | deepseek-chat, deepseek-reasoner | Your existing deepseek session |
| **NVIDIA NIM** | 14 models, 40 RPM each | Free signup at build.nvidia.com |
| **Ollama** | Any local model | `ollama pull qwen2.5-coder` |

### Cloud APIs (API Key Required)

| Provider | Models | Environment Variable |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| Zhipu | glm-4-plus, glm-4, glm-4-flash | `ZHIPU_API_KEY` |
| MiniMax | MiniMax-Text-01, MiniMax-VL-01 | `MINIMAX_API_KEY` |
| LiteLLM | 100+ backends via one gateway | Backend-specific key |

### Switching Models

```bash
/model                    # show current model
/model gpt-4o             # switch to OpenAI
/model ollama/llama3.3    # switch to local Ollama
/model nvidia-web/deepseek-r1  # free NVIDIA tier
```

---

## Architecture

```
User Input
    |
    v
dulus.py  ── REPL, slash commands, voice, Telegram, GUI
    |
    ├── agent.py  ── Multi-turn loop, permission gates, governance
    |       |
    |       ├── providers.py  ── Multi-provider streaming (11 native + LiteLLM)
    |       ├── tool_registry.py ── Tool plugin system
    |       ├── tools.py  ── 30+ built-in tools
    |       ├── compaction.py  ── Context window management
    |       ├── governance.py  ── Budget/permission governance
    |       └── multi_agent/  ── Sub-agent lifecycle (the Flock)
    |
    ├── context.py  ── System prompt builder (git, CLAUDE.md, memory)
    |       └── memory/  ── MemPalace semantic memory
    |
    ├── skill/  ── Markdown skill loading + execution
    ├── checkpoint/  ── Session snapshots + rewind
    ├── plugin/  ── Auto-Adapter plugin system
    ├── voice/  ── STT (Whisper) + TTS (multi-engine)
    ├── task/  ── Task management
    ├── webbridge/  ── Playwright browser automation
    └── dulus_mcp/  ── MCP client
```

**Key invariant:** Dependencies flow downward. No circular imports. Every module has a small public API surface.

---

## The Flock (Sub-Agents)

Dulus can spawn typed agents that work in **isolated git worktrees** so they do not trip over each other. Ship a feature while a reviewer nitpicks the previous one. A tester runs in parallel.

```
/agents                              # show active flock
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

Agents talk to each other via `SendMessage` and `CheckAgentResult`.

---

## Permissions

| Mode | Behavior |
|---|---|
| `auto` *(default)* | Reads always allowed. Prompt before writes / shell. |
| `accept-all` | No prompts. Everything auto-approved. **YOLO.** |
| `manual` | Prompt for every operation. Paranoid setting. |
| `plan` | Read-only. Only the plan file is writable. |

Switch anytime: `/permissions auto` or `/permissions plan`.

---

## Slash Commands

`/` + Tab in the REPL shows everything. Highlights:

| Command | Description |
|---|---|
| `/model [name]` | Show or switch model |
| `/config [k=v]` | Read / write config |
| `/save` `/load` `/resume` | Session management |
| `/memory [query]` | Persistent semantic memory |
| `/skills` `/agents` | List skills / active flock |
| `/voice` | Voice input (offline Whisper) |
| `/image` `/img` | Clipboard image to vision model |
| `/brainstorm [topic]` | Council of ghosts |
| `/ssj` | Power menu (10 shortcuts) |
| `/worker [tasks]` | Auto-implement a TODO list |
| `/telegram [token] [id]` | Telegram bridge |
| `/checkpoint [id]` | List / rewind checkpoints |
| `/plan [desc]` | Enter / exit plan mode |
| `/compact [focus]` | Manual context compression |
| `/mcp` `/plugin` | Server + extension management |
| `/cost` | Tokens and USD burned |
| `/cloudsave` | Cloud sync via GitHub Gist |
| `/status` `/doctor` | Version + install health |
| `/lang [code]` | Switch language (34 codes) |
| `/help` | All commands, nicely printed |

---

## Built-in Tools

**Core:** Read · Write · Edit · Bash · Glob · Grep · WebFetch · WebSearch
**Notebook / Diagnostics:** NotebookEdit · GetDiagnostics
**Memory:** MemorySave · MemoryDelete · MemorySearch · MemoryList
**Agents:** Agent · SendMessage · CheckAgentResult · ListAgentTasks · ListAgentTypes
**Tasks:** TaskCreate · TaskUpdate · TaskGet · TaskList
**Skills:** Skill · SkillList
**Voice:** VoiceRecord · VoiceSpeak
**Other:** AskUserQuestion · SleepTimer · EnterPlanMode · ExitPlanMode · LaunchSandbox
**OCR:** ExtractTextFromImage
**WebBridge:** WebBridgeNavigate · WebBridgeClick · WebBridgeType · WebBridgeEvaluate · WebBridgeScreenshot
**tmux:** 11 tools for driving tmux sessions

MCP tools auto-registered as `mcp__<server>__<tool>`.

---

## Built Different

- **~12,000 lines** of readable Python. Not 100K+. Not TypeScript/JavaScript salad. Python you can read and modify in an afternoon.
- **No build step.** `pip install dulus` → it works. No npm. No webpack. No cargo.
- **No gatekeeping.** GPLv3. Fork it, bend it, run it offline.
- **One person, one vision.** Built by KevRojo from Santo Domingo, Dominican Republic.
- **263+ tests.** Real test coverage, not a badge.
- **2.5 MB wheel.** Smaller than most frameworks' READMEs.

---

## Community & Token

### $DULUS AI Token (Solana)

**Contract:** `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`

The $DULUS token is the fuel layer for the Dulus ecosystem. The open-source REPL stays free forever — $DULUS is the key to the business layer.

| Phase | Utility |
|---|---|
| **Now** | Community ownership. Creator-fee rewards locked on-chain |
| **Business v1** | Early access + discounted seats for $DULUS holders |
| **Credits** | Pay for Dulus Business API credits with $DULUS |
| **Deployments** | Spin up cloud Dulus instances, pay with $DULUS |
| **Subscriptions** | Monthly Dulus Pro subscription payable in $DULUS |
| **Governance** | Top holders vote on feature priority and marketplace policies |

> I am the top holder. I bought my position with my own funds. I am not selling. I will keep building. — KevRojo

### Connect

- **X / Twitter:** [@KevRojo](https://x.com/KevRojo) — Official creator account
- **GitHub:** [github.com/KevRojo/Dulus](https://github.com/KevRojo/Dulus)
- **Website:** [dulus.ai](https://dulus.ai/)
- **PyPI:** [pypi.org/project/dulus](https://pypi.org/project/dulus)
- **DexScreener:** [View $DULUS Chart](https://dexscreener.com/solana/9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump)

---

## License

GPLv3. Fork it, modify it, redistribute it — but keep it open.

> *Named after the bird, not the rocket. We keep flying.*

---

<div align="center">

**[Getting Started](GETTING_STARTED.md)** · **[Architecture](ARCHITECTURE.md)** · **[API Reference](API.md)** · **[Contributing](CONTRIBUTING.md)** · **[FAQ](FAQ.md)**

<p><sub>Built with talons by <a href="https://github.com/KevRojo">KevRojo</a> · Santo Domingo, Dominican Republic · 2026</sub></p>

</div>
