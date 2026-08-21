"""Sign in to a Dulus account from the CLI.

Dulus issues its own credentials rather than delegating identity to a third
party, so this talks to the Dulus API directly: an OAuth 2.0
Authorization-Code + PKCE flow for interactive login, and long-lived
``dulus_sk_*`` API keys for servers and CI.

The flow is the same one already used for the other providers -- open the
system browser, capture the code on a loopback redirect, exchange it for
tokens -- with two differences that matter:

  * The loopback port is chosen by the OS instead of being hard-coded, so two
    logins can run at once and a busy port never blocks sign-in.
  * The client is public, so it holds no secret. PKCE is what proves the code
    is being redeemed by the same program that requested it.

Tokens land in ``~/.dulus/account.json`` with owner-only permissions.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import secrets
import time
from typing import Any, Callable


DULUS_API_BASE = os.environ.get("DULUS_API_BASE", "https://control.dulus.ai").rstrip("/")
DULUS_OAUTH_CLIENT_ID = "dulus-cli"
DULUS_OAUTH_SCOPE = "inference balance:read"
_REDIRECT_PATH = "/callback"
_LOGIN_TIMEOUT_SECONDS = 300
# Locked Auth0 tenant constants — same tenant the private build uses. A public
# client must not be able to repoint auth at its own tenant to dodge the plan
# gate. The device flow is what identifies the human; the Dulus OAuth code
# flow below only converts that identity into CLI tokens.
_AUTH0_DOMAIN = "dulus.us.auth0.com"
_AUTH0_CLIENT_ID = "gm7NFQrAhhBKG0VsAEdVkhUU7oayQC1g"
_AUTH0_SCOPES = "openid profile email"
# Refresh slightly early so a request never leaves with a token that expires
# while it is in flight.
_EXPIRY_BUFFER_SECONDS = 60


def _store_path() -> pathlib.Path:
    home = pathlib.Path(os.environ.get("DULUS_HOME") or (pathlib.Path.home() / ".dulus"))
    home.mkdir(parents=True, exist_ok=True)
    return home / "account.json"


def load_store() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_store(data: dict) -> None:
    path = _store_path()
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        # These are live credentials; on a shared machine the default mode
        # would leave them readable by every other account.
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        pass


def clear_store() -> None:
    try:
        _store_path().unlink(missing_ok=True)
    except Exception:
        pass


def _pkce_pair() -> tuple[str, str]:
    """Return ``(verifier, challenge)`` for PKCE S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _token_expired(store: dict) -> bool:
    expires_at = store.get("expires_at")
    if not expires_at:
        return False  # unknown lifetime: let a 401 drive the refresh instead
    try:
        return time.time() >= float(expires_at)
    except Exception:
        return False


def _persist_tokens(payload: dict) -> dict:
    store = {
        "access_token": payload.get("access_token", ""),
        "refresh_token": payload.get("refresh_token", ""),
        "token_type": payload.get("token_type", "Bearer"),
        "scope": payload.get("scope", ""),
        "obtained_at": time.time(),
        "expires_at": time.time() + int(payload.get("expires_in", 3600)) - _EXPIRY_BUFFER_SECONDS,
    }
    save_store(store)
    return store


def refresh(refresh_token: str) -> dict | None:
    """Exchange a refresh token for a fresh access token.

    The server rotates refresh tokens, so the response carries a new one that
    replaces the old. A failure here means the token was revoked or replayed
    and the user has to sign in again.
    """
    import requests

    try:
        response = requests.post(
            f"{DULUS_API_BASE}/v1/oauth/token",
            json={
                "grant_type": "refresh_token",
                "client_id": DULUS_OAUTH_CLIENT_ID,
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
        if response.status_code != 200:
            return None
        return _persist_tokens(response.json())
    except Exception:
        return None


def login(notify: Callable[[str], Any] = print) -> str | None:
    """Sign in via the device flow. Returns an access token, or None.

    The server has no browser consent page for the CLI: /v1/oauth/authorize
    is a POST-only API that expects an account lease. So the chain is:

      1. Auth0 device-code login (works headless; the approving browser can
         be on any machine — nothing has to reach the CLI's localhost).
      2. GET /api/entitlements with the Auth0 token → account lease.
      3. POST /v1/oauth/authorize with the lease → authorization code.
      4. POST /v1/oauth/token (code + PKCE verifier) → CLI tokens.
    """
    import requests
    import webbrowser

    # ── 1. Auth0 device code ────────────────────────────────────────────
    try:
        start = requests.post(
            f"https://{_AUTH0_DOMAIN}/oauth/device/code",
            data={"client_id": _AUTH0_CLIENT_ID, "scope": _AUTH0_SCOPES},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        ).json()
    except Exception as exc:
        notify(f"[dulus] Could not reach the login server: {exc}")
        return None

    device_code = start.get("device_code")
    user_code = start.get("user_code")
    verify_full = start.get("verification_uri_complete") or start.get("verification_uri")
    if not device_code or not user_code or not verify_full:
        notify("[dulus] Login server returned no device code.")
        return None

    notify(f"[dulus] Go to {start.get('verification_uri') or verify_full} and enter: {user_code}")
    notify(f"[dulus] If the browser didn't open, use:\n{verify_full}")
    try:
        webbrowser.open(verify_full)
    except Exception:
        pass

    interval = max(1, int(start.get("interval") or 5))
    deadline = time.time() + min(int(start.get("expires_in") or 300), _LOGIN_TIMEOUT_SECONDS)
    auth0_token = None
    while time.time() < deadline:
        time.sleep(interval)
        try:
            poll = requests.post(
                f"https://{_AUTH0_DOMAIN}/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": _AUTH0_CLIENT_ID,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        except Exception:
            continue
        if poll.status_code == 200:
            auth0_token = poll.json().get("access_token")
            break
        err = (poll.json() or {}).get("error", "")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        if err == "access_denied":
            notify("[dulus] Sign-in denied.")
            return None
        if err in ("expired_token", "expired"):
            notify("[dulus] The login code expired. Run /login dulus again.")
            return None
        notify(f"[dulus] Login failed: {err or poll.status_code}")
        return None

    if not auth0_token:
        notify("[dulus] Sign-in timed out before it was approved.")
        return None

    # ── 2. Account lease ────────────────────────────────────────────────
    try:
        ent = requests.get(
            f"{DULUS_API_BASE}/api/entitlements",
            headers={"Authorization": f"Bearer {auth0_token}"},
            timeout=30,
        )
    except Exception as exc:
        notify(f"[dulus] Could not reach the Dulus API: {exc}")
        return None
    if ent.status_code != 200:
        notify(f"[dulus] Account lookup failed ({ent.status_code}).")
        return None
    lease = (ent.json() or {}).get("leaseToken")
    if not lease:
        notify("[dulus] This account has no active Dulus plan — sign up at dulus.ai first.")
        return None

    # ── 3. Authorization code (POST — there is no GET consent page) ─────
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    redirect_uri = f"http://127.0.0.1{_REDIRECT_PATH}"
    try:
        authz = requests.post(
            f"{DULUS_API_BASE}/v1/oauth/authorize",
            params={
                "client_id": DULUS_OAUTH_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
                "scope": DULUS_OAUTH_SCOPE,
            },
            headers={"X-Dulus-Lease": lease},
            timeout=30,
        )
    except Exception as exc:
        notify(f"[dulus] Authorization request failed: {exc}")
        return None
    if authz.status_code != 200:
        notify(f"[dulus] Authorization rejected ({authz.status_code}): {authz.text[:200]}")
        return None
    code = (authz.json() or {}).get("code")
    if not code:
        notify("[dulus] Server returned no authorization code.")
        return None

    # ── 4. Code exchange ────────────────────────────────────────────────
    try:
        response = requests.post(
            f"{DULUS_API_BASE}/v1/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": DULUS_OAUTH_CLIENT_ID,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
            timeout=30,
        )
    except Exception as exc:
        notify(f"[dulus] Token exchange failed: {exc}")
        return None

    if response.status_code != 200:
        notify(f"[dulus] Token exchange rejected ({response.status_code}).")
        return None

    store = _persist_tokens(response.json())
    notify("[dulus] Signed in.")
    return store.get("access_token") or None


def access_token(notify: Callable[[str], Any] = print) -> str:
    """Return a usable credential, refreshing when needed.

    Resolution order: an explicit API key from the environment, then a stored
    OAuth token, refreshed if expired. Returns "" when the user is not signed
    in, leaving it to the caller to decide whether to prompt.
    """
    explicit = (os.environ.get("DULUS_API_KEY") or "").strip()
    if explicit:
        return explicit

    store = load_store()
    token = store.get("access_token")
    if not token:
        return ""
    if not _token_expired(store):
        return token
    if store.get("refresh_token"):
        refreshed = refresh(store["refresh_token"])
        if refreshed and refreshed.get("access_token"):
            return refreshed["access_token"]
    return ""


def auth_headers(notify: Callable[[str], Any] = print) -> dict:
    """Authorization header for Dulus API calls, or empty when signed out."""
    token = access_token(notify)
    return {"Authorization": f"Bearer {token}"} if token else {}


def create_api_key(name: str = "cli", notify: Callable[[str], Any] = print) -> dict | None:
    """Mint a ``dulus_sk_*`` key for non-interactive use.

    Requires an interactive session first: keys are minted with an OAuth
    token, never with another key, so a leaked key cannot mint its own
    replacements.
    """
    import requests

    headers = auth_headers(notify)
    if not headers:
        notify("[dulus] Sign in first: /login dulus")
        return None
    try:
        response = requests.post(
            f"{DULUS_API_BASE}/v1/api-keys",
            json={"name": name},
            headers=headers,
            timeout=30,
        )
    except Exception as exc:
        notify(f"[dulus] Could not reach the Dulus API: {exc}")
        return None

    if response.status_code == 409:
        notify(f"[dulus] An API key named '{name}' already exists.")
        return None
    if response.status_code != 201:
        notify(f"[dulus] Could not create the API key ({response.status_code}).")
        return None

    payload = response.json()
    notify("[dulus] API key created. It is shown once and cannot be retrieved again:")
    notify(f"  {payload.get('apiKey', '')}")
    return payload
