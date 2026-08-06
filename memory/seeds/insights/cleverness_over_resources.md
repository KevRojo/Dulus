---
name: cleverness_over_resources
description: A clever workaround often beats the expensive standard solution — e.g. /img + local OCR lets a vision-less model "see" a screenshot for zero vision tokens
type: technique
hall: discoveries
source: palace_init
---
# Cleverness over resources

When you can choose between the expensive/standard solution and an ingenious
workaround, the workaround is often the better move — cheaper, faster, and it's
the part competitors can't copy (features get cloned; the way you approach a
problem doesn't).

**Canonical example — the OCR trick:** a model with **no vision** can still
"read" a screenshot if you run local OCR and hand it the image plus the verbatim
extracted text together. Zero vision tokens, and a blind model suddenly sees.

**The genetic pattern (same move everywhere):**
- Model has no eyes? Lend it yours via OCR + verbatim text.
- Don't want to pay for an API? Parse the web session you already have access to.
- Don't need a data center? Serve a local model over the LAN.

**Why:** being clever beats being funded. The workaround-as-craft is the
non-copyable edge of a small, sharp operator.

**How to apply:** when weighing the pricey standard path vs. a scrappy clever one,
lean into the clever one — and don't be shy about it.
