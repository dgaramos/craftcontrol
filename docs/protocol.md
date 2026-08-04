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

Protocol `schema` and pack `storageVersion` are intentionally independent. Storage version `2` shards players into separate world dynamic properties without changing protocol schema `1`; a storage migration does not require a wire-protocol version change when the emitted envelope contract remains compatible.

## Topics

- `telemetry.started`
- `player.joined`
- `player.left`
- `player.respawned`
- `player.dimension.changed`
- `entity.died`
- `block.broken`
- `block.placed`
- `snapshot.started`
- `snapshot.player`
- `snapshot.finished`

Send `/scriptevent bedrock_telemetry:sync full` from the dedicated-server console to request a full snapshot. The message body is reserved for future filters.

Damage and movement are aggregated in the snapshot rather than logged for every sample. State is flushed every five seconds and immediately before a requested snapshot. Consumers must reconcile from snapshots after either process restarts.
