# Frontend/backend deployment split

CraftControl runs as the independently deployable **CraftControl Client** and
**CraftControl Server** images inside the same repository and Compose project.
The target preserves one public origin: the Client serves the browser
application and proxies `/api/*`, including `/api/events`, to the Server over
the private Compose network.

## Current ownership inventory

The Client now lives under `apps/client/` and contains templates, static
files, browser-side API and authentication code, localization, and visual
assets. Flask still serves the index template and `/static/*` from that
application directory as compatibility behavior.

The Server now lives under `apps/server/` and contains the Python package,
entry points, dependencies, SQLite, authentication and CSRF enforcement, the
SSE stream, Bedrock and Docker adapters, telemetry ingestion, pack lifecycle,
and coordinated backups. Root entry points and package links remain temporary
compatibility facades. Only the backend service may receive persistent
or privileged mounts.

`packages/contracts/openapi.json` is the canonical OpenAPI 3.1 description of
the business API. The authenticated `/api/docs` interface serves a bundled
Swagger UI from the backend and reuses the active session and CSRF protections.
`packages/contracts/http-surface.json` remains a route-level characterization
guard: tests compare it with Flask's real URL map, ensure browser calls remain
within `/api`, and require the documented business methods to stay aligned.
Stable OpenAPI schemas also generate
`apps/client/static/js/api-contract.d.ts`; a deterministic check prevents the
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
- Retain the former single-service image only as a tested emergency rollback.

## Guarded deployment

`bin/deploy-craftcontrol-release` is the coordinated production entrypoint;
the frontend and backend commands deploy one component. All refuse dirty or
unpublished source, validate the active split topology, and run boundary-aware
canaries. Backend replacement and rollback always create a verified coordinated
backup first.

## Phase sequence

1. Freeze the current HTTP surface and document ownership.
2. Extract the static frontend while Flask compatibility serving remains.
3. Extract the Python backend behind the same-origin frontend proxy.
4. Publish versioned OpenAPI and authenticated Swagger documentation while
   retaining the characterization manifest as a migration guard.
5. Generate frontend API declarations and validate representative backend
   responses against the published schemas.
6. Run frontend, backend, contract, and integration quality gates independently.
7. Complete: build, deploy, health-check, and roll back both images independently. The
   pinned release pair, guarded frontend/backend deploy and rollback commands,
   and coordinated release command are implemented.
8. Complete: authenticated session continuity, CSRF, SSE, backup, SQLite
   invariants, automatic failure recovery, and explicit compatibility rollback
   are enforced by the cutover workflow.

## CraftControl Host Agent execution boundary

The split topology introduces an optional privileged-execution boundary between
the backend container and the Docker daemon. When `BEDROCK_PROXY_URL` is set in the
backend's environment, the composition root wires `HostAgentContainerOperations`
instead of the direct `DockerOperations` adapter:

```text
Backend container
  └── ContainerOperations (HTTP)
        └── craftcontrol-bedrock-proxy (systemd, Docker host)
              ├── PREPARATION — writes configuration files
              ├── RESTART     — docker compose restart minecraft-server
              └── HEALTH_WAIT — Bedrock UDP health probe
```

The backend still mounts the Docker socket for Bedrock console operations
(`BedrockClient`): attaching to the container stdin, streaming logs, and
receiving Docker events. These operations are not part of the bedrock-proxy contract
and are not delegated.

The two adapters coexist in the codebase. Configuration selects exactly one
`ContainerOperations` implementation:

| `BEDROCK_PROXY_URL` set? | Adapter |
|---|---|
| Yes | `HostAgentContainerOperations` (HTTP, delegates to agent) |
| No | `DockerOperations` (direct Compose, no agent required) |

The adapter switch is invisible to application services and use cases: both
satisfy the same `ContainerOperations` port. SQLite persistence, event delivery,
SSE publication, and operation evidence remain owned by the backend regardless
of which adapter is selected.

### Required backend configuration (split mode with host agent)

| Variable | Where set | Description |
|---|---|---|
| `BEDROCK_PROXY_URL` | backend environment | Base URL the backend uses to reach the agent, e.g. `http://host-gateway:7890`. |
| `BEDROCK_PROXY_TOKEN_FILE` | backend environment | Path to the shared-secret file inside the container, e.g. `/run/bedrock-proxy-token`. |
| `BEDROCK_PROXY_HEALTH_TIMEOUT_SECONDS` | backend environment | Health-wait deadline sent to the agent for each lifecycle operation. Default `300`; accepted range: 10–600. |
| `BEDROCK_PROXY_RESTART_TIMEOUT_SECONDS` | backend environment | Compose restart deadline sent to the agent for each lifecycle operation. Default `180`; accepted range: 10–300. |

The token file is mounted from the host via a bind mount or Docker secret. Its
value must match the secret file read by the agent on the host side. See
`docs/bedrock-proxy-contract.md` for key distribution and token rotation procedures.

Never set the token value as a plain environment variable; always use a file
mount. No token value may appear in logs, API responses, or the `.env` file.

### Failure behavior

The backend follows the failure protocol described in `docs/bedrock-proxy-contract.md`:

- **Pre-delivery failures** (connection refused, connect timeout before TCP handshake) — the request was never delivered; the operation is failed immediately with `error_code: executor_internal_error`.
- **Post-delivery ambiguous failures** (read-phase timeout after TCP handshake, or an OSError after delivery) — the request may have been delivered; the backend retries `GET /v1/status/{operation_id}` up to three times before concluding the result is ambiguous and failing the operation with `error_code: executor_internal_error`.
- **Successful completion** — the agent returns `status: done` with `outcome: ok` or `outcome: error`; the backend records the structured `error_code` and transitions the operation accordingly.

In all failure paths the operation is transitioned to FAILED and SSE delivers `operation.failed`. Transport details, agent addresses, filesystem paths, and container names are sanitized before being stored in `terminal_error` or returned in public API responses — no host internals are exposed in the UI.

## Independent quality gates

`bin/check-frontend`, `bin/check-backend`, `bin/check-contracts`, and
`bin/check-integration` partition the test suite by ownership. `bin/check` is
the local umbrella gate and also checks patch whitespace. GitHub Actions and
Gitea Actions execute the four boundaries as separate jobs with fail-fast
disabled, so one failure does not hide results from the other applications.

## Split-image production topology

`apps/client/Dockerfile` builds a static, read-only Nginx image. It owns the
public origin and forwards `/api/*` to `craftcontrol-backend` on the private
Compose network. The dedicated `/api/events` location disables proxy buffering
and caching, retains a long read timeout, and passes reconnect headers. Docker's
embedded DNS is resolved dynamically so recreating only the backend does not
leave the frontend pinned to an obsolete container address.

`apps/server/Dockerfile` contains the CraftControl Server Flask application,
OpenAPI contracts, CraftControl Telemetry Pack, and operations CLI, but no
CraftControl Client files. In
`docker-compose.split.yml`, only this service receives SQLite, Bedrock, backup,
and Docker access; it has no host-published port. The production frontend uses port
`8082`; the backend has no host-published port.

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

The coordinated command first prepares both images, retrying each build up to
three times when a registry or DNS failure is transient. It only begins service
replacement after both images are ready, then deploys the backend while the
static frontend continues serving and replaces the frontend without touching the
new backend. Rollback versions are always explicit; an arbitrary unpinned image
is never inferred from a mutable tag.
