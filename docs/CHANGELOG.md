# Changelog

All notable changes to Dulus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.10.22] - 2026-07-24

### Fixed
- `/mcp install` no longer writes servers that can't start. Catalog sources
  scraped from GitHub READMEs (e.g. "awesome" lists) often carry only a
  name/description/repo URL and no real launcher. Those sailed through and
  landed in `mcp.json` with an empty `command`, then blew up at connect time
  with "has no command configured". `install()` now rejects stdio entries with
  no command and sse/http entries with no URL up front, pointing you at the
  repo for manual setup. (MCP)
- Runtime check now validates the exact launcher, not a loose category. Several
  curated servers tagged `runtime="python"` actually boot via `uvx` (git,
  fetch, …). The old check passed if *any* of python/uv/uvx was present, so a
  box with `python` but no `uv` marked them "installed" and they failed later.
  `_check_runtime` now takes the entry's real command and checks that. (MCP)
- Case-insensitive server-name lookup in `get_server()` and `get_status()`, so
  `/mcp status Git` finds a server registered as `git`. (MCP)

## [3.10.21] - 2026-07-23

### Fixed
- Same crash via a second entry point: `compaction.py` created its checkpoint
  dir at import time with a hardcoded `~/.dulus` path (hit as soon as `agent.py`
  imported it). Now derives from the resolved `config.CONFIG_DIR` and tolerates
  a denied filesystem. (Sentry)
- Ollama backend `HTTP 500` propagated as an unhandled `HTTPError` and crashed
  the app. `stream_ollama` now retries transient 5xx/429 with backoff and fails
  soft with a friendly turn (REPL intact) if the backend stays down. (Sentry)

## [3.10.20] - 2026-07-23

### Fixed
- Startup crash `PermissionError [WinError 5]` on `~/.dulus`: `load_config()`
  called `CONFIG_DIR.mkdir()` unguarded, so on OEM/multi-user/service-account
  Windows boxes where `Path.home()` isn't writable the app died on boot.
  `CONFIG_DIR` now resolves to the first writable candidate — `$DULUS_CONFIG_DIR`
  → `~/.dulus` → `%LOCALAPPDATA%\dulus` (or `$XDG_DATA_HOME`) → temp dir — and
  all dir creation is wrapped to warn instead of raise. (Sentry)

## [3.10.10] - 2026-07-15

### Added
- Gold `short_memory` infrastructure: on every startup, `ensure_memory_palace()`
  guarantees `~/.dulus/memory/short_memory.md` exists with `gold: true`.
- Repo-shipped seed template at `memory/seeds/short_memory.md` (generic; no
  private project paths). Fresh machines stop showing `(empty)` on the 10-turn
  short-memory nudge.

### Fixed
- `short_memory` is locked gold: `save_memory` always forces gold + user scope;
  `delete_memory` / `MemoryDelete` refuse hard-delete and re-seal gold;
  `/memory permanent` and `/memory unbind` cannot strip the flag.
- Agent 10-turn short-memory load always re-seals gold before reading the file.

## [3.10.9] - 2026-07-15

### Fixed
- MemPalace auto-mine reliability on Windows and session exit: centralized
  `memory/mempalace_bridge.py` so MemorySave, consolidate, and `/exit`
  all schedule the real `mempalace mine` (package), not only local AI file mining.
- Windows child process was dying silently (`CREATE_NO_WINDOW` alone kept the
  mine in the parent console job). Detach with `DETACHED_PROCESS` +
  `CREATE_NEW_PROCESS_GROUP`; log to `$DULUS_HOME/logs/mempalace_mine.log`.
- Wait briefly for in-flight mines before `os._exit` so indexes are not dropped.
- User memory paths respect `DULUS_HOME` instead of hard-coding `~/.dulus`.

### Added
- Multi-language README documentation (EN, ES, FR, ZH, JA, KO, PT, RU, AR)
- Comprehensive architecture documentation
- API reference documentation
- Deployment guide
- Security policy
- Brand guidelines

## [3.9.5] - 2026-07-11

### Fixed
- TTS `c` cancel key not working while the REPL prompt was active:
  `msvcrt.kbhit()` only sees keystrokes when the raw console owns stdin, so
  prompt_toolkit swallowed the `c` before the watcher saw it. Added a second
  detection path via `GetAsyncKeyState` (physical key state, edge-detected)
  that fires regardless of who owns stdin, plus a 30ms sleep so the watcher
  no longer busy-spins a CPU core during playback.

## [3.9.4] - 2026-07-11

### Fixed
- Catastrophic config reset: `save_config()` wrote the caller's dict verbatim,
  so a thin dict (e.g. only `lang` + `user_name` at early startup) silently
  wiped every other key — API keys, voice config, everything. Now it merges
  DEFAULTS + on-disk config first (with `.bak` fallback if the on-disk copy
  is corrupt), then applies runtime changes on top.

## [3.9.3] - 2026-07-11

### Fixed
- `/lang` was silently overpowered by `soul.md` / gold memories that assert a
  voice ("I speak Dominican Spanish"). The chosen language is now re-asserted
  at the end of the system prompt (highest-authority position) and `/lang`
  injects an immediate directive into the live conversation so the switch
  takes effect the same turn. Defaults untouched — no `/lang` set means the
  soul keeps control.

## [3.9.2] - 2026-07-11

### Added
- `/update` self-update command: quiet cached (6h TTL) non-blocking PyPI check
  on startup, in-place upgrade, `now|check|status|on|off` subcommands.

## [3.9.0] - 2026-07-11

### Added
- MCP Marketplace: `/mcp list|search|install` over a live catalog of 2000+
  servers from registry.modelcontextprotocol.io + awesome-mcp, deduped,
  6h-TTL cached, offline-safe. One-shot install: resolve command, write
  config, connect, verify tools, hot-reload into the live session.

### Fixed
- Windows launcher for node-based MCP servers (`npx` ships as `npx.cmd`).

## [3.6.2] - 2026-07-04

### Fixed
- Opt-in telemetry never sent events: `MP_TOKEN` defaulted to empty string so
  `is_enabled()` was always False, even after user consent. The public
  project's write-only ingestion token now ships as the default
  (`DULUS_MP_TOKEN` env var still overrides).

### Added
- Named telemetry events (names/counts only — never content): `message_sent`,
  `tool_used`, `command_used`, `model_selected`, wired into the REPL loop,
  tool dispatch, slash commands and `/model`.
- Memory: session history search improvements — token matching, newest-first
  ordering, no truncation (from 786bd34).

## [3.2.0] - 2026-05-30

### Added
- `mempalace` integration as optional dependency for semantic memory
- `composio` bundled for 1,000+ SaaS integrations
- `beautifulsoup4` for HTML parsing in web scraping flows
- `sentry-sdk` for error tracking
- `pytesseract` for local OCR support
- Full 263+ test suite
- WebChat server with SSE streaming
- Desktop GUI (tkinter-based)

### Changed
- Flat module layout for readability
- Provider-agnostic neutral message format
- Improved context compaction with two-layer system

## [0.2.96] - 2026-05-28

### Added
- `/lang` command — 34 ISO language codes + free-form descriptors
- Local OCR as first-class feature (`/ocr`, `ExtractTextFromImage`)
- `kepano/obsidian-skills` bundled
- Sandbox OS embedded inside desktop GUI via pywebview

### Changed
- Welcome wizard defaults to Gemini guest (no login required)
- Slim wheel reduced from 11.4 MB to 2.5 MB
- LiteLLM gateway — one provider entry, 100+ backends

## [0.2.93] - 2026-05-25

### Added
- IA without API key on first-run via browser harvest
- CORS on daemon for Android Sandbox APK
- NVIDIA NIM free tier provider (14 models, 40 RPM)
- Auto-Adapter plugin system
- MCP server support (stdio / SSE / HTTP)

### Changed
- Improved provider resilience with exponential backoff
- Better error handling for tool execution failures

## [0.2.90] - 2026-05-20

### Added
- Mesa Redonda multi-model debate
- SSJ Developer Mode (10 workflow shortcuts)
- Sub-agent system (the Flock) with git worktrees
- Voice input/output (Whisper STT + multi-engine TTS)
- Telegram bridge with multi-user support
- Checkpoint/rewind system
- Brainstorm mode (council of ghosts)

### Changed
- Governance layer for budget and permission management
- Improved memory system with confidence x recency ranking

## [0.2.85] - 2026-05-15

### Added
- WebBridge browser automation via Playwright
- Docker multi-arch support (amd64, arm64)
- One-liner installer for Linux/macOS/WSL/Windows
- Daily session archives and cloud sync via GitHub Gist

### Changed
- tmux tools for agent-driven session management
- Plan mode for read-only analysis

## [0.2.80] - 2026-05-10

### Added
- Multi-provider support (Anthropic, OpenAI, Gemini, DeepSeek, Qwen, Kimi)
- 30+ built-in tools (Read, Write, Edit, Bash, Glob, Grep, WebFetch, etc.)
- Persistent memory system (user + project scope)
- CLAUDE.md auto-injection
- `/cost` command for token tracking
- Spinners for fun waiting UX

### Changed
- Initial public release on PyPI (May 5, 2026)
- GPLv3 license

## [0.2.60] - 2026-05-05

### Added
- Initial PyPI release
- Core agent loop with streaming
- Tool dispatch system
- Context compaction
- Plugin architecture

---

## Version History Legend

- **MAJOR** — Breaking changes to API or architecture
- **MINOR** — New features, backward-compatible
- **PATCH** — Bug fixes, performance improvements
