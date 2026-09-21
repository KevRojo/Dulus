"""Guards against modules removed from the public runtime leaving dead wiring.

The free/public tree periodically drops premium subsystems (Dulus OS sandbox,
the desktop GUI, the plugin Auto-Adapter, ...). Those removals have twice left
behind imports of now-missing modules that nothing in the suite exercised:

  * ``webchat_server.create_app()`` kept ``from sandbox_bootstrap import ...``
    and raised ``ModuleNotFoundError`` for every caller — the whole webchat
    server was unreachable while the suite stayed green.
  * ``common`` imported ``backend.ui.input`` (a path that never existed) behind
    a bare ``except ImportError``, silently downgrading slash-command
    completion to ``input()``.

Both were invisible because no test imported the entry points. These tests are
deliberately shallow: they only assert the public surface still wires up.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root (parent of tests/) is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── webchat server ────────────────────────────────────────────────────────────


class TestWebchatServer:
    def test_create_app_succeeds(self):
        """create_app() must build without importing removed modules."""
        import webchat_server

        app = webchat_server.create_app()
        assert app is not None

    def test_create_app_registers_routes(self):
        """A successful build should expose the core webchat routes."""
        import webchat_server

        app = webchat_server.create_app()
        rules = {str(r) for r in app.url_map.iter_rules()}
        assert "/api/health" in rules
        assert len(rules) > 10

    def test_no_sandbox_static_routes(self):
        """The Mini OS frontend is gone; its static routes must not linger."""
        import webchat_server

        app = webchat_server.create_app()
        rules = {str(r) for r in app.url_map.iter_rules()}
        assert "/sandbox" not in rules
        assert "/sandbox/<path:path>" not in rules


# ── slash-command completion wiring ───────────────────────────────────────────


class TestSlashCompletionWiring:
    def test_prompt_toolkit_path_is_live(self):
        """common must bind ui.input, not silently fall back to input()."""
        import inspect

        import common

        src = inspect.getsource(common.read_slash_input)
        assert "return input(prompt)" not in src, (
            "common fell back to the bare-input stub; its slash-completion "
            "import target is broken"
        )

    def test_setup_reports_prompt_toolkit(self):
        """setup_slash_commands returns HAS_PROMPT_TOOLKIT when wired up."""
        pytest.importorskip("prompt_toolkit")

        import common

        assert common.setup_slash_commands(lambda: {}, lambda: {}) is True


# ── removed tool surface ──────────────────────────────────────────────────────


class TestRemovedToolSurface:
    def test_launch_sandbox_schema_absent(self):
        """LaunchSandbox must not be advertised to the model any more."""
        import tools

        names = {s.get("name") for s in tools.TOOL_SCHEMAS}
        assert "LaunchSandbox" not in names

    def test_sandbox_command_absent(self):
        """/sandbox opened a URL that can only 404 now."""
        import dulus

        assert "sandbox" not in dulus.COMMANDS


# ── packaging ─────────────────────────────────────────────────────────────────


class TestPackagingManifest:
    def test_declared_py_modules_exist(self):
        """Every py-module in pyproject must resolve to a real file."""
        try:
            import tomllib
        except ModuleNotFoundError:  # Python 3.10
            import tomli as tomllib  # type: ignore[no-redef]

        root = Path(__file__).resolve().parent.parent
        with (root / "pyproject.toml").open("rb") as fh:
            cfg = tomllib.load(fh)

        declared = cfg["tool"]["setuptools"].get("py-modules", [])
        missing = [m for m in declared if not (root / f"{m}.py").exists()]
        assert not missing, f"pyproject declares missing py-modules: {missing}"
