import { system, world } from "@minecraft/server";
import { MAX_METRIC_TYPES, ensurePlayer, incrementMap, observeDimension, round } from "./model.js";
import { metricKey } from "./domain/metrics.js";
import { applyMetrics, flush, loadState, metricEnabled, metricsSnapshot, mutatePlayer, storageStatus } from "./adapters/store.js";
import { publish, publishBlockChanges, publishItemUse, publishMetrics, publishSnapshot, queueBlockChange, queueItemUse } from "./adapters/transport.js";
import { capabilitySnapshot, probeGameModeReading, readGameMode, startMovementSampling, subscribeScriptEvents } from "./adapters/capabilities.js";
import { samplePlayerMovement } from "./domain/movement.js";
import { trackGameModes, removePlayer } from "./domain/gamemode.js";
import { registerEvents } from "./domain/events.js";

const productionDependencies = { system, world, ensurePlayer, incrementMap, observeDimension, round, applyMetrics, flush, loadState, metricEnabled, metricKey, metricsSnapshot, mutatePlayer, storageStatus, publish, publishBlockChanges, publishItemUse, publishMetrics, publishSnapshot, queueBlockChange, queueItemUse, capabilitySnapshot, probeGameModeReading, readGameMode, startMovementSampling, subscribeScriptEvents, samplePlayerMovement, trackGameModes, removePlayer, registerEvents };

function playerName(entity) {
  return entity?.typeId === "minecraft:player" ? entity.name : null;
}

export function startTelemetryRuntime(overrides = {}) {
  const { system, world, ensurePlayer, incrementMap, observeDimension, round, applyMetrics, flush, loadState, metricEnabled, metricKey, metricsSnapshot, mutatePlayer, storageStatus, publish, publishBlockChanges, publishItemUse, publishMetrics, publishSnapshot, queueBlockChange, queueItemUse, capabilitySnapshot, probeGameModeReading, readGameMode, startMovementSampling, subscribeScriptEvents, samplePlayerMovement, trackGameModes, removePlayer, registerEvents } = { ...productionDependencies, ...overrides };
  const positions = new Map();
  const gameModes = new Map();

  function update(name, callback) {
    return mutatePlayer(name, (state) => callback(ensurePlayer(state, name)));
  }

registerEvents({
  onPlayerJoin(event) {
    update(event.playerName, (stats) => { stats.joins += 1; });
    publish("player.joined", event.playerName);
  },

  onPlayerLeave(event) {
    positions.delete(event.playerId);
    removePlayer(gameModes, event.playerId);
    update(event.playerName, () => {});
    publish("player.left", event.playerName);
  },

  onPlayerSpawn(event) {
    const player = event.player;
    update(player.name, (stats) => observeDimension(stats, player.dimension.id, Date.now()));
    positions.set(player.id, { ...player.location, dimension: player.dimension.id });
    if (!event.initialSpawn) publish("player.respawned", player.name);
  },

  onEntityDie(event) {
    const victim = playerName(event.deadEntity);
    const killer = playerName(event.damageSource.damagingEntity);
    const cause = String(event.damageSource.cause);
    if (victim) update(victim, (stats) => { stats.deaths += 1; });
    if (killer) update(killer, (stats) => {
      if (victim) stats.playerKills += 1;
      else {
        stats.mobKills += 1;
        incrementMap(stats.killsByType, event.deadEntity.typeId);
      }
    });
    if (victim || killer) publish("entity.died", victim, {
      victim: victim || null,
      victimType: event.deadEntity.typeId,
      killer: killer || null,
      killerType: event.damageSource.damagingEntity?.typeId || null,
      projectileType: event.damageSource.damagingProjectile?.typeId || null,
      cause,
    });
  },

  onEntityHurt(event) {
    const victim = playerName(event.hurtEntity);
    const attacker = playerName(event.damageSource.damagingEntity);
    if (victim) update(victim, (stats) => { stats.damageTaken = round(stats.damageTaken + event.damage); });
    if (attacker) update(attacker, (stats) => { stats.damageDealt = round(stats.damageDealt + event.damage); });
  },

  onPlayerBreakBlock(event) {
    const type = event.brokenBlockPermutation?.type?.id || "minecraft:unknown";
    update(event.player.name, (stats) => {
      stats.blocksBroken += 1;
      incrementMap(stats.brokenByType, type);
    });
    queueBlockChange(event.player.name, "broken", type);
  },

  onPlayerPlaceBlock(event) {
    const type = event.block?.typeId || "minecraft:unknown";
    update(event.player.name, (stats) => {
      stats.blocksPlaced += 1;
      incrementMap(stats.placedByType, type);
    });
    queueBlockChange(event.player.name, "placed", type);
  },

  onPlayerUseItem(event) {
    // Opt-in: a pack that was never told to collect item use collects none of
    // it, and an identifier that is not a namespaced id is discarded rather
    // than stored (docs/telemetry-metrics.md).
    if (!metricEnabled("itemUse")) return;
    const type = metricKey(event.itemStack?.typeId);
    const name = event.source?.name;
    if (!type || !name) return;
    update(name, (stats) => {
      stats.itemsUsed += 1;
      incrementMap(stats.usedByType, type, 1, MAX_METRIC_TYPES);
    });
    queueItemUse(name, type);
  },

  onPlayerDimensionChange(event) {
    update(event.player.name, (stats) => observeDimension(stats, event.toDimension.id, Date.now(), true));
    positions.set(event.player.id, { ...event.toLocation, dimension: event.toDimension.id });
    publish("player.dimension.changed", event.player.name, { from: event.fromDimension.id, to: event.toDimension.id });
  },
});

subscribeScriptEvents((event) => {
  if (event.id === "bedrock_telemetry:sync") system.run(publishSnapshot);
  else if (event.id === "bedrock_telemetry:metrics") system.run(() => {
    const metrics = applyMetrics(event.message);
    if (metrics) publishMetrics(metrics);
  });
});

startMovementSampling(() => {
  const livePlayers = world.getAllPlayers();
  for (const player of livePlayers) {
    samplePlayerMovement(positions, player, (dim, distance) => {
      update(player.name, (stats) => {
        stats.distance = round(stats.distance + distance);
        incrementMap(stats.distanceByDimension, dim, distance, 8);
        stats.distanceByDimension[dim] = round(stats.distanceByDimension[dim]);
        incrementMap(stats.activeTimeByDimension, dim, 5, 8);
        observeDimension(stats, dim, Date.now());
      });
    });
  }
  probeGameModeReading(livePlayers);
  trackGameModes(gameModes, livePlayers, readGameMode, publish);
  publishBlockChanges();
  publishItemUse();
  flush();
}, 100);

system.runTimeout(() => {
  loadState();
  probeGameModeReading(world.getAllPlayers());
  publish("telemetry.started", null, { version: "0.5.0", product: "CraftControl Telemetry Pack", storage: storageStatus(), capabilities: capabilitySnapshot(), metrics: metricsSnapshot() });
  publishSnapshot();
}, 1);
}

startTelemetryRuntime();
