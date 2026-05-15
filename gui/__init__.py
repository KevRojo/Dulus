"""Dulus GUI package — professional desktop interface.

GUI-heavy modules are loaded LAZILY. Headless environments (server,
Docker without X11, WSL without python3-tk, Termux) need to be able to
do `from gui.session_utils import ...` without crashing on the
tkinter/customtkinter import chain. We wrap the lazy attribute lookup
in try/except so importing `gui` itself is always safe; only touching
an attribute triggers the heavy imports, and they raise a clearer error
when tkinter is missing.
"""
from __future__ import annotations

import importlib
from typing import Any

# Map exposed name -> (submodule, attribute). Lazy so that `import gui`
# works on a tk-less box; only attribute access pulls the GUI deps in.
_LAZY_ATTRS = {
    "DulusMainWindow":   ("gui.main_window",     "DulusMainWindow"),
    "ChatWidget":        ("gui.chat_widget",     "ChatWidget"),
    "DulusBridge":       ("gui.agent_bridge",    "DulusBridge"),
    "DulusSidebar":      ("gui.sidebar",         "DulusSidebar"),
    "SettingsDialog":    ("gui.settings_dialog", "SettingsDialog"),
    "ToolPanel":         ("gui.tool_panel",      "ToolPanel"),
    "TasksView":         ("gui.tasks_view",      "TasksView"),
}

__all__ = list(_LAZY_ATTRS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_ATTRS:
        mod_name, attr_name = _LAZY_ATTRS[name]
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as e:
            # Surface a clearer message than the bare 'No module named tkinter'.
            raise ImportError(
                f"Dulus GUI ({name}) requires tkinter. On Linux/WSL:\n"
                "    sudo apt install python3-tk\n"
                "Then `pip install --upgrade --force-reinstall customtkinter`.\n"
                f"(original error: {e})"
            ) from e
        return getattr(mod, attr_name)
    raise AttributeError(f"module 'gui' has no attribute {name!r}")
