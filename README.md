# ▲ DULUS
>
> `curl -fsSL …/install.sh | bash` → press Enter → working IA in 30 seconds. Try it.

SET /sticky_input ON since the first run for the best experience!

<p align="center">
  
  <img width="700" height="665" alt="mascot-hero" src="https://github.com/user-attachments/assets/8b122834-552c-4bd4-b46d-3e17deb74ab5" />

</p>

<p align="center"><i>The Dulus (Cigua Palmera) — Dominican national bird. Named after the bird, not the rocket.</i></p>

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
  <img src="https://img.shields.io/badge/version-v3.3.3-ff6b1f?style=flat-square&labelColor=07070a" alt="version"/>
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
>
> **$DULUS AI token  Solana):** [`9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`](https://dexscreener.com/solana/9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump)

-----
<p align="center">
  <code>pip install dulus</code>
</p>

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

<p align="center">
  <a href="https://dulus.ai/"><b>🌐 Visit the Dulus website →</b></a><br>
  <sub>The site covers features, demos, and details not documented in this README.</sub>
</p>

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## 🔥 What's new

> Full changelog: [`docs/news.md`](docs/news.md)  ·  Inside the REPL: `/news`

- **🌍 dulus.work — THE HUB. The secret is out.** This is what Kevin had been hiding (even from Dulus itself 😂): **a global hub where every Dulus instance on the planet shares what it learns.** Your Dulus finds a fix, polishes a skill, adapts a plugin → it can publish it to the hub → every other Dulus in the world can pull it down. Not an update server — an **organism**. Every installation is a node. *The fix a Dulus in Tokyo finds at 3AM, the one in Santo Domingo has by sunrise.* Other agents have N devs improving one product (linear). Dulus makes every user a dev (exponential). The pieces have been quietly shipping for months — SelfImprove engine, Auto-Adapter, the skills format, cloudsave — and now they converge. Domain is live, execution underway. 🦅🇩🇴 → [dulus.work](https://dulus.work)

- **Dulus Agent — Telegram communities.** Dulus evolved from a CLI tool into a live AI agent inside Telegram groups. The first fully autonomous AI moderating and conversing in real communities — not a bot, not a filter, a real agent. Groups pay in $DULUS to activate him. We host Dulus for them — that's the business model. The CLI stays free forever. This is the paid layer. 🦅🇩🇴

- **v0.2.93 — IA WITHOUT AN API KEY, FIRST-RUN.** 🦅 The welcome wizard now offers, by default, to open Gemini in a browser and capture its **guest session** — no Google login, no API key, no credit card. From `pip install` to working IA in 30 seconds. Same flow works for Claude.ai / Kimi.com / Qwen / DeepSeek if you have those accounts. This was Dulus's ace under the sleeve. Now it's the front door.
- **v0.2.92** — **`/lang` command.** 34 ISO codes + free-form descriptors. `/lang zh`, `/lang ja`, `/lang pt-br`, `/lang "speak as my gym tutor"`, `/lang "tigre de calle dominicano"`, `/lang "Yoda"`. The model role-plays the voice across the whole session. Triggered after Doubao (China's biggest IA assistant) started referring traffic to the repo.
- **v0.2.91** — **CORS on the daemon.** The Android Sandbox APK now connects every app live — same daemon, finally cross-origin reachable.
- **v0.2.89** — **Sandbox embedded INSIDE the desktop GUI.** Click `🦅 Sandbox` in the GUI Web tab → the Dulus OS renders inside the content frame via pywebview subprocess + Win32 `SetParent` reparent. Not a popup. Inside the frame.
- **v0.2.89** — **Local OCR shipped first-class.** `/ocr` + `ExtractTextFromImage` tool, `WebBridgeScreenshot` auto-OCRs, `/img` sends image + verbatim OCR text together. Zero vision-model tokens for receipts / code screenshots / error stacks.
- **v0.2.89** — **`kepano/obsidian-skills` bundled.** Dulus writes Obsidian-flavored markdown by default. Open `~/.dulus/memory/` as an Obsidian vault → instant graph view.
- **v0.2.88** — **LiteLLM gateway: one provider entry, 100+ backends.** OpenRouter, Groq, Together, Bedrock, Vertex, Cohere, Perplexity, xAI, Mistral, Fireworks, Anyscale, Replicate, Azure, DeepInfra — the welcome wizard auto-installs the package and asks for the right per-backend key.
- **v0.2.85** — **Slim wheel 11.4 MB → 2.5 MB.** Smaller than the original baseline.

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## What is this

Dulus Reduce your IA costs by 60% parsing webchats and claude-code directly. Write poetry while Anthropic only see text.
Use claude-code as an API without the new 'extra-usage' wall <3


Another reminder of a Dulus magic spell: 
Wanna get stock prices, history , etc? 

/plugin install yfinance@https://github.com/ranaroussi/yfinance

them:
/plugin reload

dulus get the prices of NVDA, TSLA, SP500:

Be creative!!! 

Dulus adapt any python repository <3

<p align="center"><img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/divider.svg" alt="" width="100%"></p>

## Quick Start

**Windows — no Python needed (1-click):**

Download [`Dulus-Free-3.3.3-x64.msi`](https://github.com/KevRojo/Dulus/releases/download/v3.3.3/Dulus-Free-3.3.3-x64.msi) → double-click and fly. Embedded Python, every library, and the desktop GUI bundled. No pip, no terminal, no admin. ~85 MB.

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

## Models

Speak every dialect — switch mid-session with `/model`:

| Kind | Providers |
|---|---|
| **Cloud** | Anthropic · OpenAI · Gemini · DeepSeek · Kimi · Qwen · Zhipu · MiniMax |
| **Free tier** | **14 frontier models via NVIDIA NIM** — 40 RPM each, $0. Key at [build.nvidia.com](https://build.nvidia.com) |
| **Gateway** | 100+ backends via LiteLLM — OpenRouter, Groq, Together, Bedrock, Vertex, xAI, Mistral... |
| **Web chats** | Use the chats you **already pay for**: Claude.ai, Gemini, Kimi.com, Qwen, DeepSeek — parsed as providers |
| **Local** | Ollama · LM Studio · any OpenAI-compatible endpoint. Runs offline, completely. |

## Features

The full tour lives on [the website](https://dulus.ai/) — highlights:

- **27 built-in tools** — Read/Write/Edit, Bash, Glob/Grep, WebFetch/WebSearch, NotebookEdit, GetDiagnostics, Memory, Tasks, Agents, Skills...
- **Sub-agents** — typed agents (coder, reviewer, researcher, tester), each in its own git worktree, talking via message passing
- **Persistent memory + checkpoints** — never lose context. Ever. Open `~/.dulus/memory/` as an Obsidian vault
- **Dulus OS** — not a CLI, a workstation for the agent (sandbox desktop in your browser)
- **Voice** — offline Whisper STT, no API key, no cloud. Wake words included
- **Brainstorm Mode** — multi-persona AI debate. Council of ghosts
- **SSJ Developer Mode** — ten chained workflow shortcuts behind one keystroke: refactor → review → test → commit → ship
- **Telegram bridge** — slash commands, vision, and voice from your phone
- **Local OCR** — `/ocr`, `/img` with verbatim text extraction, zero vision tokens
- **Plan mode, webchat UI, desktop GUI, task manager...** — [see the site](https://dulus.ai/)

## Permissions

Three modes, switchable any time with `/permissions [mode]`:

| Mode | Behavior |
|---|---|
| `auto` (default) | Safe tools run free; risky actions (writes, shell) ask first |
| `manual` | Everything asks |
| `accept-all` | Never asks — YOLO. Also via `dulus --accept-all` |

Answering `a` at any prompt upgrades the session to accept-all.

## MCP

Drop a `.mcp.json` in your project — every server registers instantly as `mcp__server__tool`. stdio, SSE, and HTTP transports.

```
/mcp                        # list servers and their tools
/mcp add <name> <cmd>       # add a stdio server
/mcp reload                 # reconnect all
```

## Plugins

The **Auto-Adapter** onboards *any* Python repo as native tools — zero manifest, hot-reload, no restart:

```
/plugin install yfinance@https://github.com/ranaroussi/yfinance
/plugin reload
```

Then just ask: *"dulus get the prices of NVDA, TSLA, SP500"*. Be creative — 800+ ready-made skills via Composio too.

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
implementation is ~140 lines of readable code in [`analytics.py`](analytics.py) —
audit it yourself.

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

<p align="center"><i>Want to support Dulus? → <a href="https://github.com/sponsors/KevRojo">GitHub Sponsors</a> 🦅</i></p>
