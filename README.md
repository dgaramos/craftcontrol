<div align="center">
  <img src="apps/frontend/static/craftcontrol-mark.svg" width="112" alt="CraftControl logo">
  <h1>CraftControl</h1>
  <p><strong>A mobile-first control center for Minecraft Bedrock servers.</strong></p>
  <p>Manage worlds, players, rules, time, weather, permissions, and structured gameplay statistics without living in a server console.</p>
</div>

> [!IMPORTANT]
> CraftControl currently targets trusted private networks. Built-in authentication and CSRF protection are active, but TLS termination and hardened Docker access remain deployment requirements. Do not expose port `8082` directly to the Internet.

## Why CraftControl?

Bedrock Dedicated Server is powerful, but routine administration still means remembering property names, editing files, issuing console commands, and reconstructing player state from logs. CraftControl turns those operations into a focused interface designed for a phone first.

- **Purposeful controls:** toggles, segmented choices, contextual explanations, and a review drawer instead of a wall of raw fields.
- **Live world management:** gamerules, time, weather, operators, and safe server lifecycle actions.
- **Durable player profiles:** presence, aliases, sessions, play time, permissions, deaths, and event history survive disconnects and manager restarts.
- **Global activity analytics:** follow joins, leaves, respawns, dimension changes, deaths, and permission changes live; filter by player, period, source, cause, or responsible entity.
- **Optional world telemetry:** the companion behavior pack adds authoritative kills, blocks, damage, distance, dimensions, and structured death events.
- **Independent operation:** CraftControl does not require Prometheus, Grafana, Loki, the custom exporter, or the behavior pack.
- **Bilingual and responsive:** the complete interface works in Portuguese and English on phones, tablets, Steam Deck, and desktop browsers.

## Interface

CraftControl uses a Minecraft-inspired visual system without reproducing the game UI. Deepslate surfaces, emerald state, and copper accents keep the application recognizable while preserving readability and touch-friendly interaction.

The five primary destinations are intentionally task-oriented:

| Area | What it manages |
| --- | --- |
| Home | Server health, online players, freshness, and common destinations |
| World | World identity, generation, view distance, time, weather, and cycles |
| Players | Permanent profiles, sessions, operators, history, and telemetry |
| Data | Activity, Deaths, Rankings, Mining, Combat, Exploration, and period history |
| Rules | Gameplay, interface, mobs, drops, commands, fire, TNT, and regeneration |
| Server | Packs, network, compression, threads, and container lifecycle |

Persistent changes enter a review drawer and are applied together. Lightning-marked gamerules take effect immediately.

## Architecture

```text
Phone, tablet, or desktop
          |
          | HTTP :8082 — trusted LAN only
          v
┌────────────────────────────────────────────┐
│                CraftControl                │
│                                            │
│ Flask API ─ Service layer ─ Event runtime  │
│     │             │              │         │
│     │             │              └─ SSE    │
│     │             └─ SQLite player state   │
│     └─ validated HTTP operations           │
└───────────────┬────────────────────────────┘
                │ Docker socket + project mount
                v
      itzg/minecraft-bedrock-server
                │
                └─ optional telemetry pack
```

The process intentionally runs with one Gunicorn worker and multiple threads. Its broker, refresh lock, Docker supervisors, and SSE delivery are process-local; multiple workers would duplicate those responsibilities.

### Event-driven state

CraftControl avoids browser polling. It follows Bedrock logs and Docker lifecycle events, commits operational events to SQLite, publishes changes through Server-Sent Events, and performs targeted refreshes. A full safety reconciliation runs every 15 minutes by default.

```text
Bedrock logs ───────┐
Docker events ──────┼─> event broker ─> SQLite ─> SSE ─> browser
Manager operations ─┘        │
                             └─> targeted reconciliation
```

Cached values retain both the last observation time and the last actual change time. Stale values remain visible and are marked instead of being silently replaced with false empty data.

## Quick start

### Requirements

- Docker Engine with the Compose plugin
- An existing `itzg/minecraft-bedrock-server` deployment
- CraftControl and the Bedrock project stored as sibling directories, or a customized project mount

Expected default layout:

```text
/mnt/storage/docker/
├── minecraft-bedrock/
└── craftcontrol/
```

Create the local configuration and start the service:

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
```

Open the interface from a device on the same network:

```text
http://HOST_IP:8082
```

The planned homelab hostname is `craftcontrol.lab.home.arpa`; DNS and reverse-proxy configuration remain external to this release.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `MANAGER_PORT` | `8082` | Compatibility host port for the web interface |
| `MINECRAFT_CONTAINER` | `minecraft-bedrock` | Bedrock container managed by CraftControl |
| `MINECRAFT_PROJECT` | `/minecraft-project` | Bedrock Compose project inside CraftControl |
| `DATABASE_PATH` | `/data/manager.db` | Existing SQLite state and player-history database |
| `CONSOLE_WAIT_SECONDS` | `1` | Delay before reading console responses |
| `BOOTSTRAP_OPERATOR` | `VonCrush` | Player provisioned once as the initial in-game operator |
| `RECONCILE_SECONDS` | `900` | Full safety-reconciliation interval |
| `BACKUP_ROOT` | `/data/backups/coordinated` | Coordinated recovery-set directory |
| `AUTH_MODE` | `local` | Built-in authentication; `disabled` is LAN recovery compatibility only |
| `AUTH_COOKIE_SECURE` | `true` | Send panel session cookies over HTTPS only |
| `TZ` | `America/Sao_Paulo` | Container timezone |
| `CRAFTCONTROL_VERSION` | `0.2.16` | Release tag displayed for the active CraftControl image |

The old service name, container name, database filename, Python package, and variables remain supported deliberately. This visual rebrand does not destructively rename persistent paths. Compatibility migrations will be released separately.

## User access management

CraftControl accounts belong to players the Bedrock server has already observed. There is no separate username directory: a player's private stable identity keeps panel access attached across Gamertag changes, while the public API and interface never expose the XUID.

Three states are deliberately independent:

| State | Meaning |
| --- | --- |
| Online / offline | Whether the player is currently connected to Bedrock |
| Minecraft member / operator | Commands and administrative power inside the game |
| CraftControl viewer / operator / owner | What the player can do in this web panel |

Granting Minecraft operator status does not grant panel access, and granting panel access does not change in-game permission.

### Panel roles

| Capability | Viewer | Operator | Owner |
| --- | :---: | :---: | :---: |
| Read status, players, history, and telemetry | Yes | Yes | Yes |
| Configure the server, world, gamerules, time, and weather | No | Yes | Yes |
| Start and restart Bedrock | No | Yes | Yes |
| Stop Bedrock | No | No | Yes |
| Change Minecraft operator permission | No | Yes | Yes |
| Manage panel users and the Telemetry Pack | No | No | Yes |

Authorization is enforced by the API; hiding a control in the browser is not treated as a security boundary.

### Claim the first owner

The player must have joined the server at least once. Generate the one-time bootstrap code:

```bash
docker compose exec craftcontrol craftcontrol auth bootstrap --player VonCrush
```

On the login screen, open **First access or invitation**, enter the Gamertag and code, then choose a password containing 8–128 characters. The bootstrap code expires after 30 minutes and can create only the first active owner.

### Invite or recover a player from the interface

As an owner, open **Players**, select a player, and use the separate **CraftControl access** card:

1. choose `viewer`, `operator`, or `owner`;
2. press **Generate access**;
3. copy the one-time code shown by the interface;
4. send it through a private channel;
5. the player uses **First access or invitation** to set a personal password.

Invitation codes expire after 15 minutes, work once, and are stored only as SHA-256 hashes. Generating a recovery code for an active account follows the same flow. Suspending access immediately revokes all of that player's sessions without deleting Minecraft permissions, telemetry, or history. CraftControl prevents suspension of the last active owner.

The CLI provides break-glass equivalents:

```bash
# Invite an observed player
docker compose exec craftcontrol craftcontrol auth invite Nicole --role operator

# Reset an active account's password without changing its existing role
docker compose exec craftcontrol craftcontrol auth recover VonCrush
```

Tokens are displayed once. Avoid putting them in screenshots, tickets, shared logs, or shell history. Password change and user-controlled revocation of other sessions are planned; until then, use a recovery code to replace a forgotten password and owner suspension to revoke access.

### Sessions and browser security

Passwords use salted `scrypt` hashes. Opaque session identifiers are stored only as hashes, expire after 12 idle hours or 7 absolute days, and are revoked on logout or suspension. Five failed login attempts within 15 minutes temporarily block that normalized Gamertag.

Every authenticated state-changing request requires a CSRF token bound to that exact session. The browser handles it automatically and the server also validates the request origin. `AUTH_COOKIE_SECURE=true` requires HTTPS. Authelia or another external identity gate is optional for trusted-LAN deployments, but removing it also removes its MFA and second authentication layer. CraftControl is not ready for direct Internet exposure while it retains direct Docker socket access.

For recovery procedures and security details, see [Local authentication and authorization](docs/authentication.md).

## Player history

CraftControl stores permanent player data in `./data/manager.db`:

- private XUID-backed identity and public opaque profile ID;
- current Gamertag and preserved aliases;
- online/offline state and active session;
- session count and accumulated play time;
- operator and Bedrock permission state;
- connection, disconnection, permission, and death history;
- optional structured behavior-pack statistics.

XUIDs never appear in public API responses or the interface. Disconnecting a player closes the session and marks the profile offline; it never deletes the profile.

The Players workspace uses a compact roster so presence, Minecraft permission, and CraftControl access remain visibly distinct. Selecting a player opens a consolidated individual profile: authoritative combat totals and kills by creature, blocks broken and placed by type, exploration by dimension, and headline activity statistics appear before recent evidence and administration. Sessions, detailed deaths, and the technical timeline remain available in collapsible records without being mistaken for complete lifetime totals. In-game operator status and panel role remain independent. Recent sessions distinguish active, normally closed, and inferred closures while separating duration from localized start/end timestamps. Server-wide player rules live in a separate, always-visible section instead of being hidden in the player cards.

### Death data

Without the behavior pack, death messages are parsed from server logs and explicitly shown as derived data. With structured telemetry active, new death events are stored with the cause, killer entity or player, and projectile when Bedrock supplies them. Aggregate snapshots recover totals but cannot reconstruct details for older events.

## Activity and death analytics

The **Data** workspace provides seven global views backed by permanent player history, daily buckets, and authoritative lifetime aggregates:

- **Activity** combines joins, leaves, respawns, dimension changes, deaths, and permission changes. New durable events refresh the active view through SSE without browser polling.
- **Deaths** focuses on cause, responsible entity or player, projectile, dimension, and coordinates when that evidence exists.
- **Rankings** compares lifetime activity, combat, blocks, and exploration aggregates in a podium, top-ten leaderboard, and server record cards.
- **Blocks** separates Mining from Building, with server totals, favorite block types, miner/builder leaderboards, and per-ore rankings.
- **Combat** keeps its complete layout visible even before the first fight, then fills lifetime deaths, PvP and mob kills, damage, structured causes/opponents/projectiles, PvP encounters, and player summaries as evidence arrives.
- **Exploration** keeps a permanent atlas visible with sampled horizontal distance, discovered dimensions, dimension visits, play time, sessions, recent dimension transitions, and explorer profiles.
- **Periods** provides honest 7/30-day rankings, a daily activity calendar, a most-active-day record, and a session heatmap in the configured timezone.

Both views support player, lifetime/7-day/30-day, source, event-type, and free-text detail filters. Results are paginated server-side and every item identifies whether it came from the structured Telemetry Pack or server/manager evidence. When a structured and derived death describe the same player within the same short window, the interface prefers the structured event while retaining the raw derived evidence privately in SQLite. XUIDs and raw log lines never leave the repository layer.

Player names in the global feed open the permanent player profile and return to the same analytics filters. Death entries offer a focused detail dialog so cause, killer, projectile, dimension, coordinates, source, and timestamp remain readable on a phone. Creature, projectile, block, navigation, action, state, and metric icons use original bundled pixel-art SVG sprites designed for CraftControl's deepslate interface, without platform emoji or third-party game textures. Block identifiers receive Portuguese and English names plus semantic family icons, with a neutral localized fallback for unknown blocks. See the [visual system rules](docs/design-system.md).

Snapshots can recover aggregate totals after downtime, but they cannot recreate every missed historical event. Empty states and source labels preserve that distinction instead of presenting missing details as zero.

Lifetime rankings combine manager-owned play time, session count, and longest-session evidence with Telemetry Pack deaths, kills, blocks, damage, distance, and dimensions. Period rankings are intentionally unavailable until detailed history can prove them; CraftControl never relabels lifetime snapshots as seven- or thirty-day statistics.

## Optional telemetry pack

The companion Bedrock behavior pack runs inside the world and emits schema-versioned JSON through content logs. CraftControl consumes incremental events and requests authoritative snapshots after startup, reconnects, manual refreshes, and recovery.

Current structured metrics include:

- joins, leaves, respawns, and first/last observation;
- deaths, player kills, mob kills, causes, projectiles, and bounded kills by creature type;
- blocks broken and placed, including bounded per-type totals;
- damage dealt and received;
- sampled horizontal distance and active movement time by dimension;
- dimensions visited with first and last observation timestamps.

Block changes are coalesced per player into five-second incremental batches to limit content-log and database amplification. Authoritative snapshots still recover lifetime totals after a missed batch, while unrecoverable per-event detail is never invented.

The manager remains fully usable when the pack is absent or temporarily unavailable. The embedded **CraftControl Telemetry Pack** integration provides native status, installation, upgrade, disable, removal, backup, and rollback commands:

```bash
docker compose exec craftcontrol craftcontrol telemetry status
docker compose exec craftcontrol craftcontrol telemetry install
```

Installation is idempotent, writes only to persistent Bedrock data, creates a recoverable backup, and never restarts Bedrock automatically. See [Telemetry Pack integration](docs/telemetry-pack.md) for the complete command and recovery guide.

The **Server → Telemetry Pack** panel exposes the same installer service on mobile and desktop. It reports embedded and installed versions, world association, runtime health, and the timestamp of the latest pack response. Install, upgrade, disable, and rollback actions create a backup first and leave the required Bedrock restart under explicit operator control.

Compact release tags identify the active CraftControl image and the Behavior Pack version observed at runtime. The Server panel also separates image activation time, installed pack file time, and latest pack response so an installed upgrade is not confused with a pack already loaded by Bedrock.

Telemetry reconciliation is sequence-aware. Missing ranges and pack resets automatically degrade health and request a coalesced authoritative snapshot; stale deltas are rejected, and health becomes healthy again only after a complete snapshot. The panel surfaces the current sequence, completed-snapshot time, gap count, missing-event count, and recovery errors.

Telemetry Pack storage has its own migration version, separate from the log protocol. Pack `0.2.2` validates and backs up monolithic world state before migrating it to sharded storage version `2`: metadata remains in `bedrock_telemetry:state`, while every player receives an independent bounded property. Invalid, oversized, or future-version state blocks persistence instead of overwriting counters. CraftControl surfaces that condition as degraded health even if log delivery itself remains available.

Pack `0.2.3` capability-checks every optional stable Bedrock event before subscription. Missing signals disable only their corresponding metric and are reported in startup/snapshot envelopes. The Telemetry Pack panel distinguishes full from partial support and lists every available or unavailable metric, preventing unsupported data from being presented as a real zero.

## Data and backups

CraftControl does not store the Minecraft world. World data remains in the Bedrock project, normally:

```text
/mnt/storage/docker/minecraft-bedrock/data/
```

CraftControl state lives in:

```text
./data/manager.db
```

The embedded SQLite database uses transactional, sequential migrations tracked by `PRAGMA user_version`. Existing databases receive an immutable SQLite backup under `data/backups/` before the first pending migration; a failed migration rolls back and prevents startup on a partially upgraded schema. See [Database migrations](docs/database-migrations.md).

Use CraftControl's coordinated backup command instead of copying a live SQLite file or world directory:

```bash
docker compose exec craftcontrol craftcontrol backup create
docker compose exec craftcontrol craftcontrol backup list
docker compose exec craftcontrol craftcontrol backup verify BACKUP_ID
```

When Bedrock is running, CraftControl holds world saves only for the copy window, creates a consistent SQLite backup, resumes saves even after an error, and writes SHA-256 checksums to a versioned manifest. Recovery sets contain the world, `manager.db`, server configuration, allowlists, permissions, and behavior-pack files. Preview retention with `craftcontrol backup prune --keep 7`; deletion additionally requires `--yes`.

Restore is deliberately offline, refuses to run while Bedrock is active, and creates a pre-restore recovery copy before replacing the world and database. See [Coordinated backup and restore](docs/backup-and-restore.md) for the complete tested runbook. Cached settings can be reconstructed; player aliases, sessions, detailed history, and manager-side event evidence cannot always be rebuilt from a world backup alone.

Telemetry envelopes used for recovery and diagnostics are retained in SQLite with a bounded 10,000-event window. Permanent player history remains separate and is not subject to that operational retention limit.

## Updating

Production deployments must use the guarded workflow from a clean `main`
checkout. It anchors every Compose operation to the production project,
verifies the live data and Bedrock mounts before creating a coordinated backup,
preserves `.env` and SQLite checksums during synchronization, and runs health,
frontend, authentication, CLI, and Bedrock canaries:

```bash
bin/deploy-craftcontrol --check
bin/deploy-craftcontrol
```

The default production root is `/mnt/storage/docker/craftcontrol`. An explicit
`CRAFTCONTROL_DEPLOY_ROOT` may be used for an equivalent installation. Never
run a bare `docker compose up` from the development checkout: relative bind
mounts would point at development data. Never overwrite the world, `.env`, or
manager database as part of an application update.

## API

The authenticated OpenAPI 3.1 contract is available at `/api/openapi.json`,
with an interactive Swagger UI at `/api/docs`. Both use the same local session
as the panel. Swagger automatically attaches the session CSRF token to unsafe
"Try it out" requests; it does not bypass capability checks. The contract is
the canonical description of the business API, while
`packages/contracts/http-surface.json` remains a route-level migration guard.
Stable response envelopes are expressed as reusable schemas and generate the
frontend declarations at `apps/frontend/static/js/api-contract.d.ts`. Regenerate
them with `python packages/contracts/generate_types.py --write`; the test suite
and quality gate reject stale declarations.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/status` | Bedrock container status |
| `GET` | `/api/schema` | Editable settings and gamerule schema |
| `GET` | `/api/state` | Cached server state and freshness |
| `POST` | `/api/refresh` | Asynchronous full reconciliation and telemetry snapshot |
| `GET` | `/api/events` | Persisted and live SSE notifications |
| `GET` | `/api/players` | Permanent player roster |
| `GET` | `/api/players/profile/<id>` | One opaque player profile and history |
| `PUT` | `/api/players/<name>/operator` | Grant or revoke in-game operator status |
| `GET` | `/api/analytics/activity` | Filtered and paginated global activity/death history |
| `GET` | `/api/analytics/rankings` | Sanitized lifetime leaderboards and record holders |
| `GET` | `/api/analytics/blocks` | Sanitized mining, building, block-type, and ore aggregates |
| `GET` | `/api/analytics/combat` | Sanitized combat totals, rankings, death evidence, and PvP encounters |
| `GET` | `/api/analytics/exploration` | Sanitized travel, dimension, presence, and explorer aggregates |
| `GET` | `/api/analytics/periods` | Sanitized 7/30-day rankings, calendar, and session heatmap |
| `PUT` | `/api/config` | Validate and queue persistent configuration |
| `PUT` | `/api/gamerules/<rule>` | Apply an allowlisted gamerule |
| `POST` | `/api/world/<action>` | Run an allowlisted world shortcut |
| `POST` | `/api/time/<action>` | Run validated time and weather operations |
| `POST` | `/api/server/<action>` | Start, stop, restart, or apply the server |
| `GET` | `/api/auth/me` | Current panel identity, role, capabilities, and CSRF token |
| `POST` | `/api/auth/login` | Start a local authenticated session |
| `POST` | `/api/auth/claim` | Claim an invitation or recovery code and set a password |
| `POST` | `/api/auth/logout` | Revoke the current session |
| `GET` | `/api/auth/access` | Owner-only player access roster |
| `POST` | `/api/auth/access/invite` | Owner-only invitation or recovery code creation |
| `PUT` | `/api/auth/access/<player>/suspend` | Owner-only access suspension and session revocation |

This is an internal API and may evolve before a stable release. There is no arbitrary console or shell endpoint.

## Security status

Current safeguards:

- local player-backed accounts with salted `scrypt` password hashes;
- opaque, revocable, server-side sessions with idle and absolute expiration;
- owner, operator, and viewer capability enforcement in the API;
- one-time bootstrap, invitation, and recovery codes stored only as hashes;
- login throttling and security audit records;
- session-bound CSRF tokens required for every state-changing authenticated request;
- explicit allowlists for every server action and command;
- validation of types, ranges, lengths, and characters;
- atomic `.env` updates;
- no XUID exposure;
- `no-new-privileges` on the application container;
- no dependency on outbound telemetry or observability services.

Current limitations:

- no TLS termination;
- direct Docker socket access.

Panel accounts attach to observed Minecraft player profiles while remaining independent from in-game operator status. See [Local authentication and authorization](docs/authentication.md). CSRF validation is transparent to the interface: the API issues a token bound to the active opaque session, and the browser sends it in `X-CSRF-Token` for every state-changing request. Keep HTTPS and a trusted external boundary in place until direct Docker access is replaced with a restricted operations boundary.

## Development

CraftControl uses Python 3.12, Flask, Gunicorn, SQLite, Docker SDK for Python, and dependency-free browser JavaScript.

Run the complete quality gate:

```bash
python -m unittest discover -s tests -v
python -m compileall -q apps/backend/minecraft_manager apps/backend/app.py apps/backend/wsgi.py app.py wsgi.py
node --check apps/frontend/static/app.js
docker compose config --quiet
git diff --check
```

The application is a modular monolith with layered use cases, explicit dependency injection, ports and adapters at meaningful external boundaries, and an internal event-driven runtime. Production dependencies are assembled manually in `composition.py`; no service locator or dependency-injection framework is required.

```text
apps/backend/minecraft_manager/
├── composition.py  # production composition root
├── ports.py        # structural boundary contracts
├── http/           # HTTP mapping grouped by domain
├── players/        # player application use cases
├── services.py     # compatibility orchestration facade
├── repository.py   # compatibility SQLite repository
├── runtime.py      # event supervisors and reconciliation
└── adapters        # Bedrock, Docker, files, and telemetry installation
```

The modular migration is incremental and preserves public endpoints, SQLite data, environment variables, and deployment paths. See [Architecture](docs/architecture.md) for system context, dependency rules, dependency injection, event consistency, deliberate non-goals, and the target module layout.

Quality checks follow the deployment boundaries and can run independently:

```bash
bin/check-frontend
bin/check-backend
bin/check-contracts
bin/check-integration
```

`bin/check` runs the complete local gate. GitHub Actions and Gitea Actions run
the four gates as independent jobs so a failure identifies the owning boundary.

### Split-image preview

The migration now produces independent `craftcontrol-frontend:0.1.0` and
`craftcontrol-backend:0.1.0` images through `docker-compose.split.yml`. The
frontend is a read-only Nginx service with no persistent or privileged mounts;
it owns the browser origin and proxies `/api/*`, including unbuffered SSE, to
the private backend. Only the backend contains Python, SQLite access, Bedrock
mounts, backups, and Docker operations.

```bash
docker compose -f docker-compose.split.yml config --quiet
docker compose -f docker-compose.split.yml build
bin/check-split-runtime
```

The split Compose file currently publishes the preview on port `18082` to avoid
colliding with production. It is not yet the supported production deployment;
continue using `bin/deploy-craftcontrol` until authenticated session/CSRF,
persistent-state, rollback, and production cutover canaries are complete.

## Roadmap

The immediate direction is:

1. complete the CraftControl visual and compatibility rebrand;
2. expose the integrated CraftControl Telemetry Pack in the responsive web interface;
3. add player-backed local accounts, roles, sessions, and CSRF protection;
4. expand deaths, rankings, mining, building, combat, exploration, and activity analytics;
5. add coordinated backup, export, retention, and operational diagnostics.

## License and trademarks

No project license has been declared yet. All rights remain with the repository owner until a license is added.

CraftControl is an independent project and is not affiliated with Mojang Studios or Microsoft. Minecraft is a trademark of Microsoft Corporation.
