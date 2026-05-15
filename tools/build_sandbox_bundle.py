#!/usr/bin/env python3
"""Build the sandbox tarball that ships inside the Dulus wheel.

Usage:
    python tools/build_sandbox_bundle.py            # uses existing sandbox/dist
    python tools/build_sandbox_bundle.py --rebuild  # also runs `npm run build` first

Output:
    _bundles/sandbox.tar.gz   (committed to git; consumed by sandbox_bootstrap.py)

Why a script and not a setuptools hook:
    The Vite build needs Node.js and a populated node_modules. Wedging that
    into the Python build chain would force every consumer of `pip install
    dulus` to also have Node.js, which is exactly the noise we're trying to
    avoid by pre-compressing. Maintainers run this once before publishing;
    everyone else just gets the tarball for free.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SANDBOX = REPO / "sandbox"
DIST = SANDBOX / "dist"
OUT_DIR = REPO / "_bundles"
OUT_FILE = OUT_DIR / "sandbox.tar.gz"


def _ensure_dist(rebuild: bool) -> None:
    """Make sure sandbox/dist/index.html exists, optionally rebuilding."""
    if rebuild or not (DIST / "index.html").exists():
        if not (SANDBOX / "package.json").exists():
            sys.exit(f"sandbox/package.json missing — nothing to build at {SANDBOX}")
        print(f"[1/3] Building sandbox bundle (vite)…")
        # On Windows `npm` is npm.cmd; subprocess needs shell=True there.
        npm = "npm.cmd" if os.name == "nt" else "npm"
        if not (SANDBOX / "node_modules").exists():
            print("      Installing npm deps first (one-time, ~1 min)…")
            subprocess.run([npm, "install"], cwd=SANDBOX, check=True)
        subprocess.run([npm, "run", "build"], cwd=SANDBOX, check=True)
    else:
        print(f"[1/3] sandbox/dist already exists — skipping vite build")


def _build_tarball() -> None:
    """Pack sandbox/dist/* into _bundles/sandbox.tar.gz."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[2/3] Compressing {DIST.relative_to(REPO)} -> {OUT_FILE.relative_to(REPO)}…")
    # Reproducibility: stable mtime/uid/gid so the tarball hash doesn't
    # change on byte-for-byte identical input. Not critical for shipping,
    # but nice for diff'ing wheels.
    def reset(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
        tarinfo.uid = 0
        tarinfo.gid = 0
        tarinfo.uname = ""
        tarinfo.gname = ""
        tarinfo.mtime = 1700000000  # arbitrary fixed epoch
        return tarinfo

    with tarfile.open(OUT_FILE, "w:gz") as tar:
        for entry in sorted(DIST.rglob("*")):
            if entry.is_file():
                arc = entry.relative_to(DIST).as_posix()
                tar.add(entry, arcname=arc, filter=reset)


def _summary() -> None:
    """Print size + file count for quick sanity checking."""
    src_bytes = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    src_count = sum(1 for p in DIST.rglob("*") if p.is_file())
    out_bytes = OUT_FILE.stat().st_size
    print(
        f"[3/3] OK — {src_count} files, "
        f"{src_bytes/1024:.0f} KB source, "
        f"{out_bytes/1024:.0f} KB packed "
        f"({(out_bytes/src_bytes)*100:.0f}% of original)."
    )
    print(f"\nReady to ship: {OUT_FILE}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Also run `npm run build` before packing (force fresh dist).",
    )
    args = parser.parse_args()

    _ensure_dist(args.rebuild)
    if not (DIST / "index.html").exists():
        sys.exit(f"sandbox/dist/index.html still missing — vite build must have failed.")
    _build_tarball()
    _summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
