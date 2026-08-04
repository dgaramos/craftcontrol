# Project instructions

Read `README.md`, `docs/protocol.md`, and every Markdown file under the ignored `roadmap/` directory before changing the project.

- This is a passive Minecraft Bedrock behavior pack, not a Java Edition plugin or independent runtime service.
- Use stable `@minecraft/server` APIs only. Do not enable experimental toggles without explicit approval.
- Do not change gameplay, expose commands to players, collect chat, or persist inventory contents.
- Never emit XUIDs. Player names are correlated to private identities by the manager.
- Persist authoritative aggregates in world dynamic properties and treat log events as a delivery mechanism.
- Keep the pack functional when the manager is offline and support full snapshot reconciliation.
- Preserve schema-versioned envelopes and idempotent sequence handling.
- Keep high-cardinality maps bounded and movement sampling conservative.
- Installation must be reversible and must back up `world_behavior_packs.json`.
- Never commit or package `roadmap/`.

Run `npm test`, syntax checks, manifest validation, and `git diff --check` before handoff.
