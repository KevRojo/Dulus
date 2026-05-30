# Changelog

All notable changes to Dulus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-language README documentation (EN, ES, FR, ZH, JA, KO, PT, RU, AR)
- Comprehensive architecture documentation
- API reference documentation
- Deployment guide
- Security policy
- Brand guidelines

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
