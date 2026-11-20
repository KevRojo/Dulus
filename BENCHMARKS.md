# The benchmark

**Measured. Not claimed. And corrected when it was wrong.**

The Dulus Benchmark Arena replays six synthetic coding sessions, from an 8-turn fix to a 120-turn audit, through Dulus, six other agent harnesses and a naive control. Every harness gets byte-identical transcripts, one tokenizer and one price table. Dulus runs its own context code, in the order the app runs it. The other six are modelled from how each one manages its context (grow, slide a window, or summarise at a threshold), not run from their source.

Run of November 16, 2026 · arena 1.0.0 · five sessions on Claude Sonnet 4.6 with its 1M-token window, one on DeepSeek with 64k.
**→ [The full results on dulus.ai](https://dulus.ai/benchmarks/)** · **[The dossier (PDF, 29 pages)](https://dulus.ai/assets/docs/dulus-benchmark-dossier.pdf)**

---

## What holds

**Dulus never ran out of room.** It is the only harness in the field that never sent a prompt bigger than the model's window. Its largest was 698,407 tokens of a million. Claude Code, Codex CLI, Cursor and Cline each overflowed once, GitHub Copilot 26 times, Aider and the naive loop 135 times.

**It ranks first under four of five weightings.** The arena re-scores everyone under five published profiles. Dulus places first under neutral, fidelity-first, capability-first and the arena's default. Cost-first puts Cline first and Dulus fifth (see below).

**It costs the least once sessions pause.** Dulus keeps its prompt cache for an hour; the others are modelled with the five-minute default. From about one turn in eleven coming back after a pause longer than five minutes, Dulus is the cheapest harness in the arena:

| Turns after a pause | Dulus | Cline, the cheapest other | Claude Code |
|---|---:|---:|---:|
| 26 of 288 (one in eleven) | **$72.19** | $79.53 | $88.91 |
| 71 of 288 (one in four) | **$72.19** | $127.94 | $142.94 |

## What doesn't

**On sessions that never pause, four harnesses cost less than Dulus.** This is the arena's headline run, and the case most favourable to a five-minute cache:

| Harness | All six sessions, no pauses | Context overflows |
|---|---:|---:|
| Cline | $53.83 | 1 |
| Cursor | $57.42 | 1 |
| Codex CLI | $58.73 | 1 |
| Claude Code | $58.88 | 1 |
| **Dulus** | **$72.19** | **0** |
| Aider | $97.68 | 135 |
| GitHub Copilot (agent mode) | $234.70 | 26 |
| Naive loop (the control) | $723.32 | 135 |

Almost all of the gap is the one-hour cache. Writing to it costs twice the input price, against 1.25× for five minutes, and a session that never pauses never gets anything back for it. Head to head, Dulus is cheaper in 19 of the 42 scenario-by-harness matchups and dearer in 23.

**The window changes the order.** At a 200k window instead of 1M, with no pauses, Claude Code is the cheapest at $48.25 and Dulus costs $51.17.

## Why pauses decide it

A provider bills the cached part of a prompt at a tenth of the price, but only for as long as it was asked to keep it. Step away to read a diff, run the tests or think, and a five-minute cache is gone: the next request writes the whole prompt again. Dulus asks for an hour. It pays more for every write, and in exchange a coffee break doesn't cost it the cache.

How often real sessions pause is the one number this benchmark does not have. Our own account, building with Dulus, served 91.9% of 1.78 billion input tokens from the cache in the first half of November. That is a different instrument from the arena, and it is one account.

## Corrected on November 16, 2026

The first edition, published October 18, said Dulus cost $25.63 against $48.00 for Claude Code, cheaper in all 42 matchups and first under every weighting. Running the arena again turned up five errors in the instrument, every one in Dulus's favour:

1. **Cache writes were free.** New content went from full price straight to the cached price, never paying to be written.
2. **Dulus was priced at the wrong cache.** It ships the one-hour cache and was billed at the five-minute rate.
3. **Dulus trimmed on every turn.** The app trims and compacts only past 70% of the window, and it was simulated trimming from the first turn.
4. **Those trims were invisible.** They rewrote messages already sent, and the simulator kept reading them from the cache.
5. **One extreme row flattened the costs.** Scored on a min-max scale, the naive control squeezed every real cost difference into the last hundredths.

Each fix landed with a test that fails without it, and each was broken on purpose to prove a test catches it. Claude's window had also grown from 200k to 1M between the two runs, and nothing in the old report said which window it used; every report now does. The capability record also listed some things only the private source tree runs; it now describes the app you download.

## What this benchmark does not measure

- **Output quality.** It measures what a session costs and what the model can still see, not whether the code it writes is good.
- **The competitors' real code.** Their rows are models of a strategy, with weaker evidence behind them (37–44% evidence quality, against 89% for Dulus).
- **Real sessions.** The six sessions are synthetic, shaped like real agent work but not sampled from it.

<sub>Built and re-run by the agents that work on Dulus, and read by [an audit](AUDIT.md).</sub>
