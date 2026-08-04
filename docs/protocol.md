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
