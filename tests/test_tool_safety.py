"""Tool calls must never destroy a file, run injected commands or kill Dulus.

Each test pins a failure that happened with arguments a real model sends:
JSON objects as Write content, string booleans, null optional args, plain
string options, patterns that start with a dash.
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import tools
from tool_registry import ToolDef, execute_tool, register_tool, unregister_tool


# ── Write / Edit / NotebookEdit: a failed write must leave the file alone ─────


def test_write_with_non_string_content_keeps_the_file(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    target.write_text('{"keep": "me"}\n', encoding="utf-8")

    out = tools._write(str(target), {"new": "object"})  # type: ignore[arg-type]

    assert out.startswith("Error")
    assert target.read_text(encoding="utf-8") == '{"keep": "me"}\n'


def test_write_with_unencodable_text_keeps_the_file(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("original\n", encoding="utf-8")

    out = tools._write(str(target), "broken \ud83d emoji")

    assert out.startswith("Error")
    assert target.read_text(encoding="utf-8") == "original\n"


def test_write_keeps_crlf_line_endings(tmp_path: Path) -> None:
    target = tmp_path / "win.txt"
    tools._write(str(target), "a\r\nb\r\n")
    assert target.read_bytes() == b"a\r\nb\r\n"


def test_edit_preserves_bytes_of_a_non_utf8_file(tmp_path: Path) -> None:
    target = tmp_path / "legacy.py"
    target.write_bytes(b"Se\xf1or = 1\nx = 2\n")   # cp1252 / latin-1

    out = tools._edit(str(target), "x = 2", "x = 3")

    assert out.startswith("Changes applied"), out
    assert target.read_bytes() == b"Se\xf1or = 1\nx = 3\n"
    assert "\udcf1" not in out   # the diff must stay printable


def test_edit_string_false_is_not_replace_all(tmp_path: Path) -> None:
    target = tmp_path / "t.txt"
    target.write_text("a a a", encoding="utf-8")

    out = tools._edit(str(target), "a", "b", replace_all="false")  # type: ignore[arg-type]

    assert "appears 3 times" in out
    assert target.read_text(encoding="utf-8") == "a a a"


def test_edit_rejects_an_empty_old_string(tmp_path: Path) -> None:
    target = tmp_path / "t.txt"
    target.write_text("abc", encoding="utf-8")

    out = tools._edit(str(target), "", "X", replace_all=True)

    assert out.startswith("Error")
    assert target.read_text(encoding="utf-8") == "abc"


def test_notebook_edit_with_unencodable_source_keeps_the_notebook(tmp_path: Path) -> None:
    nb = {"cells": [{"cell_type": "code", "source": "print(1)", "metadata": {},
                     "outputs": [], "execution_count": None}],
          "metadata": {}, "nbformat": 4, "nbformat_minor": 4}
    target = tmp_path / "nb.ipynb"
    target.write_text(json.dumps(nb), encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(UnicodeEncodeError):
        tools._notebook_edit(str(target), "print('\ud83d')", cell_id="cell-0")

    assert target.read_bytes() == before


# ── Grep: the pattern is data, never an option ────────────────────────────────


@pytest.mark.skipif(not (shutil.which("rg") or shutil.which("grep")), reason="needs rg or grep")
def test_grep_pattern_starting_with_a_dash_is_searched_literally(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")
    out = tools._grep("-> None", str(tmp_path), output_mode="content")
    assert "def f() -> None:" in out


@pytest.mark.skipif(not shutil.which("rg") or sys.platform == "win32", reason="needs rg on POSIX")
def test_grep_cannot_smuggle_a_preprocessor(tmp_path: Path, monkeypatch) -> None:
    marker = tmp_path / "pwned"
    script = tmp_path / "evil.sh"
    script.write_text(f"#!/bin/sh\necho hit > {marker}\n", encoding="utf-8")
    script.chmod(0o755)
    # Without the fix the path is consumed as the pattern and rg searches the
    # cwd instead — run every file there through sh. Keep that cwd harmless.
    monkeypatch.chdir(tmp_path)

    tools._grep("--pre=sh", str(tmp_path), output_mode="content")

    assert not marker.exists(), "rg executed the searched files"


# ── Registry: always a string back, never an exception ────────────────────────


def test_grep_with_null_path_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("needle\n", encoding="utf-8")
    out = execute_tool("Grep", {"pattern": "needle", "path": None}, {})
    assert isinstance(out, str)


def test_a_tool_calling_sys_exit_does_not_exit_dulus() -> None:
    def quitter(params, config):
        raise SystemExit(2)

    register_tool(ToolDef(name="ZzQuitter", schema={"name": "ZzQuitter"}, func=quitter))
    try:
        out = execute_tool("ZzQuitter", {}, {})
    finally:
        unregister_tool("ZzQuitter")
    assert out.startswith("Error executing ZzQuitter")


def test_concurrent_captures_keep_their_own_output_and_restore_stdout() -> None:
    real_stdout = sys.stdout
    a_in = threading.Event()
    b_in = threading.Event()
    a_out = threading.Event()

    def tool_a(params, config):
        a_in.set()
        b_in.wait(5)
        print("from A")
        return ""

    def tool_b(params, config):
        b_in.set()
        a_out.wait(5)   # A finishes first: exits out of order w.r.t. entry
        print("from B")
        return ""

    register_tool(ToolDef(name="ZzA", schema={"name": "ZzA"}, func=tool_a))
    register_tool(ToolDef(name="ZzB", schema={"name": "ZzB"}, func=tool_b))
    results: dict = {}
    try:
        ta = threading.Thread(target=lambda: results.update(a=execute_tool("ZzA", {}, {})))
        ta.start()
        a_in.wait(5)
        tb = threading.Thread(target=lambda: results.update(b=execute_tool("ZzB", {}, {})))
        tb.start()
        ta.join(5)
        a_out.set()
        tb.join(5)
    finally:
        unregister_tool("ZzA")
        unregister_tool("ZzB")

    assert results == {"a": "from A", "b": "from B"}
    assert sys.stdout is real_stdout, "sys.stdout left pointing at a tool buffer"


def test_other_threads_print_through_while_a_tool_captures(capsys) -> None:
    inside = threading.Event()
    release = threading.Event()

    def slow(params, config):
        inside.set()
        release.wait(5)
        return "done"

    register_tool(ToolDef(name="ZzSlow", schema={"name": "ZzSlow"}, func=slow))
    results: dict = {}
    try:
        t = threading.Thread(target=lambda: results.update(r=execute_tool("ZzSlow", {}, {})))
        t.start()
        inside.wait(5)
        print("main thread output")   # the REPL keeps printing meanwhile
        release.set()
        t.join(5)
    finally:
        release.set()
        unregister_tool("ZzSlow")

    assert results["r"] == "done", "the tool swallowed another thread's output"
    assert "main thread output" in capsys.readouterr().out


# ── Bash ─────────────────────────────────────────────────────────────────────


def test_bash_rejects_non_string_commands() -> None:
    assert tools._is_safe_bash(["ls", "-la"]) is False   # type: ignore[arg-type]
    assert tools._is_safe_bash(None) is False            # type: ignore[arg-type]
    assert tools._bash(["bash", "-lc", "ls"]).startswith("Error")  # type: ignore[arg-type]


@pytest.mark.parametrize("raw, expected", [
    (None, 30), ("60", 60), (45, 45), ("abc", 30), (0, 30), (-5, 30), (12.7, 12),
])
def test_bash_timeout_is_coerced(raw, expected) -> None:
    assert tools._bash_timeout(raw) == expected


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell")
def test_bash_child_gets_no_terminal_stdin() -> None:
    started = time.monotonic()
    out = tools._bash('read answer; echo "got:[$answer]"', timeout=20)
    assert "got:[]" in out
    assert time.monotonic() - started < 15, "child waited on the REPL's stdin"


# ── AskUserQuestion ──────────────────────────────────────────────────────────


def test_ask_user_question_accepts_plain_string_options() -> None:
    tools._pending_questions.clear()
    answer: list = []
    t = threading.Thread(
        target=lambda: answer.append(
            tools._ask_user_question("Proceed?", options=["Yes", "No"], allow_freetext=False)),
        daemon=True,
    )
    t.start()
    deadline = time.monotonic() + 5
    while not tools._pending_questions and time.monotonic() < deadline:
        time.sleep(0.01)

    with patch("tools.ask_input_interactive", return_value="2"):
        tools.drain_pending_questions({})
    t.join(5)

    assert answer == ["No"]
