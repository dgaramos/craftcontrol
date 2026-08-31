# Bedrock Configuration: Single Source of Truth

This document describes how Minecraft Bedrock Dedicated Server configuration is structured, where each value is authoritative, and how CraftControl reads, presents, and reconciles configuration state.

---

## Authority matrix

| Setting | Authoritative source | Changed by | Persists across restarts |
|---|---|---|---|
| `gamemode`, `force-gamemode`, `difficulty`, `max-players`, and all other server properties | `server.properties` (file on disk) | CraftControl settings write-through | Yes |
| World-level gamerules (`gamerule` command) | World data (leveldb) | Bedrock console command | Yes |
| Per-session runtime overrides (e.g. `gamemode` command applied to a logged-in player) | Bedrock process memory | Bedrock console command | No — reset on player disconnect or server restart |
| Compose service environment | `.env` (Docker Compose) | Manual edit or `bin/deploy-craftcontrol` | Yes — affects next container start |

CraftControl never treats Bedrock process memory as canonical. `server.properties` is the authoritative source for server-level settings including `gamemode`. World-level gamerules are durable but control game rules, not the player `gamemode` default.

---

## Runtime changes do not write to server.properties

Bedrock accepts a `gamemode` command at the console while the server is running. This command changes the effective mode for the targeted player immediately in-process. It does not write the new value back to `server.properties`.

The consequence is a read asymmetry: if an operator issues `gamemode creative PlayerName` at the Bedrock console, the in-game mode for that player changes, but `server.properties` still records the original value. The next player to join inherits the `server.properties` default, not the console-issued override.

Note: `@s` is not a valid target selector from the server console because the console is not an entity. Use a player name or an explicit selector such as `@a` when targeting players from the console.

CraftControl does not issue console `gamemode` commands on behalf of any feature except the explicit "change gamemode" use case, which writes through to `server.properties` before signalling Bedrock.

---

## Player session override lifecycle

A runtime mode change applied to an individual player follows this lifecycle:

1. **Apply** — Bedrock applies the mode to the player's current session in memory.
2. **Active** — The player experiences the overridden mode while connected.
3. **Reset on disconnect** — When the player disconnects, Bedrock discards the per-session override. The next session for that player starts from the `server.properties` `gamemode` value (subject to `force-gamemode`, see below).
4. **Never persist** — The override is never written to `server.properties`, world data, or any CraftControl database table. CraftControl does not replay it when the player reconnects.

This lifecycle is a Bedrock property, not a CraftControl policy. CraftControl surfaces the authoritative value and labels observed deviations rather than attempting to synchronise them.

---

## Global boot gamemode vs per-player temporary gamemode

Bedrock has two distinct gamemode concepts that are frequently confused:

**Global boot gamemode (`server.properties`)**

The `gamemode` entry in `server.properties` sets the default mode assigned to every new player on their first join. Whether it also applies to returning players depends on the `force-gamemode` property:

- **`force-gamemode=false` (default):** Bedrock preserves each player's saved mode from their previous session or the world's original creation settings. Changes to `gamemode` in `server.properties` made after world creation may be ignored for existing players.
- **`force-gamemode=true`:** Bedrock overrides every player's mode with the value in `server.properties` on each join, regardless of their saved state. This guarantees that `server.properties` changes take effect for all future sessions.

This value is durable: it survives server restarts and applies to all future sessions (subject to `force-gamemode`) until the file is edited.

**Per-player temporary gamemode (console command)**

The `gamemode <mode> <player>` console command applies an immediate, session-scoped override to one player. It does not affect other players or the global default. It does not persist past the player's current session.

CraftControl's settings panel targets the global boot gamemode. It reads `server.properties`, presents the stored value, and writes changes back to `server.properties` before requesting a Bedrock restart. Whether the new value takes effect for existing players on their next join depends on the `force-gamemode` property.

CraftControl does not currently expose a per-player temporary override through its panel. Any per-player mode seen in Bedrock logs is treated as observed state, not as a configuration change to reconcile.

---

## CraftControl presentation and reconciliation

### What CraftControl shows

The settings panel always displays the value read from `server.properties`. This is the canonical configuration state that survives restarts and applies to future sessions.

When CraftControl reads telemetry or log events that report a value differing from `server.properties`, it labels that value as **observed** and does not promote it to canonical. The canonical panel value does not change as a result of an observed runtime deviation.

### Reconciliation on disconnect

A player disconnect triggers presence reconciliation and session closure. It does not trigger a configuration reconciliation. Specifically:

- The player's profile is updated to offline and the session is closed.
- The `gamemode` stored in `server.properties` is not re-read, re-written, or changed.
- Any per-session override that existed in Bedrock memory is discarded by Bedrock itself. CraftControl does not track or restore it.

This means disconnect never updates the canonical gamemode. The `server.properties` value before the disconnect is identical to the value after it.

### Observed state labelling

If telemetry or log data provides a player's current in-game mode and that mode differs from the `server.properties` default, CraftControl may display the observed mode alongside the canonical setting with a clear label distinguishing the two. The label indicates that the observed value is derived from runtime data and is not authoritative. It will not persist past the player's next disconnect or server restart.

---

## Related documents

- `docs/architecture.md` — dependency direction and event/consistency model
- `docs/operation-lifecycle.md` — how CraftControl operations interact with Bedrock runtime state
- `docs/backup-and-restore.md` — handling world data (which contains world-level gamerules)
