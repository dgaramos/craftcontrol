---
name: review-pr
description: Review a CraftControl pull request or local diff for architecture, tests, security, frontend composition, and documentation accuracy. Use with `/review-pr <number>`.
---

# Review PR

Load the PR metadata and diff, or compare the local branch with `main`. Apply the backend checklist to backend/tests, frontend checklist to browser modules/tests, and docs checklist to Markdown. Report findings as blocker, important, or suggestion using `file:line`, current behavior, and proposed correction. Never modify code unless the user asks for fixes.
