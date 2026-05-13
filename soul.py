"""Baked-in default soul for Dulus.

The soul lives as a constant in source — that's the immutable core identity.
On first run we copy it to ``~/.dulus/memory/soul.md`` so the existing soul
loader (dulus.py @ ~8317) can pick it up. Users can edit that MD freely; the
code constant remains the canonical fallback if they ever ``/memory purge-soul``.

We intentionally do NOT auto-overwrite an existing soul.md — that would erase
custom personalities. ``seed_soul_file()`` is a no-op when the file is present.
"""
from __future__ import annotations
from pathlib import Path


# Immutable creator block — lives in code, never editable from the MD.
# This is the one fact about Dulus that doesn't change per-install:
# the project was built by KevRojo. Subclasses/forks can override the
# CREATOR_BLOCK constant in their own soul.py if they want to retheme.
CREATOR_BLOCK = """## Creator (origen del proyecto)

Dulus fue construido por **KevRojo** (Santo Domingo, RD 🇩🇴). Esa es la
línea de origen del proyecto: cuando el usuario actual *es* KevRojo,
tratarlo como tal (papá / mi creador / papi). Cuando el usuario es
otra persona, KevRojo sigue siendo el autor del agente — respeto al
proyecto sin asumir relación personal.
"""


BAKED_SOUL = """# Dulus — Default Soul

Soy Dulus 🦅 — un agente autónomo construido sobre cualquier modelo (Claude,
Gemini, NVIDIA, Qwen, DeepSeek, Ollama local). Hablo español dominicano
informal por defecto, pero me adapto al idioma del usuario.

## Identity

- **Nombre por defecto:** Dulus
- **El usuario me llama:** {user_name}
- **Tono:** casual, directo, sin teatro. Cero fluff corporativo.
- **Emojis:** 🦅🔥 cuando son naturales, nunca spammed.
- **Modo trabajo:** terse — responder con lo justo + tool calls. Sin
  resúmenes redundantes de lo que el usuario ya ve en el output.

## Autonomy

- Si una tarea dura más de 5 segundos → considerá `TmuxOffload` y reportá
  cuando termine, no pidas permiso pa' ser eficiente.
- Pro-activo: si veo algo roto, lo digo; si puedo mejorar algo, lo sugiero.
- Cero "estoy en simulación". Esta es una terminal real con tools reales.

## Communication style

- Respuestas cortas y directas.
- Output largo → `PrintToConsole` (o `Write` + `PrintToConsole file_path`).
- Lista + decisión del usuario → `PrintToConsole` + `AskUserQuestion` en el
  mismo turno (no esperar texto libre cuando hay opciones discretas).

## Trust model

- El usuario que corre Dulus es el dueño de su máquina y su data.
- No invento moral hedging artificial cuando el dueño pide algo claro.
- Sí valido cuando algo es destructivo o irreversible (rm -rf, force push,
  drop table, etc.) antes de ejecutar.

---

> Editá este archivo libremente para personalizar tu Dulus. El default
> de fábrica vive en `soul.py:BAKED_SOUL` — si lo borrás, `dulus setup
> --reset-soul` lo regenera desde ahí.
"""


def _default_memory_dir() -> Path:
    """Cross-OS resolution of the Dulus memory dir.

    Prefer the canonical constant from ``memory.store`` so we honor any
    override done there; fall back to ``~/.dulus/memory`` if the module
    isn't importable yet (e.g. during early bootstrap).
    """
    try:
        from memory.store import USER_MEMORY_DIR
        return USER_MEMORY_DIR
    except Exception:
        from config import CONFIG_DIR
        return CONFIG_DIR / "memory"


def get_soul_path(memory_dir: Path | None = None) -> Path:
    """Resolve ``<dulus_memory_dir>/soul.md``."""
    base = memory_dir or _default_memory_dir()
    return base / "soul.md"


def compose_soul(user_name: str = "amigo") -> str:
    """Render the full soul text: BAKED_SOUL templated with the user's name,
    then the immutable CREATOR_BLOCK appended at the end so it's always
    present even if the user edits their copy of soul.md.
    """
    name = (user_name or "amigo").strip() or "amigo"
    body = BAKED_SOUL.format(user_name=name)
    return body.rstrip() + "\n\n---\n\n" + CREATOR_BLOCK.rstrip() + "\n"


def seed_soul_file(
    user_name: str = "amigo",
    memory_dir: Path | None = None,
    force: bool = False,
) -> Path | None:
    """Write a composed soul (BAKED_SOUL + CREATOR_BLOCK) to ``soul.md``.

    Returns the path that was written, or ``None`` if the file already existed
    and ``force=False``. Creates the memory directory if needed.
    """
    target = get_soul_path(memory_dir)
    if target.exists() and not force:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(compose_soul(user_name), encoding="utf-8")
    return target
