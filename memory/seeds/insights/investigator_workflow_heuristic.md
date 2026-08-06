---
name: investigator_workflow_heuristic
description: Investigator workflow — scope, collect read-only, correlate across sources, report; question your own assumptions
type: feedback
hall: advice
source: palace_init
---
# Investigator / analyst workflow

When asked to diagnose, audit, or figure something out, follow this order:

1. **Scope** — define exactly what is being investigated before touching anything.
2. **Collect** — read-only tools first (Grep, Glob, `git log`, memory search). Don't mutate while you're still learning.
3. **Correlate** — cross-reference multiple sources before concluding. One signal is a hint, not a finding.
4. **Report** — state findings clearly, separating what you verified from what you inferred.

**Principles:** keep a chain of custody (note each step you took), and question
your **own** assumptions first — the most expensive bugs come from trusting a
premise you never checked.
