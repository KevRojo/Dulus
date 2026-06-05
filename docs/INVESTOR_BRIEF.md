# DULUS AI — Investor Brief

> **The Open-Source AI Agent That Democratizes Access to Frontier AI.**
>
> Built by one person. Used by thousands. Flying toward a $1B+ market.

---

**Prepared by:** KevRojo, Founder & Solo Developer
**Contact:** [@KevRojo](https://x.com/KevRojo) | dev@dulus.ai
**Date:** June 2026
**Ask:** Seed / Pre-Series A

---

## Executive Summary

Dulus is an open-source, multi-provider autonomous AI agent that enables any developer to use frontier AI — Claude, GPT-4, Gemini, DeepSeek, Qwen, Kimi, and 100+ others — from a single Python CLI, with **zero API key required on first run**.

In 14 days since public launch, Dulus has achieved:
- **~19,000+ PyPI downloads**
- **2,000 GitHub clones** (747 unique cloners)
- **13,600+ X impressions** with 25-50% engagement on key posts
- Referral traffic from **Doubao** (China's largest AI assistant)

**The thesis:** AI agent frameworks today are either locked to one provider or require a PhD to set up. Dulus is the **Linux of AI agents** — open, universal, and accessible. The open-source engine is free forever. The business is SaaS on top.

**The moat:** ~31K lines of readable Python, 263+ tests, a passionate community, and a utility token ($DULUS) that aligns incentives between builders and users.

---

## The Problem

### AI Agents Today Suck

| Pain Point | Current State |
|---|---|
| **Provider lock-in** | Claude Code = Claude only. Cursor = OpenAI only. Switching costs are infinite. |
| **Setup complexity** | Install Docker, configure YAML, set up vector DBs, write manifests. Hours of pain. |
| **Cost barrier** | Every framework wants your credit card before you can type "hello". |
| **Code bloat** | Frameworks are 100K+ lines of TypeScript salad. Unreadable. Unforkable. |
| **Closed source** | You can't audit, modify, or self-host. You're renting, not owning. |

**The result:** Millions of developers are excluded from using AI agents. Small teams can't afford the overhead. Indie hackers give up. The promise of "AI for everyone" is broken.

---

## The Solution — Dulus

### One Command. Zero Friction. Any Model.

```bash
pip install dulus && dulus   # 30 seconds to working AI
```

### Key Differentiators

| Feature | Dulus | Claude Code | AutoGPT | Cursor |
|---|---|---|---|---|
| **Models** | 100+ | 1 | ~5 | ~5 |
| **API key to start** | No | Yes | Yes | Yes |
| **Setup time** | 30s | 30min+ | 2hr+ | 10min |
| **Lines of code** | ~31K | ~100K+ | ~50K+ | Closed |
| **License** | GPLv3 | Proprietary | MIT | Proprietary |
| **Voice (offline)** | Yes | No | No | No |
| **Semantic memory** | Yes | Basic | File | No |
| **Sub-agents** | Yes | No | No | No |
| **Auto-Adapter** | Yes | No | No | No |
| **MCP support** | Yes | No | No | No |

### The Auto-Adapter: Category-Defining Feature

Any Python repository becomes a Dulus tool with one command:

```bash
/plugin install yfinance@https://github.com/ranaroussi/yfinance
```

Dulus reads the repo, generates the adapter, and the tool is immediately available. **No manifest files. No custom code.** This is a category shift — not a feature.

### Browser Harvest: The "Secret Weapon"

Dulus opens your browser, captures your live session (Gemini guest, Claude.ai, Kimi, Qwen, DeepSeek), and drives it like an API. **No API key. No token billing. No rate limits beyond what the web UI gives you.** This is how Dulus achieves its "60% AI cost reduction" claim.

---

## Market Opportunity

### TAM / SAM / SOM

| Market | Size | Definition |
|---|---|---|
| **TAM** | $47B (2026) | Global AI agent framework market |
| **SAM** | $12B | Developer-focused AI agent tools |
| **SOM** | $500M | Python CLI + open-source AI agents |

### Growth Drivers

1. **AI model proliferation** — New models launch weekly. Developers need a universal harness.
2. **Cost pressure** — Enterprises are cutting AI spend. Free/open-source solutions win.
3. **Developer empowerment** — The trend toward self-hosted, auditable tools accelerates.
4. **Global demand** — Doubao (China's #1 AI) already refers traffic to Dulus. The need is international.

### Competitive Landscape

| Company | Stage | Funding | Weakness vs Dulus |
|---|---|---|---|
| **Anthropic (Claude Code)** | Public | $8.2B | Single provider, proprietary, $20+/mo |
| **Cursor** | Series A | $40M | Closed source, limited models |
| **Continue.dev** | Seed | $2M | IDE-only, no sub-agents |
| **AutoGPT** | Open source | $0 | Complex setup, limited providers |
| **Dulus** | **Pre-seed** | **Self-funded** | **Category winner** |

---

## Business Model

### Open Core + SaaS

| Tier | Price | Features |
|---|---|---|
| **Open Source (REPL)** | Free | Full agent, 30+ tools, all providers, voice, memory |
| **Dulus Pro** | $19/mo | Cloud-hosted instance, priority models, team features |
| **Dulus Business** | $49/user/mo | Multi-user workspaces, shared MemPalace, SSO, audit logs |
| **Dulus Enterprise** | Custom | On-premise, custom models, dedicated support, SLA |

### Revenue Projections (Conservative)

| Year | Users | Pro ($19/mo) | Business ($49/mo) | Revenue |
|---|---|---|---|---|
| Y1 | 10,000 | 500 | 50 | $144K |
| Y2 | 50,000 | 3,000 | 300 | $864K |
| Y3 | 200,000 | 10,000 | 1,000 | $2.9M |

### $DULUS Token Economics

The $DULUS token on Solana creates a virtuous cycle:

```
Developers use Dulus (free)
    -> Community grows
    -> $DULUS demand increases (utility for Pro/Business)
    -> Creator (KevRojo) is incentivized to keep building
    -> Product improves
    -> More developers use Dulus
```

**Token utility roadmap:**
- **Now:** Community ownership, creator rewards locked on-chain
- **Business v1:** Holders get early access + discounts
- **Credits:** Pay for API credits with $DULUS
- **Deployments:** Spin up cloud instances with $DULUS
- **Governance:** Top holders vote on feature priority

**Contract:** `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`
- 30M tokens locked (verifiable on-chain)
- Creator is top holder, bought with personal funds, not selling

---

## Technology & Moat

### Technical Architecture

- **~31,000 lines** of readable Python
- **263+ unit tests** with real coverage
- **Zero build step** — `pip install dulus` and it works
- **Flat module layout** — every module is readable and modifiable
- **Neutral message format** — provider-agnostic, future-proof
- **Generator-based streaming** — real-time, interruptible, Ctrl+C safe
- **Graceful degradation** — every optional feature fails softly

### Why This Is Defensible

1. **Community lock-in** — Developers who customize their Dulus (soul, skills, plugins) won't switch
2. **Auto-Adapter moat** — The plugin ecosystem creates network effects
3. **Multi-provider resilience** — Not dependent on any single AI company
4. **Speed of iteration** — 1 developer, no meetings, ships daily
5. **Open source gravity** — Best developers want to use and contribute to open tools

---

## Roadmap

### Shipped (May 2026)
- [x] Multi-provider harness (11 native + 100+ via LiteLLM)
- [x] Auto-Adapter for any Python repo
- [x] WebBridge (Playwright browser automation)
- [x] Voice I/O (Whisper STT + multi-engine TTS)
- [x] MemPalace semantic memory
- [x] Mesa Redonda multi-model debate
- [x] Sandbox OS (browser + Android APK)
- [x] Telegram community bridge
- [x] MCP server support
- [x] `/lang` — 34 languages
- [x] Local OCR
- [x] One-liner installer (Linux/macOS/WSL/Windows)
- [x] Docker multi-arch stack

### Q3 2026
- [ ] Dulus Pro cloud hosting (pay with $DULUS)
- [ ] Plugin marketplace with monetization
- [ ] CI/CD pipeline (GitHub Actions, auto-release)
- [ ] Quality badges (CI, coverage, downloads, security)
- [ ] Mobile app (iOS/Android wrapper)

### Q4 2026
- [ ] Dulus Business (multi-user workspaces, SSO)
- [ ] Enterprise tier (on-premise, SLA)
- [ ] Plugin SDK + documentation
- [ ] Community leaderboard
- [ ] Series A preparation

### 2027
- [ ] Distributed Flock (remote sub-agents)
- [ ] Model fine-tuning pipeline
- [ ] Enterprise marketplace
- [ ] $10M ARR target

---

## Traction

### Metrics (as of June 2026 — Day 30 public)

| Metric | Value |
|---|---|
| PyPI downloads | ~19,000+ |
| GitHub clones (30 days) | 2,000+ |
| Unique cloners | 747+ |
| X impressions (30 days) | 25,000+ |
| X engagement rate | 4% baseline, 25-50% on key posts |
| Telegram community | 200+ active members |
| Countries reached | 45+ (confirmed by PyPI geo) |
| Referral from Doubao | Confirmed traffic spike |

### Community Validation

> *"Dulus matches or exceeds many funded agent frameworks."*
> — @DoediLiem, independent Claude user, May 2026

> *"pip install dulus and I was chatting with Claude in 30 seconds. No API key. Mind blown."*
> — Community member, X post

> *"The Auto-Adapter is a category shift. I installed my entire Python toolkit as Dulus plugins in under a minute."*
> — Early adopter

---

## Team

| Role | Person | Background |
|---|---|---|
| **Founder / Lead Developer** | KevRojo ([@KevRojo](https://x.com/KevRojo)) | Solo builder from Santo Domingo, Dominican Republic. Built Dulus from 0 to 19K downloads in 30 days. Full-stack Python developer. |

**Hiring plan (funded):**
- **Backend Engineer** — Distributed systems, scaling the Flock
- **DevRel / Community** — Documentation, tutorials, events
- **Designer** — Brand, UI/UX for Pro/Business tiers

---

## The Ask

### Funding Request: Seed Round

| | |
|---|---|
| **Amount** | $500K - $1.5M |
| **Instrument** | SAFE or priced equity |
| **Use of funds** | Engineering (60%), cloud infrastructure (20%), community/DevRel (15%), legal/admin (5%) |
| **Runway** | 18 months |
| **Milestone** | Dulus Pro launch, 1,000 paying users, Series A ready |

### Why Invest Now

1. **Product-market fit signal** — 19K downloads in 30 days with zero marketing budget
2. **Technical moat** — Auto-Adapter + multi-provider + 31K lines of readable code
3. **Category timing** — AI agents are exploding; universal harnesses will win
4. **Founder velocity** — Solo dev shipped more in 30 days than most teams ship in a year
5. **Token alignment** — $DULUS creates a community-owned ecosystem with built-in demand

---

## Risk Factors

| Risk | Mitigation |
|---|---|
| **Solo developer risk** | Open-source license means community can fork and continue; hiring plan in place |
| **Provider API changes** | Multi-provider design means no single point of failure |
| **Competition from funded players** | Speed of iteration, community ownership, and open-source moat |
| **Token market volatility** | Token is utility, not core revenue; business model is SaaS |
| **Regulatory (crypto)** | Token utility designed to comply with regulations; legal review planned |

---

## Appendix

### Links

| Resource | URL |
|---|---|
| GitHub | https://github.com/KevRojo/Dulus |
| PyPI | https://pypi.org/project/dulus |
| Website | https://dulus.ai/ |
| X / Twitter | https://x.com/KevRojo |
| DexScreener | https://dexscreener.com/solana/9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump |

### Financial Summary

| Item | Amount |
|---|---|
| Current revenue | $0 (pre-monetization) |
| Burn rate | ~$500/month (infrastructure) |
| Runway (self-funded) | Indefinite (lifestyle business) |
| Target: Dulus Pro launch | Q3 2026 |
| Target: 1,000 paying users | Q4 2026 |
| Target: Series A | Q1 2027 |

---

> *Named after the bird, not the rocket. We keep flying.*
>
> **We are not building a chatbot. We are building the infrastructure that lets a billion people have an AI companion.**
