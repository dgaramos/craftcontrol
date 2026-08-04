# CraftControl Telemetry Pack

A passive, server-side behavior pack that produces durable and structured player statistics for Minecraft Bedrock Dedicated Server and CraftControl.

The pack observes stable Bedrock Script API events, maintains aggregate statistics inside the world, and writes versioned JSON envelopes to the server log. External consumers can ingest incremental events and request an authoritative snapshot after restarts. It does not alter gameplay and does not require the consumer to remain online.

> [!IMPORTANT]
> Back up the world before installing or upgrading any behavior pack. Test against a copy of the world first.

## What it collects

- Player joins, leaves, respawns, and dimensions visited
- Player deaths, damage cause, killer, victim type, and projectile type when available
- Player and mob kills
- Blocks broken and placed, including bounded per-block-type totals
- Damage dealt and received
- Horizontal distance traveled, sampled every five seconds
- First and last observation timestamps
- Aggregate snapshots for recovery and reconciliation

The pack does not collect chat, inventory contents, coordinates in log events, IP addresses, or XUIDs. Xbox achievements are not available as a reliable general-purpose Script API telemetry source.

## Architecture

```text
Stable Bedrock world events
          |
          v
Behavior pack adapters
          |
          +--> in-memory aggregates --> metadata + per-player world properties
          |
          +--> [BEDROCK_TELEMETRY] JSON --> BDS log --> external consumer
                                                     |
/scriptevent bedrock_telemetry:sync full ------------+--> snapshot reconciliation
```

The behavior pack is not another Docker service. Its source is maintained independently, but the built pack executes inside the Bedrock process after it is attached to a world.

## Reliability model

- Aggregates are the authoritative state and are persisted in the world every five seconds.
- Incremental log records provide low-latency delivery but can be replayed or lost around an unclean server stop.
- Every incremental record has a world-local monotonic sequence.
- A consumer requests a full snapshot after startup, reconnect, sequence gap, or schema change.
- Snapshots emit one player per line to avoid oversized server log records.
- Per-block-type maps retain the 128 most frequent values to bound state growth.
- A movement jump greater than 128 blocks per sample is treated as teleportation and is not added to traveled distance.
- Metadata and every player shard are checked independently against the 30 KB safety limit; an oversized write is refused instead of corrupting persisted state.
- Persisted storage and log protocol have independent versions. Legacy storage is validated and migrated before event subscriptions begin.
- The original legacy JSON is retained at `bedrock_telemetry:state_backup_v0`; failed, corrupt, oversized, or future-version state blocks writes instead of being replaced with empty counters.
- Every optional stable event is capability-checked before subscription. Unavailable signals disable only their corresponding metric and are reported once in logs and every authoritative snapshot.

See [docs/protocol.md](docs/protocol.md) for the wire contract.

## Repository structure

```text
behavior_pack/
├── manifest.json
└── scripts/
    ├── main.js       # Stable Bedrock event subscriptions
    ├── migrations.js # Validated persisted-state migration pipeline
    ├── model.js      # Pure statistics model and bounded counters
    ├── store.js      # World dynamic-property persistence
    └── transport.js  # Structured log protocol and snapshots
scripts/
├── install.mjs       # Validated installation and world association
├── install.sh        # Operator-friendly wrapper
└── package.sh        # .mcpack builder
tests/
├── model.test.js     # Pure Node.js unit tests
└── runtime.test.js   # Simulated Bedrock Script API integration flow
```

## Requirements

- Minecraft Bedrock Dedicated Server compatible with `@minecraft/server` 2.0.0
- Node.js 18 or newer for tests and the installer
- `zip` only when producing a `.mcpack` archive
- `content-log-console-output-enabled=true`; with the `itzg` image, configure `CONTENT_LOG_CONSOLE_OUTPUT_ENABLED=true`

The manifest uses stable Script API version `2.0.0`, matching the module shipped by the target Bedrock Dedicated Server; it does not request Beta APIs or experimental gameplay toggles.

## Test and package

```bash
npm test
npm run check
npm run pack
```

The runtime integration test loads the production `main.js` through a deterministic Script API mock, emits join, block-break, leave, and snapshot events, and asserts the exact structured snapshot consumed by the manager.

The package command creates:

```text
dist/craftcontrol-telemetry-0.2.3.mcpack
```

Packaging uses sorted paths, normalized timestamps, and stripped ZIP metadata so the standalone repository and CraftControl subtree produce byte-equivalent artifacts from the same commit.

## Install on a dedicated server

Stop the Bedrock server and identify the persistent BDS data directory plus the exact world directory name. For the `itzg/minecraft-bedrock-server` image, the persistent host directory normally corresponds to `/data` inside the container.

```bash
./scripts/install.sh /mnt/storage/docker/minecraft-bedrock/data "Bedrock level"
```

The installer:

1. Validates that the world directory exists.
2. Copies the pack to `behavior_packs/craftcontrol-telemetry` and removes the legacy directory only after the new copy succeeds.
3. Normalizes pack directories to mode `755` and files to `644` so the Bedrock runtime can read them independently of the source checkout's permissions.
4. Backs up the existing `world_behavior_packs.json` when present.
5. Adds or updates this pack's UUID and version without removing other packs.

Start the Bedrock server and verify the log:

```text
[BEDROCK_TELEMETRY] {"schema":1,...,"type":"telemetry.started",...}
[BEDROCK_TELEMETRY] {"schema":1,...,"type":"snapshot.started",...}
```

Request a snapshot from the dedicated-server console:

```text
scriptevent bedrock_telemetry:sync full
```

## Upgrade

Stop Bedrock, back up the world, update the repository, run tests, rerun the installer, and start Bedrock. Pack UUIDs remain stable across compatible releases; the manifest version changes when an upgrade must be applied.

## Remove or disable

Stop Bedrock, back up `world_behavior_packs.json`, remove the entry with pack ID `8c916948-76c6-4aa5-91e0-97671dfd3830`, and start the server again. The pack directory may then be archived or removed. Existing dynamic-property telemetry remains embedded in the world so reinstalling the same pack can recover it.

The CraftControl rebrand preserves the original pack UUIDs, `bedrock_telemetry` dynamic-property key, log prefix, and script-event namespace specifically to retain existing world state and consumer compatibility.

## Persisted-state migrations

Release `0.2.2` introduces sharded storage schema version `2`, independently from telemetry protocol schema `1`. Metadata and sequence remain under `bedrock_telemetry:state`; each player is persisted under a separate `bedrock_telemetry:player:*` property. On first load of legacy storage `0` or monolithic storage `1`, the pack fills missing aggregate fields without resetting counters, validates every candidate shard, saves the untouched source JSON as `bedrock_telemetry:state_backup_v0` or `bedrock_telemetry:state_backup_v1`, writes and verifies all player shards, and commits metadata last.

On normal writes, player shards are persisted before metadata. Startup discovers every shard and promotes metadata to the highest shard sequence when recovering from an interrupted write, preventing sequence reuse. One large roster can therefore no longer exhaust a single dynamic-property value.

Migration failures never fall back to writable empty state. Persistence is blocked for that runtime, the original dynamic property remains untouched, and startup/snapshot envelopes report the blocked storage status for the manager. Unknown future storage versions are treated the same way, preventing an older pack from downgrading a newer world's data.

## Runtime capabilities

Release `0.2.3` probes stable Bedrock event signals before subscribing. Joins, leaves, respawns, deaths and kills, damage, broken and placed blocks, dimension changes, movement sampling, and snapshot requests are reported independently. A missing or throwing optional signal produces one `[BEDROCK_TELEMETRY_CAPABILITY]` warning and leaves the rest of the pack running. `telemetry.started` and `snapshot.started` include the complete capability map so consumers never present an unavailable metric as silently authoritative.

## Performance and limitations

- Block events generate log records individually in this initial release. Aggregate persistence is still batched every five seconds. Production profiling will determine whether log batching is needed.
- Distance is sampled horizontal movement, not a native Minecraft statistic.
- Gamertag is the only player identity emitted. A trusted consumer must correlate it with its private Bedrock identity registry.
- Damage and movement totals are persisted but intentionally not emitted for every occurrence; snapshots reconcile them.
- Each player's bounded aggregate record is stored independently. A single unusually large per-player record is rejected without replacing persisted storage.

## Security and privacy

The pack has no network module, no HTTP client, no player-facing commands, and no generic remote execution path. Snapshot requests use the namespaced `scriptevent` channel and only cause read-only telemetry output. Consumers must strictly validate the prefix, schema, topic, size, and field types before persistence.

## License

MIT. This project is independent and is not affiliated with Mojang Studios or Microsoft. Minecraft is a trademark of Microsoft Corporation.
