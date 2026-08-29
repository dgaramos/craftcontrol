# Host Agent Inter-Process Contract

This document is the authoritative design contract for the channel between
CraftControl and the host agent introduced by
[#228](https://github.com/dgaramos/craftcontrol/issues/228). Both sides must
be implementable independently from this document alone.

---

## Scope

The host agent is a minimal service deployed on the Docker host (outside all
containers). It accepts authenticated requests from the CraftControl Server,
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

The agent exposes an **HTTP/1.1 server on a configurable address and port**
(default bind `0.0.0.0:7890`). Unix sockets were considered and rejected: they
require the socket path to be accessible from inside the CraftControl container,
which either demands a bind mount of `/var/run` or a dedicated socket directory.

On Linux with Docker bridge networking, a service bound only to `127.0.0.1` is
not reachable from inside a container even when `host-gateway` is configured,
because `host-gateway` resolves to the bridge gateway IP (e.g. `172.17.0.1`),
and traffic from that interface arrives on the bridge, not the loopback. The
agent therefore binds to `0.0.0.0` by default. Network isolation is maintained
by a host firewall rule (e.g. `iptables` or `ufw`) that restricts inbound
connections on port `7890` to the Docker bridge subnet only. A deployment that
can guarantee the Docker bridge address (e.g. `172.17.0.1`) may bind to that
address instead.

The CraftControl Server reaches the agent via the Docker host gateway address
visible from inside the container (typically `host-gateway`, configured in
`docker-compose.yml` as an `extra_hosts` entry). The agent itself is not part
of any Docker network.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_AGENT_URL` | `http://host-gateway:7890` | Base URL the backend uses to reach the agent. |
| `HOST_AGENT_TOKEN_FILE` | `/run/secrets/host_agent_token` | Path to the shared-secret file, read at startup. |
| `HOST_AGENT_BIND` | `0.0.0.0:7890` | Address the agent listens on (agent side). Restrict access to the Docker bridge subnet via a host firewall rule. |
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
   TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32), end='')")
   echo -n "$TOKEN" | sudo install -m 0600 -o craftcontrol-agent -g craftcontrol-agent \
     /dev/stdin /etc/craftcontrol/host-agent-token
   ```

2. Store the same token where the backend can read it. In the Docker Compose
   deployment, mount it as a Docker secret:

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
4. Restart the CraftControl Server (`bin/deploy-craftcontrol`).

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
  "health_timeout_seconds": 120,
  "restart_timeout_seconds": 60
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `operation_id` | UUID string | yes | Stable correlation identifier assigned by the application service. Included in all agent logs and audit records. |
| `intended_state` | object | yes | Configuration snapshot the agent must apply. Field names use lowercase `snake_case` (for example `gamemode` and `force_gamemode`). CraftControl translates its uppercase UI-schema keys at this boundary; see `packages/contracts/openapi.yaml` for field definitions. |
| `health_timeout_seconds` | integer | no | Seconds to wait for the health probe to confirm server readiness. Default `120`. Valid range: 10–600. Values outside this range are rejected with `400 Bad Request`. |
| `restart_timeout_seconds` | integer | no | Seconds allowed for the `docker compose restart` command to complete. Default `60`. Valid range: 10–300. Values outside this range are rejected with `400 Bad Request`. |

#### Idempotency

If `execute` is called a second time with the same `operation_id` while the
first call is still running, the agent returns `409 Conflict`:

```json
{"error": "conflict", "operation_id": "<UUID>", "message": "Operation already in progress"}
```

If `execute` is called with the same `operation_id` after the first call
completed, the agent returns the stored result immediately (idempotent replay).
Results are retained for at least 10 minutes.

**After agent restart:** In-memory operation records are lost on restart.
`GET /v1/status/{operation_id}` returns `404` for any operation that was
in-flight or completed before the restart. The caller must treat this `404` as
an **ambiguous** result, not a safe-retry opportunity: the operation may have
partially or fully executed before the restart. The backend must surface this
as a recoverable failure (`error_code: executor_internal_error`) and require
explicit operator confirmation before retrying.

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

#### Response — `200 OK` (terminal — success)

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

#### Response — `200 OK` (terminal — failure)

```json
{
  "operation_id": "<UUID>",
  "status": "done",
  "outcome": "error",
  "executor_ref": null,
  "health_reached": false,
  "failed_stage": "health_wait",
  "detail": "Server did not reach healthy state within 120s",
  "error_code": "health_probe_timeout",
  "exception_type": null
}
```

`status` is always `"done"` for a terminal response, regardless of `outcome`.
`outcome` is `"ok"` on success and `"error"` on failure. A terminal failure
response always includes a non-null `failed_stage` and `error_code`.

The `outcome`, `executor_ref`, `health_reached`, `failed_stage`, `detail`,
`error_code`, and `exception_type` fields conform exactly to the
**Executor result shape** defined in
[operation-lifecycle.md — Executor result shape](operation-lifecycle.md#executor-result-shape).
The adapter returns this shape as-is. The application service then performs the
lifecycle mapping described in `operation-lifecycle.md` — expanding the result
into `stage_log` entries and writing the operation record — so no application
service or use-case changes are required when this adapter is introduced.

#### Response — `200 OK` (in progress)

```json
{
  "operation_id": "<UUID>",
  "status": "running",
  "current_stage": "health_wait"
}
```

| `current_stage` | Description |
|-----------------|-------------|
| `prepare` | Writing configuration files and staging the Compose project. |
| `restart` | Issuing the Compose restart command. |
| `health_wait` | Polling the Bedrock health probe. |

#### Bedrock health probe specification

The health probe runs in the agent's network namespace (the Docker host, outside
all containers). Bedrock Dedicated Server uses UDP/RakNet; a UDP datagram is
sent to the target port and a validated `ID_UNCONNECTED_PONG` response (minimum 35 bytes, correct magic) indicates the server is ready.

| Parameter | Value |
|-----------|-------|
| Host | `127.0.0.1` |
| Port | `19132` (Bedrock default; overridable by `intended_state.server_port` when present) |
| Protocol | UDP |
| Datagram | A complete RakNet unconnected ping (33 bytes): `0x01` (packet ID) + 8-byte timestamp (uint64 BE) + 16-byte magic (`00 ff ff 00 fe fe fe fe fd fd fd fd 12 34 56 78`) + 8-byte client GUID (uint64 BE) |
| Per-attempt read timeout | 2 s |
| Polling interval | 5 s |
| Success condition | A UDP response of at least 35 bytes whose first byte is `0x1c` (`ID_UNCONNECTED_PONG`) and whose bytes 17–32 match the RakNet magic sequence |
| Failure condition | No response, a response that fails the pong validation above, or an OS error within 2 s |

`health_reached` is set to `true` only when the probe succeeds at least once
within `health_timeout_seconds`. Any implementation must use these exact
parameters so that `health_reached` values are comparable across adapters.

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

### `GET /v1/bedrock/status`

Reports whether the Bedrock server container is currently running. This is
distinct from agent process liveness — the agent may be healthy while the
Bedrock container is stopped or restarting.

**Authentication:** Bearer token required (same as all other authenticated
endpoints).

Returns `200 OK` with:

```json
{"bedrock_running": true}
```

or, when the container is stopped or unreachable:

```json
{"bedrock_running": false}
```

The backend uses this endpoint in `HostAgentContainerOperations.status()` to
determine real Bedrock availability rather than agent liveness.

---

## Error codes

The following machine-readable `error_code` values are defined for the
executor result shape. New codes must be added to this table before
implementation.

| Code | Stage | Description |
|------|-------|-------------|
| `preparation_write_failed` | `prepare` | A configuration file could not be written. |
| `preparation_compose_invalid` | `prepare` | The staged Compose configuration failed validation. |
| `restart_command_failed` | `restart` | The `docker compose restart` command exited non-zero. |
| `restart_timeout` | `restart` | The restart command did not complete within the configured deadline. |
| `health_probe_failed` | `health_wait` | The health probe returned a non-healthy response. |
| `health_probe_timeout` | `health_wait` | The server did not reach healthy state before `health_timeout_seconds`. |
| `executor_internal_error` | any | An unhandled exception occurred in the agent. |

---

## Unavailability handling

Agent unavailability is handled differently depending on whether the failure
occurred before or after the agent received the request.

### Pre-delivery failures (safe to fail immediately)

A connection refused or a timeout that fires before the TCP connection to the
agent is established means the request was never delivered. The backend must:

1. Set `outcome: error`, `failed_stage: PREPARATION`, `error_code:
   executor_internal_error`, and `detail` to a human-readable connectivity
   description.
2. Transition the operation to `FAILED` via the standard lifecycle path.
3. Emit `operation.failed` over SSE.
4. Not expose host internals (agent address, filesystem paths, or container
   names) in the UI or public API responses.

The operator may restart the agent and retry the operation.

### Post-delivery ambiguous failures

A `5xx` response, a timeout that fires after the TCP connection was established,
a connection reset, an EOF, a write failure, or a protocol error — whenever the
agent may have already received `POST /v1/execute` — means the agent may have
accepted and begun executing the request. Immediately marking the operation
`FAILED` would race with a successful execution; a subsequent retry may receive
`409 Conflict`.

The backend must:

1. Poll `GET /v1/status/{operation_id}` up to three times with a 5 s interval
   before concluding failure.
2. If polling returns a terminal result, process it normally.
3. If polling returns `404` or a transport error on every attempt, treat the
   outcome as ambiguous: set `outcome: error`, `failed_stage` to the last known
   stage (or `PREPARATION` if unknown), `error_code: executor_internal_error`,
   and `detail` to a message indicating the result is unknown.
4. Transition the operation to `FAILED` and emit `operation.failed` over SSE.
5. Not expose host internals in the UI or public API responses.

An ambiguous result requires explicit operator confirmation before retrying.

---

## Permitted operations

The agent is explicitly **not** a general command runner. The following table
lists every operation the agent may execute. Any request for an operation not
in this table must be rejected with `400 Bad Request`.

| Operation | Trigger | Host privilege required |
|-----------|---------|------------------------|
| Write server configuration files to the Bedrock data directory | `POST /v1/execute` (`prepare`) | Write access to the Bedrock data path |
| Stage and validate the Compose project file | `POST /v1/execute` (`prepare`) | Read access to the Compose project directory |
| `docker compose restart minecraft-server` | `POST /v1/execute` (`restart`) | Docker socket access |
| Poll the Bedrock UDP health probe | `POST /v1/execute` (`health_wait`) | Network access to localhost |

No console commands, arbitrary shell execution, world data mutations, or `.env`
file writes are permitted.

---

## Deployment

The agent runs as a **systemd service** on the Docker host, outside all
containers. The agent source and tests live under `services/host-agent/`. The systemd unit file is available under `deploy/host-agent/systemd/`.

| Property | Value |
|----------|-------|
| Service name | `craftcontrol-host-agent` |
| OS user | `craftcontrol-agent` (no login shell, no sudo) |
| Binds to | `0.0.0.0:7890` (default) |
| Network exposure | Restricted to the Docker bridge subnet via host firewall rule; not reachable from the LAN |
| Secret file | `/etc/craftcontrol/host-agent-token`, mode `0600`, owned by `craftcontrol-agent` |
| Docker socket access | Group membership in `docker` for `craftcontrol-agent` |

---

## Relationship to existing code

The backend's `ContainerOperations` port
(`apps/server/minecraft_manager/ports.py`) defines the interface both adapters
implement. `HostAgentContainerOperations` (implemented in
`apps/server/minecraft_manager/host_agent.py`) calls this agent over HTTP and
returns results in the executor result shape defined in
`docs/operation-lifecycle.md`. `DockerOperations` is the direct Compose adapter
used when the host agent is not configured.

Configuration selects exactly one implementation at startup: when `HOST_AGENT_URL`
is set in the environment, `HostAgentContainerOperations` is composed; otherwise
`DockerOperations` is used. No application service or use case changes are
required to switch between adapters — both satisfy the same `ContainerOperations`
port.

The direct Compose adapter (`DockerOperations`) and the host-agent adapter
(`HostAgentContainerOperations`) coexist in the codebase. The host agent owns
Docker socket access for the operations it executes (PREPARATION, RESTART,
HEALTH_WAIT). The Docker socket is still mounted in the backend container for
operations that remain there: `BedrockClient` uses it for console attachment,
log streaming, and Docker event subscriptions. Those operations are not delegated
to the agent.

---

## Open questions

None. All design decisions are settled. Implementation may begin.
