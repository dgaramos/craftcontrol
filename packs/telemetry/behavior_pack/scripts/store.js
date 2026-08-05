import { world } from "@minecraft/server";
import { PLAYER_BACKUP_V2_PREFIX, PLAYER_STATE_PREFIX, STATE_BACKUP_KEY, STATE_BACKUP_V1_KEY, STATE_BACKUP_V2_KEY, STATE_KEY, emptyState, playerKey, playerStateKey } from "./model.js";
import { migrateShardedV2, migrateState, validateMeta, validatePlayerShard } from "./migrations.js";
import { STORAGE_VERSION } from "./versions.js";

let state;
let metaDirty = false;
const dirtyPlayers = new Set();
let blocked = false;
let migration = { status: "not-required", storageVersion: STORAGE_VERSION, migratedFrom: null };

function serialize(candidate) {
  const value = JSON.stringify(candidate);
  if (value.length > 30000) throw new Error(`state is ${value.length} bytes; refusing unsafe write`);
  return value;
}

function loadShardedState(meta) {
  const validated = validateMeta(meta);
  if (typeof world.getDynamicPropertyIds !== "function") throw new Error("dynamic property discovery is unavailable");
  const players = {};
  let sequence = validated.sequence;
  for (const id of world.getDynamicPropertyIds().filter((item) => item.startsWith(PLAYER_STATE_PREFIX))) {
    const raw = world.getDynamicProperty(id);
    if (typeof raw !== "string") continue;
    const shard = validatePlayerShard(JSON.parse(raw));
    if (players[shard.key]) throw new Error(`duplicate player shard: ${shard.key}`);
    players[shard.key] = shard.player;
    sequence = Math.max(sequence, shard.sequence);
  }
  if (sequence !== validated.sequence) metaDirty = true;
  return { storageVersion: STORAGE_VERSION, sequence, players };
}

function persistMigration(raw, result) {
  const shards = Object.entries(result.state.players).map(([key, player]) => [
    playerStateKey(key),
    serialize({ storageVersion: STORAGE_VERSION, sequence: result.state.sequence, key, player }),
  ]);
  const meta = serialize({ storageVersion: STORAGE_VERSION, sequence: result.state.sequence });
  const backupKey = result.migratedFrom === 0 ? STATE_BACKUP_KEY : result.migratedFrom === 1 ? STATE_BACKUP_V1_KEY : STATE_BACKUP_V2_KEY;
  if (typeof world.getDynamicProperty(backupKey) !== "string") world.setDynamicProperty(backupKey, raw);
  for (const [id, value] of result.backups || []) {
    const backupId = `${PLAYER_BACKUP_V2_PREFIX}${id.slice(PLAYER_STATE_PREFIX.length)}`;
    if (typeof world.getDynamicProperty(backupId) !== "string") world.setDynamicProperty(backupId, value);
  }
  for (const [id, value] of shards) {
    world.setDynamicProperty(id, value);
    if (world.getDynamicProperty(id) !== value) throw new Error(`failed to verify player shard: ${id}`);
  }
  world.setDynamicProperty(STATE_KEY, meta);
  if (world.getDynamicProperty(STATE_KEY) !== meta) throw new Error("failed to verify storage metadata");
}

export function loadState() {
  if (state) return state;
  const raw = world.getDynamicProperty(STATE_KEY);
  if (typeof raw !== "string") return (state = emptyState());
  try {
    const parsed = JSON.parse(raw);
    if (parsed?.storageVersion === STORAGE_VERSION) {
      state = loadShardedState(parsed);
    } else if (parsed?.storageVersion === 2) {
      if (typeof world.getDynamicPropertyIds !== "function") throw new Error("dynamic property discovery is unavailable");
      const shards = world.getDynamicPropertyIds().filter((item) => item.startsWith(PLAYER_STATE_PREFIX)).map((id) => [id, world.getDynamicProperty(id)]).filter(([, value]) => typeof value === "string");
      const result = migrateShardedV2(parsed, shards);
      state = result.state;
      persistMigration(raw, result);
      migration = { status: "migrated", storageVersion: STORAGE_VERSION, migratedFrom: 2 };
      console.warn(`[BEDROCK_TELEMETRY_MIGRATION] storage 2 -> ${STORAGE_VERSION} complete`);
    } else {
      const result = migrateState(parsed);
      state = result.state;
      persistMigration(raw, result);
      migration = { status: "migrated", storageVersion: STORAGE_VERSION, migratedFrom: result.migratedFrom };
      console.warn(`[BEDROCK_TELEMETRY_MIGRATION] storage ${result.migratedFrom} -> ${STORAGE_VERSION} complete`);
    }
  } catch (error) {
    console.error(`[BEDROCK_TELEMETRY_ERROR] invalid persisted state: ${error}`);
    blocked = true;
    migration = { status: "blocked", storageVersion: STORAGE_VERSION, migratedFrom: null, error: String(error) };
    state = emptyState();
  }
  return state;
}

export function storageStatus() {
  loadState();
  return { ...migration, persistenceBlocked: blocked };
}

export function mutate(callback) {
  const result = callback(loadState());
  metaDirty = true;
  return result;
}

export function mutatePlayer(name, callback) {
  const current = loadState();
  const key = playerKey(name);
  const result = callback(current);
  dirtyPlayers.add(key);
  metaDirty = true;
  return result;
}

export function nextSequence() {
  return mutate((current) => ++current.sequence);
}

export function flush(force = false) {
  if (!metaDirty && dirtyPlayers.size === 0 && !force) return;
  if (blocked) {
    console.error("[BEDROCK_TELEMETRY_ERROR] persistence blocked; preserving original state");
    return;
  }
  try {
    const current = loadState();
    for (const key of dirtyPlayers) {
      const player = current.players[key];
      if (!player) continue;
      world.setDynamicProperty(playerStateKey(key), serialize({ storageVersion: STORAGE_VERSION, sequence: current.sequence, key, player }));
    }
    world.setDynamicProperty(STATE_KEY, serialize({ storageVersion: STORAGE_VERSION, sequence: current.sequence }));
    dirtyPlayers.clear();
    metaDirty = false;
  } catch (error) {
    console.error(`[BEDROCK_TELEMETRY_ERROR] ${error}`);
  }
}
