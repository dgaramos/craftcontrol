# Homelab deploy infrastructure

This document describes how to recreate the self-hosted deploy infrastructure
from scratch. It is intended as a recovery guide if the homelab is lost.

## Overview

Pushes to `main` trigger the `deploy-homelab` job in
`.gitea/workflows/quality.yml`. That job runs on the self-hosted runner,
which calls a deploy script that rsyncs the accepted revision into a persistent
deploy root and rebuilds the Docker images there.

```
push to main
  → Gitea CI (self-hosted runner)
      → /usr/local/bin/craftcontrol-homelab-deploy <sha>
          → bin/deploy-craftcontrol-release --check   (preflight)
          → bin/deploy-craftcontrol-release            (deploy)
              → bin/deploy-craftcontrol-backend
              → bin/deploy-craftcontrol-frontend
```

## Directory layout on the host

```
/mnt/storage/docker/
  craftcontrol/                      ← DEPLOY_ROOT (persistent git clone of main)
    bin/
      deploy-craftcontrol-release
      deploy-craftcontrol-backend
      deploy-craftcontrol-frontend
    apps/server/controlplane/
    apps/client/
    data/                            ← SQLite database and backups (never overwritten)
    docker-compose.split.yml
    versions.env
  craftcontrol-gitea-runner/
    config.yaml                      ← Act runner configuration
    data/                            ← Runner state (registration, cache)
  craftcontrol-github-runner/
    deploy-craftcontrol.sh           ← mounted into the runner as craftcontrol-homelab-deploy
```

## Runner container

The Gitea Act Runner (`craftcontrol-gitea-runner`) runs as a container with
these mounts:

| Host path | Container path | Mode |
|---|---|---|
| `/var/run/docker.sock` | `/var/run/docker.sock` | rw |
| `/mnt/storage/docker` | `/mnt/storage/docker` | rw |
| `craftcontrol-github-runner/deploy-craftcontrol.sh` | `/usr/local/bin/craftcontrol-homelab-deploy` | ro |
| `craftcontrol-gitea-runner/config.yaml` | `/config.yaml` | ro |
| `craftcontrol-gitea-runner/data` | `/data` | rw |

The runner uses the `gitea_default` Docker network so it can reach Gitea by
service name.

Runner labels declared in `config.yaml`:

```yaml
runner:
  capacity: 1
  labels:
    - ubuntu-latest:docker://craftcontrol-gitea-job:latest
    - self-hosted:host
    - homelab:host
    - craftcontrol:host
```

The workflow job targets `[self-hosted, homelab, craftcontrol]`.

## How the deploy script works

`craftcontrol-homelab-deploy` (mounted from
`craftcontrol-github-runner/deploy-craftcontrol.sh`) receives the accepted
SHA and does the following safety checks before delegating:

1. Verifies the checked-out revision matches the accepted SHA.
2. Verifies `origin` (Gitea) and `github` (GitHub) both point to the same
   revision on `main`. A push that only lands on one remote is rejected.
3. Calls `bin/deploy-craftcontrol-release --check` (preflight).
4. Calls `bin/deploy-craftcontrol-release` (actual deploy).

`bin/deploy-craftcontrol-backend` (inside DEPLOY_ROOT):

1. Validates the deploy root, compose file, and production database exist.
2. Rsyncs `apps/server` (Dockerfile + source), `packages`, `packs`,
   `bin/craftcontrol`, `docker-compose.split.yml`, and `versions.env` from
   SOURCE_ROOT (runner workspace) into DEPLOY_ROOT.
3. Runs `compose build craftcontrol-backend`.
4. Creates a pre-upgrade backup: `compose exec -T craftcontrol-backend craftcontrol backup create`.
5. Verifies the backup.
6. Runs `compose up -d --no-deps craftcontrol-backend`.
7. Waits for the health check, then validates mounts, database integrity,
   and HTTP health endpoints.
8. Falls back to the previous image on failure (rollback path is separate).

## Recreating the infrastructure

### 1. Install prerequisites

- Docker and Docker Compose plugin
- Gitea (or connect to an existing instance)
- A user and group for the host agent (`craftcontrol-agent`)

### 2. Create the deploy root

```bash
git clone <gitea-repo-url> /mnt/storage/docker/craftcontrol
```

The deploy scripts (`bin/deploy-craftcontrol-*`) live in this clone and are
called by the runner at deploy time. Keep this clone on `main` and clean.

### 3. Copy the initial data

Restore `data/manager.db` and `data/backups/` from a backup before starting
the containers. Never let a deploy overwrite these.

### 4. Register the Gitea runner

Create `craftcontrol-gitea-runner/config.yaml` with the labels above and a
registration token from the Gitea repository settings
(Settings → Actions → Runners → New runner).

The token goes in the runner's `data/` directory after first registration;
it is not stored in the config file.

### 5. Mount the deploy script

Place the deploy script at
`craftcontrol-github-runner/deploy-craftcontrol.sh` (see the contents in the
`craftcontrol-homelab-deploy` call above) and ensure it is executable. The
runner container mounts it read-only as `/usr/local/bin/craftcontrol-homelab-deploy`.

### 6. Start the runner

```bash
docker compose up -d craftcontrol-gitea-runner
```

Verify the runner appears as online in Gitea (Settings → Actions → Runners).

### 7. Start the application containers

```bash
cd /mnt/storage/docker/craftcontrol
source versions.env
docker compose -f docker-compose.split.yml up -d
```

### 8. Install the Bedrock Proxy service

Follow `deploy/bedrock-proxy/bin/install-craftcontrol-bedrock-proxy-runtime`.
The service listens on a local port and requires a shared secret in
`/etc/craftcontrol/bedrock-proxy-token`. That file must be present before the
backend container starts (it is mounted read-only into the container).

## Backup contract

See `deploy/README.md` for the canonical backup interface. The short version:
always run backup via `docker exec` against the running container, never via
the host-side `craftcontrol` binary. The container image always ships
`/usr/local/bin/craftcontrol` matching its own Python module layout.
