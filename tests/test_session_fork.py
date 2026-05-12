"""Tests for SessionFork — Feature 11.

Covers:
* enumerate_turns on empty / missing files
* enumerate_turns with TurnBegin / TurnEnd records
* _extract_user_text with str, list, dict, and mixed input
* truncate_at_turn boundary correctness
* fork (full copy and at specific turn)
* undo (success and error cases)
"""

from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path

# Ensure dulus modules are importable
import sys

_PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_DIR))

from dulus_tools.session_fork import SessionFork, TurnInfo


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


def _make_wire_record(msg_type: str, payload: dict | None = None, *, meta: bool = False) -> str:
    """Return a single JSONL line for the wire format."""
    if meta:
        return json.dumps({"type": "metadata", "message": payload or {}})
    return json.dumps({"type": "message", "message": {"type": msg_type, "payload": payload or {}}})


def _build_wire_file(path: Path, records: list[str]) -> None:
    """Write a list of JSON strings to *path* as JSONL."""
    path.write_text("\n".join(records) + "\n", encoding="utf-8")


@pytest.fixture
def tmp_session(tmp_path: Path):
    """Provide a fresh SessionFork pointing at a temporary directory."""
    session_dir = tmp_path / "test-session"
    session_dir.mkdir()
    return SessionFork(str(session_dir))


# --------------------------------------------------------------------------- #
#  enumerate_turns
# --------------------------------------------------------------------------- #


def test_enumerate_turns_empty_dir(tmp_session: SessionFork):
    """Missing wire.jsonl should return an empty list."""
    assert tmp_session.enumerate_turns() == []


def test_enumerate_turns_no_turns(tmp_session: SessionFork):
    """Wire file with no TurnBegin should return an empty list."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("SystemMessage", {"text": "hello"}),
        _make_wire_record("ChatMessage", {"text": "world"}),
    ])
    assert tmp_session.enumerate_turns() == []


def test_enumerate_turns_single_turn(tmp_session: SessionFork):
    """A single TurnBegin with a plain-string user_input."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "Hello world"}),
        _make_wire_record("TurnEnd"),
    ])
    turns = tmp_session.enumerate_turns()
    assert len(turns) == 1
    assert turns[0] == TurnInfo(index=0, user_text="Hello world")


def test_enumerate_turns_multiple_turns(tmp_session: SessionFork):
    """Multiple turns with different user input formats."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "First query"}),
        _make_wire_record("ChatMessage", {"text": "response 1"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": [{"text": "Second"}, {"text": "query"}]}),
        _make_wire_record("ChatMessage", {"text": "response 2"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "Third and final query here"}),
        _make_wire_record("TurnEnd"),
    ])
    turns = tmp_session.enumerate_turns()
    assert len(turns) == 3
    assert turns[0] == TurnInfo(index=0, user_text="First query")
    assert turns[1] == TurnInfo(index=1, user_text="Second query")
    assert turns[2] == TurnInfo(index=2, user_text="Third and final query here")


def test_enumerate_turns_skips_metadata(tmp_session: SessionFork):
    """Metadata records should be ignored when counting turns."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("some_meta", meta=True),
        _make_wire_record("TurnBegin", {"user_input": "query"}),
        _make_wire_record("some_meta", meta=True),
        _make_wire_record("TurnEnd"),
    ])
    turns = tmp_session.enumerate_turns()
    assert len(turns) == 1
    assert turns[0].index == 0


def test_enumerate_turns_ignores_bad_json(tmp_session: SessionFork):
    """Malformed JSON lines should be silently skipped."""
    wire = tmp_session._session_dir / "wire.jsonl"
    wire.write_text(
        "this is not json\n"
        + _make_wire_record("TurnBegin", {"user_input": "ok"})
        + "\n{ broken json\n"
        + _make_wire_record("TurnEnd")
        + "\n",
        encoding="utf-8",
    )
    turns = tmp_session.enumerate_turns()
    assert len(turns) == 1
    assert turns[0].user_text == "ok"


def test_enumerate_turns_with_custom_path(tmp_session: SessionFork, tmp_path: Path):
    """Passing an explicit wire_path should work."""
    custom_wire = tmp_path / "custom_wire.jsonl"
    _build_wire_file(custom_wire, [
        _make_wire_record("TurnBegin", {"user_input": "custom"}),
        _make_wire_record("TurnEnd"),
    ])
    turns = tmp_session.enumerate_turns(custom_wire)
    assert len(turns) == 1
    assert turns[0].user_text == "custom"


# --------------------------------------------------------------------------- #
#  _extract_user_text
# --------------------------------------------------------------------------- #


def test_extract_user_text_str(tmp_session: SessionFork):
    assert tmp_session._extract_user_text("hello world") == "hello world"


def test_extract_user_text_str_multiline(tmp_session: SessionFork):
    """Only the first line is kept."""
    assert tmp_session._extract_user_text("line one\nline two") == "line one"


def test_extract_user_text_str_truncation(tmp_session: SessionFork):
    """Long strings are truncated to 80 characters."""
    long_text = "x" * 100
    assert len(tmp_session._extract_user_text(long_text)) == 80


def test_extract_user_text_list_of_dicts(tmp_session: SessionFork):
    parts = [{"text": "hello"}, {"text": "world"}]
    assert tmp_session._extract_user_text(parts) == "hello world"


def test_extract_user_text_list_of_strs(tmp_session: SessionFork):
    parts = ["hello", "world"]
    assert tmp_session._extract_user_text(parts) == "hello world"


def test_extract_user_text_list_mixed(tmp_session: SessionFork):
    parts = ["hello", {"text": "world"}, 42]  # 42 is ignored
    assert tmp_session._extract_user_text(parts) == "hello world"


def test_extract_user_text_list_no_text_key(tmp_session: SessionFork):
    parts = [{"foo": "bar"}]
    assert tmp_session._extract_user_text(parts) == ""


def test_extract_user_text_none(tmp_session: SessionFork):
    assert tmp_session._extract_user_text(None) == ""


def test_extract_user_text_int(tmp_session: SessionFork):
    assert tmp_session._extract_user_text(42) == ""


# --------------------------------------------------------------------------- #
#  truncate_at_turn
# --------------------------------------------------------------------------- #


def test_truncate_at_turn_missing_file(tmp_session: SessionFork):
    """Should raise ValueError when wire file does not exist."""
    with pytest.raises(ValueError, match="wire file not found"):
        tmp_session.truncate_at_turn(tmp_session._session_dir / "nope.jsonl", 0)


def test_truncate_at_turn_zero(tmp_session: SessionFork):
    """Truncate at the very first turn."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "first"}),
        _make_wire_record("ChatMessage", {"text": "r1"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "second"}),
        _make_wire_record("ChatMessage", {"text": "r2"}),
        _make_wire_record("TurnEnd"),
    ])
    lines = tmp_session.truncate_at_turn(wire, 0)
    assert len(lines) == 3  # TurnBegin + ChatMessage + TurnEnd
    records = [json.loads(l) for l in lines]
    assert all(r["message"]["type"] in ("TurnBegin", "ChatMessage", "TurnEnd") for r in records)


def test_truncate_at_turn_one(tmp_session: SessionFork):
    """Truncate at the second turn (index 1)."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "first"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "second"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "third"}),
        _make_wire_record("TurnEnd"),
    ])
    lines = tmp_session.truncate_at_turn(wire, 1)
    assert len(lines) == 4  # turn 0 (2 lines) + turn 1 (2 lines)


def test_truncate_at_turn_includes_metadata(tmp_session: SessionFork):
    """Metadata should always be carried forward."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("system", {"version": "1"}, meta=True),
        _make_wire_record("TurnBegin", {"user_input": "q"}),
        _make_wire_record("TurnEnd"),
    ])
    lines = tmp_session.truncate_at_turn(wire, 0)
    assert len(lines) == 3
    records = [json.loads(l) for l in lines]
    assert records[0]["type"] == "metadata"


def test_truncate_at_turn_beyond_range(tmp_session: SessionFork):
    """Turn index beyond available turns should include all existing turns."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "only"}),
        _make_wire_record("TurnEnd"),
    ])
    lines = tmp_session.truncate_at_turn(wire, 99)
    # When turn_index exceeds available turns, all existing content is returned
    assert len(lines) == 2  # TurnBegin + TurnEnd


# --------------------------------------------------------------------------- #
#  fork
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_fork_full(tmp_session: SessionFork, tmp_path: Path):
    """Fork with turn_index=None should copy the entire wire file."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "hello"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "world"}),
        _make_wire_record("TurnEnd"),
    ])

    new_sid = await tmp_session.fork(turn_index=None, title_prefix="Fork")
    new_dir = tmp_session._session_dir.parent / new_sid
    assert new_dir.exists()
    new_wire = new_dir / "wire.jsonl"
    assert new_wire.exists()
    # Should have all 4 records
    lines = [l for l in new_wire.read_text(encoding="utf-8").split("\n") if l.strip()]
    assert len(lines) == 4


@pytest.mark.asyncio
async def test_fork_at_turn(tmp_session: SessionFork, tmp_path: Path):
    """Fork at turn 0 should only include that turn."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "first"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "second"}),
        _make_wire_record("TurnEnd"),
    ])

    new_sid = await tmp_session.fork(turn_index=0, title_prefix="Test")
    new_dir = tmp_session._session_dir.parent / new_sid
    new_wire = new_dir / "wire.jsonl"
    lines = [l for l in new_wire.read_text(encoding="utf-8").split("\n") if l.strip()]
    assert len(lines) == 2  # Only first turn


@pytest.mark.asyncio
async def test_fork_empty_wire(tmp_session: SessionFork):
    """Forking an empty wire file should create an empty wire.jsonl."""
    wire = tmp_session._session_dir / "wire.jsonl"
    wire.write_text("", encoding="utf-8")
    new_sid = await tmp_session.fork(turn_index=None)
    new_dir = tmp_session._session_dir.parent / new_sid
    new_wire = new_dir / "wire.jsonl"
    assert new_wire.exists()


# --------------------------------------------------------------------------- #
#  undo
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_undo_success(tmp_session: SessionFork):
    """Undo on a session with 2+ turns should fork at the second-to-last."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "first"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "second"}),
        _make_wire_record("TurnEnd"),
        _make_wire_record("TurnBegin", {"user_input": "third"}),
        _make_wire_record("TurnEnd"),
    ])

    new_sid = await tmp_session.undo()
    assert new_sid.startswith("undo-")
    new_dir = tmp_session._session_dir.parent / new_sid
    new_wire = new_dir / "wire.jsonl"
    lines = [l for l in new_wire.read_text(encoding="utf-8").split("\n") if l.strip()]
    # Should have first 2 turns (4 lines)
    assert len(lines) == 4


@pytest.mark.asyncio
async def test_undo_fewer_than_two_turns(tmp_session: SessionFork):
    """Undo on a session with fewer than 2 turns should raise ValueError."""
    wire = tmp_session._session_dir / "wire.jsonl"
    _build_wire_file(wire, [
        _make_wire_record("TurnBegin", {"user_input": "only"}),
        _make_wire_record("TurnEnd"),
    ])
    with pytest.raises(ValueError, match="Cannot undo"):
        await tmp_session.undo()


@pytest.mark.asyncio
async def test_undo_empty_session(tmp_session: SessionFork):
    """Undo on an empty session should raise ValueError."""
    with pytest.raises(ValueError, match="Cannot undo"):
        await tmp_session.undo()


# --------------------------------------------------------------------------- #
#  _read_all_lines
# --------------------------------------------------------------------------- #


def test_read_all_lines_missing(tmp_session: SessionFork):
    """Reading a non-existent path should return []."""
    assert tmp_session._read_all_lines(tmp_session._session_dir / "nope.txt") == []


def test_read_all_lines_basic(tmp_session: SessionFork):
    """Should return stripped non-empty lines."""
    wire = tmp_session._session_dir / "wire.jsonl"
    wire.write_text("line one\n\n  \nline two\n", encoding="utf-8")
    lines = tmp_session._read_all_lines(wire)
    assert lines == ["line one", "line two"]
