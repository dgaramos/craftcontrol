# Frontend Tests

Jest test suite for `apps/client/static/js/`. Run from the repo root:

```bash
bin/check-frontend
```

Or directly:

```bash
cd apps/client && npm test
```

## Two kinds of tests

### Behavioral tests

Test that a module does the right thing at runtime. They import the module under test, supply mock dependencies, call functions, and assert on outputs or side effects.

Files mirror the module they exercise: for example,
`features/analytics/activity-view.test.js`,
`features/players/players-access.test.js`, and
`features/settings/settings-feature.test.js`.

These tests use `jest.fn()` mocks and live alongside the modules they exercise. They are the primary signal for correctness regressions.

### Structural contract tests

Test that the source file of a module contains expected exports, imports, class names, or strings — without executing it. They use `readFileSync` to read the `.js` source as text and assert on its content.

Files live in `contracts/`: `brand-contracts.test.js`,
`analytics-contracts.test.js`, `players-contracts.test.js`,
`auth-contracts.test.js`, `i18n-contracts.test.js`, and
`feature-contracts.test.js`.

These tests guard architectural boundaries: that a feature module exports its factory, that composition does not inline logic that belongs in a sub-module, that a bug fix is not accidentally reverted. They run fast (no imports, no mocks) and are stable across refactors that preserve the named exports.

## Shared infrastructure

`helpers.js` is the single home for reusable DOM builders, stub factories, and
test setup. Keep a helper local only when it serves one test module; promote it
here when a second module needs it.

**When to write a structural contract test:** when a bug was caused by a missing export, an undefined reference passed as a dependency, or an architectural invariant that behavioral tests cannot easily express (e.g. "this function must not exist in composition.js").

## Non-JS asset tests

Tests for SVG sprites, webmanifest, HTML templates, README, and docker-compose live in `apps/server/tests/test_brand.py` (Python/pytest) because they require XML parsing or cover artifacts outside the JS module graph. They are not duplicated here.
