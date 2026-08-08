# -*- coding: utf-8 -*-
"""
Rotating ASCII boot banner for Dulus.

Picks a random banner from the pack on each launch (without repeating until the
cycle is exhausted), but only from a curated set of good-looking fonts — the
flat / squished / oversized ones in the pack are filtered out. The
"=== FONT: x ===" header is never printed, and the ASCII is painted in the
active theme's accent color when the caller passes one.

    from banner_rotator import show_banner
    show_banner(color=ansi_accent)   # color: optional ANSI prefix (theme accent)
"""

import json
import random
import re
from pathlib import Path

PACK = Path(__file__).parent / "banners_dulus_ai.txt"
# State lives under the user's home, not the package dir, so it still works when
# Dulus is installed into a read-only site-packages.
STATE = Path.home() / ".dulus" / "banner_state.json"
_RESET = "\033[0m"

# Curated set of nice fonts (block / 3D / bold / clean). Add or remove names at
# will — any name not present in the pack is simply ignored. If none match (e.g.
# the pack was regenerated with new names) it falls back to every banner.
GORGEOUS = {
    # 3D / dimensional
    "3-d", "banner3-d", "henry3d", "larry3d", "rozzo", "sub-zero",
    # blocks / bold
    "big", "block2", "bulbhead", "chunky", "colossal", "doom", "epic",
    "starwars", "univers", "standard", "slant", "smslant", "ogre",
    "roman", "crawford",
    # shadow / elegant / serif
    "shadow", "georgia11", "stampatello", "serifcap",
    "nancyj", "nancyj-fancy", "nancyj-underlined", "varsity", "whimsy",
    # stylish / clean
    "graffiti", "speed", "swan", "rounded", "puffy", "thick", "tubular",
    "stellar", "twisted", "cricket", "letters", "smpoison",
}

_HEADER_RE = re.compile(r"=== FONT: (.+?) ===")


def load_banners():
    """Pack art blocks with the FONT header stripped, keeping only the curated
    fonts. Falls back to every banner if the curated set matches nothing."""
    try:
        data = PACK.read_text(encoding="utf-8")
    except Exception:
        return []
    blocks = [b for b in re.split(r"\n\n+", data.strip()) if b.strip()]
    curated, every = [], []
    for b in blocks:
        lines = b.split("\n")
        m = _HEADER_RE.match(lines[0]) if lines else None
        name = m.group(1).strip().lower() if m else ""
        art = "\n".join(lines[1:] if m else lines).rstrip("\n")
        if not art.strip():
            continue
        every.append(art)
        if name in GORGEOUS:
            curated.append(art)
    return curated or every


def pick_banner():
    banners = load_banners()
    if not banners:
        return ""
    try:
        used = set(json.loads(STATE.read_text(encoding="utf-8")))
    except Exception:
        used = set()

    # The filtered pack changed size: drop stale indices out of range.
    used = {u for u in used if 0 <= u < len(banners)}

    remaining = [i for i in range(len(banners)) if i not in used]
    if not remaining:  # full cycle -> restart
        used.clear()
        remaining = list(range(len(banners)))

    idx = random.choice(remaining)
    used.add(idx)
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(sorted(used)), encoding="utf-8")
    except Exception:
        pass
    return banners[idx]


def show_banner(color=None):
    """Print a random curated banner. `color` is an optional ANSI prefix (the
    active theme's accent) applied to every non-blank line."""
    art = pick_banner()
    if not art:
        return
    if color:
        art = "\n".join(
            (color + ln + _RESET) if ln.strip() else ln
            for ln in art.split("\n")
        )
    print(art)


if __name__ == "__main__":
    show_banner()
