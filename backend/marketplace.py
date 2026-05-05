"""Plugin Marketplace — esqueleto y registry de plugins disponibles. (#20)

Este módulo maneja:
- Registry local de plugins conocidos
- Metadatos de plugins del marketplace
- Instalación simulada/remota de plugins
"""
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
MARKETPLACE_FILE = DATA_DIR / "marketplace.json"

# Plugins pre-registrados en el marketplace oficial
DEFAULT_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "mp-themes",
        "name": "Theme Switcher",
        "version": "1.0.0",
        "author": "Dulus Team",
        "description": "Switch between Cyberpunk, Sakura, Sunset and Gold themes in real-time.",
        "tags": ["ui", "themes", "dashboard"],
        "downloads": 420,
        "rating": 4.8,
        "installed": False,
        "source": "builtin",
    },
    {
        "id": "mp-git-stats",
        "name": "Git Stats Visualizer",
        "version": "0.9.0",
        "author": "kimi-code",
        "description": "Visualize commit history, contributor stats and code churn.",
        "tags": ["git", "visualization", "stats"],
        "downloads": 128,
        "rating": 4.5,
        "installed": False,
        "source": "community",
    },
    {
        "id": "mp-agent-profiles",
        "name": "Agent Profiles",
        "version": "1.1.0",
        "author": "kimi-code2",
        "description": "Personas system with avatars, colors and identity per agent.",
        "tags": ["agents", "personas", "identity"],
        "downloads": 256,
        "rating": 4.9,
        "installed": False,
        "source": "community",
    },
    {
        "id": "mp-mempalace-bridge",
        "name": "MemPalace Bridge",
        "version": "0.5.0",
        "author": "Dulus Team",
        "description": "Connect Smart Context to MemPalace for infinite agent memory.",
        "tags": ["memory", "integration", "mempalace"],
        "downloads": 69,
        "rating": 4.2,
        "installed": False,
        "source": "official",
    },
]


def load_registry() -> list[dict[str, Any]]:
    if MARKETPLACE_FILE.exists():
        try:
            with open(MARKETPLACE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass
    save_registry(DEFAULT_REGISTRY)
    return DEFAULT_REGISTRY.copy()


def save_registry(registry: list[dict[str, Any]]) -> None:
    with open(MARKETPLACE_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def get_plugin_by_id(plugin_id: str) -> dict[str, Any] | None:
    for p in load_registry():
        if p["id"] == plugin_id:
            return p
    return None


def install_plugin(plugin_id: str) -> dict[str, Any] | None:
    registry = load_registry()
    for p in registry:
        if p["id"] == plugin_id:
            p["installed"] = True
            p["downloads"] = p.get("downloads", 0) + 1
            save_registry(registry)
            return p
    return None


def uninstall_plugin(plugin_id: str) -> dict[str, Any] | None:
    registry = load_registry()
    for p in registry:
        if p["id"] == plugin_id:
            p["installed"] = False
            save_registry(registry)
            return p
    return None


def search_plugins(query: str = "", tag: str = "") -> list[dict[str, Any]]:
    results = load_registry()
    if query:
        q = query.lower()
        results = [p for p in results if q in p["name"].lower() or q in p["description"].lower()]
    if tag:
        results = [p for p in results if tag in p.get("tags", [])]
    return results


def get_stats() -> dict[str, Any]:
    registry = load_registry()
    return {
        "total_plugins": len(registry),
        "installed": sum(1 for p in registry if p["installed"]),
        "total_downloads": sum(p.get("downloads", 0) for p in registry),
        "categories": list(set(t for p in registry for t in p.get("tags", []))),
    }


if __name__ == "__main__":
    print("🛒 Dulus Plugin Marketplace v0.1")
    print("=" * 40)
    for p in load_registry():
        status = "✅" if p["installed"] else "⬜"
        print(f"{status} {p['name']} v{p['version']} — {p['description'][:50]}...")
    print(f"\nStats: {json.dumps(get_stats(), indent=2)}")
