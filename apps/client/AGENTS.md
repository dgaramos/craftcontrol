# Project instructions

Read `README.md` and every Markdown file under the ignored `roadmap/` directory
before changing the project.

- No framework, no bundler, no build step. ES modules loaded directly by the
  browser. Do not introduce a transpiler, bundler, or runtime framework without
  an explicit architecture decision.
- All server communication goes through `api.js`. Features must not construct
  fetch calls directly.
- All user-visible strings go through `t()` from `js/i18n/index.js`. Every key
  added to `en.js` must also be added to `pt.js` and `es.js`. A missing key
  fails the quality gate.
- Navigation state is encoded in the URL. Features must not store navigation
  state in memory or localStorage.
- `composition.js` is the single wiring point. Features declare dependencies as
  constructor parameters; they do not import singletons.
- SSE invalidation drives data refresh. Do not add polling when an SSE event and
  targeted reconciliation is sufficient.
- `static/api-contract.d.ts` is generated from the monorepo OpenAPI spec. Do not
  edit it by hand; regenerate it when the API surface changes.
- Pixel-art icons live in the SVG sprites. Do not add raster images or external
  icon libraries.
- Never commit `node_modules/`, coverage output, or roadmap content.

## Testing conventions

**Shared helpers live in `tests/helpers.js`.** DOM builders, stub factories, and
reusable setup belong there — never inline them in a single test file.

**Prefer dependency injection over `jest.spyOn` on platform globals.** When a
feature depends on `localStorage`, `fetch`, or `history`, accept the dependency
as a constructor parameter with a production default. Tests pass a fake object.
Reserve `jest.spyOn` for third-party or platform APIs that cannot be refactored.

**Test files mirror `static/js/` structure.** Put tests for `core/` in
`tests/core/`, shared UI components in `tests/components/`, localisation in
`tests/i18n/`, and feature tests in the matching `tests/features/<domain>/`
directory. Cross-cutting structural checks belong in `tests/contracts/` and
app-level tests that genuinely span modules may remain at `tests/`. Do not
create test files at an unrelated path.

**One concern per test file.** Contract tests (`*-contracts.test.js`) verify the
API shape; feature tests (`*-feature.test.js`) verify behaviour. Keep them
separate so a contract change doesn't force rewriting behaviour tests.

Run `../../bin/check-frontend` and `git diff --check` before handoff.

## Local development

A zero-dependency dev proxy serves the frontend against any running backend:

```bash
# First-time setup — copy and edit the env file:
cp apps/client/.env.example apps/client/.env
# edit CRAFTCONTROL_BACKEND to point at your backend

# Or manage it with the local-env dotfiles tool (no .env file needed):
local-env set CRAFTCONTROL_BACKEND http://192.168.15.50:8082

# Start the proxy (from the repo root):
cd apps/client && npm run dev
# → http://localhost:3333
```

The proxy serves `apps/client/static/` and `apps/client/templates/` locally and
forwards `/api/*` and `/metrics` to the configured backend. Changes to CSS and JS
are picked up on the next browser reload — no rebuild required.

`PORT` overrides the default listen port (3333). Both vars can also be exported
directly in the shell; env vars take precedence over the `.env` file.
