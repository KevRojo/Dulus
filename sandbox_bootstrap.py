"""Resolve the path to the Dulus Sandbox web UI.

The sandbox (the desktop-OS-in-a-browser at `/sandbox/`) ships inside the
wheel as plain files at `sandbox/dist/` — same layout as Dulus 0.2.81.
No tarball, no extract-on-first-run; pip installs it and webchat serves
it directly from site-packages.

GitHub Linguist's "this repo is 49% TypeScript" complaint is handled by
`.gitattributes` (`sandbox/** linguist-vendored=true`), not by hiding
the files from the wheel.
"""
from __future__ import annotations

from pathlib import Path


def ensure_sandbox() -> Path:
    """Return the directory the webchat server should serve `/sandbox/` from.

    Resolution order:
      1. Installed wheel: `<site-packages>/sandbox/dist/`
      2. Editable / source checkout: `<repo>/sandbox/dist/`
    """
    # 1. Wheel layout — sandbox/dist lives next to this module.
    here = Path(__file__).resolve().parent
    candidate = here / "sandbox" / "dist"
    if (candidate / "index.html").exists():
        return candidate

    # 2. importlib.resources fallback (zipped/egg installs).
    try:
        from importlib.resources import files as _f
        pkg_dist = Path(str(_f("sandbox") / "dist"))
        if (pkg_dist / "index.html").exists():
            return pkg_dist
    except Exception:
        pass

    raise FileNotFoundError(
        "Dulus sandbox is missing — sandbox/dist/index.html not found. "
        "Reinstall Dulus (`pip install --upgrade dulus`) or, in a source "
        "checkout, run `npm run build` inside the sandbox/ folder."
    )


# Back-compat: some code imports SANDBOX_DIR. Resolve lazily so importing
# this module on a slim install (no sandbox shipped) doesn't crash.
def __getattr__(name: str):
    if name == "SANDBOX_DIR":
        return ensure_sandbox()
    raise AttributeError(name)


__all__ = ["ensure_sandbox"]
