"""Lookback prompt-cache behaviour: block re-anchoring, cache-aware gate, and
stale-anchor recovery after compaction.

Front-truncation fights prefix-based prompt caching: every time the window
start jumps forward, the whole conversation prefix is rewritten (a cache miss
at write price). These tests pin the three mitigations:

  1. Block re-anchoring — the anchor survives ~n growth turns (not n//4), so
     the cache-busting rewrite happens ~4x less often.
  2. Cache-aware gate — when the hidden head isn't much bigger than the kept
     window, we send the full archive so the cache keeps hitting instead of
     paying a rewrite for a tiny saving.
  3. Anchor signature — after compaction rewrites the archive, a stale anchor
     index must not be reused verbatim; the window realigns.
"""
from __future__ import annotations

from lookback import (
    apply_lookback_window,
    LOOKBACK_ANCHOR_KEY,
    LOOKBACK_ANCHOR_SIG_KEY,
    _anchor_slack,
    _msg_sig,
)

# Fat filler so the cache-aware gate (default ratio 2.0) lets these small
# synthetic archives truncate — real turns are far bigger than "u0".
_FILLER = "x" * 400


def _mk_msgs(user_turns: int):
    msgs = []
    for i in range(user_turns):
        msgs.append({"role": "user", "content": f"u{i} {_FILLER}"})
        msgs.append({"role": "assistant", "content": f"a{i} {_FILLER}"})
    return msgs


def test_lookback_anchor_hysteresis_keeps_prefix():
    """Anchor sticks across growing turns so the API prefix stays append-only."""
    msgs = _mk_msgs(20)
    cfg = {"lookback": True, "lookback_turns": 5}
    w1, m1 = apply_lookback_window(msgs, cfg)
    anchor = cfg.get(LOOKBACK_ANCHOR_KEY)
    assert m1["truncated"] is True
    assert isinstance(anchor, int) and anchor > 0

    msgs.append({"role": "user", "content": f"u20 {_FILLER}"})
    msgs.append({"role": "assistant", "content": f"a20 {_FILLER}"})
    w2, m2 = apply_lookback_window(msgs, cfg)
    assert cfg.get(LOOKBACK_ANCHOR_KEY) == anchor
    assert m2["start_index"] == m1["start_index"]
    # Window grows by appending; previous window is a prefix of the new one.
    assert w1 == w2[: len(w1)]


def test_lookback_reanchors_only_after_full_block():
    """Block re-anchoring: the prefix survives ~n growth turns, not n//4.

    Gate disabled here to isolate the slack behaviour from the cache-aware gate.
    """
    n = 8
    cfg = {"lookback": True, "lookback_turns": n, "lookback_min_hidden_ratio": 0}
    slack = _anchor_slack(n)
    assert slack == n  # block re-anchoring: slack grew from the old n//4

    msgs = _mk_msgs(n)
    anchor = None
    idx = n
    while anchor is None and idx < 4 * n:
        msgs.append({"role": "user", "content": f"u{idx} {_FILLER}"})
        msgs.append({"role": "assistant", "content": f"a{idx} {_FILLER}"})
        idx += 1
        _, meta = apply_lookback_window(msgs, cfg)
        if meta["truncated"]:
            anchor = cfg[LOOKBACK_ANCHOR_KEY]
    assert anchor is not None

    held = 0
    while idx < 8 * n:
        msgs.append({"role": "user", "content": f"u{idx} {_FILLER}"})
        msgs.append({"role": "assistant", "content": f"a{idx} {_FILLER}"})
        idx += 1
        apply_lookback_window(msgs, cfg)
        if cfg[LOOKBACK_ANCHOR_KEY] != anchor:
            break
        held += 1
    # Old n//4 slack (==2) would have re-anchored after ~2 turns; block mode
    # holds far longer.
    assert held >= n // 2


def test_lookback_gates_when_head_too_small():
    """Tiny archive: truncating would bust the cache for near-zero savings → yield."""
    msgs = _mk_msgs(12)
    cfg = {"lookback": True, "lookback_turns": 10}
    window, meta = apply_lookback_window(msgs, cfg)
    assert meta["truncated"] is False
    assert meta["gated"] is True
    assert window is msgs                      # full archive returned as-is
    assert LOOKBACK_ANCHOR_KEY not in cfg      # anchor cleared for a clean retry


def test_lookback_gate_disabled_by_ratio_zero():
    """ratio=0 forces truncation (providers without a prompt cache)."""
    msgs = _mk_msgs(12)
    cfg = {"lookback": True, "lookback_turns": 10, "lookback_min_hidden_ratio": 0}
    _, meta = apply_lookback_window(msgs, cfg)
    assert meta["truncated"] is True
    assert meta["gated"] is False


def test_lookback_stale_anchor_after_compaction_reanchors():
    """A stored anchor index must realign, not be reused verbatim, post-compaction."""
    msgs = _mk_msgs(20)
    cfg = {"lookback": True, "lookback_turns": 5}
    _, m1 = apply_lookback_window(msgs, cfg)
    assert m1["truncated"] is True
    old_anchor = cfg[LOOKBACK_ANCHOR_KEY]
    assert LOOKBACK_ANCHOR_SIG_KEY in cfg

    # Simulate compaction dropping one user turn from the front. The stored
    # index stays in range but now lands on a *different* turn — the anchor must
    # not be reused verbatim; the window has to realign against the new archive.
    compacted = msgs[2:]
    assert compacted[old_anchor]["content"] != msgs[old_anchor]["content"]

    _, m2 = apply_lookback_window(compacted, cfg)
    assert m2["truncated"] is True
    new_anchor = cfg[LOOKBACK_ANCHOR_KEY]
    # Realigned: two front messages vanished, so the correct anchor shifted back
    # by exactly 2. Blind index reuse would have started the window one turn short.
    assert new_anchor == old_anchor - 2
    assert cfg[LOOKBACK_ANCHOR_SIG_KEY] == _msg_sig(compacted[new_anchor])
    assert compacted[new_anchor]["role"] == "user"
