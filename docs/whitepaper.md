# $DULUS AI — Technical Whitepaper

**Contract Address (Solana):** `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`
**Network:** Solana
**Creator:** KevRojo ([@KevRojo](https://x.com/KevRojo))
**GitHub:** [github.com/KevRojo/Dulus](https://github.com/KevRojo/Dulus)
**PyPI:** [pypi.org/project/dulus](https://pypi.org/project/dulus)
**Version:** v3.2.0 — June 2026
**License:** GPLv3

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Vision & Philosophy](#2-vision--philosophy)
3. [Technical Architecture](#3-technical-architecture)
4. [MemPalace: Semantic Memory](#4-mempalace-semantic-memory)
5. [Multi-Agent System](#5-multi-agent-system)
6. [Security Model](#6-security-model)
7. [Tokenomics of $DULUS](#7-tokenomics-of-dulus)
8. [Technical Roadmap](#8-technical-roadmap)
9. [Comparative Analysis](#9-comparative-analysis)
10. [A Message to the Community](#10-a-message-to-the-community)
11. [References](#11-references)

---

## 1. Abstract

Dulus is an open-source, multi-provider autonomous AI agent harness built in ~31,000 lines of Python by a solo developer from Santo Domingo, Dominican Republic. It enables any developer to run frontier AI models — including Claude, GPT-4, Gemini, DeepSeek, Qwen, Kimi, and 100+ others via LiteLLM — from a single CLI, with zero API key required on first run.

The $DULUS AI token on Solana serves as the utility and governance layer for the Dulus ecosystem. The open-source REPL remains free forever; $DULUS unlocks the business tier.

**Key innovations:**
- Browser session harvesting (zero-API-key access)
- Auto-Adapter plugin system (any Python repo becomes a tool)
- MemPalace semantic memory (ChromaDB-based)
- The Flock sub-agent system (isolated git worktrees)
- Mesa Redonda multi-model debate

---

## 2. Vision & Philosophy

### The Problem with AI Today

AI agent frameworks have split into two broken categories:

1. **Closed ecosystems** — locked to one model, one cloud, one pricing tier
2. **Complex frameworks** — require extensive setup, configuration, and ML expertise

Neither serves the global developer community. The promise of "AI for everyone" remains unfulfilled.

### The Dulus Philosophy

**Dulus is not a chatbot. Dulus is your companion.**

| Principle | Meaning |
|---|---|
| **Universal access** | Any model, any provider, any language |
| **Zero friction** | 30 seconds from install to working AI |
| **Zero cost to start** | No API key, no credit card, no subscription |
| **Open forever** | GPLv3. The engine is free. The business is SaaS on top. |
| **Built different** | ~31K lines of readable Python. No build step. No gatekeeping. |
| **Community-owned** | $DULUS token aligns incentives between builders and users |

### The Bird

The Palmchat (*Dulus dominicus*) is the national bird of the Dominican Republic. It symbolizes:
- **Freedom** — flying without boundaries
- **Resilience** — thriving in any environment
- **Community** — nesting in colonies, flying together

This is the spirit of Dulus: an AI companion that is free, adaptable, and built for the flock.

---

## 3. Technical Architecture

### 3.1 System Overview

```
User Input
    |
    v
+----------------------------------+
| dulus.py (Entry Point)           |
| - REPL with prompt_toolkit       |
| - 30+ slash commands             |
| - Voice, Telegram, GUI           |
+----------------------------------+
    |
    v
+----------------------------------+
| agent.py (Core Loop)             |
| - Multi-turn conversation        |
| - Permission gating              |
| - Governance integration         |
| - Context compaction             |
+----------------------------------+
    |
    +------+------+------+------+
    |      |      |      |      |
    v      v      v      v      v
+------+ +------+ +------+ +------+ +---------+
|provid| |tool_ | |compac| |gover-| |multi_  |
|ers.py| |regist| |tion. | |nance | |agent/  |
|(4.5K)| |ry.py | |py    | |.py   | |(Flock) |
+------+ +------+ +------+ +------+ +---------+
    |      |
    v      v
+------+ +------+
|tools | |context|
|(2.9K)| |.py   |
+------+ +------+
              |
              v
    +---------+---------+
    |         |         |
    v         v         v
+------+  +------+  +------+
|memory|  |skill |  |plugin|
|(Mem- |  |/     |  |/Auto |
|Palace|  |      |  |Adapt)|
+------+  +------+  +------+
```

### 3.2 Key Design Decisions

**Flat module layout:** Every module is importable from the top level. No deep package hierarchies. This makes the codebase readable and forkable.

**Neutral message format:** All messages use a provider-independent schema:
```python
{"role": "user|assistant|tool", "content": "...", "tool_calls": [...]}
```
This enables seamless model switching mid-conversation.

**Generator-based streaming:** The agent loop yields events as they happen, enabling real-time UI updates and always-interruptible operation (Ctrl+C works even during API calls).

**Threading, not asyncio:** Synchronous generators via `concurrent.futures` keep the codebase simple and debuggable. No event loop complexity.

**Graceful degradation:** Every optional dependency (voice, MemPalace, Playwright) fails softly. The CLI always boots and chats.

### 3.3 Provider Architecture

Two streaming adapters cover all providers:

| Adapter | Providers | Lines |
|---|---|---|
| `stream_anthropic()` | Anthropic (native SDK) | ~800 |
| `stream_openai_compat()` | OpenAI, Gemini, Kimi, Qwen, Zhipu, DeepSeek, Ollama, LM Studio, Custom | ~2,000 |

**Provider resilience:** Exponential backoff with full jitter:
- Retry on: timeout, connection errors, 429, 5xx
- No retry on: 4xx client errors, auth failures
- Max 3 retries, max 30s delay

### 3.4 Tool System

The tool registry (`tool_registry.py`, ~215 lines) is the foundation of extensibility:

```python
@dataclass
class ToolDef:
    name: str               # unique identifier
    schema: dict            # JSON schema for LLM API
    func: Callable          # (params, config) -> str
    read_only: bool         # auto-approve in 'auto' mode
    concurrent_safe: bool   # safe for parallel agents
```

**30+ built-in tools** across categories:
- **File:** Read, Write, Edit, Glob, Grep
- **Shell:** Bash (with safety whitelist)
- **Web:** WebFetch, WebSearch, WebBridge (Playwright)
- **Memory:** MemorySave, MemoryDelete, MemorySearch, MemoryList
- **Agents:** Agent, SendMessage, CheckAgentResult
- **Tasks:** TaskCreate, TaskUpdate, TaskGet, TaskList
- **Skills:** Skill, SkillList
- **Voice:** VoiceRecord, VoiceSpeak
- **Other:** AskUserQuestion, SleepTimer, LaunchSandbox, ExtractTextFromImage

**MCP integration:** Any MCP server (stdio/SSE/HTTP) auto-registers tools as `mcp__<server>__<tool>`.

### 3.5 Context Management

Two-layer compression system (`compaction.py`, ~375 lines):

**Layer 1: Snip (rule-based)**
- Truncates old tool results
- Keeps first half + last quarter
- Zero API cost

**Layer 2: Auto-Compact (model-driven)**
- Calls current model to summarize old messages
- 70/30 old/recent split
- Replaces old messages with summary

**Trigger:** Context > 70% of model limit.

**Token estimation:** `len(content) / 3.5` (heuristic that works for most models).

---

## 4. MemPalace: Semantic Memory

### 4.1 Architecture

MemPalace gives Dulus long-term memory across sessions. Built on ChromaDB with sentence-transformer embeddings.

```
User Query
    |
    v
+-------------+     +-------------+     +-------------+
| Embedding   |---->| ChromaDB    |---->| Ranked      |
| (sentence   |     | (vector     |     | Results     |
| transformer)|     |  store)     |     | (confidence |
+-------------+     +-------------+     |  x recency) |
                                        +------+------+
                                               |
                                               v
                                        +-------------+
                                        | Injected    |
                                        | into System |
                                        | Prompt      |
                                        +-------------+
```

### 4.2 Storage Format

Markdown files with YAML frontmatter:

```markdown
---
name: user preferences
description: coding style preferences
type: feedback
created: 2026-04-02
---

User prefers 4-space indentation and type hints.
Never uses asyncio. Prefers FastAPI over Flask.
```

**Scopes:**
- **User:** `~/.dulus/memory/` — cross-project
- **Project:** `.dulus/memory/` — project-specific

**Types:** `user`, `feedback`, `project`, `reference`

### 4.3 Search Algorithm

Results ranked by: **confidence x recency**

Gold-starred memories are pinned to the top of results.

### 4.4 Soul File

The soul (`~/.dulus/memory/soul.md`) defines Dulus's personality:
- Name, tone, communication style
- Autonomy preferences
- Trust model
- Creator attribution (immutable)

The soul is editable by the user, making each Dulus unique.

---

## 5. Multi-Agent System

### 5.1 The Flock

Dulus can spawn typed sub-agents that work in **isolated git worktrees**:

```
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

### 5.2 Key Design Decisions

- **Fresh context** — Each sub-agent starts with empty history + task prompt
- **Depth limiting** — Max depth 3, checked at spawn time
- **Cooperative cancellation** — Flag-based, checked each loop iteration
- **Threading** — `ThreadPoolExecutor` for true parallelism

### 5.3 Agent Communication

Agents communicate via:
- `SendMessage` — Send a message to another agent
- `CheckAgentResult` — Poll for completion and get results

### 5.4 Mesa Redonda

Multi-model debate where multiple AI models work the same problem:

1. User poses a question
2. Dulus spawns agents with different models
3. Each agent analyzes from its model's perspective
4. Results are synthesized into a consensus answer

This mitigates model-specific biases and hallucinations.

---

## 6. Security Model

### 6.1 Permission System

| Mode | Behavior |
|---|---|
| `auto` | Reads always allowed. Prompts before writes/shell. |
| `accept-all` | No prompts (dangerous — CI/CD only) |
| `manual` | Prompt for every operation |
| `plan` | Read-only. Only plan file writable. |

### 6.2 Safe Execution

- Bash whitelist for auto-approved commands (`ls`, `cat`, `grep`)
- Dangerous commands always require explicit approval
- Config encryption (XOR + base64) for API keys
- Governance layer for budget and capability restrictions

### 6.3 Data Privacy

- All processing local (except API calls to chosen provider)
- No telemetry, analytics, or tracking
- MemPalace data stays on user's machine
- Open source — fully auditable

### 6.4 Sandbox

The experimental `sandbox/` directory contains Dulus OS — a browser-based mini-OS with 58 lazy-loaded apps for isolated tool execution.

---

## 7. Tokenomics of $DULUS

### 7.1 Token Overview

| Field | Value |
|---|---|
| **Network** | Solana |
| **Contract** | `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump` |
| **Standard** | SPL |
| **Locked** | 30,000,000 tokens |
| **Creator** | KevRojo (@KevRojo) |

### 7.2 Token Utility Roadmap

| Phase | Utility |
|---|---|
| **Now** | Community ownership. Creator-fee rewards locked on-chain. |
| **Business v1** | $DULUS holders get early access + discounted seats on Pro/Business tiers. |
| **Credits** | Pay for Dulus Business API credits with $DULUS. |
| **Deployments** | Spin up cloud Dulus instances, pay hosting with $DULUS. |
| **Subscriptions** | Monthly Dulus Pro subscription payable in $DULUS. |
| **Governance** | Top holders vote on feature priority and plugin marketplace policies. |

### 7.3 Economic Model

The token creates a virtuous cycle:

```
Free open-source REPL
    -> Developer adoption
    -> Community growth
    -> Demand for Pro/Business tiers
    -> $DULUS utility demand
    -> Creator incentivized to build
    -> Better product
    -> More adoption
```

### 7.4 Creator Commitment

- KevRojo is the creator — full transparency, public identity
- 30M tokens locked (verifiable on-chain)
- Top holder position acquired with personal funds
- **Not selling. Building.**

---

## 8. Technical Roadmap

### Q3 2026
- [ ] Dulus Pro cloud hosting (pay with $DULUS)
- [ ] Plugin marketplace with monetization
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Quality badges and coverage reporting
- [ ] Mobile app wrapper

### Q4 2026
- [ ] Dulus Business (multi-user, SSO, audit logs)
- [ ] Enterprise tier (on-premise, SLA)
- [ ] Plugin SDK + documentation
- [ ] Series A preparation

### 2027
- [ ] Distributed Flock (remote sub-agents)
- [ ] Model fine-tuning pipeline
- [ ] Enterprise marketplace
- [ ] $10M ARR target

---

## 9. Comparative Analysis

### vs Claude Code

| Dimension | Claude Code | Dulus |
|---|---|---|
| Models | Claude only | 100+ |
| API key | Required | Optional (browser harvest) |
| Code | ~100K+ lines, proprietary | ~31K lines, GPLv3 |
| Voice | No | Yes (offline) |
| Memory | Basic | Semantic (ChromaDB) |
| Sub-agents | No | Yes |
| Plugins | No | Auto-Adapter |
| Cost | $20+/mo | Free |

### vs AutoGPT

| Dimension | AutoGPT | Dulus |
|---|---|---|
| Setup | Hours (Docker, configs) | 30 seconds |
| Models | Limited | 100+ |
| Memory | File-based | Semantic |
| Voice | No | Yes |
| Code complexity | High | Low |

### vs Continue.dev

| Dimension | Continue.dev | Dulus |
|---|---|---|
| Type | IDE extension | Standalone agent |
| Interfaces | Editor sidebar | REPL / Web / GUI / Telegram |
| Sub-agents | No | Yes |
| Plugin system | Limited | Auto-Adapter |

---

## 10. A Message to the Community

I want to talk about the token. Honestly. No hype.

I didn't launch it to get rich. The community launched it first, and when I saw early believers exposed without the actual builder behind it, I stepped in. I bought my position using the contract's own creator rewards. 

Them i see people dont trust on that token so i launch my own.

**$DULUS has a real purpose.**

The open-source project isn't going anywhere. The REPL, the tools, the free model tier — that stays free forever. But Dulus is growing into a business layer: cloud-hosted instances, multi-user workspaces, model credits, managed deployments.

And that business layer is going to run on $DULUS.

The token will be how you pay for Pro subscriptions. How you buy inference credits. How you spin up a cloud instance without fiat friction. Holders with enough weight get automatic tier discounts. And eventually — the flock votes: top holders decide feature priority and plugin marketplace policies.

This isn't a promise. It's the architecture. That's how I've designed it.

So when someone asks "what's the token for" — the answer is: it's the fuel for Dulus's business layer. The more I build, the more it makes sense to hold.

We keep flying. 🦅🇩🇴

— KevRojo / [@KevRojo](https://x.com/KevRojo)

---

## 11. References

1. Dulus GitHub Repository: https://github.com/KevRojo/Dulus
2. PyPI Package: https://pypi.org/project/dulus
3. Dulus Website: https://dulus.ai/
4. $DULUS on DexScreener: https://dexscreener.com/solana/9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump
5. Creator X: https://x.com/KevRojo
6. ChromaDB: https://www.trychroma.com
7. LiteLLM: https://github.com/BerriAI/litellm
8. MCP Specification: https://modelcontextprotocol.io
9. Whisper (OpenAI): https://github.com/openai/whisper
10. Playwright: https://playwright.dev

---

*Dulus — Named after the bird, not the rocket.*
