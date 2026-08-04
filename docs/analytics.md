# Activity and death analytics

CraftControl's Data workspace reads durable `player_history` records. It does not scrape the exporter, query Prometheus, or require the Telemetry Pack. The optional pack improves death detail and provenance when available.

## Views and filters

The Activity view includes joins, leaves, deaths, and Minecraft permission changes. The Deaths view restricts the same durable query to deaths. Filters support:

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

## Consistency limitations

Incremental events provide detailed history. Telemetry snapshots reconcile aggregates but cannot reconstruct the exact time, cause, or counterpart of an event missed while CraftControl was unavailable. Counts sourced from snapshots and rows in global history therefore have different guarantees, and the interface does not synthesize missing events.
