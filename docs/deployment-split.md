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
6. Run frontend, backend, contract, and integration quality gates independently.
7. Build, deploy, health-check, and roll back both images independently. The
   pinned release pair, guarded frontend/backend deploy and rollback commands,
   and coordinated release command are implemented. Production cutover still
   waits for the phase-eight state, session, CSRF, SSE, and rollback canaries.

## Independent quality gates

`bin/check-frontend`, `bin/check-backend`, `bin/check-contracts`, and
`bin/check-integration` partition the test suite by ownership. `bin/check` is
the local umbrella gate and also checks patch whitespace. GitHub Actions and
Gitea Actions execute the four boundaries as separate jobs with fail-fast
disabled, so one failure does not hide results from the other applications.

## Split-image preview

`apps/frontend/Dockerfile` builds a static, read-only Nginx image. It owns the
public origin and forwards `/api/*` to `craftcontrol-backend` on the private
Compose network. The dedicated `/api/events` location disables proxy buffering
and caching, retains a long read timeout, and passes reconnect headers. Docker's
embedded DNS is resolved dynamically so recreating only the backend does not
leave the frontend pinned to an obsolete container address.

`apps/backend/Dockerfile` contains the Flask application, OpenAPI contracts,
Telemetry Pack, and operations CLI, but no frontend files. In
`docker-compose.split.yml`, only this service receives SQLite, Bedrock, backup,
and Docker access; it has no host-published port. The preview frontend uses port
`18082`, keeping the current production service untouched.

`bin/check-split-runtime` starts both images against disposable container-local
state, checks the index and static assets, proxies health and authentication,
verifies unbuffered SSE headers, recreates the backend, and proves the existing
frontend reconnects through dynamic service discovery. It never mounts the
production database, world, `.env`, backups, or Docker socket.

## Independent frontend releases

`versions.env` is the reviewed compatibility pair for the two images. The
frontend exposes the actual image version through an uncacheable
`/version.json`; the browser displays it independently from the API and pack.
After the split topology becomes active, use:

```bash
bin/deploy-craftcontrol-frontend --check
bin/deploy-craftcontrol-frontend
bin/deploy-craftcontrol-frontend --rollback 0.1.0
```

The command requires clean, published `main`, the production split Compose
file, and both live split containers. It replaces the frontend with
`--no-deps`, verifies frontend health and same-origin API/auth proxying, and
asserts that neither the backend container ID nor the SQLite checksum changed.
It refuses the current compatibility topology so this capability cannot bypass
the remaining cutover canaries.

## Independent backend and coordinated releases

The backend follows the same clean, published-main and active-topology guards:

```bash
bin/deploy-craftcontrol-backend --check
bin/deploy-craftcontrol-backend
bin/deploy-craftcontrol-backend --rollback 0.1.0
```

Before either a forward deploy or rollback, it creates and verifies a
coordinated world/SQLite backup. It then replaces only the backend, confirms
the frontend container identity did not change, revalidates `/data` and
Bedrock mount sources, runs SQLite `quick_check`, and exercises health,
anonymous authentication, backup CLI, and Bedrock canaries through the public
frontend origin.

For a tested pair, use:

```bash
bin/deploy-craftcontrol-release --check
bin/deploy-craftcontrol-release
bin/deploy-craftcontrol-release --rollback 0.1.0 0.1.0
```

The coordinated command deploys the backend first while the static frontend
continues serving, then replaces the frontend without touching the new
backend. Rollback versions are always explicit; an arbitrary unpinned image is
never inferred from a mutable tag.
