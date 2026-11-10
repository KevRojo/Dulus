"""Signing in where there is no desktop: SSH sessions, servers, containers.

Dulus won't start without a Dulus account, so the sign-in has to finish on
every machine it runs on. These pin what makes that true: the link and code
always reach the person, a browser is opened only where one can show up,
opening it can never take over the terminal, and waiting for approval rides
out a flaky network.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import threading

import pytest

import dulus
import dulus_account
import welcome

LINK = "https://dulus.us.auth0.com/activate?user_code=ABCD-EFGH"
SHORT_LINK = "https://dulus.us.auth0.com/activate"


@pytest.fixture()
def machine(monkeypatch):
    """A Linux box with nothing on it: no SSH, no display, no $BROWSER, no openers."""
    for name in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY",
                 "DISPLAY", "WAYLAND_DISPLAY", "BROWSER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    installed: set[str] = set()
    monkeypatch.setattr(dulus_account.shutil, "which",
                        lambda name: f"/usr/bin/{name}" if name in installed else None)
    return installed


def _commands(mode: str = "auto") -> list[list[str]]:
    return [opener.args[0] for opener in dulus_account._browser_openers(LINK, mode)]


# ── where a browser can show up ─────────────────────────────────────────────

def test_a_linux_desktop_opens_through_xdg_open(machine, monkeypatch):
    machine.update({"xdg-open", "gio"})
    monkeypatch.setenv("DISPLAY", ":0")
    assert _commands()[0] == ["xdg-open", LINK]


def test_wayland_counts_as_a_desktop(machine, monkeypatch):
    machine.add("xdg-open")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert _commands() == [["xdg-open", LINK]]


def test_a_server_with_no_display_is_headless(machine):
    # xdg-open is often installed on servers, but with no display all it can
    # do is fall back to a text browser in this very terminal.
    machine.update({"xdg-open", "www-browser", "lynx"})
    assert dulus_account._browser_openers(LINK) == []


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
@pytest.mark.parametrize("variable", ["SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"])
def test_over_ssh_nothing_opens_on_any_os(machine, monkeypatch, platform, variable):
    # Over SSH a browser would open on the far machine's screen, or nowhere —
    # on a Mac or a Windows box just as much as on Linux.
    machine.update({"xdg-open", "open"})
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setenv("DISPLAY", "localhost:10.0")  # X11 forwarding still means SSH
    monkeypatch.setenv(variable, "203.0.113.7 51000 10.0.0.5 22")
    assert dulus_account._browser_openers(LINK) == []


def test_macos_opens_with_open(machine, monkeypatch):
    machine.add("open")
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _commands() == [["open", LINK]]


def test_windows_opens_through_the_shell(machine, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    openers = dulus_account._browser_openers(LINK)
    assert [(o.func, o.args) for o in openers] == [(dulus_account._start_file, (LINK,))]


def test_wsl_opens_the_windows_browser(machine):
    machine.add("wslview")
    assert _commands() == [["wslview", LINK]]


def test_headless_flag_never_opens_anything(machine, monkeypatch):
    machine.add("xdg-open")
    monkeypatch.setenv("DISPLAY", ":0")
    assert dulus_account._browser_openers(LINK, "never") == []


def test_browser_flag_tries_over_ssh_too(machine, monkeypatch):
    machine.add("xdg-open")
    monkeypatch.setenv("DISPLAY", "localhost:10.0")
    monkeypatch.setenv("SSH_CONNECTION", "203.0.113.7 51000 10.0.0.5 22")
    assert _commands("always") == [["xdg-open", LINK]]


def test_an_explicit_browser_variable_is_honoured_without_a_desktop(machine, monkeypatch):
    # VS Code sets $BROWSER in remote and container terminals to a helper that
    # opens the link on the person's own machine.
    helper = "/home/me/.vscode-server/bin/abc/bin/helpers/browser.sh"
    machine.add(helper)
    monkeypatch.setenv("SSH_CONNECTION", "203.0.113.7 51000 10.0.0.5 22")
    monkeypatch.setenv("BROWSER", helper)
    assert _commands() == [[helper, LINK]]


def test_a_browser_variable_with_a_placeholder(machine, monkeypatch):
    machine.add("firefox")
    monkeypatch.setenv("BROWSER", "firefox --new-tab %s")
    assert _commands() == [["firefox", "--new-tab", LINK]]


def test_text_browsers_are_never_started(machine, monkeypatch):
    machine.update({"w3m", "lynx", "xdg-open"})
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("BROWSER", os.pathsep.join(["w3m", "lynx -accept_all_cookies %s"]))
    assert _commands() == [["xdg-open", LINK]]


@pytest.mark.parametrize("command, text", [
    ("w3m", True),
    ("/usr/bin/lynx", True),
    ("links2", True),
    ("www-browser", True),
    ("LYNX.EXE", True),
    ("lynx -accept_all_cookies", True),
    # Debian's *graphical* default; the old substring match called it a text browser.
    ("x-www-browser", False),
    ("firefox", False),
    ("google-chrome", False),
    ("", False),
])
def test_text_browsers_are_told_apart(command, text):
    assert dulus_account._is_text_browser(command) is text


# ── opening one can never take over the terminal ────────────────────────────

class _Proc:
    def __init__(self, exit_code=0, hang=False):
        self.exit_code, self.hang = exit_code, hang

    def wait(self, timeout=None):
        if self.hang:
            raise subprocess.TimeoutExpired("opener", timeout)
        return self.exit_code


def test_openers_run_cut_off_from_the_terminal(monkeypatch):
    seen = {}

    def popen(argv, **options):
        seen.update(options)
        return _Proc(exit_code=0)

    monkeypatch.setattr(dulus_account.subprocess, "Popen", popen)
    assert dulus_account._spawn_detached(["xdg-open", LINK]) is True
    assert seen["stdin"] == seen["stdout"] == seen["stderr"] == subprocess.DEVNULL
    assert seen["start_new_session"] is True


@pytest.mark.parametrize("proc, opened", [
    (_Proc(exit_code=0), True),
    (_Proc(exit_code=3), False),       # xdg-open: "no method available"
    (_Proc(hang=True), True),          # still running: that's the browser itself
    (FileNotFoundError("gio"), False),
])
def test_an_opener_counts_only_when_it_worked(monkeypatch, proc, opened):
    def popen(argv, **options):
        if isinstance(proc, BaseException):
            raise proc
        return proc

    monkeypatch.setattr(dulus_account.subprocess, "Popen", popen)
    assert dulus_account._spawn_detached(["xdg-open", LINK]) is opened


@pytest.mark.skipif(sys.platform == "win32", reason="sessions and /dev/null are POSIX")
def test_a_real_opener_gets_no_terminal_and_its_own_session():
    # What a text browser started from here would get: nothing to draw on and
    # nothing to read from.
    probe = (
        "import os, sys\n"
        "null = os.stat(os.devnull)\n"
        "cut_off = all(os.path.samestat(os.fstat(fd), null) for fd in (0, 1, 2))\n"
        "sys.exit(0 if cut_off and os.getsid(0) == os.getpid() else 1)\n"
    )
    assert dulus_account._spawn_detached([sys.executable, "-c", probe]) is True


# ── the sign-in itself ──────────────────────────────────────────────────────

class _Reply:
    def __init__(self, status: int = 200, body=None):
        self.status_code = status
        self._body = body
        self.text = body if isinstance(body, str) else ""

    def json(self):
        if not isinstance(self._body, dict):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._body


PENDING = _Reply(403, {"error": "authorization_pending"})
APPROVED = _Reply(200, {"access_token": "auth0-token"})


class _LoginServer:
    """Auth0 and the Dulus API, scripted. ``polls`` answer the device flow in order."""

    def __init__(self, polls=(), starts=None, token=None):
        self.device_code = _Reply(200, {
            "device_code": "dev-123", "user_code": "ABCD-EFGH",
            "verification_uri": SHORT_LINK, "verification_uri_complete": LINK,
            "interval": 5, "expires_in": 900,
        })
        self.starts = list(starts) if starts is not None else [self.device_code]
        self.polls = list(polls)
        self.token = token or _Reply(200, {"access_token": "cli-token", "refresh_token": "r",
                                           "expires_in": 3600})
        self.on_first_poll = None
        self.polled = 0

    def _answer(self, script, fallback):
        step = script.pop(0) if script else fallback
        if isinstance(step, BaseException):
            raise step
        return step

    def post(self, url, **_):
        if url.endswith("/oauth/device/code"):
            return self._answer(self.starts, self.device_code)
        if "auth0.com" in url:
            self.polled += 1
            if self.polled == 1 and self.on_first_poll:
                self.on_first_poll()
            return self._answer(self.polls, PENDING)
        if url.endswith("/v1/oauth/authorize"):
            return _Reply(200, {"code": "auth-code"})
        if url.endswith("/v1/oauth/token"):
            return self.token
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url, **_):
        assert url.endswith("/api/entitlements")
        return _Reply(200, {"leaseToken": "lease", "leaseExpiresAt": None})


class _Clock:
    """Stands in for ``time`` inside dulus_account, so waiting costs nothing."""

    def __init__(self):
        self.now = 1_000_000.0
        self.wall = 1_000_000.0
        self.slept = 0.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.wall

    def sleep(self, seconds):
        self.now += seconds
        self.wall += seconds
        self.slept += seconds


@pytest.fixture()
def server(monkeypatch, tmp_path):
    monkeypatch.setenv("DULUS_HOME", str(tmp_path))
    monkeypatch.delenv("DULUS_API_KEY", raising=False)
    fake = _LoginServer()
    monkeypatch.setitem(sys.modules, "requests", fake)
    monkeypatch.setattr(dulus_account, "time", _Clock())
    monkeypatch.setattr(dulus_account, "_browser_openers", lambda url, mode="auto": [])
    return fake


def _sign_in(**options):
    said: list[str] = []
    token = dulus_account.login(notify=said.append, **options)
    return token, "\n".join(said)


def test_a_headless_sign_in_shows_link_and_code_before_waiting(server):
    on_screen: list[str] = []
    said: list[str] = []
    server.on_first_poll = lambda: on_screen.append("\n".join(said))
    server.polls = [PENDING, APPROVED]

    assert dulus_account.login(notify=said.append) == "cli-token"
    assert LINK in on_screen[0]
    assert f"Or go to {SHORT_LINK} and enter ABCD-EFGH" in on_screen[0]
    assert "Not opening a browser here" in on_screen[0]
    assert "Signed in." in said[-1]


def test_a_desktop_opens_the_browser_after_the_link_is_up(server, monkeypatch):
    said: list[str] = []
    shown_when_opened: list[str] = []

    def open_it():
        shown_when_opened.append("\n".join(said))
        return True

    monkeypatch.setattr(dulus_account, "_browser_openers", lambda url, mode="auto": [open_it])
    server.polls = [APPROVED]

    assert dulus_account.login(notify=said.append) == "cli-token"
    assert LINK in shown_when_opened[0]
    assert any("Opening your browser — check it shows ABCD-EFGH" in line for line in said)


def test_a_browser_that_does_not_open_is_reported_not_claimed(server, monkeypatch):
    monkeypatch.setattr(dulus_account, "_browser_openers", lambda url, mode="auto": [lambda: False])
    server.polls = [APPROVED]

    token, said = _sign_in()

    assert token == "cli-token"
    assert "Couldn't open a browser here — use the link above" in said
    assert "Opening your browser" not in said


def test_a_hanging_browser_launcher_never_blocks_the_sign_in(server, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(dulus_account, "_BROWSER_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(dulus_account, "_browser_openers",
                        lambda url, mode="auto": [lambda: release.wait(30)])
    server.polls = [APPROVED]
    try:
        assert _sign_in()[0] == "cli-token"
    finally:
        release.set()


def test_the_browser_mode_reaches_the_opener_choice(server, monkeypatch):
    modes = []
    monkeypatch.setattr(dulus_account, "_browser_openers",
                        lambda url, mode="auto": modes.append((url, mode)) or [])
    server.polls = [APPROVED]
    _sign_in(browser="never")
    assert modes == [(LINK, "never")]


def _qr_of(data: str) -> str:
    segno = pytest.importorskip("segno")
    buf = io.StringIO()
    segno.make_qr(data, error="m").terminal(out=buf, compact=True)
    return buf.getvalue()


def test_a_headless_sign_in_draws_a_qr_of_the_link(server, monkeypatch):
    expected = _qr_of(LINK)
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "60")
    monkeypatch.delenv("NO_COLOR", raising=False)
    screen = io.StringIO()
    server.polls = [APPROVED]

    assert _sign_in(out=screen)[0] == "cli-token"
    drawn = screen.getvalue()
    # Pure white on pure black whatever the terminal's theme: left to the
    # theme, a light one inverts the QR and many phone scanners give up.
    assert drawn.count("\033[38;5;231;48;5;16m") == len(expected.splitlines())
    assert re.sub(r"\033\[[0-9;]*m", "", drawn) == expected


def test_a_browser_that_fails_to_open_still_gets_the_phone_a_qr(server, monkeypatch):
    # The desktop was a mirage — a tmux pane on a server that kept an old
    # DISPLAY — so the person is on the phone route after all.
    expected = _qr_of(LINK)
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "60")
    monkeypatch.setattr(dulus_account, "_browser_openers", lambda url, mode="auto": [lambda: False])
    screen = io.StringIO()
    server.polls = [APPROVED]

    assert _sign_in(out=screen)[0] == "cli-token"
    assert re.sub(r"\033\[[0-9;]*m", "", screen.getvalue()) == expected


def test_a_browser_that_opens_gets_no_qr(server, monkeypatch):
    _qr_of(LINK)  # skips without segno
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "60")
    monkeypatch.setattr(dulus_account, "_browser_openers", lambda url, mode="auto": [lambda: True])
    screen = io.StringIO()
    server.polls = [APPROVED]

    _sign_in(out=screen)

    assert screen.getvalue() == ""


def test_no_color_gets_a_plain_qr(server, monkeypatch):
    expected = _qr_of(LINK)
    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setenv("LINES", "60")
    monkeypatch.setenv("NO_COLOR", "1")
    screen = io.StringIO()
    server.polls = [APPROVED]

    _sign_in(out=screen)

    assert screen.getvalue() == expected


def test_no_qr_when_it_would_push_the_link_off_screen(server, monkeypatch):
    _qr_of(LINK)  # skips without segno
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setenv("LINES", "24")
    screen = io.StringIO()
    server.polls = [APPROVED]

    token, said = _sign_in(out=screen)

    assert token == "cli-token"
    assert screen.getvalue() == ""
    assert LINK in said


def test_waiting_rides_out_a_flaky_network(server):
    server.polls = [
        ConnectionError("network is unreachable"),
        _Reply(503, "<html>Service Unavailable</html>"),
        _Reply(200, "<html>Welcome to the hotel Wi-Fi</html>"),  # a captive portal
        _Reply(429, {"error": "slow_down"}),
        PENDING,
        APPROVED,
    ]

    token, said = _sign_in()

    assert token == "cli-token"
    assert said.count("still trying") == 1
    # RFC 8628: slow_down adds five seconds to every later poll.
    assert dulus_account.time.slept == 5 * 4 + 10 * 2


@pytest.mark.parametrize("answer, message", [
    (_Reply(403, {"error": "access_denied"}), "Sign-in denied."),
    (_Reply(403, {"error": "expired_token"}), "The login code expired."),
    (_Reply(400, {"error": "invalid_grant", "error_description": "Invalid device code."}),
     "Login failed: Invalid device code."),
])
def test_a_final_answer_ends_the_wait(server, answer, message):
    server.polls = [PENDING, answer, APPROVED]
    token, said = _sign_in()
    assert token is None
    assert message in said


def test_the_code_is_waited_on_for_its_whole_lifetime(server):
    # Approving from a phone may mean creating the account first. The wait used
    # to give up after five minutes on a code that lives fifteen.
    token, said = _sign_in()

    assert token is None
    assert "the code expires in 15 min" in said
    assert "timed out" in said
    assert 900 <= dulus_account.time.slept < 900 + 5 + 1


def test_the_clock_being_set_mid_wait_does_not_end_the_sign_in(server):
    # A Raspberry Pi boots with no idea of the date; NTP then jumps the wall
    # clock by years — often while someone is approving from their phone.
    def ntp_sync():
        dulus_account.time.wall += 20 * 365 * 24 * 3600

    server.on_first_poll = ntp_sync
    server.polls = [PENDING, PENDING, APPROVED]

    assert _sign_in()[0] == "cli-token"


def test_starting_the_sign_in_retries_a_flaky_network(server):
    server.starts = [ConnectionError("dns"), _Reply(502, "<html>Bad Gateway</html>"),
                     server.device_code]
    server.polls = [APPROVED]

    token, said = _sign_in()

    assert token == "cli-token"
    assert "trying again" in said


def test_an_unreachable_login_server_says_what_to_check(server):
    server.starts = [ConnectionError("dns")] * 3

    token, said = _sign_in()

    assert token is None
    assert "Couldn't get a sign-in code from the login server (ConnectionError)" in said
    assert "HTTPS_PROXY" in said


def test_a_proxy_page_instead_of_a_device_code_is_not_a_crash(server):
    server.starts = [_Reply(200, "<html>Please log in to the proxy</html>")]
    token, said = _sign_in()
    assert token is None
    assert "(HTTP 200)" in said


def test_a_refusal_to_start_is_reported_as_such(server):
    server.starts = [_Reply(403, {"error": "unauthorized_client",
                                  "error_description": "Grant type not allowed"})]
    token, said = _sign_in()
    assert token is None
    assert "wouldn't start a sign-in: Grant type not allowed" in said
    assert "HTTPS_PROXY" not in said


def test_a_garbled_token_reply_after_approval_is_not_a_crash(server):
    server.polls = [APPROVED]
    server.token = _Reply(200, "<html>oops</html>")

    token, said = _sign_in()

    assert token is None
    assert "Token exchange rejected (200)" in said
    assert "Signed in." not in said


# ── /login dulus and the welcome wizard ─────────────────────────────────────

@pytest.mark.parametrize("args, mode", [
    ("dulus", "auto"),
    ("dulus --headless", "never"),
    ("dulus headless", "never"),
    ("dulus --no-browser", "never"),
    ("dulus --browser", "always"),
    ("dulus force --headless", "never"),
])
def test_login_dulus_flags_pick_the_browser_mode(monkeypatch, args, mode):
    # --headless used to *force* the raw browser open — on a headless box that
    # started lynx inside the terminal and froze the sign-in.
    seen = {}

    def login(notify=print, **options):
        seen.update(options)
        return None

    monkeypatch.setattr(dulus_account, "load_store", lambda: {})
    monkeypatch.setattr(dulus_account, "clear_store", lambda: None)
    monkeypatch.setattr(dulus_account, "login", login)

    assert dulus.cmd_login(args, None, {}) is True
    assert seen["browser"] == mode
    assert seen["out"] is sys.stdout


def test_the_welcome_wizard_does_not_ask_to_sign_in_twice(monkeypatch):
    # The launch gate has just signed this person in; the wizard's default
    # choice used to start a second sign-in — two approvals from a phone.
    monkeypatch.setattr(dulus_account, "session_status", lambda renew=True: "active")
    calls = []
    monkeypatch.setattr(dulus_account, "login", lambda *a, **options: calls.append(options))
    config: dict = {}
    welcome._setup_dulus_account(config, "dulus-b-27b")
    assert calls == []
    assert config["model"] == "dulus/dulus-b-27b"


def test_the_welcome_wizard_still_signs_in_when_needed(monkeypatch):
    calls = []
    monkeypatch.setattr(dulus_account, "session_status", lambda renew=True: "none")
    monkeypatch.setattr(dulus_account, "login", lambda **options: calls.append(options) or "token")
    welcome._setup_dulus_account({}, "dulus-b-27b")
    assert calls == [{"out": sys.stdout}]
