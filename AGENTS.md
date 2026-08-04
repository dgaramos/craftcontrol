# Project Instructions

## Purpose

Maintain CraftControl, a mobile-first, bilingual control panel for Minecraft Bedrock servers. The application must remain usable without Prometheus, Grafana, the custom exporter, or a behavior pack.

## Required context

Before planning, reviewing, or changing this project, read `README.md` and every Markdown file under the local `roadmap/` directory when that directory exists. The roadmap is private operational context: do not stage, commit, publish, quote, or copy it into deployment artifacts.

## Architecture

- Treat `docs/architecture.md` as the authoritative architecture and dependency-direction reference.
- Keep CraftControl a modular monolith: organize by domain, retain layered use cases inside modules, and use ports/adapters only at meaningful persistence and infrastructure boundaries.
- Inject dependencies through constructors and assemble production implementations in the composition root. Use `typing.Protocol` for replaceable boundaries; do not add a DI framework, service locator, or redundant interface for every concrete service.
- Runtime supervisors must call application-facing ports and must never reach through a service to its repository or adapter.
- Keep HTTP mapping in `minecraft_manager/routes.py`, orchestration in `services.py`, event ingestion in `runtime.py`, persistence in `repository.py`, and Bedrock/Docker/filesystem concerns in their adapters.
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
- Never overwrite `.env`, `data/manager.db`, or Minecraft world data during deployment.
- Keep the embedded telemetry pack under `packs/telemetry/` synchronized from its standalone repository with Git subtree. Pack installation must use the shared installer, persistent Bedrock data, backups, atomic association updates, and explicit restart decisions.

## Quality gate

Run these checks before handing off changes:

```bash
python -m unittest discover -s tests -v
python -m compileall -q minecraft_manager app.py wsgi.py
node --check static/app.js
node --check static/js/api.js
node --check static/js/events.js
docker compose config --quiet
git diff --check
```

Update tests and the English `README.md` whenever public behavior, persistence, recovery rules, configuration, or API contracts change.
