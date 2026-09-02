# CraftControl Host Agent

A minimal HTTP service that runs on the Docker host — outside all containers —
and executes exactly the permitted host-level operations on behalf of the
CraftControl Server.

The host agent is optional. Without it, the CraftControl Server performs
lifecycle operations directly using the Docker socket mounted into its container.
With it, the Docker socket stays out of the CraftControl Server container for
those operations; the Server delegates preparation, restart, and health probing
over an authenticated HTTP channel.

---

## Responsibilities

The host agent owns exactly three operation stages:

| Stage | What it does |
|---|---|
| `PREPARATION` | Writes `server.properties` and `.env` atomically on the host filesystem |
| `RESTART` | Restarts the Bedrock Docker Compose service |
| `HEALTH_WAIT` | Polls the Bedrock UDP/RakNet probe until the server responds or the deadline passes |

Everything else (state management, player tracking, telemetry, auth, backups)
remains in the CraftControl Server.

---

## Layout

```
services/host-agent/
├── agent.py          # bootstrap entry point, HTTPServer setup
├── router.py         # request routing and bearer-token authentication
├── handler.py        # per-endpoint request parsing and response serialisation
├── operations.py     # OperationExecutor — stage execution and field validation
├── store.py          # OperationStore — SQLite-backed operation persistence
├── auth.py           # shared-secret token loading and verification
├── ports.py          # Protocol definitions for replaceable boundaries
├── queue_worker.py   # bounded thread pool for sequential operation execution
├── preflight.py      # startup self-check (filesystem, Docker, token)
├── requirements.txt  # Python dependencies
└── adapters/
    ├── docker.py     # DockerAdapter — Compose restart via Docker SDK
    ├── filesystem.py # FilesystemAdapter — atomic config file writes
    └── raknet.py     # RakNetAdapter — UDP health probe for Bedrock
```

---

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|---|---|---|
| `HOST_AGENT_BIND` | `0.0.0.0:7890` | HTTP bind address |
| `HOST_AGENT_SECRET_FILE` | `/etc/craftcontrol/host-agent-token` | Shared-secret token file |
| `HOST_AGENT_COMPOSE_PROJECT` | `minecraft-bedrock` | Docker Compose project name |
| `HOST_AGENT_COMPOSE_FILE` | `/opt/craftcontrol/docker-compose.yml` | Path to docker-compose.yml |
| `HOST_AGENT_COMPOSE_SERVICE` | `minecraft-server` | Compose service name for Bedrock |
| `HOST_AGENT_BEDROCK_CONTAINER` | `minecraft-server` | Docker container name |
| `HOST_AGENT_BEDROCK_DATA` | `/opt/craftcontrol/data/bedrock` | Bedrock data directory |
| `HOST_AGENT_DB` | `/var/lib/craftcontrol/host-agent.db` | SQLite operation persistence |
| `HOST_AGENT_WORKERS` | `1` | Worker threads (keep at 1 — no concurrent restarts) |
| `HOST_AGENT_QUEUE_SIZE` | `8` | Max pending operations before 503 |

The CraftControl Server connects to the host agent by setting `HOST_AGENT_URL`
in its own environment. The shared secret must match on both sides.

---

## Security model

- All requests require a `Bearer <token>` header matching the shared secret.
- The token is read from a file at startup; it never appears in environment variables or logs.
- The agent validates every field in `intended_state` against strict allowlists before writing any file.
- Endpoint surface is minimal: `/health`, `/status`, `/execute`, `/poll/<id>`.
- No shell execution — Docker operations go through the Docker SDK; filesystem writes are atomic.

---

## Installation

The host agent is installed on the Docker host as a systemd service:

```bash
# Run on the host, not inside a container
deploy/host-agent/bin/install-craftcontrol-host-agent-runtime
```

systemd unit and udev rules live in `deploy/host-agent/systemd/` and
`deploy/host-agent/udev/`. See [docs/host-agent.md](../../docs/host-agent.md)
for the full installation and configuration walkthrough.

---

## Running tests

From `services/host-agent/`:

```bash
pytest tests/ -x -q
```

Requirements: Python 3.12+, `pip install -r requirements.txt`.

The test suite covers the executor, handler, queue worker, store, and preflight
check. Integration with a live Docker daemon is not required — `FakeDocker` and
`FakeFilesystem` adapters stand in for the real infrastructure.

---

## Extracting or repackaging

The host agent is already a standalone Python application with no dependency on
the `controlplane` package. If extracted:

1. Copy `services/host-agent/` as the project root.
2. The `deploy/host-agent/` scripts reference the installed binary path — update
   `install-craftcontrol-host-agent-runtime` if the install location changes.
3. `HOST_AGENT_SECRET_FILE` and `HOST_AGENT_DB` paths are configurable; no
   hardcoded paths exist inside the Python source.
