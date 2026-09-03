import { STORAGE_VERSION } from "../behavior_pack/scripts/versions.js";

export function storageMetadata(overrides = {}) {
  return { storageVersion: STORAGE_VERSION, sequence: 0, ...overrides };
}

export function playerSnapshot(overrides = {}) {
  const { aliases, ...player } = overrides;
  const name = player.name ?? "VonCrush";
  return {
    name, aliases: aliases ?? [name], firstSeenAt: 0, lastSeenAt: 0,
    joins: 0, deaths: 0, playerKills: 0, mobKills: 0, blocksBroken: 0,
    blocksPlaced: 0, damageDealt: 0, damageTaken: 0, distance: 0,
    dimensions: {}, brokenByType: {}, placedByType: {}, killsByType: {},
    distanceByDimension: {}, activeTimeByDimension: {}, firstDimensionVisitAt: {},
    lastDimensionVisitAt: {}, ...player,
  };
}

export function playerShard(overrides = {}) {
  const { player, ...shard } = overrides;
  const key = shard.key ?? "voncrush";
  return {
    storageVersion: STORAGE_VERSION, sequence: 0, key,
    player: playerSnapshot({ name: "VonCrush", ...player }), ...shard,
  };
}

export function telemetryEnvelope(overrides = {}) {
  const { player, data, ...envelope } = overrides;
  return {
    schema: 1, sequence: 1, type: "telemetry.started", timestamp: 0,
    player: player === undefined ? null : player, data: data ?? {}, ...envelope,
  };
}

export function telemetryLogRecord(overrides = {}) {
  return `[BEDROCK_TELEMETRY] ${JSON.stringify(telemetryEnvelope(overrides))}`;
}

export function capturedTelemetryRecords(consoleSpy) {
  return consoleSpy.mock.calls
    .map(([line]) => String(line))
    .filter((line) => line.startsWith("[BEDROCK_TELEMETRY] "))
    .map((line) => JSON.parse(line.slice("[BEDROCK_TELEMETRY] ".length)));
}
