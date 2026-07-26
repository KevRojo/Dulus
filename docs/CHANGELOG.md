# Changelog

All notable changes to Dulus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.10.42] - 2026-07-26

### Added
- **FS Compass — `SmartTree` + `ResolvePath`: the agent stops getting lost in
  the OneDrive maze.** On Windows, OneDrive silently redirects Desktop /
  Documents / Downloads under paths like `C:\Users\you\OneDrive\Desktop`, and a
  model doing blind `dir`/`ls` hops burns 5–10 turns trying to find them. Two new
  read-only tools fix that. **`ResolvePath`** turns human-speak into a real
  absolute path in one call — `"onedrive desktop my-project"` → the actual
  folder — by reading the Windows registry's "User Shell Folders" key (the
  single source of truth for where OneDrive actually put things) and then
  fuzzy-walking the tree. **`SmartTree`** prints a clean, depth-limited directory
  map with those known folders pre-resolved and noise dirs (`node_modules`,
  `.git`, caches, `AppData`, `$RECYCLE.BIN`) pruned. Both are stdlib-only, safe
  to run concurrently, and degrade gracefully off Windows (XDG-ish fallbacks).
  Registration never blocks boot — if anything goes wrong loading it, Dulus
  starts anyway. Fewer wasted turns, fewer "I can't find your file." 🦅

### Fixed
- **`/wake calibrate` no longer freezes the REPL on macOS.** The mic calibration
  forced `samplerate=16000`; when the device's native rate is 44.1/48 kHz (every
  Mac), CoreAudio rejects the format — the `||PaMacCore (AUHAL)|| Error on line
  2523` — and leaves `stream.read()` blocking forever on the main thread, hanging
  the whole prompt. Now it opens at the device's **native samplerate**, runs all
  PortAudio (even `sd.query_devices()`, which also opens the AudioUnit) in a
  daemon thread with an **8-second hard timeout**, and reports a clear error
  (busy device / mic permission) instead of locking up. The cosmetic CoreAudio
  diagnostics PortAudio prints from C are also suppressed during capture.

## [3.10.40] - 2026-07-26

### Fixed
- **A malformed tool call no longer crashes the whole process.** The permission
  gate read `inputs['command']` (and `['file_path']`, `['notebook_path']`)
  directly, so if a `Bash`/`Write`/`NotebookEdit` call arrived without its
  "required" argument — a model omitting it, or an offloaded `--run-tool` job
  with bad params — the resulting `KeyError` propagated **unhandled** all the way
  to `main()` and killed Dulus (caught in the wild as `KeyError: 'command'` via
  the excepthook). Every arg is now read with `.get()`; a missing argument is
  reported gracefully by the tool instead of taking the process down.

## [3.10.39] - 2026-07-25

### Fixed
- **A finished background job no longer ruptures the REPL.** When an offloaded
  Tmux job (or a background sub-agent) completed, the job sentinel woke the agent
  by calling `run_query()` **from its own thread** — while the main thread was
  blocked in the prompt. That ran a whole turn *over* your live prompt,
  overwriting the input line and eating half-typed text, so a completed job felt
  like it hijacked the session. Background notifications are now injected as
  role `user` messages and delivered **only on the main thread**: the notice
  waits in the conversation like something you typed and is answered on your next
  turn, so it can never collide with the prompt or steal input. (No capability
  was removed — TmuxOffload still offloads any tool.)

## [3.10.38] - 2026-07-25

### Fixed
- **`pip install dulus` on Python 3.10 said "from versions: none".** Every wheel
  declared `requires-python = ">=3.11"`, so pip on a Python 3.10 box (Ubuntu
  22.04's default, and plenty of live machines) filtered out **all 267 releases**
  and reported none existed. The code actually runs fine on 3.10 — the only 3.11
  feature used is `tomllib`, and both call sites already fall back to `tomli`.
  Lowered the floor to `requires-python = ">=3.10"`, added the 3.10 classifier,
  and added `tomli>=2.0; python_version < "3.11"` so the TOML paths work on 3.10.
  (Combined with the 3.10.37 Metadata-2.2 fix, `pip install dulus` now works on
  fresh Ubuntu 22.04 **and** 24.04 out of the box.)

## [3.10.37] - 2026-07-25

### Fixed
- **`pip install dulus` failed on a fresh Ubuntu 24.04 (and any pip < 24.1) with
  "Could not find a version that satisfies the requirement dulus (from versions:
  none)".** Every recent wheel was built with `setuptools>=77`, which implements
  PEP 639 and stamps the package with **Metadata-Version 2.4**. pip 24.0 — what
  ships on Ubuntu 24.04 LTS and many current distros — cannot parse Metadata 2.4
  and **silently skips the distribution**, so pip saw zero installable versions.
  The build now pins `setuptools>=61,<77` and uses the legacy `license = {text=…}`
  form, which keeps Metadata-Version at **2.2** — readable by old pip. Verified:
  the 3.10.37 wheel reports `Metadata-Version: 2.2`. Nothing else changed; this
  is purely a packaging-metadata fix so the install works everywhere.

## [3.10.36] - 2026-07-25

### Added
- **ChatGPT Plus/Pro/Team as a provider — no API key.** New `chatgpt-oauth`
  provider: run `/login chatgpt` (Codex OAuth via auth.openai.com, or it reuses
  an existing `~/.codex/auth.json` from `codex login`), then `chatgpt/*` model ids
  — `chatgpt/gpt-5.4`, `chatgpt/gpt-5.1-codex`, `chatgpt/o4-mini`, … — stream from
  the ChatGPT backend (Responses API) billed against your ChatGPT subscription,
  not platform API credits. Aliases: `/login-chatgpt`, `/chatgpt-login`,
  `/login-codex`, `/codex-login`. Model ids `gpt-5.x` / `codex-*` route here ahead
  of the paid API; plain `gpt-4o`/`o3` still go to the OpenAI API as before.
- Prompt-cache accounting for the ChatGPT backend: sends a stable
  `prompt_cache_key` and reads `input_tokens_details.cached_tokens`, so cache
  hits are credited when the backend reports them. (Note: the ChatGPT/Codex
  subscription endpoint currently forces `store:false` and does not populate the
  prompt cache, so cached tokens read 0 there today — this is correct reporting +
  future-proofing, not a promise of caching on that path.)

## [3.10.35] - 2026-07-25

### Fixed
- **The Gemini harvest now works on a bare server, and never fails in silence.**
  With gemini-web the default, a fresh Ubuntu box couldn't connect: the harvester
  launched with `channel="chrome"`, which needs Google Chrome installed, and a
  server doesn't have it — so it died and the catch-all `except` swallowed the
  error, leaving "nothing happened" on screen. Two fixes: (1) if Google Chrome
  is missing, the harvester now installs it with `playwright install --with-deps
  chrome` and retries — **Chrome specifically**, because installing plain Chromium
  leaves out the system libraries (`libnss3`/`libatk`/`libgbm`/…) a bare box needs,
  while the google-chrome package pulls them in as dependencies. (2) The harvest
  no longer returns silently on failure — it prints the real error and the exact
  command to fix it. Also adds `--disable-dev-shm-usage` so containers with a
  small `/dev/shm` don't crash Chrome.

### Changed
- **The first-run wizard stops pitching a local-model download when you pick
  Gemini Web.** Choosing the free, self-connecting gemini-web no longer drops you
  into the Ollama/Qwen local-AI setup right afterward — that prompt only shows for
  provider choices that actually benefit from it.

## [3.10.34] - 2026-07-25

### Changed
- **Gemini Web is the free, zero-config default provider on a fresh install.**
  New installs now default to `gemini-web/gemini-latest`, and the welcome wizard
  lists it as the first option — FREE, no API key — and auto-connects it by
  running the harvester headless in the background: it opens Gemini, sends a
  priming message, and captures the session with no manual browser step. Set
  `DULUS_GEMINI_HEADLESS=0` to watch the window for a one-time Google sign-in if
  your region requires one. Every other provider is still one wizard choice away.

## [3.10.33] - 2026-07-25

### Fixed
- **gemini-web now saves the reply it actually gave you.** `stream_gemini_web`
  streamed the model's text to the screen but persisted the
  `[gemini-web: no response after retries]` placeholder as the assistant turn —
  so every gemini-web exchange was recorded in history as an error, poisoning
  multi-turn context. The parsed text is now captured into the saved
  `AssistantTurn`, matching what was streamed.
- **`/gemini_chats new` actually starts a new chat now.** Clearing the thread
  `pop()`-ed the conversation-id keys, but `save_config()` deliberately re-merges
  the on-disk file on top of defaults (to prevent config wipes), so a popped key
  silently resurrected its old value — the "new" chat kept talking to the old
  thread. Clearing now writes `""`, which persists and reads as "no thread".
- **A fresh Gemini chat answers on the first try instead of the third.** The
  harvester seeded the throwaway "DULUS" priming thread's ids into config, so the
  first two real requests came back empty (an anonymous Gemini thread rejects a
  continuation from a different payload) and burned a 2-retry cascade on every
  new conversation. The harvest now clears the thread; `stream_gemini_web`
  re-captures the real ids from the first successful response, so continuity is
  kept from message one onward.

## [3.10.32] - 2026-07-25

### Changed
- **The boot/welcome color-wave signature now shows YOUR name, not a hardcoded
  one.** The animated `◆ name ◆` under the banner was always "kevrojo". It now
  reads the name you gave in the first-run welcome wizard (`config["user_name"]`,
  already persisted there) and animates that instead, so every install greets
  its own owner. Falls back to "dulus" when the name was skipped or left as the
  generic default. Both entry points — the REPL boot banner and the welcome
  banner — are wired to the same saved name.

## [3.10.30] - 2026-07-25

### Added
- **Grok Build billing on the TUI toolbar.** When the active provider is Grok,
  the toolbar shows the remaining usage pulled from the Grok Build billing
  endpoints, so you can see what's left without leaving the terminal. Fetched on
  a daemon thread with a 12s timeout, so a slow or unreachable billing API never
  blocks the prompt.

### Fixed
- **Deepgram TTS no longer switches voices mid-answer on a network blip.** The
  retry added in 3.10.29 only lived in the pipeline producer, which means it
  only ever ran for replies long enough to split into 2+ chunks — the
  single-shot path most answers take had *no* retry at all, so one transient
  failure dropped the whole reply to a different TTS backend and Dulus re-spoke
  it in another voice. Both paths now share `_deepgram_fetch_retry()`
  (3 attempts, 0.4s incremental backoff, honours the stop event and re-raises
  once spent, so a genuine outage still falls back cleanly and quickly).
- Type-checker narrowing bug in `_parse_grok_billing_payloads()`: the billing
  `config` blob was fetched twice around its own `isinstance()` guard, which
  left it Optional and made all 28 downstream reads type errors. Bound to a
  local before the check.

## [3.10.29] - 2026-07-24

### Changed
- **Deepgram TTS starts speaking ~3x sooner on long replies.** `_say_deepgram()`
  used to `urlopen(...).read()` the *entire* MP3 before playing a single sound,
  and Deepgram's synthesis time scales with input length (measured: 11 chars =
  1.1s, 368 chars = 10.2s) — so the longer the answer, the longer the silence
  before Dulus spoke. It now splits the text on sentence boundaries and runs a
  producer/consumer pipeline: the first (deliberately short) chunk plays while
  the rest are still being synthesized, so time-to-first-sound stops depending
  on total length (measured first-sound 10.1s → 3.0s). Under two chunks it uses
  the original single-shot path, so short replies gain nothing to lose.

### Added
- `/tts stream on|off` — toggle the low-latency Deepgram pipeline (default ON),
  persisted in config. `DULUS_DEEPGRAM_TTS_STREAM=0` overrides it for a one-off
  A/B against the old single-shot path (env wins over config).

## [3.10.25] - 2026-07-24

### Fixed
- Repaired UTF-8 damage introduced in v3.10.24. Four `backend/` modules were
  rewritten by a tool that decoded them as cp1252 and re-encoded as UTF-8,
  double-encoding every non-ASCII character (`—` → `â€"`, `🦅` → `ðŸ¦…`,
  `español` → `espaÃ±ol`) and prepending a BOM. Nothing crashed — the mojibake
  is still valid UTF-8 — but Spanish strings and emoji rendered as garbage.
  The files are restored and the v3.10.24 fix reapplied without touching their
  encoding. Upgrade straight past v3.10.24.

## [3.10.24] - 2026-07-24

### Fixed
- **Dulus could not be imported at all from a read-only install.** Six modules
  created a directory inside `site-packages` at *import* time with an unguarded
  `mkdir` — `backend/plugins.py` (`plugins/`) and `backend/{context,marketplace,
  personas,tasks,mempalace_bridge}.py` (`data/`). Anywhere `site-packages` is
  not writable — a container running as a non-root user, a system-wide install,
  a locked-down profile — the first one raised `PermissionError` while `backend`
  was still loading and took the whole package down before it could print
  anything. Both locations now resolve through a new `backend.paths
  .resolve_writable_dir()`: the bundled directory first (so installs that ship
  plugins or data keep finding them), then `$DULUS_CONFIG_DIR` / `~/.dulus`,
  then temp — and never raise. Same wound as the `~/.dulus` crashes fixed in
  v3.10.20/21, in the remaining entry points.

## [3.10.23] - 2026-07-24

### Security
- **WebChat now authenticates once it leaves loopback.** The API can run shell
  (`/api/sandbox/exec`), read and write files and spend model tokens. That is
  harmless bound to `127.0.0.1`, where only you can reach it — but `/webchat
  lan on`, a container or any cloud host previously exposed all of it with no
  credential at all. A `before_request` gate now covers every endpoint:
  - `DULUS_WEBCHAT_TOKEN` sets the secret; when unset one is generated and
    printed once at startup.
  - `DULUS_WEBCHAT_AUTH` — `auto` (default: on only once the bind leaves
    loopback), `always`, or `off`.
  - Clients may present it as `X-Dulus-Token`, `Authorization: Bearer <tok>`
    or `?token=`.
  - `/api/health` and the static UI stay reachable so health probes and page
    loads still work; every functional call behind them is gated.
  - Loopback runs are unchanged — no token required — but a cross-site browser
    request is now refused (`403`), closing a CSRF path to the local agent.
  Because the gate is a `before_request` hook rather than per-route opt-in,
  endpoints added later are protected by default.

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
