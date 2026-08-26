# CraftControl Project Guide

Follow `AGENTS.md` as the authoritative project instruction file. Before working, read `README.md` and all Markdown files in `roadmap/` when present. The `roadmap/` directory is private, ignored planning context and must never be committed, published, or included in deployment copies.

For any PR review, load `.agent-review/craftcontrol/PROFILE.md` and its
applicable layer checklists. This local profile supplies CraftControl-specific
review rules to Claudio DR or any other agent; it augments generic skills and
never triggers review automatically. Use the `claudio-reviewer` agent if
the profile is unavailable.

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
- Keep the UI mobile-first, Minecraft-inspired, understandable to non-specialists,
  and fully available in the supported locales defined by `AGENTS.md`.
- Do not expose arbitrary console commands or weaken the existing allowlists.
- Preserve player-backed local authentication, backend RBAC, one-time hashed invitations, and revocable server-side sessions. Panel roles never imply Minecraft operator status.
- Never overwrite `.env`, the SQLite database, or world data.
- Use `craftcontrol backup` and `docs/backup-and-restore.md` for recovery operations. Never perform a live restore; require explicit confirmation and preserve the pre-restore recovery set.
- Run the quality gate documented in `AGENTS.md` before handoff.
- Follow `CONTRIBUTING.md` for the full PR workflow: branch naming, PR title format, metadata requirements, Conventional Commits, and CodeRabbit interaction.
