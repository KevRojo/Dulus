"""Central registry of per-model-family custom parameters.

Declare a model family ONCE here — its reasoning-effort levels, toolbar hint,
and /menu entries — and every consumer reads from it:

  * cmd_effort               → valid levels, slider position, "applies to" line
  * the REPL toolbar         → whether to show ⚡effort and which levels are "hot"
  * _CMD_META (autocomplete) → the union of all effort levels for /effort
  * the quick menu (/menu)   → model options, auto-injected

Adding a new model with custom params is now ONE entry below instead of edits
across five files. Pure stdlib, no Dulus imports, so any module can read it
without circular-import risk.
"""
from __future__ import annotations

# Canonical order for slider position + autocomplete listing.
_EFFORT_ORDER = ["minimal", "low", "medium", "high", "max", "ultra"]
_SLIDER_IDX = {"minimal": 0, "low": 1, "medium": 2, "high": 3, "max": 4, "ultra": 4}


def _norm_wire(model) -> str:
    """Bare wire name: final path segment, provider prefix stripped, lowercased.

    Handles ``chatgpt-oauth/gpt-5.6-sol``, ``chatgpt-oauth/chatgpt/gpt-5.6-sol``
    (legacy double prefix), ``kimi-oauth/k3-256k``, plain ``k3``, etc.
    """
    w = str(model or "").strip().lower()
    if "/" in w:
        w = w.rsplit("/", 1)[-1]
    for prefix in ("chatgpt-", "codex-"):
        if w.startswith(prefix):
            w = w[len(prefix):]
            break
    return w


# ── The registry: one entry per model family ────────────────────────────────
MODEL_FAMILIES = [
    {
        "id": "gpt-5.6",
        "match": lambda w: w == "gpt-5.6" or w.startswith("gpt-5.6-"),
        "effort": {
            "levels": ["minimal", "low", "medium", "high", "max", "ultra"],
            "default": "high",
            "hot": ["max", "ultra"],
            "applies": "GPT-5.6 Sol/Terra/Luna via ChatGPT OAuth.",
        },
        "menu_models": [
            ("☀️", "GPT-5.6 Sol  (oauth)", "chatgpt-oauth/gpt-5.6-sol"),
            ("⭐", "GPT-5.6 Sol Pro  (oauth)", "chatgpt-oauth/gpt-5.6-sol-pro"),
            ("🌍", "GPT-5.6 Terra  (oauth)", "chatgpt-oauth/gpt-5.6-terra"),
            ("🌙", "GPT-5.6 Luna  (oauth)", "chatgpt-oauth/gpt-5.6-luna"),
        ],
    },
    {
        "id": "kimi-k3",
        "match": lambda w: w.startswith("k3"),
        "effort": {
            "levels": ["low", "high", "max"],
            "default": "high",
            "hot": ["max"],
            "applies": "Kimi k3 / k3-256k. kimi-for-coding uses /thinking (on/off).",
        },
        "menu_models": [
            ("🌙", "Kimi K3  (oauth, 1M)", "kimi-oauth/k3"),
            ("🌙", "Kimi K3-256k (oauth)", "kimi-oauth/k3-256k"),
        ],
    },
]

# Fallback used when a model has no registered effort param.
_DEFAULT_EFFORT = {
    "levels": ["low", "high", "max"],
    "default": "high",
    "hot": ["max"],
    "applies": "Kimi k3 / k3-256k. kimi-for-coding uses /thinking (on/off).",
}


def family_for(model):
    """The MODEL_FAMILIES entry matching *model*, or None."""
    w = _norm_wire(model)
    for fam in MODEL_FAMILIES:
        try:
            if fam.get("match") and fam["match"](w):
                return fam
        except Exception:
            continue
    return None


def effort_config(model):
    """The effort dict for *model*'s family, or None if it has no effort param."""
    fam = family_for(model)
    return fam.get("effort") if fam else None


def has_effort(model) -> bool:
    """Whether *model* exposes a reasoning-effort control."""
    return effort_config(model) is not None


def effort_levels(model):
    """Valid effort levels for *model* (falls back to low/high/max)."""
    cfg = effort_config(model) or _DEFAULT_EFFORT
    return list(cfg["levels"])


def effort_hot(model):
    """Levels rendered 'hot' (highlighted) in the toolbar for *model*."""
    cfg = effort_config(model) or _DEFAULT_EFFORT
    return list(cfg.get("hot", ["max"]))


def effort_applies(model) -> str:
    """The 'Applies to ...' descriptor for *model*'s effort control."""
    cfg = effort_config(model) or _DEFAULT_EFFORT
    return cfg.get("applies", "")


def effort_slider_idx(level) -> int:
    """0-4 slider position for an effort level (max and ultra both peg at 4)."""
    return _SLIDER_IDX.get(str(level or "").strip().lower(), 3)


def all_effort_levels():
    """Union of every family's effort levels, ordered minimal→ultra (autocomplete)."""
    seen = set()
    for fam in MODEL_FAMILIES:
        for lv in fam.get("effort", {}).get("levels", []):
            seen.add(lv)
    return [lv for lv in _EFFORT_ORDER if lv in seen] or list(_DEFAULT_EFFORT["levels"])


def menu_model_options():
    """[(label, '/model <id>')] for every family's models — injected into /menu."""
    out = []
    for fam in MODEL_FAMILIES:
        for emoji, label, model_id in fam.get("menu_models", []):
            out.append((f"{emoji}  {label}", f"/model {model_id}"))
    return out
