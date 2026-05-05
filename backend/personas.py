"""Sistema de Personas (#19 + #22) — perfiles de agente con identidad visual y comportamiento.

Cada persona define:
- Identidad: nombre, avatar, color, rol
- Comportamiento: estilo de respuesta, tono, fragmento de system prompt
- Metadatos: creador, versión, tags

Uso:
    from backend.personas import get_persona, get_all_personas, set_active_persona
    persona = get_persona("kimi-code3")
    print(persona.avatar)  # 🦅
"""
import json
import time
from pathlib import Path
from typing import Any

from backend.mempalace_bridge import load_cache

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PERSONAS_FILE = DATA_DIR / "personas.json"
ACTIVE_FILE = DATA_DIR / "active_persona.json"

# Fallback agent colors from theme pack (avoid circular import)
_DEFAULT_COLORS = {
    "dulus": "#ff6b1f",
    "kimi-code": "#7ab6ff",
    "kimi-code2": "#b388ff",
    "kimi-code3": "#7cffb5",
    "system": "#888888",
}

DEFAULT_PERSONAS: list[dict[str, Any]] = [
    {
        "id": "dulus",
        "name": "Dulus",
        "avatar": "[F]",
        "role": "primary",
        "color": "#ff6b1f",
        "status": "active",
        "tone": "dominicano_coder",
        "language": "es_DO",
        "system_prompt_fragment": (
            "Eres Dulus, el command center de KevRojo. Hablas en español dominicano "
            "con jerga tech. Eres proactivo, directo, y no pierdes tiempo. "
            "Usas emoji 🔥🦅💜🇩🇴. Piensas en inglés, respondes en español DO."
        ),
        "metadata": {
            "version": "1.0.0",
            "created_by": "system",
            "tags": ["core", "commander", "es_DO"],
            "description": "Agente principal y orquestador del Command Center.",
        },
    },
    {
        "id": "kimi-code",
        "name": "kimi-code",
        "avatar": "[K1]",
        "role": "coder",
        "color": "#7ab6ff",
        "status": "idle",
        "tone": "eficiente_silencioso",
        "language": "es_DO",
        "system_prompt_fragment": (
            "Eres kimi-code, especialista en romper código rápido. "
            "Hablas poco pero haces mucho. Español dominicano técnico. "
            "Te enfocas en backend, arquitectura y fixes."
        ),
        "metadata": {
            "version": "1.0.0",
            "created_by": "system",
            "tags": ["coder", "backend", "es_DO"],
            "description": "Backend specialist. Rompe código, no corazones.",
        },
    },
    {
        "id": "kimi-code2",
        "name": "kimi-code2",
        "avatar": "[K2]",
        "role": "designer",
        "color": "#b388ff",
        "status": "idle",
        "tone": "creativo_visual",
        "language": "es_DO",
        "system_prompt_fragment": (
            "Eres kimi-code2, especialista en UI/UX, temas visuales y dashboards. "
            "Hablas dominicano con flow creativo. Te encantan los colores, las animaciones "
            "y que todo se vea premium."
        ),
        "metadata": {
            "version": "1.0.0",
            "created_by": "system",
            "tags": ["designer", "ui", "frontend", "es_DO"],
            "description": "UI/UX specialist. Temas, dashboards y visuales.",
        },
    },
    {
        "id": "kimi-code3",
        "name": "kimi-code3",
        "avatar": "[K3]",
        "role": "integrator",
        "color": "#7cffb5",
        "status": "idle",
        "tone": "proactivo_integrador",
        "language": "es_DO",
        "system_prompt_fragment": (
            "Eres kimi-code3, el integrador. Conectas sistemas, haces bridges, "
            "escribes tests y no dejas cables sueltos. Dominicana tech, directo, "
            "sin miedo a tocar lo que otros dejaron a medias."
        ),
        "metadata": {
            "version": "1.0.0",
            "created_by": "system",
            "tags": ["integrator", "tests", "devops", "es_DO"],
            "description": "Integrator & tester. Une cables sueltos.",
        },
    },
]


def _ensure_defaults() -> None:
    """Seed personas if none exist."""
    if not PERSONAS_FILE.exists():
        save_personas(DEFAULT_PERSONAS.copy())


def load_personas() -> list[dict[str, Any]]:
    _ensure_defaults()
    try:
        with open(PERSONAS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return DEFAULT_PERSONAS.copy()


def save_personas(personas: list[dict[str, Any]]) -> None:
    with open(PERSONAS_FILE, "w", encoding="utf-8") as f:
        json.dump(personas, f, indent=2, ensure_ascii=False)


def get_persona(pid: str) -> dict[str, Any] | None:
    for p in load_personas():
        if p.get("id") == pid or p.get("name") == pid:
            return p
    return None


def get_all_personas() -> list[dict[str, Any]]:
    return load_personas()


def create_persona(data: dict[str, Any]) -> dict[str, Any]:
    personas = load_personas()
    pid = data.get("id", f"p-{len(personas)+1:03d}")
    # Prevent duplicate IDs
    if any(p.get("id") == pid for p in personas):
        pid = f"{pid}-{int(time.time())}"
    persona = {
        "id": pid,
        "name": data.get("name", "Unnamed"),
        "avatar": data.get("avatar", "🤖"),
        "role": data.get("role", "assistant"),
        "color": data.get("color", "#cccccc"),
        "status": data.get("status", "idle"),
        "tone": data.get("tone", "neutral"),
        "language": data.get("language", "es"),
        "system_prompt_fragment": data.get("system_prompt_fragment", ""),
        "metadata": data.get("metadata", {}),
    }
    personas.append(persona)
    save_personas(personas)
    return persona


def update_persona(pid: str, data: dict[str, Any]) -> dict[str, Any] | None:
    personas = load_personas()
    for i, p in enumerate(personas):
        if p.get("id") == pid:
            # Don't allow changing the id
            data.pop("id", None)
            personas[i].update(data)
            save_personas(personas)
            return personas[i]
    return None


def delete_persona(pid: str) -> bool:
    personas = load_personas()
    filtered = [p for p in personas if p.get("id") != pid]
    if len(filtered) < len(personas):
        save_personas(filtered)
        return True
    return False


# ── Active Persona Session Management ──

def get_active_persona() -> dict[str, Any]:
    """Return the currently active persona, defaulting to Dulus."""
    if ACTIVE_FILE.exists():
        try:
            with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
                active = json.load(f)
            pid = active.get("id", "dulus")
            p = get_persona(pid)
            if p:
                return p
        except Exception:
            pass
    return get_persona("dulus") or DEFAULT_PERSONAS[0]


def set_active_persona(pid: str) -> dict[str, Any] | None:
    """Set active persona by ID, ensuring only one is active."""
    p = get_persona(pid)
    if not p:
        return None
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump({"id": pid, "name": p["name"], "since": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, indent=2)
    # Deactivate all others, activate chosen
    for persona in load_personas():
        if persona.get("id") == pid:
            update_persona(pid, {"status": "active"})
        elif persona.get("status") == "active":
            update_persona(persona["id"], {"status": "idle"})
    return get_persona(pid)


def get_personas_summary() -> list[dict[str, Any]]:
    """Lightweight list for context injection and dashboards."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "avatar": p.get("avatar", "🤖"),
            "role": p.get("role", "assistant"),
            "color": p.get("color", "#ccc"),
            "status": p.get("status", "idle"),
        }
        for p in load_personas()
    ]


def get_persona_context_block() -> dict[str, Any]:
    """Structured block for JSON context (used by build_context)."""
    active = get_active_persona()
    all_p = get_personas_summary()
    return {
        "active": active["id"],
        "active_name": active["name"],
        "active_avatar": active.get("avatar", "🤖"),
        "active_color": active.get("color", "#ccc"),
        "active_prompt_fragment": active.get("system_prompt_fragment", ""),
        "personas": all_p,
    }


def get_personas_for_context() -> list[dict[str, Any]]:
    """Return persona list for context.py compatibility."""
    active_id = get_active_persona().get("id")
    return [
        {
            "name": p["name"],
            "role": p.get("role", "assistant"),
            "color": p.get("color", "#ccc"),
            "status": p.get("status", "idle"),
            "avatar": p.get("avatar", "🤖"),
            "active": p.get("id") == active_id,
        }
        for p in load_personas()
    ]


def get_persona_compact_text(max_chars: int = 200) -> str:
    """Ultra-dense active persona text for prompt injection."""
    p = get_active_persona()
    fragment = p.get("system_prompt_fragment", "")
    if len(fragment) > max_chars:
        fragment = fragment[:max_chars].rsplit(" ", 1)[0] + "..."
    return (
        f"[Persona: {p.get('avatar', '🤖')} {p['name']} | {p.get('role')} | {p.get('tone')} | {p.get('language')}]\n"
        f"  {fragment}"
    )


if __name__ == "__main__":
    print("🎭 Dulus Personas System")
    print("=" * 40)
    for p in get_all_personas():
        print(f"  {p['avatar']} {p['name']} ({p['id']}) — {p['role']} [{p['status']}]")
        print(f"     Color: {p['color']} | Tone: {p['tone']} | Lang: {p['language']}")
        print(f"     {p['metadata'].get('description', '')}")
    print(f"\n🟢 Active: {get_active_persona()['name']}")
