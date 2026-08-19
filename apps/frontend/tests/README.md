# Frontend Tests

Jest test suite for `apps/frontend/static/js/`. Run from the repo root:

```bash
bin/check-frontend
```

Or directly:

```bash
cd apps/frontend && npm test
```

## Two kinds of tests

### Behavioral tests

Test that a module does the right thing at runtime. They import the module under test, supply mock dependencies, call functions, and assert on outputs or side effects.

Files: `activity-view.test.js`, `analytics-branches.test.js`, `players-access.test.js`, `settings-feature.test.js`, etc.

These tests use `jest.fn()` mocks and live alongside the modules they exercise. They are the primary signal for correctness regressions.

### Structural contract tests

Test that the source file of a module contains expected exports, imports, class names, or strings — without executing it. They use `readFileSync` to read the `.js` source as text and assert on its content.

Files: `brand-contracts.test.js`, `composition-contracts.test.js`, `analytics-contracts.test.js`, `players-contracts.test.js`, `auth-contracts.test.js`, `i18n-contracts.test.js`, `feature-contracts.test.js`.

These tests guard architectural boundaries: that a feature module exports its factory, that composition does not inline logic that belongs in a sub-module, that a bug fix is not accidentally reverted. They run fast (no imports, no mocks) and are stable across refactors that preserve the named exports.

**When to write a structural contract test:** when a bug was caused by a missing export, an undefined reference passed as a dependency, or an architectural invariant that behavioral tests cannot easily express (e.g. "this function must not exist in composition.js").

## Non-JS asset tests

Tests for SVG sprites, webmanifest, HTML templates, README, and docker-compose live in `tests/test_brand.py` (Python/pytest) because they require XML parsing or cover artifacts outside the JS module graph. They are not duplicated here.
