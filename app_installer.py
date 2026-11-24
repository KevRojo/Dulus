"""Dulus app installer — from the pip package to the Dulus app in one command.

`pip install dulus` gets the open-source core. The maintained Dulus is the
app: signed builds for Windows, macOS and Linux that also run in a terminal on
a server (`dulus --cli`), published as releases of
github.com/Dulus-Ai/dulus-updates. This module finds the newest release, picks
the build for this machine, downloads it (resumable, checked against the
sha256 the release publishes) and hands it to the OS installer. `/app` and
`/update` drive it; the welcome wizard and the startup notice offer it.

Every failure meant for the user is an AppInstallError whose message is
written for them. Nothing here may take the CLI down.

Public API:
    detect_platform() -> Platform
    latest_release(timeout=8, max_age=0) -> Release              # AppInstallError
    pick_asset(release, plat) -> Asset | None
    expected_sha256(release, asset) -> str
    download(asset, dest_dir, sha256="", progress=None) -> Path  # AppInstallError
    install(path, plat, interactive=True) -> InstallResult       # AppInstallError
    pip_uninstall_command() -> list[str] | None
    startup_notice(timeout=3) -> list[str] | None
    print_card(release, asset, plat) / offer(release, asset, plat)  # the /app screens
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

UPDATES_REPO = "Dulus-Ai/dulus-updates"
RELEASES_PAGE = f"https://github.com/{UPDATES_REPO}/releases/latest"
LATEST_RELEASE_API = f"https://api.github.com/repos/{UPDATES_REPO}/releases/latest"
CACHE_TTL_SEC = 6 * 3600       # the startup notice asks GitHub at most every 6h...
_RETRY_AFTER_FAIL_SEC = 3600   # ...and stays quiet for an hour after a failed ask
_USER_AGENT = "Dulus-AppInstaller/1.0"
# Builds are only ever fetched from the release downloads of the updates repo.
_ASSET_URL_PREFIX = f"https://github.com/{UPDATES_REPO}/releases/download/".lower()


class AppInstallError(Exception):
    """A failure to show the user as-is: the message is written for them."""


# ── What runs where ─────────────────────────────────────────────────────────

_OS_NAMES = {"windows": "Windows", "macos": "macOS", "linux": "Linux", "android": "Android"}


@dataclass(frozen=True)
class Platform:
    """The machine a build has to run on."""

    os: str                  # windows | macos | linux | android | whatever platform.system() says
    arch: str                # x64 | arm64 | x86 | the raw machine name
    pkg: str = ""            # Linux: deb | rpm | "" (no package manager we know how to drive)
    container: bool = False  # Docker/Podman: an install there vanishes with the container

    @property
    def label(self) -> str:
        """'macOS (Apple Silicon)', 'Windows (x64)', 'Linux (arm64)'."""
        name = _OS_NAMES.get(self.os, self.os.capitalize() or "this OS")
        arch = self.arch
        if self.os == "macos":
            arch = {"arm64": "Apple Silicon", "x64": "Intel"}.get(arch, arch)
        return f"{name} ({arch})"


def _norm_arch(machine: str) -> str:
    m = (machine or "").strip().lower()
    if m in ("x86_64", "amd64", "x64", "em64t"):
        return "x64"
    if m in ("arm64", "aarch64", "arm64e"):
        return "arm64"
    if m in ("i386", "i486", "i586", "i686", "x86"):
        return "x86"
    return m or "unknown"


def _apple_silicon() -> bool:
    """True on an Apple Silicon Mac, even when this Python runs under Rosetta."""
    try:
        out = subprocess.run(["sysctl", "-in", "hw.optional.arm64"],
                             capture_output=True, text=True, timeout=3)
        return out.stdout.strip() == "1"
    except Exception:
        return False


def _on_android() -> bool:
    return (hasattr(sys, "getandroidapilevel")
            or os.environ.get("PREFIX", "").startswith("/data/data/com.termux"))


def _in_container() -> bool:
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")


def _linux_package_format() -> str:
    """deb on Debian/Ubuntu and friends, rpm on Fedora/RHEL/SUSE, else ''."""
    if shutil.which("dpkg"):
        return "deb"
    if shutil.which("rpm"):
        return "rpm"
    return ""


def detect_platform() -> Platform:
    system = platform.system().lower()
    arch = _norm_arch(platform.machine())
    if system == "windows":
        return Platform("windows", arch)
    if system == "darwin":
        if arch == "x64" and _apple_silicon():
            arch = "arm64"
        return Platform("macos", arch)
    if system in ("linux", "android"):
        if system == "android" or _on_android():
            return Platform("android", arch)
        return Platform("linux", arch, pkg=_linux_package_format(), container=_in_container())
    return Platform(system or "unknown", arch)


# ── Releases ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Asset:
    name: str
    size: int
    url: str
    sha256: str = ""  # the digest GitHub publishes for the upload; "" when it has none


@dataclass(frozen=True)
class Release:
    tag: str
    name: str
    published_at: str  # ISO 8601, as GitHub sends it
    html_url: str
    assets: tuple[Asset, ...] = ()

    @property
    def version(self) -> str:
        return self.tag.lstrip("vV")

    @property
    def date(self) -> str:
        """'Nov 22, 2026', or '' when GitHub didn't say."""
        try:
            day = time.strptime(self.published_at[:10], "%Y-%m-%d")
        except ValueError:
            return ""
        return f"{time.strftime('%b', day)} {day.tm_mday}, {day.tm_year}"


def _safe_name(name: str) -> str:
    """An asset name usable as a file name: no directories, nothing odd."""
    base = re.sub(r"[^A-Za-z0-9._+-]", "_", os.path.basename(name.replace("\\", "/")))
    return base if base.strip(".") else ""


def _parse_release(data: object) -> Release | None:
    """A Release from GitHub's JSON, keeping only assets this module may fetch."""
    if not isinstance(data, dict):
        return None
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return None
    assets = []
    for raw in data.get("assets") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        url = str(raw.get("browser_download_url") or "")
        if not _safe_name(name) or not url.lower().startswith(_ASSET_URL_PREFIX):
            continue
        digest = str(raw.get("digest") or "").lower()
        sha256 = digest[7:] if digest.startswith("sha256:") else ""
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            sha256 = ""
        try:
            size = max(0, int(raw.get("size") or 0))
        except (TypeError, ValueError):
            size = 0
        assets.append(Asset(name=name, size=size, url=url, sha256=sha256))
    return Release(
        tag=tag,
        name=str(data.get("name") or tag),
        published_at=str(data.get("published_at") or ""),
        html_url=str(data.get("html_url") or RELEASES_PAGE),
        assets=tuple(assets),
    )


def _release_json(rel: Release) -> dict:
    """``rel`` in GitHub's own shape, so a cached copy goes back through _parse_release."""
    return {
        "tag_name": rel.tag, "name": rel.name, "published_at": rel.published_at,
        "html_url": rel.html_url,
        "assets": [{"name": a.name, "size": a.size, "browser_download_url": a.url,
                    "digest": f"sha256:{a.sha256}" if a.sha256 else ""} for a in rel.assets],
    }


def _trust_os_certificates() -> None:
    """Use the OS trust store, so TLS-intercepting corporate proxies still work."""
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass


def _open(url: str, timeout: float, headers: dict | None = None):
    _trust_os_certificates()
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def _describe(exc: BaseException) -> str:
    """Why talking to GitHub failed, in words a person can act on."""
    if isinstance(exc, urllib.error.HTTPError):
        headers = getattr(exc, "headers", None) or {}
        if exc.code == 429 or (exc.code == 403 and headers.get("X-RateLimit-Remaining") == "0"):
            return "GitHub's rate limit for your network is used up — try again in a few minutes"
        if exc.code == 404:
            return f"nothing published at github.com/{UPDATES_REPO}"
        return f"GitHub answered HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return f"couldn't reach GitHub ({exc.reason})"
    if isinstance(exc, TimeoutError):
        return "GitHub took too long to answer"
    return f"{type(exc).__name__}: {exc}"


# The cache remembers the last good answer and, separately, when asking last
# failed — so a failed ask neither makes an old release look fresh nor gets
# retried on every boot behind a firewall that drops GitHub.

def _cache_path() -> Path:
    try:
        from config import CONFIG_DIR
        return Path(CONFIG_DIR) / "cache" / "app-release.json"
    except Exception:
        return Path.home() / ".dulus" / "cache" / "app-release.json"


def _read_cache() -> dict:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_cache(data: dict) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _cached(data: dict) -> tuple[Release | None, float, float]:
    """(release, fetched_at, failed_at) from cache data; zeros when absent."""
    def stamp(key: str) -> float:
        try:
            return float(data.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    return _parse_release(data.get("release")), stamp("fetched_at"), stamp("failed_at")


def latest_release(*, timeout: float = 8.0, max_age: float = 0.0) -> Release:
    """The newest published release of the Dulus app.

    A cached answer younger than ``max_age`` seconds is used as-is. When GitHub
    can't be asked, any cached answer, however old, is better than none;
    without one this raises AppInstallError.
    """
    data = _read_cache()
    cached, fetched_at, _ = _cached(data)
    if cached and max_age > 0 and time.time() - fetched_at < max_age:
        return cached
    try:
        with _open(LATEST_RELEASE_API, timeout, {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }) as resp:
            rel = _parse_release(json.loads(resp.read().decode("utf-8")))
        if rel is None:
            raise AppInstallError(f"the latest release at github.com/{UPDATES_REPO} has no tag")
    except Exception as exc:
        reason = str(exc) if isinstance(exc, AppInstallError) else _describe(exc)
        _write_cache({**data, "failed_at": time.time(), "error": reason})
        if cached:
            return cached
        raise AppInstallError(reason) from exc
    _write_cache({"fetched_at": time.time(), "release": _release_json(rel)})
    return rel


# ── Picking the build ───────────────────────────────────────────────────────

_SIDECAR = re.compile(r"\.(sha256|sha512|sha1|md5|sig|asc|blockmap|ya?ml|json|txt|zsync)$", re.I)
_FORMATS = (".tar.gz", ".tgz", ".appimage", ".deb", ".rpm", ".pkg", ".dmg", ".msi", ".exe",
            ".apk", ".zip")
# What a build that names no architecture is built for. The macOS builds are
# Apple Silicon only (dulus.ai/download says so); an APK carries every ABI.
_DEFAULT_ARCH = {"windows": "x64", "macos": "arm64", "linux": "x64", "android": "universal"}


def _format(name: str) -> str:
    n = name.lower()
    return next((ext[1:] for ext in _FORMATS if n.endswith(ext)), "")


def _asset_os(name: str) -> str:
    n, fmt = name.lower(), _format(name)
    if fmt in ("exe", "msi") or re.search(r"windows|win(32|64)", n):
        return "windows"
    if fmt in ("dmg", "pkg") or re.search(r"mac|darwin|osx", n):
        return "macos"
    if fmt == "apk" or "android" in n:
        return "android"
    if fmt in ("deb", "rpm", "appimage") or "linux" in n:
        return "linux"
    return ""


def _asset_arch(name: str, os_name: str) -> str:
    n = name.lower()
    if "universal" in n:
        return "universal"
    if re.search(r"arm64|aarch64|apple[-_ ]?silicon", n):
        return "arm64"
    if re.search(r"x86[-_]64|amd64|x64|win64|intel", n):
        return "x64"
    if re.search(r"i[3-6]86|x86|win32", n):
        return "x86"
    return _DEFAULT_ARCH.get(os_name, "x64")


def _arch_order(plat: Platform) -> list[str]:
    """Architectures this machine runs, native first."""
    if plat.os == "windows":  # Windows on Arm runs x64 builds under emulation
        return {"arm64": ["arm64", "x64"], "x64": ["x64", "x86"]}.get(plat.arch, [plat.arch])
    if plat.os == "macos":    # Rosetta runs Intel builds on Apple Silicon, never the reverse
        return {"arm64": ["arm64", "universal", "x64"],
                "x64": ["x64", "universal"]}.get(plat.arch, [plat.arch])
    return [plat.arch, "universal"]


def _format_order(plat: Platform) -> list[str]:
    """Package formats this machine installs, best first."""
    if plat.os == "windows":
        return ["exe", "msi"]
    if plat.os == "macos":   # a .pkg also installs over SSH; a .dmg needs a desktop
        return ["pkg", "dmg"]
    if plat.os == "android":
        return ["apk"]
    if plat.os == "linux":
        return ([plat.pkg] if plat.pkg else []) + ["appimage"]
    return []


def _installable(rel: Release) -> list[Asset]:
    return [a for a in rel.assets if not _SIDECAR.search(a.name) and _asset_os(a.name)]


def pick_asset(rel: Release, plat: Platform) -> Asset | None:
    """The build in ``rel`` for this machine, or None when it has none."""
    arches, formats = _arch_order(plat), _format_order(plat)
    best: tuple[tuple[int, int, int], Asset] | None = None
    for asset in _installable(rel):
        if _asset_os(asset.name) != plat.os:
            continue
        fmt, arch = _format(asset.name), _asset_arch(asset.name, plat.os)
        if fmt not in formats or arch not in arches:
            continue
        # A native build beats an emulated one; then the preferred format; then
        # an installer ("setup") over a portable build of the same kind.
        rank = (arches.index(arch), formats.index(fmt),
                0 if re.search(r"setup|install", asset.name, re.I) else 1)
        if best is None or rank < best[0]:
            best = (rank, asset)
    return best[1] if best else None


def builds_summary(rel: Release) -> str:
    """'Windows (.exe) · macOS (.pkg, .dmg) · Linux (.deb)' — what ``rel`` ships."""
    found: dict[str, list[str]] = {}
    for asset in _installable(rel):
        fmts = found.setdefault(_asset_os(asset.name), [])
        fmt = "." + _format(asset.name) if _format(asset.name) else asset.name
        if fmt not in fmts:
            fmts.append(fmt)
    order = [os_name for os_name in _OS_NAMES if os_name in found]
    order += [os_name for os_name in found if os_name not in _OS_NAMES]
    return " · ".join(f"{_OS_NAMES.get(o, o)} ({', '.join(found[o])})" for o in order)


# ── Downloading ─────────────────────────────────────────────────────────────

def _size(n: float) -> str:
    """383 MB, 94.4 MB, 1.2 GB."""
    n = float(n or 0)
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit != "MB" or n >= 100 else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def download_dir() -> Path:
    """~/Downloads when it's there to write to, else the Dulus config dir's downloads/."""
    downloads = Path.home() / "Downloads"
    if downloads.is_dir() and os.access(downloads, os.W_OK):
        return downloads
    try:
        from config import CONFIG_DIR
        target = Path(CONFIG_DIR) / "downloads"
    except Exception:
        target = Path.home() / ".dulus" / "downloads"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_sha256(rel: Release, asset: Asset, timeout: float = 10.0) -> str:
    """The digest to check ``asset`` against: GitHub's own, else a published
    ``<name>.sha256``. '' when the release offers neither."""
    if asset.sha256:
        return asset.sha256
    sidecar = next((a for a in rel.assets if a.name.lower() == asset.name.lower() + ".sha256"),
                   None)
    if sidecar is None:
        return ""
    try:
        with _open(sidecar.url, timeout) as resp:
            text = resp.read(4096).decode("utf-8", "replace")
    except Exception:
        return ""
    found = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    return found.group(0).lower() if found else ""


ProgressFn = Callable[[int, int], None]


def download(asset: Asset, dest_dir: Path, *, sha256: str = "",
             progress: ProgressFn | None = None, timeout: float = 30.0) -> Path:
    """Fetch ``asset`` into ``dest_dir``; returns the verified file.

    An interrupted download resumes from its ``.part`` file, and a finished one
    that still checks out is reused without touching the network. A file whose
    size or sha256 doesn't match the release is never handed back.
    """
    name = _safe_name(asset.name)
    if not name:
        raise AppInstallError(f"refusing the odd file name {asset.name!r}")
    final, part = dest_dir / name, dest_dir / (name + ".part")

    def checks_out(path: Path) -> bool:
        if asset.size and path.stat().st_size != asset.size:
            return False
        return not sha256 or _sha256_of(path) == sha256

    if final.is_file() and checks_out(final):
        return final

    have = part.stat().st_size if part.is_file() else 0
    if asset.size and have > asset.size:
        part.unlink()
        have = 0
    if not asset.size or have < asset.size:
        need = asset.size - have
        free = shutil.disk_usage(dest_dir).free
        if asset.size and free < need + (64 << 20):
            raise AppInstallError(
                f"not enough free space in {dest_dir}: it needs {_size(need)}, "
                f"{_size(free)} is free")
        headers = {"Accept": "application/octet-stream"}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with _open(asset.url, timeout, headers) as resp:
                if have and getattr(resp, "status", 200) != 206:
                    have = 0  # this server won't resume: start over
                total = asset.size or have + int(resp.headers.get("Content-Length") or 0)
                done = have
                if progress:
                    progress(done, total)  # the starting point, so speed counts this run only
                with open(part, "ab" if have else "wb") as fh:
                    while True:
                        block = resp.read(1 << 20)
                        if not block:
                            break
                        fh.write(block)
                        done += len(block)
                        if progress:
                            progress(done, total)
        except urllib.error.HTTPError as exc:
            if not (exc.code == 416 and have):  # 416 on a resume: nothing left to send
                raise AppInstallError(f"the download failed: {_describe(exc)}") from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise AppInstallError(
                f"the download was cut off ({_describe(exc)}) — run it again to resume") from exc

    got = part.stat().st_size if part.is_file() else 0
    if not got or (asset.size and got != asset.size):
        raise AppInstallError(
            f"the download stopped at {_size(got)} of {_size(asset.size)} — run it again to resume")
    if sha256 and _sha256_of(part) != sha256:
        part.unlink()
        raise AppInstallError(
            "the download doesn't match the sha256 the release published, so it was deleted — "
            "run it again")
    os.replace(part, final)
    return final


# ── Installing ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InstallResult:
    finished: bool  # installed by the time install() returned (False: an installer is open)
    message: str


def _shell_join(cmd: list[str]) -> str:
    return subprocess.list2cmdline(cmd) if os.name == "nt" else shlex.join(cmd)


def _is_root() -> bool:
    geteuid = getattr(os, "geteuid", None)
    return bool(geteuid) and geteuid() == 0


def _privileged(cmd: list[str], interactive: bool) -> list[str] | None:
    """``cmd`` run as root — as-is for root, through sudo otherwise; None without sudo.

    Without a terminal, sudo can't ask for a password: -n makes it fail fast
    instead of hanging.
    """
    if _is_root():
        return cmd
    if shutil.which("sudo"):
        return ["sudo"] + ([] if interactive else ["-n"]) + cmd
    return None


def _package_command(path: Path, plat: Platform) -> list[str] | None:
    """The root command that installs ``path`` on this machine, if it takes one."""
    fmt, target = _format(path.name), str(path)
    if plat.os == "linux" and fmt == "deb":
        # apt-get pulls in the package's dependencies; bare dpkg can't.
        return (["apt-get", "install", "-y", target] if shutil.which("apt-get")
                else ["dpkg", "-i", target])
    if plat.os == "linux" and fmt == "rpm":
        for manager in ("dnf", "yum"):
            if shutil.which(manager):
                return [manager, "install", "-y", target]
        if shutil.which("zypper"):
            return ["zypper", "--non-interactive", "install", target]
        return ["rpm", "-U", target]
    if plat.os == "macos" and fmt == "pkg":
        return ["installer", "-pkg", target, "-target", "/"]
    return None


def _has_desktop() -> bool:
    """A Mac someone is sitting at, not one reached over SSH."""
    return not any(os.environ.get(v) for v in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"))


def _open_file(path: Path) -> None:
    """Open ``path`` the way a double-click would."""
    if sys.platform == "win32":
        os.startfile(str(path))  # ShellExecute, so the installer's UAC prompt shows up
        return
    opener = ("open" if sys.platform == "darwin"
              else shutil.which("termux-open") or shutil.which("xdg-open"))
    if not opener:
        raise AppInstallError(f"nothing here can open {path.name} — open it from your files")
    subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def manual_install_hint(path: Path, plat: Platform) -> str:
    """How to install ``path`` by hand, for when Dulus doesn't do it."""
    cmd = _package_command(path, plat)
    if cmd and (plat.os == "linux" or not _has_desktop()):
        return _shell_join(cmd if _is_root() else ["sudo"] + cmd)
    if _format(path.name) == "appimage":
        return _shell_join(["chmod", "+x", str(path)]) + " && " + _shell_join([str(path)])
    if plat.os == "windows":
        return _shell_join([str(path)])
    if plat.os == "macos":
        return _shell_join(["open", str(path)])
    if plat.os == "android":
        return _shell_join(["termux-open", str(path)])
    return str(path)


def install(path: Path, plat: Platform, *, interactive: bool = True) -> InstallResult:
    """Hand the downloaded build to the OS.

    Linux packages (and a .pkg on a Mac reached over SSH) install right here,
    through sudo, in the foreground so its password prompt works. Everything
    else opens the platform's own installer. Raises AppInstallError carrying
    the command to run by hand when it can't finish.
    """
    fmt = _format(path.name)
    cmd = _package_command(path, plat)
    if cmd and (plat.os == "linux" or not _has_desktop()):
        run = _privileged(cmd, interactive)
        if run is None:
            raise AppInstallError(f"installing needs root — as root, run: {_shell_join(cmd)}")
        code = subprocess.run(run).returncode
        if code != 0:
            raise AppInstallError(f"{cmd[0]} exited with code {code} — to retry by hand: "
                                  f"{manual_install_hint(path, plat)}")
        return InstallResult(True, "The Dulus app is installed.")
    if plat.os == "linux" and fmt == "appimage":
        path.chmod(path.stat().st_mode | 0o755)
        return InstallResult(True, f"Ready to run: {path}")
    if plat.os == "macos" and fmt == "dmg" and not _has_desktop():
        raise AppInstallError(f"a .dmg installs from the Mac's own screen — open {path} there")
    if plat.os in ("windows", "macos", "android"):
        _open_file(path)
        if fmt == "dmg":
            return InstallResult(False, "Drag Dulus into Applications in the window that opened.")
        if plat.os == "android":
            return InstallResult(False, "Android's installer is open — confirm the install there.")
        return InstallResult(False, "The installer is open — follow its steps.")
    raise AppInstallError(
        f"Dulus can't install {path.name} here — {manual_install_hint(path, plat)}")


# ── Retiring the pip copy ───────────────────────────────────────────────────

def _uninstall_command(prefix: str, executable: str, externally_managed: bool) -> list[str]:
    """The command that removes a dulus installed into ``prefix``."""
    where = prefix.replace("\\", "/").lower()
    if "/pipx/venvs/" in where:
        return ["pipx", "uninstall", "dulus"]
    if "/uv/tools/" in where:
        return ["uv", "tool", "uninstall", "dulus"]
    cmd = [executable, "-m", "pip", "uninstall", "dulus"]
    if externally_managed:  # PEP 668: pip refuses to touch the system Python without it
        cmd.append("--break-system-packages")
    return cmd


def pip_uninstall_command() -> list[str] | None:
    """How to remove the pip copy of Dulus that's running now.

    None when this isn't one. pip puts a ``dulus-<version>.dist-info`` next to
    the modules it installs; a source checkout or an editable install has none
    there (at most a ``dulus.egg-info``) — it belongs to someone working on the
    core, and there's nothing to retire.
    """
    try:
        here = Path(__file__).resolve().parent
        if not any(re.fullmatch(r"dulus-[^-]+\.dist-info", entry, re.I)
                   for entry in os.listdir(here)):
            return None
    except OSError:
        return None
    try:
        import sysconfig
        managed = (Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED").exists()
    except Exception:
        managed = False
    return _uninstall_command(sys.prefix, sys.executable, managed)


# ── The startup notice ──────────────────────────────────────────────────────

def startup_notice(timeout: float = 3.0) -> list[str] | None:
    """What to say about the app when Dulus starts; None when there's no build
    for this machine (or no answer about one).

    Cheap enough for every boot: answers come from a 6h cache, a failed ask
    keeps quiet for an hour, and it never raises.
    """
    try:
        plat = detect_platform()
        if plat.container:
            return None
        rel, fetched_at, failed_at = _cached(_read_cache())
        now = time.time()
        if (not (rel and now - fetched_at < CACHE_TTL_SEC)
                and now - failed_at >= _RETRY_AFTER_FAIL_SEC):
            rel = latest_release(timeout=timeout)
        if rel is None or pick_asset(rel, plat) is None:
            return None
        from common import clr
        return [
            clr("  🆕 ", "yellow") + clr(f"Dulus v{rel.version}", "white", "bold")
            + clr(f" is out — the app, built for {plat.label}.", "white"),
            clr("     The pip package is the open-source core; updates land in the app: ", "dim")
            + clr("/app", "cyan", "bold"),
        ]
    except Exception:
        return None


# ── The /app screens ────────────────────────────────────────────────────────

def print_card(rel: Release, asset: Asset | None, plat: Platform) -> None:
    """What the app is, what's out, and the build for this machine (if any)."""
    from common import clr
    print()
    print(clr("  🦅 The Dulus app", "cyan", "bold") + clr("  ·  the maintained Dulus", "dim"))
    for line in (
        "Signed builds for Windows, macOS and Linux — the desktop app, or the",
        "terminal on a server (dulus --cli). No Python to manage, and updates",
        "land there first. This pip package is the open-source core.",
    ):
        print(clr(f"     {line}", "dim"))
    print()
    rows = [("Latest", f"v{rel.version}" + (f"  ·  {rel.date}" if rel.date else "")),
            ("For", plat.label)]
    if asset is not None:
        rows.append(("Build", f"{asset.name}  ·  {_size(asset.size)}"))
    rows.append(("From", f"github.com/{UPDATES_REPO}"))
    for key, value in rows:
        print(clr(f"     {key:<8}", "dim") + clr(value, "white"))
    print()
    if asset is None:
        print(clr(f"  No build for {plat.label} in v{rel.version} yet.", "yellow"))
        summary = builds_summary(rel)
        if summary:
            for line in textwrap.wrap(f"It ships for {summary}.", width=71):
                print(clr(f"     {line}", "dim"))
        print(clr("     This core keeps working meanwhile — ", "dim")
              + clr("/update pip", "cyan") + clr(" keeps it current.", "dim"))
        print(clr(f"     All builds: {rel.html_url or RELEASES_PAGE}", "dim"))
        print()


class _Progress:
    """One line that rewrites itself on a terminal; a line every 10% anywhere else."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout
        isatty = getattr(self.stream, "isatty", None)
        self.tty = bool(isatty and isatty())
        self.started = time.monotonic()
        self.first: int | None = None
        self.drawn = 0.0
        self.decile = -1
        self.line = self.shown = ""

    def __call__(self, done: int, total: int) -> None:
        now = time.monotonic()
        if self.first is None:
            self.first, self.started = done, now
        pct = min(100, done * 100 // total) if total else 0
        speed = (done - self.first) / max(now - self.started, 1e-6)
        self.line = (f"  ⬇  {pct:3d}%  {_size(done)} / {_size(total)}  ·  {_size(speed)}/s"
                     if total else f"  ⬇  {_size(done)}  ·  {_size(speed)}/s")
        if self.tty:
            if now - self.drawn >= 0.2 or (total and done >= total):
                self._draw()
                self.drawn = now
        elif pct // 10 > self.decile:
            self.decile = pct // 10
            print(self.line, file=self.stream, flush=True)

    def _draw(self) -> None:
        self.stream.write("\r\033[2K" + self.line)
        self.stream.flush()
        self.shown = self.line

    def finish(self) -> None:
        """End the line — showing where it stopped, if it stopped between redraws."""
        if self.tty and self.shown:
            if self.line != self.shown:
                self._draw()
            self.stream.write("\n")
            self.stream.flush()


def ask_yes(question: str) -> bool:
    """Yes unless the answer says no. Ctrl+C and a closed stdin are a no, never a yes."""
    print(question, end="", flush=True)
    try:
        answer = input("").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("", "y", "yes", "s", "si", "sí")


def _print_next_steps(plat: Platform, finished: bool) -> None:
    from common import clr
    cli = clr("dulus --cli", "cyan")
    if plat.os == "android":
        steps = [[clr("Open Dulus from your app drawer once Android has installed it.", "white")]]
    elif finished:
        steps = [[clr("Open Dulus from your apps, or run  ", "white") + cli
                  + clr("  in a new terminal", "white"),
                  clr("(on a server too).", "white")]]
    else:
        where = {"windows": "the Start menu", "macos": "Applications"}.get(plat.os, "your apps")
        steps = [[clr(f"When the installer is done, open Dulus from {where} —", "white"),
                  clr("or run  ", "white") + cli + clr("  in a new terminal.", "white")]]
    retire = pip_uninstall_command()
    if retire:
        # The pip `dulus` usually sits earlier on PATH than the app's, so it
        # keeps opening the core until it's gone.
        steps.append([
            clr("Retire this pip copy, so `dulus` opens the app — exit, then run:", "white"),
            clr(f"  {_shell_join(retire)}", "cyan"),
        ])
    print()
    print(clr("  Next", "cyan", "bold"))
    for n, lines in enumerate(steps, 1):
        lead = f"    {n}. " if len(steps) > 1 else "    "
        for i, line in enumerate(lines):
            print((lead if i == 0 else " " * len(lead)) + line)
    print()


def offer(rel: Release, asset: Asset, plat: Platform, *,
          ask: Callable[[str], bool] = ask_yes, assume_yes: bool = False,
          download_only: bool = False, interactive: bool = True) -> str:
    """Confirm, download, verify and install ``asset``, printing as it goes.

    Returns "installed" (done by the time this returns), "launched" (the OS
    installer is open), "downloaded", "declined" or "failed".
    """
    from common import clr, err, info, ok
    if not assume_yes:
        what = "Download it" if download_only else "Download and install it"
        if not ask(clr(f"  {what} now? ({_size(asset.size)}) [Y/n] ", "cyan", "bold")):
            info("No problem — /app gets it any time.")
            return "declined"

    progress = _Progress()
    try:
        dest = download_dir()
        want = expected_sha256(rel, asset)
        path = download(asset, dest, sha256=want, progress=progress)
    except KeyboardInterrupt:
        progress.finish()
        info("Paused — run /app again to pick up where it stopped.")
        return "failed"
    except (AppInstallError, OSError) as exc:
        progress.finish()
        err(f"Couldn't download the Dulus app: {exc}")
        print(clr(f"     Grab it yourself: {asset.url}", "dim"))
        return "failed"
    progress.finish()
    ok(f"Downloaded {path}" + ("  (sha256 verified)" if want else ""))

    if download_only:
        print(clr("     Install it when you're ready: ", "dim")
              + clr(manual_install_hint(path, plat), "cyan"))
        _print_next_steps(plat, finished=False)
        return "downloaded"

    try:
        result = install(path, plat, interactive=interactive)
    except KeyboardInterrupt:
        print()
        info(f"Install cancelled. The download stays at {path}.")
        return "failed"
    except (AppInstallError, OSError) as exc:
        err(f"The install didn't finish: {exc}")
        return "failed"
    (ok if result.finished else info)(result.message)
    _print_next_steps(plat, result.finished)
    return "installed" if result.finished else "launched"
