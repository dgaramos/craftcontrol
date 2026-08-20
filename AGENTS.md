# Project Instructions

## Purpose

Maintain CraftControl, a mobile-first, bilingual control panel for Minecraft Bedrock servers. The application must remain usable without Prometheus, Grafana, the custom exporter, or a behavior pack.

## Required context

Before planning, reviewing, or changing this project, read `README.md` and every Markdown file under the local `roadmap/` directory when that directory exists. The roadmap is private operational context: do not stage, commit, publish, quote, or copy it into deployment artifacts.

## Agent review profile

The tool-neutral profile at `.agent-review/craftcontrol/PROFILE.md` is the
authoritative CraftControl-specific review context. Load it and every applicable
layer checklist for any PR review, whether the reviewer is Cody DR, Claudio DR,
or another agent. The profile augments generic review skills; it does not
trigger a review automatically. If it is unavailable, use the repository-native
`review-pr` entry point. Never copy roadmap content, credentials, databases, or
world data into the profile or review output.

## Architecture

- Treat `docs/architecture.md` as the authoritative architecture and dependency-direction reference.
- Keep CraftControl a modular monolith: organize by domain, retain layered use cases inside modules, and use ports/adapters only at meaningful persistence and infrastructure boundaries.
- Inject dependencies through constructors and assemble production implementations in the composition root. Use `typing.Protocol` for replaceable boundaries; do not add a DI framework, service locator, or redundant interface for every concrete service.
- Runtime supervisors must call application-facing ports and must never reach through a service to its repository or adapter.
- Keep HTTP mapping in `apps/backend/minecraft_manager/routes.py`, orchestration in `services.py`, event ingestion in `runtime.py`, persistence in `repository.py`, and Bedrock/Docker/filesystem concerns in their adapters.
- Preserve the internal event broker, persisted operational events, SSE browser updates, targeted refreshes, and periodic full reconciliation.
- Keep one Gunicorn worker unless the process-local broker and runtime supervisors are redesigned for multiple workers.
- Do not add browser polling when an event-driven invalidation and targeted reconciliation is sufficient.
- Keep the manager independent from the exporter and observability stack.
- Use SQLite for local durable state and schema changes that migrate existing databases without deleting user data.
- Use the coordinated backup service for live world/database backups. Hold Bedrock saves only during the copy window, resume in `finally`, use SQLite's backup API, and verify checksums before restore.
- Restores are offline, explicitly confirmed, and must create a pre-restore recovery copy. Never restore `.env` automatically.

The legacy file locations in the preceding rule are compatibility facades during the modular refactor. New domain modules may live under `http/`, `server/`, `players/`, `telemetry/`, `operations/`, and `runtime/`; do not remove a compatibility import until its callers and tests have migrated.

## Player data invariants

- A disconnect updates presence and closes a session; it never removes a player profile.
- Use XUID internally as the stable identity, preserve aliases, and never expose XUID through public APIs or UI.
- Keep permanent player history separate from the rolling operational event retention.
- Make connect/disconnect, reconciliation, and death ingestion idempotent.
- Mark abrupt-stop session closures as inferred.
- Treat log-parsed deaths as derived and preserve their raw evidence. Do not present them as authoritative.
- A behavior pack may be offered only as an optional structured-data enhancement.

## Product and security rules

- Keep the interface responsive, touch-friendly, Minecraft-inspired, and fully available in Portuguese and English.
- Prefer understandable controls and contextual explanations over dense administration forms.
- Do not add generic shell or arbitrary Bedrock-console endpoints.
- Validate all commands and values with explicit allowlists.
- Assume trusted-LAN deployment only until authentication, CSRF, TLS, and restricted Docker access are implemented.
- Keep panel roles independent from Minecraft operator status. Enforce capabilities in the backend, preserve the last owner, hash all passwords and tokens, and never expose session identifiers or credentials in logs.
- Never overwrite `.env`, `data/manager.db`, or Minecraft world data during deployment.
- Keep the embedded telemetry pack under `packs/telemetry/` synchronized from its standalone repository with Git subtree. Pack installation must use the shared installer, persistent Bedrock data, backups, atomic association updates, and explicit restart decisions.

## Quality gate

Run these checks before handing off changes:

```bash
bin/check
```

The same checks are independently runnable as `bin/check-frontend`,
`bin/check-backend`, `bin/check-contracts`, and `bin/check-integration`. Keep a
test in exactly one gate unless a boundary invariant deliberately spans gates.

Update tests and the English `README.md` whenever public behavior, persistence, recovery rules, configuration, or API contracts change.

## Production deployment

- Deploy only with `bin/deploy-craftcontrol` from a clean, published `main`.
- Never run a bare `docker compose up` from a development checkout; relative bind mounts can select development state.
- Run `bin/deploy-craftcontrol --check` before the mutating deployment. The guarded command owns mount validation, coordinated backup and verification, tracked-file synchronization, state checksum checks, rebuild, and production canaries.

## Pull requests and Git history

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution workflow: branch naming, PR title format, metadata requirements (Project, Milestone, Label, Assignee), Conventional Commits, CodeRabbit interaction, and what not to commit.
