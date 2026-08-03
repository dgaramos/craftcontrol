# Minecraft Bedrock Manager

A mobile-first web control panel for managing a self-hosted Minecraft Bedrock server from a phone, tablet, or desktop browser.

The manager provides a focused graphical interface for common server settings, live gamerules, player presence, world shortcuts, and container operations. It is designed for a private homelab and currently targets the [`itzg/minecraft-bedrock-server`](https://github.com/itzg/docker-minecraft-bedrock-server) container layout used by the companion Bedrock project.

> [!IMPORTANT]
> This project is intended for trusted local networks. It does not provide built-in authentication and must not be exposed directly to the Internet.

## Highlights

- Responsive, touch-friendly interface with a Minecraft-inspired visual design
- Portuguese and English interface with a browser-persisted language preference
- Contextual help text for every server setting and gamerule
- Touch-friendly toggles and segmented option controls instead of ambiguous boolean dropdowns
- Persistent server settings managed through the Bedrock project's `.env` file
- Live gamerule updates without editing files or opening a console
- Current container status and cached online-player list
- Manual state refresh from the web interface
- One-tap shortcuts for day, night, and clear weather
- Start, stop, restart, and apply operations for the Bedrock container
- SQLite state cache initialized automatically at startup
- Strict allowlists for editable properties, gamerules, and console commands
- No generic command shell exposed by the API

## Screens and settings

The interface groups configuration into practical categories:

- **General:** server name, game mode, difficulty, cheats, and player limit
- **World:** view distance, simulation distance, world name, seed, world type, and forced game mode
- **Players:** idle timeout, default permission, allowlist, and Xbox Live authentication
- **Packs:** required resource packs
- **Network:** LAN visibility and IPv4/IPv6 Bedrock ports
- **Advanced:** thread and compression settings
- **Interface:** coordinates, days played, death messages, and recipe messages
- **Gameplay:** PvP, keep inventory, natural regeneration, immediate respawn, and spawn radius
- **Time and weather:** daylight, weather, fire, TNT, and random tick behavior
- **Mobs, drops, and commands:** the corresponding Bedrock gamerules

Persistent settings require the server container to be recreated. Live gamerules and quick actions are sent directly to the running Bedrock server and take effect immediately.

## Architecture

```text
Mobile or desktop browser
          |
          | HTTP :8082 (LAN only)
          v
Minecraft Bedrock Manager
  |       |                |
  |       |                +-- /data/manager.db
  |       |                    cached state and players
  |       |
  |       +-- /minecraft-project/.env
  |           persistent server configuration
  |
  +-- /var/run/docker.sock
      container status, lifecycle, and Bedrock console access
          |
          v
Minecraft Bedrock Server
```

The manager uses one Gunicorn worker with multiple threads so the in-process refresh lock and background refresh state remain consistent. On startup, it creates the SQLite database if necessary and asynchronously queries the Bedrock container to populate the interface.

The Python application follows a layered package structure:

```text
minecraft_manager/
├── __init__.py      # Flask application factory
├── routes.py        # HTTP endpoints and response mapping
├── services.py      # Use-case orchestration and refresh lifecycle
├── bedrock.py       # Bedrock console adapter and log parsers
├── docker_ops.py    # Allowlisted container lifecycle operations
├── files.py         # Atomic .env and server.properties access
├── repository.py    # SQLite state repository
├── schema.py        # Editable fields, gamerules, and validation
└── config.py        # Environment-backed runtime configuration
```

`wsgi.py` is the production entry point used by Gunicorn. The top-level `app.py` remains only as a compatibility entry point for Flask tooling. HTTP routes contain no direct Docker, filesystem, or SQLite implementation logic, which keeps infrastructure replaceable and the core behavior testable.

## Requirements

- Docker Engine with the Compose plugin
- An existing Minecraft Bedrock Compose project
- A Bedrock container named `minecraft-bedrock`, or a custom name configured through `MINECRAFT_CONTAINER`
- The manager and Bedrock project stored as sibling directories by default:

```text
/mnt/storage/docker/
├── minecraft-bedrock/
└── minecraft-bedrock-manager/
```

The default deployment expects the Bedrock project at `../minecraft-bedrock` relative to this repository.

## Installation

Clone or copy the project into the Docker services directory:

```bash
cd /mnt/storage/docker/minecraft-bedrock-manager
cp .env.example .env
docker compose up -d --build
```

Confirm that the container is healthy:

```bash
docker compose ps
docker compose logs --tail=100 minecraft-bedrock-manager
```

Open the manager from another device on the same local network:

```text
http://HOST_IP:8082
```

Replace `HOST_IP` with the LAN address of the Docker host, for example `192.168.1.50`.

## Configuration

The manager's own configuration is stored in `.env`:

| Variable | Default | Description |
| --- | --- | --- |
| `MANAGER_PORT` | `8082` | Host TCP port used by the web interface |
| `MINECRAFT_CONTAINER` | `minecraft-bedrock` | Name of the managed Bedrock container |
| `MINECRAFT_PROJECT` | `/minecraft-project` | Bedrock project path inside the manager container |
| `DATABASE_PATH` | `/data/manager.db` | SQLite cache location inside the container |
| `CONSOLE_WAIT_SECONDS` | `1` | Delay before reading Bedrock console responses |
| `TZ` | `America/Sao_Paulo` | Container timezone |

The host-side Bedrock project mount is defined in `docker-compose.yml`:

```yaml
- ../minecraft-bedrock:/minecraft-project
```

If the projects are not sibling directories, update the source side of this mount. The `MINECRAFT_PROJECT` variable normally should remain `/minecraft-project` because it represents the path inside the manager container.

## How configuration changes work

There are two distinct update paths:

### Persistent server settings

1. The manager validates the submitted value against its allowlist and type constraints.
2. It updates the Minecraft Bedrock project's `.env` file atomically.
3. The value is stored in the manager cache.
4. The interface applies the change by recreating the Bedrock service with Docker Compose.

The world data directory is not replaced or deleted during this operation.

### Live gamerules and world actions

Gamerules and quick actions are validated against fixed allowlists and sent to the running Bedrock process through its console connection. They do not require a container restart.

The **Day** and **Night** buttons only set the current world time. They do not enable or disable the daylight cycle; use the corresponding gamerule for that behavior.

## State refresh and online players

The manager keeps a small SQLite cache at:

```text
./data/manager.db
```

The cache stores the last observed settings, gamerules, player names, player count, and refresh timestamp. It is populated on startup and updated when the **Refresh** button is pressed.

Online players are derived from the Bedrock console response when available, with a connection/disconnection log parser as a fallback. As a result, player presence is a recently observed state rather than a guaranteed real-time session registry.

## Container operations

The **Server** menu provides these operations:

- **Start:** starts the `minecraft-bedrock` Compose service
- **Restart:** restarts the configured Bedrock container
- **Stop:** stops the configured Bedrock container
- **Apply:** recreates the Bedrock service after persistent configuration changes

Equivalent commands for the manager itself are:

```bash
cd /mnt/storage/docker/minecraft-bedrock-manager
docker compose restart
docker compose stop
docker compose up -d
```

## Updating

If the deployment directory is a Git checkout:

```bash
cd /mnt/storage/docker/minecraft-bedrock-manager
git pull --ff-only
docker compose up -d --build
```

If development and deployment use separate directories, copy the updated source files into the deployment directory and rebuild the service. The current Compose file bind-mounts `app.py`, `wsgi.py`, `minecraft_manager/`, `static/`, and `templates/`, but rebuilding is still recommended when dependencies or the Dockerfile change.

## Data and backups

The manager does not store Minecraft world data. The Bedrock world's files remain in the separate Minecraft server project, normally under:

```text
/mnt/storage/docker/minecraft-bedrock/data/
```

Only the manager's disposable state cache lives in `./data/manager.db`. Backing up this database is optional because the service can reconstruct its state from the Bedrock project and server.

World backup and restore procedures must be performed against the Minecraft Bedrock project, not this manager repository.

## API overview

The browser uses a small JSON API:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/status` | Read the Bedrock container status |
| `GET` | `/api/schema` | Read the editable settings schema |
| `GET` | `/api/state` | Read cached settings, gamerules, and players |
| `POST` | `/api/refresh` | Start an asynchronous state refresh |
| `PUT` | `/api/config` | Validate and save persistent settings |
| `PUT` | `/api/gamerules/<rule>` | Change an allowlisted gamerule |
| `POST` | `/api/world/<action>` | Run an allowlisted world shortcut |
| `POST` | `/api/server/<action>` | Start, stop, restart, or apply the server |

This API is an internal implementation interface and may change before a stable release.

## Security model

The manager mounts `/var/run/docker.sock` to inspect and operate the Bedrock container. Access to the Docker socket is effectively administrative access to the Docker host, even though this application restricts its own API to fixed operations.

Current safeguards include:

- No generic console or shell endpoint
- Fixed allowlists for server operations, gamerules, and world commands
- Input type, range, length, and character validation
- Atomic writes to the Bedrock `.env` file
- `no-new-privileges` enabled for the manager container

Current limitations include:

- No built-in authentication or authorization
- No CSRF protection
- No TLS termination
- Direct Docker socket access

Keep port `8082` restricted to a trusted LAN. Before any Internet-facing deployment, place the service behind an authenticated reverse proxy such as Authelia and add CSRF protection. A restricted Docker socket proxy or dedicated operations gateway is also recommended.

## Troubleshooting

### The interface loads but server actions fail

Verify the container name and project mount:

```bash
docker inspect minecraft-bedrock
docker compose exec minecraft-bedrock-manager ls -la /minecraft-project
```

### Current gamerules are not displayed

The Bedrock container must be running and accepting console input. Press **Refresh**, wait a few seconds, and inspect the manager logs:

```bash
docker compose logs --tail=200 minecraft-bedrock-manager
```

### Online players are missing or stale

Press **Refresh** while players are connected. The manager queries the console and scans recent connection logs, so a newly recreated Bedrock container may have limited history.

### Changes are saved but not active

Persistent settings require the Bedrock container to be recreated. Use **Save changes** in the interface or recreate the server from its Compose project.

## Development

The application uses:

- Python 3.12
- Flask
- Gunicorn
- Docker SDK for Python
- SQLite
- Vanilla HTML, CSS, and JavaScript

Run syntax checks before committing changes:

```bash
python -m unittest discover -s tests -v
python -m compileall -q minecraft_manager app.py wsgi.py
node --check static/app.js
docker compose config --quiet
```

## Roadmap

- Authelia integration and trusted-proxy configuration
- CSRF protection
- Restricted Docker socket proxy or minimal operations gateway
- Improved player-session tracking
- Allowlist and operator management
- Backup and restore controls for the Bedrock world
- Audit log for configuration and lifecycle changes
- Prometheus metrics and Grafana dashboard links
- Automated tests and release images

## License and trademarks

No license has been declared for this repository yet. All rights remain with the repository owner unless a license is added.

This is an independent homelab project and is not affiliated with Mojang Studios or Microsoft. Minecraft is a trademark of Microsoft Corporation.
