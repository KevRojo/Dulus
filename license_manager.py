"""Dulus License Manager — Offline-first key validation + feature gating.

Tiers:
  FREE      No key required. Limited tool calls, local providers only.
  PRO       $15/mo. Full features, BYOK, priority support.
  ENTERPRISE $50/mo. Team features + admin dashboard + SSO (future).

Key format (offline):
  DULUS-<base64(json_payload + ":" + hmac_signature)>

The secret lives in ~/.dulus/.license_secret (never commit this file).
If the secret file is missing we fall back to a hardcoded dev-key so
Kev can develop without friction, but distribution builds MUST bundle
a real secret via CI env var or PyInstaller --add-data.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ── Secret resolution ───────────────────────────────────────────────────────
# 1. CI / build-time env var   (safest for releases)
# 2. ~/.dulus/.license_secret (Kev's local dev key)
# 3. Fallback dev secret       (NEVER use in production builds)
_LICENSE_SECRET = os.environ.get("DULUS_LICENSE_SECRET", "")
if not _LICENSE_SECRET:
    _secret_path = Path.home() / ".dulus" / ".license_secret"
    if _secret_path.exists():
        _LICENSE_SECRET = _secret_path.read_text().strip()
    else:
        _LICENSE_SECRET = "dulus-dev-secret-do-not-distribute"
        import warnings
        warnings.warn(
            "DULUS_LICENSE_SECRET not set — using hardcoded DEV secret. "
            "Generated keys will be trivially forgeable in production!",
            RuntimeWarning,
            stacklevel=2,
        )


class LicenseTier:
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class LicenseManager:
    """Parse and validate a Dulus license key."""

    def __init__(self, key: Optional[str] = None):
        self.raw_key = key or ""
        self.tier = LicenseTier.FREE
        self.expiry: float = 0.0
        self.features: list[str] = []
        self.valid = False
        self.error: Optional[str] = None

        if self.raw_key:
            self._validate()

    # ── validation core ─────────────────────────────────────────────────────

    def _validate(self) -> None:
        if not self.raw_key.startswith("DULUS-"):
            self.error = "Invalid key prefix"
            return

        try:
            b64 = self.raw_key.split("-", 1)[1]
            payload_sig = base64.urlsafe_b64decode(b64 + "==")
            payload_json, sig_hex = payload_sig.rsplit(b":", 1)
            data = json.loads(payload_json)
        except Exception as exc:
            self.error = f"Malformed key: {exc}"
            return

        # Verify HMAC-SHA256 signature
        expected_sig = hmac.new(
            _LICENSE_SECRET.encode(),
            payload_json,
            hashlib.sha256,
        ).hexdigest()[:24]

        if not hmac.compare_digest(sig_hex.decode(), expected_sig):
            self.error = "Invalid signature (tampered or wrong secret)"
            return

        self.tier = data.get("tier", LicenseTier.FREE)
        self.expiry = data.get("exp", 0)
        self.features = data.get("features", [])

        if time.time() > self.expiry:
            self.error = "License expired"
            return

        self.valid = True

    # ── feature gates ───────────────────────────────────────────────────────

    def can_use(self, feature: str) -> bool:
        """Check if a feature is allowed by current tier."""
        if self.tier == LicenseTier.ENTERPRISE:
            return True
        if self.tier == LicenseTier.PRO:
            return feature not in {"sso", "audit_logs", "admin_dashboard"}
        # FREE
        free_features = {"chat", "tools_basic", "local_providers"}
        return feature in free_features

    def max_tool_calls(self) -> int:
        if self.tier == LicenseTier.ENTERPRISE:
            return 999_999
        if self.tier == LicenseTier.PRO:
            return 10_000
        return 25  # FREE daily limit

    def max_providers(self) -> int:
        if self.tier in (LicenseTier.PRO, LicenseTier.ENTERPRISE):
            return 99
        return 2  # FREE: e.g. ollama + 1 cloud

    def max_subagents(self) -> int:
        if self.tier == LicenseTier.ENTERPRISE:
            return 50
        if self.tier == LicenseTier.PRO:
            return 10
        return 0  # FREE: no subagents

    def max_plugins(self) -> int:
        if self.tier == LicenseTier.ENTERPRISE:
            return 999
        if self.tier == LicenseTier.PRO:
            return 50
        return 3  # FREE

    def allow_cloudsave(self) -> bool:
        return self.tier in (LicenseTier.PRO, LicenseTier.ENTERPRISE)

    def allow_voice(self) -> bool:
        return self.tier in (LicenseTier.PRO, LicenseTier.ENTERPRISE)

    def allow_telegram(self) -> bool:
        return self.tier in (LicenseTier.PRO, LicenseTier.ENTERPRISE)

    def allow_mcp(self) -> bool:
        return self.tier in (LicenseTier.PRO, LicenseTier.ENTERPRISE)

    # ── UI helpers ──────────────────────────────────────────────────────────

    def status_banner(self) -> str:
        if self.error:
            return f"[LICENSE EXPIRED / INVALID] {self.error} — running in FREE mode"
        if self.tier == LicenseTier.FREE:
            return "[FREE] Limited features. More: https://kevrojo.github.io/Dulus/"
        return f"[{self.tier.upper()}] Valid until {time.strftime('%Y-%m-%d', time.localtime(self.expiry))}"


# ── CLI helper for Kev ─────────────────────────────────────────────────────

def _generate_key(tier: str, days: int, secret: str) -> str:
    """Generate a signed license key (Kev-only tool)."""
    payload = json.dumps({
        "tier": tier,
        "exp": int(time.time() + days * 86400),
        "features": [],
        "iat": int(time.time()),
    }, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()[:24]
    token = base64.urlsafe_b64encode(payload + b":" + sig.encode()).decode().rstrip("=")
    return f"DULUS-{token}"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Dulus License Key Generator (Kev only)")
    ap.add_argument("tier", choices=["free", "pro", "enterprise"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--secret", default=_LICENSE_SECRET)
    args = ap.parse_args()
    print(_generate_key(args.tier, args.days, args.secret))
