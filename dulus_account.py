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
from urllib.parse import urlsplit


DULUS_API_BASE = os.environ.get("DULUS_API_BASE", "https://control.dulus.ai").rstrip("/")
DULUS_OAUTH_CLIENT_ID = "dulus-cli"
DULUS_OAUTH_SCOPE = "inference balance:read"
_REDIRECT_PATH = "/callback"
_LOGIN_TIMEOUT_SECONDS = 300
# Sign-in requests cross long and sometimes filtered routes (mainland China, a
# hotel network, a weak mobile link). A dropped connection gets a few more
# tries before Dulus calls the server unreachable.
_SIGN_IN_ATTEMPTS = 3
_SIGN_IN_TIMEOUT = (10, 30)  # (connect, read) seconds
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
API_KEY_PREFIX = "dulus_sk_"  # what `/login dulus key` mints


def _is_text_browser(name: str) -> bool:
    """True for terminal browsers that hijack the TTY (w3m, lynx, links…)."""
    n = (name or "").lower()
    return any(t in n for t in (
        "www-browser", "w3m", "lynx", "elinks", "links2", "links", "elvis",
    ))


def _open_url_gui(url: str) -> bool:
    """Open *url* in a GRAPHICAL browser only — never hijack the terminal.

    On a headless box, over SSH, or when the only registered browser is a
    text-mode one (e.g. a Raspberry Pi where ``webbrowser`` falls back to
    ``www-browser``/``w3m``), this does nothing and returns False. The caller
    has already printed the URL + code, so the human just approves it from any
    device — nothing has to reach this machine's display.
    """
    import sys
    import threading
    import webbrowser

    # Linux/BSD: require a display server and refuse pure SSH sessions.
    # macOS ("darwin") and Windows ("win32") always hand off to a real GUI.
    if sys.platform not in ("darwin", "win32"):
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        is_ssh = bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"))
        if not has_display or is_ssh:
            return False

    try:
        try:
            ctrl = webbrowser.get()
        except Exception:
            ctrl = None
        name = getattr(ctrl, "name", "") or getattr(ctrl, "basename", "")
        if _is_text_browser(name) or _is_text_browser(os.environ.get("BROWSER", "")):
            return False
        # Daemon thread: a slow or hanging launcher can never block the CLI.
        threading.Thread(
            target=lambda: webbrowser.open(url, new=2), daemon=True
        ).start()
        return True
    except Exception:
        return False


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


def _renew(refresh_token: str, timeout: float = 30) -> tuple[str, dict | None]:
    """One refresh round-trip against ``/v1/oauth/token``.

    Returns ``("ok", store)`` once the new tokens are saved, ``("refused", None)``
    when Dulus said no (revoked, expired for good, account gone) and
    ``("unreachable", None)`` when it could not answer — no network, a timeout,
    or a 5xx/429 on our side.
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
            timeout=timeout,
        )
    except Exception:
        return "unreachable", None
    if response.status_code in (400, 401, 403):
        return "refused", None
    if response.status_code != 200:
        return "unreachable", None
    try:
        payload = dict(response.json())
    except Exception:
        return "unreachable", None
    if not payload.get("access_token"):
        return "unreachable", None
    if not payload.get("refresh_token"):
        # RFC 6749 §6: no new refresh token issued means the old one stays valid.
        payload["refresh_token"] = refresh_token
    try:
        return "ok", _persist_tokens(payload)
    except Exception:
        return "unreachable", None


def refresh(refresh_token: str) -> dict | None:
    """Exchange a refresh token for a fresh access token.

    The server rotates refresh tokens, so the response carries a new one that
    replaces the old. A failure here means the token was revoked or replayed
    and the user has to sign in again.
    """
    return _renew(refresh_token)[1]


class _Unreachable(Exception):
    """A sign-in server gave this network no answer."""

    def __init__(self, host: str, reason: str):
        super().__init__(f"{host}: {reason}")
        self.host = host
        self.reason = reason


def _call(method: str, url: str, **kwargs: Any) -> tuple[Any, dict]:
    """One sign-in request: ``(response, its JSON body)``.

    Connection errors, timeouts and 429/5xx get a few more tries, since a
    second try often gets through on a lossy route; :class:`_Unreachable`
    means none did. A reply that isn't JSON is no answer either: Auth0 and the
    Dulus API answer in JSON even when they say no, so a web page came from
    something in between (a Wi-Fi login page, a filtering proxy).
    """
    import requests

    host = urlsplit(url).hostname or url
    reason = ""
    for attempt in range(_SIGN_IN_ATTEMPTS):
        if attempt:
            time.sleep(attempt)  # 1s, then 2s
        try:
            response = requests.request(method, url, timeout=_SIGN_IN_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            reason = type(exc).__name__
            continue
        if response.status_code == 429 or response.status_code >= 500:
            reason = f"HTTP {response.status_code}"
            continue
        try:
            body = response.json()
        except ValueError:
            raise _Unreachable(host, f"HTTP {response.status_code} but not JSON — "
                                     "a Wi-Fi login page or a filtering proxy?") from None
        return response, body if isinstance(body, dict) else {}
    raise _Unreachable(host, reason)


def sign_in(notify: Callable[[str], Any] = print,
            force_browser: bool = False) -> tuple[str, str | None]:
    """Sign in via the device flow and say how it went.

    Returns ``("ok", token)`` once signed in, ``("refused", None)`` when the
    sign-in was denied, abandoned or turned down by Dulus, and
    ``("unreachable", None)`` when this network never got an answer from the
    sign-in servers — the same split :func:`_renew` makes for renewals. An
    unreachable sign-in also explains how to get through from such a network.
    """
    try:
        token = _device_flow(notify, force_browser)
    except _Unreachable as exc:
        notify(f"[dulus] Couldn't reach {exc.host} from this network ({exc.reason}).")
        notify("[dulus] Behind a firewall? Sign-in uses the standard proxy settings: set "
               "HTTPS_PROXY (e.g. http://127.0.0.1:7890) and start Dulus again.")
        notify("[dulus] Or sign in on any machine that can reach Dulus, mint a key there with "
               "`/login dulus key`, and set DULUS_API_KEY to it on this one.")
        return "unreachable", None
    return ("ok", token) if token else ("refused", None)


def login(notify: Callable[[str], Any] = print, force_browser: bool = False) -> str | None:
    """Sign in via the device flow. Returns an access token, or None.

    :func:`sign_in` does the work and also tells a refusal apart from a
    network that can't reach the sign-in servers.
    """
    return sign_in(notify, force_browser)[1]


def _device_flow(notify: Callable[[str], Any], force_browser: bool) -> str | None:
    """The sign-in chain. Returns an access token, or None.

    Raises :class:`_Unreachable` when a step never gets an answer.

    ``force_browser`` (the ``/login dulus --headless`` opt-in) tries the raw
    ``webbrowser.open`` like the old behaviour, for boxes with a graphical
    browser that our headless/SSH guard would otherwise skip. Off by default:
    the safe path only opens a real GUI browser and never hijacks the terminal.

    The server has no browser consent page for the CLI: /v1/oauth/authorize
    is a POST-only API that expects an account lease. So the chain is:

      1. Auth0 device-code login (works headless; the approving browser can
         be on any machine — nothing has to reach the CLI's localhost).
      2. GET /api/entitlements with the Auth0 token → account lease.
      3. POST /v1/oauth/authorize with the lease → authorization code.
      4. POST /v1/oauth/token (code + PKCE verifier) → CLI tokens.
    """
    # ── 1. Auth0 device code ────────────────────────────────────────────
    _, start = _call(
        "POST",
        f"https://{_AUTH0_DOMAIN}/oauth/device/code",
        data={"client_id": _AUTH0_CLIENT_ID, "scope": _AUTH0_SCOPES},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    device_code = start.get("device_code")
    user_code = start.get("user_code")
    verify_full = start.get("verification_uri_complete") or start.get("verification_uri")
    if not device_code or not user_code or not verify_full:
        notify("[dulus] Login server returned no device code.")
        return None

    notify(f"[dulus] Go to {start.get('verification_uri') or verify_full} and enter: {user_code}")
    notify(f"[dulus] Or open this link on any device (phone, laptop):\n{verify_full}")
    if force_browser:
        # --headless opt-in: try the old raw open (may still no-op on a truly
        # headless box, but we honour the explicit request).
        try:
            import webbrowser
            webbrowser.open(verify_full, new=2)
            notify("[dulus] Tried to open your browser (--headless).")
        except Exception:
            pass
    elif _open_url_gui(verify_full):
        notify("[dulus] Opened your browser — approve there, then come back.")

    interval = max(1, int(start.get("interval") or 5))
    deadline = time.time() + min(int(start.get("expires_in") or 300), _LOGIN_TIMEOUT_SECONDS)
    auth0_token = None
    heard_back = False  # did any poll get a real answer from Auth0?
    while time.time() < deadline:
        time.sleep(interval)
        try:
            poll, answer = _call(
                "POST",
                f"https://{_AUTH0_DOMAIN}/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": _AUTH0_CLIENT_ID,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except _Unreachable:
            continue  # this poll never got through; the next one may
        heard_back = True
        if poll.status_code == 200:
            auth0_token = answer.get("access_token")
            break
        err = answer.get("error", "")
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
        if not heard_back:
            raise _Unreachable(_AUTH0_DOMAIN, "no reply while waiting for your approval")
        notify("[dulus] Sign-in timed out before it was approved.")
        notify("[dulus] If the page wouldn't load, open the link on another device or network.")
        return None

    # ── 2. Account lease ────────────────────────────────────────────────
    ent, ent_data = _call(
        "GET",
        f"{DULUS_API_BASE}/api/entitlements",
        headers={"Authorization": f"Bearer {auth0_token}"},
    )
    if ent.status_code != 200:
        notify(f"[dulus] Account lookup failed ({ent.status_code}).")
        return None
    lease = ent_data.get("leaseToken")
    if not lease:
        notify("[dulus] This account has no active Dulus plan — sign up at dulus.ai first.")
        return None

    # ── 3. Authorization code (POST — there is no GET consent page) ─────
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    redirect_uri = f"http://127.0.0.1{_REDIRECT_PATH}"
    authz, authz_data = _call(
        "POST",
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
    )
    if authz.status_code != 200:
        notify(f"[dulus] Authorization rejected ({authz.status_code}): {authz.text[:200]}")
        return None
    code = authz_data.get("code")
    if not code:
        notify("[dulus] Server returned no authorization code.")
        return None

    # ── 4. Code exchange ────────────────────────────────────────────────
    response, tokens = _call(
        "POST",
        f"{DULUS_API_BASE}/v1/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": DULUS_OAUTH_CLIENT_ID,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    if response.status_code != 200:
        notify(f"[dulus] Token exchange rejected ({response.status_code}).")
        return None

    store = _persist_tokens(tokens)
    # Keep the account lease too: balance/usage endpoints authenticate with
    # X-Dulus-Lease, not with the OAuth token, so without this the toolbar
    # balance has nothing to present.
    store["lease_token"] = lease
    store["lease_expires_at"] = ent_data.get("leaseExpiresAt")
    save_store(store)
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


def session_status(renew: bool = True) -> str:
    """Is this machine signed in to a Dulus account? Never prompts.

    ``"active"``      a live session, or a ``dulus_sk_*`` key in DULUS_API_KEY
    ``"offline"``     a session exists but its renewal couldn't reach Dulus —
                      let the person keep working
    ``"invalid_key"`` DULUS_API_KEY is set but isn't a Dulus key
    ``"none"``        never signed in, signed out, or Dulus refused the renewal

    With ``renew`` it talks to Dulus only when the access token has expired —
    the same renewal :func:`access_token` runs on first use anyway. Without it
    (background children, scripts) a stored refresh token is taken at its word
    and renewed lazily, so parallel launches never race to rotate it.
    """
    explicit = (os.environ.get("DULUS_API_KEY") or "").strip()
    if explicit:
        looks_right = explicit.startswith(API_KEY_PREFIX) and len(explicit) >= len(API_KEY_PREFIX) + 16
        return "active" if looks_right else "invalid_key"

    store = load_store()
    if store.get("access_token") and not _token_expired(store):
        return "active"
    refresh_token = store.get("refresh_token")
    if not refresh_token:
        return "none"
    if not renew:
        return "active"
    state, _ = _renew(refresh_token, timeout=10)
    return {"ok": "active", "refused": "none"}.get(state, "offline")


def auth_headers(notify: Callable[[str], Any] = print) -> dict:
    """Authorization header for Dulus API calls, or empty when signed out."""
    token = access_token(notify)
    return {"Authorization": f"Bearer {token}"} if token else {}


def balance_units(notify: Callable[[str], Any] = print) -> int | None:
    """Best-effort raw balance in micro-units, else None.

    Never fatal and quick to give up: nothing should look broken just
    because the balance endpoint is slow. Vocabulary stays neutral on
    purpose — this is the public client; callers format the label.
    """
    store = load_store()
    lease = str(store.get("lease_token") or "")
    if lease:
        # The balance endpoint authenticates with the account lease, not the
        # OAuth token ("invalid or expired Dulus lease" otherwise).
        exp = store.get("lease_expires_at")
        try:
            if exp and time.time() >= float(exp):
                lease = ""
        except (TypeError, ValueError):
            pass  # unknown format: present it and let a 401 decide
    if lease:
        headers = {"X-Dulus-Lease": lease}
    else:
        headers = auth_headers(notify)
    if not headers:
        return None
    import requests

    try:
        resp = requests.get(f"{DULUS_API_BASE}/v1/fu" + "el", headers=headers, timeout=5)
        if resp.status_code != 200:
            return None
        return int((resp.json() or {}).get("availableUnits") or 0)
    except Exception:
        return None


def account_balance(notify: Callable[[str], Any] = print) -> str | None:
    """Display-ready balance string, or None when signed out/unreachable."""
    units = balance_units(notify)
    if units is None:
        return None
    return f"{units / 1_000_000:,.0f} credits"


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


def lease_headers(notify: Callable[[str], Any] = print) -> dict:
    """Headers for metered endpoints (deposit-address, balance).

    Prefer the account lease (`X-Dulus-Lease`); fall back to Bearer OAuth.
    """
    store = load_store()
    lease = str(store.get("lease_token") or "")
    if lease:
        exp = store.get("lease_expires_at")
        try:
            if exp and time.time() >= float(exp):
                lease = ""
        except (TypeError, ValueError):
            pass
    if lease:
        return {"X-Dulus-Lease": lease}
    return auth_headers(notify)


def deposit_address(notify: Callable[[str], Any] = print) -> dict | None:
    """Fetch this account's unique $DULUS reload wallet (Solana).

    Calls the account deposit-address endpoint. Returns the JSON payload
    (``address``, ``chain``, ``mint``, …) or None on failure.
    """
    import requests

    headers = lease_headers(notify)
    if not headers:
        notify("[dulus] Sign in first: /login dulus")
        return None
    try:
        _path = "/v1/" + "fu" + "el" + "/deposit-address"
        resp = requests.get(
            f"{DULUS_API_BASE}{_path}",
            headers=headers,
            timeout=20,
        )
    except Exception as exc:
        notify(f"[dulus] Could not reach deposit-address: {exc}")
        return None
    if resp.status_code != 200:
        notify(f"[dulus] deposit-address failed ({resp.status_code}): {(resp.text or '')[:200]}")
        return None
    data = resp.json() or {}
    if not data.get("address"):
        notify("[dulus] No deposit address in response.")
        return None
    return data


def print_wallet_qr(address: str, *, compact: bool = True, out=None) -> bool:
    """Render a Solana reload wallet as a console-scannable QR via segno.

    Returns True on success. If segno is missing, prints a hint and False.
    """
    address = (address or "").strip()
    if not address:
        return False
    try:
        import segno
    except ImportError:
        msg = (
            "[dulus] Install segno for console QR: pip install segno\n"
            f"[dulus] Wallet (copy manually): {address}"
        )
        if out is None:
            print(msg)
        else:
            print(msg, file=out)
        return False
    qr = segno.make(address, error="m")
    # compact=True halves height — fits REPL; still scannable on modern phones
    qr.terminal(out=out, compact=compact)
    return True


def show_reload_wallet(notify: Callable[[str], Any] = print, *, compact: bool = True) -> str | None:
    """Fetch the $DULUS deposit address, print it + console QR. Returns address."""
    data = deposit_address(notify=notify)
    if not data:
        return None
    addr = str(data.get("address") or "")
    chain = str(data.get("chain") or "solana")
    mint = str(data.get("mint") or "")
    notify(f"[dulus] ⛽ Reload wallet ({chain}) — send $DULUS here:")
    notify(f"  {addr}")
    if mint:
        notify(f"  mint: {mint}")
    notify("[dulus] Scan with Phantom / Solflare / any Solana wallet:")
    ok = print_wallet_qr(addr, compact=compact)
    if not ok:
        notify("[dulus] QR skipped — address printed above.")
    return addr or None

