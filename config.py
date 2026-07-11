"""Configuration management for Dulus (multi-provider)."""
import os
import json
from pathlib import Path

CONFIG_DIR        = Path.home() / ".dulus"
CONFIG_FILE       = CONFIG_DIR  / "config.json"
HISTORY_FILE      = CONFIG_DIR  / "input_history.txt"
SESSIONS_DIR      = CONFIG_DIR  / "sessions"
DAILY_DIR         = SESSIONS_DIR / "daily"       # daily/YYYY-MM-DD/session_*.json
SESSION_HIST_FILE = SESSIONS_DIR / "history.json" # master: all sessions ever
OUTPUT_DIR        = CONFIG_DIR  / "output"         # WebFetch compressed cache

# kept for backward-compat (/resume still reads from here)
MR_SESSION_DIR = SESSIONS_DIR / "mr_sessions"

DEFAULTS = {
    "model":            "ollama/gemma4:latest",
    "max_tokens":       128000,
    "permission_mode":  "auto",   # auto | accept-all | manual
    "verbose":          False,
    "thinking":         False,
    "git_status":       False,
    # 0 = auto: scale budget with /thinking level (low=2048, med=6000,
    # high=16000, on=8192). A non-zero value here overrides ALL levels —
    # the old default of 50000 silently let every thinking turn burn up
    # to 50K output tokens regardless of level.
    "thinking_budget":  0,
    # Anthropic prompt-cache TTL. "1h" = cache survives think-pauses between
    # turns (the default 5-min ephemeral cache dies if you pause >5 min,
    # forcing a full prefix re-write at 1.25x price every time). 1h costs 2x
    # once on write, then ~0.1x on every hit — massively cheaper for
    # interactive sessions.
    "cache_ttl":        "1h",
    "custom_base_url":  "",       # for "custom" provider
    "max_tool_output":  2500,
    "max_agent_depth":  3,
    "max_concurrent_agents": 3,
    "adapter_max_fix_attempts": 20,  # max fix attempts per task in autoadapter worker
    "session_limit_daily":   10,    # max sessions kept per day in daily/
    "session_limit_history": 200,  # max sessions kept in history.json
    "license_key":          "",    # Dulus license key (PRO/ENTERPRISE)
    # Shell configuration (Windows only)
    # Valid types: "auto" (detects gitbash/wsl), "gitbash", "wsl", "powershell", "cmd", "custom"
    # For "custom", you MUST provide the full path to the shell executable
    "shell": {
        "type": "auto",           # auto | gitbash | wsl | powershell | cmd | custom
        "path": ""                # e.g.: "C:\\Program Files\\Git\\bin\\bash.exe"
    },
    # DeepSeek-specific overrides (for models that struggle with tools)
    "deep_override": False,  # Use simplified system prompt for DeepSeek
    "deep_tools":    False,  # Enable auto JSON wrapping for DeepSeek tool calls
    # Bocha AI Search (博查) — optional native Chinese search backend (opt-in)
    "bocha_search_key": "",
    "bocha_search_enabled": False,
    # Brave Search API Key
    "brave_search_key": "",
    "brave_search_enabled": False,
    "tts_enabled":          False,
    "tts_provider":         "auto",   # auto | azure | openai | gtts | pyttsx3 | riva | edge | elevenlabs
    "azure_speech_key":     "",
    "azure_speech_region":  "",
    "azure_tts_voice":      "",       # e.g. es-ES-AlvaroNeural, es-MX-JorgeNeural
    "elevenlabs_api_key":   "",
    "elevenlabs_voice_id":  "CwhRBWXzGAHq8TQ4Fs17",   # default voice (Roger)
    "elevenlabs_model_id":  "eleven_multilingual_v2",
    # WebFetch/WebSearch settings
    "webfetch_compress": False,   # Enable Ollama compression for WebFetch
    "webfetch_translate": False,  # Translate to Spanish when compressing
    "search_region":     "do-es", # Default search region (e.g. 'do-es', 'us-en', 'mx-es')
    # Per-provider API keys (optional; env vars take priority)
    # "anthropic_api_key": "sk-ant-..."
    # "openai_api_key":    "sk-..."
    # "gemini_api_key":    "..."
    # "kimi_api_key":      "..."
    # "qwen_api_key":      "..."
    # "zhipu_api_key":     "..."
    # "deepseek_api_key":  "..."
    # License key (Pro / Enterprise)
    "license_key": "",
    # Qwen-web (chat.qwen.ai consumer session) — populated by /harvest-qwen
    "qwen_web_auth_path": "",
    "qwen_web_chat_id":   "",
    "qwen_web_parent_id": "",
    # RTK (Rust Token Killer) — transparently rewrites covered shell commands
    # via the rtk binary for token-optimized output. Soft-fallback if rtk is
    # missing. Linux/Mac users: bash rtk/install.sh to fetch the binary.
    "rtk_enabled": True,
}


# ── Simple secret encryption (XOR + base64) — no external deps ────────────
_SECRET_KEY = os.environ.get("DULUS_SECRET", "falcon-default-key")

def _encrypt(value: str) -> str:
    """Encrypt a string with XOR + base64."""
    if not value or value.startswith("enc:"):
        return value
    key = _SECRET_KEY.encode("utf-8")
    data = value.encode("utf-8")
    enc = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
    return "enc:" + __import__("base64").b64encode(enc).decode("ascii")


def _decrypt(value: str) -> str:
    """Decrypt a string encrypted with _encrypt."""
    if not value or not value.startswith("enc:"):
        return value
    try:
        key = _SECRET_KEY.encode("utf-8")
        enc = __import__("base64").b64decode(value[4:])
        data = bytes(enc[i] ^ key[i % len(key)] for i in range(len(enc)))
        return data.decode("utf-8")
    except Exception:
        return value


def _secure_keys(cfg: dict) -> dict:
    """Encrypt all *_api_key values before saving."""
    for k, v in list(cfg.items()):
        if k.endswith("_api_key") and v and isinstance(v, str):
            cfg[k] = _encrypt(v)
    return cfg


def _unsecure_keys(cfg: dict) -> dict:
    """Decrypt all *_api_key values after loading."""
    for k, v in list(cfg.items()):
        if k.endswith("_api_key") and v and isinstance(v, str):
            cfg[k] = _decrypt(v)
    return cfg


def load_config() -> dict:
    CONFIG_DIR.mkdir(exist_ok=True)
    SESSIONS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            # Config is corrupt (truncated write, crash mid-save, etc).
            # NEVER silently reset the user's config: try the .bak backup
            # first, and if that also fails, preserve the corrupt file for
            # manual recovery instead of letting the next save_config()
            # clobber it with bare defaults.
            recovered = False
            backup = CONFIG_FILE.with_suffix(".json.bak")
            if backup.exists():
                try:
                    cfg.update(json.loads(backup.read_text(encoding="utf-8")))
                    recovered = True
                    print(f"[dulus] WARNING: config.json was corrupt - recovered from {backup.name}")
                except Exception:
                    pass
            try:
                import time as _time
                quarantine = CONFIG_FILE.with_name(
                    f"config.corrupt-{int(_time.time())}.json")
                CONFIG_FILE.replace(quarantine)
                print(f"[dulus] Corrupt config preserved at: {quarantine}")
            except Exception:
                pass
            if not recovered:
                print("[dulus] WARNING: config.json was corrupt and no backup was found - "
                      "starting with defaults. Your old config was preserved (see above).")
    # Decrypt secured keys
    cfg = _unsecure_keys(cfg)
    # Backward-compat: legacy single api_key → anthropic_api_key
    if cfg.get("api_key") and not cfg.get("anthropic_api_key"):
        cfg["anthropic_api_key"] = cfg.pop("api_key")
    # Also accept ANTHROPIC_API_KEY env for backward-compat
    if not cfg.get("anthropic_api_key"):
        cfg["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
    # Bridge config-stored provider keys → env vars so submodules that read
    # from os.environ (e.g. voice/stt.py for NVIDIA Riva) work without
    # duplicating the key. Only sets vars that aren't already in env.
    _ENV_BRIDGE = {
        "nvidia-web_api_key": "NVIDIA_API_KEY",
        "openai_api_key":     "OPENAI_API_KEY",
        "gemini_api_key":     "GEMINI_API_KEY",
        "deepseek_api_key":   "DEEPSEEK_API_KEY",
        "kimi_api_key":       "MOONSHOT_API_KEY",
        "kimi_code_api_key":  "KIMI_CODE_API_KEY",
        "azure_speech_key":   "AZURE_SPEECH_KEY",
        "composio_api_key":   "COMPOSIO_API_KEY",
    }
    for cfg_key, env_var in _ENV_BRIDGE.items():
        val = cfg.get(cfg_key)
        if val and not os.environ.get(env_var):
            # Sanitize: embedded null bytes break os.environ on Windows.
            clean_val = str(val).replace("\x00", "")
            if clean_val:
                os.environ[env_var] = clean_val
    return cfg


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(exist_ok=True)
    # Build a complete config from defaults + whatever is already on disk, THEN
    # apply the runtime changes on top. This prevents catastrophic resets: if a
    # caller passes a thin `cfg` (e.g. only {"lang", "user_name"} at early
    # startup or from a command that rebuilt a minimal dict), we must NOT drop
    # every other key the user had. Previously we wrote `cfg` verbatim, so a
    # thin dict wiped the entire config down to those few keys — exactly the
    # "config shrank to lang+user_name" bug. Mirror the private repo's logic.
    data = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                data.update(existing)
        except Exception:
            # Corrupt on-disk config: fall back to the last-known-good backup so
            # we still don't lose the user's keys on this save.
            try:
                backup = CONFIG_FILE.with_suffix(".json.bak")
                if backup.exists():
                    bdata = json.loads(backup.read_text(encoding="utf-8"))
                    if isinstance(bdata, dict):
                        data.update(bdata)
            except Exception:
                pass
    # Strip internal runtime keys (e.g. _run_query_callback), then apply the
    # caller's runtime changes on top of the merged base.
    runtime = {k: v for k, v in cfg.items() if not k.startswith("_")}
    data.update(runtime)
    # Encrypt API keys before saving
    data = _secure_keys(dict(data))
    payload = json.dumps(data, indent=2)
    # Atomic write: dump to a temp file in the same dir, then replace.
    # A crash mid-write can no longer truncate/corrupt config.json.
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    # Keep a rolling backup of the last-known-good config so load_config()
    # can auto-recover if the main file ever goes bad.
    if CONFIG_FILE.exists():
        try:
            backup = CONFIG_FILE.with_suffix(".json.bak")
            # Only back up if current file is valid JSON (don't overwrite a
            # good backup with a corrupt file).
            json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            backup.write_text(CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    tmp.replace(CONFIG_FILE)


def current_provider(cfg: dict) -> str:
    from providers import detect_provider
    return detect_provider(cfg.get("model", "claude-opus-4-6"))


def has_api_key(cfg: dict) -> bool:
    """Check whether the active provider has an API key configured."""
    from providers import get_api_key
    pname = current_provider(cfg)
    key = get_api_key(pname, cfg)
    return bool(key)


def calc_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    from providers import calc_cost as _cc
    return _cc(model, in_tokens, out_tokens)
