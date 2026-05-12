"""License server validation helpers.

Mirrors the signing logic in license_manager.py for cross-validation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json


def parse_key(key: str) -> dict:
    """Parse a DULUS license key into its components.

    Returns a dict with keys:
        - payload_b64: base64-encoded payload bytes
        - sig: the hex signature string
        - payload: the decoded payload dict
    On error returns {"error": "..."}.
    """
    if not key.startswith("DULUS-"):
        return {"error": "Invalid key format"}

    token = key[6:]  # strip DULUS-
    # Add padding if needed
    padding = 4 - len(token) % 4
    if padding != 4:
        token += "=" * padding

    try:
        raw = base64.urlsafe_b64decode(token.encode())
    except Exception as e:
        return {"error": f"Base64 decode failed: {e}"}

    if b":" not in raw:
        return {"error": "Missing signature separator"}

    payload_bytes, sig_bytes = raw.rsplit(b":", 1)
    try:
        payload = json.loads(payload_bytes)
    except Exception as e:
        return {"error": f"Invalid JSON payload: {e}"}

    payload_b64 = base64.b64encode(payload_bytes).decode()
    sig = sig_bytes.decode()

    return {
        "payload_b64": payload_b64,
        "sig": sig,
        "payload": payload,
    }


def _verify_payload(payload_b64: str, sig: str, secret: str) -> bool:
    """Verify that *sig* matches HMAC-SHA256 of the payload using *secret*."""
    try:
        payload_bytes = base64.b64decode(payload_b64.encode())
    except Exception:
        return False

    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(expected, sig)
