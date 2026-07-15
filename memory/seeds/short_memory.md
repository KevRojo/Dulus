---
name: short_memory
description: Gold short memory — live scratchpad reloaded every 10 tool turns and at startup
type: project
hall: facts
gold: true
source: palace_init
---
# Short Memory (gold)

Updated: (seed) · Fill this on first real session.

## Hard rules
- Prefer local verification before any commit/push when the user asks.
- Speak in the user's language/style.
- Never push private product trees or secrets to public repos.

## Live paths (edit per machine)
| What | Path |
|---|---|
| CLI/REPL | `dulus` / `dulus.py` |
| Desktop GUI host | `dulus --gui` → pywebview |
| Runtime home | `~/.dulus/` (`DULUS_HOME`) |
| This file | `~/.dulus/memory/short_memory.md` |

## Working notes
- Keep this short and live: decisions, paths, corrections, active task.
- Prune stale lines. Gold = auto-loaded at every startup.
