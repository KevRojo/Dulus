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


def test_version_and_help_answer_before_the_swap() -> None:
    """`--version` and `--help` are queries, not runs.

    They emit no frames, so if the swap ran first their answer would land on
    stderr and stdout would come back empty.
    """
    swap = SOURCE.index("sys.stdout = sys.stderr")

    assert SOURCE.index('print(f"dulus v{VERSION}")') < swap
    assert SOURCE.index("print(__doc__)") < swap


def test_protocol_mode_disables_cursor_repaints() -> None:
    """Live rendering and animations only emit escapes a parent has to strip."""
    assert 'os.environ["DULUS_NO_ANIMATIONS"] = "1"' in SOURCE
    assert 'config["rich_live"] = False' in SOURCE


def test_protocol_mode_never_hands_the_prompt_to_another_process() -> None:
    """IPC dispatch would answer in another session and emit no frames here."""
    assert 'and not os.environ.get("DULUS_NO_IPC")\n        and not _protocol_enabled()' in SOURCE


def test_one_shot_run_emits_the_full_lifecycle() -> None:
    one_shot = _one_shot_branch()

    assert '_emit({"type": "step_start", "sessionID": session_id})' in one_shot
    assert "_baseline = len(getattr(state, \"messages\", []) or [])" in one_shot
    assert "_code = _emit_turn_result(state, config, since=_baseline)" in one_shot
    # Non-zero only: the success path keeps the pre-existing `return` so text
    # mode's control flow is untouched.
    assert "if _code:\n                sys.exit(_code)" in one_shot


def test_baseline_is_captured_before_the_turn_runs() -> None:
    """Captured after the turn it would already include this turn's messages."""
    one_shot = _one_shot_branch()

    assert one_shot.index("_baseline = len(") < one_shot.index("run_query(initial_prompt)")


def test_agent_loop_records_the_verdict_of_the_turn_it_ran() -> None:
    """`AssistantTurn.error` is otherwise unobservable to any caller.

    On that path `run()` rolls the history back and breaks — no exception, no
    new assistant message, no TurnDone. Without these two fields a failed run
    is indistinguishable from a successful one.
    """
    agent_src = (Path(__file__).resolve().parent.parent / "agent.py").read_text(encoding="utf-8")

    assert "last_error: str = \"\"" in agent_src
    assert "last_reply: str | None = None" in agent_src
    # Cleared at the start of every turn so a stale verdict can't be reused.
    assert "state.last_error = \"\"" in agent_src
    assert "state.last_reply = None" in agent_src
    # The shared err() record is turn-scoped too, or a stale reason from an
    # earlier turn gets blamed for this turn's outcome.
    assert "_common.clear_last_error()" in agent_src
    # Captured before the rollback throws the evidence away.
    error_branch = agent_src[agent_src.index("if assistant_turn.error:"):]
    error_branch = error_branch[:error_branch.index("break")]
    assert "state.last_error = sanitize_text(assistant_turn.text or \"\").strip()" in error_branch
    assert error_branch.index("state.last_error") < error_branch.index("state.messages.pop()")
    assert "state.last_reply = _reply_text" in agent_src


def test_err_records_the_reason_for_every_module() -> None:
    """Handled-and-printed failures leave no exception to inspect later.

    Recording in `common.err` rather than a local wrapper is deliberate: every
    module does `from common import err`, which binds the function object at
    import time, so a wrapper in dulus.py would miss providers.py and tools.py.
    """
    common_src = (Path(__file__).resolve().parent.parent / "common.py").read_text(encoding="utf-8")

    assert "_LAST_ERROR: str = \"\"" in common_src
    assert "def last_error() -> str:" in common_src
    assert "def clear_last_error() -> None:" in common_src
    err_body = common_src[common_src.index("def err(msg: str):"):common_src.index("def pip_install_cmd")]
    assert "_LAST_ERROR = str(msg).strip()" in err_body


def test_failures_exit_non_zero_in_protocol_mode() -> None:
    """A parent can only tell success from failure by the exit code + frame.

    Every failure path reachable from a one-shot run has to do both: emit an
    `error` frame and exit non-zero. Previously all of them exited 0.
    """
    one_shot = _one_shot_branch()

    assert '_emit_error("interrupted")' in one_shot
    assert "sys.exit(130)" in one_shot
    assert "_emit_error(_one_shot_err)" in one_shot

    # Provider/API errors are swallowed by run_query so the REPL survives them;
    # in protocol mode they must surface instead.
    assert "_emit_error(friendly_api_error(e))" in SOURCE
    # Missing credentials are a warning interactively, terminal for a parent.
    assert "_emit_error(_msg)" in SOURCE


def _one_shot_branch() -> str:
    branch = SOURCE[SOURCE.index("    if initial_prompt:"):]
    return branch[:branch.index("# ── Bracketed paste mode")]


# ── Turn verdict (end to end) ─────────────────────────────────────────────────
#
# These are the cases that were red before this fix: an auth failure reported
# `exit 0` with a `text` frame containing the gold-memory dump.

GOLD_MEMORY = {
    "role": "assistant",
    "content": "[Golden Memory Loaded: short_memory]\n\n# Short Memory (gold)…",
}


def _verdict(state, config=None, since=1):
    """Run the real verdict logic and return (exit_code, [frames])."""
    dulus = _dulus()
    common = pytest.importorskip("common")
    buf = io.StringIO()
    original = dulus._PROTOCOL_OUT
    dulus._PROTOCOL_OUT = buf
    try:
        code = dulus._emit_turn_result(state, config or {"model": "kimi/kimi-k2.5"}, since=since)
    finally:
        dulus._PROTOCOL_OUT = original
        common.clear_last_error()
    return code, [json.loads(line) for line in buf.getvalue().splitlines()]


def test_provider_auth_failure_is_a_failed_run() -> None:
    """The reported bug, verbatim.

    `dulus --print --accept-all --output json -- "di hola"` against an
    unauthenticated web provider exited 0 and reported the gold memory as the
    assistant's answer. The provider ends the turn with `error=True`, which
    raises nothing and rolls the turn's messages back — leaving the boot-time
    gold memory as the last assistant message.
    """
    state = SimpleNamespace(
        messages=[GOLD_MEMORY],
        last_error="[gemini-web] Auth file not found: /x/auth.json. Run /harvest.",
        last_reply=None,
    )

    code, frames = _verdict(state)

    assert code == 1
    assert frames == [{
        "type": "error",
        "message": "[gemini-web] Auth file not found: /x/auth.json. Run /harvest.",
    }]
    # The gold memory must not appear anywhere on the wire.
    assert "Golden Memory" not in json.dumps(frames)


def test_silent_empty_turn_is_a_failed_run() -> None:
    """No exception, no `last_error` — only something printed to the human.

    An invalid API key surfaces this way. The emptiness net catches it and the
    reason comes from whatever `err()` last reported, from any module.
    """
    common = pytest.importorskip("common")
    common.clear_last_error()
    common.err("Invalid API key for provider 'openai'")

    code, frames = _verdict(
        SimpleNamespace(messages=[GOLD_MEMORY], last_error="", last_reply=None)
    )

    assert code == 1
    assert frames == [{"type": "error", "message": "Invalid API key for provider 'openai'"}]


def test_unexplained_empty_turn_still_fails() -> None:
    """The floor: a run with no answer is never a success, reason or not."""
    code, frames = _verdict(
        SimpleNamespace(messages=[GOLD_MEMORY], last_error="", last_reply=None)
    )

    assert code == 1
    assert frames == [{"type": "error", "message": "model produced no assistant reply"}]


def test_partial_text_followed_by_a_failure_is_a_failed_run() -> None:
    """Streamed prose is not an answer if the turn then died."""
    code, frames = _verdict(SimpleNamespace(
        messages=[GOLD_MEMORY],
        last_error="Quota exhausted for provider 'nvidia'",
        last_reply="let me check that for you…",
    ))

    assert code == 1
    assert [f["type"] for f in frames] == ["error"]
    assert "let me check" not in json.dumps(frames)


def test_successful_turn_emits_text_then_step_finish() -> None:
    code, frames = _verdict(SimpleNamespace(
        messages=[
            GOLD_MEMORY,
            {"role": "user", "content": "di hola"},
            {"role": "assistant", "content": "¡Hola!", "tool_calls": []},
        ],
        last_error="",
        last_reply="¡Hola!",
        total_input_tokens=3447,
        total_output_tokens=12,
        total_cache_read_tokens=0,
        total_cache_creation_tokens=0,
    ))

    assert code == 0
    assert [f["type"] for f in frames] == ["text", "step_finish"]
    assert frames[0]["part"]["text"] == "¡Hola!"
    assert set(frames[1]["part"]["tokens"]) >= {"input", "output", "cache"}


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


def test_final_assistant_text_never_reaches_below_the_baseline() -> None:
    """The gold-memory bug.

    Gold memories are appended as `role: "assistant"` at boot. A failed turn
    rolls its own messages back, so a bare `messages[-1]` read returned the
    gold-memory dump and the run looked like a success whose answer was a
    memory file. `since` scopes the scan to this turn's messages.
    """
    dulus = _dulus()
    gold = {"role": "assistant", "content": "[Golden Memory Loaded: short_memory]\n\n# gold"}

    rolled_back = SimpleNamespace(messages=[gold])
    assert dulus._final_assistant_text(rolled_back, since=1) == ""
    # …and without the baseline it is exactly the old, wrong behaviour.
    assert "Golden Memory" in dulus._final_assistant_text(rolled_back)

    # A real reply above the baseline is still found, even behind a tool result.
    answered = SimpleNamespace(messages=[
        gold,
        {"role": "user", "content": "di hola"},
        {"role": "assistant", "content": "", "tool_calls": [{"name": "Read"}]},
        {"role": "tool", "content": "file contents"},
        {"role": "assistant", "content": "¡Hola!", "tool_calls": []},
    ])
    assert dulus._final_assistant_text(answered, since=1) == "¡Hola!"


def test_turn_reply_prefers_what_the_agent_loop_recorded() -> None:
    """`last_reply` survives mid-run auto-compaction; a message index does not.

    Compaction rebinds `state.messages` to a shorter list, which invalidates
    the pre-turn baseline. The agent loop's own record of the turn it ran is
    immune to that, so it wins when present.
    """
    dulus = _dulus()

    compacted = SimpleNamespace(messages=[{"role": "system", "content": "summary"}],
                                last_reply="¡Hola!")
    assert dulus._turn_reply_text(compacted, since=7) == "¡Hola!"

    # Absent (a caller that doesn't go through agent.run()) → fall back to the scan.
    scanned = SimpleNamespace(messages=[{"role": "assistant", "content": "from history"}])
    assert dulus._turn_reply_text(scanned, since=0) == "from history"

    # Present but empty is a real answer of "" — a failed turn, not a fallback.
    empty = SimpleNamespace(messages=[{"role": "assistant", "content": "stale"}], last_reply="")
    assert dulus._turn_reply_text(empty, since=0) == ""


def test_turn_error_message_prefers_the_most_specific_reason() -> None:
    dulus = _dulus()
    common = pytest.importorskip("common")

    # 1. The agent loop's verdict for an error=True turn wins.
    common.clear_last_error()
    common.err("something printed earlier")
    state = SimpleNamespace(last_error="[gemini-web] Auth file not found: /x. Run /harvest.")
    assert dulus._turn_error_message(state) == "[gemini-web] Auth file not found: /x. Run /harvest."

    # 2. Otherwise the last thing reported to the human channel, from any module.
    common.clear_last_error()
    common.err("Invalid API key for provider 'openai'")
    assert dulus._turn_error_message(SimpleNamespace(last_error="")) == \
        "Invalid API key for provider 'openai'"

    # 3. Nothing recorded is still a failure — an empty run is never a success.
    common.clear_last_error()
    assert dulus._turn_error_message(SimpleNamespace(last_error="")) == \
        "model produced no assistant reply"


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
