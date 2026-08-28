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

## I use Codex. Are there skills that help me follow project conventions?

Yes. Install the global `cody-dr` portable workflow plugin. CraftControl does
not duplicate its lifecycle skills under `.agents/skills/`; the plugin loads
`.dr-agents/craftcontrol/PROFILE.md`. Issue authoring remains draft-first,
findings handling requires an explicit decision before each fix or publication,
and the Cody App publishes review content only as `COMMENT`.

The profile distinguishes App-safe PR metadata from a personal GitHub Project.
The latter requires an explicitly authorized, disclosed personal fallback until
the portable `ship-change` adapter supports the repository publisher dispatch.

Yes. CraftControl provides Claude Code agents under `.claude/agents/`.
The lifecycle agents delegate to the portable Claudio DR workflows from the
`claudio-dr` plugin, which supply the evidence-first review contract,
publication authorization, and issue lifecycle. The layer and management
agents are standalone native utilities.

### Lifecycle agents (backed by Claudio DR portable workflows)

Invoke with `/skill-name`; use the issue number where indicated.

| Agent | Purpose |
| --- | --- |
| `/execute-issue <n>` | Run issue preparation, implementation, and shipping in order |
| `/start-issue <n>` | Verify metadata, read required context, map files, and create a branch |
| `/implement` | Implement a prepared issue, run tests, and self-review the diff |
| `/ship-issue` | Commit, push with confirmation, and open a metadata-complete PR |
| `/review-pr <n>` | Review a PR or local diff using Claudio DR evidence-first criteria — accepts a PR number, URL, branch name, or commit range |
| `/handle-pr-findings <n>` | Triage and address CodeRabbit or human review findings |
| `/create-issue` | Draft a scoped issue with acceptance criteria and required metadata |

Use `/execute-issue <n>` for a normal issue. Use `/create-issue` before work
when the request is not yet a complete GitHub issue. These agents load the
CraftControl-local profile at `.dr-agents/craftcontrol/PROFILE.md`, which
applies architecture, quality gate, and publisher rules to every run.

Claudio DR is the default reviewer and issue author for Claude Code sessions.
Reviews published through the Claudio GitHub App appear with `claudio-dr[bot]`
as the author; publication requires explicit authorization — no personal account
is used as a fallback.

### Layer agents (standalone native utilities)

| Agent | Purpose |
| --- | --- |
| `/backend` | Apply backend architecture, DI, persistence, and test conventions |
| `/frontend` | Apply frontend ESM, injection, i18n, and test conventions |

### Management agents (standalone native utilities)

| Agent | Purpose |
| --- | --- |
| `/manage-project` | Inspect and manage GitHub Project membership |
| `/manage-milestone` | Inspect and assign delivery milestones |

All agents complement, but do not replace, `AGENTS.md`, `CLAUDE.md`, and
`CONTRIBUTING.md`.
