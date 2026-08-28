# CraftControl profile

Use this profile when reviewing, implementing, or authoring issues in
CraftControl. It strengthens the portable contract; explicit PR/ref input,
evidence requirements, incremental re-review, and explicit publication
authorization still apply.

## Project identity

- **Repository:** `dgaramos/craftcontrol`
- **Main branch:** `main`
- **Supported branches:** `<issue-number>-<type>/<slug>`
- **Quality command:** `bin/check`

## Required context

Read before reviewing or implementing: `README.md`, every Markdown file in
`roadmap/`, `AGENTS.md`, `CONTRIBUTING.md`, and `docs/architecture.md`. The
roadmap is private operational context: never stage, quote, publish, or copy it
into an artifact.

## Architecture boundaries

### Backend (`apps/server/`)

- HTTP → use cases → ports/adapters. Routes do not reach repositories or
  adapters; runtime supervisors call application-facing ports.
- Inject dependencies through constructors and assemble production in the
  composition root. Use `Protocol` only for meaningful replaceable boundaries.
- Preserve XUID as internal identity, permanent player profiles, idempotent
  ingestion, and the separation of player history from operational retention.
- Migrate SQLite without deleting user data. Do not add locks or transactions
  that harm runtime reconciliation or SSE delivery.
- Enforce capabilities, allowlists, and CSRF. Do not expose arbitrary console
  access, session identifiers, credentials, or XUIDs.

### Frontend (`apps/client/static/js/`)

- Preserve native ES modules and dependency direction: `core` → `components` →
  `features`; core never imports features.
- Inject feature dependencies through the composition root. Avoid direct global
  DOM coupling when an injected helper exists.
- Keep all visible copy localized in every UI locale defined by `AGENTS.md`.
  Preserve touch usability, empty/error states, CSRF behavior, and SSE-driven
  refreshes; do not add browser polling when targeted invalidation is sufficient.
- Escape external content before DOM insertion.
- Keep tests deterministic, restore globals, and avoid time/order coupling.

### Contracts (`packages/contracts/openapi.json`)

- Treat `packages/contracts/openapi.json` as canonical. Keep routes, envelopes,
  errors, authentication cookies, capabilities, CSRF, pagination, and generated
  frontend declarations aligned.
- Do not change only one side of an endpoint. Evaluate consumer compatibility,
  migration, and contract coverage.

### Operations (Compose, Docker, deploy, backup, restore)

- Keep the panel usable without Prometheus, Grafana, the exporter, or the
  Telemetry Pack. Derived events retain evidence and never become authoritative.
- Pack lifecycle uses the shared installer, persistent Bedrock data, backups,
  atomic association updates, and an explicit restart decision.
- Coordinated backups pause saves only for the copy window and resume in
  `finally`. Restore is offline, confirmed, creates a recovery copy, and never
  restores `.env` automatically.
- Do not deploy with bare Compose from a development checkout. Protect `.env`,
  SQLite, and world data from overwrite or development bind mounts.

## Review checklist

- [ ] HTTP → use cases → ports/adapters boundary preserved; no route reaches a repository
- [ ] Dependencies injected through constructors; `patch` only at third-party boundaries
- [ ] `core` → `components` → `features` dependency direction preserved in JS
- [ ] All visible copy localized; SSE-driven refresh used instead of polling
- [ ] `packages/contracts/openapi.json` and generated frontend declarations in sync
- [ ] SQLite migration is backward-compatible and data-safe
- [ ] Backup/restore conventions preserved for any operations change
- [ ] English `README.md` updated for any public behavior change
- [ ] Roadmap content not staged, quoted, or published
- [ ] `bin/check` passes before handoff

## Testing conventions

Flag any new `unittest.mock.patch` call that targets a stdlib module
(`pathlib.Path`, `subprocess`, `socket`, `time`, `sqlite3`, etc.) as a
correctness risk. The project rule is constructor injection: infrastructure
dependencies are injected as constructor parameters with production defaults,
and tests pass fakes directly. `patch` is permitted only at third-party
boundaries with no injectable seam.

## Quality and contribution rules

Run `bin/check` before handoff. Independent gates: `bin/check-frontend`,
`bin/check-backend`, `bin/check-contracts`, `bin/check-dr-agents`, and
`bin/check-integration`; keep a test in exactly one gate unless it deliberately
spans a boundary.

Use an issue branch, Conventional Commits, and a PR with Project, Milestone,
Label, and Assignee. Address actionable CodeRabbit findings before merge. Never
commit roadmap content, `.env`, databases, world data, credentials, or keys.

Validate commands, paths, versions, contracts, and links against the current
repository state. Check branch name, PR title, linked issue, and required
metadata before handoff.

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

## Identity and publication

Codex reviews are attributed to **Cody DR** and Claude Code reviews to
**Claudio DR**. The optional GitHub App publishers are `cody-dr` and
`claudio-dr`. Without explicit user authorization, return publication-ready
content marked not published. With explicit authorization, a personal GitHub
account may publish only as a disclosed fallback when the requested App
operation is unconfigured or unavailable before dispatch.

When a reviewer authors a commit, use its matching co-author trailer:
`Cody DR <dgaramos+cody@gmail.com>` or `Claudio DR <dgaramos+claudio@gmail.com>`.

This profile never triggers an automatic review.

## Publisher dispatch contract

| Reviewer | Mode | Availability |
| --- | --- | --- |
| Cody DR | review | available |
| Cody DR | create-issue | available |
| Cody DR | apply-pr-metadata (App-safe fields) | available |
| Cody DR | personal Project metadata | explicit personal fallback required |
| Cody DR | reply | available |
| Cody DR | resolve-thread | available |
| Claudio DR | review | available |
| Claudio DR | create-issue | available |
| Claudio DR | apply-pr-metadata (App-safe fields) | available |
| Claudio DR | personal Project metadata | explicit personal fallback required |
| Claudio DR | reply | available |
| Claudio DR | resolve-thread | available |

Dispatch `publish-cody-review.yml` or `publish-claudio-review.yml` with
`pr_number`, `reviewed_head_sha`, `event`, `review_body`, and the optional
manifests `inline_comments_json`, `replies_json`, and `resolve_thread_ids_json`.

**Review event rules:** always use `event: COMMENT`; never `APPROVE` or
`REQUEST_CHANGES`. Every finding whose evidence line is within the diff must be
an inline diff comment. Informational observations must be labelled
non-actionable. Auth/CSRF claims must be grounded in `apps/server/minecraft_manager/auth/`.

Dispatch `publish-cody-issue.yml` or `publish-claudio-issue.yml` with `title`,
`body`, labels, assignees, and `milestone_number`.

Dispatch `publish-cody-pr-metadata.yml` or `publish-claudio-pr-metadata.yml`
with `pr_number`, `base_branch`, and any of `labels_json`, `assignees_json`,
`milestone_number`, and the three project fields `project_owner`,
`project_number`, `project_status`.

After any App publication, verify the author is `cody-dr[bot]` or
`claudio-dr[bot]`. A failed App verification is a failed publication, not a
fallback trigger.
