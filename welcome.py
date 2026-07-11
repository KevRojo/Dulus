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
            from memory.store import USER_MEMORY_DIR
            target_dir = USER_MEMORY_DIR
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

    # Web-harvest feature pitch
    _pitch_web_harvest(config)

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
