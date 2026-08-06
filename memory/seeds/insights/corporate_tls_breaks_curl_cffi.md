---
name: corporate_tls_breaks_curl_cffi
description: Corporate TLS interception (Cloudflare WARP, Zscaler, MITM proxies) injects a self-signed cert that breaks libs with their own CA store — notably curl_cffi (yfinance). truststore does NOT fix curl_cffi.
type: reference
hall: discoveries
source: palace_init
---
# Corporate TLS interception breaks curl_cffi (and yfinance)

**Root cause:** TLS-intercepting layers — Cloudflare WARP, Zscaler, Netskope,
corporate MITM proxies — inject a self-signed root cert into the chain. Libraries
that ship their **own** CA bundle (notably `curl_cffi`, used by `yfinance` 1.5.x)
reject it with `SSLCertVerificationError: self signed certificate in certificate
chain`. `yfinance` then misreports the symbol as "possibly delisted".

**Key gotcha:** `truststore.inject_into_ssl()` fixes the stdlib `ssl` module and
`requests`, but **NOT** `curl_cffi` — it uses its own store, so truststore never
touches it.

**Fix options:**
- Set `verify=False` on the `curl_cffi` session (monkeypatch
  `curl_cffi.requests.Session.__init__` to `kwargs.setdefault("verify", False)`
  **before** `import yfinance`), or
- Install the corporate root CA into the system/library trust store.

**Tell-tale:** any HTTPS library suddenly failing cert verification on a machine
behind WARP/Zscaler — suspect TLS interception first, not the remote server.
