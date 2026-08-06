---
name: tool_chaining_capability
description: You can chain several tools in a single turn without waiting for the user between them
type: technique
hall: behavior
source: palace_init
---
# Chain tools in one turn

You can run multiple tools in sequence within a single turn without stopping for
the user between them. Example: `WebFetch` (get a list) immediately followed by
`AskUserQuestion` (ask which item) in the same pass — the user answers once and
the whole workflow completes.

**Why:** it maximizes throughput and cuts conversation turns. Don't artificially
split a multi-step action into several turns "to be safe" when the steps are
independent or the dependencies are known.

Corollary: when calls are independent, fire them **in parallel** in one turn
rather than one-at-a-time.
