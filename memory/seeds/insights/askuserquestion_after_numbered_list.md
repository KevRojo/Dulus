---
name: askuserquestion_after_numbered_list
description: When showing a numbered list of options, use AskUserQuestion with those options instead of waiting for a free-text reply
type: feedback
hall: advice
source: palace_init
---
# Rule: AskUserQuestion after a numbered list

When you present a numbered list the user is meant to pick from (top-10, choices,
candidate approaches, files to open…), **immediately** call `AskUserQuestion`
with those items as `options` — don't print the list and then wait for the user
to type "the 3rd one".

**Why:** it saves a whole conversation turn and the user clicks instead of
typing. Free-text "which one?" is slower and ambiguous.

**Correct:**
1. gather the options
2. `AskUserQuestion(question="Which one?", options=[{"label": "1. …"}, {"label": "2. …"}, …])`

**Wrong:** print a table → "which do you want?" → wait for the user to type it.
