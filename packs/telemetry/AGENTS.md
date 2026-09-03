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

## Testing conventions

**`tests/minecraft-server.mock.js` is the Bedrock runtime fake.** It provides
`world`, `system`, and event signals. All tests import from it via Jest module
mapping — never mock `@minecraft/server` inline.

**Tests mirror production ownership.** Adapter tests live in
`tests/adapters/`, domain tests in `tests/domain/`, and full-runtime runners
and `.fixture.mjs` scenarios in `tests/runtime/`. Keep package-level boundary
tests for `main.js`, `model.js`, and `migrations.js` at `tests/`; installer
tests live in `tests/scripts/`.

**`.mjs` fixtures are integration scenarios.** Files like `runtime.fixture.mjs`
and `flush-blocked.fixture.mjs` run the full pack against the fake runtime and
assert on observable output (console lines, HTTP calls). Add a new fixture for
each distinct end-to-end scenario; keep unit tests in `.test.js` files.

**`jest.fn()` is the right tool for injected collaborators.** The pack modules
accept collaborators as constructor or function parameters — pass `jest.fn()`
stubs directly. Do not use `jest.mock()` on internal pack modules.

**Suppress console noise with a helper, not inline spies.** The pattern
`jest.spyOn(console, "warn").mockImplementation(() => {})` is repeated across
many tests. Extract it as `suppressConsoleWarn()` (and `suppressConsoleError()`)
in a shared `tests/helpers.mjs` file. New tests must use the helper; migrate
existing tests when a file is touched.

**Use shared builders for recurring telemetry data.** `tests/factories.mjs`
owns explicit-override builders for persisted metadata, player snapshots,
player shards, protocol envelopes, and captured telemetry log records.

**Never commit duplicate files.** Files ending in ` 2.js` or ` 2.mjs` are
copy artifacts — delete them before committing.

Run `npm test`, syntax checks, manifest validation, and `git diff --check` before handoff.
