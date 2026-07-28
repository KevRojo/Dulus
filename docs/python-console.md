# The model's second brain: a live Python heap that costs no tokens 🧠

After the [Lookback](news.md) write-up, people kept asking what's next on the token diet. This is it — and it's my favorite kind of win. Not a cheaper model. Not a smaller prompt. Just a different *place to put the data*.

Fair warning, same as last time: **i cannot stop saving tokens** askjdhsajkdha. This is another one.

## The bleed, again

If you read the lookback piece you already know the song: every turn, your agent re-sends its *entire* context to the API. Now watch what happens when the agent explores your disk. It runs a recursive scan. A hundred thousand file paths come back. That dump lands in the conversation — and from that moment, you re-send a hundred thousand paths **every single turn** for the rest of the session.

You're not paying to search once. You're paying to re-read the search forever.

The usual answer is "truncate the output." But truncation just means the agent *loses* the data and has to scan **again** the next time it needs it. Re-scan or re-send — pick your bill. Both are the wrong bill.

## The idea: give the model somewhere to *keep* things

What if the agent had memory that wasn't the conversation?

A live Python console whose variables **persist between calls**. Scan once into a variable — it stays alive. Next turn, filter it. The turn after, aggregate it. The data never re-enters the chat. It lives in the interpreter's heap, off to the side, and the model only ever prints the small slice it actually needs.

<p align="center">
  <img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/readme/pyc_heap.svg" alt="Working memory off-context: the data lives in the kernel heap, only a slice reaches the model" width="100%">
</p>

Full honesty on where this came from: it started as *one line* — "imagine the model had a live Python console, searching recursively." I went and built it the same day.

## Why this is a token trick, not a convenience

Every other "code interpreter" tool runs one-shot: send code, get output, output goes into the context, done. The output *is* the product — and the output costs tokens, forever, every replayed turn.

The persistent kernel flips it. The **data** is the product, and the data never touches the context. You pay for the question and the slice — never the haystack. It's working memory outside the context window: the context stays flat while the data grows.

## The receipts 🧾

<p align="center">
  <img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/readme/pyc_receipts.svg" alt="One scan of 101,619 files, queried three ways, cost a handful of tokens" width="100%">
</p>

One real run on my own machine. I pointed it at a project folder and let it scan.

- **101,619 files** walked into a variable. What the context saw: the number `101619`.
- Then three separate calls, each on the data already in memory — no re-scan, no re-send:
  - filter for one keyword → **8 lines**
  - a histogram of every file extension → **10 lines**
  - total size of the `.py` files → **one string**

Three questions answered over a hundred thousand records, and the context never held more than a thumbnail. Those 101,619 paths — roughly 7 MB of text, call it **1.5–2 million tokens** if you'd dumped them — simply never happened.

## The part that almost cost me money (again)

<p align="center">
  <img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/readme/pyc_trap.svg" alt="A line cap isn't a cost cap — one giant line slips past and gets re-billed every turn" width="100%">
</p>

Here's the trap, and it's the exact lesson lookback beat into me. My first cut capped the output at 80 *lines*. Felt safe. It wasn't.

A line cap does nothing against one **enormous** line. `print('x' * 10_000_000)`, or the `repr` of a million-element list — that single monster sails right past a line cap, lands in the context, and because context is re-sent every turn, you pay for it again on **every call** for the rest of the session. The precise bill a big `Edit` diff used to rack up.

So the fix isn't a line cap. It's a **character cap at the source** — before the data ever leaves the kernel — plus a bounded `repr` so echoing a huge object shows its *shape*, never its whole body. 10 MB print → 1.3k characters. Million-element list → under a thousand. The haystack stays in the heap; only a thumbnail crosses over.

Restated, because it keeps being true: **a token optimization that ignores the re-send is just moving the bill, not cutting it.** Cap at the source, or don't bother.

## The boring engineering that actually matters

It runs in an **isolated subprocess kernel**, not in-process — on purpose. The model writes arbitrary code in loops, and an infinite loop or a crash should cost you a *kernel*, never your agent. The parent enforces a wall-clock timeout; a runaway cell gets killed (its state forfeit — that's the price of an infinite loop) and the next call spins up a fresh kernel on its own. `input()` can't hang it. A stray background thread can't corrupt it. Two sub-agents can hit it at once. Bulletproof was the requirement, not the bonus.

## The quiet part, out loud

I'm going to say it, because I'm tired of not saying it: **we did this first.**

Not a lab. Not a research team. One builder in the Dominican Republic and his agent, on a random Tuesday, turning "imagine the model had a live console" into a shipped, hardened, cache-safe feature the *same day*. If a persistent, off-context REPL shows up in someone else's agent next quarter — good, it's a great idea, I already know. But you read it here first, and I'm putting a date on it on purpose.

Credit is cheap. Pay it. 🦅🇩🇴

---

Run it yourself → `pip install dulus` · [dulus.ai](https://dulus.ai)
Rather not babysit infra? Hosted agents + dashboard, zero setup → [dulus.online](https://dulus.online)

Same brain either way. 🦅🇩🇴
