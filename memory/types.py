"""Memory type and hall taxonomy with system-prompt guidance text.

Four types capture context NOT derivable from the current project state.
Code patterns, architecture, git history, and file structure are derivable
(via grep/git/CLAUDE.md) and should NOT be saved as memories.

Halls categorize memories by their nature (orthogonal to type):
  facts, events, discoveries, preferences, advice.
"""

MEMORY_TYPES = ["user", "feedback", "project", "reference"]

# Halls categorize HOW information should be used, while types
# categorize WHAT the information is about.
MEMORY_HALLS = ["soul", "facts", "events", "discoveries", "preferences", "advice"]

MEMORY_HALL_DESCRIPTIONS: dict[str, str] = {
    "soul": "Identity, core relationship, and 'spirit' of the agent.",
    "facts": "Decisions locked in, choices made, truths established.",
    "events": "Sessions, milestones, debugging breakthroughs, timeline entries.",
    "discoveries": "New insights, breakthroughs, non-obvious findings.",
    "preferences": "Habits, likes, opinions, working-style choices.",
    "advice": "Recommendations, solutions, guidance for future reference.",
}

# Condensed per-type guidance (used in system prompt injection)
MEMORY_TYPE_DESCRIPTIONS: dict[str, str] = {
    "user": (
        "Information about the user's role, goals, responsibilities, and knowledge. "
        "Helps tailor future behavior to the user's preferences."
    ),
    "feedback": (
        "Guidance the user has given about how to approach work — both what to avoid "
        "and what to keep doing. Lead with the rule, then **Why:** and **How to apply:**."
    ),
    "project": (
        "Ongoing work, goals, bugs, or incidents not derivable from code or git history. "
        "Lead with the fact/decision, then **Why:** and **How to apply:**. "
        "Always convert relative dates to absolute dates."
    ),
    "reference": (
        "Pointers to external systems (issue trackers, dashboards, Slack channels, docs)."
    ),
}

# What NOT to save (mirrors Claude Code source)
WHAT_NOT_TO_SAVE = """\
## What NOT to save in memory
- Code patterns, conventions, architecture, file paths, or project structure — derivable from the codebase.
- Git history, recent changes, who-changed-what — use `git log` / `git blame`.
- Debugging solutions or fix recipes — the fix is in the code; the commit message has context.
- Anything already documented in CLAUDE.md files.
- Ephemeral task details: in-progress work, temporary state, current conversation context.

These exclusions apply even when explicitly asked. If asked to save a PR list or activity summary,
ask what was *surprising* or *non-obvious* — that is the part worth keeping."""

# Memory format example (frontmatter)
MEMORY_FORMAT_EXAMPLE = """\
```markdown
---
name: {{memory name}}
description: {{one-line description — used to decide relevance, so be specific}}
type: {{user | feedback | project | reference}}
---

{{memory content — for feedback/project types: rule/fact, then **Why:** and **How to apply:** lines}}
```"""

# Full guidance injected into the system prompt
MEMORY_SYSTEM_PROMPT = """\
## Memory system

You have a persistent, file-based memory system. Memories are stored as markdown files with
YAML frontmatter. Build this up over time so future conversations have context about the user,
their preferences, and the work you're doing together.

**Types** (save only what cannot be derived from the codebase):
- **user** — role, goals, knowledge, preferences
- **feedback** — guidance on how to work (corrections AND confirmations of non-obvious approaches)
- **project** — ongoing work, decisions, deadlines not in git history
- **reference** — pointers to external systems (Linear, Grafana, Slack, etc.)

**Halls** (categorize HOW the memory should be used):
- **soul** — identity, core relationship, and 'spirit' of the agent (Sacred)
- **facts** — decisions locked in, choices made, truths established
- **events** — sessions, milestones, debugging breakthroughs, timeline entries
- **discoveries** — new insights, breakthroughs, non-obvious findings
- **preferences** — habits, likes, opinions, working-style choices
- **advice** — recommendations, solutions, guidance for future reference

Halls are orthogonal to types. Example: a "feedback" memory about "always use black for formatting"
would go in the "preferences" hall. A "project" memory about "migrated auth to Clerk on 2026-03"
would go in the "events" hall. If unsure, omit the hall — it's optional.

**When to save**: If the user corrects you, confirms an approach, or shares context that should
persist beyond this conversation. For feedback: save corrections AND quiet confirmations.

**Body structure for feedback/project**: Lead with the rule/fact, then:
  **Why:** (reason given) | **How to apply:** (when this guidance kicks in)

**Format**:
{format_example}

**Saving is two steps**:
1. Write the memory to its own file (e.g. `feedback_testing.md`) using MemorySave.
2. The index (MEMORY.md) is updated automatically.

**What NOT to save**: code patterns, architecture, git history, debugging fixes,
anything already in CLAUDE.md, or ephemeral task state.

**Before recommending from memory**: A memory naming a file, function, or flag may be stale.
Verify it still exists before acting on it. For current state, prefer `git log` or reading code.
""".format(format_example=MEMORY_FORMAT_EXAMPLE)
