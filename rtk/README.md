# RTK (Rust Token Killer) — Dulus integration

Dulus transparently rewrites covered shell commands (`ls`, `tree`, `grep`,
`find`, `git`, `diff`, `cat`, …) through the `rtk` binary so model-issued
commands always emit token-optimized output. 60–90% savings on common ops.

## Status

- **Windows**: `rtk.exe` is bundled — no setup needed.
- **Linux / macOS**: run `bash install.sh` once to drop the binary in
  `~/.local/bin/rtk`. Dulus will pick it up automatically.

## Toggle

Controlled by `rtk_enabled` in `~/.dulus/config.json` (default: `true`).
Set to `false` to disable rewriting.

If the binary is missing, Dulus silently falls back to the raw command —
nothing breaks.

## Upstream

Source / license: <https://github.com/rtk-ai/rtk> (MIT).
