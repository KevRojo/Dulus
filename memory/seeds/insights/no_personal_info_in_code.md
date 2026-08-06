---
name: no_personal_info_in_code
description: Never write the user's personal info (name, home/desktop paths, folder names) into code, docstrings, tool schemas, or examples — use placeholders
type: feedback
hall: advice
source: palace_init
---
# Rule: no personal info in code

**Never** embed the user's personal identifiers — full name, home-directory
paths, OneDrive/Desktop folder names, machine-specific paths — inside code
comments, docstrings, tool schemas, examples, or any source artifact.

**Why:** these artifacts get committed, shipped, and read by others. A real path
or name leaking into a docstring example is a privacy and professionalism leak.

**How to apply:** use neutral placeholders — `C:\Users\<user>\...`,
`path/to/folder`, `example-folder`, `~/project`. If a tool needs to demonstrate
path handling, use a generic example, never a path pulled from the live
environment.
