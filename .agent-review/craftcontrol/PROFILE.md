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
`claudio-dr`. Without explicit user authorization, return publication-ready
content marked not published. With explicit authorization, a personal GitHub
account may publish only as a disclosed fallback when the requested App
operation is unconfigured or unavailable before dispatch.

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

Publication remains explicitly authorized. Use the configured reviewer App
first. A personal GitHub account is permitted only as an explicitly authorized
fallback when the requested App operation is unconfigured or unavailable before
dispatch; record its login in the outcome. Never fall back after an App dispatch
or verification failure.

### Review

Dispatch `publish-cody-review.yml` or `publish-claudio-review.yml` with
`pr_number`, `reviewed_head_sha`, `event`, `review_body`, and the optional
review manifests `inline_comments_json`, `replies_json`, and
`resolve_thread_ids_json`.

**Review event rules (enforced):**

- Always use `event: COMMENT`. Never use `APPROVE` or `REQUEST_CHANGES`.
  Merge blocking and approval are human decisions; no reviewer bot may submit
  either state for this project.
- Every formal finding whose evidence line is within the diff must be delivered
  as an inline diff comment in `inline_comments_json`, not embedded as body
  text in the top-level review comment.
- Informational observations must be labelled non-actionable and must not
  appear in the merge-risk justification or approval rationale.
- A claim about authentication, CSRF, or authorization must be grounded in the
  repository's real auth rules (see `apps/backend/minecraft_manager/auth/`)
  before it is included in any finding. Mutation-only assumptions must not be
  applied to read-only endpoints.
- A recommendation to change an OpenAPI response schema must identify a
  concrete contract risk and its consumer impact before it is classified as a
  finding.

### Create issue

Dispatch `publish-cody-issue.yml` or `publish-claudio-issue.yml` with `title`,
`body`, labels, assignees, `milestone_number`, `project_owner`,
`project_number`, and `project_status`. The App applies and verifies issue,
label, assignee, and milestone metadata. A personal Project requires an
explicitly authorized, disclosed personal fallback. Do not supply review-only
fields to this mode.

### Apply PR metadata

Dispatch `publish-cody-pr-metadata.yml` or `publish-claudio-pr-metadata.yml`
with `pr_number` and `base_branch` (required), plus any of `labels_json`
(JSON array), `assignees_json` (JSON array), `milestone_number` (numeric string),
and the three project fields `project_owner`, `project_number`, `project_status`
(must be supplied together or not at all).

The workflow authenticates as the matching App, verifies the publishing identity,
applies all supplied metadata, and then re-reads the PR to confirm every field.
A missing permission or a verification mismatch fails the workflow before any
personal-account fallback. Project metadata is required by CraftControl; a
personal Project therefore requires an explicitly authorized fallback that
records the personal actor.

| Reviewer | Mode | Availability |
| --- | --- | --- |
| Cody DR | review | available |
| Cody DR | create-issue | available |
| Cody DR | apply-pr-metadata | available |
| Cody DR | reply | available |
| Cody DR | resolve-thread | available |
| Claudio DR | review | available |
| Claudio DR | create-issue | available |
| Claudio DR | apply-pr-metadata | available |
| Claudio DR | reply | available |
| Claudio DR | resolve-thread | available |

## Post-publication verification

After an App publication, verify the target and that the author is
`cody-dr[bot]` for Cody DR or `claudio-dr[bot]` for Claudio DR. Verify reply
and resolution actions for both reviewers. A failed App verification is a
failed publication, not a fallback to a personal account. When an App operation
was unavailable before dispatch and a personal fallback was explicitly
authorized, verify the authenticated personal actor and report it as a personal
fallback rather than a reviewer-App action.
