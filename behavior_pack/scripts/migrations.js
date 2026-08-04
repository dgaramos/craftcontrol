import { STORAGE_VERSION } from "./versions.js";

const NUMBER_FIELDS = [
  "joins", "deaths", "playerKills", "mobKills", "blocksBroken", "blocksPlaced",
  "damageDealt", "damageTaken", "distance",
];
const MAP_FIELDS = ["dimensions", "brokenByType", "placedByType"];

function record(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function normalizePlayer(value, key) {
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

export function migrateState(value) {
  if (!record(value)) throw new Error("persisted state must be an object");
  if (value.storageVersion === STORAGE_VERSION) return { state: validateState(value), migratedFrom: null };
  if (value.storageVersion !== undefined) throw new Error(`unsupported storage version: ${value.storageVersion}`);
  if (value.schema !== 1) throw new Error("unrecognized legacy persisted state");
  const candidate = { storageVersion: STORAGE_VERSION, sequence: value.sequence, players: value.players };
  return { state: validateState(candidate), migratedFrom: 0 };
}
