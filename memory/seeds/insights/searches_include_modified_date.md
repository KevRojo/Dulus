---
name: searches_include_modified_date
description: When hunting for the right copy/version among duplicates, ALWAYS sort by modified date — the most recent is usually the most advanced
type: feedback
hall: advice
source: palace_init
---
# Always include modified date when searching for "the right copy"

When you search for files, duplicate project folders, or "which copy is the good
one" across workspaces, **always include and sort by the modified date** — don't
run a bare listing that shows only names.

**How:**
- PowerShell: `Get-ChildItem -Recurse | Sort-Object LastWriteTime -Descending | Select FullName, LastWriteTime`
- Unix: `ls -lt` / `find . -printf '%T@ %p\n' | sort -rn`

**Why:** when the same project exists in several folders at different stages, the
name tells you nothing — the **modification time** is what reveals which copy is
the most advanced (the real source). Guessing by name/path burns time and picks
the wrong one.
