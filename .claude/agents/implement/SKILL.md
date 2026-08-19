---
name: implement
description: Implement a prepared CraftControl issue with the right layer-specific checks. Use with `/implement` after `/start-issue`.
---

# Implement

Identify the affected layer before editing. Invoke `/backend` for `apps/backend/` or `tests/`, `/frontend` for browser modules or frontend tests, and both when necessary. Make the smallest safe change, update observable tests, and run `bin/check`.

Before `/ship-issue`, invoke `/review-pr` on the local diff, including staged
and untracked files. Treat that as a mandatory self-review gate: address every
`blocking` and `important` finding, rerun the affected checks, and repeat the
review when the fix materially changes the diff. Do not advance when the
quality gate fails or the review still has `blocking` or `important` findings.
