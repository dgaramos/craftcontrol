import { STORAGE_VERSION } from "./versions.js";

const NUMBER_FIELDS = [
  "joins", "deaths", "playerKills", "mobKills", "blocksBroken", "blocksPlaced",
  "damageDealt", "damageTaken", "distance",
];
const MAP_FIELDS = [
  "dimensions", "brokenByType", "placedByType", "killsByType", "distanceByDimension",
  "activeTimeByDimension", "firstDimensionVisitAt", "lastDimensionVisitAt",
];

function record(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function normalizePlayer(value, key) {
  if (!record(value)) throw new Error(`invalid player record: ${key}`);
  const name = typeof value.name === "string" && value.name.trim() ? value.name : key;
  const player = { ...value, name };
  player.aliases = Array.isArray(value.aliases) ? [...new Set(value.aliases.filter((item) => typeof item === "string" && item))] : [name];
  if (!player.aliases.includes(name)) player.aliases.push(name);
  player.firstSeenAt = Number.isFinite(value.firstSeenAt) ? value.firstSeenAt : 0;
  player.lastSeenAt = Number.isFinite(value.lastSeenAt) ? value.lastSeenAt : player.firstSeenAt;
  for (const field of NUMBER_FIELDS) player[field] = Number.isFinite(value[field]) && value[field] >= 0 ? value[field] : 0;
  for (const field of MAP_FIELDS) player[field] = record(value[field]) ? { ...value[field] } : {};
  return player;
}

export function validateState(value) {
  if (!record(value)) throw new Error("persisted state must be an object");
  if (value.storageVersion !== STORAGE_VERSION) throw new Error(`unsupported storage version: ${value.storageVersion}`);
  if (!Number.isInteger(value.sequence) || value.sequence < 0) throw new Error("invalid persisted sequence");
  if (!record(value.players)) throw new Error("invalid persisted players map");
  const players = Object.fromEntries(Object.entries(value.players).map(([key, player]) => [key, normalizePlayer(player, key)]));
  return { storageVersion: STORAGE_VERSION, sequence: value.sequence, players };
}

export function validateMeta(value) {
  if (!record(value) || value.storageVersion !== STORAGE_VERSION) throw new Error(`unsupported storage version: ${value?.storageVersion}`);
  if (!Number.isInteger(value.sequence) || value.sequence < 0) throw new Error("invalid persisted sequence");
  if (value.players !== undefined) throw new Error("storage v2 metadata must not contain players");
  return { storageVersion: STORAGE_VERSION, sequence: value.sequence };
}

export function validatePlayerShard(value) {
  if (!record(value) || value.storageVersion !== STORAGE_VERSION) throw new Error(`unsupported player shard version: ${value?.storageVersion}`);
  if (typeof value.key !== "string" || !value.key) throw new Error("invalid player shard key");
  if (!Number.isInteger(value.sequence) || value.sequence < 0) throw new Error("invalid player shard sequence");
  return { storageVersion: STORAGE_VERSION, sequence: value.sequence, key: value.key, player: normalizePlayer(value.player, value.key) };
}

export function migrateShardedV2(meta, shards) {
  if (!record(meta) || meta.storageVersion !== 2 || !Number.isInteger(meta.sequence) || meta.sequence < 0) {
    throw new Error("invalid storage v2 metadata");
  }
  const players = {};
  let sequence = meta.sequence;
  for (const [id, raw] of shards) {
    const shard = JSON.parse(raw);
    if (!record(shard) || shard.storageVersion !== 2 || typeof shard.key !== "string" || !shard.key) {
      throw new Error(`invalid storage v2 player shard: ${id}`);
    }
    if (!Number.isInteger(shard.sequence) || shard.sequence < 0 || players[shard.key]) throw new Error(`invalid storage v2 player shard: ${id}`);
    players[shard.key] = normalizePlayer(shard.player, shard.key);
    sequence = Math.max(sequence, shard.sequence);
  }
  return { state: { storageVersion: STORAGE_VERSION, sequence, players }, migratedFrom: 2, backups: shards };
}

export function migrateState(value) {
  if (!record(value)) throw new Error("persisted state must be an object");
  if (value.storageVersion === 1) {
    const candidate = { storageVersion: STORAGE_VERSION, sequence: value.sequence, players: value.players };
    return { state: validateState(candidate), migratedFrom: 1 };
  }
  if (value.storageVersion !== undefined) throw new Error(`unsupported storage version: ${value.storageVersion}`);
  if (value.schema !== 1) throw new Error("unrecognized legacy persisted state");
  const candidate = { storageVersion: STORAGE_VERSION, sequence: value.sequence, players: value.players };
  return { state: validateState(candidate), migratedFrom: 0 };
}
