# Contributor FAQ

This FAQ answers intent-level questions about contributing. For the required
workflow, branch naming, pull-request metadata, and quality gate, see
[Contributing](../CONTRIBUTING.md).

## How do I report a bug?

Open a GitHub issue with a concise title, the observed behavior, expected
behavior, reproduction steps, and relevant safe logs or screenshots. Never
include passwords, tokens, `.env` values, XUIDs, database files, or world data.
Add the appropriate label, milestone, Project, and assignee before requesting
work on it. Write the durable issue title and body in English; Portuguese is
appropriate for discussion when it makes the problem clearer.

## How do I suggest a feature?

Open an issue in English that explains the user problem and expected outcome before
proposing implementation details. State the intended scope, non-goals, affected
area, and verifiable acceptance criteria. Use the issue to agree on the change
before starting a branch.

## What is CodeRabbit and why does it comment on my PR?

CodeRabbit is the automated pull-request reviewer. It summarizes changes and
may identify correctness, security, test, or documentation concerns. Treat its
actionable findings as review feedback: verify them against the current code,
fix accepted findings, and explain or resolve the thread with evidence. Useful
PR commands are documented in [Contributing](../CONTRIBUTING.md#coderabbit).

## What are the project milestones and how do I pick one?

Choose the milestone that matches the delivery scope:

| Milestone | Use for |
| --- | --- |
| Reliable Foundation | Reliability, security, backups, authentication, and core invariants |
| Clean Architecture | Modular-monolith refactoring, ports/adapters, and layered use cases |
| Complete Panel | Product UI, bilingual mobile experience, and feature parity |
| Community Ready | Installation, diagnostics, contribution tooling, and release automation |

Every issue and PR also needs all four metadata fields: GitHub Project,
Milestone, Label, and Assignee. The [metadata guide](../CONTRIBUTING.md#metadata)
gives the complete rule.

## Can I work on an issue that is already assigned?

Do not start competing implementation without coordinating first. Comment on the
issue, mention the assignee, and agree on ownership or a split of the work. You
may help with investigation, tests, documentation, or a follow-up issue when
the assignee agrees. Keep one branch and pull request focused on one agreed
scope.

## What happens if the quality gate fails on my PR?

Do not request merge while it fails. Read the failing job, reproduce it with the
matching local gate when possible, correct the failure, and push the focused
fix. The full local command is `bin/check`; the independent gates are
`bin/check-frontend`, `bin/check-backend`, `bin/check-contracts`, and
`bin/check-integration`. If the failure is environmental, report the exact
command and evidence in the PR instead of masking it.

## Who reviews and merges PRs?

CodeRabbit reviews pull requests automatically. Human review follows the
repository's ownership rules; external contributors need approval from the
repository owner before merge. The owner may merge their own PR after required
checks and review findings are resolved. Do not merge directly to `main`.

## I use Claude Code. Are there skills that help me follow project conventions?

Yes. CraftControl provides native Claude Code skills under `.claude/agents/`.
Invoke them with `/skill-name`; use the issue number where indicated.

| Skill | Purpose |
| --- | --- |
| `/execute-issue <n>` | Run issue preparation, implementation, and shipping in order |
| `/start-issue <n>` | Verify metadata, read required context, map files, and create a branch |
| `/implement` | Implement a prepared issue, run tests, and self-review the diff |
| `/ship-issue` | Commit, push with confirmation, and open a metadata-complete PR |
| `/review-pr <n>` | Review a PR or local diff by backend, frontend, and docs criteria |
| `/handle-pr-findings <n>` | Triage and address CodeRabbit or human review findings |
| `/create-issue` | Create a scoped issue with acceptance criteria and required metadata |
| `/backend` | Apply backend architecture, DI, persistence, and test conventions |
| `/frontend` | Apply frontend ESM, injection, i18n, and test conventions |
| `/manage-project` | Inspect and manage GitHub Project membership |
| `/manage-milestone` | Inspect and assign delivery milestones |

Use `/execute-issue <n>` for a normal issue. Use `/create-issue` before work
when the request is not yet a complete GitHub issue. Layer skills complement,
but do not replace, `AGENTS.md`, `CLAUDE.md`, and `CONTRIBUTING.md`.
