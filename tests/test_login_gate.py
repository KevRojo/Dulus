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


# ── sign_in over a long or filtered route ───────────────────────────────────

_DEVICE = f"https://{dulus_account._AUTH0_DOMAIN}/oauth/device/code"
_POLL = f"https://{dulus_account._AUTH0_DOMAIN}/oauth/token"
_LEASE = f"{dulus_account.DULUS_API_BASE}/api/entitlements"
_AUTHORIZE = f"{dulus_account.DULUS_API_BASE}/v1/oauth/authorize"
_EXCHANGE = f"{dulus_account.DULUS_API_BASE}/v1/oauth/token"


class _Page(_Resp):
    """What a Wi-Fi login page or a filtering proxy sends back: not JSON."""

    def json(self):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


class _Clock:
    """Virtual time, so retries and the wait for approval cost the suite nothing."""

    def __init__(self):
        self.now = 1_000_000.0

    def time(self):
        return self.now

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture()
def network(store, monkeypatch):
    """Answer each sign-in URL from its own script of replies; the last one repeats."""
    import requests

    script: dict = {}
    calls: list = []

    def send(url, **_):
        calls.append(url)
        replies = script[url]
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr(requests, "post", send)
    monkeypatch.setattr(requests, "get", send)
    monkeypatch.setattr(dulus_account, "time", _Clock())
    monkeypatch.setattr(dulus_account, "_browser_openers", lambda url, mode="auto": [])
    return script, calls


def _a_clean_sign_in():
    return {
        _DEVICE: [_Resp(200, {"device_code": "dc", "user_code": "ABCD-EFGH",
                              "verification_uri": "https://login.test/activate"})],
        _POLL: [_Resp(400, {"error": "authorization_pending"}), _Resp(200, {"access_token": "a0"})],
        _LEASE: [_Resp(200, {"leaseToken": "lease"})],
        _AUTHORIZE: [_Resp(200, {"code": "c0"})],
        _EXCHANGE: [_Resp(200, {"access_token": "cli", "refresh_token": "r0", "expires_in": 3600})],
    }


def test_sign_in_rides_out_a_lossy_route(network):
    """Every step can lose a request on the way and the sign-in still lands."""
    import requests

    script, calls = network
    script.update(_a_clean_sign_in())
    script[_DEVICE].insert(0, requests.ConnectionError("connection reset by peer"))
    script[_POLL].insert(0, requests.ReadTimeout("read timed out"))
    script[_LEASE].insert(0, _Resp(503))
    script[_AUTHORIZE].insert(0, requests.ConnectTimeout("connect timed out"))
    script[_EXCHANGE].insert(0, _Resp(502))

    assert dulus_account.sign_in(notify=lambda m: None) == ("ok", "cli")
    assert calls.count(_DEVICE) == 2 and calls.count(_LEASE) == 2
    assert dulus_account.load_store()["lease_token"] == "lease"


def test_login_still_hands_back_just_the_token(network):
    script, _ = network
    script.update(_a_clean_sign_in())
    assert dulus_account.login(notify=lambda m: None) == "cli"


def test_a_login_server_that_never_answers_is_unreachable(network):
    import requests

    script, calls = network
    script[_DEVICE] = [requests.ConnectionError("connection reset by peer")]
    said: list = []

    assert dulus_account.sign_in(notify=said.append) == ("unreachable", None)
    assert calls == [_DEVICE] * 3
    # Name what didn't answer, then the two ways through: a proxy, or a key
    # minted on a machine that can reach Dulus.
    text = "\n".join(said)
    assert dulus_account._AUTH0_DOMAIN in text
    assert "HTTPS_PROXY" in text and "DULUS_API_KEY" in text


def test_a_wifi_login_page_is_not_an_answer(network):
    script, _ = network
    script[_DEVICE] = [_Page(200)]
    assert dulus_account.sign_in(notify=lambda m: None) == ("unreachable", None)


def test_polls_that_never_get_through_are_unreachable(network):
    import requests

    script, _ = network
    script.update(_a_clean_sign_in())
    script[_POLL] = [requests.ConnectTimeout("connect timed out")]
    assert dulus_account.sign_in(notify=lambda m: None) == ("unreachable", None)


def test_dulus_api_out_of_reach_after_approval_is_unreachable(network):
    script, _ = network
    script.update(_a_clean_sign_in())
    script[_LEASE] = [_Resp(503)]
    assert dulus_account.sign_in(notify=lambda m: None) == ("unreachable", None)


@pytest.mark.parametrize("url, reply", [
    (_DEVICE, _Resp(403, {"error": "unauthorized_client"})),
    (_POLL, _Resp(403, {"error": "access_denied"})),
    (_POLL, _Resp(400, {"error": "authorization_pending"})),  # the code ran out unapproved
    (_LEASE, _Resp(401, {"detail": "invalid token"})),
])
def test_a_real_no_is_refused_not_unreachable(network, url, reply):
    """Only a network that can't get an answer opens the gate; a "no" keeps it shut."""
    script, _ = network
    script.update(_a_clean_sign_in())
    script[url] = [reply]
    assert dulus_account.sign_in(notify=lambda m: None) == ("refused", None)


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

    def sign_in(notify=print, **options):
        seen["login_options"] = options
        return seen.setdefault("login", ("ok", "token"))

    monkeypatch.setattr(dulus_account, "session_status", status)
    monkeypatch.setattr(dulus_account, "sign_in", sign_in)
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
    assert gate["login"] == ("ok", "token")


def test_gate_stops_when_sign_in_does_not_finish(gate):
    gate["login"] = ("refused", None)
    with pytest.raises(SystemExit) as exc:
        dulus._require_dulus_login(_args())
    assert exc.value.code == 1


def test_gate_stops_on_ctrl_c_during_sign_in(gate, monkeypatch):
    def interrupted(notify=print, **options):
        raise KeyboardInterrupt

    monkeypatch.setattr(dulus_account, "sign_in", interrupted)
    with pytest.raises(SystemExit) as exc:
        dulus._require_dulus_login(_args())
    assert exc.value.code == 1


def test_gate_carries_on_when_the_sign_in_servers_are_unreachable(gate, capsys):
    """A network that filters the sign-in servers (mainland China…) must not lock anyone out."""
    gate["login"] = ("unreachable", None)
    dulus._require_dulus_login(_args())  # must not exit
    assert "carrying on" in capsys.readouterr().out.lower()


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

    def sign_in(notify=print, **options):
        notify("https://dulus.us.auth0.com/activate?user_code=ABCD-EFGH")
        shown_while_waiting.append(stderr.flushed)  # what's on screen while polling
        assert options["out"] is stderr  # the QR goes there too
        return "ok", "token"

    monkeypatch.setattr(dulus_account, "sign_in", sign_in)
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

    def sign_in(notify=print, **options):
        notify("https://dulus.us.auth0.com/activate?user_code=ABCD-EFGH")
        shown_while_waiting.append(pipe.flushed)
        return "ok", "token"

    monkeypatch.setattr(dulus_account, "sign_in", sign_in)
    dulus._require_dulus_login(_args())

    assert "user_code=ABCD-EFGH" in shown_while_waiting[0]


def test_a_crash_inside_the_sign_in_is_a_failed_sign_in_not_a_traceback(gate, monkeypatch, capsys):
    def sign_in(notify=print, **options):
        raise RuntimeError("proxy ate the reply")

    monkeypatch.setattr(dulus_account, "sign_in", sign_in)
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
