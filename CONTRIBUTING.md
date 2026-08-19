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
| **Fundação Confiável** | Reliability, security, backups, auth, and core invariants |
| **Arquitetura Limpa** | Modular monolith refactor, ports/adapters, layered use cases |
| **Painel Completo** | Full UI feature parity, bilingual, mobile-first |
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

Individual gates are also available:

```bash
bin/check-frontend      # JS syntax, i18n, visual contracts
bin/check-backend       # Python application and persistence tests
bin/check-contracts     # OpenAPI, route surface, generated declarations
bin/check-integration   # Compose builds, split runtime, architecture and deploy safety
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

## What not to commit

- Tokens, passwords, API keys, credentials, or private keys
- `.env` or any local environment file
- `data/manager.db` or any SQLite database
- Minecraft world data
- Anything under `roadmap/` (private planning context, listed in `.chezmoiignore`)

Machine-local values must remain outside version control.
