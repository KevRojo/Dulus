from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dulus_account


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep every test off the developer's real ~/.dulus."""
    monkeypatch.setenv("DULUS_HOME", str(tmp_path))
    monkeypatch.delenv("DULUS_API_KEY", raising=False)
    yield tmp_path


def test_pkce_pair_matches_the_s256_challenge_the_server_will_check() -> None:
    verifier, challenge = dulus_account._pkce_pair()

    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    assert challenge == expected
    # The RFC floor is 43 characters; anything shorter is brute-forceable.
    assert len(verifier) >= 43
    assert dulus_account._pkce_pair()[0] != verifier  # fresh every call


def test_tokens_round_trip_through_the_store(isolated_home) -> None:
    dulus_account.save_store({"access_token": "abc", "refresh_token": "def"})

    assert dulus_account.load_store()["access_token"] == "abc"
    assert (isolated_home / "account.json").exists()

    dulus_account.clear_store()
    assert dulus_account.load_store() == {}


def test_a_corrupt_store_reads_as_signed_out_instead_of_crashing(isolated_home) -> None:
    (isolated_home / "account.json").write_text("{not json", encoding="utf-8")

    # A truncated write must not make the CLI unusable.
    assert dulus_account.load_store() == {}
    assert dulus_account.access_token(notify=lambda _m: None) == ""


def test_expiry_uses_a_buffer_so_tokens_do_not_die_in_flight() -> None:
    assert dulus_account._token_expired({"expires_at": time.time() - 1})
    assert not dulus_account._token_expired({"expires_at": time.time() + 300})
    # An unknown lifetime is treated as valid; a 401 will drive the refresh.
    assert not dulus_account._token_expired({})


def test_persisted_expiry_is_earlier_than_the_servers(isolated_home) -> None:
    before = time.time()
    store = dulus_account._persist_tokens({"access_token": "t", "expires_in": 3600})

    # Refreshing early is what stops a request leaving with a token that
    # expires while it is still in flight.
    assert store["expires_at"] < before + 3600
    assert store["expires_at"] > before + 3000


def test_an_explicit_api_key_wins_over_a_stored_session(isolated_home, monkeypatch) -> None:
    dulus_account.save_store({"access_token": "from-oauth", "expires_at": time.time() + 999})
    monkeypatch.setenv("DULUS_API_KEY", "dulus_sk_live_" + "a" * 43)

    # CI sets the env var and must not be hijacked by a leftover login.
    assert dulus_account.access_token(notify=lambda _m: None).startswith("dulus_sk_live_")


def test_signed_out_yields_no_auth_header(isolated_home) -> None:
    assert dulus_account.auth_headers(notify=lambda _m: None) == {}


def test_valid_session_yields_a_bearer_header(isolated_home) -> None:
    dulus_account.save_store(
        {"access_token": "live-token", "expires_at": time.time() + 600}
    )

    assert dulus_account.auth_headers(notify=lambda _m: None) == {
        "Authorization": "Bearer live-token"
    }


def test_an_expired_token_is_refreshed_transparently(isolated_home, monkeypatch) -> None:
    dulus_account.save_store(
        {
            "access_token": "stale",
            "refresh_token": "refresh-me",
            "expires_at": time.time() - 10,
        }
    )

    captured: dict = {}

    class _Response:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "access_token": "fresh",
                "refresh_token": "rotated",
                "expires_in": 3600,
            }

    def _post(url, json=None, timeout=None, headers=None):
        captured["url"] = url
        captured["body"] = json
        return _Response()

    monkeypatch.setattr(dulus_account, "requests", type("R", (), {"post": _post}), raising=False)
    monkeypatch.setitem(sys.modules, "requests", type("R", (), {"post": staticmethod(_post)}))

    assert dulus_account.access_token(notify=lambda _m: None) == "fresh"
    assert captured["body"]["grant_type"] == "refresh_token"
    # The server rotates refresh tokens; storing the new one is what keeps the
    # next refresh working.
    assert dulus_account.load_store()["refresh_token"] == "rotated"


def test_a_rejected_refresh_reports_signed_out_rather_than_a_stale_token(
    isolated_home, monkeypatch
) -> None:
    dulus_account.save_store(
        {
            "access_token": "stale",
            "refresh_token": "revoked",
            "expires_at": time.time() - 10,
        }
    )

    class _Response:
        status_code = 400

        @staticmethod
        def json() -> dict:
            return {"detail": "invalid_grant"}

    monkeypatch.setitem(
        sys.modules,
        "requests",
        type("R", (), {"post": staticmethod(lambda *a, **k: _Response())}),
    )

    # A replayed or revoked refresh token must force a real re-login instead
    # of silently reusing a token the server no longer honours.
    assert dulus_account.access_token(notify=lambda _m: None) == ""


def test_minting_a_key_requires_being_signed_in(isolated_home) -> None:
    messages: list[str] = []

    assert dulus_account.create_api_key(notify=messages.append) is None
    assert any("Sign in first" in m for m in messages)


def test_the_client_is_public_and_ships_no_secret() -> None:
    source = Path(dulus_account.__file__).read_text(encoding="utf-8")

    # A CLI cannot keep a secret, so PKCE is the only thing proving the code
    # is redeemed by the same program that requested it.
    assert "client_secret" not in source
    assert "code_challenge_method" in source
    assert '"S256"' in source or "'S256'" in source


def test_scopes_stay_neutral_in_the_public_client() -> None:
    source = Path(dulus_account.__file__).read_text(encoding="utf-8")

    # Scope names show up on consent screens and in every client's config, so
    # they must not carry internal billing vocabulary.
    assert "fuel" not in source.lower()
    assert "balance:read" in source
