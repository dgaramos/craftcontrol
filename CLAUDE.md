# CraftControl Project Guide

Follow `AGENTS.md` as the authoritative rule set for this repository.
Before working, read `README.md` and all Markdown files in `roadmap/` when present.
The `roadmap/` directory is private planning context — never commit, quote, or publish it.

Key constraints:

- This is Minecraft Bedrock, not Java Edition.
- Preserve the layered Python package under `apps/server/controlplane/`; do not collapse it into `app.py`.
- Use constructor injection and manual composition; do not introduce a DI container or service locator.
- Never overwrite `.env`, the SQLite database, or world data.
- Keep all visible UI copy localized in every supported locale defined by `AGENTS.md`.
- Do not expose arbitrary console commands or weaken existing allowlists.
- **Backend module placement:** New backend implementation modules must not be created in the `controlplane` package root. Owning modules: `core/`, `server/`, `players/`, `telemetry/`, `operations/`, `runtime/`, `http/`, `auth/`, `audit/`. Compatibility facades may preserve an existing import path only; new behavior belongs in the owning module. The architecture-test allowlist is the temporary, reviewed exception list. See `AGENTS.md` for the full mapping.
- For any PR review, load `.dr-agents/craftcontrol/PROFILE.md`.

See `AGENTS.md` for architecture boundaries, test placement, module placement, secrets policy, and the quality gate.
