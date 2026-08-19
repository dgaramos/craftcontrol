---
name: implement
description: Implement a prepared CraftControl issue with the right layer-specific checks. Use with `/implement` after `/start-issue`.
---

# Implement

Identify the affected layer before editing. Invoke `/backend` for `apps/backend/` or `tests/`, `/frontend` for browser modules or frontend tests, and both when necessary. Make the smallest safe change, update observable tests, and run `bin/check`. Do not advance when the quality gate fails.
