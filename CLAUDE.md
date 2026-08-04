# CraftControl Project Guide

Follow `AGENTS.md` as the authoritative project instruction file. Before working, read `README.md` and all Markdown files in `roadmap/` when present. The `roadmap/` directory is private, ignored planning context and must never be committed, published, or included in deployment copies.

Key constraints:

- This is Minecraft Bedrock, not Java Edition.
- The service targets a trusted homelab LAN and manages `itzg/minecraft-bedrock-server`.
- Preserve the layered Python package; do not collapse the application into `app.py`.
- Preserve event-driven synchronization, SSE, SQLite history, and exporter independence.
- Player disconnects change status to offline and close sessions; they never delete profiles.
- XUID stays internal. Player history is durable. Log-derived deaths are explicitly non-authoritative.
- Keep the UI mobile-first, Minecraft-inspired, bilingual, and understandable to non-specialists.
- Do not expose arbitrary console commands or weaken the existing allowlists.
- Never overwrite `.env`, the SQLite database, or world data.
- Run the quality gate documented in `AGENTS.md` before handoff.
