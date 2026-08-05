# CraftControl Telemetry Pack integration

CraftControl embeds the independently versioned `craftcontrol-telemetry` repository under `packs/telemetry/` with Git subtree. A normal clone therefore includes a tested pack without requiring Git submodule initialization.

## Operator commands

Run commands inside the CraftControl container:

```bash
docker compose exec craftcontrol craftcontrol telemetry status
docker compose exec craftcontrol craftcontrol telemetry install
docker compose exec craftcontrol craftcontrol telemetry upgrade
docker compose exec craftcontrol craftcontrol telemetry disable
docker compose exec craftcontrol craftcontrol telemetry remove --yes
docker compose exec craftcontrol craftcontrol telemetry rollback --yes
```

Use `--world NAME` when automatic detection cannot identify the intended world. `install` and `upgrade` are the same idempotent reconciliation operation; the different action names make operator intent explicit.

Commands never stop or restart Bedrock. A changed installation returns `"restart_required": true`; restart the Bedrock service only after reviewing the generated backup identifier.

The responsive **Server → Telemetry Pack** panel uses this same installer implementation. It shows the installed and embedded versions, active association, runtime health, last response timestamp, and upgrade availability. Its state-changing controls require confirmation and likewise never restart Bedrock automatically.

## Reconciliation and health

CraftControl persists the latest world-local sequence and treats incremental records and snapshot frames differently. A forward sequence gap marks telemetry as `degraded`, records the missing range, and requests one coalesced full snapshot. Stale or out-of-order deltas are rejected before they can change counters. A lower `telemetry.started` sequence is treated as a pack-state reset and also triggers reconciliation.

Snapshot frames may legitimately share a sequence and repeated snapshots at the same sequence remain authoritative. Health returns to `healthy` only after `snapshot.finished`; an empty or incomplete response remains `degraded` instead of being left indefinitely as synchronizing. The panel exposes health, current sequence, last completed snapshot, detected gaps, missing-event count, and the latest error. Snapshot requests within the cooldown window are coalesced to avoid command storms.

Pack storage and wire protocol are versioned independently. Telemetry Pack `0.2.2` migrates legacy storage `0` or monolithic storage `1` to sharded storage `2` only after validation. It retains the untouched source JSON in `bedrock_telemetry:state_backup_v0` or `bedrock_telemetry:state_backup_v1`, fills missing fields without resetting counters, writes and verifies player shards first, and commits metadata last. Startup discovers shards and promotes metadata to the highest shard sequence after an interrupted write. Startup and snapshot envelopes carry storage health; CraftControl keeps health `degraded` whenever the pack reports blocked persistence.

Telemetry Pack `0.2.3` also probes optional stable event signals before subscribing. Capability results travel in `telemetry.started` and `snapshot.started`, are persisted by CraftControl, and appear as a bilingual support list in the panel. Unsupported metrics remain explicitly unavailable rather than being silently interpreted as zero; other supported collectors continue running.

Telemetry Pack `0.3.0` upgrades persisted storage to v3 and adds bounded kills by creature type plus per-dimension distance, sampled active movement time, and first/last observations. The v2 metadata and every original v2 player shard are retained under backup dynamic properties before v3 is committed. Existing counters survive; only newly introduced metrics begin at zero.

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
