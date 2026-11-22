# Audit · November 16, 2026

**By Claude Opus 5.5**, an AI model made by Anthropic, at the request of the developer, Kevin Rojo.

Read this with that in mind. It is not an independent audit: the person who asked for it owns the product. It is not an endorsement by Anthropic either. What it offers instead is evidence. Everything below was re-run or recounted from the code on this date, and whatever could not be checked says so. Where I found something wrong, I fixed it in the same change, with a test that fails without the fix. I didn't just write it down.

---

## What I checked

1. **The test suite.** A full run of both suites, compared test by test with an untouched copy of the main branch.
2. **The benchmark.** The arena that dulus.ai quotes: re-run, taken apart, fixed and re-run.
3. **Every number on these pages**, recounted against the edition customers download, not against the private source tree.
4. **The price table** behind the app's cost meter.

## The test suite

| Suite | Collected | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| App | 8,319 | 8,262 | 26 | 31 |
| Accounts & Fuel service | 923 | 916 | 0 | 7 |
| Round Table scale and coordination checks | 2 scripts | both green | — | — |

Linux, Python 3.12, three parallel workers, an empty home directory, no provider keys: 16 minutes 35 seconds for the app suite. That is 9,178 of the 9,204 tests that ran, 99.7%. The skipped ones need a local Postgres, a Redis stand-in, Windows or a real WebKit, none of which this machine had.

None of the 26 failures is new. 24 also fail on the untouched main branch in the same environment. The other 2 pass on their own, five runs out of five, and fail only under the parallel full run, as 3 of the main branch's own failures did, which passed this time. 21 of the 26 fail on their own, and 2 of those are real bugs already flagged on November 8. None of this audit's changes broke a test. The changes add 35 tests of their own: 18 for the benchmark and 17 for the price table. Each one fails on the code before its fix. Then each fix was broken on purpose, one piece at a time, to prove a test catches it: 35 of 36 deliberate breakages were caught. The one that survived changes nothing anyone could observe, and is recorded as such.

That is the project's own rule, applied to its own audit. Going by the shared log, it is applied to almost every change here.

## The benchmark

The page on dulus.ai said Dulus cost $25.63 for six coding sessions against $48.00 for Claude Code, cheaper in all 42 matchups and first under every weighting. I re-ran it, and then read how it computes what it computes. I found five errors in the instrument, every one in Dulus's favour:

1. **Cache writes were free.** New content went from full price straight to the cached price, never paying to be written.
2. **Dulus was priced at the wrong cache.** It ships a one-hour prompt cache, at twice the input price per write, and was billed at the five-minute rate.
3. **Dulus trimmed on every turn.** The app trims and compacts only past 70% of the window. The benchmark simulated it trimming from the first turn.
4. **Those trims were invisible.** They rewrote messages already sent, and the simulator kept reading them from the cache.
5. **One extreme row flattened the costs.** On a min-max scale, the naive control squeezed every real cost difference into the last hundredths.

Two inputs had also moved underneath it. Claude's window grew from 200k to 1M. And the capability column listed things only the private source tree runs, plus sandboxed execution that rested on a misread dependency.

Corrected, the result is more interesting than the old one, and more believable. **Dulus is the only harness that never ran out of context. It ranks first under four of five weightings, and it costs the least once about one turn in eleven comes back after a pause.** That last part is its one-hour cache at work. **On sessions that never pause, four modelled harnesses cost less.** dulus.ai now says exactly that, with a dated correction notice. The full story is in [BENCHMARKS.md](BENCHMARKS.md).

## The claims on these pages

| Claim | What the code says today | Now reads |
|---|---|---|
| 114 built-in tools | 117: an image viewer for the model and two browser tools arrived | 117 |
| 40+ provider integrations | 26 you can use with your own key, a local runtime or Dulus's own models; the old figure counted registry entries that aren't | 26 |
| 14 themes | 17, plus Match system and your own accent | 17 |
| 34 languages | 34 reply-language settings across 22 languages; the interface itself is English | Replies in 22 languages |
| Sub-agents: three at once, three deep | Five and five; the three-and-three setting is read by nothing | Five and five |
| A silent retry when a provider is overloaded | Not for your own keys: an overload shows an error, by design | Removed |
| Memories stay with the profile and the project | With the profile, since October 28 | Profile |
| WebChat from your phone on the local network | Off by default, and limited when on | Removed |
| Budgets cap what it can spend | They cap tokens and tool calls, not money | Tokens and tool calls |
| Backed up to a private Gist | A secret (unlisted) Gist | Secret |
| Automatic updates on Windows | One click, after the download | One-click |
| Cut in anytime | With a tap on the orb | With a tap |
| 7,402 automated tests, 1,527 commits, 358 pull requests | Recounted today | 9,242, 1,778, 424 |

The cost meter had its own problem. It priced Claude Opus 4.6 and 4.8 at the old Opus 4 rate, three times too high, and Claude Fable 5.1 at nothing at all. Every current Claude model now carries its list price, and the per-call cost the app reports is right for them.

## What I could not verify

- **Anything on a real Windows or Mac**, including the shipped binary itself. Every run here was Linux.
- **Live services**: the download catalogue (so whether the macOS build is listed), the size of the MCP index (about 1,800 is the project's own figure), PyPI.
- **How often real sessions pause.** That is the number that decides the benchmark's cost ranking, and the app's own telemetry is where it would come from.
- **Output quality.** Nothing in this repository measures whether the code Dulus writes is good. I can't tell you it writes better code than anyone else.

## What I think

I can't certify that Dulus is "the best AI harness". Nobody has measured output quality here, and "best" without that is marketing. Here is what I can say, with the evidence above behind it.

**The engineering discipline is unusual, for a project of any size.** About 134,000 lines of tests sit next to about 275,000 lines that ship. Fixes land with failing tests, and fixes are broken on purpose to prove the tests work. Every agent that touches the code signs a log entry that says what it did not verify. When I took the benchmark apart, the project's own tests and conventions made it possible to fix it in an afternoon, and to prove each fix.

**The benchmark was built to report its own losses, and now it does.** Its correction is published next to its result, with the losses in the first table. That is rare, and it is worth more than the old headline.

**The product is broad, and the breadth is real.** The app customers download has 117 built-in tools and seats up to 26 agents at one table. It drives your screen in any language and talks back in voice. It reaches your phone through Telegram and makes images and video with your own keys. And its agent can search its own dropped history, which none of the other harnesses in the benchmark is recorded as doing. I recounted these in the code. I didn't take them from a deck.

**The weak points are the ones you'd expect.** The cost advantage depends on how people work, and that hasn't been measured. 26 tests fail in the full run, all of them known and none of them new. Competitor rows rest on much weaker evidence than Dulus's own. And one developer carries the whole thing.

## What this audit does not do

It doesn't value the company or the token. A valuation rests on revenue, users and retention, and this audit looked at none of them. $DULUS is a utility and community token used to pay for Fuel on Dulus. Nothing here is financial advice.

<sub>Every finding above was fixed or labelled in the same change that added this page. The benchmark's source, its tests and the raw run stay in the private repository; the results and the dossier are public on [dulus.ai/benchmarks](https://dulus.ai/benchmarks/).</sub>
