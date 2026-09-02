# Claude project guide

Follow `AGENTS.md`. Read the English README, protocol specification, and private ignored roadmap before work. This project is a stable-API, passive Bedrock telemetry pack. It must not alter gameplay, leak XUIDs, depend on the manager being online, or use beta APIs without explicit approval.

When writing or modifying tests:
- Import the Bedrock runtime fake from `tests/minecraft-server.mock.js` — never
  mock `@minecraft/server` inline.
- Use `suppressConsoleWarn()` / `suppressConsoleError()` from `tests/helpers.mjs`
  instead of inline `jest.spyOn(console, ...)` calls.
- `.mjs` fixtures are for end-to-end scenarios; `.test.js` files are for units.
- Never commit files ending in ` 2.js` or ` 2.mjs`.
