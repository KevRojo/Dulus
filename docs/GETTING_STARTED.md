# Getting Started with Dulus

> Your AI companion is waiting. From zero to chatting in 30 seconds.

---

## Table of Contents

- [Installation](#installation)
- [First Run](#first-run)
- [Basic Usage](#basic-usage)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

---

## Installation

### Option A: One-liner Installer (Recommended — zero friction)

**Linux / macOS / WSL / Termux:**

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

The installer finds **or bootstraps** Python ≥3.11 (apt / deadsnakes / brew / uv), installs Dulus, and puts `dulus` on your PATH. This is the path that works on stock Ubuntu 20.04/22.04 where plain `pip install dulus` dies with `No matching distribution found` (pip hides packages that need a newer Python).

Profiles:

- **`full`** — Everything: voice (Whisper + PortAudio), browser tools (Playwright), MemPalace, tmux, WSL audio bridge (~1.5 GB)
- **`standard`** — REPL + webchat + tmux daemon + Telegram bridge (~300 MB)
- **`basic`** — Bare `pip install dulus` for servers / minimal sandboxes (~150 MB)
- **`custom`** — Toggle each feature one by one

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/KevRojo/Dulus/main/install.ps1 | iex
```

(Or skip Python entirely with the MSI — see README.)

Power-user flags:

```bash
# Preview without changing anything
curl -fsSL .../install.sh | bash -s -- --dry-run

# Non-interactive install (CI / scripts)
curl -fsSL .../install.sh | bash -s -- --profile=full --pipx

# Latest pre-release
curl -fsSL .../install.sh | bash -s -- --pre
```

### Option B: pip (only if you already have Python 3.11+)

```bash
pip install dulus
```

With optional extras:

```bash
pip install "dulus[memory]"     # + MemPalace semantic memory
pip install "dulus[voice]"      # + Voice I/O (Whisper STT + TTS)
pip install "dulus[webbridge]"  # + Playwright browser automation
pip install "dulus[full]"       # Everything
```

> If pip says `No matching distribution found for dulus`, your Python is &lt; 3.11. Use Option A — the installer upgrades Python for you.

### Option C: Docker (Zero Local Python)

```bash
# 1. Grab the compose file + env template
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env   # then add your API keys

# 2. Pull and run (WebChat at http://localhost:5050)
docker compose up -d

# 3. Or jump into the REPL inside the container
docker compose exec dulus dulus
```

Image: `ghcr.io/kevrojo/dulus` · Memory persists in the `dulus-memory` volume.

### Option D: From Source (for Contributors)

```bash
git clone https://github.com/KevRojo/Dulus && cd Dulus
pip install -e .          # editable install
dulus
```

### Termux / Android

```bash
pkg install python python-numpy python-pillow build-essential
pip install --no-deps dulus
pip install anthropic openai httpx requests rich prompt_toolkit Flask bubblewrap-cli mempalace
```

Note: Skip `sounddevice` (no usable PortAudio on Android). Voice features won't work, but the CLI still boots and chats fine.

---

## First Run

When you run `dulus` for the first time, the welcome wizard guides you through a 30-second setup:

### Step 1: Your Name

```
How should I call you? [amigo]
```

### Step 2: Choose a Provider

```
Que proveedor queres usar de entrada?
  1. Ollama (local, free)
  2. NVIDIA NIM (14 free models)
  3. Anthropic Claude
  4. Kimi for Coding
  5. Moonshot Kimi K2
  6. OpenAI (GPT-4o / o3)
  7. Google Gemini
  8. DeepSeek
  9. LiteLLM gateway (100+ providers)
```

### Step 3: Browser Harvest (Zero API Key)

```
Feature clave de Dulus: IA AHORA, SIN api key, SIN cuenta.
Abrimos un browser, escribis "hola" una vez, listo.
(Works with Gemini guest / Claude.ai / Kimi / Qwen / DeepSeek.)

Probamos AHORA con Gemini gratis (sin login)? [gemini]
```

Dulus opens your browser, you type one message, and Dulus harvests the session. No API key. No login. No credit card.

### Step 4: Optional Setup

- **MemPalace** — If installed, Dulus initializes your persistent memory
- **Soul** — Dulus seeds your companion's personality file (`~/.dulus/memory/soul.md`)
- **Health Check** — `/doctor` runs automatically to verify everything is working

---

## Basic Usage

### Chat in the REPL

```bash
$ dulus

  Dulus v3.2.0  |  model: ollama/gemma4:latest
  soul loaded, memory warm, shell sniffed.

  [00] > Write a Python function to calculate fibonacci
  ...
```

### Pipe Input (Unix-Style)

```bash
echo "explain this diff" | git diff | dulus -p --accept-all
git diff | dulus -p "write a commit message"
cat error.log | dulus -p "what caused this error"
```

### Switch Models

```
/model                    # show current
/model gpt-4o             # switch to OpenAI
/model ollama/llama3.3    # switch to local
/model nvidia-web/deepseek-r1  # free NVIDIA tier
```

### Use Memory

```
/memory search jwt        # fuzzy ranked search
/memory load 1,2,3        # inject into context
/memory consolidate       # distill session insights
/memory purge             # clear (keeps Soul)
```

### Voice Input

```bash
pip install sounddevice faster-whisper numpy
```

```
/voice                    # start voice recording
/voice lang zh            # set voice language
/voice device             # select microphone
```

### Brainstorm Mode

```
/brainstorm "should we rewrite in rust"
> persona: Skeptical PM
> persona: Principal Engineer
> persona: Grumpy DBA
> persona: Hot-take Intern
```

### Sub-Agents (The Flock)

```
/agents                              # show active
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e")
```

### Plugins (Auto-Adapter)

```
/plugin install yfinance@https://github.com/ranaroussi/yfinance
/plugin install sherlock@https://github.com/sherlock-project/sherlock
/plugin list
/plugin enable/disable/update/uninstall
```

### Checkpoints

```
/checkpoint                 # list all
/checkpoint 042             # rewind to #042
/checkpoint clear           # reclaim disk
```

### WebChat GUI

```
/webchat                    # open browser UI at localhost:5050
```

Or use the desktop GUI:

```bash
dulus-gui                   # tkinter-based desktop GUI
```

### Telegram Bridge

```
/telegram <bot_token> <chat_id>              # single user
/telegram <bot_token> <id1>,<id2>,<id3>      # multi-user
```

---

## Advanced Configuration

### Config File

Located at `~/.dulus/config.json`:

```json
{
  "model": "ollama/gemma4:latest",
  "max_tokens": 128000,
  "permission_mode": "auto",
  "thinking": false,
  "git_status": false,
  "max_tool_output": 2500,
  "max_agent_depth": 3,
  "max_concurrent_agents": 3,
  "search_region": "do-es",
  "tts_enabled": false,
  "tts_provider": "auto"
}
```

Set in the REPL:

```
/config model=anthropic/claude-sonnet-4-6
/config permission_mode=plan
/config max_tokens=64000
```

### CLAUDE.md

Drop a `CLAUDE.md` at your project root. It gets auto-injected into the system prompt so Dulus remembers your stack, conventions, and preferences.

```markdown
# Project Context

- Language: Python 3.12
- Framework: FastAPI
- Database: PostgreSQL
- Testing: pytest
- Style: black + ruff
- NEVER use asyncio in this codebase.
```

### Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API access |
| `OPENAI_API_KEY` | OpenAI API access |
| `GEMINI_API_KEY` | Google Gemini API |
| `DEEPSEEK_API_KEY` | DeepSeek API |
| `MOONSHOT_API_KEY` | Kimi API |
| `NVIDIA_API_KEY` | NVIDIA NIM free tier |
| `DASHSCOPE_API_KEY` | Qwen/Alibaba API |
| `DULUS_SECRET` | Secret key for config encryption |

### Per-Provider API Keys (in config)

```json
{
  "anthropic_api_key": "sk-ant-...",
  "openai_api_key": "sk-...",
  "nvidia-web_api_key": "nvapi-..."
}
```

These are encrypted with XOR + base64 before saving to disk.

---

## Troubleshooting

### "No matching distribution found for dulus"

Your Python is older than 3.11 (common on stock Ubuntu 20.04/22.04). pip hides packages that require a newer interpreter and prints that useless error instead of telling you the truth.

**Fix (zero friction):** use the one-liner — it bootstraps Python 3.11+ for you:

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### "No module named 'tkinter'"

```bash
# Linux / WSL
sudo apt install python3-tk

# macOS and Windows: tkinter is bundled
```

### "PortAudio library not found"

```bash
sudo apt install libportaudio2 portaudio19-dev libasound2-dev
pip install sounddevice --upgrade --force-reinstall
```

### Tool calls fail on local model

Use a model that supports function calling: `qwen2.5-coder`, `llama3.3`, `mistral`, `phi4`. Avoid base models without tool-use training.

### MemPalace fails to import

```bash
pip install dulus[memory]   # pulls chromadb
```

On Termux/aarch64 where NumPy has no prebuilt wheels, skip the memory extra. The CLI works fine without it.

### "Voice transcribes technical terms wrong"

Add domain terms to `~/.dulus/voice_keyterms.txt`, one per line. Whisper respects the hint.

### WebBridge not working

```bash
pip install dulus[webbridge]   # pulls Playwright
playwright install
```

### Check API costs

```
/cost
```

### Reset everything

```bash
rm -rf ~/.dulus    # removes config, memory, sessions
```

Then run `dulus` again to re-run the welcome wizard.

---

## Next Steps

- Read the [Architecture Guide](ARCHITECTURE.md) to understand how Dulus works under the hood
- Check the [API Reference](API.md) for programmatic usage
- See [Contributing](CONTRIBUTING.md) to extend Dulus with your own tools
- Join the community on [X / @KevRojo](https://x.com/KevRojo)

---

> *Named after the bird, not the rocket. We keep flying.*
