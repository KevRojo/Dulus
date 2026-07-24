# Dulus documentation

This directory is the technical library for Dulus. For the product overview,
installation paths, screenshots, and feature tour, start with the
[main README](../README.md) or the [interactive site](https://kevrojo.github.io/Dulus/).

## Start here

| I want to… | Read |
|---|---|
| Install Dulus and finish first-run setup | [Getting started](GETTING_STARTED.md) |
| Understand the runtime end to end | [Architecture](architecture.md) |
| Embed or extend Dulus from Python | [API guide](API.md) |
| Explore modules and dependencies visually | [Interactive dependency graph](api.html) |
| Build a plugin, provider, tool, or skill | [Contributing](CONTRIBUTING.md) |
| Deploy the web and desktop surfaces | [Deployment](DEPLOYMENT.md) |
| Review the security and permission model | [Security](SECURITY.md) |
| Diagnose a common problem | [FAQ](FAQ.md) |
| See what shipped | [Release journal](news.md) and [changelog](CHANGELOG.md) |
| Read the longer product thesis | [Dulus AI whitepaper](Dulus_AI_Whitepaper_%28v2.0%29.pdf) |

## Runtime map

```text
prompt
  │
  ▼
provider router ─── Anthropic · OpenAI · Gemini · NVIDIA · LiteLLM
  │                Ollama · LM Studio · browser-backed providers
  ▼
agent loop
  ├── context ───── project instructions · memory · skills · persona
  ├── tools ─────── core registry · MCP · plugins · Auto-Adapter
  ├── state ─────── sessions · tasks · checkpoints · jobs · costs
  └── surfaces ──── CLI · WebChat · desktop GUI · Telegram · Dulus OS
```

The shortest route through the implementation is:

1. [`dulus.py`](../dulus.py) — entry point, REPL, slash commands, and bridges.
2. [`agent.py`](../agent.py) — streaming tool-use loop.
3. [`providers.py`](../providers.py) — cloud, local, gateway, and browser routes.
4. [`tools.py`](../tools.py) — built-in tools and dispatch.
5. [`tool_registry.py`](../tool_registry.py) — unified registration and execution.
6. [`context.py`](../context.py) — system, project, memory, and skill context.

## Feature guides by subsystem

| Subsystem | Implementation |
|---|---|
| Persistent memory and background jobs | [`memory/`](../memory/) |
| Multi-agent worktrees and messaging | [`multi_agent/`](../multi_agent/) |
| MCP transports and marketplace | [`dulus_mcp/`](../dulus_mcp/) |
| Plugins and repository Auto-Adapter | [`plugin/`](../plugin/) |
| Reusable skills | [`skill/`](../skill/) |
| File and conversation checkpoints | [`checkpoint/`](../checkpoint/) |
| Durable task tracking | [`task/`](../task/) |
| Speech, TTS, and wake words | [`voice/`](../voice/) |
| Native desktop interface | [`gui/`](../gui/) |
| Local browser interface | [`webchat_ui/`](../webchat_ui/) |
| Dulus OS | [`sandbox/`](../sandbox/) |

## Development baseline

```bash
git clone https://github.com/KevRojo/Dulus
cd Dulus
python -m venv .venv
python -m pip install -e .
python -m pytest -q
```

Use a model that supports tool calling, then launch the editable install:

```bash
dulus
dulus --model ollama/qwen2.5-coder
dulus -p "explain this repository and identify the safest first contribution"
```

Before opening a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md), run the
focused tests for the files you touched, then run the complete suite.

## Versions and generated pages

- [`news.md`](news.md) is the narrative release journal surfaced by `/news`.
- [`CHANGELOG.md`](CHANGELOG.md) is the compact structured history.
- [`api.html`](api.html) is generated from the current Python source.
- [`index.html`](index.html) is the GitHub Pages product tour.

If a generated page disagrees with the source, the source is authoritative.
Please update both in the same change.

## Languages

The main documentation is available in:

[English](README_EN.md) ·
[Español](README_ES.md) ·
[Français](README_FR.md) ·
[中文](README_ZH.md) ·
[日本語](README_JA.md) ·
[한국어](README_KO.md) ·
[Português](README_PT.md) ·
[Русский](README_RU.md) ·
[العربية](README_AR.md)

---

Dulus is built in public under the [GPLv3](../LICENSE). Questions and bug
reports belong in [GitHub Issues](https://github.com/KevRojo/Dulus/issues).
