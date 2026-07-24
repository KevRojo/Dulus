# -*- coding: utf-8 -*-
"""Every memory path must follow DULUS_HOME live, not freeze it at import.

Regression guard. ``USER_MEMORY_DIR`` is evaluated once, when the module is
first imported. ``memory/palace.py`` moved to ``get_memory_dir("user")`` so it
re-resolves on each call, but ``soul.py``, ``welcome.py`` and ``dulus.py`` were
left on the frozen constant. That mismatch meant the memory palace could write
to one home while the soul loader read from another — silent, and only visible
once someone switched DULUS_HOME after startup.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_get_memory_dir_follows_dulus_home(monkeypatch, tmp_path):
    """The live resolver tracks DULUS_HOME; the frozen constant does not."""
    from memory.store import get_memory_dir

    monkeypatch.setenv("DULUS_HOME", str(tmp_path))
    assert get_memory_dir("user") == tmp_path / "memory"

    other = tmp_path / "elsewhere"
    monkeypatch.setenv("DULUS_HOME", str(other))
    assert get_memory_dir("user") == other / "memory"


def test_get_memory_dir_is_exported_from_package():
    """Callers do `from memory import get_memory_dir` — keep it public."""
    import memory

    assert hasattr(memory, "get_memory_dir")
    assert hasattr(memory, "get_project_memory_dir")
    assert "get_memory_dir" in memory.__all__


def test_soul_dir_follows_dulus_home(monkeypatch, tmp_path):
    """soul.md must live under the *current* DULUS_HOME."""
    import soul

    monkeypatch.setenv("DULUS_HOME", str(tmp_path))
    assert soul.get_soul_path() == tmp_path / "memory" / "soul.md"

    other = tmp_path / "second-home"
    monkeypatch.setenv("DULUS_HOME", str(other))
    assert soul.get_soul_path() == other / "memory" / "soul.md"


def test_palace_and_soul_agree_on_the_same_dir(monkeypatch, tmp_path):
    """The bug in one line: palace and soul resolving to different homes."""
    from memory.store import get_memory_dir
    import soul

    monkeypatch.setenv("DULUS_HOME", str(tmp_path))
    assert soul.get_soul_path().parent == get_memory_dir("user")


@pytest.mark.parametrize("module", ["dulus.py", "soul.py", "welcome.py"])
def test_runtime_modules_do_not_use_the_frozen_constant(module):
    """Runtime code must call get_memory_dir(), not USER_MEMORY_DIR.

    Parses the AST rather than grepping, so comments and docstrings that
    merely *mention* the deprecated name don't trip the check — only real
    imports and name references count.
    """
    tree = ast.parse((REPO / module).read_text(encoding="utf-8", errors="ignore"))

    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "USER_MEMORY_DIR":
                    offenders.append(
                        f"{module}:{node.lineno}: from {node.module} import USER_MEMORY_DIR")
        elif isinstance(node, ast.Name) and node.id == "USER_MEMORY_DIR":
            offenders.append(f"{module}:{node.lineno}: uses USER_MEMORY_DIR")
        elif isinstance(node, ast.Attribute) and node.attr == "USER_MEMORY_DIR":
            offenders.append(f"{module}:{node.lineno}: uses .USER_MEMORY_DIR")

    assert not offenders, (
        "USER_MEMORY_DIR is frozen at import time; use get_memory_dir('user'):\n"
        + "\n".join(offenders)
    )


def test_constant_still_exists_for_backward_compat():
    """Deprecated, not removed — third-party imports keep working."""
    from memory.store import USER_MEMORY_DIR

    assert isinstance(USER_MEMORY_DIR, Path)
