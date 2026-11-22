"""A typo in a command argument is the user's mistake, not a Dulus bug.

err() forwards the exception in flight to Sentry, and argument parsing reads
``except ValueError: err("... must be a number")``, so every typo filed a
production issue: ``/config max_tokens=8k`` became "ValueError: could not
convert string to float: '8k'". Those calls pass report=False; a command that
really crashes still has to reach Sentry.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import common
import config as cfgmod

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def reported(monkeypatch) -> list:
    """What err() hands to Sentry (conftest keeps the real client off)."""
    sentry_sdk = pytest.importorskip("sentry_sdk")
    seen: list = []
    monkeypatch.setattr(sentry_sdk, "capture_exception",
                        lambda error=None, **_: seen.append(error or sys.exc_info()[1]))
    return seen


def test_err_inside_except_reports_the_exception(reported) -> None:
    try:
        raise RuntimeError("simulated bug")
    except RuntimeError:
        common.err("Something broke")
    assert [str(e) for e in reported] == ["simulated bug"]


def test_report_false_still_shows_and_records_the_error(reported, capsys) -> None:
    try:
        int("lots")
    except ValueError:
        common.err("Amount must be an integer", report=False)
    out = capsys.readouterr()
    assert reported == []
    assert "Amount must be an integer" in out.out + out.err
    assert common.last_error() == "Amount must be an integer"


@pytest.mark.parametrize("line, message", [
    ("/config max_tokens=8k", "max_tokens must be a whole number"),
    ("/budget warn abc", "warn must be a fraction"),
    ("/budget tokens lots", "Amount must be an integer"),
    ("/proactive 5x", "Invalid duration: '5x'"),
    ("/wake threshold loud", "Threshold must be a number"),
    ("/checkpoint nope", "Unknown subcommand: nope"),
])
def test_a_typo_in_a_command_is_not_a_sentry_event(line, message, reported, capsys,
                                                   monkeypatch) -> None:
    dulus = pytest.importorskip("dulus")
    monkeypatch.setattr(cfgmod, "save_config", lambda c: None)
    conf = dict(cfgmod.DEFAULTS, _session_id="test")

    assert dulus.handle_slash(line, object(), conf) is True
    out = capsys.readouterr()
    assert message in out.out + out.err
    assert reported == []


def test_a_crashing_command_still_reaches_sentry(reported, monkeypatch) -> None:
    dulus = pytest.importorskip("dulus")

    def broken(args, state, config):
        raise ValueError("simulated command bug")

    monkeypatch.setitem(dulus.COMMANDS, "zz_broken", broken)
    assert dulus.handle_slash("/zz_broken", object(), {}) is True
    assert [str(e) for e in reported] == ["simulated command bug"]


def test_the_suite_never_reports_to_production() -> None:
    dulus = pytest.importorskip("dulus")
    assert dulus._SENTRY is False


def test_events_carry_the_dulus_version_not_the_cwd_commit(tmp_path) -> None:
    """Left unset, sentry-sdk takes `git rev-parse HEAD` of the cwd as the release."""
    dulus = pytest.importorskip("dulus")
    pytest.importorskip("sentry_sdk")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    try:
        subprocess.run(git + ["init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "a user project"],
                       cwd=tmp_path, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    env = {k: v for k, v in os.environ.items() if k not in ("DULUS_NO_SENTRY", "SENTRY_RELEASE")}
    env["SENTRY_DSN"] = "http://public@127.0.0.1:9/1"  # armed, but never production
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH")]))
    probe = ("import dulus, sentry_sdk; "
             "print('release=%s' % sentry_sdk.get_client().options['release'])")

    proc = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=300)
    out = proc.stdout + proc.stderr
    assert f"release=dulus@{dulus.VERSION}" in proc.stdout, out[-4000:]
