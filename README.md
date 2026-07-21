# ▲ DULUS

> **Use AI free — a CLI coding agent with no API key required to get started.**
>
> Dulus is a lightweight Python reimplementation of Claude Code that isn't locked to one provider. It ships the whole loop — REPL, tool dispatch, streaming, context compaction, checkpoints, sub-agents, voice, Telegram bridge, MCP, plugins — in code you can actually read and fork.
>
> Plus LiteLLM (100+ paid providers), local models via Ollama, `/lang` in 34 languages, Mesa Redonda multi-model debate, voice in/out, local OCR, MemPalace semantic memory, embedded sandbox OS. No build step. No gatekeeping.

<p align="center">
  <img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — Cigua Palmera" width="320">
</p>

<p align="center"><i>The Dulus (Cigua Palmera) — Dominican national bird. Named after the bird, not the rocket.</i></p>

<p align="center">
  <a href="#quick-start"><b>Quick Start</b></a> ·
  <a href="#models"><b>Models</b></a> ·
  <a href="#features"><b>Features</b></a> ·
  <a href="#permissions"><b>Permissions</b></a> ·
  <a href="#mcp"><b>MCP</b></a> ·
  <a href="#plugins"><b>Plugins</b></a> ·
  <a href="#slash-commands"><b>Slash commands</b></a> ·
  <a href="#faq"><b>FAQ</b></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="pypi"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="downloads"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="python"/>
  <img src="https://img.shields.io/badge/license-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="license"/>
  <img src="https://img.shields.io/badge/version-v3.10.18-ff6b1f?style=flat-square&labelColor=07070a" alt="version"/>
  <img src="https://img.shields.io/badge/providers-100%2B%20via%20LiteLLM-ff6b1f?style=flat-square&labelColor=07070a" alt="providers"/>
  <img src="https://img.shields.io/badge/tools-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="tools"/>
  <img src="https://img.shields.io/badge/tests-263+-ff6b1f?style=flat-square&labelColor=07070a" alt="tests"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="x"/></a>
</p>

<p align="center">
  🌐 <b>Multilingual</b> ·
  <a href="docs/README_EN.md">English</a> ·
  <a href="docs/README_ES.md">Español</a> ·
  <a href="docs/README_FR.md">Français</a> ·
  <a href="docs/README_ZH.md">中文</a> ·
  <a href="docs/README_JA.md">日本語</a> ·
  <a href="docs/README_KO.md">한국어</a> ·
  <a href="docs/README_PT.md">Português</a> ·
  <a href="docs/README_RU.md">Русский</a> ·
  <a href="docs/README_AR.md">العربية</a>
</p>

> **Official X / creator handle:** [@KevRojo](https://x.com/KevRojo) — that's me, the only contributor to this repo. Any other account claiming to be Dulus is a copycat.

-----

<p align="center">
  <code>pip install dulus</code>
</p>

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

<p align="center">
  <a href="https://dulus.ai/"><b>🌐 dulus.ai</b></a> — features, demos & the full tour&nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="https://dulus.online/"><b>🏢 dulus.online</b></a> — Synthetic Operations: deploy & govern AI fleets&nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="https://dulus.work/"><b>🌍 dulus.work</b></a> — the HUB<br>
  <sub>Three fronts, one bird: the free CLI, the platform where fleets run, and the network that makes them all smarter.</sub>
</p>

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## 🔥 What's new

> Full changelog: [`docs/news.md`](docs/news.md)  ·  Inside the REPL: `/news`

- **🔬 Fully type-checked — 582 → 0, and real bugs fell out.** A top-to-bottom Pyright pass took the codebase from **582 static errors to zero** across 142 files — and it wasn't cosmetics. The checker flushed out genuine landmines: the skill runner (`execute_skill`) was called with the wrong arguments in the `--command` path and would have thrown `TypeError` the moment a skill ran; `/mcp reload` accidentally shadowed its own error printer and then tried to *call a string*; and a handful of dead imports pointed at symbols that no longer existed — repaired to the real APIs. Cleaner to read, safer to fork, fewer surprises. 🦅
- **🩹 First community bug report → fixed on PyPI the same day.** [@aognio](https://github.com/aognio) found Dulus through Hacker News and reported a crash when NVIDIA's free tier ran out of quota ([#18](https://github.com/KevRojo/Dulus/issues/18)). Root cause: quota errors arrive mid-stream, past the old error guard. Now provider failures can't kill the REPL — fallback chain first, friendly *"try /model"* worst case, history intact. Report a bug, get a release. 🦅
- **🛰️ Error tracking that actually tracks.** Confession: a mis-configured Sentry init meant no crash report had ever left anyone's machine. Fixed with a silent atexit flush (no noisy exit banner), and quota/provider failures now report as handled events — visibility without crashes.
- **🌐 Three domains, one organism.** [dulus.ai](https://dulus.ai) is the front door. [dulus.online](https://dulus.online) is *Synthetic Operations* — deploy one agent or an entire company: persistent workers with tools, memory, approvals and measurable ownership, coordinated by MOD (plan → execute → validate, every step with a receipt). [dulus.work](https://dulus.work) is the HUB where every instance shares what it learns.
- **🔄 Self-update — the fleet moves as one.** Dulus keeps itself current: a quiet, cached, non-blocking check against PyPI at startup, and if there's a newer release it upgrades in place. `/update`, `/update now`, `/update status`, `/update on|off`. On by default, handles PEP 668, never blocks your boot. 🦅
- **🔌 MCP Marketplace — 2000+ servers, zero friction.** `/mcp search <anything>` browses **2000+ servers** (the official [modelcontextprotocol.io](https://registry.modelcontextprotocol.io) registry + the awesome-mcp list, cached & offline-safe), and `/mcp install <name>` installs *and auto-connects* in one shot — tools go live in the same session.
- **IA without an API key, first-run.** The welcome wizard offers, by default, to open Gemini in a browser and capture its **guest session** — no Google login, no API key, no credit card. From `pip install` to working IA in 30 seconds. Same flow works for Claude.ai / Kimi.com / Qwen / DeepSeek if you have those accounts.
- **`/lang` command.** 34 ISO codes + free-form descriptors. `/lang zh`, `/lang ja`, `/lang pt-br`, `/lang "speak as my gym tutor"`, `/lang "Yoda"`. The model role-plays the voice across the whole session.

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## What is this

Dulus is a lightweight Python reimplementation of Claude Code that isn't locked to Claude. Fork it, bend it, run it offline against Qwen on your own machine.

It reads your codebase, writes and edits files, runs shell commands, and adapts arbitrary Python repos into native tools on the fly:

```
/plugin install yfinance@https://github.com/ranaroussi/yfinance
/plugin reload

dulus get the prices of NVDA, TSLA, SP500
```

Be creative — adapt any Python repository as a plugin in seconds.

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

<a id="quick-start"></a>
## Quick Start

**Windows — no Python needed (1-click):**

Download the latest `Dulus-Free-x64.msi` from [Releases](https://github.com/KevRojo/Dulus/releases) → double-click and fly. Embedded Python, every library, and the desktop GUI bundled. No pip, no terminal, no admin. ~85 MB.

**Linux / macOS / WSL — one command (handles Python for you):**

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

The installer finds or **bootstraps Python 3.11+** (apt / deadsnakes / brew / uv), installs Dulus, and puts `dulus` on your PATH. Works on stock Ubuntu 20.04/22.04 where plain `pip install dulus` dies with `No matching distribution found` (pip hides packages that need a newer Python — Dulus needs ≥3.11).

**Already on Python 3.11+?** Then this is enough:

```bash
pip install dulus
dulus
```

**Windows (PowerShell, if you prefer the terminal over the MSI):**

```powershell
iwr -useb https://raw.githubusercontent.com/KevRojo/Dulus/main/install.ps1 | iex
```

First run opens a welcome wizard that can get you **working IA without an API key** — it captures a Gemini guest session from your browser (no login, no card). Or set any key you already have. Zero to flight in 30 seconds.

> 💡 Set `/sticky_input ON` on first run for the best experience.

**From source (hacking on Dulus itself):**

```bash
git clone https://github.com/KevRojo/Dulus && cd Dulus
pip install -e .
dulus
```

**Pick a model:**

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # or OPENAI_API_KEY, GEMINI_API_KEY, ...
dulus
```

**Zero API keys?**

```bash
# NVIDIA NIM — 14 free models, 40 RPM each, no card
dulus --model nvidia-web/deepseek-ai/deepseek-r1

# Fully offline via Ollama
ollama pull qwen2.5-coder
dulus --model ollama/qwen2.5-coder
```

Or pipe it like a good unix citizen:

```bash
echo "explain this diff" | git diff | dulus -p --accept-all
```

<a id="models"></a>
## Models

Speak every dialect — switch mid-session with `/model`:

| Kind | Providers |
|---|---|
| **Cloud** | Anthropic · OpenAI · Gemini · DeepSeek · Kimi · Qwen · Zhipu · MiniMax |
| **Free tier** | **14 frontier models via NVIDIA NIM** — 40 RPM each, $0. Key at [build.nvidia.com](https://build.nvidia.com) |
| **Gateway** | 100+ backends via LiteLLM — OpenRouter, Groq, Together, Bedrock, Vertex, xAI, Mistral... |
| **Web chats** | Use the chats you **already pay for**: Claude.ai, Gemini, Kimi.com, Qwen, DeepSeek — parsed as providers |
| **Local** | Ollama · LM Studio · any OpenAI-compatible endpoint. Runs offline, completely. |

```
/model                         # show current
/model gpt-4o                  # switch
/model kimi:moonshot-v1-32k    # colon syntax works too
```

### Free Tier — NVIDIA NIM

No credit card. No waiting list. Dulus ships a `nvidia-web` provider that talks to [NVIDIA NIM](https://build.nvidia.com) — 14 top-tier models at 40 requests/minute each, for free. When one model hits its ceiling, Dulus auto-falls to the next one in the chain.

```bash
export NVIDIA_API_KEY=nvapi-...
dulus --model nvidia-web/deepseek-r1
```

Override the fallback chain in `~/.dulus/nvidia-providers.json`. **Get your key:** [build.nvidia.com](https://build.nvidia.com) → sign up → 1000 free credits, ~90 seconds.

<a id="features"></a>
## Features

The full tour lives on [the website](https://dulus.ai/) — highlights:

| | |
|---|---|
| **27 built-in tools** | Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, NotebookEdit, GetDiagnostics, Memory, Tasks, Agents, Skills, and more |
| **MCP integration** | Any MCP server (stdio / SSE / HTTP). Tools auto-registered as `mcp__<server>__<tool>` |
| **Plugin system** | **Auto-Adapter** onboards any Python repo — zero manifest required. Hot-reload in-session |
| **Sub-agents** | Typed agents (coder / reviewer / researcher / tester) in isolated git worktrees, talking via message passing |
| **Voice input** | Offline STT via Whisper. No API key, no cloud. Wake words included |
| **Brainstorm** | Multi-persona AI debate — a council of ghosts |
| **SSJ Developer Mode** | Power menu: 10 workflow shortcuts behind one keystroke |
| **Telegram bridge** | Run Dulus from your phone. Slash commands, vision, voice, multi-user |
| **Checkpoints** | Auto-snapshot conversation + files. Rewind to any turn |
| **Plan mode** | Read-only analysis phase before touching anything |
| **Context compression** | Auto-compact long sessions. Keep the signal, drop the slop |
| **Persistent memory** | Dual-scope (user + project), ranked by confidence × recency. Open `~/.dulus/memory/` as an Obsidian vault |
| **Dulus OS** | Not a CLI — a workstation for the agent (sandbox desktop in your browser) |
| **Local OCR** | `/ocr`, `/img` with verbatim text extraction, zero vision tokens |

<a id="permissions"></a>
## Permissions

Pick your leash length — switch anytime with `/permissions [mode]`:

| Mode | Behavior |
|---|---|
| `auto` *(default)* | Safe tools run free; risky actions (writes, shell) ask first |
| `manual` | Prompt for every operation. Paranoid setting |
| `accept-all` | Never asks — YOLO. Also via `dulus --accept-all` |
| `plan` | Read-only. Only the plan file is writable |

Answering `a` at any prompt upgrades the session to accept-all.

<a id="mcp"></a>
## MCP

Drop a `.mcp.json` in your project root (or `~/.dulus/mcp.json` for user-wide) — every server registers instantly as `mcp__server__tool`. stdio, SSE, and HTTP transports.

```json
{
  "mcpServers": {
    "git":         { "type": "stdio", "command": "uvx", "args": ["mcp-server-git"] },
    "playwright":  { "type": "stdio", "command": "npx", "args": ["-y","@playwright/mcp"] }
  }
}
```

**Built-in MCP marketplace.** Browse **2000+ servers** (the official [modelcontextprotocol.io](https://registry.modelcontextprotocol.io) registry + the awesome-mcp list) and install any of them by name — no hunting for the launch command, no hand-editing JSON.

```
/mcp list [query]           # browse the 2000+ server catalog
/mcp search <query>         # search every source at once
/mcp install <name>         # install by name — auto-connects, tools go live
/mcp installed              # what's installed + live status
/mcp runtimes               # which runtimes you have (node/python/docker)
/mcp                        # list configured servers and their tools
/mcp add <name> <cmd>       # add a stdio server manually
/mcp reload                 # reconnect all
```

<a id="plugins"></a>
## Plugins

The **Auto-Adapter** onboards *any* Python repo as native tools — zero manifest, hot-reload, no restart:

```
/plugin install my-plugin@https://github.com/user/my-plugin
/plugin install art@gh                      # shorthand for github
/plugin                                     # list
/plugin enable / disable / update / uninstall
/plugin recommend                           # auto-detect useful plugins
```

Then just ask — *"dulus get the prices of NVDA, TSLA, SP500"*. Adapt-and-install runs in under a second, new tools register live. 800+ ready-made skills via Composio too.

## Sub-agents — the flock

Dulus can spawn typed agents that work in **isolated git worktrees** so they don't trip over each other. Ship a feature while a reviewer nitpicks the previous one; tester runs in parallel.

```
/agents                              # show active flock
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

Agents talk to each other via `SendMessage` and `CheckAgentResult`.

## Voice

```bash
pip install sounddevice faster-whisper numpy
```

Then `/voice` in the REPL. Offline. Supports `/voice lang zh` and `/voice device` for mic selection.

**Linux / WSL:** `sounddevice` needs the PortAudio C library, which isn't bundled with the wheel. If you see `PortAudio library not found`:

```bash
sudo apt install libportaudio2 portaudio19-dev libasound2-dev
pip install sounddevice --upgrade --force-reinstall
```

Note: `pip install portaudio` will always fail — there is no PyPI package by that name, only the apt one above.

## Telegram bridge

```
/telegram <bot_token> <chat_id>                  # single user
/telegram <bot_token> <id1>,<id2>,<id3>          # multi-user — same Dulus, multiple authorized chats
```

Auto-starts next launch. Supports slash commands, vision, and voice from your phone. Each authorized chat gets its own replies — Dulus tracks who sent each message and routes the response back.

## Memory

Persistent memories stored as markdown in two scopes:

| Scope | Path |
|---|---|
| User | `~/.dulus/memory/` |
| Project | `.dulus/memory/` |

Types: `user` · `feedback` · `project` · `reference`. Search is ranked by **confidence × recency**. Mark a memory gold to pin it.

```
/memory search jwt         # fuzzy ranked
/memory load 1,2,3         # inject multiple into context
/memory consolidate        # distill the session into long-term insights
/memory purge              # nuclear (keeps Soul)
```

## Checkpoints

Every agent turn can snapshot **conversation + files** into a checkpoint. Break something? `/checkpoint` and rewind.

```
/checkpoint                 # list
/checkpoint 042             # rewind to #042 (files + context restored)
/checkpoint clear           # reclaim disk
```

## Brainstorm

Spin up a **council of ghosts**. Dulus fabricates expert personas, has them argue, and hands you the distilled take.

```
/brainstorm "should we rewrite in rust"
> persona: Skeptical PM
> persona: Principal Engineer
> persona: Grumpy DBA
> persona: Hot-take Intern
```

Round 3 usually produces consensus. Round 5 produces a joint venture.

## SSJ Developer Mode

Ten workflow shortcuts behind one keystroke. Refactor → review → test → commit → ship, chained and unattended.

```
/ssj
╭─ SSJ ───────────────╮
│ 1  /plan            │
│ 2  /worker          │
│ 3  /review          │
│ 4  /commit          │
│ 5  /ship            │
╰─────────────────────╯
```

<a id="slash-commands"></a>
## Slash commands

`/` + Tab in the REPL shows everything. The highlights:

| | |
|---|---|
| `/model [name]` | show or switch model |
| `/config [k=v]` | read / write config |
| `/save` `/load` `/resume` | session management |
| `/memory [query]` | persistent memory |
| `/skills` `/agents` | list skills / active flock |
| `/voice` | voice input (offline Whisper) |
| `/image` `/img` | clipboard image → vision model |
| `/brainstorm [topic]` | council of ghosts |
| `/ssj` | power menu |
| `/telegram [token] [id]` | Telegram bridge |
| `/checkpoint [id]` | list / rewind checkpoints |
| `/plan [desc]` | enter / exit plan mode |
| `/compact [focus]` | manual context compression |
| `/mcp` `/plugin` | server + extension management |
| `/cost` | tokens and USD burned |
| `/cloudsave` | cloud sync via GitHub Gist |
| `/status` `/doctor` | version + install health |
| `/init` | drop a CLAUDE.md template |
| `/export` `/copy` | transcript tools |
| `/news` | what's new |
| `/help` | all of the above, nicely printed |

## Built-in tools

**Core** · Read · Write · Edit · Bash · Glob · Grep · WebFetch · WebSearch
**Notebook / diagnostics** · NotebookEdit · GetDiagnostics
**Memory** · MemorySave · MemoryDelete · MemorySearch · MemoryList
**Agents** · Agent · SendMessage · CheckAgentResult · ListAgentTasks · ListAgentTypes
**Tasks** · TaskCreate · TaskUpdate · TaskGet · TaskList
**Skills** · Skill · SkillList
**Other** · AskUserQuestion · SleepTimer · EnterPlanMode · ExitPlanMode

MCP tools auto-registered as `mcp__<server>__<tool>`.

## CLAUDE.md

Drop a `CLAUDE.md` at your project root. It gets auto-injected into the system prompt so Dulus remembers your stack, your conventions, and that one thing you hate.

## Project structure

```
dulus/
├── dulus.py             # entry · REPL · slash commands · SSJ · Telegram
├── agent.py             # agent loop · streaming · tool dispatch · compaction
├── providers.py         # multi-provider streaming
├── tools.py             # core tools + registry wiring
├── tool_registry.py     # tool plugin registry
├── compaction.py        # context compression
├── context.py           # system prompt builder
├── config.py            # config management
├── cloudsave.py         # GitHub Gist sync
├── multi_agent/         # sub-agent system
├── memory/               # persistent memory
├── skill/                # skill system
├── mcp/                  # MCP client
├── voice/                # voice input
├── checkpoint/           # checkpoint / rewind
├── plugin/                # plugin system
├── task/                  # task management
└── tests/                 # 263+ unit tests
```

> **Interactive dependency graph & API docs:** [`docs/api.html`](docs/api.html) — open it in a browser to explore the full module graph (D3.js, zoom/pan, clusters by package).

<a id="faq"></a>
## FAQ

**Tool calls fail on my local model.**
Use one that supports function calling: `qwen2.5-coder`, `llama3.3`, `mistral`, `phi4`. Avoid base models without tool-use training.

**How do I connect to a remote GPU box?**
```
/config custom_base_url=http://your-server:8000/v1
/model custom/your-model-name
```

**How do I check API cost?** `/cost`.

**Voice transcribes "kubectl" as "cubicle".**
Add domain terms to `.dulus/voice_keyterms.txt`, one per line. Whisper respects the hint.

**Can I pipe input?**
```bash
echo "explain this" | dulus -p --accept-all
git diff | dulus -p "write a commit message"
```

**Is this safe to point at prod?**
`--accept-all` isn't. `plan` mode is. Use your head.

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## 🔒 Privacy & anonymous telemetry (opt-in)

On first launch Dulus asks **once** if you'd like to share anonymous usage
statistics. **Nothing is sent unless you say yes.**

| Collected (if you opt in) | NEVER collected |
|---|---|
| Event names (`session_start`, `tool_used`, `model_selected`) | Prompts or responses |
| Dulus version, OS name, Python version | File contents or paths |
| Provider/model names (e.g. `gemini`) | API keys or tokens |
| A random anonymous ID generated on your machine | Emails, usernames, IPs (geo disabled) |

Data goes to [Mixpanel](https://mixpanel.com) (event analytics). The full
implementation is readable code in [`analytics.py`](analytics.py) — audit it yourself.

**Opt out anytime:**
```
/config telemetry=off        # inside Dulus
DULUS_TELEMETRY=0            # environment variable
```

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## 💛 Sponsors & Startup Programs

Dulus is proudly supported by these startup programs — powering our infrastructure, observability, and analytics:

<p align="center">
  <a href="https://www.datadoghq.com/partner/datadog-for-startups/"><img src="https://cdn.simpleicons.org/datadog" height="42" alt="Datadog" title="Datadog for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.cloudflare.com/forstartups/"><img src="https://cdn.simpleicons.org/cloudflare" height="42" alt="Cloudflare" title="Cloudflare for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://sentry.io/for/startups/"><img src="https://cdn.simpleicons.org/sentry" height="42" alt="Sentry" title="Sentry for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.anthropic.com/startups"><img src="https://cdn.simpleicons.org/anthropic" height="42" alt="Anthropic" title="Claude for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://aws.amazon.com/activate/"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/amazonwebservices/amazonwebservices-plain-wordmark.svg" height="42" alt="AWS" title="AWS Activate"></a>
</p>
<p align="center">
  <a href="https://www.mongodb.com/startups"><img src="https://cdn.simpleicons.org/mongodb" height="38" alt="MongoDB" title="MongoDB for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://mixpanel.com/startups/"><img src="https://cdn.simpleicons.org/mixpanel" height="38" alt="Mixpanel" title="Mixpanel for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://amplitude.com/startups"><img src="https://www.google.com/s2/favicons?domain=amplitude.com&sz=128" height="38" alt="Amplitude" title="Amplitude Startup Scholarship"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.digitalocean.com/hatch"><img src="https://cdn.simpleicons.org/digitalocean" height="38" alt="DigitalOcean" title="DigitalOcean Hatch"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.notion.com/startups"><img src="https://cdn.simpleicons.org/notion" height="38" alt="Notion" title="Notion for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.zendesk.com/campaign/startups/"><img src="https://cdn.simpleicons.org/zendesk" height="38" alt="Zendesk" title="Zendesk for Startups"></a>&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://deepgram.com/startups"><img src="https://www.google.com/s2/favicons?domain=deepgram.com&sz=128" height="38" alt="Deepgram" title="Deepgram Startup Program — powering Dulus's voice"></a>
</p>

## License

GPLv3. Fork it, modify it, redistribute it — but keep it open. Derivative works must stay under GPLv3. Just don't ship `--accept-all` as the default.

## Donations

If Dulus saved you tokens, time, or sanity — throw some sats:

```
BTC: 1JzatQDn9fMLnKTd3KYgztsLHC95bJEzSN
```

On x: [@KevRojo](https://x.com/KevRojo)

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

<p align="center">
  <sub>▲ Built by <a href="https://github.com/KevRojo">KevRojo</a> · Named after the bird, not the reusable rocket · 2026</sub>
</p>
