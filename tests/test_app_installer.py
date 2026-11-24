"""From the pip package to the Dulus app: /app, /update, the welcome wizard,
the startup notice and what the agent tells people.

`pip install dulus` gets the open-source core; the maintained Dulus is the app,
released on github.com/Dulus-Ai/dulus-updates. These pin that every surface
points at the right build for the machine, that a download is only handed over
when it matches the release's sha256, and that nothing installs from Telegram,
the web chat or a pipe.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import threading
import unicodedata
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

import app_installer as A
import dulus
import welcome
from app_installer import Platform

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
BASE = "https://github.com/Dulus-Ai/dulus-updates/releases/download/v7.0.4/"

# v7.0.4 as GitHub's API returns it (names, sizes and digests are the real ones).
RELEASE_JSON = {
    "tag_name": "v7.0.4",
    "name": "Dulus v7.0.4",
    "published_at": "2026-11-22T17:20:16Z",
    "html_url": "https://github.com/Dulus-Ai/dulus-updates/releases/tag/v7.0.4",
    "assets": [
        {"name": name, "size": size, "browser_download_url": BASE + name, "digest": "sha256:" + sha}
        for name, size, sha in [
            ("Dulus-7.0.4-linux-amd64.deb", 453111916,
             "45fe194c689a5136e18ce206927ea44539544a6a0179139443c460748ddd04c1"),
            ("Dulus-7.0.4-linux-amd64.deb.sha256", 94,
             "440170c37b330a74ef6515163976abb9c762e9440cfed7fe40d401b256935310"),
            ("Dulus-7.0.4-macos-arm64.pkg", 700924218,
             "7fb81f605d8ea40792e440ef832b78344b3e0fe8404c2364f1a9713705c81bd8"),
            ("Dulus-7.0.4-macos.dmg", 764715674,
             "5a01c10f426ab9ccd244e97ccbd4739ac49af1457c331919e83e6ea56e40e147"),
            ("Dulus-7.0.4-windows-setup.exe", 401778606,
             "e3de9068a0cc0a380856a2fe0c561c5e47f8eed181a0128f15837c1a775e7916"),
            ("Dulus-Android-alpha.apk", 98994786,
             "e34b84afa5aef4dd8f45ba428b33fe1f0c3bd83de65709eea011d5c5e9da9e30"),
        ]
    ],
}

WINDOWS = Platform("windows", "x64")
MAC = Platform("macos", "arm64")
UBUNTU = Platform("linux", "x64", pkg="deb")
PI = Platform("linux", "arm64", pkg="deb")


def _release(data: dict | None = None) -> A.Release:
    rel = A._parse_release(data or RELEASE_JSON)
    assert rel is not None
    return rel


def _out(capsys) -> str:
    captured = capsys.readouterr()
    return ANSI.sub("", captured.out + captured.err)


def _cols(line: str) -> int:
    """Terminal columns: wide and emoji-presentation characters take two."""
    cols = 0
    for i, ch in enumerate(line):
        if ch in "\ufe0f\u200d" or unicodedata.combining(ch):
            continue
        wide = unicodedata.east_asian_width(ch) in "WF" or line[i + 1:i + 2] == "\ufe0f"
        cols += 2 if wide else 1
    return cols


class Response(io.BytesIO):
    """What urlopen hands back: a readable body with a status and headers."""

    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


@pytest.fixture()
def github(monkeypatch):
    """Answers A._open from a URL table; every call lands in .calls."""

    class GitHub:
        def __init__(self):
            self.routes: dict = {}
            self.calls: list[tuple[str, dict]] = []

        def __call__(self, url, timeout, headers=None):
            self.calls.append((url, dict(headers or {})))
            route = self.routes.get(url)
            if route is None:
                raise urllib.error.URLError("no route to host")
            return route(dict(headers or {})) if callable(route) else route

    gh = GitHub()
    gh.routes[A.LATEST_RELEASE_API] = lambda _h: Response(json.dumps(RELEASE_JSON).encode())
    monkeypatch.setattr(A, "_open", gh)
    return gh


@pytest.fixture(autouse=True)
def _private_cache(monkeypatch, tmp_path_factory):
    """Every test starts with no release cached."""
    cache = tmp_path_factory.mktemp("cache") / "app-release.json"
    monkeypatch.setattr(A, "_cache_path", lambda: cache)


# ── which build each machine gets ───────────────────────────────────────────

@pytest.mark.parametrize("plat, expected", [
    (WINDOWS, "Dulus-7.0.4-windows-setup.exe"),
    (Platform("windows", "arm64"), "Dulus-7.0.4-windows-setup.exe"),  # x64 emulation
    (MAC, "Dulus-7.0.4-macos-arm64.pkg"),                             # the .pkg, not the .dmg
    (Platform("macos", "x64"), None),                                 # Apple Silicon builds only
    (UBUNTU, "Dulus-7.0.4-linux-amd64.deb"),
    (Platform("linux", "x64", pkg="rpm"), None),
    (Platform("linux", "x64"), None),                                 # no package manager to drive
    (PI, None),
    (Platform("android", "arm64"), "Dulus-Android-alpha.apk"),
], ids=lambda p: p.label if isinstance(p, Platform) else str(p))
def test_each_machine_gets_its_own_build(plat, expected):
    asset = A.pick_asset(_release(), plat)
    assert (asset.name if asset else None) == expected


def test_a_checksum_file_is_never_taken_for_a_build():
    only_sums = {**RELEASE_JSON, "assets": [a for a in RELEASE_JSON["assets"]
                                            if a["name"].endswith(".sha256")]}
    assert A.pick_asset(_release(only_sums), UBUNTU) is None


def test_a_native_build_beats_an_emulated_one():
    data = {**RELEASE_JSON, "assets": [
        {"name": n, "size": 1, "browser_download_url": BASE + n}
        for n in ("Dulus-macos-x64.pkg", "Dulus-macos-arm64.dmg")]}
    assert A.pick_asset(_release(data), MAC).name == "Dulus-macos-arm64.dmg"


def test_builds_only_come_from_dulus_updates():
    data = {**RELEASE_JSON, "assets": [
        {"name": "Dulus-windows-setup.exe", "size": 1,
         "browser_download_url": "https://evil.example/Dulus-windows-setup.exe"},
        {"name": "..", "size": 1, "browser_download_url": BASE + ".."},
    ]}
    assert _release(data).assets == ()


@pytest.mark.parametrize("name, safe", [
    ("../../.bashrc", ".bashrc"),
    ("..\\..\\Dulus-setup.exe", "Dulus-setup.exe"),
    ("Dulus 7.0.4 (1).exe", "Dulus_7.0.4__1_.exe"),
    ("..", ""),
])
def test_a_download_never_leaves_the_download_folder(name, safe):
    assert A._safe_name(name) == safe


def test_the_release_digest_becomes_the_sha256_to_check():
    exe = A.pick_asset(_release(), WINDOWS)
    assert exe.sha256 == "e3de9068a0cc0a380856a2fe0c561c5e47f8eed181a0128f15837c1a775e7916"
    assert _release().date == "Nov 22, 2026"


def test_the_builds_on_offer_are_summed_up():
    assert A.builds_summary(_release()) == (
        "Windows (.exe) · macOS (.pkg, .dmg) · Linux (.deb) · Android (.apk)")


# ── telling machines apart ──────────────────────────────────────────────────

def test_apple_silicon_under_rosetta_is_still_apple_silicon(monkeypatch):
    monkeypatch.setattr(A.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(A.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(A, "_apple_silicon", lambda: True)
    assert A.detect_platform() == MAC


@pytest.mark.parametrize("tools, pkg", [({"dpkg", "rpm"}, "deb"), ({"rpm"}, "rpm"), (set(), "")])
def test_linux_installs_what_its_package_manager_takes(monkeypatch, tools, pkg):
    monkeypatch.setattr(A.platform, "system", lambda: "Linux")
    monkeypatch.setattr(A.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(A, "_on_android", lambda: False)
    monkeypatch.setattr(A, "_in_container", lambda: False)
    monkeypatch.setattr(A.shutil, "which",
                        lambda name: f"/usr/bin/{name}" if name in tools else None)
    assert A.detect_platform() == Platform("linux", "x64", pkg=pkg)


# ── asking GitHub ───────────────────────────────────────────────────────────

def test_the_latest_release_comes_from_dulus_updates(github):
    rel = A.latest_release()
    assert github.calls[0][0] == (
        "https://api.github.com/repos/Dulus-Ai/dulus-updates/releases/latest")
    assert rel.version == "7.0.4" and len(rel.assets) == 6


def test_offline_the_last_known_release_still_answers(github):
    A.latest_release()
    del github.routes[A.LATEST_RELEASE_API]
    assert A.latest_release().version == "7.0.4"


def test_a_used_up_rate_limit_is_explained(github):
    def limited(_headers):
        raise urllib.error.HTTPError(A.LATEST_RELEASE_API, 403, "rate limit",
                                     {"X-RateLimit-Remaining": "0"}, None)  # type: ignore[arg-type]
    github.routes[A.LATEST_RELEASE_API] = limited
    with pytest.raises(A.AppInstallError, match="rate limit"):
        A.latest_release()


# ── the startup notice ──────────────────────────────────────────────────────

def test_the_startup_notice_names_the_build_and_the_command(github, monkeypatch):
    monkeypatch.setattr(A, "detect_platform", lambda: MAC)
    lines = [ANSI.sub("", line) for line in A.startup_notice() or []]
    assert "Dulus v7.0.4" in lines[0] and "macOS (Apple Silicon)" in lines[0]
    assert lines[1].rstrip().endswith("/app")
    assert all(_cols(line) <= 76 for line in lines)


def test_the_startup_notice_answers_from_cache_between_boots(github, monkeypatch):
    monkeypatch.setattr(A, "detect_platform", lambda: WINDOWS)
    assert A.startup_notice() and A.startup_notice()
    assert len(github.calls) == 1


def test_after_a_failed_ask_boots_stay_quiet_for_an_hour(github, monkeypatch):
    monkeypatch.setattr(A, "detect_platform", lambda: WINDOWS)
    del github.routes[A.LATEST_RELEASE_API]
    assert A.startup_notice() is None
    assert A.startup_notice() is None
    assert len(github.calls) == 1  # a firewall that drops GitHub costs one timeout, not one a boot


@pytest.mark.parametrize("plat", [PI, Platform("linux", "x64", pkg="deb", container=True)],
                         ids=["no build", "container"])
def test_no_startup_notice_without_a_build_to_offer(github, monkeypatch, plat):
    monkeypatch.setattr(A, "detect_platform", lambda: plat)
    assert A.startup_notice() is None


# ── downloading ─────────────────────────────────────────────────────────────

PAYLOAD = b"dulus-app-build " * 4096
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()
ASSET = A.Asset("Dulus-7.0.4-linux-amd64.deb", len(PAYLOAD), BASE + "Dulus-7.0.4-linux-amd64.deb",
                PAYLOAD_SHA)


def test_a_download_lands_verified(github, tmp_path):
    github.routes[ASSET.url] = Response(PAYLOAD)
    seen = []
    path = A.download(ASSET, tmp_path, sha256=PAYLOAD_SHA,
                      progress=lambda d, t: seen.append((d, t)))
    assert path == tmp_path / ASSET.name and path.read_bytes() == PAYLOAD
    assert not (tmp_path / (ASSET.name + ".part")).exists()
    assert seen[-1] == (len(PAYLOAD), len(PAYLOAD))


def test_a_download_that_doesnt_match_the_release_is_deleted(github, tmp_path):
    github.routes[ASSET.url] = Response(b"x" * len(PAYLOAD))
    with pytest.raises(A.AppInstallError, match="sha256"):
        A.download(ASSET, tmp_path, sha256=PAYLOAD_SHA)
    assert list(tmp_path.iterdir()) == []


def test_an_interrupted_download_resumes_where_it_stopped(github, tmp_path):
    half = len(PAYLOAD) // 2
    (tmp_path / (ASSET.name + ".part")).write_bytes(PAYLOAD[:half])

    def ranged(headers):
        assert headers["Range"] == f"bytes={half}-"
        return Response(PAYLOAD[half:], status=206)

    github.routes[ASSET.url] = ranged
    assert A.download(ASSET, tmp_path, sha256=PAYLOAD_SHA).read_bytes() == PAYLOAD


def test_a_server_that_wont_resume_starts_over(github, tmp_path):
    (tmp_path / (ASSET.name + ".part")).write_bytes(b"stale bytes")
    github.routes[ASSET.url] = Response(PAYLOAD, status=200)
    assert A.download(ASSET, tmp_path, sha256=PAYLOAD_SHA).read_bytes() == PAYLOAD


def test_a_finished_download_is_reused_without_the_network(github, tmp_path):
    (tmp_path / ASSET.name).write_bytes(PAYLOAD)
    assert A.download(ASSET, tmp_path, sha256=PAYLOAD_SHA) == tmp_path / ASSET.name
    assert github.calls == []


def test_a_cut_connection_keeps_the_part_to_resume_from(github, tmp_path):
    class Cut(Response):
        def read(self, *args):
            raise ConnectionResetError("connection reset by peer")

    github.routes[ASSET.url] = Cut(b"")
    with pytest.raises(A.AppInstallError, match="resume"):
        A.download(ASSET, tmp_path, sha256=PAYLOAD_SHA)
    assert (tmp_path / (ASSET.name + ".part")).exists()


def test_a_full_disk_is_caught_before_downloading(github, tmp_path, monkeypatch):
    monkeypatch.setattr(A.shutil, "disk_usage",
                        lambda _p: SimpleNamespace(total=10 << 30, used=10 << 30, free=1 << 20))
    with pytest.raises(A.AppInstallError, match="free space"):
        A.download(ASSET, tmp_path, sha256=PAYLOAD_SHA)
    assert github.calls == []


def test_a_published_sha256_file_stands_in_for_a_missing_digest(github):
    data = json.loads(json.dumps(RELEASE_JSON))
    for asset in data["assets"]:
        asset["digest"] = ""
    rel = _release(data)
    deb = A.pick_asset(rel, UBUNTU)
    github.routes[BASE + "Dulus-7.0.4-linux-amd64.deb.sha256"] = Response(
        b"45FE194C689A5136E18CE206927EA44539544A6A0179139443C460748DDD04C1  "
        b"Dulus-7.0.4-linux-amd64.deb\n")
    assert A.expected_sha256(rel, deb) == (
        "45fe194c689a5136e18ce206927ea44539544a6a0179139443c460748ddd04c1")


# ── installing ──────────────────────────────────────────────────────────────

@pytest.fixture()
def linux_box(monkeypatch):
    """Linux with apt-get and sudo, not root; .runs records each command."""
    runs: list[list[str]] = []

    class Done:
        returncode = 0

    tools = ("apt-get", "dpkg", "sudo")
    monkeypatch.setattr(A.shutil, "which",
                        lambda name: f"/usr/bin/{name}" if name in tools else None)
    monkeypatch.setattr(A, "_is_root", lambda: False)
    monkeypatch.setattr(A.subprocess, "run", lambda cmd, **kw: runs.append(cmd) or Done())
    return runs


def test_a_deb_installs_through_apt_in_the_foreground(linux_box, tmp_path):
    deb = tmp_path / "Dulus-7.0.4-linux-amd64.deb"
    result = A.install(deb, UBUNTU)
    assert linux_box == [["sudo", "apt-get", "install", "-y", str(deb)]]
    assert result.finished


def test_root_installs_without_sudo(linux_box, tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_is_root", lambda: True)
    deb = tmp_path / "Dulus.deb"
    A.install(deb, UBUNTU)
    assert linux_box == [["apt-get", "install", "-y", str(deb)]]


def test_without_a_terminal_sudo_never_waits_for_a_password(linux_box, tmp_path):
    deb = tmp_path / "Dulus.deb"
    A.install(deb, UBUNTU, interactive=False)
    assert linux_box[0][:2] == ["sudo", "-n"]


def test_a_failed_install_says_how_to_retry_by_hand(linux_box, tmp_path, monkeypatch):
    class Failed:
        returncode = 100

    monkeypatch.setattr(A.subprocess, "run", lambda cmd, **kw: Failed())
    deb = tmp_path / "Dulus.deb"
    with pytest.raises(A.AppInstallError, match=re.escape(f"sudo apt-get install -y {deb}")):
        A.install(deb, UBUNTU)


@pytest.mark.parametrize("plat, name", [
    (WINDOWS, "Dulus-7.0.4-windows-setup.exe"),
    (MAC, "Dulus-7.0.4-macos-arm64.pkg"),
    (MAC, "Dulus-7.0.4-macos.dmg"),
], ids=["windows", "mac pkg", "mac dmg"])
def test_desktop_installers_open_like_a_double_click(monkeypatch, tmp_path, plat, name):
    for var in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"):
        monkeypatch.delenv(var, raising=False)
    opened = []
    monkeypatch.setattr(A, "_open_file", opened.append)
    result = A.install(tmp_path / name, plat)
    assert opened == [tmp_path / name] and not result.finished


def test_a_pkg_over_ssh_installs_with_installer(linux_box, monkeypatch, tmp_path):
    monkeypatch.setenv("SSH_CONNECTION", "203.0.113.7 51000 10.0.0.5 22")
    pkg = tmp_path / "Dulus-7.0.4-macos-arm64.pkg"
    assert A.install(pkg, MAC).finished
    assert linux_box == [["sudo", "installer", "-pkg", str(pkg), "-target", "/"]]


# ── retiring the pip copy ───────────────────────────────────────────────────

@pytest.mark.parametrize("prefix, managed, expected", [
    ("/home/k/.local/share/pipx/venvs/dulus", False, ["pipx", "uninstall", "dulus"]),
    ("C:\\Users\\k\\pipx\\venvs\\dulus", False, ["pipx", "uninstall", "dulus"]),
    ("/home/k/.local/share/uv/tools/dulus", False, ["uv", "tool", "uninstall", "dulus"]),
    ("/usr", False, ["/usr/bin/python3", "-m", "pip", "uninstall", "dulus"]),
    ("/usr", True, ["/usr/bin/python3", "-m", "pip", "uninstall", "dulus",
                    "--break-system-packages"]),
], ids=["pipx", "pipx windows", "uv tool", "pip", "pip PEP 668"])
def test_the_pip_copy_is_retired_the_way_it_was_installed(prefix, managed, expected):
    assert A._uninstall_command(prefix, "/usr/bin/python3", managed) == expected


def test_a_source_checkout_has_no_pip_copy_to_retire():
    # The suite runs from a checkout (or an editable install, which leaves a
    # dulus.egg-info right here): someone working on the core must never be
    # told to uninstall it.
    assert A.pip_uninstall_command() is None


def test_a_pip_install_is_told_how_to_retire(monkeypatch, tmp_path):
    site = tmp_path / "site-packages"
    (site / "dulus-3.15.4.dist-info").mkdir(parents=True)
    monkeypatch.setattr(A, "__file__", str(site / "app_installer.py"))
    monkeypatch.setattr(A.sys, "prefix", str(tmp_path))
    cmd = A.pip_uninstall_command()
    assert cmd is not None and cmd[1:4] == ["-m", "pip", "uninstall"]


# ── the /app conversation ───────────────────────────────────────────────────

@pytest.mark.parametrize("answer, expected", [("", True), ("y", True), ("sí", True), ("n", False)])
def test_enter_means_yes(monkeypatch, answer, expected):
    monkeypatch.setattr("builtins.input", lambda _prompt="": answer)
    assert A.ask_yes("Install? ") is expected


@pytest.mark.parametrize("error", [KeyboardInterrupt, EOFError])
def test_ctrl_c_or_a_closed_stdin_is_a_no(monkeypatch, error):
    def interrupted(_prompt=""):
        raise error

    monkeypatch.setattr("builtins.input", interrupted)
    assert A.ask_yes("Install? ") is False


def test_saying_no_downloads_nothing(monkeypatch, capsys):
    monkeypatch.setattr(A, "download", lambda *a, **k: pytest.fail("downloaded after a no"))
    rel = _release()
    assert A.offer(rel, A.pick_asset(rel, MAC), MAC, ask=lambda _q: False) == "declined"
    assert "/app gets it any time" in _out(capsys)


def test_an_accepted_offer_installs_and_says_how_to_retire_pip(monkeypatch, tmp_path, capsys):
    rel = _release()
    exe = A.pick_asset(rel, WINDOWS)
    monkeypatch.setattr(A, "download_dir", lambda: tmp_path)
    monkeypatch.setattr(A, "download", lambda asset, dest, **k: dest / asset.name)
    monkeypatch.setattr(A, "install",
                        lambda path, plat, **k: A.InstallResult(False, "Installer open."))
    monkeypatch.setattr(A, "pip_uninstall_command", lambda: ["pipx", "uninstall", "dulus"])

    assert A.offer(rel, exe, WINDOWS, ask=lambda _q: True) == "launched"
    text = _out(capsys)
    assert "sha256 verified" in text
    assert "Start menu" in text and "pipx uninstall dulus" in text
    next_steps = text[text.index("Next"):].splitlines()
    assert all(_cols(line) <= 80 for line in next_steps)


def test_a_failed_download_hands_over_the_direct_link(monkeypatch, tmp_path, capsys):
    rel = _release()
    exe = A.pick_asset(rel, WINDOWS)

    def cut(*_a, **_k):
        raise A.AppInstallError("the download was cut off — run it again to resume")

    monkeypatch.setattr(A, "download_dir", lambda: tmp_path)
    monkeypatch.setattr(A, "download", cut)
    assert A.offer(rel, exe, WINDOWS, assume_yes=True) == "failed"
    assert exe.url in _out(capsys)


# ── /app and /update ────────────────────────────────────────────────────────

@pytest.fixture()
def app_cmd(monkeypatch):
    """/app on a Mac with GitHub answering; .offers records each offer() call."""
    offers: list[dict] = []
    monkeypatch.setattr(A, "detect_platform", lambda: MAC)
    monkeypatch.setattr(A, "latest_release", lambda **k: _release())
    monkeypatch.setattr(A, "offer", lambda rel, asset, plat, **k: offers.append(
        {"asset": asset.name, **k}) or "launched")
    return offers


def test_app_in_a_terminal_offers_this_machines_build(app_cmd, monkeypatch, capsys):
    monkeypatch.setattr(dulus, "_app_can_install_here", lambda config: True)
    assert dulus.cmd_app("", None, {}) is True
    assert app_cmd == [{"asset": "Dulus-7.0.4-macos-arm64.pkg", "assume_yes": False,
                        "download_only": False, "interactive": False}]
    assert "Dulus-7.0.4-macos-arm64.pkg" in _out(capsys)


@pytest.mark.parametrize("args, flags", [
    ("now", {"assume_yes": True, "download_only": False}),
    ("download", {"assume_yes": False, "download_only": True}),
])
def test_app_subcommands(app_cmd, monkeypatch, args, flags):
    monkeypatch.setattr(dulus, "_app_can_install_here", lambda config: True)
    dulus.cmd_app(args, None, {})
    assert {k: app_cmd[0][k] for k in flags} == flags


def test_app_check_downloads_nothing(app_cmd, monkeypatch, capsys):
    monkeypatch.setattr(dulus, "_app_can_install_here", lambda config: True)
    dulus.cmd_app("check", None, {})
    assert app_cmd == []
    assert BASE + "Dulus-7.0.4-macos-arm64.pkg" in _out(capsys)


def test_app_from_telegram_or_the_web_chat_only_shows_the_link(app_cmd, capsys):
    # Those run slash commands on their own threads: an install there would pop
    # an installer on a screen nobody is watching.
    worker = threading.Thread(target=dulus.cmd_app, args=("now", None, {}))
    worker.start()
    worker.join()
    text = _out(capsys)
    assert app_cmd == []
    assert BASE + "Dulus-7.0.4-macos-arm64.pkg" in text
    assert "Run /app in a terminal on this machine" in text


def test_app_without_a_build_points_at_update_pip(app_cmd, monkeypatch, capsys):
    monkeypatch.setattr(A, "detect_platform", lambda: PI)
    dulus.cmd_app("", None, {})
    text = _out(capsys)
    assert app_cmd == []
    assert "No build for Linux (arm64) in v7.0.4 yet" in text and "/update pip" in text


def test_app_inside_a_container_points_at_the_host(app_cmd, monkeypatch, capsys):
    monkeypatch.setattr(A, "detect_platform",
                        lambda: Platform("linux", "x64", pkg="deb", container=True))
    monkeypatch.setattr(dulus, "_app_can_install_here", lambda config: True)
    dulus.cmd_app("", None, {})
    assert app_cmd == [] and "inside a container" in _out(capsys)


def test_app_says_where_to_go_when_github_cant_be_asked(monkeypatch, capsys):
    def offline(**_k):
        raise A.AppInstallError("couldn't reach GitHub (no route to host)")

    monkeypatch.setattr(A, "latest_release", offline)
    dulus.cmd_app("", None, {})
    assert A.RELEASES_PAGE in _out(capsys)


@pytest.mark.parametrize("args, forwarded", [("", ""), ("now", "now"), ("check", "check")])
def test_update_gets_the_app(monkeypatch, args, forwarded):
    seen = []
    monkeypatch.setattr(dulus, "cmd_app", lambda a, s, c: seen.append(a) or True)
    assert dulus.cmd_update(args, None, {}) is True
    assert seen == [forwarded]


def test_update_pip_still_upgrades_the_core_in_place(monkeypatch):
    import updater
    monkeypatch.setattr(updater, "is_update_available", lambda: (True, "3.15.4", "3.15.5"))
    upgraded = []
    monkeypatch.setattr(updater, "perform_update",
                        lambda target=None: upgraded.append(target) or (True, "Updated."))
    monkeypatch.setattr(dulus, "cmd_app", lambda *a: pytest.fail("/update pip went to the app"))
    dulus.cmd_update("pip", None, {})
    assert upgraded == ["3.15.5"]


def test_app_is_a_registered_command():
    for name in ("app", "install-app", "get-app"):
        assert dulus.COMMANDS[name] is dulus.cmd_app and name in dulus._CMD_META
    assert any(cmd.startswith("/app") for _, rows in dulus._HELP_PAGES for cmd, _ in rows)


def test_app_installer_ships_in_the_wheel():
    # A module missing from py-modules is missing from `pip install dulus`:
    # /app would die with ModuleNotFoundError on every real install.
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib  # type: ignore[no-redef]
    cfg = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml")
                        .read_text(encoding="utf-8"))
    assert "app_installer" in cfg["tool"]["setuptools"]["py-modules"]


# ── the welcome wizard ──────────────────────────────────────────────────────

class _ReachedCoreSetup(Exception):
    pass


@pytest.fixture()
def wizard(monkeypatch):
    """A first run at a terminal: the name is Ana; provider setup raises."""

    class TTY(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", TTY())
    monkeypatch.setattr(welcome, "_prompt", lambda question, default="": "Ana")
    monkeypatch.setattr(welcome, "show_welcome_banner", lambda **k: None)

    def core_setup(*_a, **_k):
        raise _ReachedCoreSetup

    monkeypatch.setattr(welcome, "_prompt_choice", core_setup)
    monkeypatch.setattr(A, "detect_platform", lambda: WINDOWS)
    monkeypatch.setattr(A, "latest_release", lambda **k: _release())


def test_the_wizard_offers_the_app_first_and_hands_over_to_it(wizard, monkeypatch, capsys):
    monkeypatch.setattr(A, "offer", lambda *a, **k: "launched")
    config = welcome.run_welcome_wizard({})
    assert config["user_name"] == "Ana"
    text = _out(capsys)
    assert "Dulus-7.0.4-windows-setup.exe" in text and "The app takes it from here" in text


def test_the_wizard_sets_up_the_core_when_the_app_is_declined(wizard, monkeypatch):
    monkeypatch.setattr(A, "offer", lambda *a, **k: "declined")
    with pytest.raises(_ReachedCoreSetup):
        welcome.run_welcome_wizard({})


@pytest.mark.parametrize("trouble", ["no build", "offline"])
def test_no_offer_when_there_is_nothing_to_offer(wizard, monkeypatch, capsys, trouble):
    if trouble == "no build":
        monkeypatch.setattr(A, "detect_platform", lambda: PI)
    else:
        def offline(**_k):
            raise A.AppInstallError("couldn't reach GitHub")
        monkeypatch.setattr(A, "latest_release", offline)
    monkeypatch.setattr(A, "offer", lambda *a, **k: pytest.fail("offered with nothing to offer"))
    with pytest.raises(_ReachedCoreSetup):
        welcome.run_welcome_wizard({})
    assert "The Dulus app" not in _out(capsys)


# ── what the agent tells people ─────────────────────────────────────────────

def test_the_agent_sends_people_to_app_not_pip():
    from context import build_system_prompt
    prompt = build_system_prompt({"model": "dulus/dulus-b-27b"})
    assert "type /app" in prompt and "github.com/Dulus-Ai/dulus-updates" in prompt
    assert "after `pip install dulus`" not in prompt


def test_no_sudo_and_not_root_says_to_run_it_as_root(linux_box, tmp_path, monkeypatch):
    monkeypatch.setattr(A.shutil, "which",
                        lambda name: "/usr/bin/apt-get" if name == "apt-get" else None)
    deb = tmp_path / "Dulus.deb"
    expected = re.escape(f"as root, run: apt-get install -y {deb}")
    with pytest.raises(A.AppInstallError, match=expected):
        A.install(deb, UBUNTU)
    assert linux_box == []
