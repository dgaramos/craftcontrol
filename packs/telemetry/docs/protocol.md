# Telemetry protocol

Every record is written as one server log line:

```text
[BEDROCK_TELEMETRY] {"schema":1,"sequence":42,"type":"entity.died",...}
```

Consumers must ignore lines without the exact prefix, reject unsupported schema versions, and treat `(world, sequence, type)` as an event identity. Incremental events can be replayed or lost around an unclean Bedrock stop; snapshots are authoritative.

## Event envelope

| Field | Description |
| --- | --- |
| `schema` | Protocol schema, currently `1` |
| `sequence` | Monotonic world-local sequence |
| `type` | Allowlisted event topic |
| `timestamp` | Unix epoch in milliseconds |
| `player` | Player name or `null`; no XUID is emitted |
| `data` | Topic-specific payload |

`telemetry.started` and `snapshot.started` include a `storage` object with the independently versioned persisted-state status and a `capabilities` map. Each capability contains `supported` and may include a bounded startup error. Consumers must treat `persistenceBlocked: true` as degraded even when a snapshot reaches `snapshot.finished`, and must label metrics from unsupported capabilities as unavailable rather than zero.

Protocol `schema` and pack `storageVersion` are intentionally independent. Storage version `2` introduced per-player shards. Storage version `3` adds bounded creature-kill and per-dimension movement/time/visit maps while preserving protocol schema `1`; a storage migration does not require a wire-protocol version change when the emitted envelope contract remains compatible.

## Topics

- `telemetry.started`
- `player.joined`
- `player.left`
- `player.respawned`
- `player.dimension.changed`
- `player.gamemode.changed`
- `entity.died`
- `blocks.changed`
- `snapshot.started`
- `snapshot.player`
- `snapshot.finished`

Send `/scriptevent bedrock_telemetry:sync full` from the dedicated-server console to request a full snapshot. The message body is reserved for future filters.

Damage and movement are aggregated in the snapshot rather than logged for every sample. State is flushed every five seconds and immediately before a requested snapshot. Consumers must reconcile from snapshots after either process restarts.

Pack `0.3.2` publishes the effective game mode of each online player. `snapshot.player` data includes a `gameMode` field with value `"survival"`, `"creative"`, or `"adventure"` when the player is online during the snapshot and the `gameModeReading` capability is supported. A missing `gameMode` field means the mode is unknown — either the player is offline or the runtime does not expose `Player.getGameMode()`. Consumers must treat a missing field as unknown rather than defaulting to any specific mode.

`player.gamemode.changed` is emitted when a player's observed mode changes between sampling cycles. Its `data` contains `previous` (the prior known value) and `current` (the new value); both are one of the three mode strings above.

Pack `0.4.0` publishes coalesced block activity per player and five-second persistence cycle through `blocks.changed`. Its `broken` and `placed` objects contain a `total` and bounded `byType` counts.

Snapshot player data in pack `0.3.0` adds `killsByType`, `distanceByDimension`, `activeTimeByDimension`, `firstDimensionVisitAt`, and `lastDimensionVisitAt`. Type and dimension maps are bounded. Visit timestamps are Unix epoch milliseconds as produced by the Bedrock JavaScript runtime.

## Version history

| Pack | Storage | Key additions |
| --- | --- | --- |
| 0.4.0 | 3 | Removes deprecated per-block topics; `blocks.changed` is the sole incremental block-activity topic |
| 0.3.0 | 3 | `killsByType`, `distanceByDimension`, `activeTimeByDimension`, `firstDimensionVisitAt`, `lastDimensionVisitAt` in snapshot player data; bounded type and dimension maps |
| 0.3.1 | 3 | `blocks.changed` coalesces per-player block activity per five-second cycle; `block.broken` and `block.placed` deprecated |
| 0.3.2 | 3 | `player.gamemode.changed` emitted when game mode changes between cycles; `gameMode` field in `snapshot.player` when `gameModeReading` capability is supported and the player is online |

Protocol schema `1` is unchanged across all pack versions listed above. Storage version `3` is unchanged from 0.3.0. Per-player dynamic properties are bounded to 30 KB per shard; writes that would exceed that limit are caught and logged as errors rather than silently corrupting state.

## Capabilities

The `capabilities` map in `telemetry.started` and `snapshot.started` lists the runtime availability of each optional feature. A capability object contains `supported: true | false` and, when false, may include a bounded startup `error` string.

| Capability | Feature |
| --- | --- |
| `blocksBroken` | `playerBreakBlock` event subscription |
| `blocksPlaced` | `playerPlaceBlock` event subscription |
| `damageAggregates` | `entityHurt` event subscription |
| `deathsAndKills` | `entityDie` event subscription |
| `dimensionChanges` | `playerDimensionChange` event subscription |
| `gameModeReading` | `Player.getGameMode()` — present from pack 0.3.2 |
| `movementSampling` | `system.runInterval` + `world.getAllPlayers` |
| `playerJoins` | `playerJoin` event subscription |
| `playerLeaves` | `playerLeave` event subscription |
| `playerRespawns` | `playerSpawn` event subscription |
| `snapshotRequests` | `system.afterEvents.scriptEventReceive` subscription |
