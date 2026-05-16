"""First-run welcome wizard for Dulus.

Kept intentionally small per scope:
  1. Pick provider + model
  2. Prompt for API key (when needed)
  3. Seed soul.md from baked default
  4. Run ``mempalace init`` if the plugin is installed

No Telegram, no TTS, no name prompt yet — those stay in their own
``dulus setup`` subcommands later.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def is_first_run(config_path: Optional[Path] = None) -> bool:
    from config import CONFIG_FILE
    path = config_path or CONFIG_FILE
    return not path.exists()


_PROVIDER_MENU = [
    ("ollama",     "Ollama (local, free)",                    "gemma3:latest",                  False),
    ("nvidia-web", "NVIDIA NIM (14 free models)",             "llama-3.3-70b-instruct",         True),
    ("anthropic",  "Anthropic Claude",                         "claude-sonnet-4-6",              True),
    ("kimi-code",  "Kimi for Coding (kimi.com/coding)",        "kimi-for-coding",                True),
    ("kimi",       "Moonshot Kimi K2 (general)",               "kimi-k2.5",                      True),
    ("openai",     "OpenAI (GPT-4o / o3)",                     "gpt-4o",                         True),
    ("gemini",     "Google Gemini",                            "gemini-2.0-flash",               True),
    ("deepseek",   "DeepSeek",                                 "deepseek-chat",                  True),
    # LiteLLM is the unified gateway — one provider entry, 100+ underlying
    # backends (OpenRouter, Groq, Together, Bedrock, Vertex, Cohere, Mistral,
    # Replicate, Anyscale, Fireworks, Perplexity, xAI, Databricks, …). The
    # user picks a litellm model-string like `openrouter/anthropic/...` and
    # LiteLLM routes to the right backend using the matching env var.
    ("litellm",    "LiteLLM gateway (100+ providers via one API)", "openrouter/anthropic/claude-3-5-sonnet", True),
]


def _prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"{question}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return raw or default


def _prompt_choice(question: str, choices, default_idx: int = 0) -> int:
    print(f"\n{question}")
    for i, (_v, label) in enumerate(choices, 1):
        marker = "›" if (i - 1) == default_idx else " "
        print(f"  {marker} {i}. {label}")
    for _ in range(3):
        raw = _prompt("Tu opcion", str(default_idx + 1))
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(choices):
                return n - 1
        print("  (numero invalido)")
    return default_idx


def _prompt_secret(question: str) -> str:
    try:
        import getpass
        return getpass.getpass(f"{question}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    except Exception:
        return _prompt(question)


def _mempalace_available() -> bool:
    try:
        __import__("mempalace")
    except Exception:
        return False
    return shutil.which("mempalace") is not None


def _run_mempalace_init() -> bool:
    try:
        # mempalace init requires a target directory — point it at the
        # Dulus memory dir so auto-mine indexes the same files Dulus reads.
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
            print("  OK MemPalace inicializado")
            return True
        print(f"  ! mempalace init fallo (exit {result.returncode}): {result.stderr.strip()[:200]}")
        return False
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"  ! mempalace init error: {e}")
        return False


BANNER = (
    "\n  Bienvenido a Dulus\n"
    "  --------------------------------------------------\n"
    "  Setup de 30 segundos. Saltas con Enter cualquier paso\n"
    "  y lo cambias despues con `dulus setup`.\n"
)


def run_welcome_wizard(config: dict) -> dict:
    if not sys.stdin.isatty():
        print("(non-interactive stdin detected - corre `dulus setup` cuando tengas terminal)")
        return config

    print(BANNER)

    # ── Step 0: name ────────────────────────────────────────────────────
    user_name = _prompt("How should I call you? (¿Cómo te llamo?)", "amigo")
    config["user_name"] = user_name

    choices = [(p, label) for p, label, _m, _k in _PROVIDER_MENU]
    idx = _prompt_choice("Que proveedor queres usar de entrada?", choices, default_idx=0)
    provider, _label, default_model, needs_key = _PROVIDER_MENU[idx]

    model = _prompt("Modelo", default_model)
    # Dulus identifies the provider via the `provider/model` prefix in config.model.
    # Strip any prefix the user typed by accident, then re-prepend the chosen one.
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
            print(f"  OK Usando {env_var} del entorno")
        else:
            key = _prompt_secret(f"API key para {provider} (Enter pa' saltar)")
            if key:
                config[f"{provider}_api_key"] = key
                print("  OK Key guardada (encriptada en config.json)")

    if _mempalace_available():
        print("\nDetecte MemPalace instalado - inicializando memoria persistente...")
        _run_mempalace_init()
    else:
        print("\n(MemPalace no instalado - opcional. Instalalo con: pip install dulus[memory])")

    try:
        from soul import seed_soul_file
        seeded = seed_soul_file(user_name=user_name)
        if seeded:
            print(f"  OK Soul sembrado para '{user_name}' en {seeded}")
    except Exception as e:
        print(f"  ! soul seeding fallo: {e}")

    # Signal the REPL to run /doctor on the next boot so the user immediately
    # sees a health snapshot — what providers got keys, what voice/TTS bits
    # are live, which optional deps are missing, etc. Cleared after the run.
    # NOTE: key MUST NOT start with "_" — save_config strips underscore-
    # prefixed keys as a runtime/in-memory convention. With a leading "_"
    # the flag was being silently dropped on disk, so /doctor never fired.
    config["pending_first_run_doctor"] = True

    print("\nListo. Voy a correr /doctor pa' que veas como quedo todo.\n")
    return config
