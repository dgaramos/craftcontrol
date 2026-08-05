import { PROTOCOL_SCHEMA_VERSION, STORAGE_VERSION } from "./versions.js";

export const SCHEMA_VERSION = PROTOCOL_SCHEMA_VERSION;
export const STATE_KEY = "bedrock_telemetry:state";
export const STATE_BACKUP_KEY = "bedrock_telemetry:state_backup_v0";
export const STATE_BACKUP_V1_KEY = "bedrock_telemetry:state_backup_v1";
export const STATE_BACKUP_V2_KEY = "bedrock_telemetry:state_backup_v2";
export const PLAYER_STATE_PREFIX = "bedrock_telemetry:player:";
export const PLAYER_BACKUP_V2_PREFIX = "bedrock_telemetry:backup_v2_player:";
export const LOG_PREFIX = "[BEDROCK_TELEMETRY]";
export const MAX_BLOCK_TYPES = 128;

export function emptyState() {
  return { storageVersion: STORAGE_VERSION, sequence: 0, players: {} };
}

export function playerKey(name) {
  return String(name).trim().toLocaleLowerCase();
}

export function playerStateKey(key) {
  return `${PLAYER_STATE_PREFIX}${encodeURIComponent(key)}`;
}

export function emptyPlayer(name, now) {
  return {
    name, aliases: [name], firstSeenAt: now, lastSeenAt: now,
    joins: 0, deaths: 0, playerKills: 0, mobKills: 0,
    blocksBroken: 0, blocksPlaced: 0, damageDealt: 0, damageTaken: 0,
    distance: 0, dimensions: {}, brokenByType: {}, placedByType: {},
    killsByType: {}, distanceByDimension: {}, activeTimeByDimension: {},
    firstDimensionVisitAt: {}, lastDimensionVisitAt: {},
  };
}

export function ensurePlayer(state, name, now = Date.now()) {
  const key = playerKey(name);
  const player = state.players[key] || emptyPlayer(name, now);
  player.name = name;
  player.lastSeenAt = now;
  if (!player.aliases.includes(name)) player.aliases.push(name);
  state.players[key] = player;
  return player;
}

export function incrementMap(map, key, amount = 1, limit = MAX_BLOCK_TYPES) {
  map[key] = (map[key] || 0) + amount;
  const entries = Object.entries(map);
  if (entries.length > limit) {
    entries.sort((a, b) => b[1] - a[1]);
    for (const [name] of entries.slice(limit)) delete map[name];
  }
}

export function observeDimension(stats, dimension, now, incrementVisit = false) {
  if (!dimension) return;
  if (incrementVisit || stats.dimensions[dimension] === undefined) incrementMap(stats.dimensions, dimension, 1, 8);
  if (!stats.firstDimensionVisitAt[dimension]) stats.firstDimensionVisitAt[dimension] = now;
  stats.lastDimensionVisitAt[dimension] = now;
}

export function horizontalDistance(from, to) {
  const x = to.x - from.x;
  const z = to.z - from.z;
  return Math.sqrt(x * x + z * z);
}

export function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}
