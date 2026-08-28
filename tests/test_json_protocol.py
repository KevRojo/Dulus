"""Tests for `--output json` — the machine-readable protocol mode.

Two layers on purpose:

* **Source invariants.** The bug that made Dulus unusable as a child process
  was ordering, not logic: the boot banner printed before anything could
  redirect it, so the parent's first stdout line was `🦅 Dulus — …` instead of
  a frame. That kind of regression is invisible to a unit test on `_emit`, so
  the ordering is asserted against the source directly.
* **Frame contract.** `_emit` and its payload builders are pure enough to
  exercise without a provider, so the wire shape is pinned here.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SOURCE = (Path(__file__).resolve().parent.parent / "dulus.py").read_text(encoding="utf-8")


def _dulus():
    """Import dulus, skipping when the provider SDKs aren't installed."""
    return pytest.importorskip("dulus")


# ── Source invariants ─────────────────────────────────────────────────────────


def test_output_flag_is_declared_with_both_formats() -> None:
    assert 'parser.add_argument("--output", choices=["text", "json"], default="text"' in SOURCE


def test_channel_split_happens_before_the_first_print() -> None:
    """stdout must be swapped before anything in main() can print.

    The license gate is the first unconditional print in `main()`. If the swap
    ever moves below it, the banner lands on the protocol channel again and
    every parser downstream breaks on line 1.
    """
    swap = SOURCE.index("sys.stdout = sys.stderr")
    license_gate = SOURCE.index('print(f"\\n🦅 Dulus — {_lic.status_banner()}")')
    parse_args = SOURCE.index("args = parser.parse_args()")

    assert parse_args < swap < license_gate


def test_protocol_mode_disables_cursor_repaints() -> None:
    """Live rendering and animations only emit escapes a parent has to strip."""
    assert 'os.environ["DULUS_NO_ANIMATIONS"] = "1"' in SOURCE
    assert 'config["rich_live"] = False' in SOURCE


def test_protocol_mode_never_hands_the_prompt_to_another_process() -> None:
    """IPC dispatch would answer in another session and emit no frames here."""
    assert 'and not os.environ.get("DULUS_NO_IPC")\n        and not _protocol_enabled()' in SOURCE


def test_one_shot_run_emits_the_full_lifecycle() -> None:
    assert '_emit({"type": "step_start", "sessionID": session_id})' in SOURCE
    assert '_emit({"type": "text", "part": {"text": _final_assistant_text(state)}})' in SOURCE
    assert '_emit({"type": "step_finish", "part": _usage_part(state, config)})' in SOURCE


def test_failures_exit_non_zero_in_protocol_mode() -> None:
    """A parent can only tell success from failure by the exit code + frame.

    Every failure path reachable from a one-shot run has to do both: emit an
    `error` frame and exit non-zero. Previously all of them exited 0.
    """
    one_shot = SOURCE[SOURCE.index("    if initial_prompt:"):]
    one_shot = one_shot[:one_shot.index("# ── Bracketed paste mode")]

    assert '_emit_error("interrupted")' in one_shot
    assert "sys.exit(130)" in one_shot
    assert "_emit_error(_one_shot_err)" in one_shot
    assert "sys.exit(1)" in one_shot

    # Provider/API errors are swallowed by run_query so the REPL survives them;
    # in protocol mode they must surface instead.
    assert "_emit_error(friendly_api_error(e))" in SOURCE
    # Missing credentials are a warning interactively, terminal for a parent.
    assert "_emit_error(_msg)" in SOURCE


# ── Frame contract ────────────────────────────────────────────────────────────


def test_emit_writes_one_jsonl_line_to_the_protocol_channel(monkeypatch) -> None:
    dulus = _dulus()
    buf = io.StringIO()
    monkeypatch.setattr(dulus, "_PROTOCOL_OUT", buf)

    dulus._emit({"type": "step_start", "sessionID": "abc123"})
    dulus._emit({"type": "text", "part": {"text": "hola, señor 🦅"}})

    lines = buf.getvalue().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"type": "step_start", "sessionID": "abc123"}
    # ensure_ascii=False keeps accents and emoji readable on the wire.
    assert json.loads(lines[1])["part"]["text"] == "hola, señor 🦅"
    assert "\\u" not in lines[1]


def test_emit_is_a_noop_in_text_mode(monkeypatch, capsys) -> None:
    dulus = _dulus()
    monkeypatch.setattr(dulus, "_PROTOCOL_OUT", None)

    assert dulus._protocol_enabled() is False
    dulus._emit({"type": "text", "part": {"text": "should not appear"}})

    assert capsys.readouterr().out == ""


def test_emit_survives_a_closed_parent_pipe(monkeypatch) -> None:
    """A parent that hangs up must not turn into a traceback on the way out."""
    dulus = _dulus()

    class Hungup:
        def write(self, _data):
            raise BrokenPipeError("parent went away")

        def flush(self):
            pass

    monkeypatch.setattr(dulus, "_PROTOCOL_OUT", Hungup())
    dulus._emit({"type": "error", "message": "boom"})  # must not raise


def test_error_frame_shape() -> None:
    dulus = _dulus()
    buf = io.StringIO()
    original = dulus._PROTOCOL_OUT
    dulus._PROTOCOL_OUT = buf
    try:
        dulus._emit_error(ValueError("no API key"))
    finally:
        dulus._PROTOCOL_OUT = original

    assert json.loads(buf.getvalue()) == {"type": "error", "message": "no API key"}


def test_final_assistant_text_flattens_block_content() -> None:
    dulus = _dulus()
    state = SimpleNamespace(messages=[
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "hidden reasoning"},
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]},
    ])

    # Thinking blocks are not the answer and must never reach the wire.
    assert dulus._final_assistant_text(state) == "first\nsecond"


def test_final_assistant_text_handles_plain_and_missing_answers() -> None:
    dulus = _dulus()

    plain = SimpleNamespace(messages=[{"role": "assistant", "content": "listo"}])
    assert dulus._final_assistant_text(plain) == "listo"

    # A run that died before the assistant replied has no text, not a crash.
    assert dulus._final_assistant_text(SimpleNamespace(messages=[])) == ""
    dangling = SimpleNamespace(messages=[{"role": "user", "content": "hi"}])
    assert dulus._final_assistant_text(dangling) == ""


def test_usage_part_reports_the_keys_parsers_read() -> None:
    dulus = _dulus()
    state = SimpleNamespace(
        messages=[{"role": "user", "content": "hi"}],
        total_input_tokens=1200,
        total_output_tokens=40,
        total_cache_read_tokens=900,
        total_cache_creation_tokens=300,
    )

    part = dulus._usage_part(state, {"model": "kimi/kimi-k2.5"})

    tokens = part["tokens"]
    assert isinstance(tokens["input"], int)
    assert isinstance(tokens["output"], int)
    assert tokens["cache"] == {"read": 900, "write": 300}
    assert isinstance(part["cost"], float)


def test_usage_part_survives_a_state_without_counters() -> None:
    """Counters are absent when the run failed before the first turn closed."""
    dulus = _dulus()

    part = dulus._usage_part(SimpleNamespace(messages=[]), {})

    assert part["tokens"]["cache"] == {"read": 0, "write": 0}
    assert part["cost"] == 0.0
