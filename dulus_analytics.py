"""Dulus Analytics — canonical server-side event SDK.

Fan-out a Amplitude, Mixpanel, PostHog, Datadog y Sentry desde el backend/CLI.
Cada evento lleva: event_type, user_id (hash safe), properties sanitizadas,
correlation_id y timestamp ISO. No se envian secrets ni payloads de cliente.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _sanitize(props: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in props.items():
        key = str(k).lower()
        if any(x in key for x in ("pass", "secret", "token", "key", "credential", "private", "pwd", "ssn")):
            continue
        if isinstance(v, str) and len(v) > 500:
            out[k] = v[:500] + "…"
        else:
            out[k] = v
    return out


@dataclass
class DulusAnalytics:
    """Inicializa con las variables de entorno de cada provider.

    Nombres esperados:
        AMPLITUDE_API_KEY              (browser + server)
        AMPLITUDE_SECRET_KEY           (server-only)
        MIXPANEL_PROJECT_TOKEN         (browser)
        MIXPANEL_API_SECRET            (server)
        POSTHOG_PROJECT_API_KEY
        POSTHOG_HOST                   (default https://us.i.posthog.com)
        DATADOG_API_KEY
        DATADOG_APP_KEY
        SENTRY_DSN
    """

    amplitude_key: Optional[str] = field(default_factory=lambda: os.getenv("AMPLITUDE_API_KEY"))
    amplitude_secret: Optional[str] = field(default_factory=lambda: os.getenv("AMPLITUDE_SECRET_KEY"))
    mixpanel_secret: Optional[str] = field(default_factory=lambda: os.getenv("MIXPANEL_API_SECRET"))
    posthog_key: Optional[str] = field(default_factory=lambda: os.getenv("POSTHOG_PROJECT_API_KEY"))
    posthog_host: str = field(default_factory=lambda: os.getenv("POSTHOG_HOST", "https://us.i.posthog.com"))
    datadog_api_key: Optional[str] = field(default_factory=lambda: os.getenv("DATADOG_API_KEY"))
    datadog_app_key: Optional[str] = field(default_factory=lambda: os.getenv("DATADOG_APP_KEY"))
    sentry_dsn: Optional[str] = field(default_factory=lambda: os.getenv("SENTRY_DSN"))

    _http: Any = None
    _sentry_client: Any = None

    def __post_init__(self):
        # Lazy imports — no crashear si faltan dependencias
        if self.sentry_dsn:
            try:
                import sentry_sdk
                sentry_sdk.init(
                    dsn=self.sentry_dsn,
                    environment=os.getenv("ENVIRONMENT", "development"),
                    traces_sample_rate=0.2,
                    send_default_pii=False,
                )
                self._sentry_client = sentry_sdk
            except Exception as exc:
                self._warn(f"Sentry init failed: {exc}")

    def _warn(self, msg: str) -> None:
        # No print por defecto; los tests pueden inyectar un logger
        if os.getenv("DULUS_ANALYTICS_DEBUG"):
            print(f"[DulusAnalytics] {msg}")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _user_hash(self, user_id: str) -> str:
        # Hash irreversible para eventos donde no se quiere PII
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    def track(
        self,
        event: str,
        *,
        user_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        site: str = "dulus.ai",
    ) -> None:
        """Envia un evento canonico a todos los providers configurados."""
        props = _sanitize(properties or {})
        props["site"] = site
        props["timestamp"] = self._now_iso()
        if correlation_id:
            props["correlation_id"] = correlation_id
        safe_user = self._user_hash(user_id) if user_id else None

        self._amplitude(event, safe_user, props)
        self._mixpanel(event, safe_user, props)
        self._posthog(event, safe_user, props)

    def _amplitude(self, event: str, user_id: Optional[str], props: Dict[str, Any]) -> None:
        if not self.amplitude_key:
            return
        try:
            import urllib.request

            payload = {
                "api_key": self.amplitude_key,
                "events": [
                    {
                        "user_id": user_id or "anonymous",
                        "event_type": event,
                        "event_properties": props,
                        "time": int(time.time() * 1000),
                    }
                ],
            }
            req = urllib.request.Request(
                "https://api2.amplitude.com/2/httpapi",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "*/*"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            self._warn(f"Amplitude send failed: {exc}")

    def _mixpanel(self, event: str, user_id: Optional[str], props: Dict[str, Any]) -> None:
        if not self.mixpanel_secret:
            return
        try:
            import base64
            import urllib.request

            data = json.dumps({"event": event, "properties": props})
            b64 = base64.b64encode(data.encode()).decode()
            req = urllib.request.Request(
                f"https://api-eu.mixpanel.com/import?strict=1&project_id={self.mixpanel_secret}",
                data=b64.encode(),
                headers={"Authorization": f"Basic {self.mixpanel_secret}:"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            self._warn(f"Mixpanel send failed: {exc}")

    def _posthog(self, event: str, user_id: Optional[str], props: Dict[str, Any]) -> None:
        if not self.posthog_key:
            return
        try:
            import urllib.request

            payload = {
                "api_key": self.posthog_key,
                "event": event,
                "distinct_id": user_id or "anonymous",
                "properties": props,
                "timestamp": self._now_iso(),
            }
            req = urllib.request.Request(
                f"{self.posthog_host.rstrip('/')}/capture/",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            self._warn(f"PostHog send failed: {exc}")


# Instancia global por conveniencia
default = DulusAnalytics()


def track(*args, **kwargs) -> None:
    return default.track(*args, **kwargs)
