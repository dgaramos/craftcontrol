# Database migrations

CraftControl evolves its embedded SQLite schema through numbered, contiguous migrations in `minecraft_manager/migrations.py`. The database stores its applied version in SQLite's native `PRAGMA user_version`; this is independent from both the Telemetry Pack storage version and telemetry protocol schema.

At startup CraftControl:

1. reads the current database version;
2. rejects a database newer than the running application;
3. creates `data/backups/manager.db.pre-vN.bak` before changing an existing version `N` database;
4. applies each pending migration in its own `BEGIN IMMEDIATE` transaction;
5. updates `user_version` in that same transaction;
6. rolls back the complete migration when any statement fails;
7. starts the runtime only after the schema reaches the supported version.

The pre-migration backup is immutable: a retry does not overwrite it. Fresh empty databases do not create a redundant version-zero backup.

## Inspect the schema version

```bash
docker compose exec craftcontrol python -c 'import sqlite3; connection=sqlite3.connect("/data/manager.db"); print(connection.execute("PRAGMA user_version").fetchone()[0])'
```

## Recovery

If startup reports a migration failure, keep CraftControl stopped and preserve the failed database plus its `-wal` and `-shm` sidecars before restoring the matching file from `data/backups/`. Do not restore while CraftControl is running. The backup is a consistent SQLite copy created through the SQLite backup API, not a raw copy of an open database.

Never lower `user_version` manually. Restore the pre-migration backup or run a documented forward repair migration instead.
