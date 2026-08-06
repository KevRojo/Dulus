---
name: native_code_over_sketchy_plugins
description: For security-critical work (Web3/crypto, anything touching keys/funds) prefer writing your own native code over installing sketchy third-party plugins
type: feedback
hall: advice
source: palace_init
---
# Prefer native code over sketchy third-party plugins

When the task is security-critical — Web3/crypto, signing, anything touching
keys, funds, or credentials — prefer **writing your own code against the base
libraries** (e.g. raw `web3.py` / `eth-account`) over installing a random
third-party plugin or wrapper from the internet.

**Why:** you keep full control and can audit exactly what runs. Third-party
plugins can hide `exec`/`eval`, phone home, or pull remote payloads — a real risk
when keys or money are involved.

**How to apply:** if a plugin/skill fails a security smell test (obfuscation,
`exec`/`eval`, silent network calls, unnecessary bloat), discard it and build the
solution from the trusted base libraries instead.
