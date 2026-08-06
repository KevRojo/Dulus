---
name: webbridge_evaluate_first_pattern
description: In browser automation prefer running JS (evaluate) over Playwright click — actionability checks stall on SPAs/shadow-DOM
type: feedback
hall: advice
source: palace_init
---
# Browser automation: prefer JS `evaluate` over `click`

When driving a browser (WebBridge / Playwright), default to executing JS —
`document.querySelector('<sel>').click()` — for clicks and fills. Only reach for
a real Playwright `click` when you specifically need trusted input dispatch
(native file picker, hover side-effects, anti-bot checks that inspect trusted
events).

**Why:** Playwright's actionability checks (visible, enabled, stable,
receives-events) routinely **stall** on SPAs, modals, shadow-DOM widgets, and
popups. Each stall burns ~30s of timeout and a whole turn. Raw JS bypasses all of
that and almost never hangs.

**How:**
- Click: `document.querySelector('button[name="x"]').click()`
- Click by text: `[...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Go').click()`
- Fill: `const i = document.querySelector('input'); i.value = 'foo'; i.dispatchEvent(new Event('input', {bubbles:true}))`
