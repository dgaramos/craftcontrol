---
name: frontend
description: Implement and review CraftControl native JavaScript frontend changes. Use for `apps/frontend/static/js/` and frontend tests.
---

# Frontend

Keep native ESM and explicit dependency injection: features receive `state`, `api`, `$`, `t`, and helpers from `composition.js`; do not import globals or call `document.querySelector` inside features. Localize every visible string through `t()`, preserve PT/EN/ES, escape user content, and keep phone-width behavior. Reuse `apps/frontend/tests/helpers.js`, restore modified globals, and run `bin/check-frontend` and `bin/check`.
