# CraftControl Client

Dependency-free browser JavaScript UI for CraftControl. Served as static assets
by an Nginx container that also proxies `/api/*` and SSE streams to the
CraftControl Server.

No build step. No framework. No bundler. ES modules loaded directly by the browser.

---

## Layout

```
apps/client/
├── Dockerfile            # Nginx image — serves static assets, proxies /api/*
├── nginx.conf            # Nginx configuration (SSE unbuffered, gzip, cache headers)
├── static/
│   ├── app.js            # Entry point — bootstraps routing and state
│   ├── composition.js    # Manual dependency wiring (no service locator)
│   ├── events.js         # SSE client — subscribes to server-sent events
│   ├── api.js            # Typed fetch wrapper over /api/*
│   ├── auth.js           # Login, logout, session state
│   ├── js/
│   │   ├── core/         # Shared primitives
│   │   │   ├── dom.js          # DOM helpers
│   │   │   ├── invalidation.js # Cache invalidation via SSE events
│   │   │   ├── navigation.js   # URL-encoded navigation state
│   │   │   ├── render.js       # Reactive render utilities
│   │   │   ├── route.js        # Client-side routing
│   │   │   └── state.js        # In-memory application state
│   │   ├── components/   # Reusable UI components
│   │   │   ├── feedback.js     # Toast / notification component
│   │   │   └── time.js         # Relative time formatting
│   │   ├── features/     # One directory per primary area
│   │   │   ├── analytics/      # Activity, deaths, rankings, blocks, combat, exploration
│   │   │   ├── auth/           # Login flow and session management UI
│   │   │   ├── players/        # Profiles, sessions, permissions, individual telemetry
│   │   │   ├── rules/          # Gamerule controls and review drawer
│   │   │   ├── server/         # Pack management, backups, lifecycle operations
│   │   │   ├── settings/       # Server properties and configuration
│   │   │   └── world/          # World identity, time, weather, and cycles
│   │   └── i18n/         # Internationalisation
│   │       ├── index.js        # i18n loader and t() helper
│   │       ├── en.js           # English strings
│   │       ├── pt.js           # Portuguese (Brazil) strings
│   │       ├── es.js           # Spanish strings
│   │       └── game-terms.js   # Minecraft-specific term overrides
│   ├── api-contract.d.ts # TypeScript declarations for the OpenAPI surface (generated)
│   ├── craftcontrol-mark.svg   # Logo mark
│   ├── craftcontrol-ui.svg     # UI icon sprite
│   ├── craftcontrol-blocks.svg # Block pixel-art sprite
│   ├── craftcontrol-mobs.svg   # Mob pixel-art sprite
│   └── site.webmanifest        # PWA manifest
└── templates/
    └── index.html        # Single HTML shell — all navigation is client-side
```

---

## Architecture rules

- **No framework, no bundler.** ES modules only. The browser loads them directly.
- **No global state.** `state.js` is the single source of truth; features read
  and write through it.
- **SSE-driven invalidation.** The server pushes events over `/api/events`. The
  client invalidates only the affected domain, not the whole page.
- **Constructor injection.** `composition.js` wires features together. Features
  declare their dependencies as constructor parameters — no `import` of singletons
  inside feature modules.
- **i18n required.** Every user-visible string goes through `t()`. The three
  supported locales are English, Portuguese (Brazil), and Spanish. A failing i18n
  check blocks the quality gate.
- **No arbitrary API calls.** All server communication goes through `api.js`.
  Features must not construct fetch calls directly.

---

## Internationalisation

Strings live in `static/js/i18n/{en,pt,es}.js`. To add a new string:

1. Add the key and English value to `en.js`.
2. Add the same key to `pt.js` and `es.js`.
3. Reference it in the template with `data-i18n="key"` or in JS with `t("key")`.

The i18n check (`bin/check-frontend`) fails if any key is missing from any locale.

---

## Testing

```bash
# Full frontend gate (syntax, i18n completeness, interaction and visual-contract tests)
../../bin/check-frontend

# Fast unit subset
npx jest
```

Tests live in `scripts/` (check scripts) and the Jest suite covers DOM
interactions and visual contracts. Requirements: Node.js 18+.

---

## Nginx

`nginx.conf` configures:

- Static asset serving with cache headers.
- `/api/*` proxy to the CraftControl Server (default: `http://server:5000`).
- SSE (`/api/events`) with `proxy_buffering off` and extended timeouts.
- gzip compression for text assets.

The Nginx container has no persistent mounts and no privileged access. It is
the public-facing entry point; the CraftControl Server is private to the
Compose network.

---

## Extracting to a standalone repository

If extracted:

1. Copy `apps/client/` as the project root.
2. Update `nginx.conf` to point `/api/*` at the CraftControl Server's address.
3. `api-contract.d.ts` is generated from `packages/contracts/openapi.json` in the
   monorepo — keep it in sync when the API surface changes.
4. No dependency on `apps/server/` exists in any client source file.
