"""Sandbox auto-extract bootstrap.

The Dulus Sandbox web UI (the desktop-OS-in-a-browser at /sandbox/) is a
~2.4 MB Vite-built React bundle. Shipping its 60-something individual
files inside the Python wheel makes the wheel layout noisy AND, more
importantly, it makes GitHub's Linguist think Dulus is half-TypeScript
when it's a Python project with a bundled web UI.

The fix:
  1. The wheel ships a single compressed artifact at
     `dulus/_bundles/sandbox.tar.gz` (built by `tools/build_sandbox_bundle.py`
     before each release).
  2. The first time anything in Dulus needs the sandbox (webchat hitting
     `/sandbox/...`, the agent inspecting the OS, etc.), this module
     transparently extracts the tarball to `~/.dulus/sandbox/` and
     returns that path.
  3. Re-extraction is automatic when the tarball version changes — we
     write a small marker file next to the extracted contents and
     compare on every call. Users never see a prompt, never get a
     notification; they just see the sandbox.

Why `~/.dulus/sandbox/` instead of the package path:
  - Users on Linux/macOS expect runtime data under `$XDG_DATA_HOME`-ish
    paths, not inside site-packages (which is often read-only or
    shared across venvs).
  - The sandbox writes its own state during use (preferences, last
    session, etc.) — site-packages is the wrong filesystem for that.
  - Lets `pip install --upgrade dulus` swap the BUNDLE in the wheel
    without touching the user's currently-extracted copy until they
    hit the version mismatch check.
"""
from __future__ import annotations

import logging
import shutil
import tarfile
from importlib.resources import files as _pkg_files
from pathlib import Path

logger = logging.getLogger(__name__)

# Where the extracted sandbox lives at runtime.
DULUS_HOME = Path.home() / ".dulus"
SANDBOX_DIR = DULUS_HOME / "sandbox"
VERSION_MARKER = SANDBOX_DIR / ".bundle_version"

# Where the compressed bundle lives inside the installed wheel.
BUNDLE_PACKAGE = "_bundles"
BUNDLE_FILENAME = "sandbox.tar.gz"


def _bundle_path() -> Path | None:
    """Return the on-disk path of the shipped sandbox tarball, or None
    if the wheel was built without the bundle (e.g. a slim/dev install).
    """
    try:
        return Path(str(_pkg_files(BUNDLE_PACKAGE) / BUNDLE_FILENAME))
    except (ModuleNotFoundError, FileNotFoundError):
        return None


def _bundle_signature(p: Path) -> str:
    """Cheap-but-stable identity for a tarball — size + mtime is plenty
    for our 'has the wheel rotated?' check, and a lot faster than a real
    hash for a 1 MB file on every webchat start."""
    try:
        st = p.stat()
        return f"{st.st_size}-{int(st.st_mtime)}"
    except OSError:
        return ""


def _extract(bundle: Path, target: Path) -> None:
    """Atomic-ish extract: wipe + re-create, then write the marker.
    A partially-extracted state is recoverable on the next call because
    we re-check the marker before serving."""
    # Wipe any previous extraction so we never serve a mixed-version
    # filesystem (newer index.html pointing at older chunks, etc.).
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)

    with tarfile.open(bundle, "r:gz") as tar:
        # `filter='data'` strips out unsafe members on Python 3.12+ —
        # belt-and-suspenders since we control the tarball, but cheap.
        try:
            tar.extractall(target, filter="data")  # type: ignore[arg-type]
        except TypeError:
            # Older Python: no filter kwarg.
            tar.extractall(target)

    VERSION_MARKER.write_text(_bundle_signature(bundle), encoding="utf-8")


def ensure_sandbox() -> Path:
    """Make sure ~/.dulus/sandbox/ contains a current sandbox, then
    return that directory. Safe to call on every request — almost all
    invocations are a single stat() and an early return.

    If the bundle is missing from the wheel (slim install, dev checkout
    without running the build script, etc.) we fall back to the in-repo
    `sandbox/dist/` directory when it exists, so developers don't have
    to extract anything during a `pip install -e .` workflow.
    """
    bundle = _bundle_path()

    # Dev fallback: no bundle shipped, but the repo's sandbox/dist exists.
    if bundle is None or not bundle.exists():
        try:
            from importlib.resources import files as _f
            dev = Path(str(_f("sandbox") / "dist"))
            if (dev / "index.html").exists():
                return dev
        except Exception:
            pass
        # Last-resort: relative to this file (editable installs / source runs).
        here = Path(__file__).resolve().parent
        dev = here / "sandbox" / "dist"
        if (dev / "index.html").exists():
            return dev
        raise FileNotFoundError(
            "Dulus sandbox bundle is missing and no sandbox/dist fallback "
            "found. Reinstall Dulus or run tools/build_sandbox_bundle.py."
        )

    DULUS_HOME.mkdir(parents=True, exist_ok=True)
    sig_now = _bundle_signature(bundle)

    # Already extracted and matches the shipped bundle → done.
    if VERSION_MARKER.exists():
        try:
            if VERSION_MARKER.read_text(encoding="utf-8").strip() == sig_now:
                return SANDBOX_DIR
        except OSError:
            pass

    # Either first run, or `pip install --upgrade dulus` rotated the wheel.
    logger.info("Extracting Dulus sandbox to %s", SANDBOX_DIR)
    _extract(bundle, SANDBOX_DIR)
    return SANDBOX_DIR


__all__ = ["ensure_sandbox", "SANDBOX_DIR"]
