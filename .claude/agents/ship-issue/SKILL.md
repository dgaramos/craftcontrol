---
name: ship-issue
description: Commit, push, and open a CraftControl pull request for a completed issue. Use with `/ship-issue`.
---

# Ship issue

Review the staged files for secrets, world data, `.env`, and SQLite files. If any protected artifact is staged, stop before commit and push; unstage it without deleting or overwriting it, and ask the user how to proceed when classification is uncertain. Commit with `type(scope): imperative summary`. Ask explicit confirmation before pushing to GitHub and Gitea, then again before creating a PR. Use the PR template, title `type(scope): description (#issue)`, and set assignee, milestone, label, and Project. Stop after reporting the PR and pending checks; never merge.
