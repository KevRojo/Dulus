# Bundled Agent Skills

Curated third-party Agent Skills shipped with Dulus so they're available
out of the box. Each `<name>/SKILL.md` follows the [Agent Skills
specification](https://agentskills.io/specification) and is loaded by
`skill.loader.load_skills()` as `source="bundled"` — the lowest priority
tier, so you can shadow any of them by dropping your own `SKILL.md` with
the same name under `~/.dulus/skills/<name>/` (user-level) or
`./.dulus-context/skills/<name>/` (project-level).

## Currently bundled

### [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)
Steph Ango's (@kepano) Obsidian-focused skill bundle. MIT licensed —
see [LICENSE-obsidian-skills](LICENSE-obsidian-skills).

| Skill | What it does |
| --- | --- |
| `defuddle` | Extract clean Markdown from web pages |
| `json-canvas` | Author `.canvas` files (Obsidian / JSON Canvas spec) |
| `obsidian-bases` | Edit Obsidian Bases (`.base` files) with views, filters, formulas |
| `obsidian-cli` | Operate Obsidian vaults via the Obsidian CLI |
| `obsidian-markdown` | Write Obsidian Flavored Markdown (wikilinks, embeds, callouts, properties) |

> The Obsidian skills make Dulus's MemPalace notes Obsidian-friendly
> by default — wiki-links resolve, the graph view connects related
> memories, callouts render. Open `~/.dulus/memory/` as an Obsidian
> vault to see the visualisation.

### [NousResearch/hermes-agent — unbroker](https://github.com/NousResearch/hermes-agent/tree/main/optional-skills/security/unbroker)
Data-broker removal skill by [SHL0MS](https://github.com/SHL0MS). MIT licensed
(engine); broker dataset adapted from
[BADBOOL](https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List) by
Yael Grauer (CC BY-NC-SA 4.0).

| Skill | What it does |
| --- | --- |
| `unbroker` | Find and remove a consenting person's exposed PII from data brokers / people-search sites (CCPA/GDPR opt-outs, ledger, re-scans). Consent-gated, US-first. |

Seasoned for Dulus: `HERMES_HOME` → `DULUS_HOME` (default `~/.dulus`), Hermes
tool names mapped to Dulus natives (`web_extract`→`WebFetch`,
`browser_*`→`WebBridge*`, `delegate_task`→`Agent`, `cronjob`→`Reminder`).
The deterministic engine (`scripts/pdd.py`, stdlib-only) is unmodified.
Try it: *"Use the unbroker skill to remove my data from data brokers."*

## How to shadow a bundled skill

Drop a file with the SAME `name:` in the frontmatter:

```
~/.dulus/skills/obsidian-markdown/SKILL.md     # user override
./.dulus-context/skills/obsidian-markdown/SKILL.md   # project override
```

Project-level wins over user-level wins over bundled. The bundled
copy stays on disk untouched.
