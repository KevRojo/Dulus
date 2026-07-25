"""Grok Build remaining-usage probe (toolbar + OAuth billing path)."""
from __future__ import annotations

import time

import providers


def _credits_payload(usage_pct=33.0, prepaid_cents=0):
    return {
        "config": {
            "currentPeriod": {
                "type": "USAGE_PERIOD_TYPE_WEEKLY",
                "start": "2026-07-22T06:26:22.071202+00:00",
                "end": "2026-07-29T06:26:22.071202+00:00",
            },
            "creditUsagePercent": usage_pct,
            "onDemandCap": {"val": 0},
            "onDemandUsed": {"val": 0},
            "productUsage": [
                {"product": "Api", "usagePercent": usage_pct},
                {"product": "GrokBuild"},
            ],
            "isUnifiedBillingUser": True,
            "prepaidBalance": {"val": prepaid_cents},
            "billingPeriodStart": "2026-07-22T06:26:22.071202+00:00",
            "billingPeriodEnd": "2026-07-29T06:26:22.071202+00:00",
        }
    }


def _legacy_payload(limit_cents=20000, used_cents=11263):
    return {
        "config": {
            "monthlyLimit": {"val": limit_cents},
            "used": {"val": used_cents},
            "onDemandCap": {"val": 0},
            "billingPeriodStart": "2026-07-01T00:00:00+00:00",
            "billingPeriodEnd": "2026-08-01T00:00:00+00:00",
            "history": [],
        }
    }


def test_is_grok_model_detects_common_ids():
    assert providers.is_grok_model("grok-4")
    assert providers.is_grok_model("grok-3")
    assert providers.is_grok_model("xai/grok-2-latest")
    assert providers.is_grok_model("xai-oauth/grok-4")
    assert providers.is_grok_model("GROK-BUILD")
    assert not providers.is_grok_model("claude-sonnet-4-6")
    assert not providers.is_grok_model("gpt-4o")
    assert not providers.is_grok_model("")
    assert not providers.is_grok_model(None)


def test_parse_grok_billing_payloads_percent_and_usd():
    snap = providers._parse_grok_billing_payloads(
        _credits_payload(33.0),
        _legacy_payload(20000, 11263),
    )
    assert snap["provider"] == "grok"
    assert snap["usage_percent"] == 33.0
    assert snap["remaining_percent"] == 67.0
    assert snap["limit_usd"] == 200.0
    assert snap["used_usd"] == 112.63
    assert abs(snap["remaining_usd"] - 87.37) < 0.001
    assert snap["prepaid_usd"] == 0.0
    assert snap["status"] == "ok"
    assert snap["period_type"] == "USAGE_PERIOD_TYPE_WEEKLY"


def test_parse_status_low_and_exhausted():
    low = providers._parse_grok_billing_payloads(_credits_payload(85.0), None)
    assert low["remaining_percent"] == 15.0
    assert low["status"] == "low"

    dead = providers._parse_grok_billing_payloads(_credits_payload(100.0), None)
    assert dead["remaining_percent"] == 0.0
    assert dead["status"] == "exhausted"


def test_format_grok_usage_toolbar_prefers_percent():
    snap = providers._parse_grok_billing_payloads(
        _credits_payload(33.0),
        _legacy_payload(),
    )
    assert providers.format_grok_usage_toolbar(snap) == "💳 67% left"
    assert providers.format_grok_usage_toolbar(None) == ""


def test_peek_toolbar_empty_for_non_grok(monkeypatch):
    providers.reset_grok_usage_cache()
    monkeypatch.setattr(
        providers,
        "get_grok_usage_snapshot",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )
    assert providers.peek_grok_usage_toolbar({"model": "claude-sonnet-4-6"}) == ""


def test_peek_toolbar_uses_cache_for_grok(monkeypatch):
    providers.reset_grok_usage_cache()
    snap = providers._parse_grok_billing_payloads(_credits_payload(40.0), None)
    # Pre-seed cache as if a prior refresh already completed.
    with providers._grok_usage_lock():
        providers._GROK_USAGE_CACHE["snapshot"] = snap
        providers._GROK_USAGE_CACHE["fetched_at"] = time.time()
        providers._GROK_USAGE_CACHE["error"] = None

    label = providers.peek_grok_usage_toolbar({"model": "grok-4"})
    assert label == "💳 60% left"


def test_get_snapshot_background_refresh_does_not_block(monkeypatch):
    providers.reset_grok_usage_cache()
    called = {"n": 0}

    def fake_fetch(config=None, timeout=12.0):
        called["n"] += 1
        # Simulate slow network — if wait=False path blocked, test would hang.
        time.sleep(0.05)
        return providers._parse_grok_billing_payloads(_credits_payload(10.0), None)

    monkeypatch.setattr(providers, "fetch_grok_billing", fake_fetch)
    # First peek: no cache yet → returns None immediately, kicks bg thread
    first = providers.get_grok_usage_snapshot({}, force=False, wait=False)
    assert first is None
    # Wait for bg thread
    deadline = time.time() + 2.0
    snap = None
    while time.time() < deadline:
        snap = providers.get_grok_usage_snapshot({}, force=False, wait=False)
        if snap is not None:
            break
        time.sleep(0.02)
    assert snap is not None
    assert snap["remaining_percent"] == 90.0
    assert called["n"] >= 1


def test_fetch_grok_billing_uses_proxy_urls(monkeypatch):
    providers.reset_grok_usage_cache()
    hits: list[str] = []

    class FakeResp:
        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status
            self.text = str(payload)

        def json(self):
            return self._payload

    def fake_get(url, headers=None, timeout=12.0):
        hits.append(url)
        if "format=credits" in url:
            return FakeResp(_credits_payload(33.0))
        return FakeResp(_legacy_payload())

    monkeypatch.setattr(providers, "_xai_oauth_get_token", lambda cfg: "tok-test")
    monkeypatch.setattr(providers.requests, "get", fake_get)

    snap = providers.fetch_grok_billing({})
    assert any("cli-chat-proxy.grok.com/v1/billing?format=credits" in u for u in hits)
    assert any(u.endswith("/billing") and "format=" not in u for u in hits)
    assert snap["remaining_percent"] == 67.0
    assert abs(snap["remaining_usd"] - 87.37) < 0.001


def test_fetch_requires_token(monkeypatch):
    monkeypatch.setattr(providers, "_xai_oauth_get_token", lambda cfg: "")
    try:
        providers.fetch_grok_billing({})
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "OAuth" in str(e) or "login" in str(e).lower()
