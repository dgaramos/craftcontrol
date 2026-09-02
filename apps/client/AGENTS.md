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

Run `../../bin/check-frontend` and `git diff --check` before handoff.
