"""governance.py — Dulus governance layer: budgets, capabilities, hooks.

A lightweight, opt-in per-session governance layer for safe, auditable,
cost-capped agent runs. Three independent pieces you can use together or
on their own:

    Ledger        Per-session resource budgets across dimensions
                  (tokens, cost, tool_calls, ...). Atomic charge that
                  reports over-limit and first-breach so a supervisor can act.

    Capabilities  Least-privilege grants — which tools / fs paths / hosts an
                  agent may touch. Sub-agents derive a child capability set
                  that is always a SUBSET of the parent (children ⊆ parent).

    Hooks         Lifecycle callbacks (pre_tool, post_tool, on_error, on_breach)
                  that observe, audit, notify — or VETO an operation before it
                  runs. The governance "when".

Together they form: hooks (when) + capabilities (what's allowed) +
ledger (how much it may spend) = an enterprise-grade governance/audit/
cost-control layer.

Design influences (ideas only — reimplemented from scratch for Dulus, GPL-3):
  - multi-dimension per-agent ledger with used/granted/warn_at
    (concept seen in SafeRL-Lab/cheetahclaws cc_kernel, Apache-2.0)
  - lifecycle hooks that gate/audit/notify around tool calls
    (concept seen in MoonshotAI/kimi-code, MIT)
No third-party code is copied; this is an original Dulus implementation.
"""
from __future__ import annotations

import fnmatch
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional


# ── Ledger ──────────────────────────────────────────────────────────────────

# Standard budget dimensions. Custom dims are allowed; these are just the
# ones Dulus charges automatically when wired into the agent loop.
STD_DIMS = ("tokens", "cost_micro", "tool_calls", "wall_s")


@dataclass(frozen=True)
class ChargeResult:
    dim:          str
    amount:       int
    used:         int
    granted:      int          # -1 == unlimited
    over_limit:   bool
    warned:       bool         # crossed the warn_at threshold this charge
    first_breach: bool         # first time this dim went over its hard limit

    @property
    def remaining(self) -> int:
        return -1 if self.granted < 0 else max(0, self.granted - self.used)


class Ledger:
    """Per-session resource budget. Thread-safe; atomic charges.

    limits: {"tokens": 200_000, "cost_micro": 5_000_000, "tool_calls": 300}
            A dimension absent from `limits` (or set to a negative value) is
            treated as UNLIMITED. warn_at is the fraction of the limit at which
            a one-time warning fires (0.8 == 80%).
    """

    def __init__(self, limits: Optional[dict] = None, warn_at: float = 0.8):
        if not (0.0 < warn_at <= 1.0):
            raise ValueError("warn_at must be in (0, 1]")
        self._limits: dict = dict(limits or {})
        self._used: dict = defaultdict(int)
        self._warn_at = warn_at
        self._warned: set = set()
        self._breached: set = set()
        self._lock = threading.Lock()

    def granted(self, dim: str) -> int:
        v = self._limits.get(dim, -1)
        return -1 if v is None or v < 0 else int(v)

    def used(self, dim: str) -> int:
        return self._used.get(dim, 0)

    def remaining(self, dim: str) -> int:
        g = self.granted(dim)
        return -1 if g < 0 else max(0, g - self.used(dim))

    def would_exceed(self, dim: str, amount: int) -> bool:
        g = self.granted(dim)
        return g >= 0 and (self.used(dim) + max(0, amount)) > g

    def charge(self, dim: str, amount: int) -> ChargeResult:
        """Record usage atomically. Always succeeds (never blocks); the caller
        inspects `over_limit` / `first_breach` and decides what to do."""
        amount = max(0, int(amount))
        with self._lock:
            self._used[dim] += amount
            used = self._used[dim]
            g = self.granted(dim)
            over = g >= 0 and used > g
            first_breach = False
            if over and dim not in self._breached:
                self._breached.add(dim)
                first_breach = True
            warned = False
            if g >= 0 and dim not in self._warned and used >= g * self._warn_at:
                self._warned.add(dim)
                warned = True
            return ChargeResult(dim, amount, used, g, over, warned, first_breach)

    def set_limit(self, dim: str, amount: Optional[int]) -> None:
        """Change a limit live (preserves already-charged usage). A negative /
        None amount removes the limit (unlimited). Re-arms warn/breach flags."""
        with self._lock:
            if amount is None or int(amount) < 0:
                self._limits.pop(dim, None)
            else:
                self._limits[dim] = int(amount)
            self._warned.discard(dim)
            self._breached.discard(dim)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                d: {"used": self.used(d), "granted": self.granted(d),
                    "remaining": self.remaining(d)}
                for d in set(self._limits) | set(self._used)
            }


# ── Capabilities ─────────────────────────────────────────────────────────────

@dataclass
class Capabilities:
    """Least-privilege grants for an agent. Empty/None lists with allow_all=True
    means "everything"; otherwise grants are explicit allow-lists with optional
    deny-lists that win. Patterns use fnmatch globbing.

    A sub-agent gets `parent.derive_child(...)` which can only NARROW the parent
    (children ⊆ parent) — it can never widen what the parent was granted.
    """
    tools:     Optional[list] = None   # allowed tool-name globs; None => all
    deny_tools: list = field(default_factory=list)
    fs_paths:  Optional[list] = None   # allowed path globs; None => all
    net_hosts: Optional[list] = None   # allowed host globs; None => all
    allow_all: bool = True

    def allows_tool(self, name: str) -> bool:
        if any(fnmatch.fnmatch(name, p) for p in self.deny_tools):
            return False
        if self.tools is None:
            return self.allow_all
        return any(fnmatch.fnmatch(name, p) for p in self.tools)

    def allows_path(self, path: str) -> bool:
        if self.fs_paths is None:
            return self.allow_all
        norm = os.path.normpath(os.path.expanduser(path or ""))
        return any(fnmatch.fnmatch(norm, os.path.normpath(os.path.expanduser(p)))
                   for p in self.fs_paths)

    def allows_net(self, host: str) -> bool:
        if self.net_hosts is None:
            return self.allow_all
        return any(fnmatch.fnmatch((host or "").lower(), p.lower())
                   for p in self.net_hosts)

    def derive_child(self, tools=None, fs_paths=None, net_hosts=None) -> "Capabilities":
        """Return a child capability set that is a SUBSET of self. The child may
        only request things the parent already allows; anything broader is
        silently clamped to the parent's grant."""
        def _narrow(child, parent, allow_check):
            if child is None:
                return parent
            kept = [c for c in child if (parent is None and self.allow_all) or allow_check(c)]
            return kept

        return Capabilities(
            tools=_narrow(tools, self.tools, lambda t: self.allows_tool(t)),
            deny_tools=list(self.deny_tools),
            fs_paths=_narrow(fs_paths, self.fs_paths, lambda p: self.allows_path(p)),
            net_hosts=_narrow(net_hosts, self.net_hosts, lambda h: self.allows_net(h)),
            allow_all=self.allow_all and (tools is None and fs_paths is None and net_hosts is None),
        )


# ── Hooks ────────────────────────────────────────────────────────────────────

# A pre_tool hook may return False (or raise HookVeto) to BLOCK the operation.
# All other hooks are observational (return value ignored).
EVENTS = ("pre_tool", "post_tool", "on_error", "on_breach")


class HookVeto(Exception):
    """Raised/returned by a pre_tool hook to block an operation."""
    def __init__(self, reason: str = "blocked by hook"):
        super().__init__(reason)
        self.reason = reason


class Hooks:
    def __init__(self):
        self._cbs: dict = defaultdict(list)

    def register(self, event: str, fn: Callable) -> None:
        if event not in EVENTS:
            raise ValueError(f"unknown hook event {event!r}; valid: {EVENTS}")
        self._cbs[event].append(fn)

    def fire(self, event: str, **ctx) -> tuple[bool, str]:
        """Fire all callbacks for `event`. For pre_tool, returns (allowed, reason):
        any callback returning False / raising HookVeto blocks the op. Other
        events always return (True, ""). Callback exceptions never crash the
        agent — they're swallowed (governance must never take the loop down)."""
        for fn in self._cbs.get(event, []):
            try:
                res = fn(**ctx)
            except HookVeto as v:
                return False, v.reason
            except Exception:
                continue
            if event == "pre_tool" and res is False:
                return False, "blocked by hook"
        return True, ""


# ── Session container ────────────────────────────────────────────────────────

@dataclass
class Governance:
    """Bundles the three pieces for one agent session. Any may be None."""
    ledger:       Optional[Ledger] = None
    capabilities: Optional[Capabilities] = None
    hooks:        Optional[Hooks] = None

    def child(self, **caps) -> "Governance":
        """Governance for a spawned sub-agent: SHARES the ledger (one budget for
        the whole tree), NARROWS capabilities (child ⊆ parent), shares hooks."""
        child_caps = self.capabilities.derive_child(**caps) if self.capabilities else None
        return Governance(ledger=self.ledger, capabilities=child_caps, hooks=self.hooks)


def from_config(config: dict) -> Optional[Governance]:
    """Build a Governance from a config dict, or None if not enabled.

    Expected (all optional) under config["governance"]:
        {
          "limits":  {"tokens": 200000, "cost_micro": 5000000, "tool_calls": 300},
          "warn_at": 0.8,
          "tools":   ["Read", "Grep", "Glob", "Bash", "Web*"],   # allow-list
          "deny_tools": ["Write", "Edit"],
          "fs_paths": ["~/project/*"],
          "net_hosts": ["*.github.com", "api.openai.com"]
        }
    """
    g = (config or {}).get("governance")
    if not g:
        return None
    ledger = Ledger(limits=g.get("limits"), warn_at=g.get("warn_at", 0.8)) if g.get("limits") else None
    caps = None
    if any(k in g for k in ("tools", "deny_tools", "fs_paths", "net_hosts")):
        caps = Capabilities(
            tools=g.get("tools"),
            deny_tools=g.get("deny_tools", []),
            fs_paths=g.get("fs_paths"),
            net_hosts=g.get("net_hosts"),
            allow_all=("tools" not in g and "fs_paths" not in g and "net_hosts" not in g),
        )
    hooks = Hooks() if g.get("hooks", True) else None
    if not (ledger or caps or hooks):
        return None
    return Governance(ledger=ledger, capabilities=caps, hooks=hooks)
