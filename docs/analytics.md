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

Snapshot-backed rankings remain lifetime aggregates. Durable daily evidence now supports honest seven-day and thirty-day period rankings through `GET /api/analytics/periods?days=7|30`; custom periods remain unavailable. A snapshot can repair a lifetime total after downtime but cannot reconstruct when that total was earned.

## Mining and building

`GET /api/analytics/blocks` derives a bounded lifetime view from each player's Telemetry Pack snapshot. It returns global broken/placed totals, the most frequent broken and placed block types, each player's favorite type, and separate miner and builder leaderboards. A curated ore classifier combines normal and deepslate variants for diamond, iron, gold, copper, coal, redstone, lapis, and emerald, plus Nether quartz, Nether gold, and ancient debris where appropriate.

Incremental `block.broken` and `block.placed` events update both the lifetime counter and the corresponding bounded per-type map. The next authoritative snapshot reconciles those values after downtime or a detected sequence gap. The repository limits each type map to 128 entries and the public endpoint emits only top lists, favorites, aggregate ore totals, opaque player IDs, Gamertags, and observation timestamps; it never exposes XUIDs or the complete persistence envelope.

The responsive Blocks view offers two task-focused modes. Mining presents ore cards and a selected per-ore leaderboard, while Building emphasizes placed block types and builders. All values remain explicitly lifetime-only because the pack does not yet persist time buckets.

## Combat

`GET /api/analytics/combat` combines authoritative lifetime snapshot counters with the bounded structured death history already stored by CraftControl. Snapshot evidence provides player kills, mob kills, damage dealt, and damage taken. The best available profile death count may come from a snapshot or clearly labeled derived server evidence. Structured death rows supply bounded breakdowns for cause, responsible entity or player, projectile, and observed PvP encounters.

The Combat view always renders its complete information architecture, including when every value is zero. Zero-valued summary cards, explanatory empty panels, and per-player telemetry status distinguish “nothing observed yet” from a broken or unavailable screen. Rankings omit zero-valued entries but retain their labeled container and empty explanation.

Telemetry Pack `0.3.0` retains a bounded kill map by creature type, enabling global targets and each player's favorite creature. Per-hit events are intentionally not persisted: only aggregate damage is reconciled by snapshots, avoiding high-frequency permanent logging. Lifetime Combat values remain available alongside the separately collected daily period rankings.

## Exploration

`GET /api/analytics/exploration` combines Telemetry Pack movement and dimension aggregates with manager-owned sessions and play time. It returns sampled horizontal distance, the union and visit counts of observed dimensions, recent structured dimension transitions, and bounded rankings for distance, discovered dimensions, play time, and sessions. Public player references use opaque IDs and Gamertags only.

The Exploration view always renders five summary cards, a metric picker and ranking, dimensional atlas, recent-journey log, and explorer profiles. Every area has a deliberate zero state, so opening the screen before movement telemetry exists still shows what will be collected.

Distance is a five-second horizontal movement sample. Jumps larger than 128 blocks are discarded to avoid counting long teleports. Telemetry Pack `0.3.0` separates distance and active movement time by dimension and records first/last dimension observations. Active movement time advances only on valid movement samples; manager play time can include AFK time. CraftControl exposes these limitations instead of presenting sampled distance as exact travel or session duration as active gameplay.

## Daily history and period rankings

Database schema version 4 introduces `player_daily`, one bounded aggregate row per player and local calendar day. Manager evidence increments joins and sessions immediately and splits completed play time across local midnight boundaries. Idempotent telemetry events add blocks, kills, deaths, and dimension transitions; authoritative snapshots contribute only positive deltas not already observed, including sampled distance and aggregate damage.

`GET /api/analytics/periods?days=7|30` returns totals, per-player rankings, a zero-filled daily calendar, the most active day, and a seven-by-twenty-four session heatmap. Open sessions are included at read time without prematurely persisting unfinished duration. Calendar boundaries use `TZ`—`America/Sao_Paulo` by default in this deployment—and the response names the effective timezone.

Daily collection starts when schema version 4 is deployed. Existing lifetime totals become a reconciliation baseline and are not assigned to the installation day, because that would make 7/30-day rankings historically false. Detailed sessions that predate the migration can still contribute to the heatmap, but earlier lifetime telemetry cannot be reconstructed by day. Negative snapshot differences caused by a reset never subtract historical daily evidence.
