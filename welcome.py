"""Welcome wizard for Dulus -- Your feathered AI companion.

A warm, friendly first-run experience that introduces Dulus as a companion,
not just a tool. Features:
  - Time-aware greetings (morning/afternoon/evening)
  - Beautiful ASCII art of the Cigua Palmera
  - First-run vs. returning user detection
  - Animated bird spinner during setup
  - Provider + model selection
  - API key prompting (when needed)
  - Soul seeding with personalized personality
  - MemPalace initialization

Usage:
    from welcome import run_welcome_wizard, is_first_run, show_welcome_banner
    if is_first_run():
        config = run_welcome_wizard(config)
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# ASCII Art: The Cigua Palmera (Dulus dominicus)
# ---------------------------------------------------------------------------

CIGUA_ASCII = r"""
                    🦅
                .--._.
               / o o \
              |   >   |
               \\ - /
            .-'  |  '-.
           /  .-'|'-._ \
          |  /   |    \ |
          |  |  ~+~   | |
           \ |  \|/  | /
            \|   |   |/
             |   |   |
            /    |    \
           /  .--|--.  \
          '   |  |  |   '
              |  |  |
             .|  |  |.
            (_|  |  |_)
               \/ \/
         ~ The Cigua Palmera ~
      National bird of Dominican Republic
"""

CIGUA_COMPACT = r"""
       🦅
      /o o\
      | > |
       \-/
    ~ Dulus ~
"""

# ---------------------------------------------------------------------------
# Warm, friendly messages that introduce Dulus as a companion
# ---------------------------------------------------------------------------

_WELCOME_MESSAGES = {
    "first_run": {
        "greeting": [
            "🦅 Hey there! I'm Dulus, your AI companion!",
            "🪶 Welcome, friend! I'm Dulus -- the bird that codes.",
            "🦅 Klk! I'm Dulus, your feathered friend from the Dominican skies!",
        ],
        "intro": [
            "I'm not just any bird -- I'm here to help you build, create, and ship.",
            "Think of me as your coding buddy who never gets tired and always has your back.",
            "Together, we'll turn your ideas into reality. Let's fly!",
        ],
        "no_api_key": [
            "No API key? No problem! I work with free models out of the box. 🎉",
            "I can run entirely locally with Ollama -- zero cost, total privacy.",
            "Or try my web-harvest feature: free AI from your browser session!",
        ],
        "tips": [
            "💡 Tip: Type /help anytime to see what I can do!",
            "💡 Tip: I remember our conversations -- just chat naturally!",
            "💡 Tip: Use /harvest-gemini for free AI without any API key!",
            "💡 Tip: I'm open source -- customize me however you like!",
        ],
    },
    "returning": {
        "greeting": [
            "🦅 Welcome back, {name}! Missed me?",
            "🪶 {name}! My favorite human is back!",
            "🦅 Hey {name}! Ready to build something amazing?",
        ],
        "mood_boost": [
            "Let's pick up where we left off!",
            "I've been sharpening my talons. Let's code!",
            "Another day, another chance to ship something awesome!",
        ],
    },
}

_MOTIVATIONAL_QUOTES = [
    "Every great flight starts with a single flap! 🪶",
    "Even eagles need a push sometimes. 🦅",
    "Code like nobody's watching, ship like everybody is. 🔥",
    "The sky isn't the limit -- it's just the beginning. ☁️",
    "Small commits lead to mighty launches. 🚀",
    "Bug today, feature tomorrow! 🐛✨",
    "Your IDE is your nest -- make it cozy. 🪺",
    "Talous sharp, code sharper. 🦅",
]

# ---------------------------------------------------------------------------
# Time-based greetings
# ---------------------------------------------------------------------------

_MORNING_GREETINGS = [
    "🌅 Good morning! The early bird catches the bug... I mean, the worm!",
    "🌅 Rise and shine! Ready to build something amazing today?",
    "☕ Morning! Coffee for you, electricity for me. Let's go!",
]

_AFTERNOON_GREETINGS = [
    "🌤️ Good afternoon! Halfway through the day -- let's make it count!",
    "🌤️ Afternoon vibes! Time to crush some code.",
    "☀️ Hey there! The sun is high and so is my processing power!",
]

_EVENING_GREETINGS = [
    "🌙 Good evening! Night owls and coding birds unite!",
    "🌃 Evening! The best code is written after dark, don't you think?",
    "✨ Hey there! Let's build something beautiful under the stars.",
]

_NIGHT_GREETINGS = [
    "🌌 Still up? I love the dedication! Let's hack the night away.",
    "🦉 Night owl mode activated! I'm right here with you.",
    "🌙 The quiet hours are the best for deep work. Let's fly!",
]


# ---------------------------------------------------------------------------
# Bird spinner for loading animation
# ---------------------------------------------------------------------------

_BIRD_SPINNER_FRAMES = [
    "🪶  ", " 🪶 ", "  🪶", " 🪶 ",
    "🦅  ", " 🦅 ", "  🦅", " 🦅 ",
    "🐦  ", " 🐦 ", "  🐦", " 🐦 ",
]


class BirdSpinner:
    """An animated bird spinner that flutters during setup operations."""

    def __init__(self, message: str = "Getting ready...") -> None:
        self.message = message
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the spinner animation in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self, final_message: str | None = None) -> None:
        """Stop the spinner and optionally print a final message."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if final_message:
            # Clear the spinner line and print final message
            print(f"\r{' ' * (len(self.message) + 10)}\r  {final_message}")

    def _animate(self) -> None:
        """Run the spinner animation loop."""
        frame_idx = 0
        while not self._stop_event.is_set():
            frame = _BIRD_SPINNER_FRAMES[frame_idx % len(_BIRD_SPINNER_FRAMES)]
            print(f"\r  {frame} {self.message}", end="", flush=True)
            frame_idx += 1
            time.sleep(0.15)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_first_run(config_path: Optional[Path] = None) -> bool:
    """Check if this is the first time Dulus is being run.

    Args:
        config_path: Optional path to the config file. Uses default if None.

    Returns:
        True if no config file exists (first run), False otherwise.
    """
    from config import CONFIG_FILE
    path = config_path or CONFIG_FILE
    return not path.exists()


def _get_time_greeting() -> str:
    """Return a time-of-day appropriate greeting.

    Returns:
        A warm greeting string based on the current local hour.
    """
    hour = datetime.now().hour
    if 5 <= hour < 12:
        import random
        return random.choice(_MORNING_GREETINGS)
    elif 12 <= hour < 17:
        import random
        return random.choice(_AFTERNOON_GREETINGS)
    elif 17 <= hour < 21:
        import random
        return random.choice(_EVENING_GREETINGS)
    else:
        import random
        return random.choice(_NIGHT_GREETINGS)


def _get_random_message(category: str, key: str, name: str = "friend") -> str:
    """Get a random message from the welcome message library.

    Args:
        category: Message category ('first_run' or 'returning').
        key: Message key within the category.
        name: User's name for personalization.

    Returns:
        A randomly selected, personalized message string.
    """
    import random
    messages = _WELCOME_MESSAGES.get(category, {}).get(key, [""])
    msg = random.choice(messages)
    return msg.format(name=name)


def _get_motivational_quote() -> str:
    """Get a random motivational quote."""
    import random
    return random.choice(_MOTIVATIONAL_QUOTES)


# ---------------------------------------------------------------------------
# Provider menu (unchanged API for compatibility)
# ---------------------------------------------------------------------------

_PROVIDER_MENU = [
    ("ollama",     "Ollama (local, free)",                    "gemma3:latest",                  False),
    ("nvidia-web", "NVIDIA NIM (14 free models)",             "llama-3.3-70b-instruct",         True),
    ("anthropic",  "Anthropic Claude",                         "claude-sonnet-4-6",              True),
    ("kimi-code",  "Kimi for Coding (kimi.com/coding)",        "kimi-for-coding",                True),
    ("kimi",       "Moonshot Kimi K2 (general)",               "kimi-k2.5",                      True),
    ("openai",     "OpenAI (GPT-4o / o3)",                     "gpt-4o",                         True),
    ("gemini",     "Google Gemini",                            "gemini-2.0-flash",               True),
    ("deepseek",   "DeepSeek",                                 "deepseek-chat",                  True),
    ("litellm",    "LiteLLM gateway (100+ providers via one API)", "openrouter/anthropic/claude-3-5-sonnet", True),
]


def _prompt(question: str, default: str = "") -> str:
    """Prompt the user for text input with a default value.

    Args:
        question: The prompt text to display.
        default: Default value returned if user presses Enter.

    Returns:
        The user's input, or the default if empty.
    """
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"{question}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return raw or default


def _prompt_choice(question: str, choices: list[tuple[str, str]], default_idx: int = 0) -> int:
    """Display a numbered menu and get user selection.

    Args:
        question: The question to display above choices.
        choices: List of (value, label) tuples.
        default_idx: Index of the default selection.

    Returns:
        The selected index (0-based).
    """
    print(f"\n{question}")
    for i, (_v, label) in enumerate(choices, 1):
        marker = ">" if (i - 1) == default_idx else " "
        print(f"  {marker} {i}. {label}")
    for _ in range(3):
        raw = _prompt("Your choice", str(default_idx + 1))
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(choices):
                return n - 1
        print("  (invalid number)")
    return default_idx


def _prompt_secret(question: str) -> str:
    """Prompt for a secret value (password/API key) without echoing.

    Args:
        question: The prompt text to display.

    Returns:
        The entered secret string.
    """
    try:
        import getpass
        return getpass.getpass(f"{question}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    except Exception:
        return _prompt(question)


def _mempalace_available() -> bool:
    """Check if MemPalace is installed and available.

    Returns:
        True if mempalace module and CLI are both available.
    """
    try:
        __import__("mempalace")
    except Exception:
        return False
    return shutil.which("mempalace") is not None


def _run_mempalace_init() -> bool:
    """Initialize MemPalace for persistent memory storage.

    Returns:
        True if initialization succeeded, False otherwise.
    """
    try:
        try:
            # Resolve live: USER_MEMORY_DIR is frozen at import time and goes
            # stale if DULUS_HOME changed after startup.
            from memory.store import get_memory_dir
            target_dir = get_memory_dir("user")
        except Exception:
            from config import CONFIG_DIR
            target_dir = CONFIG_DIR / "memory"
        target_dir.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            ["mempalace", "init", str(target_dir), "--yes", "--auto-mine"],
            env=env,
            timeout=120,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("  OK MemPalace initialized")
            return True
        print(f"  ! mempalace init failed (exit {result.returncode}): {result.stderr.strip()[:200]}")
        return False
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"  ! mempalace init error: {e}")
        return False


# ---------------------------------------------------------------------------
# Welcome banner display
# ---------------------------------------------------------------------------


def show_welcome_banner(user_name: str = "friend", is_returning: bool = False) -> None:
    """Display a warm, bird-themed welcome banner.

    This is the 'hug' that greets users when they start Dulus --
    whether it's their first time or they're coming back.

    Args:
        user_name: The user's preferred name.
        is_returning: True if the user has used Dulus before.
    """
    import random

    print()
    print(CIGUA_ASCII)
    print()

    # Time-based greeting
    print(f"  {_get_time_greeting()}")
    print()

    if is_returning:
        # Warm welcome back for returning users
        greeting = random.choice(_WELCOME_MESSAGES["returning"]["greeting"])
        print(f"  {greeting.format(name=user_name)}")
        print()
        boost = random.choice(_WELCOME_MESSAGES["returning"]["mood_boost"])
        print(f"  {boost}")
        print()
        # Add a motivational quote
        print(f"  {_get_motivational_quote()}")
    else:
        # Enthusiastic first-run welcome
        greeting = random.choice(_WELCOME_MESSAGES["first_run"]["greeting"])
        print(f"  {greeting}")
        print()
        for intro_msg in _WELCOME_MESSAGES["first_run"]["intro"]:
            print(f"  {intro_msg}")
        print()
        for no_key_msg in _WELCOME_MESSAGES["first_run"]["no_api_key"]:
            print(f"  {no_key_msg}")
        print()
        # Add a motivational quote
        print(f"  {_get_motivational_quote()}")
        print()
        # Show tips
        for tip in _WELCOME_MESSAGES["first_run"]["tips"]:
            print(f"  {tip}")

    print()
    print("  " + "-" * 60)
    print()


# ---------------------------------------------------------------------------
# Main welcome wizard
# ---------------------------------------------------------------------------


def run_welcome_wizard(config: dict) -> dict:
    """Run the warm, friendly welcome wizard for first-time users.

    Guides new users through a 30-second setup:
      1. Personal greeting with bird art
      2. Name preference
      3. Provider + model selection
      4. API key prompting (when needed)
      5. Web-harvest feature pitch
      6. MemPalace initialization
      7. Soul seeding with personalized personality

    Args:
        config: The Dulus configuration dictionary to populate.

    Returns:
        The updated configuration dictionary.
    """
    if not sys.stdin.isatty():
        print("(non-interactive stdin detected -- run `dulus setup` when you have a terminal)")
        return config

    # Check if this might be a returning user (config exists but is minimal)
    user_name = config.get("user_name", "")
    is_returning = bool(user_name) and user_name != "amigo"

    # Show the warm welcome banner
    show_welcome_banner(user_name=user_name or "friend", is_returning=is_returning)

    if is_returning:
        print(f"  Great to see you again, {user_name}! Let's make sure everything is set up.")
    else:
        # Step 0: Get the user's name (first time only)
        user_name = _prompt("How should I call you? (What should I call you?)", "friend")
        if not user_name or user_name.lower() in ("friend", "amigo", ""):
            user_name = "friend"
        config["user_name"] = user_name
        print(f"\n  Nice to meet you, {user_name}! 🪶")
        print()

    # Animated spinner for provider selection
    spinner = BirdSpinner("Preparing your flight...")
    spinner.start()
    time.sleep(0.5)  # Brief dramatic pause
    spinner.stop("All set! Let's pick your AI engine.")

    # Provider selection
    choices = [(p, label) for p, label, _m, _k in _PROVIDER_MENU]
    idx = _prompt_choice("Which provider would you like to use?", choices, default_idx=0)
    provider, _label, default_model, needs_key = _PROVIDER_MENU[idx]

    # LiteLLM special flow
    if provider == "litellm":
        _setup_litellm(config, default_model)
    else:
        _setup_standard_provider(config, provider, default_model, needs_key)

    # Free local AI (Ollama + Qwen). Replaces the old browser web-harvest pitch,
    # which needed Playwright and spammed "playwright not found" when missing.
    # The browser /harvest flow still exists on demand — it just isn't the
    # default first-run path anymore.
    _setup_local_ai(config)

    # MemPalace initialization
    spinner = BirdSpinner("Setting up your memory palace...")
    spinner.start()
    if _mempalace_available():
        spinner.stop()
        print("\n  I see MemPalace is installed -- let me initialize your memory...")
        _run_mempalace_init()
    else:
        spinner.stop()
        print("\n  (MemPalace not installed -- optional. Install with: pip install dulus[memory])")

    # Seed the soul with personalized personality
    spinner = BirdSpinner("Crafting my personality just for you...")
    spinner.start()
    try:
        from soul import seed_soul_file
        seeded = seed_soul_file(user_name=user_name)
        if seeded:
            spinner.stop(f"Personality ready! Your Dulus is unique to you, {user_name}.")
        else:
            spinner.stop("Personality already set! Using your existing soul.")
    except Exception as e:
        spinner.stop(f"Note: Soul seeding skipped ({e})")

    # Signal to run /doctor on next boot
    config["pending_first_run_doctor"] = True

    print()
    print("  " + "=" * 60)
    print(f"  🦅 All set, {user_name}! Your Dulus is ready to fly!")
    print(f"  {_get_motivational_quote()}")
    print("  Run /doctor to see your health snapshot.")
    print("  " + "=" * 60)
    print()

    return config


def _setup_litellm(config: dict, default_model: str) -> None:
    """Configure LiteLLM gateway provider.

    Handles installation check, model string input, and backend API key.

    Args:
        config: The Dulus configuration dictionary to update.
        default_model: Default LiteLLM model string.
    """
    # Check if litellm is installed
    try:
        import importlib.util as _iu, litellm as _ll  # type: ignore
        _ok = bool(_iu.find_spec("litellm")) and hasattr(_ll, "completion")
    except Exception:
        _ok = False

    if not _ok:
        print("\n  LiteLLM is not installed in this Python.")
        ans = _prompt("Install it now? (recommended) [Y/n]", "Y")
        if ans.lower().startswith("y"):
            print("\n  Installing litellm... (~30s)")
            spinner = BirdSpinner("Installing LiteLLM...")
            spinner.start()
            r = subprocess.run(
                __import__("common").pip_install_cmd("-U", "litellm"),
                capture_output=True,
                text=True,
            )
            spinner.stop()
            if r.returncode != 0:
                print("  ! pip install failed -- you can retry manually:")
                print("    pip install -U litellm")
            else:
                print("  OK litellm installed.")
        else:
            print("  (Skipped -- install later with: pip install dulus[litellm])")

    # Get model string
    model_full = _prompt(
        "LiteLLM model (format: `backend/model`)",
        default_model,
    )
    if model_full.startswith("litellm/"):
        model_full = model_full[len("litellm/"):]
    config["model"] = f"litellm/{model_full}"

    # Detect backend and get API key
    backend = model_full.split("/", 1)[0] if "/" in model_full else ""
    _backend_env = {
        "openrouter":   "OPENROUTER_API_KEY",
        "groq":         "GROQ_API_KEY",
        "together_ai":  "TOGETHER_API_KEY",
        "perplexity":   "PERPLEXITYAI_API_KEY",
        "cohere":       "COHERE_API_KEY",
        "mistral":      "MISTRAL_API_KEY",
        "fireworks_ai": "FIREWORKS_API_KEY",
        "xai":          "XAI_API_KEY",
        "anyscale":     "ANYSCALE_API_KEY",
        "deepinfra":    "DEEPINFRA_API_KEY",
        "replicate":    "REPLICATE_API_KEY",
        "openai":       "OPENAI_API_KEY",
        "anthropic":    "ANTHROPIC_API_KEY",
        "gemini":       "GEMINI_API_KEY",
    }
    env_var = _backend_env.get(backend, "")
    if backend and env_var and os.environ.get(env_var):
        print(f"  OK Using {env_var} from environment for backend '{backend}'")
    elif backend:
        key = _prompt_secret(f"API key for '{backend}' (Enter to skip)")
        if key:
            config[f"{backend}_api_key"] = key
            print(f"  OK Key saved as {backend}_api_key")


def _setup_standard_provider(config: dict, provider: str, default_model: str, needs_key: bool) -> None:
    """Configure a standard (non-LiteLLM) provider.

    Args:
        config: The Dulus configuration dictionary to update.
        provider: The selected provider identifier.
        default_model: Default model name for this provider.
        needs_key: Whether this provider requires an API key.
    """
    model = _prompt("Model", default_model)
    if "/" in model:
        model = model.split("/", 1)[1]
    config["model"] = f"{provider}/{model}"

    if needs_key:
        try:
            from providers import PROVIDERS
            env_var = PROVIDERS.get(provider, {}).get("api_key_env", "")
        except Exception:
            env_var = ""
        if env_var and os.environ.get(env_var):
            print(f"  OK Using {env_var} from environment")
        else:
            key = _prompt_secret(f"API key for {provider} (Enter to skip)")
            if key:
                config[f"{provider}_api_key"] = key
                print("  OK Key saved (encrypted in config.json)")


# ── Local AI (Ollama) first-run setup ──────────────────────────────────────
# Qwen2.5-Coder catalog for local Ollama (Dulus is a coding agent).
# (model_tag, approx_download_size, min_ram_gb, human_label)
_OLLAMA_MODELS = [
    ("qwen2.5-coder:0.5b", "0.4 GB",  3,  "tiny — runs on almost anything"),
    ("qwen2.5-coder:1.5b", "1.0 GB",  4,  "small — light laptops"),
    ("qwen2.5-coder:3b",   "1.9 GB",  8,  "balanced — everyday coding"),
    ("qwen2.5-coder:7b",   "4.7 GB",  16, "strong — the sweet spot"),
    ("qwen2.5-coder:14b",  "9.0 GB",  32, "big — workstation / good GPU"),
]


def _detect_hardware() -> dict:
    """Best-effort, dependency-free hardware probe for model sizing."""
    info = {"ram_gb": 0.0, "cores": os.cpu_count() or 1, "gpu": "", "arch": platform.machine()}
    ram = 0.0
    try:
        import psutil  # optional dependency
        ram = psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        try:
            if os.name == "nt":
                import ctypes

                class _MS(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                ms = _MS()
                ms.dwLength = ctypes.sizeof(_MS)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))  # type: ignore[attr-defined]
                ram = ms.ullTotalPhys / (1024 ** 3)
            else:
                ram = (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) / (1024 ** 3)
        except Exception:
            ram = 0.0
    info["ram_gb"] = round(ram, 1)
    try:
        if shutil.which("nvidia-smi"):
            info["gpu"] = "nvidia"
        elif platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64"):
            info["gpu"] = "apple-silicon"  # unified memory — great for local LLMs
    except Exception:
        pass
    return info


def _recommend_model(hw: dict) -> tuple[str, str, str]:
    """Pick the largest Qwen that fits RAM (with a GPU/unified-memory bump)."""
    ram = hw.get("ram_gb") or 0.0
    budget = ram + (8 if hw.get("gpu") else 0)  # GPU users can punch above raw RAM
    tag, size, label = _OLLAMA_MODELS[0][0], _OLLAMA_MODELS[0][1], _OLLAMA_MODELS[0][3]
    for m_tag, m_size, min_ram, m_label in _OLLAMA_MODELS:
        if budget >= min_ram:
            tag, size, label = m_tag, m_size, m_label
    return tag, size, label


def _ensure_ollama_installed() -> bool:
    """True if the `ollama` CLI is available; offer to install it if not."""
    if shutil.which("ollama"):
        return True
    print("\n  Ollama isn't installed yet (it's the free local-model runtime).")
    system = platform.system()
    if system == "Windows":
        cmd, hint = ["winget", "install", "--id", "Ollama.Ollama", "-e"], "winget install Ollama.Ollama"
    elif system == "Darwin":
        if shutil.which("brew"):
            cmd, hint = ["brew", "install", "ollama"], "brew install ollama"
        else:
            cmd, hint = None, "download from https://ollama.com/download"
    else:  # Linux
        cmd, hint = None, "curl -fsSL https://ollama.com/install.sh | sh"

    ans = _prompt(f"  Install it now? ({hint}) [Y/n]", "y").strip().lower()
    if ans not in ("y", "yes", "s", "si", ""):
        print("  Skipped. Install Ollama anytime from https://ollama.com/download, then run `dulus setup`.")
        return False
    try:
        if cmd and shutil.which(cmd[0]):
            print("  Installing Ollama — this can take a minute…")
            subprocess.run(cmd, check=False)
        elif system == "Linux":
            subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=False)
        else:
            print("  Please install from https://ollama.com/download , then re-run `dulus setup`.")
            return False
    except Exception as e:
        print(f"  Couldn't auto-install ({e}). Get it at https://ollama.com/download")
        return False
    if shutil.which("ollama"):
        return True
    print("  Ollama installed — reopen your terminal so it lands on PATH, then run `dulus setup`.")
    return False


def _ollama_pull(model: str) -> bool:
    """Pull a model with live progress. True on success."""
    try:
        print(f"\n  Downloading {model} … (Ctrl+C to skip)")
        return subprocess.run(["ollama", "pull", model], check=False).returncode == 0
    except KeyboardInterrupt:
        print(f"\n  Skipped. You can `ollama pull {model}` anytime.")
        return False
    except Exception as e:
        print(f"  Pull failed: {e}")
        return False


def _ollama_say_hola(model: str) -> "str | None":
    """Ask the model to say hi so the user sees it actually works."""
    try:
        r = subprocess.run(
            ["ollama", "run", model, "Reply with one short, friendly line in Spanish that says hola."],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        import re
        out = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout or "")  # strip ANSI codes
        # Drop blank lines and any "Thinking…" status/reasoning noise (some models
        # stream a chain-of-thought); the greeting is the last real line.
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        lines = [ln for ln in lines if not ln.lower().startswith("thinking")]
        return lines[-1][:200] if lines else None
    except Exception:
        return None


def _setup_local_ai(config: dict) -> None:
    """First-run local-AI setup: Ollama + a right-sized Qwen model.

    Replaces the old browser web-harvest pitch (which needed Playwright and
    was noisy — 'playwright not found' — when it wasn't installed). Local
    models are free, private, and work offline: no API key, no browser.
    """
    print()
    print("-" * 60)
    print("  ✨ Free local AI — private, offline, no API key, no browser.")
    print("     Powered by Ollama + Qwen, right-sized to your machine.")
    print("-" * 60)

    hw = _detect_hardware()
    ram_txt = f"{hw['ram_gb']:.0f} GB RAM" if hw.get("ram_gb") else "RAM: unknown"
    gpu_txt = {"nvidia": " + NVIDIA GPU", "apple-silicon": " + Apple Silicon"}.get(hw.get("gpu", ""), "")
    print(f"\n  Your machine: {ram_txt}, {hw['cores']} cores{gpu_txt}")

    rec_tag, rec_size, rec_why = _recommend_model(hw)
    print(f"  Recommended:  {rec_tag}  ({rec_size}) — {rec_why}\n")
    print("  Local model options (Qwen2.5-Coder):")
    for tag, size, _min, label in _OLLAMA_MODELS:
        marker = "→" if tag == rec_tag else " "
        print(f"    {marker} {tag:<22} {size:>8}   {label}")
    print()

    choice = _prompt(
        f"Set up local AI now? Enter for the recommended {rec_tag}, "
        f"type another tag, or 'no' to skip",
        rec_tag,
    ).strip()
    if choice.lower() in ("no", "n", "skip", "later"):
        print("  Skipped local AI. Set it up anytime with `dulus setup` or `/model`.")
        print("  (Prefer a cloud key or the browser /harvest flow? Both still work.)")
        return

    model = choice or rec_tag
    if not _ensure_ollama_installed():
        return
    if not _ollama_pull(model):
        return

    config["model"] = f"ollama/{model}"  # base_url defaults to localhost:11434 in the provider

    print("\n  Testing it (asking it to say hi)…")
    reply = _ollama_say_hola(model)
    if reply:
        print(f"  🗣️  {model}: {reply.splitlines()[0][:120]}")
        print(f"\n  ✅ Local AI ready — Dulus is now using ollama/{model}, free and offline.")
    else:
        print(f"  Model pulled. The hello test returned nothing, but it should work via /model.")


def _pitch_web_harvest(config: dict) -> None:
    """Pitch Dulus's killer web-harvest feature.

    This is the wow moment: free AI from browser sessions with zero setup.

    Args:
        config: The Dulus configuration dictionary to update with harvest preference.
    """
    print()
    print("-" * 60)
    print("  ✨ Dulus's superpower: Free AI, right now, no API key needed!")
    print()
    print("     I can open your browser, you type 'hi' once, and boom --")
    print("     free AI powered by Gemini guest / Claude.ai / Kimi / Qwen / DeepSeek.")
    print("-" * 60)
    harvest_choice = _prompt(
        "Want to try it NOW with free Gemini (no login)? "
        "[gemini] / claude / kimi / qwen / deepseek / no",
        "gemini",
    ).strip().lower()

    if harvest_choice in ("claude", "kimi", "gemini", "qwen", "deepseek"):
        config["pending_first_run_harvest"] = harvest_choice
        print(f"  OK -- I'll run /harvest-{harvest_choice} as soon as the REPL starts!")
    elif harvest_choice in ("yes", "si", "y", "s", ""):
        config["pending_first_run_harvest"] = "gemini"
        print("  OK -- I'll run /harvest-gemini as soon as the REPL starts!")
    else:
        print("  Skipped. You can run it anytime with /harvest-gemini (or /harvest, /harvest-kimi, etc.)")
