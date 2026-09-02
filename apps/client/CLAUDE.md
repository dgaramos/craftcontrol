# Claude project guide

Follow `AGENTS.md`. Read `README.md` and the private ignored `roadmap/` before
work. This is a dependency-free ES module UI — no framework, no bundler, no
build step. Keep it that way. All user-visible strings must go through the i18n
system; all three supported locales (English, Portuguese, Spanish) must stay in
sync.

When writing or modifying tests:
- Shared helpers and DOM builders belong in `tests/helpers.js`.
- Prefer constructor injection over `jest.spyOn` on platform globals
  (`localStorage`, `fetch`, `history`).
- Test files mirror the `static/js/` structure; keep contract tests and feature
  tests in separate files.
