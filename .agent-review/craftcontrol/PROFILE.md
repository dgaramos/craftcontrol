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

## Quality gate

Run `bin/check` before handoff. A failed gate stops implementation, shipping,
or a claim that a finding is resolved.

## Lifecycle skill mapping

| Local entry point | Portable skill |
| --- | --- |
| Start an issue branch | `start-issue` |
| Implement an issue | `implement-issue` |
| Ship a completed issue | `ship-change` |
| Run the full lifecycle | `execute-issue` |
| Review a pull request | `review-pr` |
| Triage review findings | `handle-pr-findings` |
| Draft or publish an issue | `author-issue` |

## PR metadata

- **Base branch:** `main`
- **Branch naming:** `<issue-number>-<type>/<slug>`
- **Labels, milestone, assignee, Project and reviewers:** inherit the linked
  issue; apply and verify each after opening the PR
- **PR template:** `.github/pull_request_template.md`
- **Merge policy:** squash merge after required checks and actionable findings
  are addressed

## Publisher dispatch contract

Publication remains explicitly authorized. Dispatch the matching workflow with
the current PR number, reviewed head SHA, event, summary, and batched manifest.
Never use a personal GitHub comment as a fallback for a configured App.

| Reviewer | Mode | Dispatch | Availability |
| --- | --- | --- | --- |
| Cody DR | review | `gh workflow run publish-cody-review.yml` | available |
| Cody DR | create-issue | `gh workflow run publish-cody-issue.yml` | available |
| Cody DR | reply | `gh workflow run publish-cody-review.yml` with `replies_json` | available |
| Cody DR | resolve-thread | `gh workflow run publish-cody-review.yml` with `resolve_thread_ids_json` | available |
| Claudio DR | review | `gh workflow run publish-claudio-review.yml` | available |
| Claudio DR | create-issue | `gh workflow run publish-claudio-issue.yml` | available |
| Claudio DR | reply | `gh workflow run publish-claudio-review.yml` with `replies_json` | available |
| Claudio DR | resolve-thread | `gh workflow run publish-claudio-review.yml` with `resolve_thread_ids_json` | available |

## Post-publication verification

After a review, reply, resolution, or issue publication, verify the target and
that the author is `cody-dr[bot]` for Cody DR or `claudio-dr[bot]` for Claudio
DR. A failed verification is a failed publication, not a fallback to a personal
account.
