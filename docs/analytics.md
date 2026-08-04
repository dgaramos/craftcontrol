# Activity and death analytics

CraftControl's Data workspace reads durable `player_history` records. It does not scrape the exporter, query Prometheus, or require the Telemetry Pack. The optional pack improves death detail and provenance when available.

## Views and filters

The Activity view includes joins, leaves, respawns, dimension changes, deaths, and Minecraft permission changes. The Deaths view restricts the same durable query to deaths. Filters support:

- event type;
- current Gamertag or a preserved alias;
- lifetime, seven days, or thirty days;
- structured Telemetry Pack evidence or server/manager evidence;
- free-text matching for player, cause, killer, projectile, and other bounded event detail;
- pages of up to 50 records, with the browser using 25.

The endpoint is `GET /api/analytics/activity`. Query parameters are `kind`, `player`, `source`, `search`, `days`, `page`, and `page_size`. Values are allowlisted and bounded in the application service.

## Privacy and provenance

The repository maps private identities to opaque public IDs and current names. It emits an explicit set of detail fields and never returns XUIDs or raw log evidence. Coordinates appear only when a structured death event supplies them.

Log-derived deaths remain stored as evidence. If a structured death for the same identity occurs within ten seconds, global analytics suppresses the derived duplicate and presents the richer structured event without deleting either database record.

Respawns and dimension changes are emitted by the optional Telemetry Pack and persisted idempotently using the world sequence in their event key. The internal broker publishes a targeted state change after ingestion; while Data is open, the browser's existing SSE connection refreshes the view without a polling loop. Player links resolve through opaque public IDs, and death details remain inside a focused responsive dialog.

## Consistency limitations

Incremental events provide detailed history. Telemetry snapshots reconcile aggregates but cannot reconstruct the exact time, cause, or counterpart of an event missed while CraftControl was unavailable. Counts sourced from snapshots and rows in global history therefore have different guarantees, and the interface does not synthesize missing events.

## Rankings and records

`GET /api/analytics/rankings` returns bounded lifetime leaderboards. Manager evidence provides play time, session count, and longest session. Telemetry snapshots provide player kills, mob kills, blocks broken and placed, damage dealt and received, horizontal distance, and dimensions visited. Deaths use the best available source per profile.

Every entry contains only the opaque public player ID, current Gamertag, value, source, and observation timestamp. The UI groups metrics into Activity, Combat, Blocks, and Exploration; each category offers a selected podium, top-ten list, and one record card per metric. Player names link to the permanent profile.

The current snapshots are lifetime aggregates. Seven-day, thirty-day, and custom-period rankings must remain unavailable until durable time-bucketed evidence exists. A snapshot can repair a lifetime total after downtime but cannot reconstruct when that total was earned.
