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
from urllib.parse import parse_qs, urlencode, urlparse


DULUS_API_BASE = os.environ.get("DULUS_API_BASE", "https://api.dulus.ai").rstrip("/")
DULUS_OAUTH_CLIENT_ID = "dulus-cli"
DULUS_OAUTH_SCOPE = "inference balance:read"
_REDIRECT_PATH = "/callback"
_LOGIN_TIMEOUT_SECONDS = 180
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
    """Run the browser login. Returns an access token, or None on failure."""
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer

    import requests

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    captured: dict = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = parse_qs(urlparse(self.path).query)
            captured["code"] = (query.get("code") or [None])[0]
            captured["state"] = (query.get("state") or [None])[0]
            captured["error"] = (query.get("error") or [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ok = captured.get("code") and not captured.get("error")
            body = (
                "<h2>Dulus &mdash; you're signed in</h2>"
                "<p>You can close this tab and return to the terminal.</p>"
                if ok
                else "<h2>Dulus &mdash; sign-in failed</h2><p>%s</p>"
                % (captured.get("error") or "no code received")
            )
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;background:#111;color:#eee;"
                b"text-align:center;padding-top:60px'>" + body.encode("utf-8") + b"</body></html>"
            )

        def log_message(self, *_args) -> None:
            pass  # the default handler logs every hit to stderr

    # Port 0 lets the OS pick a free port, so a second login (or a leftover
    # socket) can never make sign-in fail with "address already in use".
    try:
        server = HTTPServer(("127.0.0.1", 0), _Handler)
    except OSError as exc:
        notify(f"[dulus] Cannot start the local callback server: {exc}")
        return None
    port = server.server_port
    redirect_uri = f"http://127.0.0.1:{port}{_REDIRECT_PATH}"
    server.timeout = 1

    authorize_url = f"{DULUS_API_BASE}/v1/oauth/authorize?" + urlencode(
        {
            "response_type": "code",
            "client_id": DULUS_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": DULUS_OAUTH_SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    notify("[dulus] Opening your browser to sign in…")
    notify(f"[dulus] If it doesn't open, paste this URL manually:\n{authorize_url}")
    try:
        webbrowser.open(authorize_url)
    except Exception:
        pass

    deadline = time.time() + _LOGIN_TIMEOUT_SECONDS
    while "code" not in captured and "error" not in captured and time.time() < deadline:
        server.handle_request()
    try:
        server.server_close()
    except Exception:
        pass

    if captured.get("error"):
        notify(f"[dulus] Sign-in denied: {captured['error']}")
        return None
    if not captured.get("code"):
        notify("[dulus] Sign-in timed out (no callback received).")
        return None
    # The state proves this callback belongs to the request we just made; a
    # mismatch means someone else's authorization was injected.
    if captured.get("state") != state:
        notify("[dulus] State mismatch — aborting for safety (possible CSRF).")
        return None

    try:
        response = requests.post(
            f"{DULUS_API_BASE}/v1/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": DULUS_OAUTH_CLIENT_ID,
                "code": captured["code"],
                "redirect_uri": redirect_uri,
                # Proves this exchange comes from the program that started the
                # flow, which is what makes a stolen code useless.
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
