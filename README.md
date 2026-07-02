# ▲ DULUS
>
> `pip install dulus` → press Enter → working IA in 30 seconds. Try it.

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
