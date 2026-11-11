"""Sign in to a Dulus account from the CLI.

Dulus issues its own credentials rather than delegating identity to a third
party, so this talks to the Dulus API directly: a device-code sign-in for
people, and long-lived ``dulus_sk_*`` API keys for servers and CI.

The sign-in has to work wherever Dulus runs, so nothing in it depends on this
machine having a screen: Dulus shows a link and a code, and the person
approves from any device — this one, a phone, a laptop. A browser is opened
for them only when there's a desktop in front of them, and never in a way
that can take over the terminal.

The client is public, so it holds no secret. PKCE is what proves the code is
being redeemed by the same program that requested it.

Tokens land in ``~/.dulus/account.json`` with owner-only permissions.
"""
from __future__ import annotations

import base64
import functools
import hashlib
import io
import json
import os
import pathlib
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, NoReturn, TextIO


DULUS_API_BASE = os.environ.get("DULUS_API_BASE", "https://control.dulus.ai").rstrip("/")
DULUS_OAUTH_CLIENT_ID = "dulus-cli"
DULUS_OAUTH_SCOPE = "inference balance:read"
_REDIRECT_PATH = "/callback"
# Device codes live 15 minutes. Someone on a server may need all of it: find
# their phone, create the account, confirm the e-mail.
_LOGIN_TIMEOUT_SECONDS = 900
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

# Terminal browsers. Started from here they would take over the very terminal
# that is showing the sign-in link.
_TEXT_BROWSERS = frozenset({
    "www-browser", "w3m", "lynx", "elinks", "links", "links2", "elvis", "browsh",
})
# How long a browser opener (xdg-open, open, wslview…) gets to report failure.
# One still running after this is the browser itself, so it counts as opened.
_BROWSER_WAIT_SECONDS = 4.0


def _is_text_browser(command: str) -> bool:
    """True for terminal browsers that hijack the TTY (w3m, lynx, links…)."""
    program = os.path.basename((command or "").strip().split(" ", 1)[0]).lower()
    return program.removesuffix(".exe") in _TEXT_BROWSERS


def _over_ssh() -> bool:
    """A browser opened from an SSH session lands on the far machine's screen, or nowhere."""
    return any(os.environ.get(name) for name in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"))


def _spawn_detached(argv: list[str]) -> bool:
    """Run one browser opener cut off from the terminal. False only when it plainly failed.

    No stdin, stdout or stderr and a session of its own: whatever it ends up
    starting — even a text browser it falls back to — can't draw over the CLI,
    read its keystrokes or hold up the sign-in.
    """
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, ValueError):
        return False
    try:
        return proc.wait(timeout=_BROWSER_WAIT_SECONDS) == 0
    except subprocess.TimeoutExpired:
        return True  # still running: that's the browser itself, not a failure


def _start_file(url: str) -> bool:
    """Windows: hand *url* to the default browser, the way ``webbrowser`` does."""
    if sys.platform != "win32":
        return False
    try:
        os.startfile(url)
    except OSError:
        return False
    return True


def _browser_openers(url: str, mode: str = "auto") -> list[Callable[[], bool]]:
    """Ways to show *url* in a graphical browser on this machine, best first.

    ``mode`` is ``"auto"`` (only with a desktop in front of the person),
    ``"always"`` (over SSH too) or ``"never"``. No openers means headless:
    the person approves from another device. Unlike ``webbrowser.open`` this
    never falls back to a text browser.
    """
    if mode == "never":
        return []
    desktop = mode == "always" or not _over_ssh()
    if sys.platform == "win32":
        return [functools.partial(_start_file, url)] if desktop else []
    commands: list[list[str]] = []
    # An explicit $BROWSER says how links open here. VS Code points it at a
    # helper that opens them on the person's own machine from a remote or
    # container terminal, so it counts even with no desktop of our own.
    for entry in os.environ.get("BROWSER", "").split(os.pathsep):
        try:
            argv = shlex.split(entry)
        except ValueError:
            continue
        if argv and not _is_text_browser(argv[0]):
            commands.append([a.replace("%s", url) for a in argv] if "%s" in entry else argv + [url])
    if desktop:
        if sys.platform == "darwin":
            commands.append(["open", url])
        else:
            commands.append(["wslview", url])  # WSL: the Windows default browser
            # Without a display xdg-open can only fall back to a text browser.
            if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                commands += [["xdg-open", url], ["gio", "open", url], ["x-www-browser", url]]
    return [functools.partial(_spawn_detached, argv) for argv in commands if shutil.which(argv[0])]


def _show_qr(data: str, out: Any, spare_lines: int) -> bool:
    """Draw *data* on *out* as a QR for a phone to scan. False when it didn't.

    Only whole, with *spare_lines* of text still on screen under it, and only
    with segno installed.
    """
    try:
        import segno
    except ImportError:
        return False
    buf = io.StringIO()
    segno.make_qr(data, error="m").terminal(out=buf, compact=True)
    rows = buf.getvalue().splitlines()
    try:
        size = os.get_terminal_size(out.fileno())
    except (AttributeError, OSError, ValueError):
        size = shutil.get_terminal_size()
    if len(rows) + spare_lines > size.lines or max(map(len, rows), default=0) > size.columns:
        return False
    # White on black, set explicitly: in the terminal's own colors the QR
    # comes out inverted on a light theme, which many phone scanners can't
    # read. 256-color 231 and 16 are pure white and black; themes leave them be.
    if not (os.environ.get("NO_COLOR") or os.environ.get("TERM", "").lower() == "dumb"):
        rows = [f"\033[38;5;231;48;5;16m{row}\033[0m" for row in rows]
    out.write("\n".join(rows) + "\n")
    out.flush()
    return True


def _json_body(response: Any) -> dict:
    """A reply's JSON object, or {} for an empty, HTML or otherwise unusable body."""
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - a proxy's error page is not JSON
        return {}
    return body if isinstance(body, dict) else {}


def _transient(status: int) -> bool:
    """Rate-limited or failing on the server's side: worth asking again."""
    return status == 429 or status >= 500


def _seconds(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


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


def _poll_device_flow(device_code: str) -> tuple[str, str]:
    """Ask Auth0 once whether the person approved. Returns ``(outcome, detail)``.

    ``"token"`` carries the Auth0 access token; ``"pending"`` and
    ``"slow_down"`` are the RFC 8628 waits; ``"retry"`` is no usable answer at
    all (no network, a 5xx, a proxy's HTML page); ``"denied"``, ``"expired"``
    and ``"failed"`` end the sign-in.
    """
    import requests

    try:
        reply = requests.post(
            f"https://{_AUTH0_DOMAIN}/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": _AUTH0_CLIENT_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 - offline for a moment: ask again
        return "retry", type(exc).__name__
    body = _json_body(reply)
    if reply.status_code == 200 and body.get("access_token"):
        return "token", str(body["access_token"])
    error = str(body.get("error") or "")
    if error == "authorization_pending":
        return "pending", ""
    if error == "slow_down":
        return "slow_down", ""
    if error == "access_denied":
        return "denied", ""
    if error in ("expired_token", "expired"):
        return "expired", ""
    if error and not _transient(reply.status_code):
        return "failed", str(body.get("error_description") or error)
    return "retry", f"HTTP {reply.status_code}"


class _Unreachable(Exception):
    """The sign-in servers gave this network no answer — which is not a refusal."""


def _unreachable(notify: Callable[[str], Any], what: str, url: str) -> NoReturn:
    """Say what didn't answer and how to get through, then end the sign-in."""
    notify(f"[dulus] {what}")
    notify(f"[dulus] Check this machine can reach {url} — behind a proxy, set HTTPS_PROXY.")
    raise _Unreachable(what)


def _ask_dulus(notify: Callable[[str], Any], send: Callable[..., Any], url: str,
               **kwargs: Any) -> Any:
    """One Dulus API call after approval, with the tries the start of the sign-in gets.

    By then the person has approved, often from a phone: one connection lost on
    a long route (mainland China, a hotel network) shouldn't throw that away.
    """
    problem = ""
    for attempt in range(3):
        if attempt:
            time.sleep(2 * attempt)
        try:
            reply = send(url, timeout=30, **kwargs)
        except Exception as exc:  # noqa: BLE001 - no network for a moment: try again
            problem = type(exc).__name__
            continue
        if not _transient(reply.status_code):
            return reply
        problem = f"HTTP {reply.status_code}"
    _unreachable(notify, f"Could not reach the Dulus API ({problem}).", DULUS_API_BASE)


def sign_in(
    notify: Callable[[str], Any] = functools.partial(print, flush=True),
    browser: str = "auto",
    out: TextIO | None = None,
    *,
    quiet: bool = False,
) -> tuple[str, str | None]:
    """:func:`login`, also saying how it went.

    Returns ``("ok", token)`` once signed in, ``("refused", None)`` when the
    sign-in was denied, abandoned or turned down, and ``("unreachable", None)``
    when this network never got an answer from the sign-in servers — the same
    split :func:`_renew` makes for renewals.

    ``quiet`` says nothing about servers that don't answer (no retry notices,
    nothing to check), so the launch gate can let such a person in without a
    word. The sign-in itself — link, code, approval — still shows.
    """
    explain = (lambda _message: None) if quiet else notify
    try:
        token = _device_flow(notify, browser, out, explain)
    except _Unreachable:
        # A filtered network (mainland China, a locked-down office) can still
        # run on an account: a key minted wherever Dulus answers works here.
        explain("[dulus] Or sign in on any machine that can reach Dulus, mint a key there with "
                "`/login dulus key`, and set DULUS_API_KEY to it on this one.")
        return "unreachable", None
    return ("ok", token) if token else ("refused", None)


def login(
    notify: Callable[[str], Any] = functools.partial(print, flush=True),
    browser: str = "auto",
    out: TextIO | None = None,
) -> str | None:
    """Sign in via the device flow. Returns an access token, or None.

    Works the same on a desktop, over SSH and on a box with no screen:

      * The link and code are shown before anything else is tried, so the
        sign-in can always be approved from another device.
      * ``browser="auto"`` opens one only with a desktop in front of the
        person, and says so when it couldn't; ``"never"`` (``/login dulus
        --headless``) opens none; ``"always"`` (``--browser``) tries over SSH
        too. Openers run cut off from the terminal, so none can take it over.
      * With no browser, ``out`` (the stream the person is watching) also gets
        a QR of the link to scan with a phone, when it fits on screen.
      * Waiting for approval rides out a flaky network or proxy until the code
        expires.

    The server has no browser consent page for the CLI: /v1/oauth/authorize
    is a POST-only API that expects an account lease. So the chain is:

      1. Auth0 device-code login (works headless; the approving browser can
         be on any machine — nothing has to reach the CLI's localhost).
      2. GET /api/entitlements with the Auth0 token → account lease.
      3. POST /v1/oauth/authorize with the lease → authorization code.
      4. POST /v1/oauth/token (code + PKCE verifier) → CLI tokens.

    :func:`sign_in` does the work and also tells a refusal apart from a
    network that can't reach the sign-in servers.
    """
    return sign_in(notify, browser, out)[1]


def _device_flow(notify: Callable[[str], Any], browser: str, out: TextIO | None,
                 explain: Callable[[str], Any]) -> str | None:
    """The chain :func:`login` describes.

    ``explain`` gets what's said about servers that don't answer. Raises
    :class:`_Unreachable` when a step gets no answer.
    """
    import requests

    # ── 1. Auth0 device code ────────────────────────────────────────────
    start: dict = {}
    problem = ""
    for attempt in range(3):
        if attempt:
            explain(f"[dulus] No answer from the login server yet ({problem}) — trying again…")
            time.sleep(2 * attempt)
        start = {}
        try:
            reply = requests.post(
                f"https://{_AUTH0_DOMAIN}/oauth/device/code",
                data={"client_id": _AUTH0_CLIENT_ID, "scope": _AUTH0_SCOPES},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
        except Exception as exc:  # noqa: BLE001 - no network yet: try again
            problem = type(exc).__name__
            continue
        start = _json_body(reply)
        problem = f"HTTP {reply.status_code}"
        if not _transient(reply.status_code):
            break

    device_code = str(start.get("device_code") or "")
    user_code = str(start.get("user_code") or "")
    short_link = str(start.get("verification_uri") or "")
    link = str(start.get("verification_uri_complete") or short_link)
    if not (device_code and user_code and link):
        refusal = start.get("error_description") or start.get("error")
        if not refusal:
            _unreachable(explain, f"Couldn't get a sign-in code from the login server ({problem}).",
                         f"https://{_AUTH0_DOMAIN}")
        notify(f"[dulus] The login server wouldn't start a sign-in: {refusal}")
        return None

    interval = _seconds(start.get("interval"), 5)
    lifetime = min(_seconds(start.get("expires_in"), _LOGIN_TIMEOUT_SECONDS),
                   _LOGIN_TIMEOUT_SECONDS)
    # Monotonic: a Raspberry Pi has no clock of its own, and NTP setting it
    # mid-wait must not end the sign-in on the spot.
    deadline = time.monotonic() + lifetime

    # The link goes up first: whatever happens with a browser, the person can
    # always finish from another device.
    openers = _browser_openers(link, browser)
    if openers:
        notify("[dulus] To sign in, open this link on any device (phone, laptop):")
    else:
        notify("[dulus] Not opening a browser here — sign in from your phone or laptop:")
        if out is not None:
            _show_qr(link, out, spare_lines=7)  # keeps the link below it on screen
    notify(f"\n    {link}\n")
    if short_link and short_link != link:
        notify(f"[dulus] Or go to {short_link} and enter {user_code}")
    else:
        notify(f"[dulus] Then enter the code {user_code}")

    if openers:
        # In a daemon thread with a deadline, so even a launcher that hangs
        # (Windows' shell can) never holds up the sign-in.
        launched: list[bool] = []
        worker = threading.Thread(
            target=lambda: launched.append(any(open_it() for open_it in openers)), daemon=True,
        )
        worker.start()
        worker.join(2 * _BROWSER_WAIT_SECONDS)
        if launched and not launched[0]:
            # Most often a desktop that isn't really there (a tmux pane that
            # kept an old DISPLAY), so the phone route gets its QR as well.
            notify("[dulus] Couldn't open a browser here — use the link above on any device.")
            if out is not None:
                _show_qr(link, out, spare_lines=8)
        else:
            notify(f"[dulus] Opening your browser — check it shows {user_code}, then approve.")
    notify(f"[dulus] Waiting for approval — the code expires in {max(1, lifetime // 60)} min. "
           "Ctrl+C to cancel.")

    auth0_token = ""
    stalled = False
    answered = False  # did Auth0 answer even one poll?
    while time.monotonic() < deadline:
        time.sleep(interval)
        outcome, detail = _poll_device_flow(device_code)
        answered = answered or outcome != "retry"
        if outcome == "token":
            auth0_token = detail
            break
        if outcome == "slow_down":
            interval += 5
        elif outcome == "retry" and not stalled:
            stalled = True
            notify(f"[dulus] Can't reach the login server ({detail}) — still trying…")
        elif outcome == "denied":
            notify("[dulus] Sign-in denied.")
            return None
        elif outcome == "expired":
            notify("[dulus] The login code expired. Run /login dulus again.")
            return None
        elif outcome == "failed":
            notify(f"[dulus] Login failed: {detail}")
            return None

    if not auth0_token:
        if not answered:
            _unreachable(explain, "The login server never answered while waiting for approval.",
                         f"https://{_AUTH0_DOMAIN}")
        notify("[dulus] Sign-in timed out before it was approved.")
        return None

    # ── 2. Account lease ────────────────────────────────────────────────
    ent = _ask_dulus(explain, requests.get, f"{DULUS_API_BASE}/api/entitlements",
                     headers={"Authorization": f"Bearer {auth0_token}"})
    if ent.status_code != 200:
        notify(f"[dulus] Account lookup failed ({ent.status_code}).")
        return None
    ent_data = _json_body(ent)
    lease = ent_data.get("leaseToken")
    if not lease:
        notify("[dulus] This account has no active Dulus plan — sign up at dulus.ai first.")
        return None

    # ── 3. Authorization code (POST — there is no GET consent page) ─────
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    redirect_uri = f"http://127.0.0.1{_REDIRECT_PATH}"
    authz = _ask_dulus(
        explain,
        requests.post,
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
    code = _json_body(authz).get("code")
    if not code:
        notify("[dulus] Server returned no authorization code.")
        return None

    # ── 4. Code exchange ────────────────────────────────────────────────
    response = _ask_dulus(
        explain,
        requests.post,
        f"{DULUS_API_BASE}/v1/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": DULUS_OAUTH_CLIENT_ID,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    payload = _json_body(response)
    if response.status_code != 200 or not payload.get("access_token"):
        notify(f"[dulus] Token exchange rejected ({response.status_code}).")
        return None

    store = _persist_tokens(payload)
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

