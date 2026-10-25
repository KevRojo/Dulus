"""State on disk must survive crashes, races and bad values without data loss.

Each test pins a way a user lost their sessions or config, or Dulus refused to
start: a save cut short, two processes starting together, a typo.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

import config as cfgmod


# ── atomic_write_text ─────────────────────────────────────────────────────────


def test_atomic_write_replaces_the_file_and_leaves_no_temp(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    target.write_text("old", encoding="utf-8")

    cfgmod.atomic_write_text(target, "new ✓")

    assert target.read_text(encoding="utf-8") == "new ✓"
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_a_failed_atomic_write_keeps_the_old_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "state.json"
    target.write_text("precious", encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(cfgmod.os, "replace", boom)
    with pytest.raises(OSError):
        cfgmod.atomic_write_text(target, "half")

    assert target.read_text(encoding="utf-8") == "precious"
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


# ── history.json ─────────────────────────────────────────────────────────────


def test_unreadable_history_is_set_aside_not_overwritten(tmp_path: Path) -> None:
    hist = tmp_path / "history.json"
    hist.write_text('{"sessions": [{"session_id": "a"}', encoding="utf-8")  # cut short

    fresh = cfgmod.load_session_history(hist)

    assert fresh == {"total_turns": 0, "sessions": []}
    kept = list(tmp_path.glob("history.corrupt-*.json"))
    assert len(kept) == 1 and '"session_id": "a"' in kept[0].read_text(encoding="utf-8")


def test_wrong_shaped_history_is_set_aside(tmp_path: Path) -> None:
    hist = tmp_path / "history.json"
    hist.write_text("[]", encoding="utf-8")
    assert cfgmod.load_session_history(hist) == {"total_turns": 0, "sessions": []}
    assert list(tmp_path.glob("history.corrupt-*.json"))


def test_history_that_cannot_be_read_is_left_alone(tmp_path: Path) -> None:
    hist = tmp_path / "history.json"
    hist.mkdir()   # reading it raises OSError, like a locked file on Windows
    assert cfgmod.load_session_history(hist) is None


def test_save_latest_keeps_every_earlier_session(tmp_path: Path, monkeypatch) -> None:
    dulus = pytest.importorskip("dulus")
    sessions = tmp_path / "sessions"
    monkeypatch.setattr(cfgmod, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(cfgmod, "DAILY_DIR", sessions / "daily")
    monkeypatch.setattr(cfgmod, "SESSION_HIST_FILE", sessions / "history.json")
    sessions.mkdir()
    earlier = [{"session_id": f"s{i}", "turn_count": 1, "messages": []} for i in range(3)]
    (sessions / "history.json").write_text(
        json.dumps({"total_turns": 3, "sessions": earlier}), encoding="utf-8")

    from agent import AgentState
    state = AgentState(messages=[{"role": "user", "content": "hi"}],
                       turn_count=dulus.MIN_AUTO_SAVE_TURNS)
    assert dulus.save_latest("", state, {"_session_id": "now"})

    hist = json.loads((sessions / "history.json").read_text(encoding="utf-8"))
    assert [s["session_id"] for s in hist["sessions"]] == ["s0", "s1", "s2", "now"]
    assert len(list((sessions / "daily").rglob("session_*_now.json"))) == 1


# ── config.json ──────────────────────────────────────────────────────────────


def test_recovered_config_is_written_back(tmp_path: Path, monkeypatch) -> None:
    conf = tmp_path / "config.json"
    monkeypatch.setattr(cfgmod, "CONFIG_FILE", conf)
    monkeypatch.setattr(cfgmod, "_ensure_config_dirs", lambda: None)
    good = {"model": "anthropic/claude-sonnet-4-6", "verbose": False}
    conf.with_suffix(".json.bak").write_text(json.dumps(good), encoding="utf-8")
    conf.write_text('{"model": "anthropic/claude', encoding="utf-8")   # cut short

    loaded = cfgmod.load_config()

    assert loaded["model"] == good["model"]
    # Next launch must not look like a first run and reset everything.
    assert json.loads(conf.read_text(encoding="utf-8")) == good
    assert list(tmp_path.glob("config.corrupt-*.json"))


def test_concurrent_writability_probes_never_fail(tmp_path: Path) -> None:
    results: list = []

    def probe():
        for _ in range(200):
            results.append(cfgmod._dir_is_writable(tmp_path))

    threads = [threading.Thread(target=probe) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(results), f"{results.count(False)} probes judged a writable dir unwritable"


@pytest.mark.parametrize("raw, expected", [
    ("8k", 1_000_000), ("64000", 64000), (8000.0, 8000), ("-1", -1), (None, None), (True, True),
])
def test_numeric_settings_are_coerced_on_load(raw, expected) -> None:
    cfg = {"max_tokens": raw}
    cfgmod._coerce_numeric_settings(cfg)
    assert cfg["max_tokens"] == expected


def test_config_command_rejects_non_numeric_values(monkeypatch) -> None:
    dulus = pytest.importorskip("dulus")
    saved: list = []
    monkeypatch.setattr(cfgmod, "save_config", lambda c: saved.append(dict(c)))
    conf = {"max_tokens": 8000}

    dulus.cmd_config("max_tokens=8k", None, conf)
    assert conf["max_tokens"] == 8000 and not saved

    dulus.cmd_config("max_tokens=16000", None, conf)
    assert conf["max_tokens"] == 16000 and saved


# ── license key ──────────────────────────────────────────────────────────────


def test_a_mistyped_license_key_does_not_stop_startup(monkeypatch) -> None:
    import license_manager as lm

    key = lm._generate_key("pro", 30, lm._LICENSE_SECRET)
    body = key.split("-", 1)[1]
    broken = 0
    for i in range(len(body) - 32, len(body)):
        for ch in "AQgw_-9z":
            if ch == body[i]:
                continue
            lic = lm.LicenseManager("DULUS-" + body[:i] + ch + body[i + 1:])
            broken += not lic.valid
    assert broken, "expected the typos to be rejected"
    assert lm.LicenseManager(key).valid
