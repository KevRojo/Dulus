"""Dulus GUI package — session and theme helpers shared with WebChat.

The desktop application lives in the signed builds. What remains here is the
storage/presentation layer the browser surfaces still read: ``session_utils``
for the on-disk session store and ``themes`` for the palette definitions.
Both are plain data modules, so importing them stays safe on headless boxes
(server, Docker without X11, Termux) — there is no tkinter import chain left.

Import them directly:

    from gui.session_utils import scan_sessions
    from gui.themes import THEMES
"""
from __future__ import annotations

__all__: list[str] = []
