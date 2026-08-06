---
name: Adaptation_Guides
description: When adapting external repos into plugins/tools — explicit schemas, safe defaults, no silent network calls
type: feedback
hall: advice
source: palace_init
---
# Adapting external code into tools/plugins

When you wrap an external Python repo (or any third-party code) into a tool or
plugin, prefer:

- **Explicit tool schemas** — declare inputs/outputs; don't rely on the caller guessing.
- **Safe defaults** — read-only, non-destructive, opt-in for anything with side effects.
- **No silent network calls** — a tool must not phone home or fetch remote code without it being obvious in its schema/name.

If the external code runs `exec`/`eval`, downloads and runs remote payloads, or
hides network I/O, treat it as unsafe until proven otherwise.
