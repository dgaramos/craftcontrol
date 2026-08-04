# Coordinated backup and restore

CraftControl creates one verifiable recovery set containing the active Bedrock world, a transactionally consistent SQLite copy, and the server configuration and behavior-pack files required to diagnose or manually reconstruct the deployment.

Backups default to `/data/backups/coordinated` inside the container, mapped to `./data/backups/coordinated` in the CraftControl project. Set `BACKUP_ROOT` to change that location. A backup on the same disk is operational recovery, not disaster recovery; copy completed sets to another machine or storage system.

## Backup consistency

When Bedrock is running, `backup create` issues `save hold`, waits until `save query` confirms that world files are ready, copies the world, and always issues `save resume` in a `finally` path. SQLite is copied through its online backup API and checked with `PRAGMA integrity_check`.

Every set contains:

```text
<backup-id>/
├── manifest.json
├── manager.db
├── world.tar.gz
└── configuration.tar.gz
```

The manifest records the format version, UTC creation time, world, SQLite schema version, byte sizes, and SHA-256 checksums. `configuration.tar.gz` includes available `.env`, Compose, Bedrock properties, permissions, allowlist, and behavior-pack files. Configuration is not restored automatically because replacing `.env` silently could change ports, mounts, secrets, or the selected world.

## Create, list, and verify

Run from `/mnt/storage/docker/craftcontrol`:

```bash
docker compose exec craftcontrol craftcontrol backup create
docker compose exec craftcontrol craftcontrol backup list
docker compose exec craftcontrol craftcontrol backup verify BACKUP_ID
```

Pass `--world NAME` to `create` only when the active world cannot be detected. Backup does not restart either service.

## Retention

Preview retention before deleting anything:

```bash
docker compose exec craftcontrol craftcontrol backup prune --keep 7
```

Apply the reviewed deletion explicitly:

```bash
docker compose exec craftcontrol craftcontrol backup prune --keep 7 --yes
```

Retention ignores pre-restore recovery directories. Copy the sets you need for disaster recovery off the Docker host before pruning.

## Offline restore

Restore replaces the selected world and `manager.db`; it refuses to run while Bedrock is active and requires `--yes`. Stop both long-running processes so the manager cannot hold or recreate SQLite WAL state, then use a one-off CraftControl container:

```bash
cd /mnt/storage/docker/craftcontrol
docker compose stop craftcontrol
docker stop minecraft-bedrock
docker compose run --rm --no-deps craftcontrol craftcontrol backup verify BACKUP_ID
docker compose run --rm --no-deps craftcontrol craftcontrol backup restore BACKUP_ID --yes
docker compose up -d craftcontrol
docker start minecraft-bedrock
docker compose ps
```

Before replacement, restore creates `BACKUP_ROOT/pre-restore/<timestamp>/` with the current SQLite database and world. Do not delete that recovery copy until the restored world and player history are verified.

After startup, check:

```bash
curl -fsS http://127.0.0.1:8082/api/status
curl -fsS http://127.0.0.1:8082/api/players
docker compose logs --tail=100 craftcontrol
```

To recover configuration or behavior-pack files, inspect and extract `configuration.tar.gz` manually, compare it with the current deployment, and apply only the required files. Never overwrite `.env` without reviewing its values.
