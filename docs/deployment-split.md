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

`packages/contracts/openapi.json` is the canonical OpenAPI 3.1 description of
the business API. The authenticated `/api/docs` interface serves a bundled
Swagger UI from the backend and reuses the active session and CSRF protections.
`packages/contracts/http-surface.json` remains a route-level characterization
guard: tests compare it with Flask's real URL map, ensure browser calls remain
within `/api`, and require the documented business methods to stay aligned.
Stable OpenAPI schemas also generate
`apps/frontend/static/js/api-contract.d.ts`; a deterministic check prevents the
browser declarations and backend contract from drifting. Representative Flask
responses are validated against the same published schemas.

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

## Guarded deployment

`bin/deploy-craftcontrol` is the only supported production update entrypoint.
It uses an explicit Compose project directory and file, refuses a dirty or
non-`main` source checkout, validates the live `/data` and
`/minecraft-project` mount sources before backup, verifies the coordinated
backup, synchronizes only tracked files, proves `.env` and SQLite checksums were
preserved, and exercises frontend, API, anonymous authentication, CLI, and
Bedrock canaries. `--check` performs the non-mutating preflight only.

## Phase sequence

1. Freeze the current HTTP surface and document ownership.
2. Extract the static frontend while Flask compatibility serving remains.
3. Extract the Python backend behind the same-origin frontend proxy.
4. Publish versioned OpenAPI and authenticated Swagger documentation while
   retaining the characterization manifest as a migration guard.
5. Generate frontend API declarations and validate representative backend
   responses against the published schemas.
6. Build, deploy, health-check, and roll back both images independently.
