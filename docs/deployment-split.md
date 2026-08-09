# Frontend/backend deployment split

CraftControl is migrating from one image to two independently deployable images
inside the same repository and Compose project. The target preserves one public
origin: the frontend serves the browser application and proxies `/api/*`,
including `/api/events`, to the backend over the private Compose network.

## Current ownership inventory

The frontend now lives under `apps/frontend/` and contains templates, static
files, browser-side API and authentication code, localization, and visual
assets. Flask still serves the index template and `/static/*` from that
application directory as compatibility behavior.

The backend now lives under `apps/backend/` and contains the Python package,
entry points, dependencies, SQLite, authentication and CSRF enforcement, the
SSE stream, Bedrock and Docker adapters, telemetry ingestion, pack lifecycle,
and coordinated backups. Root entry points and package links remain temporary
compatibility facades. Only the future backend service may receive persistent
or privileged mounts.

`packages/contracts/http-surface.json` freezes the methods and paths at the
start of the migration. Tests compare that inventory with Flask's real URL map
and ensure browser calls remain within `/api`. It is a characterization
manifest, not yet the final OpenAPI description.

## Compatibility requirements

- Keep the existing public hostname and same-origin session cookies.
- Proxy API and SSE traffic without buffering or changing reconnect headers.
- Preserve CSRF headers and Origin validation across the internal proxy.
- Never mount `.env`, SQLite, Bedrock data, backups, or the Docker socket in the
  frontend service.
- Version, deploy, health-check, and roll back frontend and backend separately.
- Pin a tested frontend/backend compatibility pair for coordinated releases.
- Preserve the single-service deployment until independent backup, rollback,
  authentication, SSE, and state-preservation canaries pass.

## Phase sequence

1. Freeze the current HTTP surface and document ownership.
2. Extract the static frontend while Flask compatibility serving remains.
3. Extract the Python backend behind the same-origin frontend proxy.
4. Replace the characterization manifest with versioned OpenAPI and generated
   frontend types.
5. Build, deploy, health-check, and roll back both images independently.
