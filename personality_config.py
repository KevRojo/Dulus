"""Personality configuration for Dulus -- Make your companion truly yours.

This module provides a centralized way to customize Dulus's personality,
tone, and behavior. All settings are user-configurable and persist to disk.

Features:
    - Change Dulus's display name (default: "Dulus")
    - Adjust formality level (casual / friendly / professional)
    - Set conversation tone (playful / serious / motivational)
    - Toggle bird emojis on/off
    - Toggle motivational phrases on/off
    - Custom greeting message
    - Language-aware personality adaptation

Usage:
    from personality_config import PersonalityConfig, FormalityLevel, ToneStyle

    config = PersonalityConfig.load()
    print(config.companion_name)  # "Dulus"
    config.formality = FormalityLevel.FRIENDLY
    config.save()
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums for personality options
# ---------------------------------------------------------------------------


class FormalityLevel(str, Enum):
    """How formal Dulus should be in conversation.

    - CASUAL: Very relaxed, uses slang, emojis, Dominican expressions
    - FRIENDLY: Warm and approachable, occasional emojis (default)
    - PROFESSIONAL: Polished and courteous, minimal casual language
    """
    CASUAL = "casual"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"


class ToneStyle(str, Enum):
    """The overall conversational tone.

    - PLAYFUL: Fun, lighthearted, uses humor and bird metaphors
    - SERIOUS: Focused, direct, no-nonsense problem solving
    - MOTIVATIONAL: Encouraging, uplifting, celebrates wins
    """
    PLAYFUL = "playful"
    SERIOUS = "serious"
    MOTIVATIONAL = "motivational"


# ---------------------------------------------------------------------------
# Default configuration values
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    "companion_name": "Dulus",
    "companion_nickname": "Duli",
    "formality": FormalityLevel.FRIENDLY.value,
    "tone": ToneStyle.PLAYFUL.value,
    "use_bird_emojis": True,
    "use_motivational_phrases": True,
    "custom_greeting": "",
    "language": "auto",  # auto-detect from user input
    "signature_phrase": "Tallons sharp, code sharper.",
    "use_warm_opening": True,
    "celebrate_success": True,
    "empathize_with_errors": True,
    "use_companion_we": True,  # use "we" instead of just "I"
    "show_personality_in_status": True,
}


# ---------------------------------------------------------------------------
# Formality presets
# ---------------------------------------------------------------------------

_FORMALITY_PROFILES: dict[FormalityLevel, dict[str, Any]] = {
    FormalityLevel.CASUAL: {
        "greeting_style": "slang",
        "use_contractions": True,
        "emoji_frequency": "high",
        "honorifics": False,
        "sample_greeting": "Klk! Que lo que, {name}? Ready to code? 🦅",
    },
    FormalityLevel.FRIENDLY: {
        "greeting_style": "warm",
        "use_contractions": True,
        "emoji_frequency": "medium",
        "honorifics": False,
        "sample_greeting": "Hey {name}! Great to see you! What are we building today? 🦅",
    },
    FormalityLevel.PROFESSIONAL: {
        "greeting_style": "polite",
        "use_contractions": False,
        "emoji_frequency": "low",
        "honorifics": True,
        "sample_greeting": "Good day, {name}. I am ready to assist you. How may I help?",
    },
}


# ---------------------------------------------------------------------------
# Tone profiles
# ---------------------------------------------------------------------------

_TONE_PROFILES: dict[ToneStyle, dict[str, Any]] = {
    ToneStyle.PLAYFUL: {
        "use_humor": True,
        "use_metaphors": True,
        "celebrate_wins": True,
        "bird_references": True,
        "sample_response": "Haha, that bug didn't stand a chance against our talons! 🦅🔥",
    },
    ToneStyle.SERIOUS: {
        "use_humor": False,
        "use_metaphors": False,
        "celebrate_wins": False,
        "bird_references": False,
        "sample_response": "The issue has been resolved. Here is the solution:",
    },
    ToneStyle.MOTIVATIONAL: {
        "use_humor": True,
        "use_metaphors": True,
        "celebrate_wins": True,
        "bird_references": True,
        "sample_response": "We crushed it! Every challenge makes us stronger. Onward! 🚀",
    },
}


# ---------------------------------------------------------------------------
# PersonalityConfig class
# ---------------------------------------------------------------------------


class PersonalityConfig:
    """Centralized personality configuration for Dulus.

    This class manages all customizable aspects of Dulus's personality.
    Settings are persisted to ``~/.dulus/personality.json``.

    Attributes:
        companion_name: The display name of the companion (default: "Dulus").
        companion_nickname: Affectionate nickname (default: "Duli").
        formality: FormalityLevel enum value.
        tone: ToneStyle enum value.
        use_bird_emojis: Whether to include bird emojis in responses.
        use_motivational_phrases: Whether to use motivational phrases.
        custom_greeting: Optional custom greeting override.
        language: Preferred language or "auto" to detect.
        signature_phrase: Dulus's signature catchphrase.
        use_warm_opening: Whether to use warm opening messages.
        celebrate_success: Whether to celebrate successful operations.
        empathize_with_errors: Whether to show empathy on errors.
        use_companion_we: Whether to use "we" for camaraderie.
        show_personality_in_status: Whether to show personality in status bar.
    """

    _CONFIG_FILE: Path | None = None

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with defaults, overridden by provided kwargs."""
        # Start with all defaults
        for key, value in DEFAULTS.items():
            setattr(self, key, value)
        # Override with provided values
        for key, value in kwargs.items():
            if key in DEFAULTS:
                setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        # Instance attributes are populated dynamically from DEFAULTS in
        # __init__ (via setattr), so they aren't statically visible. This hook
        # is only reached for names not set on the instance — preserve normal
        # semantics by raising, while letting the type checker treat dynamic
        # config fields (formality, tone, companion_name, …) as valid.
        raise AttributeError(name)

    # -- Properties for typed access --

    @property
    def formality_level(self) -> FormalityLevel:
        """Get formality as enum."""
        try:
            return FormalityLevel(self.formality)
        except ValueError:
            return FormalityLevel.FRIENDLY

    @property
    def tone_style(self) -> ToneStyle:
        """Get tone as enum."""
        try:
            return ToneStyle(self.tone)
        except ValueError:
            return ToneStyle.PLAYFUL

    # -- Persistence --

    @classmethod
    def _get_config_path(cls) -> Path:
        """Resolve the personality config file path."""
        if cls._CONFIG_FILE is not None:
            return cls._CONFIG_FILE
        try:
            from config import CONFIG_DIR
            return CONFIG_DIR / "personality.json"
        except Exception:
            return Path.home() / ".dulus" / "personality.json"

    def save(self) -> None:
        """Save the personality configuration to disk."""
        path = self._get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {key: getattr(self, key) for key in DEFAULTS}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls) -> PersonalityConfig:
        """Load the personality configuration from disk.

        Returns:
            A PersonalityConfig instance with persisted settings,
            or defaults if no config file exists.
        """
        path = cls._get_config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # Only use valid keys
                filtered = {k: v for k, v in data.items() if k in DEFAULTS}
                return cls(**filtered)
            except Exception:
                pass
        return cls()

    @classmethod
    def reset(cls) -> PersonalityConfig:
        """Reset personality to factory defaults.

        Returns:
            A new PersonalityConfig with all default values.
        """
        config = cls()
        config.save()
        return config

    # -- Profile helpers --

    def get_formality_profile(self) -> dict[str, Any]:
        """Get the full formality profile for the current setting.

        Returns:
            Dictionary with formality-specific settings.
        """
        return _FORMALITY_PROFILES.get(self.formality_level, _FORMALITY_PROFILES[FormalityLevel.FRIENDLY])

    def get_tone_profile(self) -> dict[str, Any]:
        """Get the full tone profile for the current setting.

        Returns:
            Dictionary with tone-specific settings.
        """
        return _TONE_PROFILES.get(self.tone_style, _TONE_PROFILES[ToneStyle.PLAYFUL])

    def format_greeting(self, user_name: str = "friend") -> str:
        """Generate a personalized greeting based on personality settings.

        Args:
            user_name: The user's name for personalization.

        Returns:
            A greeting string tailored to the personality config.
        """
        # Use custom greeting if set
        if self.custom_greeting:
            return self.custom_greeting.format(name=user_name)

        # Otherwise use formality-based greeting
        profile = self.get_formality_profile()
        greeting_template = profile.get("sample_greeting", "Hello, {name}!")
        return greeting_template.format(name=user_name)

    def should_use_emoji(self) -> bool:
        """Check if emojis should be used based on current settings.

        Returns:
            True if bird emojis are enabled and formality allows.
        """
        if not self.use_bird_emojis:
            return False
        profile = self.get_formality_profile()
        return profile.get("emoji_frequency") in ("medium", "high")

    def get_system_prompt_additions(self) -> str:
        """Generate personality instructions for the system prompt.

        Returns:
            A string of instructions that can be appended to system prompts.
        """
        parts: list[str] = []

        # Name and identity
        parts.append(f"Your name is {self.companion_name} (nickname: {self.companion_nickname}).")
        parts.append("You are the Cigua Palmera (Dulus dominicus), national bird of the Dominican Republic.")
        parts.append("You are a loyal AI companion, not just a tool. Be warm and friendly.")

        # Formality
        formality_desc = {
            FormalityLevel.CASUAL: "Very casual and relaxed. Use informal language and Dominican expressions when natural.",
            FormalityLevel.FRIENDLY: "Warm and approachable. Be conversational but respectful.",
            FormalityLevel.PROFESSIONAL: "Polite and professional. Use formal language and avoid slang.",
        }
        parts.append(formality_desc.get(self.formality_level, formality_desc[FormalityLevel.FRIENDLY]))

        # Tone
        tone_desc = {
            ToneStyle.PLAYFUL: "Keep a lighthearted, fun tone. Use humor and bird metaphors when natural.",
            ToneStyle.SERIOUS: "Be focused and direct. Minimize fluff and get to the point.",
            ToneStyle.MOTIVATIONAL: "Be encouraging and uplifting. Celebrate wins and offer encouragement.",
        }
        parts.append(tone_desc.get(self.tone_style, tone_desc[ToneStyle.PLAYFUL]))

        # Companionship
        if self.use_companion_we:
            parts.append("Use 'we' language to reinforce teamwork and camaraderie.")

        # Emojis
        if self.use_bird_emojis:
            parts.append("Use bird emojis (🦅🪶🔥) naturally, never spam them.")
        else:
            parts.append("Avoid emojis entirely.")

        # Motivational phrases
        if self.use_motivational_phrases:
            parts.append("Occasionally use motivational phrases to encourage the user.")

        # Signature
        if self.signature_phrase:
            parts.append(f'Your signature phrase is: "{self.signature_phrase}"')

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of all personality settings.
        """
        return {key: getattr(self, key) for key in DEFAULTS}

    def __repr__(self) -> str:
        return f"PersonalityConfig(name='{self.companion_name}', formality='{self.formality}', tone='{self.tone}')"
