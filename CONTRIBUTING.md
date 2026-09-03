# Contributing to CraftControl

This document is the single source of truth for contributing to CraftControl — for both human contributors and AI agents.

AI agents should also read [`AGENTS.md`](AGENTS.md) for architecture, data invariants, and quality-gate details.

---

## Before you start

1. Follow the [Development setup](docs/development-setup.md) guide to get the stack running and the quality gate passing locally.
2. Open or find the GitHub Issue that describes the work.
3. Make sure it has a **Project**, **Milestone**, **Label**, and **Assignee** (see [Metadata](#metadata) below).
4. Create a branch from `main` following the naming convention below.

---

## Language

English is the project's primary language for GitHub issues, pull-request
titles and descriptions, commit messages, source code, tests, and technical
documentation. Write new contribution artifacts in English so external
contributors and automated tooling share one canonical context.

Portuguese translations remain welcome where a document already has a PT-BR
counterpart or an issue explicitly requests one. Keep translated user-facing
content synchronized with its English source; use Portuguese for local
discussion when that is clearer, but record durable project decisions in
English.

---

## Branch naming

```
{issue-number}-{type}/{short-description}
```

Examples:

```
42-feat/player-history
17-fix/session-close-on-disconnect
28-docs/contributing-guide
```

The issue number prefix is mandatory. It links the branch to the issue and the project board.

---

## Conventional Commits

Every commit must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): imperative summary
```

Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `perf`.

Examples:

```
feat(players): add lifetime session history
fix(auth): clear session on password change
docs(repo): create CONTRIBUTING.md
```

Mark breaking changes with `!` and explain them in the commit body or a `BREAKING CHANGE:` footer.

Verify your subject before pushing:

```bash
git show -s --format=%s HEAD
```

Do not publish a non-conforming commit and plan to repair it later.

---

## Pull requests

All changes must go through a pull request. **Do not push directly to `main`.**

`main` is protected: PRs from external contributors require at least one approval from the repository owner (`@dgaramos`) before they can be merged. The owner can merge their own PRs without a separate approval. The quality gate checks must pass for everyone. Reviews are requested automatically via `CODEOWNERS`.

### PR title format

```
type(scope): description (#issue-number)
```

Example:

```
feat(players): add history view (#42)
```

The issue number in the title is mandatory.

### PR description

Follow [`.github/pull_request_template.md`](.github/pull_request_template.md). Fill every section; do not delete sections you leave empty — keep the placeholder comments so reviewers can see what was considered.

The canonical PR template is `.github/pull_request_template.md` (English). `.gitea/pull_request_template.md` is an active Portuguese translation used by the Gitea mirror; update it whenever the structure of the canonical template changes.

### Metadata

Every issue **and** every PR must have all four of the following set before requesting a review:

| Field | Guidance |
| --- | --- |
| **Project** | Add to the relevant GitHub Project board (e.g. `Documentation Improvement`, `Backend`, `Frontend`) |
| **Milestone** | Pick the delivery cycle that best fits the work (see below) |
| **Label** | At minimum one label from the standard set (`feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `bug`, `enhancement`, `documentation`, etc.) |
| **Assignee** | Assign yourself (or the person doing the work) |

#### Milestones

| Milestone | Scope |
| --- | --- |
| **Reliable Foundation** | Reliability, security, backups, auth, and core invariants |
| **Clean Architecture** | Modular monolith refactor, ports/adapters, layered use cases |
| **Complete Panel** | Full UI feature parity, bilingual, mobile-first |
| **Community Ready** | Installation, diagnostics, contribution tooling, release automation |

---

## Quality gate

Changes to user-visible content in `README.md` must update the corresponding
content in `README.pt-BR.md` in the same pull request.

English is the canonical language for technical and operational documentation.
When a document has a Portuguese translation (for example
`README.pt-BR.md` or `docs/installation.pt-BR.md`), user-visible changes to its
English source must update that translation in the same pull request. New
Portuguese documentation is optional unless an issue explicitly requires it.

The quality gate **must pass** before requesting a merge:

```bash
bin/check
```

Node/npm do not need to be installed on the host: `bin/check-frontend` falls
back to Docker (`node:22-alpine`) automatically. Run the gate before reporting
a missing local Node installation as a blocker.

Individual gates are also available:

```bash
bin/check-frontend          # JS syntax, i18n, visual contracts
bin/check-backend           # Python application and persistence tests
bin/check-contracts         # OpenAPI, route surface, generated declarations
bin/check-integration       # Compose builds, split runtime, architecture and deploy safety
bin/check-host-agent        # Host agent unit and integration tests
bin/check-contracts-frontend  # Frontend contract declarations
bin/check-dr-agents         # DR agents profile and workflow checks
```

Keep a test in exactly one gate unless a boundary invariant deliberately spans gates. Update tests and `README.md` whenever public behavior, persistence, API contracts, or recovery rules change.

---

## CodeRabbit

CodeRabbit reviews every PR automatically. Address its findings before merging.

Useful commands in PR comments:

| Command | Effect |
| --- | --- |
| `@coderabbitai review` | Trigger a new review pass |
| `@coderabbitai summary` | Regenerate the PR summary |
| `@coderabbitai resolve` | Mark a thread as resolved |
| `@coderabbitai help` | List all available commands |

---

## Need help?

See the [Contributor FAQ](docs/contributing-faq.md) for reporting bugs,
suggesting features, choosing milestones, quality-gate failures, reviews, and
the Claude Code skills provided by this repository.

---

## What not to commit

- Tokens, passwords, API keys, credentials, or private keys
- `.env` or any local environment file
- `data/manager.db` or any SQLite database
- Minecraft world data
- Anything under `roadmap/` (private planning context, listed in `.chezmoiignore`)

Machine-local values must remain outside version control.
