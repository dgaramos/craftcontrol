# Development setup

This guide covers everything needed to run CraftControl locally, execute the quality gate, and contribute changes.

For architecture conventions, dependency rules, and data invariants, see [Architecture](architecture.md).
For the contribution workflow, see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Prerequisites

| Tool | Minimum version | Notes |
| --- | --- | --- |
| Docker Engine | 24+ | With the Compose plugin (`docker compose`) |
| Python | 3.12 | Used by the backend and the test suite |
| Node.js | 18+ | Optional: used by the frontend test runner when installed locally |
| npm | 9+ | Optional with Docker; comes with Node when local frontend checks are preferred |
| Git | any recent | For branch management and Conventional Commits |

Verify your versions:

```bash
docker --version
docker compose version
python3 --version
# Optional: bin/check-frontend automatically uses Docker when these are absent.
node --version
npm --version
```

---

## Cloning the repository

```bash
git clone https://github.com/dgaramos/craftcontrol.git
cd craftcontrol
```

If you are working from a fork, add the upstream remote:

```bash
git remote add upstream https://github.com/dgaramos/craftcontrol.git
```

---

## Environment setup

Copy the example environment file and review every value before starting the stack:

```bash
cp .env.example .env
```

Key variables for local development:

| Variable | Development value | Notes |
| --- | --- | --- |
| `MANAGER_PORT` | `8082` | Public frontend port |
| `MINECRAFT_CONTAINER` | `minecraft-bedrock` | Must match your local Bedrock container name |
| `MINECRAFT_PROJECT` | `/minecraft-project` | Path to the Bedrock Compose project inside the backend container |
| `DATABASE_PATH` | `/data/manager.db` | SQLite file inside the container |
| `AUTH_MODE` | `local` | Keep `local` for normal development |
| `AUTH_COOKIE_SECURE` | `false` | Set to `false` when running over plain HTTP locally |
| `TZ` | `America/Sao_Paulo` | Adjust to your local timezone if needed |

Never commit `.env`. It is listed in `.gitignore` and must stay machine-local.

---

## Running the stack locally

CraftControl uses the split-image topology. Build and start both services:

```bash
docker compose -f docker-compose.split.yml build
docker compose -f docker-compose.split.yml up
```

The frontend is available at `http://localhost:8082`. The backend API is reachable through the Nginx proxy at `http://localhost:8082/api`.

To rebuild only one service after a change:

```bash
docker compose -f docker-compose.split.yml build craftcontrol-frontend
docker compose -f docker-compose.split.yml build craftcontrol-backend
```

To follow logs:

```bash
docker compose -f docker-compose.split.yml logs -f craftcontrol-backend
docker compose -f docker-compose.split.yml logs -f craftcontrol-frontend
```

To stop the stack:

```bash
docker compose -f docker-compose.split.yml down
```

> Do not use a bare `docker compose up` from a development checkout for production. Relative bind mounts can select development-local data. See [AGENTS.md](../AGENTS.md) for the production deployment workflow.

---

## Running tests

### Complete quality gate

Run all checks before committing or opening a PR:

```bash
bin/check
```

This is the only gate that must pass before requesting a merge.

`bin/check-frontend` uses the local Node/npm installation when available. If
they are absent, it runs the JavaScript syntax, i18n, interaction, and Jest
checks in `node:22-alpine` through Docker. Do not report Node as a missing
development dependency before running the gate; Docker is the supported
fallback. The frontend `node_modules` directory is created or refreshed in
the working tree just as it is for a local `npm ci`.

### Individual gates

Each gate is also runnable independently:

```bash
bin/check-frontend      # JS syntax, i18n, interaction and visual-contract tests
bin/check-backend       # Python application and persistence tests
bin/check-contracts     # OpenAPI, route surface, generated declarations
bin/check-integration   # Compose builds, split runtime, architecture and deploy safety
```

Run only the gate that covers the layer you changed to get faster feedback during development. Keep a test in exactly one gate unless a boundary invariant deliberately spans gates.

### Backend tests directly with pytest

```bash
PYTHONPATH=apps/backend:. pytest tests/ -q
```

### Frontend tests directly with npm

```bash
cd apps/frontend && npm test
```

---

## Common development tasks

### Generate or update the OpenAPI contract

After changing a backend route or schema, regenerate the contract and the frontend type declarations, then verify them:

```bash
bin/check-contracts
```

The gate rejects stale declarations.

### Apply database migrations

Migrations run automatically on backend startup. To inspect pending migrations or verify the schema version, connect to the running container:

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  python3 -c "from minecraft_manager.repository import get_db; get_db()"
```

See [Database migrations](database-migrations.md) for the migration convention and safety rules.

### Bootstrap the first panel account

After the Bedrock container is running and a player has joined at least once:

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol auth bootstrap --player <gamertag>
```

The command prints a one-time owner code. Use it at the login screen within 15 minutes.

### Create a coordinated backup

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol backup create
```

See [Coordinated backup and restore](backup-and-restore.md) for the full workflow.

### Check the Telemetry Pack status

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol telemetry status
```

---

## Project layout reference

```text
apps/
├── frontend/           Nginx image, HTML, CSS, and native ES modules
└── backend/            Flask image, composition root, and Python application
packages/contracts/     Canonical OpenAPI 3.1 contract and generated types
packs/telemetry/        Embedded Behavior Pack and lifecycle assets
bin/                    Quality, deployment, backup, and recovery commands
docs/                   Architecture, security, telemetry, and operations guides
tests/                  Backend integration and persistence tests
```

See [Architecture](architecture.md) for a full description of layers, dependency rules, and the incremental refactor target layout.
