---
name: execute-issue
description: Execute a CraftControl GitHub issue from verification through implementation and a pull request. Use with `/execute-issue <number>`.
---

# Execute issue

Run `/start-issue <number>`, `/implement`, and `/ship-issue` in that order.
`/implement` includes the mandatory `/review-pr` self-review gate before
`/ship-issue`; do not open a PR while it has `blocking` or `important` findings.
Stop before implementation if the issue lacks Project, Milestone, Label, or Assignee, or if acceptance criteria are ambiguous. Stop before push and PR creation until the user explicitly confirms each external action. Do not merge or wait for CI.
