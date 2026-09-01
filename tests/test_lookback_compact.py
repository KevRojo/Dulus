"""Lookback-aware compact: live context ~0, full archive on Loopback."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import compaction
import lookback


def _fat_history(n_turns: int = 12) -> list[dict]:
    msgs = [{"role": "system", "content": "You are Dulus. Identity stays."}]
    for i in range(n_turns):
        msgs.append({"role": "user", "content": f"user turn {i}: please do task {i} with lots of detail " * 20})
        msgs.append({
            "role": "assistant",
            "content": f"assistant turn {i}: I did the work and found path /tmp/file_{i}.py " * 15,
        })
        msgs.append({
            "role": "tool",
            "tool_call_id": f"c{i}",
            "content": ("TOOL DUMP " * 200) + f" result_{i}",
        })
    return msgs


class _FakeText:
    def __init__(self, text: str):
        self.text = text


def _fake_stream(**kwargs):
    yield _FakeText("- decision: ship fuel QR\n- path: Interant/fuel_qr.py\n- blocker: none")


def test_lookback_compact_shrinks_live_and_keeps_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(compaction, "LOOPBACK_ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(compaction, "CHECKPOINT_DIR", tmp_path / "ck")
    (tmp_path / "ck").mkdir()

    msgs = _fat_history(12)
    before_n = len(msgs)
    state = SimpleNamespace(messages=list(msgs), session_id="test_lb_compact")
    config = {
        "model": "test-model",
        "lookback": True,
        "lookback_turns": 20,
        "session_id": "test_lb_compact",
    }

    with patch.object(compaction.providers, "stream", side_effect=_fake_stream), \
         patch.object(compaction.providers, "TextChunk", _FakeText):
        # providers.TextChunk is used via isinstance — patch the class used in module
        compaction.providers.TextChunk = _FakeText  # type: ignore
        ok, info = compaction.manual_compact(state, config)

    assert ok, info
    assert "lookback-aggressive" in info
    # Live context collapsed hard
    assert len(state.messages) < before_n // 3, (len(state.messages), before_n, info)
    assert len(state.messages) <= 8, len(state.messages)  # system + card + ack + ~1 turn

    # Card present
    blob = "\n".join(str(m.get("content") or "") for m in state.messages)
    assert "[LOOKBACK COMPACT]" in blob
    assert "Loopback" in blob

    # Durable archive exists and is the FULL pre-compact history
    assert config.get("_loopback_archive_path")
    path = Path(config["_loopback_archive_path"])
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data["messages"]) == before_n

    # Loopback tool archive resolution prefers durable full history
    config["_state"] = state
    archive = lookback.get_archive_from_config(config)
    assert len(archive) == before_n
    assert archive[0]["role"] == "system"
    assert "user turn 0" in (archive[1].get("content") or "")


def test_compact_forces_lookback_even_when_off(tmp_path, monkeypatch):
    """Quality rule: compact with lookback OFF still forces lookback ON."""
    monkeypatch.setattr(compaction, "LOOPBACK_ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(compaction, "CHECKPOINT_DIR", tmp_path / "ck")
    (tmp_path / "ck").mkdir()

    msgs = _fat_history(12)
    before_n = len(msgs)
    state = SimpleNamespace(messages=list(msgs), session_id="force_lb")
    config = {"model": "test-model", "lookback": False, "session_id": "force_lb"}

    compaction.providers.TextChunk = _FakeText  # type: ignore
    with patch.object(compaction.providers, "stream", side_effect=_fake_stream), \
         patch("config.save_config", lambda cfg: None):
        ok, info = compaction.manual_compact(state, config)

    assert ok, info
    assert "lookback-aggressive" in info
    assert config.get("lookback") is True
    assert config.get("_lookback_forced_by_compact") is True
    assert "FORCED ON" in info
    blob = "\n".join(str(m.get("content") or "") for m in state.messages)
    assert "[LOOKBACK COMPACT]" in blob
    assert len(state.messages) < before_n // 3
    # Archive intact for Loopback
    config["_state"] = state
    archive = lookback.get_archive_from_config(config)
    assert len(archive) == before_n


def test_second_compact_does_not_shrink_loopback_archive(tmp_path, monkeypatch):
    """Second /compact must NOT overwrite the full archive with slim crumbs.

    Regression for the bug where each compact rewrote archive_<sid>.json with
    the already-compacted state.messages, wiping the original full history.
    """
    monkeypatch.setattr(compaction, "LOOPBACK_ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(compaction, "CHECKPOINT_DIR", tmp_path / "ck")
    (tmp_path / "ck").mkdir()

    full = _fat_history(12)
    before_n = len(full)
    state = SimpleNamespace(messages=list(full), session_id="second_compact")
    config = {
        "model": "test-model",
        "lookback": True,
        "lookback_turns": 20,
        "session_id": "second_compact",
    }

    compaction.providers.TextChunk = _FakeText  # type: ignore
    with patch.object(compaction.providers, "stream", side_effect=_fake_stream), \
         patch("config.save_config", lambda cfg: None):
        ok1, info1 = compaction.manual_compact(state, config)
        assert ok1, info1
        slim_n = len(state.messages)
        assert slim_n < before_n // 3

        # Second compact against the already-slim state
        ok2, info2 = compaction.manual_compact(state, config)
        # May succeed or say "not enough" — either way archive must stay full
        _ = (ok2, info2)

    path = Path(config["_loopback_archive_path"])
    data = json.loads(path.read_text())
    assert len(data["messages"]) == before_n, (
        f"second compact shrank archive to {len(data['messages'])} "
        f"(was {before_n})"
    )
    # In-memory binding also stays full
    assert len(config.get("_loopback_archive") or []) == before_n

    # Direct unit: save_loopback_archive refuses to shrink
    path2 = compaction.save_loopback_archive(
        [{"role": "user", "content": "crumb"}],
        state=state,
        config=config,
    )
    assert path2 is not None
    data2 = json.loads(Path(path2).read_text())
    assert len(data2["messages"]) == before_n
