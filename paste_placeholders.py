"""Paste placeholder support — fold large pastes into a compact token.

When a user pastes a large block of text (>10 lines or >2000 chars), it gets
stored in a dictionary and replaced with a short ``<<PASTE:xxxx>>`` token in
the input buffer.  Before the message reaches the agent, ``expand()`` swaps
the tokens back to full text.
"""

from __future__ import annotations

import hashlib
from typing import Dict

# In-memory store: token → original pasted text
_store: Dict[str, str] = {}

# Thresholds for triggering placeholderization
_LINE_THRESHOLD = 10
_CHAR_THRESHOLD = 2000


def maybe_placeholderize(text: str) -> str:
    """Return *text* unchanged if small, or a ``<<PASTE:…>>`` token if large."""
    if not text:
        return text
    line_count = text.count("\n") + 1
    if line_count < _LINE_THRESHOLD and len(text) < _CHAR_THRESHOLD:
        return text
    key = hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:8]
    token = f"<<PASTE:{key}>>"
    _store[token] = text
    return token


def expand(text: str) -> str:
    """Replace any ``<<PASTE:…>>`` tokens in *text* with the original content."""
    for token, original in _store.items():
        if token in text:
            text = text.replace(token, original)
    return text


def clear() -> None:
    """Drop all stored pastes (call between sessions if desired)."""
    _store.clear()


# Alias used by dulus.py
expand_placeholders = expand
