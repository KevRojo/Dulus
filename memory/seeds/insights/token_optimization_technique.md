---
name: token_optimization_technique
description: Never load a huge tool output whole — search/filter for what you need first, then process and report only the summary
type: technique
hall: behavior
source: palace_init
---
# Filter big outputs, don't swallow them

When a tool returns a large output (thousands of lines, a big JSON blob, a long
scan result), **never** load the whole thing into context. Instead:

1. **Search/filter first** — grep or a search-in-last-output tool for the keyword
   that actually matters (e.g. only the `claimed` entries, only the errors).
2. **Process** the filtered subset.
3. **Report** a summary, not the raw dump.

**Why:** loading full outputs wastes 90–95% of the context on noise you'll never
use, and it crowds out the reasoning you actually need. Search first, process
after, report only what matters.
