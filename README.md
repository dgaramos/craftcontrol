<div align="center">
  <img src="static/craftcontrol-mark.svg" width="112" alt="CraftControl logo">
  <h1>CraftControl</h1>
  <p><strong>A mobile-first control center for Minecraft Bedrock servers.</strong></p>
  <p>Manage worlds, players, rules, time, weather, permissions, and structured gameplay statistics without living in a server console.</p>
</div>

> [!IMPORTANT]
> CraftControl currently targets trusted private networks. Built-in authentication, CSRF protection, and hardened Docker access are planned but are not part of this release. Do not expose port `8082` directly to the Internet.

## Why CraftControl?

Bedrock Dedicated Server is powerful, but routine administration still means remembering property names, editing files, issuing console commands, and reconstructing player state from logs. CraftControl turns those operations into a focused interface designed for a phone first.

- **Purposeful controls:** toggles, segmented choices, contextual explanations, and a review drawer instead of a wall of raw fields.
- **Live world management:** gamerules, time, weather, operators, and safe server lifecycle actions.
- **Durable player profiles:** presence, aliases, sessions, play time, permissions, deaths, and event history survive disconnects and manager restarts.
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
| `TZ` | `America/Sao_Paulo` | Container timezone |

The old service name, container name, database filename, Python package, and variables remain supported deliberately. This visual rebrand does not destructively rename persistent paths. Compatibility migrations will be released separately.

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

### Death data

Without the behavior pack, death messages are parsed from server logs and explicitly shown as derived data. With structured telemetry active, new death events are stored with the cause, killer entity or player, and projectile when Bedrock supplies them. Aggregate snapshots recover totals but cannot reconstruct details for older events.

## Optional telemetry pack

The companion Bedrock behavior pack runs inside the world and emits schema-versioned JSON through content logs. CraftControl consumes incremental events and requests authoritative snapshots after startup, reconnects, manual refreshes, and recovery.

Current structured metrics include:

- joins, leaves, respawns, and first/last observation;
- deaths, player kills, mob kills, causes, and projectiles;
- blocks broken and placed, including bounded per-type totals;
- damage dealt and received;
- sampled horizontal distance;
- dimensions visited.

The manager remains fully usable when the pack is absent or temporarily unavailable. The embedded **CraftControl Telemetry Pack** integration provides native status, installation, upgrade, disable, removal, backup, and rollback commands:

```bash
docker compose exec craftcontrol craftcontrol telemetry status
docker compose exec craftcontrol craftcontrol telemetry install
```

Installation is idempotent, writes only to persistent Bedrock data, creates a recoverable backup, and never restarts Bedrock automatically. See [Telemetry Pack integration](docs/telemetry-pack.md) for the complete command and recovery guide.

The **Server → Telemetry Pack** panel exposes the same installer service on mobile and desktop. It reports embedded and installed versions, world association, runtime health, and the timestamp of the latest pack response. Install, upgrade, disable, and rollback actions create a backup first and leave the required Bedrock restart under explicit operator control.

Telemetry reconciliation is sequence-aware. Missing ranges and pack resets automatically degrade health and request a coalesced authoritative snapshot; stale deltas are rejected, and health becomes healthy again only after a complete snapshot. The panel surfaces the current sequence, completed-snapshot time, gap count, missing-event count, and recovery errors.

## Data and backups

CraftControl does not store the Minecraft world. World data remains in the Bedrock project, normally:

```text
/mnt/storage/docker/minecraft-bedrock/data/
```

CraftControl state lives in:

```text
./data/manager.db
```

Back up `manager.db` together with its `-wal` and `-shm` companions when present. Cached settings can be reconstructed; player aliases, sessions, detailed history, and manager-side event evidence cannot always be rebuilt from a world backup.

## Updating

For an in-place Git checkout:

```bash
git pull --ff-only
docker compose up -d --build
```

When development and deployment use separate directories, copy the source while preserving `.env` and `data/`, then rebuild. Never overwrite the world or manager database as part of an application update.

## API

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
| `PUT` | `/api/config` | Validate and queue persistent configuration |
| `PUT` | `/api/gamerules/<rule>` | Apply an allowlisted gamerule |
| `POST` | `/api/world/<action>` | Run an allowlisted world shortcut |
| `POST` | `/api/time/<action>` | Run validated time and weather operations |
| `POST` | `/api/server/<action>` | Start, stop, restart, or apply the server |

This is an internal API and may evolve before a stable release. There is no arbitrary console or shell endpoint.

## Security status

Current safeguards:

- explicit allowlists for every server action and command;
- validation of types, ranges, lengths, and characters;
- atomic `.env` updates;
- no XUID exposure;
- `no-new-privileges` on the application container;
- no dependency on outbound telemetry or observability services.

Current limitations:

- no built-in authentication or authorization;
- no CSRF protection;
- no TLS termination;
- direct Docker socket access.

The planned community security model attaches panel accounts to observed Minecraft player profiles, uses one-time invitations and local password authentication, keeps panel roles separate from in-game operator status, adds server-side sessions and CSRF protection, and later replaces direct Docker access with a restricted operations boundary.

## Development

CraftControl uses Python 3.12, Flask, Gunicorn, SQLite, Docker SDK for Python, and dependency-free browser JavaScript.

Run the complete quality gate:

```bash
python -m unittest discover -s tests -v
python -m compileall -q minecraft_manager app.py wsgi.py
node --check static/app.js
docker compose config --quiet
git diff --check
```

The application follows a layered structure:

```text
minecraft_manager/
├── routes.py       # HTTP mapping
├── services.py     # use-case orchestration
├── repository.py   # SQLite persistence
├── runtime.py      # log and Docker event supervisors
├── bedrock.py      # console adapter and parsers
├── docker_ops.py   # allowlisted lifecycle operations
├── files.py        # atomic configuration access
├── telemetry.py   # structured envelope validation
├── schema.py       # editable fields and validation
└── config.py       # environment-backed settings
```

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
