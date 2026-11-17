<p align="center">
  <img src="assets/bird.png" width="128" alt="The Dulus bird, a golden palmchat in flight">
</p>

<h1 align="center">Dulus</h1>

<p align="center">
  <b>One agent, made of many.</b><br>
  The open-source core behind the Dulus desktop app.
</p>

<p align="center">
  <a href="https://dulus.ai/download/"><b>Download the desktop app (Free)</b></a> ·
  <a href="https://dulus.ai/pricing/"><b>Plans &amp; 3× Fuel from $49</b></a> ·
  <a href="https://dulus.online/"><b>Dulus Online</b></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI version"></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="PyPI downloads"></a>
  <a href="https://github.com/KevRojo/Dulus/releases"><img src="https://img.shields.io/github/v/release/KevRojo/Dulus?style=flat-square&color=ff6b1f&labelColor=07070a" alt="Latest release"></a>
  <a href="https://github.com/KevRojo/Dulus/actions/workflows/ci.yml"><img src="https://github.com/KevRojo/Dulus/actions/workflows/ci.yml/badge.svg" alt="Quality checks"></a>
  <a href="https://github.com/KevRojo/Dulus/pkgs/container/dulus"><img src="https://img.shields.io/badge/docker-ghcr.io%2Fkevrojo%2Fdulus-ff6b1f?style=flat-square&labelColor=07070a&logo=docker" alt="Docker image"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-ff6b1f?style=flat-square&labelColor=07070a&logo=python" alt="Python 3.10+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="GPLv3 license"></a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/at-a-glance-dark.svg">
    <img src="assets/at-a-glance-light.svg" width="880" alt="7,402 automated tests, 99.7% passing · 1,527 commits in 140 days · 358 pull requests, every one merged by a human · 114 built-in tools · 26 Round Table seats">
  </picture>
</p>

---

## "That's it?"

If you installed Dulus from GitHub and thought *that's it?* — you met the core, not the app.

Dulus started as this: an open-source terminal agent — still free, still a fine place to hack. The **Dulus desktop app** is everything that grew on top of it, built on a private codebase and downloaded from [dulus.ai](https://dulus.ai/download/). This page is the public face of that app — what it does, how it's tested — while the open core below stays open.

> Dulus is an AI agent for your desktop and terminal. It works in your files, your shell, your browser and your screen — on any model you choose. And when one mind isn't enough, it calls the flock.

## One agent. Made of many.

### The Round Table
Seat up to **26 AI agents** — any mix of models — at one table with a shared task board. They split the work, call on each other by name, and bring you the decisions only you can make as cards with options and a recommended pick. Open the live view to watch the table work, drawn from real events, never invented — then take a photo or record it.

### Hands on your computer
Dulus sees the screen, clicks and types in any app, in any language — accents, ñ and emoji included. A small live overlay follows along over full-screen apps, so you can watch, approve or stop it with one click.

### Astral Voice
Talk to it. It starts answering out loud while it's still writing, lets you cut in, and keeps the whole conversation in a transcript beside the orb.

### Your phone, same conversation
Pair Telegram with a QR code and keep going from anywhere: text, voice notes, photos and files, live progress with a stop button, approvals as buttons.

### Memory that doesn't lie to you
Memories stay with the profile and project they came from. Stale facts get flagged instead of trusted, newer facts replace older ones, and old ones are archived, never silently deleted. Long conversations stay searchable even after they're compacted.

### Any model
**40+ provider integrations** — the major APIs, local runtimes, and Dulus's own hosted models — with one reasoning dial for all of them, context windows up to a million tokens where the provider offers them, and requests shaped to stay cached so long sessions cost less.

### Make things
Images and video with your own keys: FLUX.2, GPT Image, Gemini and Imagen, Meta Muse, Veo, Sora 2 and more. Drag a result back in as a reference and keep going. Documents and mini apps the agent builds land in a versioned **Artifacts** library.

<p align="center">
  <img src="assets/astral-images.png" width="880" alt="Dulus desktop app — Astral Images generating and iterating with reference images across Meta Muse and FLUX">
</p>

### Grows with you
A market of **~1,800 MCP servers** that install from inside the app, runtimes included. Skills. Plugins that reload live. And **AutoAdapter**: point it at a GitHub repo and get tools that are verified before they're switched on.

### And everything around it
A real browser pane, a live terminal panel, a steer bubble to talk to Dulus mid-task without stopping it, a Stop that really stops, checkpoints with undo and fork, HTML reports, a Tasks board, **Dulus OS** (the desktop in your browser), a desktop pet, **17 GUI themes** and **34 languages**.

## Measured. Not claimed.

Dulus is built by one developer, [Kevin Rojo](https://x.com/KevRojo), and a crew of AI coding agents. The agents write code and open pull requests. Kevin directs, decides and merges — **429 pull requests** and counting. Every agent reads a shared log before touching anything, and signs an entry when it's done: what it did, what's missing, what broke, and what it did **not** verify.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/tests-growth-dark.svg">
    <img src="assets/tests-growth-light.svg" width="880" alt="Test functions in the suite grew week by week from 882 on June 21, 2026 to 5,734 on November 8, 2026; 7,402 test cases are collected today.">
  </picture>
</p>

- **1,783.8M input tokens** processed Nov 1–15, 2026 — **91.9% served from cache** (cached tokens are free in Fuel).
- **7,402 automated tests.** The latest full run (Nov 8, 2026) passed 7,362; the 24 failures are known and tracked.
- **Every fix ships with a test that fails without it** — and we break each fix on purpose to prove a test catches it.
- **1,527+ commits in 140+ days.** About 80% of them pushed by AI agents, including Dulus working on itself.

## Two editions, one bird

| | **Dulus** — open source CLI | **Dulus desktop app** — the full product |
|---|---|---|
| **What it is** | The open-source terminal agent where it all started | The full product: desktop app, CLI, browser, voice & phone |
| **Get it** | This repo · `pip install dulus` | [dulus.ai/download](https://dulus.ai/download/) |
| **Source** | Open (GPLv3) | Private. The app shows the work, not the code |
| **Price** | Free | **Free app** on your own keys/local models — or **3× Fuel** plans from **$49/mo** |

Everything on this page lives in the desktop app.

## Free to fly. 3× Fuel when you want hosted power.

The desktop app and CLI are **100% free** with your own API keys or local models (Ollama, LM Studio, llama.cpp). When you want Dulus-hosted models (`dulus-a-9b` to `dulus-x-397b`), the OpenAI-compatible API, and **Dulus OS** in your browser without juggling keys, every plan pays you back **3× its price in Fuel** every month:

| Plan | You pay | You get in Fuel (3×) | What's included |
|---|---|---|---|
| **Free** | **$0** | Bring your own keys / local | Full desktop app + CLI, all built-in tools, Mesa Redonda, MemPalace, MCPs & plugins |
| **Operator** | **$49 / mo** | **$147 / mo in Fuel** | Everything in Free + all hosted models + API (`dulus_sk_live_…`) + Dulus OS |
| **Company** | **$99 / mo** | **$297 / mo in Fuel** | Everything in Operator + more than twice the monthly Fuel for heavier daily workloads |

- **Cached tokens are free** and **failed calls are refunded**.
- **Pay as you go:** Top up [Fuel](https://dulus.ai/fuel/) anytime with SOL or `$DULUS` on Solana (`1 Fuel = 1 $DULUS`), or keep **1,000,000 `$DULUS`** in your Fuel balance for **40 free messages/day** on the free models (held, never spent).
- 👉 **[Compare plans & get 3× Fuel](https://dulus.ai/pricing/)** · **[Manage account on Dulus Online](https://dulus.online/account/#plans)**

## Get it

**[Download Dulus](https://dulus.ai/download/)** — Windows 10/11 (64-bit, **v6.4.4** per-user installer with embedded Python, zero setup). macOS and Linux builds publish on the same page; until your OS card turns into an installer, the open-source CLI runs in any terminal via `pip install dulus` (macOS, Linux, WSL, Termux, Windows).

Sign in with a free Dulus account to unlock **Fuel**, **Dulus Online**, and **Dulus OS**. See [pricing](https://dulus.ai/pricing/).

## FAQ

### Is the desktop app open source?
No. Dulus, the open-source core you're looking at, is — and stays that way. The desktop app's source isn't published; this page shows what it does, how it's built and how it's tested.

### Why keep it private?
Because a lot of what's on this page exists nowhere else, and we'd rather show the work than hand over the blueprint.

### Where do the numbers come from?
The repository snapshot (7,402 tests, 1,527 commits) was measured on November 8, 2026; PR counts (429+) and provider cache telemetry (1,783.8M input tokens, 91.9% cached, Nov 1–15, 2026) come directly from the repo and live provider dashboard.

### Is $DULUS an investment?
No. $DULUS is a utility and community token used to pay for Fuel on Dulus. Nothing here is financial advice.

### Where do I report a bug?
[Open an issue](../../issues/new/choose) here, or write to hello@dulus.ai. Security reports go privately to security@dulus.ai.

## Built by one. Backed by many.

Made by Kevin Rojo, a solo developer in Santo Domingo, with a crew of AI agents. Supported by **15 startup programs**: **Datadog**, **Cloudflare**, **OVHcloud**, **AWS Activate**, **Microsoft for Startups**, **Google for Startups**, **DigitalOcean Hatch**, **Deepgram**, **Claude for Startups**, **Sentry**, **Mixpanel**, **Amplitude**, **PostHog**, **Notion** and **Zendesk** — see the full wall at [dulus.ai/sponsors](https://dulus.ai/sponsors/).

## Why a bird?

Dulus is named after the palmchat — the *cigua palmera*, national bird of the Dominican Republic. It lives on Hispaniola and nowhere else on Earth, and it's the only species in its family.

Palmchats live in flocks. Together they build one great nest of twigs, high in the royal palms, and inside it every pair keeps its own chamber with its own entrance. One roof, many rooms. Dulus is made the same way: one human, Kevin Rojo, sets the direction; a flock of agents does the work.

<p align="center"><sub>Named after the bird, not the rocket. Built in Santo Domingo 🇩🇴 · We keep flying.</sub></p>
