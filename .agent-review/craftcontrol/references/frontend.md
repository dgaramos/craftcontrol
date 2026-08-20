# Frontend checklist

- Preserve native ES modules and dependency direction: `core` → `components`
  → `features`; core never imports features.
- Inject feature dependencies through the composition root. Avoid direct global
  DOM coupling when an injected helper exists.
- Keep all visible copy localized in Portuguese, English, and Spanish. Preserve
  touch usability, empty/error states, CSRF behavior, and SSE-driven refreshes;
  do not add browser polling when targeted invalidation is sufficient.
- Escape external content before DOM insertion.
- Keep tests deterministic, restore globals, and avoid time/order coupling.
