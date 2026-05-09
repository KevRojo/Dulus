# ▲ DULUS

> **Hunt. Patch. Ship.** A Python autonomous agent that flies on any model — Claude, GPT, Gemini, DeepSeek, Qwen, Kimi, Zhipu, MiniMax, and local models via Ollama. ~12K lines of readable Python. No build step. No gatekeeping. Just talons.

SET /sticky_input ON since the first run for the best experience!

<p align="center">
  <img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/hero.svg" alt="Dulus" width="100%">
</p>

<p align="center">
  <a href="#quick-start"><b>Quick Start</b></a> ·
  <a href="#models"><b>Models</b></a> ·
  <a href="#features"><b>Features</b></a> ·
  <a href="#permissions"><b>Permissions</b></a> ·
  <a href="#mcp"><b>MCP</b></a> ·
  <a href="#plugins"><b>Plugins</b></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="pypi"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="downloads"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="python"/>
  <img src="https://img.shields.io/badge/license-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="license"/>
  <img src="https://img.shields.io/badge/version-v0.2.20-ff6b1f?style=flat-square&labelColor=07070a" alt="version"/>
  <img src="https://img.shields.io/badge/providers-11-ff6b1f?style=flat-square&labelColor=07070a" alt="providers"/>
  <img src="https://img.shields.io/badge/tools-27-ff6b1f?style=flat-square&labelColor=07070a" alt="tools"/>
  <img src="https://img.shields.io/badge/tests-263+-ff6b1f?style=flat-square&labelColor=07070a" alt="tests"/>
</p>

<p align="center">
  <code>pip install dulus</code>
</p>

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

<p align="center">
  <a href="https://kevrojo.github.io/Dulus/"><b>🌐 Visit the Dulus website →</b></a><br>
  <sub>The site covers features, demos, and details not documented in this README.</sub>
</p>

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## What is this
Talent cant be copied.

Dulus Reduce your IA costs by 60% parsing webchats and claude-code directly. Write poetry while Anthropic only see text.
Use claude-code as an API without the new 'extra-usage' wall <3

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/poetry-banner.png" alt="Anthropic only sees text while you and Claude are writing poetry" width="100%"></p>

<img width="1240" height="882" alt="image" src="https://github.com/user-attachments/assets/27dd76bc-8919-4bb9-b3c3-38ae7d92e482" />


<p align="center">
  <sub>⚡ <b>Saves you Claude tokens?</b> Throw a sat — BTC: <code>1JzatQDn9fMLnKTd3KYgztsLHC95bJEzSN</code></sub>
</p>

Dulus is a **lightweight Python reimplementation of Claude Code** that isn't locked to Claude. It ships the whole loop — REPL, tool dispatch, streaming, context compaction, checkpoints, sub-agents, voice, Telegram bridge, MCP, plugins — in roughly **12K lines you can actually read**. Fork it. Bend it. Run it offline against Qwen on your M2.

> **v0.2.17 — May 9, 2026** — Mega-release: Composio plugin bundled (1000+ apps, no MCP), `/skill list` interactive picker (awesome / composio / local), awesome skills live from GitHub (no Claude Code needed), lite mode finally functional, system prompt rewritten in English, `VERSION` auto-syncs from pyproject.
> **v0.2.16 — May 9, 2026** — MemPalace per-session dedup. No more re-injecting the same memory every turn — content-hash cache saves ~8K tokens in a 20-turn conversation. `/mem_palace reset` clears it on demand.
> **v0.2.15 — May 9, 2026** — Banner image hosted locally so PyPI renders it correctly.
> **v0.2.14 — May 9, 2026** — Multi-user Telegram bridge: `telegram_chat_ids: "123,456,,"` supported. Replies route to the user who sent each message.
> **v0.2.13 — May 8, 2026** — Internal robustness fixes for Ollama streaming.
> Type `/news` to see the full changelog.

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-quickstart.svg" alt="Quick Start" width="100%"></p>

## Quick Start

<img alt="image" src="https://github.com/user-attachments/assets/a5a447c6-2cce-42a5-87f8-7c3bc8367987" />


<img alt="image" src="https://github.com/user-attachments/assets/72526ae1-b69f-4529-adc7-eef1cd3876c8" />

<img alt="image" src="https://github.com/user-attachments/assets/6baf90e5-a163-4a38-bdde-3d77c0a87281" />

<img alt="image" src="https://github.com/user-attachments/assets/453c1aad-b777-4d9a-98b8-40edbadb5079" />

<img alt="image" src="https://github.com/user-attachments/assets/eb11cb86-2f53-4979-b7bf-5bd1f97ed5fc" />

<img alt="image" src="https://github.com/user-attachments/assets/986ae7b5-5400-48aa-80eb-cdfd7dbb706e" />


ROUND TABLE (DULUS UNIQUE FEATURE)

<img alt="image" src="https://github.com/user-attachments/assets/648ffe5e-28e2-49e0-bc27-362a585edd4f" />

<img alt="image" src="https://github.com/user-attachments/assets/9e8f17ed-6ca2-4ae0-b8c3-146ae5fef491" />

Dulus is the first one meeting multiple models at the same time working for the same objective and sharing their ideas.



### One-liner

```bash
pip install dulus && dulus              # core CLI — fast, no compile, works on termux
pip install "dulus[memory]" && dulus    # +MemPalace per-turn memory (pulls chromadb)
```

That's it. Dulus prompts you for a key on first run. The `[memory]` extra pulls in `mempalace` and its `chromadb` chain — skip it on Android/termux or anywhere wheels for `numpy`/`onnxruntime` aren't available; the CLI still boots and chats fine without it.

### From source (hacking on Dulus itself)

```bash
git clone https://github.com/KevRojo/Dulus && cd Dulus
pip install -e .          # editable install
dulus
```

### Termux / Android

The default install pulls `mempalace` and `sounddevice`, both of which need a NumPy that has no prebuilt wheel for `aarch64-android` — pip will try to build NumPy from source and fail. Install around it:

```bash
pkg install python python-numpy python-pillow build-essential
pip install --no-deps dulus
pip install anthropic openai httpx requests rich prompt_toolkit Flask bubblewrap-cli mempalace
```

Skip `sounddevice` (no usable PortAudio on Android — voice features won't work anyway). Dulus's runtime is graceful: voice / MemPalace just degrade if their deps aren't there, the CLI still boots and chats fine.

### Pick a model

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # or OPENAI_API_KEY, GEMINI_API_KEY, ...
dulus
```

**Zero API keys?** Two free paths:

```bash
# 1. NVIDIA NIM — 14 models free, 40 RPM each, no card
dulus --model nvidia-web/deepseek-ai/deepseek-r1

# 2. Fully offline via Ollama
ollama pull qwen2.5-coder
dulus --model ollama/qwen2.5-coder
```

Or pipe it like a good unix citizen:

```bash
echo "explain this diff" | git diff | dulus -p --accept-all
```

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/terminal-boot.svg" alt="Dulus booting into session" width="100%"></p>

<p align="center"><sub>↑ session boot. soul loaded, gold memory warm, shell sniffed. the little circles are real buttons on your Mac.</sub></p>

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-features.svg" alt="Features" width="100%"></p>

## Features

| | |
|---|---|
| **Multi-provider** | Anthropic · OpenAI · Gemini · Kimi · Qwen · Zhipu · DeepSeek · MiniMax · Ollama · LM Studio · custom OpenAI-compat endpoints |
| **27 built-in tools** | Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, NotebookEdit, GetDiagnostics, Memory, Tasks, Agents, Skills, and more |
| **MCP integration** | Any MCP server (stdio / SSE / HTTP). Tools auto-registered as `mcp__<server>__<tool>` |
| **Plugin system** | **Auto-Adapter** onboards any Python repo — zero manifest required. Hot-reload in-session. |
| **Sub-agents** | Typed agents (coder / reviewer / researcher / tester) in isolated git worktrees |
| **Voice input** | Offline STT via Whisper. No API key. No cloud. |
| **Brainstorm** | Multi-persona AI debate. Auto-generated expert roles. |
| **SSJ Developer Mode** | Power menu: 10 workflow shortcuts behind one keystroke |
| **Telegram bridge** | Run Dulus from your phone. Slash commands. Vision. Voice. Multi-user authorized list. |
| **Checkpoints** | Auto-snapshot conversation + files. Rewind to any turn. |
| **Plan mode** | Read-only analysis phase before touching anything |
| **Context compression** | Auto-compact long sessions. Keep the signal, drop the slop. |
| **tmux tools** | 11 tools for the agent to drive tmux sessions |
| **Persistent memory** | Dual-scope (user + project). Ranked by confidence × recency. |
| **Session management** | Autosave · daily archives · cloud sync via GitHub Gist |

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-models.svg" alt="Models" width="100%"></p>

## Models

### Cloud APIs

| Provider | Models | Env |
|---|---|---|
| **Anthropic** | `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `o3-mini`, `o1` | `OPENAI_API_KEY` |
| **Google** | `gemini-2.5-pro-preview-03-25`, `gemini-2.0-flash`, `gemini-1.5-pro` | `GEMINI_API_KEY` |
| **DeepSeek** | `deepseek-chat`, `deepseek-reasoner` | `DEEPSEEK_API_KEY` |
| **Qwen** | `qwen-max`, `qwen-plus`, `qwen-turbo`, `qwq-32b` | `DASHSCOPE_API_KEY` |
| **Kimi** | `moonshot-v1-8k/32k/128k`, `kimi-k2.5` | `MOONSHOT_API_KEY` |
| **Zhipu** | `glm-4-plus`, `glm-4`, `glm-4-flash` | `ZHIPU_API_KEY` |
| **MiniMax** | `MiniMax-Text-01`, `MiniMax-VL-01`, `abab6.5s-chat` | `MINIMAX_API_KEY` |

### Local

```bash
# Ollama (recommended: qwen2.5-coder, llama3.3, mistral, phi4)
dulus --model ollama/qwen2.5-coder

# LM Studio
dulus --model lmstudio/<model>

# Any OpenAI-compat server
export CUSTOM_BASE_URL=http://localhost:8000/v1
dulus --model custom/<model>
```

### Switching models mid-flight

```
/model                         # show current
/model gpt-4o                  # switch
/model kimi:moonshot-v1-32k    # colon syntax works too
```

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-freetier.svg" alt="Free Tier Providers" width="100%"></p>

## Free Tier Providers

No credit card. No waiting list. No "contact sales". Just frontier models, on tap.

Dulus ships a **`nvidia-web`** provider that talks to [NVIDIA NIM](https://build.nvidia.com) — NVIDIA's hosted inference API. Sign up, grab a key, and you've got **14 top-tier models** running at **40 requests per minute each**, for free. When one model hits its ceiling, Dulus auto-falls to the next one in the chain. Zero downtime. Zero config.

```bash
export NVIDIA_API_KEY=nvapi-...
dulus --model nvidia-web/deepseek-r1
```

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/nvidia-models.svg" alt="NVIDIA NIM free-tier models" width="100%"></p>

| Model | Type | ID |
|---|---|---|
| **DeepSeek R1** | Reasoning | `nvidia-web/deepseek-r1` |
| **DeepSeek V3** | Instruct | `nvidia-web/deepseek-v3` |
| **Kimi K2.5** | Long context | `nvidia-web/kimi-k2.5` |
| **GLM-4** | Zhipu AI | `nvidia-web/glm-4` |
| **MiniMax Text-01** | Text + Vision | `nvidia-web/minimax-text-01` |
| **Mistral Nemotron** | NVIDIA-tuned | `nvidia-web/mistral-nemotron` |
| **Mistral Large** | Instruct | `nvidia-web/mistral-large` |
| **Llama 3.3 70B** | Meta | `nvidia-web/llama-3.3-70b` |
| **Llama 3.1 405B** | Meta · flagship | `nvidia-web/llama-3.1-405b` |
| **Llama Nemotron** | NVIDIA reasoning | `nvidia-web/llama-nemotron` |
| **Qwen2.5 Coder** | Alibaba | `nvidia-web/qwen2.5-coder` |
| **Qwen3 235B A22B** | MoE · Alibaba | `nvidia-web/qwen3-235b-a22b` |
| **Phi-4** | Microsoft | `nvidia-web/phi-4` |
| **Gemma 3 27B** | Google | `nvidia-web/gemma-3-27b` |

**Automatic fallback.** Configure the chain in `~/.dulus/config.json`:

```json
{
  "nvidia_fallback_chain": [
    "deepseek-r1",
    "kimi-k2.5",
    "llama-3.3-70b",
    "mistral-nemotron",
    "phi-4"
  ]
}
```

Dulus cycles through the chain automatically when rate limits hit. The flock keeps flying.

> **Get your key:** [build.nvidia.com](https://build.nvidia.com) → sign up → 1000 free credits. Takes 90 seconds.

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-plugins.svg" alt="Plugins & MCP" width="100%"></p>

## Plugins

Dulus's **Auto-Adapter** reads a random Python repo and figures out its tools on its own — no `plugin.yaml` required.

```bash
/plugin install my-plugin@https://github.com/user/my-plugin
/plugin install art@gh                      # shorthand for github
/plugin                                     # list
/plugin enable / disable / update / uninstall
/plugin recommend                           # auto-detect useful plugins
```

Adapt-and-install runs in under a second. New tools register **live**, no restart.

## MCP

Drop a `.mcp.json` in your project root (or `~/.dulus/mcp.json` for user-wide):

```json
{
  "mcpServers": {
    "git":         { "type": "stdio", "command": "uvx", "args": ["mcp-server-git"] },
    "playwright":  { "type": "stdio", "command": "npx", "args": ["-y","@playwright/mcp"] }
  }
}
```

Manage in the REPL: `/mcp`, `/mcp reload`, `/mcp add <name> <cmd> [args]`, `/mcp remove <name>`.

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-agents.svg" alt="Sub-agents" width="100%"></p>

## Sub-agents — the flock

Dulus can spawn typed agents that work in **isolated git worktrees** so they don't trip over each other. Ship a feature while a reviewer nitpicks the previous one. Tester runs in parallel.

```
/agents                              # show active flock
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

Agents talk to each other via `SendMessage` and `CheckAgentResult`.

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/split-pane.svg" alt="Split-pane brainstorm" width="100%"></p>

<p align="center"><sub>↑ coder and reviewer working the same branch. The reviewer sent a list of nits. The coder is already fixing them.</sub></p>

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-perms.svg" alt="Permissions" width="100%"></p>

## Permissions

Pick your leash length:

| Mode | Behavior |
|---|---|
| `auto` *(default)* | Reads always allowed. Prompt before writes / shell. |
| `accept-all` | No prompts. Everything auto-approved. **YOLO.** |
| `manual` | Prompt for every operation. Paranoid setting. |
| `plan` | Read-only. Only the plan file is writable. |

Switch anytime: `/permissions auto` / `/permissions plan`.

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-bridges.svg" alt="Voice & Telegram" width="100%"></p>

## Voice

```bash
pip install sounddevice faster-whisper numpy
```

Then `/voice` in the REPL. Offline. Supports `/voice lang zh` and `/voice device` for mic selection.

## Telegram bridge

```
/telegram <bot_token> <chat_id>                  # single user
/telegram <bot_token> <id1>,<id2>,<id3>          # multi-user — same Dulus, multiple authorized chats
```

Auto-starts next launch. Supports slash commands, vision, and voice from your phone.
Multi-user mode (v0.2.14+): each authorized chat gets its own replies — Dulus tracks who
sent each message and routes the response back. Trailing commas are ignored, so
`717151713,787615162,,` works fine. Useful when you want to poke a long-running agent
from the bus, or share one Dulus instance with your team.

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-memory.svg" alt="Memory & Checkpoints" width="100%"></p>

## Memory

Persistent memories stored as markdown in two scopes:

| Scope | Path |
|---|---|
| User | `~/.dulus/memory/` |
| Project | `.dulus/memory/` |

Types: `user` · `feedback` · `project` · `reference`. Search is ranked by **confidence × recency**. Mark a memory gold to pin it.

```
/memory search jwt         # fuzzy ranked
/memory load 1,2,3          # inject multiple into context
/memory consolidate         # distill the session into long-term insights
/memory purge               # nuclear (keeps Soul)
```

## Checkpoints

Every agent turn can snapshot **conversation + files** into a checkpoint. Break something? `/checkpoint` and rewind.

```
/checkpoint                 # list
/checkpoint 042             # rewind to #042 (files + context restored)
/checkpoint clear           # reclaim disk
```

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-brainstorm.svg" alt="Brainstorm" width="100%"></p>

## Brainstorm

Spin up a **council of ghosts**. Dulus fabricates expert personas, has them argue, and hands you the distilled take.

```
/brainstorm "should we rewrite in rust"
> persona: Skeptical PM
> persona: Principal Engineer (2037 timeline)
> persona: Grumpy DBA
> persona: Hot-take Intern
```

Round 3 usually produces consensus. Round 5 produces a joint venture.

---

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/sec-ssj.svg" alt="SSJ Mode" width="100%"></p>

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

---

## Spinners

Because waiting should be fun.

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/spinners.svg" alt="Spinner messages" width="100%"></p>

<details>
<summary><b>all 24 spinners</b></summary>

```
⚡ Rewriting light speed...
🏁 Winning a race against light...
🤔 Who is Barry Allen?...
🤔 Who is KevRojo?...
🦅 Dropping from the stratosphere...
💨 Leaving electrons behind...
🌍 Orbiting the codebase...
⏱️ Breaking the sound barrier...
🔥 Faster than a hot reload...
🚀 Terminal velocity reached...
🦅 Sharpening talons on the AST...
🏎️ Shifting to 6th gear...
⚡ Speed force activated...
🌪️ Blitzing through the bytecode...
💫 Bending spacetime...
🦅 Preying on bugs from above...
👁️ Dulus vision engaged...
🍗 Hunting for memory leaks...
🪶 Shedding legacy code...
🕹️ Try-catching mid-flight...
🥚 Hatching a master plan...
⚡ I-I-I'm... I-I'm... I'm fast...
🔮 Looking at your code from the future...
☕ If I'm taking so long, don't worry, I'm just talking to your mom...
```

Drop your own in `dulus/spinners.py` and PR them. Bonus points for a reference we'll understand in 2046.
</details>

---

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
| `/worker [tasks]` | auto-implement a TODO list |
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

---

## Built-in tools

**Core** · Read · Write · Edit · Bash · Glob · Grep · WebFetch · WebSearch
**Notebook / diagnostics** · NotebookEdit · GetDiagnostics
**Memory** · MemorySave · MemoryDelete · MemorySearch · MemoryList
**Agents** · Agent · SendMessage · CheckAgentResult · ListAgentTasks · ListAgentTypes
**Tasks** · TaskCreate · TaskUpdate · TaskGet · TaskList
**Skills** · Skill · SkillList
**Other** · AskUserQuestion · SleepTimer · EnterPlanMode · ExitPlanMode

MCP tools auto-registered as `mcp__<server>__<tool>`.

---

## CLAUDE.md

Drop a `CLAUDE.md` at your project root. It gets auto-injected into the system prompt so Dulus remembers your stack, your conventions, and that one thing you hate.

---

## Project structure

```
dulus/
├── dulus.py             # entry · REPL · slash commands · SSJ · Telegram
├── agent.py              # agent loop · streaming · tool dispatch · compaction
├── providers.py          # multi-provider streaming
├── tools.py              # core tools + registry wiring
├── tool_registry.py      # tool plugin registry
├── compaction.py         # context compression
├── context.py            # system prompt builder
├── config.py             # config management
├── cloudsave.py          # GitHub Gist sync
├── multi_agent/          # sub-agent system
├── memory/               # persistent memory
├── skill/                # skill system
├── mcp/                  # MCP client
├── voice/                # voice input
├── checkpoint/           # checkpoint / rewind
├── plugin/               # plugin system
├── task/                 # task management
└── tests/                # 263+ unit tests
```

---

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

---

## License

GPLv3. Fork it, modify it, redistribute it — but keep it open. Derivative works must stay under GPLv3. Just don't ship `--accept-all` as the default.

---
## Donations

If Dulus saved you tokens, time, or sanity — throw some sats:

```
BTC: 1JzatQDn9fMLnKTd3KYgztsLHC95bJEzSN
```

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

<p align="center">
  <sub>▲ Built by <a href="https://github.com/KevRojo">KevRojo</a> · Named after the bird, not the reusable rocket · 2026</sub>
</p>
