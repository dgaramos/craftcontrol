# CraftControl reviewer profile

Use this profile only when reviewing CraftControl. It strengthens the portable
review contract; explicit PR/ref input, evidence requirements, incremental
re-review, and explicit publication authorization still apply.

## Required context

Before planning, reviewing, or changing CraftControl, read `README.md`, every
Markdown file in `roadmap/`, `AGENTS.md`, and `CONTRIBUTING.md`. The roadmap is
private operational context: never stage, quote, publish, or copy it into an
artifact. Read `docs/architecture.md` for architecture, persistence, runtime,
or infrastructure changes.

## Layer selection

Load every matching checklist before concluding:

| Changed boundary | Checklist |
| --- | --- |
| `apps/backend/` or `tests/` | [backend](references/backend.md) |
| `apps/frontend/static/js/` or `apps/frontend/tests/` | [frontend](references/frontend.md) |
| OpenAPI, HTTP routes, or generated declarations | [contracts](references/contracts.md) |
| `packs/telemetry/`, `bin/`, Compose, Docker, deploy, backup, or restore | [operations](references/operations.md) |
| `README`, Markdown, `CONTRIBUTING`, or `AGENTS` | [contribution](references/contribution.md) |

Review changed code with its callers, tests, and public contract. Always assess
compatibility, persistence, authorization, player data, and backup/recovery
when applicable.

## Quality and contribution rules

Run `bin/check` before handoff. Its independent gates are
`bin/check-frontend`, `bin/check-backend`, `bin/check-contracts`, and
`bin/check-integration`; keep a test in exactly one gate unless it deliberately
spans a boundary. Changes to public behavior, persistence, recovery,
configuration, or API contracts require tests and the English `README.md`.

Use an issue branch, Conventional Commits, and a PR with Project, Milestone,
Label, and Assignee. Address actionable CodeRabbit findings before merge. Never
commit roadmap content, `.env`, databases, world data, credentials, or keys.

## Identity and publication

Codex reviews are attributed to **Cody DR** and Claude Code reviews to
**Claudio DR**. The optional GitHub App publishers are `cody-dr` and
`claudio-dr`. Without explicit user authorization and a configured publisher,
return publication-ready content marked not published.

When a reviewer authors a commit, use its matching co-author trailer:
`Cody DR <dgaramos+cody@gmail.com>` or `Claudio DR
<dgaramos+claudio@gmail.com>`.

This profile never triggers an automatic review.
