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
- `block.broken`
- `block.placed`
- `blocks.changed`
- `snapshot.started`
- `snapshot.player`
- `snapshot.finished`

Send `/scriptevent bedrock_telemetry:sync full` from the dedicated-server console to request a full snapshot. The message body is reserved for future filters.

Damage and movement are aggregated in the snapshot rather than logged for every sample. State is flushed every five seconds and immediately before a requested snapshot. Consumers must reconcile from snapshots after either process restarts.

Pack `0.3.2` publishes the effective game mode of each online player. `snapshot.player` data includes a `gameMode` field with value `"survival"`, `"creative"`, or `"adventure"` when the player is online during the snapshot and the `gameModeReading` capability is supported. A missing `gameMode` field means the mode is unknown — either the player is offline or the runtime does not expose `Player.getGameMode()`. Consumers must treat a missing field as unknown rather than defaulting to any specific mode.

`player.gamemode.changed` is emitted when a player's observed mode changes between sampling cycles. Its `data` contains `previous` (the prior known value) and `current` (the new value); both are one of the three mode strings above.

Pack `0.3.1` coalesces block activity per player and five-second persistence cycle into `blocks.changed`. Its `broken` and `placed` objects contain a `total` and bounded `byType` counts. Consumers continue accepting the legacy per-block topics during rolling upgrades.

Snapshot player data in pack `0.3.0` adds `killsByType`, `distanceByDimension`, `activeTimeByDimension`, `firstDimensionVisitAt`, and `lastDimensionVisitAt`. Type and dimension maps are bounded. Visit timestamps are Unix epoch milliseconds as produced by the Bedrock JavaScript runtime.
