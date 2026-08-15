# CraftControl Project Guide

Follow `AGENTS.md` as the authoritative project instruction file. Before working, read `README.md` and all Markdown files in `roadmap/` when present. The `roadmap/` directory is private, ignored planning context and must never be committed, published, or included in deployment copies.

Key constraints:

- This is Minecraft Bedrock, not Java Edition.
- The service targets a trusted homelab LAN and manages `itzg/minecraft-bedrock-server`.
- Preserve the layered Python package under `apps/backend/minecraft_manager/`; do not collapse the application into `app.py`.
- Read and follow `docs/architecture.md`. CraftControl is a modular monolith with layered use cases, meaningful ports and adapters, and an internal event-driven runtime.
- Use constructor injection and manual composition. Define replaceable boundaries with `typing.Protocol`; do not introduce a DI container, service locator, or one interface per class.
- Keep dependencies directed from HTTP to application services to ports/adapters. Runtime code must not reach through services into repositories.
- Preserve event-driven synchronization, SSE, SQLite history, and exporter independence.
- Player disconnects change status to offline and close sessions; they never delete profiles.
- XUID stays internal. Player history is durable. Log-derived deaths are explicitly non-authoritative.
- Keep the UI mobile-first, Minecraft-inspired, bilingual, and understandable to non-specialists.
- Do not expose arbitrary console commands or weaken the existing allowlists.
- Preserve player-backed local authentication, backend RBAC, one-time hashed invitations, and revocable server-side sessions. Panel roles never imply Minecraft operator status.
- Never overwrite `.env`, the SQLite database, or world data.
- Use `craftcontrol backup` and `docs/backup-and-restore.md` for recovery operations. Never perform a live restore; require explicit confirmation and preserve the pre-restore recovery set.
- Run the quality gate documented in `AGENTS.md` before handoff.
- Use Conventional Commits for every commit: `type(scope): imperative summary`. Verify the final subject before pushing; never publish a non-conforming message for later cleanup.
- All changes must go through a pull request. Do not push directly to `main`. CodeRabbit reviews every PR automatically; address its findings before merging.
- Name branches with the issue number as prefix: `{issue-number}-{type}/{short-description}` (e.g. `42-feat/player-history`).
- Include the issue number in the PR title: `type(scope): description (#issue-number)` (e.g. `feat(players): add history view (#42)`).
- Follow `.github/pull_request_template.md` when writing PR descriptions.
