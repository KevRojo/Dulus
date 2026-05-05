"""Persona system for Dulus GUI.

Loads the canonical persona definitions from .dulus-context/personas.json
and provides helpers for retrieving persona data and rendering cards in
customtkinter interfaces.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ── Paths ───────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_JSON_PATH = _REPO_ROOT / ".dulus-context" / "personas.json"


# ── Cache ───────────────────────────────────────────────────────────────────

_persona_data: dict[str, Any] | None = None


def _load_json(path: Path | str | None = None) -> dict[str, Any]:
    """Load and cache personas.json. Raises FileNotFoundError if missing."""
    global _persona_data
    if _persona_data is not None:
        return _persona_data

    target = Path(path) if path else _DEFAULT_JSON_PATH
    with target.open("r", encoding="utf-8") as fh:
        _persona_data = json.load(fh)
    return _persona_data


def reload() -> dict[str, Any]:
    """Force reload personas.json from disk and return the raw data."""
    global _persona_data
    _persona_data = None
    return _load_json()


# ── Core API ────────────────────────────────────────────────────────────────

def get_all_personas(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Return all persona definitions as a list of dicts."""
    data = _load_json(path)
    return list(data.get("personas", []))


def get_persona(persona_id: str, path: Path | str | None = None) -> dict[str, Any] | None:
    """Return a single persona by its ``id`` (e.g. ``'kevrojo'``)."""
    for p in get_all_personas(path):
        if p.get("id") == persona_id:
            return p
    return None


def get_color_for_agent(agent_name: str, path: Path | str | None = None) -> str:
    """Return the hex color for an agent name/id (case-insensitive).

    Falls back to the default Dulus accent ``#ff6b1f`` if unknown.
    """
    lookup = agent_name.lower().strip()
    for p in get_all_personas(path):
        if p.get("id", "").lower() == lookup or p.get("name", "").lower() == lookup:
            return p.get("color", "#ff6b1f")
    return "#ff6b1f"


def get_display_name(agent_name: str, path: Path | str | None = None) -> str:
    """Return the pretty display name for an agent, or the raw name as fallback."""
    lookup = agent_name.lower().strip()
    for p in get_all_personas(path):
        if p.get("id", "").lower() == lookup or p.get("name", "").lower() == lookup:
            return p.get("display_name") or p.get("name") or agent_name
    return agent_name


# ── customtkinter Widget (optional) ─────────────────────────────────────────

try:
    import customtkinter as ctk
    _HAS_CTK = True
except Exception:  # pragma: no cover
    _HAS_CTK = False


class PersonaCard(ctk.CTkFrame if _HAS_CTK else object):  # type: ignore[misc]
    """A small card widget that displays a single persona's identity.

    Usage::

        card = PersonaCard(parent, persona=get_persona("kimi-code"))
        card.pack(padx=10, pady=10, fill="both", expand=True)
    """

    def __init__(
        self,
        master: Any,
        persona: dict[str, Any],
        width: int = 340,
        height: int = 280,
        **kwargs: Any,
    ) -> None:
        if not _HAS_CTK:
            raise RuntimeError("customtkinter is required to use PersonaCard")

        self._persona = persona
        self._color = persona.get("color", "#ff6b1f")
        self._accent = persona.get("accent_color", self._color)

        super().__init__(
            master,
            width=width,
            height=height,
            corner_radius=8,
            fg_color=("#f9f9f9", "#15151a"),
            border_width=1,
            border_color=self._color,
            **kwargs,
        )

        self._build()

    def _build(self) -> None:
        # Top accent bar
        self._top = ctk.CTkFrame(self, height=3, fg_color=self._color)
        self._top.pack(fill="x", padx=0, pady=0)

        # Header row: ASCII avatar + meta
        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.pack(fill="x", padx=12, pady=(12, 8))

        # Avatar label (monospace)
        avatar_text = self._persona.get("avatar_ascii", "?")
        self._avatar = ctk.CTkLabel(
            self._header,
            text=avatar_text,
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=self._color,
            width=120,
            height=110,
            fg_color=("#eeeeee", "#0f0f12"),
            corner_radius=6,
        )
        self._avatar.pack(side="left", padx=(0, 12))

        # Meta column
        self._meta = ctk.CTkFrame(self._header, fg_color="transparent")
        self._meta.pack(side="left", fill="both", expand=True)

        display = self._persona.get("display_name", self._persona.get("name", "???"))
        self._name_lbl = ctk.CTkLabel(
            self._meta,
            text=display,
            font=ctk.CTkFont(family="JetBrains Mono", size=16, weight="bold"),
            text_color=self._color,
            anchor="w",
        )
        self._name_lbl.pack(fill="x")

        role = self._persona.get("role", "Agent")
        self._role_lbl = ctk.CTkLabel(
            self._meta,
            text=role,
            font=ctk.CTkFont(family="JetBrains Mono", size=10),
            text_color=self._accent,
            anchor="w",
        )
        self._role_lbl.pack(fill="x", pady=(2, 6))

        ptype = self._persona.get("type", "unknown")
        self._type_lbl = ctk.CTkLabel(
            self._meta,
            text=f"● {ptype}",
            font=ctk.CTkFont(family="JetBrains Mono", size=10),
            text_color=("#888888", "#6a6470"),
            anchor="w",
        )
        self._type_lbl.pack(fill="x")

        # Catchphrase
        catch = self._persona.get("catchphrase", "")
        if catch:
            self._catch = ctk.CTkLabel(
                self,
                text=f'"{catch}"',
                font=ctk.CTkFont(family="JetBrains Mono", size=11, slant="italic"),
                text_color=("#555555", "#8a8490"),
                anchor="w",
                wraplength=300,
            )
            self._catch.pack(fill="x", padx=12, pady=(0, 8))

        # Skills tags
        skills = self._persona.get("skills", [])
        if skills:
            self._skills_frame = ctk.CTkFrame(self, fg_color="transparent")
            self._skills_frame.pack(fill="x", padx=12, pady=(0, 8))
            for skill in skills[:5]:
                tag = ctk.CTkLabel(
                    self._skills_frame,
                    text=skill,
                    font=ctk.CTkFont(family="JetBrains Mono", size=9),
                    text_color=self._color,
                    fg_color=("#eeeeee", "#0a0a0a"),
                    corner_radius=4,
                    padx=6,
                    pady=2,
                )
                tag.pack(side="left", padx=(0, 4), pady=(0, 4))


# ── Quick smoke-test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import pprint

    print("=== All personas ===")
    pprint.pprint(get_all_personas())

    print("\n=== Get persona 'kevrojo' ===")
    pprint.pprint(get_persona("kevrojo"))

    print("\n=== Color for 'kimi-code2' ===")
    print(get_color_for_agent("kimi-code2"))

    print("\n=== Display name for 'dulus' ===")
    print(get_display_name("dulus"))
