# Host Agent Inter-Process Contract

This document is the authoritative design contract for the channel between
CraftControl and the host agent introduced by
[#228](https://github.com/dgaramos/craftcontrol/issues/228). Both sides must
be implementable independently from this document alone.

---

## Scope

The host agent is a minimal service deployed on the Docker host (outside all
containers). It accepts authenticated requests from the CraftControl backend,
executes exactly the permitted host-level operations (Docker Compose restarts
and host filesystem reads), and returns structured evidence that conforms to the
[operation lifecycle contract](operation-lifecycle.md).

The host agent is an **executor** in the lifecycle contract's terminology: it is
responsible for the `PREPARATION`, `RESTART`, and `HEALTH_WAIT` stages only. It
does not own `operation_id` assignment, RBAC checks, backup verification,
verification, confirmation, or SSE publication — those remain in the application
service.

---

## Threat model

The channel operates on a **trusted homelab LAN**. The relevant threats are:

| Threat | Mitigation |
|--------|-----------|
| A compromised CraftControl container calls the agent with forged requests | Shared-secret token required on every request |
| A process on the host network impersonates CraftControl | Channel restricted to loopback (`127.0.0.1`) — not reachable from the container network or the LAN |
| A credential file is readable by the wrong user | Secret file owned by the agent OS user, mode `0600` |
| Token is compromised and must be rotated | Rotation procedure documented below without requiring a code change |
| The agent is restarted and loses in-flight state | Caller retries with the same `operation_id`; idempotency is documented per operation |

mTLS is a valid future hardening option but is out of scope here. The loopback
restriction plus a shared secret satisfies the homelab threat model without the
operational overhead of a PKI.

---

## Transport

The agent exposes an **HTTP/1.1 server bound to `127.0.0.1` on a configurable
port** (default `7890`). Unix sockets were considered and rejected: they require
the socket path to be accessible from inside the CraftControl container, which
either demands a bind mount of `/var/run` or a dedicated socket directory.
Loopback HTTP avoids that constraint while preserving the same effective network
isolation, because `127.0.0.1` is not reachable from the container network
without an explicit port mapping.

The CraftControl backend reaches the agent via the Docker host gateway address
visible from inside the container (typically `host-gateway`, configured in
`docker-compose.yml` as an extra host). The agent itself is not part of any
Docker network.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_AGENT_URL` | `http://host-gateway:7890` | Base URL the backend uses to reach the agent. |
| `HOST_AGENT_TOKEN_FILE` | `/run/secrets/host_agent_token` | Path to the shared-secret file, read at startup. |
| `HOST_AGENT_BIND` | `127.0.0.1:7890` | Address the agent listens on (agent side). |
| `HOST_AGENT_SECRET_FILE` | `/etc/craftcontrol/host-agent-token` | Path to the token file on the host (agent side). |

---

## Authentication

### Mechanism

Every request from the backend to the agent carries a bearer token in the
`Authorization` header:

```http
Authorization: Bearer <token>
```

The token is a randomly generated secret shared between the backend and the
agent. It is **not** a JWT; it is an opaque string of at least 32 URL-safe
base64 characters (256 bits of entropy from `secrets.token_urlsafe(32)` or
equivalent).

The agent compares the received token to the value loaded from its secret file
using a constant-time comparison (`hmac.compare_digest` or equivalent). A
missing or mismatched token returns `401 Unauthorized` with the body:

```json
{"error": "unauthorized", "message": "Invalid or missing token"}
```

### Key distribution

1. Generate the token on the host before deploying the agent:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))" \
     | sudo tee /etc/craftcontrol/host-agent-token
   sudo chmod 600 /etc/craftcontrol/host-agent-token
   sudo chown craftcontrol-agent:craftcontrol-agent /etc/craftcontrol/host-agent-token
   ```

2. Store the same token where the backend can read it. In the Docker Compose
   deployment, mount it as a secret or environment variable:

   ```yaml
   secrets:
     host_agent_token:
       file: /etc/craftcontrol/host-agent-token
   ```

   Inside the backend container the file is available at the path configured in
   `HOST_AGENT_TOKEN_FILE`.

3. The backend reads the token once at startup from the file. No token value
   appears in environment variables, logs, or API responses.

### Token rotation

Rotation requires no code change:

1. Generate a new token and write it to `/etc/craftcontrol/host-agent-token`
   on the host.
2. Update the backend secret source (Docker secret or bind mount) to point to
   the new value.
3. Restart the host agent (`sudo systemctl restart craftcontrol-host-agent`).
4. Restart the CraftControl backend (`bin/deploy-craftcontrol`).

There is no overlap window: the agent begins rejecting the old token as soon as
it restarts. Schedule the rotation during a planned maintenance window.

---

## Operations

The agent exposes exactly three endpoints. All request and response bodies are
`application/json`.

### `POST /v1/execute`

Initiate a server operation (PREPARATION + RESTART + HEALTH_WAIT).

#### Request

```json
{
  "operation_id": "<UUID v4>",
  "intended_state": {
    "server_name": "My Server",
    "difficulty": "normal",
    "max_players": 10,
    "gamemode": "survival"
  },
  "health_timeout_seconds": 120
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `operation_id` | UUID string | yes | Stable correlation identifier assigned by the application service. Included in all agent logs and audit records. |
| `intended_state` | object | yes | Configuration snapshot the agent must apply. Shape matches the existing settings schema; see `packages/contracts/openapi.yaml` for field definitions. |
| `health_timeout_seconds` | integer | no | Seconds to wait for the health probe to confirm server readiness. Default `120`. |

#### Idempotency

If `execute` is called a second time with the same `operation_id` while the
first call is still running, the agent returns `409 Conflict`:

```json
{"error": "conflict", "operation_id": "<UUID>", "message": "Operation already in progress"}
```

If `execute` is called with the same `operation_id` after the first call
completed, the agent returns the stored result immediately (idempotent replay).
Results are retained for at least 10 minutes.

#### Response — `202 Accepted`

The call returns immediately after accepting the request. The caller polls
`GET /v1/status/{operation_id}` for the result.

```json
{"operation_id": "<UUID>", "status": "accepted"}
```

#### Response — `400 Bad Request`

Returned when the request body is malformed, a required field is missing, or
`intended_state` contains an unrecognised field.

```json
{"error": "bad_request", "message": "<human-readable description>"}
```

---

### `GET /v1/status/{operation_id}`

Poll the result of a previously submitted operation.

#### Response — `200 OK` (terminal)

```json
{
  "operation_id": "<UUID>",
  "status": "done",
  "outcome": "ok",
  "executor_ref": "minecraft-bedrock_minecraft-server_1_restart_1720000000",
  "health_reached": true,
  "failed_stage": null,
  "detail": "Server reached healthy state in 43s",
  "error_code": null,
  "exception_type": null
}
```

The `outcome`, `executor_ref`, `health_reached`, `failed_stage`, `detail`,
`error_code`, and `exception_type` fields conform exactly to the
**Executor result shape** defined in
[operation-lifecycle.md — Executor result shape](operation-lifecycle.md#executor-result-shape).
The application service maps these fields to the stage log and operation record
without transformation.

#### Response — `200 OK` (in progress)

```json
{
  "operation_id": "<UUID>",
  "status": "running",
  "current_stage": "HEALTH_WAIT"
}
```

| `current_stage` | Description |
|-----------------|-------------|
| `PREPARATION` | Writing configuration files and staging the Compose project. |
| `RESTART` | Issuing the Compose restart command. |
| `HEALTH_WAIT` | Polling the Bedrock health probe. |

#### Response — `404 Not Found`

Returned when the `operation_id` is not known to the agent.

```json
{"error": "not_found", "operation_id": "<UUID>", "message": "Unknown operation"}
```

---

### `GET /v1/health`

Liveness check for the agent process. Returns `200 OK` with:

```json
{"status": "ok", "version": "<semver>"}
```

No authentication is required for this endpoint; it is used by the systemd
watchdog and by the backend's startup check.

---

## Error codes

The following machine-readable `error_code` values are defined for the
executor result shape. New codes must be added to this table before
implementation.

| Code | Stage | Description |
|------|-------|-------------|
| `preparation_write_failed` | `PREPARATION` | A configuration file could not be written. |
| `preparation_compose_invalid` | `PREPARATION` | The staged Compose configuration failed validation. |
| `restart_command_failed` | `RESTART` | The `docker compose restart` command exited non-zero. |
| `restart_timeout` | `RESTART` | The restart command did not complete within the configured deadline. |
| `health_probe_failed` | `HEALTH_WAIT` | The health probe returned a non-healthy response. |
| `health_probe_timeout` | `HEALTH_WAIT` | The server did not reach healthy state before `health_timeout_seconds`. |
| `executor_internal_error` | any | An unhandled exception occurred in the agent. |

---

## Unavailability handling

When the backend cannot reach the agent (connection refused, timeout, or
`5xx` response from `/v1/execute` or `/v1/status`), it must:

1. Set `outcome: error`, `failed_stage` to the stage that was in progress
   (or `PREPARATION` if the call never connected), `error_code:
   executor_internal_error`, and `detail` to a human-readable connectivity
   description.
2. Transition the operation to `FAILED` via the standard lifecycle path.
3. Emit `operation.failed` over SSE.
4. Not expose host internals (agent address, filesystem paths, or container
   names) in the UI or public API responses.

Agent unavailability is a recoverable failure: the operator may restart the
agent and retry the operation.

---

## Permitted operations

The agent is explicitly **not** a general command runner. The following table
lists every operation the agent may execute. Any request for an operation not
in this table must be rejected with `400 Bad Request`.

| Operation | Trigger | Host privilege required |
|-----------|---------|------------------------|
| Write server configuration files to the Bedrock data directory | `POST /v1/execute` (PREPARATION) | Write access to the Bedrock data path |
| Stage and validate the Compose project file | `POST /v1/execute` (PREPARATION) | Read access to the Compose project directory |
| `docker compose restart minecraft-server` | `POST /v1/execute` (RESTART) | Docker socket access |
| Poll the Bedrock TCP health probe (`nc` or equivalent) | `POST /v1/execute` (HEALTH_WAIT) | Network access to localhost |

No console commands, arbitrary shell execution, world data mutations, or `.env`
file writes are permitted.

---

## Deployment

The agent runs as a **systemd service** on the Docker host, outside all
containers. A minimal unit file is provided under `deploy/host-agent/` (to be
added in #230).

| Property | Value |
|----------|-------|
| Service name | `craftcontrol-host-agent` |
| OS user | `craftcontrol-agent` (no login shell, no sudo) |
| Binds to | `127.0.0.1:7890` |
| Network exposure | Loopback only — not reachable from the LAN or the container network |
| Secret file | `/etc/craftcontrol/host-agent-token`, mode `0600`, owned by `craftcontrol-agent` |
| Docker socket access | Group membership in `docker` for `craftcontrol-agent` |

---

## Relationship to existing code

The backend's existing `ContainerOperations` port
(`apps/backend/minecraft_manager/ports.py`) defines the interface the Compose
adapter currently implements. Issue #231 will add an `HttpHostAgentAdapter` that
implements the same port by calling this agent. No application service or use
case changes are required as long as the adapter returns results in the executor
result shape defined in `docs/operation-lifecycle.md`.

---

## Open questions

None. All design decisions are settled. Implementation may begin.
