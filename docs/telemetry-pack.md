# CraftControl Telemetry Pack integration

CraftControl embeds the independently versioned `craftcontrol-telemetry` repository under `packs/telemetry/` with Git subtree. A normal clone therefore includes a tested pack without requiring Git submodule initialization.

## Operator commands

Run commands inside the CraftControl container:

```bash
docker compose exec minecraft-bedrock-manager craftcontrol telemetry status
docker compose exec minecraft-bedrock-manager craftcontrol telemetry install
docker compose exec minecraft-bedrock-manager craftcontrol telemetry upgrade
docker compose exec minecraft-bedrock-manager craftcontrol telemetry disable
docker compose exec minecraft-bedrock-manager craftcontrol telemetry remove --yes
docker compose exec minecraft-bedrock-manager craftcontrol telemetry rollback --yes
```

Use `--world NAME` when automatic detection cannot identify the intended world. `install` and `upgrade` are the same idempotent reconciliation operation; the different action names make operator intent explicit.

Commands never stop or restart Bedrock. A changed installation returns `"restart_required": true`; restart the Bedrock service only after reviewing the generated backup identifier.

## Safety and persistence

The installer:

- reads the active world from `LEVEL_NAME`, `server.properties`, or the worlds directory;
- accepts only an exact child directory of `data/worlds`;
- validates the embedded manifest against CraftControl's pack UUID allowlist;
- copies into the persistent Bedrock `data/behavior_packs` directory;
- writes `world_behavior_packs.json` atomically;
- normalizes pack directories to `755` and files to `644`;
- backs up the association file and existing current/legacy pack directories before every mutation;
- rolls back automatically when installation fails;
- migrates the legacy `minecraft-bedrock-telemetry` directory only after the new pack copy succeeds;
- preserves the original pack UUID, Script API namespace, dynamic-property key, and world telemetry state.

Backups live outside the world at:

```text
<minecraft-project>/backups/craftcontrol-telemetry/<UTC timestamp>/
```

`disable` removes only the world association. `remove` also removes installed pack files, but retains a recoverable backup. Neither action deletes the behavior pack's dynamic property embedded in the world.

## Subtree maintenance

The standalone telemetry repository remains the upstream release source. From the CraftControl repository, import a new release with:

```bash
git subtree pull --prefix packs/telemetry ../craftcontrol-telemetry main --squash
```

When the remote repository is configured explicitly:

```bash
git subtree pull --prefix packs/telemetry craftcontrol-telemetry main --squash
```

Do not edit the embedded copy and standalone repository independently. Pack changes begin in the standalone repository, pass its Node.js checks, and are then pulled into CraftControl. The standalone and embedded trees must produce byte-equivalent `.mcpack` artifacts.
