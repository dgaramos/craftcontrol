# Automated homelab deployment

CraftControl deploys a successful Gitea `main` revision automatically as the
final job of the `Quality gates` workflow. The deployment job runs on the
repository-scoped `craftcontrol-homelab` self-hosted runner inside the homelab;
Gitea-hosted runners never receive Docker or LAN access.

The workflow checks out the exact accepted revision and asks the runner's
local deployment agent to run the guarded coordinated deployment:

```mermaid
flowchart LR
    push["push to Gitea main"] --> quality["Quality gates"] --> runner["homelab runner"] --> preflight --> images["prepare images"] --> backup --> activate --> canaries
```

The preflight and container deployment use `bin/deploy-craftcontrol-release`.
When a revision changes `services/bedrock-proxy/` or `deploy/bedrock-proxy/`, the
same job queues a bedrock-proxy activation after the container release. The
root-owned host service validates the revision, atomically activates the staged
agent, and restores the previous agent if its systemd health check fails. This path retains
the existing guarantees: clean and published GitHub source, validated production
mounts, a verified coordinated backup before backend replacement, SQLite
integrity checks, frontend/backend health checks, anonymous-authentication
canary, and Bedrock health verification.

## Runner configuration

The runner is intentionally repository-scoped and has the `homelab` and
`craftcontrol` labels. It needs Docker-socket and `/mnt/storage/docker` access
because the guarded deployment command operates the local production Compose
project. Do not attach these labels to a shared runner or use it for pull
requests from untrusted repositories.

The runner Compose project lives at
`/mnt/storage/docker/craftcontrol-github-runner`. Its registration token is
short-lived and is used only for initial runner registration; persistent runner
state and the local deployment agent remain outside this repository.

### Host Agent update bootstrap

The first setup is performed once on the Docker host; it does not expose an
HTTP endpoint or grant the runner systemd access. Install the two checked-in
helpers and enable the local path watcher:

```bash
sudo install -d -m 0755 /mnt/storage/docker/craftcontrol-bedrock-proxy-update
sudo install -m 0750 deploy/bedrock-proxy/bin/craftcontrol-bedrock-proxy-update /usr/local/bin/
sudo install -m 0755 deploy/bedrock-proxy/systemd/craftcontrol-bedrock-proxy-update.service /etc/systemd/system/
sudo install -m 0644 deploy/bedrock-proxy/systemd/craftcontrol-bedrock-proxy-update.path /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now craftcontrol-bedrock-proxy-update.path
```

The runner writes only a 40-character revision request. The host helper rejects
paths, commands, dirty source, unpublished revisions, and any release that
does not restart as active. It does not alter agent tokens, runtime
configuration, world data, or the agent operation database.

## Failure behavior

Deployments are serialized with the `craftcontrol-homelab-production`
concurrency group. The deploy job depends on integration and runs only for a
Gitea `push` to `main`; a failed quality job never starts a deployment. A
guarded release builds both images before recreating either service. Each image
build is retried up to three times for transient registry or DNS failures; if
preparation still fails, no service is recreated. A failure after activation
exits with the existing canary failure and preserves the verified backup for
explicit rollback using
`bin/deploy-craftcontrol-release --rollback FRONTEND_VERSION BACKEND_VERSION`.
