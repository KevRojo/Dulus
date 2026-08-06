---
name: tmux_send_keys_power_patterns
description: tmux send-keys mastery — chaining with \;, wait-for over sleep, buffers for big pastes, capture-pane feedback loops, synchronize-panes
type: reference
hall: technical
source: palace_init
---
# tmux send-keys — power patterns

## Core lesson
**Never fire `tmux send-keys` as many separate invocations when you can chain
with `\;` in one.** Multiple `tmux …; tmux …; tmux …` calls are junior-level; a
single one-liner chained with `\;` is senior-level. Remember this first.

## Pattern 1 — `\;` chaining (the mother technique)
```bash
tmux new-session -d -s s \; send-keys -t s "ssh user@host" Enter \; send-keys "cd /srv && python run.py" Enter \; attach -t s
```
`\;` separates tmux commands within ONE invocation; the `\` escapes the shell's
`;`. For any ssh/login/run/attach automation → one line with `\;`.

## Pattern 2 — `wait-for` instead of guessing with `sleep`
```bash
tmux send-keys -t s "make build && tmux wait-for -S done" Enter \; wait-for done \; send-keys "make deploy" Enter
```
Producer (inside the command): `tmux wait-for -S <chan>`. Consumer (driver):
`tmux wait-for <chan>` blocks until signaled. Any time you're tempted to `sleep N`
between commands, use `wait-for` — it's deterministic; sleep is probabilistic.

## Pattern 3 — several commands in one send-keys
`Enter` (`C-m`) is just another arg: `tmux send-keys -t s "cd /srv" Enter "source venv/bin/activate" Enter "python run.py" Enter`. If you see 5 consecutive send-keys, fuse them.

## Pattern 4 — `-N` repeat count
`tmux send-keys -t s -N 5 Up` (5× up), `-N 20 BSpace` (delete 20), `-N 3 C-w`
(kill 3 words). Beats an ugly for-loop when you need "press X N times".

## Pattern 5 — `-H` hex bytes (for unusual chars)
`-H 03` = Ctrl-C, `-H 04` = Ctrl-D/EOF, `-H 1b 5b 41` = up-arrow, `-H 0d` = Enter.
When a key name doesn't work in a weird app, send the raw byte in hex.

## Pattern 6 — `-l` literal (no key-name parsing)
`tmux send-keys -l "$(cat snippet.py)"` pastes code without parsing; `-l 'text with the word Enter'` types the literal word. Use `-l` for untrusted data or text with reserved chars.

## Pattern 7 — `load-buffer` + `paste-buffer` for big blocks
send-keys can TRUNCATE at ~200 bytes on old tmux. For large scripts use the buffer:
```bash
cat script.py | tmux load-buffer -b blk - \; paste-buffer -d -b blk -t s
```
`-d` deletes the buffer after paste. If injecting >200 bytes, never send-keys — use the buffer.

## Pattern 8 — `capture-pane` feedback loops
`tmux capture-pane -p -t s` (visible), `-S -1000` (scrollback), `-J` (join wrapped), `-e` (ANSI). Poll for a prompt:
```bash
until tmux capture-pane -p -t s | grep -q '\$ $'; do sleep 0.2; done
```
send-keys + capture-pane = a closed feedback loop: the agent sees what happened and decides the next step.

## Pattern 9 — `synchronize-panes` (type once, run on N hosts)
Split into panes (one ssh each), then `set-window-option synchronize-panes on` —
typing in one pane runs in all. Gold for administering identical servers.

## Pattern 10 — `if-shell` (conditional branching)
`tmux if-shell "test -f /tmp/ready" "send-keys -t s 'go' Enter" "display 'not ready'"`. Guards for "run X only if Y".

## Pattern 11 — `pipe-pane` (live log to file)
`tmux pipe-pane -t s -o 'cat >> /tmp/s.log'` toggles logging on; run again to toggle off. Great for debugging long-running sessions.

## Pitfalls (learned the hard way)
1. `;` without `\` is eaten by the shell — always `\;` or quote it.
2. `Enter` inside `-l` types the literal word "Enter", not a submit.
3. send-keys is ASYNC (keys are queued). Need certainty? `wait-for` or poll with capture-pane.
4. The session must exist before `send-keys -t` — use `new-session -d` (or `-A` = attach-or-create).
5. Pastes >200 bytes can truncate in send-keys — use `load-buffer`.
6. `C-[` = Escape, `C-i` = Tab, `C-h` = BSpace — terminal aliases, not always interchangeable.

## Special keys
| Token | Sends |
|---|---|
| `Enter` / `C-m` | `\r` (0x0D) — use this 99% of the time |
| `C-j` | `\n` — rare; some REPLs treat it differently |
| `Escape` | ESC |
| `BSpace` | backspace |
