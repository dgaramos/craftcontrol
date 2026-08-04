# Project Instructions

## Purpose

Maintain CraftControl, a mobile-first, bilingual control panel for Minecraft Bedrock servers. The application must remain usable without Prometheus, Grafana, the custom exporter, or a behavior pack.

## Required context

Before planning, reviewing, or changing this project, read `README.md` and every Markdown file under the local `roadmap/` directory when that directory exists. The roadmap is private operational context: do not stage, commit, publish, quote, or copy it into deployment artifacts.

## Architecture

- Keep HTTP mapping in `minecraft_manager/routes.py`, orchestration in `services.py`, event ingestion in `runtime.py`, persistence in `repository.py`, and Bedrock/Docker/filesystem concerns in their adapters.
- Preserve the internal event broker, persisted operational events, SSE browser updates, targeted refreshes, and periodic full reconciliation.
- Keep one Gunicorn worker unless the process-local broker and runtime supervisors are redesigned for multiple workers.
- Do not add browser polling when an event-driven invalidation and targeted reconciliation is sufficient.
- Keep the manager independent from the exporter and observability stack.
- Use SQLite for local durable state and schema changes that migrate existing databases without deleting user data.

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

## Quality gate

Run these checks before handing off changes:

```bash
python -m unittest discover -s tests -v
python -m compileall -q minecraft_manager app.py wsgi.py
node --check static/app.js
docker compose config --quiet
git diff --check
```

Update tests and the English `README.md` whenever public behavior, persistence, recovery rules, configuration, or API contracts change.
