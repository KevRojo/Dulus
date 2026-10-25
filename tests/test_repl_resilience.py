"""An unexpected error in a turn or a slash command must not kill the REPL.

Only openai/anthropic ``APIError`` used to be handled. Anything else — a bug
in a tool or a provider adapter, a broken slash command, Ctrl+C inside a
command — unwound out of ``repl()`` and killed the process, taking the
unsaved conversation with it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _dulus():
    return pytest.importorskip("dulus")


# ── handle_slash ──────────────────────────────────────────────────────────────


def _install(monkeypatch, dulus, name, handler):
    monkeypatch.setitem(dulus.COMMANDS, name, handler)


def test_crashing_command_is_reported_not_raised(monkeypatch, capsys) -> None:
    dulus = _dulus()

    def broken(args, state, config):
        raise ValueError("simulated command bug")

    _install(monkeypatch, dulus, "zz_broken", broken)
    assert dulus.handle_slash("/zz_broken", object(), {}) is True
    out = capsys.readouterr()
    assert "Unexpected error in /zz_broken: ValueError: simulated command bug" in out.out + out.err


def test_ctrl_c_inside_a_command_returns_to_the_prompt(monkeypatch) -> None:
    dulus = _dulus()

    def slow(args, state, config):
        raise KeyboardInterrupt

    _install(monkeypatch, dulus, "zz_slow", slow)
    try:
        handled = dulus.handle_slash("/zz_slow", object(), {})
    except KeyboardInterrupt:  # would otherwise abort the whole pytest run
        pytest.fail("Ctrl+C inside a command escaped handle_slash")
    assert handled is True


def test_raise_errors_keeps_the_exception_for_cmd_mode(monkeypatch) -> None:
    dulus = _dulus()

    def broken(args, state, config):
        raise ValueError("simulated command bug")

    _install(monkeypatch, dulus, "zz_broken", broken)
    with pytest.raises(ValueError):
        dulus.handle_slash("/zz_broken", object(), {}, raise_errors=True)


def test_sentinels_still_pass_through(monkeypatch) -> None:
    dulus = _dulus()
    _install(monkeypatch, dulus, "zz_plan", lambda a, s, c: ("__plan__", a))
    assert dulus.handle_slash("/zz_plan build it", object(), {}) == ("__plan__", "build it")


# ── The real REPL, end to end ─────────────────────────────────────────────────

_DRIVER = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, {root!r})
    import agent
    import tools
    from providers import AssistantTurn, TextChunk

    turns = iter(["crash", "answer", "answer"])

    def _scripted_stream(**kwargs):
        if next(turns) == "crash":
            raise RuntimeError("simulated adapter bug")
        yield TextChunk("scripted answer")
        yield AssistantTurn("scripted answer", [], 1, 1)

    agent.stream = _scripted_stream

    drains = iter([True])  # the first post-turn drain fails
    _real_drain = tools.drain_pending_questions

    def _drain(config):
        if next(drains, False):
            raise OSError("simulated post-turn bug")
        return _real_drain(config)

    tools.drain_pending_questions = _drain

    import dulus

    def _broken_command(args, state, config):
        raise ValueError("simulated command bug")

    dulus.COMMANDS["cost"] = _broken_command
    sys.argv = ["dulus"]
    dulus.main()
    """
)


@pytest.mark.skipif(sys.platform == "win32",
                    reason="boots the full REPL under a piped stdin; verified on POSIX only")
def test_repl_survives_a_crashing_turn_and_command(tmp_path) -> None:
    _dulus()
    home = tmp_path / "home"
    dulus_dir = home / ".dulus"
    dulus_dir.mkdir(parents=True)
    (dulus_dir / "config.json").write_text(json.dumps({
        "model": "openai/gpt-4o",
        "openai_api_key": "sk-test",
        "verbose": False,
        "mem_palace": False,
        "sticky_input": False,
        "telemetry": False,
        "_ipc_disabled": True,
    }), encoding="utf-8")
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER.format(root=str(ROOT)), encoding="utf-8")

    env = dict(
        os.environ,
        HOME=str(home),
        USERPROFILE=str(home),
        DULUS_CONFIG_DIR=str(dulus_dir),
        DULUS_HOME=str(dulus_dir),
        DULUS_NO_SENTRY="1",
        DULUS_NO_IPC="1",
        DULUS_NO_ANIMATIONS="1",
        DULUS_BAR="0",
        PYTHONUTF8="1",
    )
    proc = subprocess.run(
        [sys.executable, str(driver)],
        input=(
            "first prompt, the provider crashes\n"
            "/cost\n"
            "second prompt, a post-turn step crashes\n"
            "third prompt, still alive\n"
        ),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300, env=env, cwd=str(tmp_path),
    )
    out = proc.stdout + proc.stderr

    assert proc.returncode == 0, out[-4000:]
    assert "Unexpected error in this turn: RuntimeError: simulated adapter bug" in out, out[-4000:]
    assert "Unexpected error in /cost: ValueError: simulated command bug" in out
    assert "Unexpected error in this turn: OSError: simulated post-turn bug" in out
    assert out.count("scripted answer") >= 2, "the turns after the crashes never ran"
    assert "Goodbye!" in out
