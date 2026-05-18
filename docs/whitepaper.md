# $DULUS AI — Whitepaper

**Contract Address (Solana):** `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`  
**Network:** Solana  
**Creator:** KevRojo ([@KevRojox](https://x.com/KevRojox))  
**GitHub:** [github.com/KevRojo/Dulus](https://github.com/KevRojo/Dulus)  
**PyPI:** [pypi.org/project/dulus](https://pypi.org/project/dulus)  
**Version:** v0.2.96 — May 2026

---

## 1. Abstract

Dulus is an open-source, multi-provider autonomous AI agent harness built by a solo developer from Santo Domingo, Dominican Republic. It enables any developer to run frontier AI models — including Claude, GPT-4, Gemini, DeepSeek, Qwen, Kimi, and 100+ others via LiteLLM — from a single Python CLI, with zero API key required on first run.

The $DULUS AI token on Solana is the community and ecosystem token for the Dulus project. It is backed by a real, actively maintained, and publicly auditable open-source codebase — not a concept or a promise.

---

## 2. The Problem

AI agent frameworks today fall into two categories:

1. **Locked ecosystems** — tied to one model, one cloud, one pricing tier. If the provider raises prices or changes terms, users are stuck.
2. **Complex frameworks** — require extensive setup, configuration, and deep ML knowledge. Inaccessible to most developers.

Additionally, integrating any new Python tool, library, or repository into an AI agent traditionally requires writing custom adapters, manifests, and glue code. This is slow, error-prone, and creates friction.

---

## 3. The Solution — Dulus

Dulus eliminates all of that friction.

### 3.1 Zero Lock-in, Zero API Key

`pip install dulus` → working AI in 30 seconds. On first run, Dulus offers to open a browser and capture a live Gemini guest session — no login, no API key, no credit card. The same flow works for Claude.ai, Kimi, Qwen, and DeepSeek.

For users who want API access: 100+ providers via LiteLLM (OpenRouter, Groq, Together, Bedrock, Vertex, Mistral, xAI, Fireworks, Azure, and more). Local models via Ollama. NVIDIA NIM free tier (14 models, 40 RPM, no card required).

### 3.2 Auto-Adapter — The Killer Feature

Any Python repository becomes a live Dulus tool with a single command:

```bash
/plugin install yfinance@https://github.com/ranaroussi/yfinance
/plugin install sherlock@https://github.com/sherlock-project/sherlock
```

Dulus reads the repository, generates the adapter, and the tool is immediately available to the agent. No manifest files. No custom code. This is a category shift — not a feature.

### 3.3 Core Capabilities

| Capability | Details |
|---|---|
| **Providers** | 11 native + 100+ via LiteLLM |
| **Tools** | 30+ built-in (file, shell, web, browser, memory, voice, OCR, finance, OSINT) |
| **Browser automation** | WebBridge via Playwright — navigate, click, evaluate JS, screenshot |
| **Voice** | Whisper STT (offline) + ElevenLabs/local TTS |
| **Memory** | MemPalace semantic memory (ChromaDB), hall/wing organization |
| **Sub-agents** | Isolated git worktrees, true parallelism |
| **Mesa Redonda** | Multi-model debate — multiple models working the same problem simultaneously |
| **Sandbox OS** | Full browser-based OS with 58 lazy-loaded apps, Android APK available |
| **Telegram bridge** | Multi-user, community bot, approval queue |
| **MCP** | Model Context Protocol server support |
| **Languages** | `/lang` command, 34 ISO codes + free-form descriptors |
| **Daemon mode** | Background process with WebChat UI + IPC bus |
| **Composio** | 1,000+ SaaS integrations |

### 3.4 Codebase

~12,000 lines of readable Python. No build step. No gatekeeping. GPLv3 licensed. Fork it, bend it, run it offline.

External validation (independent Claude user, @DoediLiem on X, May 2026):
> *"matches or exceeds many funded agent frameworks."*

---

## 4. Traction (as of May 2026 — Day 14 public)

| Metric | Value |
|---|---|
| PyPI launch | May 5, 2026 |
| PyPI downloads | ~19,000+ |
| GitHub clones (14 days) | 2,000 |
| Unique cloners | 747 |
| X impressions (7 days) | 13,600+ |
| X engagement rate | 4% baseline, 25–50% on key posts |
| Telegram community | Active, growing |
| AI model migrations to Dulus | Confirmed by community reports |

Doubao (China's largest AI assistant) began referring traffic to the repository — triggering the `/lang` multilingual feature that now ships by default.

---

## 5. The $DULUS AI Token

### 5.1 Origin

The $DULUS AI token was created by the project's creator, KevRojo, to establish an official, builder-backed community token on Solana. Before the official token existed, a community member launched an unofficial $DULUS token — with good intentions, but confidence was shaky and early believers were at risk. KevRojo launched the official token to protect the community and align incentives with the actual builder.

### 5.2 Creator Commitment

- **KevRojo is the creator.** Full transparency — public GitHub, real identity, public X handle.
- **30 million tokens locked.** Verifiable on-chain.
- **Top holder position** acquired with personal funds. Not extracted — invested.
- **Not selling.** Building.

### 5.3 Token Details

| Field | Value |
|---|---|
| **Network** | Solana |
| **Contract Address** | `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump` |
| **Platform** | pump.fun / DexScreener |
| **Locked tokens** | 30,000,000 |
| **Creator** | KevRojo (@KevRojox) |
| **DexScreener** | [View chart](https://dexscreener.com/solana/9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump) |

### 5.4 Token Utility (Roadmap)

The $DULUS AI token is positioned to become the access and governance layer for the Dulus ecosystem:

- **Business version access** — priority access and discounts for token holders
- **Community governance** — voting on roadmap priorities
- **Plugin marketplace** — token-gated premium plugins and tools
- **Builder rewards** — contributors to the open-source repo rewarded in $DULUS
- **Team workspace access** — multi-user business tier unlocked via token holdings

---

## 6. Roadmap

### ✅ Shipped (May 2026)
- Multi-provider harness (11 native + 100+ via LiteLLM)
- Auto-adapter for any Python repository
- WebBridge (Playwright browser automation)
- Voice in/out (Whisper + ElevenLabs)
- MemPalace semantic memory
- Mesa Redonda multi-model debate
- Sandbox OS (browser + Android APK)
- Telegram community bridge
- One-liner installer (Linux/macOS/WSL/Windows)
- Docker multi-arch stack
- MCP server support
- LiteLLM gateway (100+ backends)
- Local OCR first-class
- `/lang` — 34 languages

### 🟡 In Progress
- Docs site (mkdocs-material, gh-pages)
- CI/CD pipeline (GitHub Actions, auto-release on tag)
- Android APK polish (full immersive, safe-area dock)

### 🟢 Upcoming
- **Business version v1** — multi-user team workspaces, shared MemPalace, cloud-hosted instances
- Plugin marketplace with monetization
- Enterprise SSO + audit logs
- CHANGELOG automation, CONTRIBUTING.md, issue/PR templates
- Quality badges (CI, coverage, downloads, security)

---

## 7. Team

| Role | Person |
|---|---|
| **Founder / Solo Developer** | KevRojo ([@KevRojox](https://x.com/KevRojox)) |
| **GitHub** | [github.com/KevRojo](https://github.com/KevRojo) |
| **Location** | Santo Domingo, Dominican Republic 🇩🇴 |
| **Contributors** | Open-source — PRs welcome |

Dulus is currently a 1-person project. The roadmap includes expanding to a small team (2–3 contributors) by Month 6.

---

## 8. Risk Factors

- **Solo developer risk** — currently one primary contributor; mitigated by open-source license and public codebase
- **Crypto market risk** — token price subject to general Solana/crypto market conditions
- **Regulatory risk** — crypto regulation evolving globally; token utility may be adjusted to comply
- **Technology risk** — AI model providers may change APIs or terms; Dulus's multi-provider design is the primary mitigation

---

## 9. Legal Disclaimer

$DULUS AI is a utility and community token. This whitepaper is for informational purposes only and does not constitute financial or investment advice. Cryptocurrency investments carry significant risk. Do your own research (DYOR). Past performance is not indicative of future results.

The Dulus open-source project (github.com/KevRojo/Dulus) is licensed under GPLv3 and will remain free and open-source regardless of token performance.

---

## 10. Links

| Resource | URL |
|---|---|
| GitHub | https://github.com/KevRojo/Dulus |
| PyPI | https://pypi.org/project/dulus |
| Website | https://kevrojo.github.io/Dulus |
| DexScreener | https://dexscreener.com/solana/9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump |
| X / Twitter | https://x.com/KevRojox |
| Contract | `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump` |

---

*Dulus — Named after the bird, not the rocket. 🦅🇩🇴*
