"""Dulus runs on a Dulus account: the session check and the launch gate."""
from __future__ import annotations

import os
import sys
import time
import types

import pytest

import dulus
import dulus_account

KEY = "dulus_sk_" + "a" * 32


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Pipe:
    def isatty(self):
        return False


@pytest.fixture()
def store(tmp_path, monkeypatch):
    path = tmp_path / "account.json"
    monkeypatch.setattr(dulus_account, "_store_path", lambda: path)
    monkeypatch.delenv("DULUS_API_KEY", raising=False)
    return path


def _fake_post(monkeypatch, result):
    import requests

    calls = []

    def post(url, json=None, timeout=None, **_):
        calls.append((url, json))
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(requests, "post", post)
    return calls


def _expired_session():
    dulus_account.save_store({"access_token": "old", "refresh_token": "r1", "expires_at": time.time() - 60})


# ── session_status ──────────────────────────────────────────────────────────

def test_dulus_key_counts_as_signed_in(store, monkeypatch):
    monkeypatch.setenv("DULUS_API_KEY", KEY)
    assert dulus_account.session_status() == "active"


@pytest.mark.parametrize("key", ["sk-proj-not-a-dulus-key-at-all", "dulus_sk_short"])
def test_foreign_or_broken_key_is_rejected(store, monkeypatch, key):
    monkeypatch.setenv("DULUS_API_KEY", key)
    assert dulus_account.session_status() == "invalid_key"


def test_no_session_means_none(store):
    assert dulus_account.session_status() == "none"


def test_live_token_needs_no_network(store, monkeypatch):
    calls = _fake_post(monkeypatch, AssertionError("no network expected"))
    dulus_account.save_store({"access_token": "t", "refresh_token": "r", "expires_at": time.time() + 600})
    assert dulus_account.session_status() == "active"
    assert calls == []


def test_expired_token_renews(store, monkeypatch):
    _expired_session()
    calls = _fake_post(monkeypatch, _Resp(200, {"access_token": "new", "refresh_token": "r2", "expires_in": 3600}))
    assert dulus_account.session_status() == "active"
    assert calls and calls[0][1]["refresh_token"] == "r1"
    saved = dulus_account.load_store()
    assert saved["access_token"] == "new" and saved["refresh_token"] == "r2"


def test_refused_renewal_means_sign_in_again(store, monkeypatch):
    _expired_session()
    _fake_post(monkeypatch, _Resp(401, {"error": "invalid_grant"}))
    assert dulus_account.session_status() == "none"


def test_unreachable_dulus_keeps_you_working(store, monkeypatch):
    _expired_session()
    _fake_post(monkeypatch, OSError("no route to host"))
    assert dulus_account.session_status() == "offline"
    _fake_post(monkeypatch, _Resp(503))
    assert dulus_account.session_status() == "offline"


def test_without_renew_a_stored_session_is_trusted(store, monkeypatch):
    _expired_session()
    calls = _fake_post(monkeypatch, AssertionError("no network expected"))
    assert dulus_account.session_status(renew=False) == "active"
    assert calls == []


def test_refresh_keeps_old_refresh_token_when_none_issued(store, monkeypatch):
    _expired_session()
    _fake_post(monkeypatch, _Resp(200, {"access_token": "new", "expires_in": 3600}))
    assert dulus_account.refresh("r1")["refresh_token"] == "r1"


def test_refresh_returns_none_when_refused(store, monkeypatch):
    _fake_post(monkeypatch, _Resp(400, {"error": "invalid_grant"}))
    assert dulus_account.refresh("r1") is None


# ── the launch gate ─────────────────────────────────────────────────────────

def _args(**over):
    base = dict(run_tool=None, job_id=None, job_path=None, exec_cmd=None)
    base.update(over)
    return types.SimpleNamespace(**base)


@pytest.fixture()
def gate(monkeypatch):
    seen: dict = {}

    def status(renew=True):
        seen["renew"] = renew
        return seen.get("answer", "none")

    def login(notify=print, **options):
        seen["login_options"] = options
        return seen.setdefault("login", "token")

    monkeypatch.setattr(dulus_account, "session_status", status)
    monkeypatch.setattr(dulus_account, "login", login)
    monkeypatch.setattr(dulus, "_protocol_enabled", lambda: False)
    monkeypatch.setattr(dulus, "_login_gate_can_prompt", lambda: True)
    return seen


def test_gate_lets_a_signed_in_person_through(gate):
    gate["answer"] = "active"
    dulus._require_dulus_login(_args())
    assert gate["renew"] is True


def test_gate_offline_carries_on(gate):
    gate["answer"] = "offline"
    dulus._require_dulus_login(_args())


def test_gate_survives_a_broken_session_check(monkeypatch, capsys):
    """A missing optional dependency or a bug in the check must not block launch."""
    def boom(renew=True):
        raise ModuleNotFoundError("No module named 'requests'")

    monkeypatch.setattr(dulus_account, "session_status", boom)
    monkeypatch.setattr(dulus, "_protocol_enabled", lambda: False)
    monkeypatch.setattr(dulus, "_login_gate_can_prompt", lambda: True)

    dulus._require_dulus_login(_args())  # must not raise

    assert "carrying on" in capsys.readouterr().err


def test_gate_signs_you_in(gate):
    dulus._require_dulus_login(_args())
    assert gate["login"] == "token"


def test_gate_stops_when_sign_in_does_not_finish(gate):
    gate["login"] = None
    with pytest.raises(SystemExit) as exc:
        dulus._require_dulus_login(_args())
    assert exc.value.code == 1


class _Screen:
    """A terminal stand-in that records what reached the person, and when it was flushed."""

    def __init__(self, tty: bool):
        self.tty = tty
        self.text = ""
        self.flushed = ""

    def isatty(self):
        return self.tty

    def write(self, data):
        self.text += data
        return len(data)

    def flush(self):
        self.flushed = self.text


def test_the_sign_in_link_goes_to_the_terminal_even_with_stdout_redirected(gate, monkeypatch):
    # `dulus -p … > out.txt` on a server: the person only sees stderr. The link
    # used to land in out.txt while Dulus sat waiting for an approval that
    # could never come.
    stdout, stderr = _Screen(tty=False), _Screen(tty=True)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(dulus, "_login_gate_can_prompt", lambda: True)
    shown_while_waiting = []

    def login(notify=print, **options):
        notify("https://dulus.us.auth0.com/activate?user_code=ABCD-EFGH")
        shown_while_waiting.append(stderr.flushed)  # what's on screen while polling
        assert options["out"] is stderr  # the QR goes there too
        return "token"

    monkeypatch.setattr(dulus_account, "login", login)
    dulus._require_dulus_login(_args())

    assert "user_code=ABCD-EFGH" in shown_while_waiting[0]
    assert "user_code" not in stdout.text and "free Dulus account" not in stdout.text
    assert "welcome aboard" in stderr.text


def test_the_sign_in_link_is_flushed_through_a_git_bash_pipe(gate, monkeypatch):
    # mintty hands Dulus a pipe, which Python buffers: unflushed, the link only
    # showed up after the sign-in it was needed for had finished.
    pipe = _Screen(tty=False)
    monkeypatch.setattr(sys, "stdout", pipe)
    monkeypatch.setattr(sys, "stderr", _Screen(tty=False))
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(dulus, "_attached_to_msys_pty", lambda stream: stream is pipe)
    shown_while_waiting = []

    def login(notify=print, **options):
        notify("https://dulus.us.auth0.com/activate?user_code=ABCD-EFGH")
        shown_while_waiting.append(pipe.flushed)
        return "token"

    monkeypatch.setattr(dulus_account, "login", login)
    dulus._require_dulus_login(_args())

    assert "user_code=ABCD-EFGH" in shown_while_waiting[0]


def test_a_crash_inside_the_sign_in_is_a_failed_sign_in_not_a_traceback(gate, monkeypatch, capsys):
    def login(notify=print, **options):
        raise RuntimeError("proxy ate the reply")

    monkeypatch.setattr(dulus_account, "login", login)
    with pytest.raises(SystemExit) as exc:
        dulus._require_dulus_login(_args())

    assert exc.value.code == 1
    assert "Sign-in failed (RuntimeError: proxy ate the reply)" in capsys.readouterr().out


def test_gate_without_a_person_explains_and_exits(gate, monkeypatch, capsys):
    monkeypatch.setattr(dulus, "_login_gate_can_prompt", lambda: False)
    with pytest.raises(SystemExit) as exc:
        dulus._require_dulus_login(_args())
    assert exc.value.code == 2
    assert "DULUS_API_KEY" in capsys.readouterr().err
    assert gate["renew"] is False
    assert "login" not in gate


def test_gate_names_a_bad_key(gate, capsys):
    gate["answer"] = "invalid_key"
    with pytest.raises(SystemExit):
        dulus._require_dulus_login(_args())
    assert "isn't a Dulus key" in capsys.readouterr().err


def test_gate_protocol_mode_reports_through_the_protocol(gate, monkeypatch):
    monkeypatch.setattr(dulus, "_protocol_enabled", lambda: True)
    sent = []
    monkeypatch.setattr(dulus, "_emit_error", lambda message, *a, **k: sent.append(message))
    with pytest.raises(SystemExit):
        dulus._require_dulus_login(_args())
    assert sent and "DULUS_API_KEY" in sent[0]
    assert "login" not in gate


def test_gate_scripts_never_renew(gate):
    gate["answer"] = "active"
    dulus._require_dulus_login(_args(exec_cmd=["status"]))
    assert gate["renew"] is False


@pytest.mark.parametrize("over", [
    {"run_tool": "Bash"},
    {"job_id": "abc"},
    {"job_path": "job.json"},
    {"exec_cmd": ["login", "dulus"]},
    {"exec_cmd": ["/logout"]},
    {"exec_cmd": ['"login dulus"']},
])
def test_gate_leaves_its_own_escape_hatches_open(gate, over):
    dulus._require_dulus_login(_args(**over))
    assert "renew" not in gate


def test_ci_never_prompts(monkeypatch):
    monkeypatch.setenv("CI", "true")
    assert dulus._login_gate_can_prompt() is False


def test_the_person_is_on_stderr_when_stdout_is_redirected(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    stderr = _Screen(tty=True)
    monkeypatch.setattr(sys, "stdout", _Pipe())
    monkeypatch.setattr(sys, "stderr", stderr)
    assert dulus._login_gate_stream() is stderr
    assert dulus._login_gate_can_prompt() is True


def test_plain_pipes_are_nobody_even_under_git_bash(monkeypatch):
    # MSYSTEM leaks into every child of a Git Bash shell — scripts and
    # scheduled jobs included — so it must never count as a person.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("MSYSTEM", "MINGW64")
    monkeypatch.setattr(sys, "stdout", _Pipe())
    monkeypatch.setattr(sys, "stderr", _Pipe())
    assert dulus._login_gate_can_prompt() is False


def test_mintty_terminal_counts_as_a_person(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(sys, "stdout", _Pipe())
    monkeypatch.setattr(sys, "stderr", _Pipe())
    monkeypatch.setattr(dulus, "_attached_to_msys_pty", lambda stream: True)
    assert dulus._login_gate_can_prompt() is True


def test_ordinary_pipe_is_not_a_mintty_terminal():
    read_fd, write_fd = os.pipe()
    with open(read_fd, "rb") as reader, open(write_fd, "wb") as writer:
        assert dulus._attached_to_msys_pty(writer) is False
        assert dulus._attached_to_msys_pty(reader) is False


@pytest.mark.parametrize("pipe_name, expected", [
    ("msys-{tag}-pty3-to-master", True),
    ("cygwin-{tag}-pty0-from-master", True),
    ("cygwin-{TAG}-pty1-to-master-nat", True),  # newer Cygwin, upper-case key
    ("dulus-test-{tag}", False),
])
def test_mintty_pipe_is_recognised_by_name(pipe_name, expected):
    if sys.platform != "win32":
        pytest.skip("mintty ptys are a Windows thing")
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                          wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    invalid = wintypes.HANDLE(-1).value

    path = "\\\\.\\pipe\\" + pipe_name.format(tag=(t := os.urandom(8).hex()), TAG=t.upper())
    server = kernel32.CreateNamedPipeW(path, 0x3, 0, 1, 4096, 4096, 0, None)  # PIPE_ACCESS_DUPLEX
    assert server not in (None, invalid)
    try:
        client = kernel32.CreateFileW(path, 0xC0000000, 0, None, 3, 0, None)  # read|write, OPEN_EXISTING
        assert client not in (None, invalid)
        with open(msvcrt.open_osfhandle(client, 0), "wb") as stream:
            assert dulus._attached_to_msys_pty(stream) is expected
    finally:
        kernel32.CloseHandle(server)
