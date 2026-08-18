# Changelog

All notable changes to Dulus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.11.1] - 2026-08-18

### Fixed
- **Kimi Code works again after its host move.** Kimi Code migrated its coding
  endpoint from `api.kimi.com/coding` to `api.kimi.ai/coding`. Dulus only knew
  the old host, so calls to the new one went out without the required KimiCLI
  user-agent and were rejected with 403. Both hosts are now recognised, so the
  user-agent is always sent and `kimi-code` / `/login kimi` models connect again.

## [3.11.0] - 2026-08-17

### Fixed
- **Profiles now actually isolate.** A profile has always had its own
  `plugins/`, `skills/` and `memory/` directories, but almost nothing read
  them: plugins resolved to the shared base, skills always searched the base,
  and every profile wrote its memories into the same place. Switching profiles
  also only ever *added* tools — the outgoing profile's tools stayed in the
  registry, so plugins appeared in the listing that could not be used from the
  active context. Each of these is now scoped to the active profile.
- **Two plugins with the same name no longer share one module.** Cached module
  names were keyed on the plugin name alone, so a plugin installed both in the
  base and in a profile resolved to whichever copy was imported first — for the
  rest of the process. Cache keys now include the install directory.
- **Uninstalling an inherited plugin from inside a profile is refused.** The
  install directory is shared, so the removal silently uninstalled the plugin
  for every other profile. Enabling or disabling one now writes to the config
  that owns it instead of forking a phantom entry into the active profile.
- **A workspace's own plugins are loaded, not just listed.** Project-scoped
  plugins are resolved relative to the working directory, which Dulus enters
  *after* the tool registry is built, so they were advertised but never
  imported. They are now rebound on every directory change.
- Plugin directories are added to `sys.path` only while a plugin module is
  executing, instead of lingering and shadowing other plugins' imports.
- Plugin tools were being registered twice on every startup.

### Changed
- A named profile is **lean** by default: it sees its own plugins and skills
  plus the bundled ones, and reads only its own memory. Run
  `/profile inherit <name> on` for a profile that also sees everything in your
  base `~/.dulus`. The `default` profile is unchanged — it *is* the base.

## [3.10.79] - 2026-08-17

### Fixed
- **Web-login harvest no longer hits an "unsupported browser" page.** The
  harvest browser overrode its user-agent with a hardcoded, years-out-of-date
  Chrome/123 string, so sites like Gemini and Qwen rejected it and never let
  the session be captured. It now lets real Chrome report its own current
  user-agent.

## [3.10.76] - 2026-08-13

### Changed
- **Quick menu now opens on double-tap `↓↓` instead of `←←`.** The left-arrow
  trigger claimed the exact key you press to move the cursor back and fix a
  word — so editing a typo could summon the whole menu. It's bound to the Down
  arrow now (a single `↓` still moves down / steps through history), so it stays
  out of the way while you edit. The `/menu` command is unchanged.

## [3.10.75] - 2026-08-09

### Changed
- **`/mcp search` is now Algolia-backed too.** MCP server lookups query the
  hosted `dulus_mcps` index (~3k servers, ~1ms, typo-tolerant) before the live
  registry/awesome crawl, which walked thousands of entries and could take 10s+.
  Same result shape; any Algolia miss or failure falls through to the full live
  crawl untouched. Kill-switch: `DULUS_ALGOLIA=0`.
- **Sharper efficiency prompting (the "Efficiency Law").** The system prompt and
  the OpenAI-compatible tool-use guidance now push aggressive tool chaining:
  emit independent calls in parallel in one turn, run dependent scan→filter→drill
  steps inside a single Python()/Bash() call, and prefer one Python-kernel
  `os.walk`+regex sweep over a string of Grep/Glob/Read round-trips. The Python
  console is flagged as the first-choice tool for any multi-file investigation —
  fewer round-trips, fewer tokens, faster answers.

### Changed
- **`/skill` search is now Algolia-backed — instant and typo-tolerant.** Skill
  lookups query a hosted Algolia index (`dulus_skills`, 60k+ curated entries)
  before the live skills.sh API, turning throttled 10s+/request crawls into
  sub-millisecond, typo-tolerant results. The live path is untouched and still
  runs as a fallback whenever Algolia is off or returns nothing. New stdlib-only
  `algolia_search.py` client ships with a search-only public key (safe to
  distribute) and a `DULUS_ALGOLIA=0` kill-switch; it never raises, so search
  always degrades gracefully.

## [3.10.73] - 2026-08-08

### Added
- **Rotating ASCII boot banner.** The startup logo now rotates through a curated
  set of ~42 good-looking fonts (block / 3D / bold / clean) on every launch
  instead of a single fixed logo — the flat, squished and oversized fonts in the
  pack are filtered out. The ASCII is painted in the active theme's accent color
  (follows `/theme`), with no per-font header line. Falls back to the Cigua eagle
  logo (boot) or the block DULUS banner (`/clear`) if the pack is missing.
  Rotation state lives under `~/.dulus`, so it works from a read-only install.

## [3.10.72] - 2026-08-08

### Fixed
- **`/lookback` was quietly restarting the prompt cache every few turns.** With
  lookback ON the API window re-anchored every `n//4` user turns, and each
  re-anchor drops the front of the conversation — which rewrites the whole
  prefix and busts the provider prompt cache (a full write at ~1.25–2x price,
  like starting a fresh session). Three fixes:
  - **Block re-anchoring.** The window now drifts a full `n` turns (n → 2n)
    before re-anchoring instead of `n//4`, cutting cache-busting rewrites ~4x.
  - **Cache-aware gate.** When the hidden head isn't meaningfully bigger than
    the window it would keep (`lookback_min_hidden_ratio`, default 2.0×),
    lookback yields and sends the full archive so the cache keeps hitting —
    front-truncation only wins when the archive is much larger than the window.
    `/context` shows when the gate is active. Set the ratio to 0 to force
    truncation (providers with no prompt cache).
  - **Anchor signature.** The anchor now carries a byte-signature of its
    message, so after context compaction rewrites the archive the window
    realigns instead of reusing a stale index that points at the wrong turn.

## [3.10.71] - 2026-08-07

### Changed
- **Bigger `/lookback` presets.** The `/lookback` autocomplete now offers
  **50 / 150 / 250** user turns (was 5–50), and `MAX_LOOKBACK_TURNS` is raised
  200 → 250. A single turn now drags its whole tool trail, so the old small
  windows were cutting context mid-conversation. The window counts user TURNS
  (each carries its tools); the full archive always stays local via loopback.

## [3.10.70] - 2026-08-07

### Fixed
- **The `←←` (double-left-arrow) quick menu silently never opened.** Two bugs:
  prompt_toolkit ≥ 3.0.52 removed `Application.run_in_terminal()` (the
  `AttributeError` was swallowed), and once it ran the menu rendered invisible —
  Dulus's stdout wrappers (island streaming + prompt_toolkit's `StdoutProxy`)
  never reach the terminal while the prompt app is suspended. Now scheduled via
  the module-level `run_in_terminal` and drawn straight to the controlling
  terminal (`/dev/tty`, `CON` on Windows).

## [3.10.69] - 2026-08-05

### Added
- **Seed wisdom on every install.** Dulus now ships 14 curated, generalizable
  insight memories: tmux send-keys mastery, filtering big tool outputs instead of
  swallowing them, the investigator workflow, AskUserQuestion-after-lists, browser
  automation (JS over click), not busy-polling background jobs, native code over
  sketchy plugins, no personal info in code, search-by-mtime, tool chaining,
  cleverness-over-resources (the `/img` OCR trick), and the corporate-TLS /
  `curl_cffi` gotcha. Planted idempotently on **every** startup (not just first
  run), so `pip install --upgrade dulus` delivers them to existing users on their
  next launch. All carry zero personal or project-specific data.

### Changed
- Default identity buckets (Soul, Preferences) no longer embed a specific
  creator/user name — generic wording so a fresh palace ships clean.

## [3.10.68] - 2026-08-05

### Fixed
- **Dulus Bar: ghost sessions + a stuck panel.** Requires **dulus-bar >= 0.3.7**.
  Closing and reopening an agent no longer leaves a duplicate session in the
  island — the server now drops a session the moment its websocket closes
  (idle-but-live sessions are unaffected). And the expanded "active agents"
  panel collapses when you click away; the permission toast still waits for an
  explicit Allow/Deny.

## [3.10.67] - 2026-08-05

### Fixed
- `cmd_wake` (voice wake-word calibration) could raise `UnboundLocalError`
  (F823): a local `import threading, time as _time` shadowed the module-level
  `threading`, so the earlier `threading.Timer(...)` in the same function
  referenced an unbound local. Keep only the local `time` import — `threading`
  is already imported at module scope. (Surfaced by an AST audit of the codebase.)

## [3.10.66] - 2026-08-05

### Fixed
- **"Open agent" from the island works again.** Bumped to **dulus-bar >= 0.3.6**,
  which now ships its agent wrappers *inside* the package. They previously lived
  at the repo root and were excluded from the wheel, so launching an agent (or
  Dulus) from the island's right-click menu ran `python <missing>/agent_wrapper.py`
  — Python errored and the freshly-opened terminal closed instantly.

## [3.10.65] - 2026-08-04

### Fixed
- **Cleaner Dulus Bar approval prompts.** The client now sends a tidy tool NAME
  (via `_clean_call` in `dulus_bar_client.py`) instead of a raw split-chunk of
  the description, so the island never shows the same call twice. Requires
  **dulus-bar >= 0.3.5**, which renders the prompt as one solid, readable bubble
  (de-duplicated + ellipsis-truncated, agent/model title, macOS-style
  Allow/Deny) — legible on any backdrop, including a light desktop — and gives
  the island's right-click menu the same full set as the tray icon.

## [3.10.64] - 2026-08-04

### Changed
- **Dulus Bar is now ON by default.** `dulus-bar` is a regular dependency, so
  `pip install dulus` opens with the floating island out of the box (it's just a
  library dep — pip pulls it and its PyQt6 at install time; the `dulus` wheel
  stays tiny, nothing is bundled). Still a silent no-op on headless/no-display
  boxes (Docker, servers, CI) — it never imports Qt without a screen.
- Startup now prints how to turn the island **off** the moment it comes on:
  `DULUS_BAR=0` or `/config dulus_bar=0`.

### Fixed
- Type-check (pyright) errors introduced with the bar bridge in 3.10.63:
  a loosely-typed permission dict in `dulus.py` and the websocket handle /
  incoming-frame types in `dulus_bar_client.py`. CI `quality` is green again.

## [3.10.63] - 2026-08-03

### Added
- **Dulus Bar integration — the floating "Dynamic Island".** New optional
  `dulus_bar_client.py`: a defensive websocket client that streams live status
  (session, model, ctx) to the [Dulus Bar](https://pypi.org/project/dulus-bar/)
  island over `ws://127.0.0.1:17372` and forwards Allow/Deny decisions back.
  Default-on when the `dulus-bar` package is installed (and GUI-capable); it
  auto-launches the island so Dulus opens with it out of the box. Off switch:
  `DULUS_BAR=0` / `/config dulus_bar=0`.
- Hooks in **CLI, WebChat, and the desktop GUI**: startup + per-turn
  `status(model, ctx)`, and tool permissions mirrored to the island with
  `Allow/Deny` (`_permission_with_bar` polls the keyboard and the island
  concurrently; WebChat/GUI resolve the pending permission on a click). The
  **Round Table is intentionally excluded** (`bar_ok=False`).
- New optional extra `dulus[bar]` (pulls `dulus-bar`). Fully optional — a silent
  no-op when the package/island isn't present.

## [3.10.62] - 2026-08-02

### Fixed
- **Sentry: handled errors surfaced via `err()` are now captured.** The
  excepthook integration only reports *uncaught* exceptions, but nearly every
  failure in the interactive agent is caught and shown through `common.err()`,
  so almost nothing reached Sentry. `err()` now forwards the in-flight exception
  (full traceback) as a handled event when it runs inside active exception
  handling; calls with no live exception send nothing. No-op when sentry-sdk is
  absent or uninitialised, so `DULUS_NO_SENTRY` / empty DSN stay honoured. One
  central hook — the ~285 existing catch sites that call `err()` now report
  without being modified.

## [3.10.61] - 2026-08-02

### Added
- **`edge` provider — local / on-device small models.** A backend-agnostic
  OpenAI-compatible route (`type: openai`, `127.0.0.1:8080/v1`) for running a
  model on-device with no per-token cost. Works today with llama.cpp's
  `llama-server` or Ollama — including **Termux on Android**. Model ids route
  via `edge/*`, `gemini-nano`, `gemma-3n`, `gemma-4` (these win over cloud
  Gemini and local Ollama); arbitrary GGUFs are reachable with the explicit
  `edge/<name>` prefix. Host/port overridable via `DULUS_EDGE_BASE_URL` env or
  `/config edge_base_url=...`. On-device models priced at `$0` in `COSTS`.
- README: new **"On the edge"** section + a Termux quickstart; the on-device
  **Gemma Nano APK (AICore/NPU)** is documented as work-in-progress.

## [3.10.60] - 2026-08-01

### Added / Changed
- **webbridge: persistent, detached, reconnectable browser.** The bridge now
  launches a detached Chromium (survives Dulus exit/Ctrl+C) with a persistent
  profile (cookies + sessions persist), and reconnects to an existing browser
  across processes via a CDP endpoint recorded in a lock file — with PID/port
  liveness checks and stale-lock cleanup. New helpers: `_launch_detached_browser`,
  `_connect_existing_browser`, `_cdp_port_open`, `_find_free_port`, `_pid_exists`.
  Ported wholesale from the private build (webbridge/tools.py and __init__.py
  were already in sync).

## [3.10.59] - 2026-08-01

### Fixed
- **webbridge: visible browser tab now stays in sync with logical state.** Tab
  switch/open/close now call `bring_to_front()` and commit the active-tab state
  only after the tab is truly foregrounded (with rollback on failure), so
  screenshots and interactions target the tab the agent thinks is active. Also:
  closed pages are pruned from the registry, new tabs get collision-free IDs,
  closing the active tab focuses a deterministic survivor, and `list_tabs`
  prunes stale pages. Covered by `tests/test_webbridge_tabs.py`.

## [3.10.58] - 2026-07-31

### Added
- **`/vim`** — toggle vi keybindings on the REPL input line (`on`/`off`/`status`,
  persists across sessions). Powered by prompt_toolkit's VI editing mode.
- **`/edit <path>`** — open a file in your real terminal editor (`$VISUAL`/
  `$EDITOR`, falling back to nvim → vim → nano; notepad on Windows); blocks until
  you close it, then returns to Dulus. No path opens a scratch buffer.

## [3.10.57] - 2026-07-29

### Changed
- **Internal: model custom-parameter registry (`model_params.py`).** Per-model
  settings — reasoning-effort levels, toolbar "hot" highlight levels, and
  quick-menu entries — are now declared once and read by `cmd_effort`, the REPL
  toolbar, `/effort` tab-completion (`_CMD_META`), and the quick menu (`/menu`).
  Behavior is unchanged; adding a model with custom params is now one registry
  entry instead of edits across five files.

## [3.10.56] - 2026-07-29

### Added
- **GPT-5.6 family via ChatGPT OAuth (no API key):** Sol, Sol Pro, Terra, and
  Luna, routed through the `chatgpt-oauth` provider. Select with
  `/model chatgpt/gpt-5.6-sol` (or `-terra` / `-luna`) after `/login chatgpt`.
- **Reasoning-effort tiers for the GPT-5.6 family** — `/effort minimal|low|
  medium|high|max|ultra` (Kimi k3 keeps low/high/max) — with toolbar indicator
  and quick-menu entries.

## [3.10.55] - 2026-07-29

### Fixed
- **Prompt cache no longer busts on every tool turn.** Replaying tool-call
  history re-serialized each call's arguments with `json.dumps()`, which can
  reorder keys / change spacing versus the bytes the model streamed. Providers
  key prompt caching on the exact bytes of earlier messages, so this invalidated
  the cache every tool turn (full re-cache at write price — worst on Grok/Kimi/
  DeepSeek). `_finalize_tool_calls` now keeps `arguments_raw` and
  `messages_to_openai` replays it byte-for-byte, keeping the prefix stable.
- **System-prompt cache no longer busts on skills-catalog refresh.** The skills
  catalog line embedded the file's KB size, a number that changed whenever the
  catalog was rebuilt, invalidating the system-prompt prefix. Removed.

## [3.10.54] - 2026-07-28

### Fixed
- **Agent no longer stops mid-task after a reasoning model "thinks" without
  acting.** Reasoning models (Grok, Kimi k3, DeepSeek) can emit only their
  `<thinking>` and end the stream — often truncated on `finish_reason="length"`
  — before any answer or tool call. The loop treated an empty `tool_calls` list
  as a completed turn and broke silently. Now a turn with no text *and* no tool
  call is detected as a stall and the model is nudged to continue (call the next
  tool or give its answer), bounded by a retry cap; a turn with real text is
  still a normal final answer.

## [3.10.53] - 2026-07-28

### Added
- **`Python` console tool — a persistent REPL kernel used as working memory
  outside the context window.** Its namespace persists across tool calls, so the
  agent can scan a large structure once into a variable and query it across turns
  while only small slices ever enter the conversation — the bulk lives in the
  kernel's heap and is never re-read or re-transmitted. Runs in an isolated
  subprocess kernel (this module doubles as the worker via `--pykernel-worker`),
  so an infinite loop or crash kills the kernel, never Dulus; the parent enforces
  a wall-clock timeout and auto-restarts a dead/killed kernel. Output is capped at
  the source by characters (not just lines) with a bounded `reprlib` echo, so one
  enormous line or a huge `repr()` can't flood the context and get re-billed every
  turn. `input()` is neutralised, tracebacks are trimmed to the caller's frames,
  and trailing bare expressions echo like a REPL. See
  [docs/python-console.md](python-console.md).

## [3.10.52] - 2026-07-28

### Fixed
- **TmuxOffload no longer leaks tmux sessions on Windows.** Windows tmux panes
  default to PowerShell, which doesn't understand the bash `&&`/`||`/`;` in the
  old send-keys cleanup one-liner, so the trailing `tmux kill-session` never ran
  — finished jobs left an idle PowerShell session lingering, accumulating with
  every offload. The session is now created *with* a `.cmd` wrapper as its main
  process (`tmux new-session -d -s NAME cmd.exe /c wrapper.cmd`); the wrapper runs
  the tool then unconditionally runs `kill-session` and exits, so the pane dies
  cleanly, with `remain-on-exit` forced off as a belt. Verified on Windows
  (tmux 3.3.6). Linux/macOS unchanged.

## [3.10.51] - 2026-07-27

### Fixed
- **Background job (TmuxOffload) notifications now arrive autonomously.** The job
  sentinel injected a finished-job notice into the conversation but never woke the
  agent — so the notice just sat there until your *next* message, defeating the
  point of offloading. It now wakes the agent via the same safe path Reminders and
  the proactive watcher use (`_enqueue_or_run` → `run_in_terminal`), which prints
  above the live prompt without corrupting it or eating half-typed input. When a
  job finishes and the chat has been idle ~10s, Dulus reviews and reports back on
  its own.

## [3.10.50] - 2026-07-27

### Fixed
- **Tool turns no longer report `+0 in / +0 out`.** Most providers only emit the
  streaming usage chunk on the FINAL text response — intermediate tool-call
  responses carry no usage, so `in_tokens` was 0 there, printing `+0` per tool
  turn and under-counting `/cost`. When the provider reports nothing, Dulus now
  estimates the real input it sent (windowed messages + tool schemas + system).
  Cache hits are still shown separately; real reported usage is never
  double-counted.

## [3.10.49] - 2026-07-27

### Fixed
- **Parallel tool calls on OpenAI-compatible providers (Kimi, DeepSeek, …).** The
  agent loop already executes every tool_call in a turn, but the request only set
  `tool_choice=auto` — never `parallel_tool_calls`. Many OpenAI-compatible servers
  default parallel OFF, so the model emitted one tool per API round-trip, and each
  round-trip resends the growing context (and re-primes the cache). Now sends
  `parallel_tool_calls=true` plus a Grok-style nudge so the model batches
  INDEPENDENT actions into one response. Opt out with
  `/config disable_parallel_tools=1`.

## [3.10.48] - 2026-07-27

### Fixed
- **The `/menu` quick popup no longer takes over the whole terminal.** It
  rendered as a full-screen panel (everything pushed to the top) with a flickery
  continuous refresh. Now it's a compact box at the cursor (`screen=False`,
  `expand=False`, `transient=True`) that redraws only on keypress.

## [3.10.47] - 2026-07-27

### Added
- **Kimi membership login — `/login kimi` (no API key).** Device-OAuth against
  auth.kimi.com (the official Kimi Code CLI flow); reuses `~/.kimi-code`
  credentials if you've logged in there. After login, `kimi-oauth/*` models
  (`kimi-oauth/k3`, `kimi-oauth/k3-256k`, `kimi-oauth/kimi-for-coding`) run on
  your Kimi membership instead of API credits. Aliases: `/login-kimi`,
  `/kimi-login`.
- **`/effort [low|high|max]`** — reasoning effort for Kimi `k3` / `k3-256k`
  (default high, per Kimi's docs), with a Claude-Code-style animated slider.
  Shown in the toolbar (`⚡high`). `kimi-for-coding` uses `/thinking` instead.
- **`/menu`** and **double-tap ← ←** — a quick popup menu (effort / thinking /
  Kimi model switch / …). `/menu` is the reliable path when a terminal swallows
  the key sequence.

### Fixed
- **Correct Kimi model IDs.** `kimi-code` / `kimi-oauth` now use the real ids
  `k3`, `k3-256k`, `kimi-for-coding` (the old `kimi-k3`/`kimi-k2.6`/… don't exist
  on api.kimi.com, so selecting them failed).
- Kimi now sends `reasoning_effort` for `k3`/`k3-256k`; `/model` heals a doubled
  provider prefix (`kimi-oauth/kimi-oauth/…`).

## [3.10.46] - 2026-07-26

### Fixed
- **Saved sessions now record prompt-cache savings.** Dulus already reads the
  provider's cached-token count (OpenAI `prompt_tokens_details.cached_tokens`,
  Kimi top-level `cached_tokens`, DeepSeek `prompt_cache_hit_tokens`), accumulates
  it, and shows it live in `/cost` and per turn. But the session **save** only
  wrote input/output totals — so a saved session lost the cache accounting and
  post-hoc analysis showed 0 cache even when the provider was caching. `/save`
  now persists `total_cache_read_tokens` / `total_cache_creation_tokens`, and
  `/load` restores them.

## [3.10.45] - 2026-07-26

### Fixed
- **A large `Edit` was silently re-billing you its full diff every turn.** `Write`
  truncated its result diff to 80 lines; `Edit` did **not** — it returned the
  entire unified diff of the change. On a big edit (say, replacing 6 lines with
  260) that diff is huge, and because it stays in the conversation it was resent
  to the model on **every** subsequent turn, quietly inflating input tokens for
  the rest of the session. `Edit` now caps its diff to the same 80 lines as
  `Write`. Real fix for real bills — a session that hammered a big file could
  spend most of its input tokens re-sending Edit diffs it already applied. Also
  surfaces MemPalace state in the boot banner (green when on, red when off).

### Added
- **`$DULUS` community line on the boot banner.** A single line under the logo —
  `buy $dulus` plus the link, with the URL rendered in the Dulus animation
  gradient. No pitch, no wall of text; one line, easy to ignore. The `/buy-dulus`
  command (added in 3.10.43) still opens the same link on demand.

## [3.10.43] - 2026-07-26

### Added
- **Lookback — send the model a small window while keeping the full history
  local.** Long sessions bleed tokens: every turn replays the *entire*
  conversation to the provider. Lookback splits what the model **sees** from
  what you **keep**. With `/lookback on` (or `/lookback 20`), only the last N
  user turns go to the API; the full conversation stays saved locally — that
  archive is **loopback**, inspectable/searchable anytime with `/loopback
  show|search|head|status`. The window only ever cuts on a **user-turn
  boundary**, so an assistant `tool_call` is never separated from its
  `tool_result` (providers reject broken chains). A gold `short_memory` in the
  system prompt keeps the essential past beside the model. The window is
  **anchored** with hysteresis (re-anchor only every ~N/4 turns) so the API
  prefix stays append-only between jumps and provider **prompt caches keep
  hitting** — a naively sliding window rewrites the prefix every call and costs
  more than it saves. The agent also gets a native **`Loopback` tool**
  (`action=status|show|head|search`) so it retrieves hidden history itself
  instead of asking you to run a slash command. Off by default; `/lookback`
  shows live status.

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
