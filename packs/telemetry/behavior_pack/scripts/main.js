import { system, world } from "@minecraft/server";
import { ensurePlayer, horizontalDistance, incrementMap, observeDimension, round } from "./model.js";
import { flush, loadState, mutatePlayer, storageStatus } from "./store.js";
import { publish, publishBlockChanges, publishSnapshot, queueBlockChange } from "./transport.js";
import { capabilitySnapshot, readGameMode, startMovementSampling, subscribeScriptEvents, subscribeWorldEvent } from "./capabilities.js";

const positions = new Map();
const gameModes = new Map();

function playerName(entity) {
  return entity?.typeId === "minecraft:player" ? entity.name : null;
}

function update(name, callback) {
  return mutatePlayer(name, (state) => callback(ensurePlayer(state, name)));
}

subscribeWorldEvent("playerJoin", "playerJoins", (event) => {
  update(event.playerName, (stats) => { stats.joins += 1; });
  publish("player.joined", event.playerName);
});

subscribeWorldEvent("playerLeave", "playerLeaves", (event) => {
  positions.delete(event.playerId);
  gameModes.delete(event.playerId);
  update(event.playerName, () => {});
  publish("player.left", event.playerName);
});

subscribeWorldEvent("playerSpawn", "playerRespawns", (event) => {
  const player = event.player;
  update(player.name, (stats) => observeDimension(stats, player.dimension.id, Date.now()));
  positions.set(player.id, { ...player.location, dimension: player.dimension.id });
  if (!event.initialSpawn) publish("player.respawned", player.name);
});

subscribeWorldEvent("entityDie", "deathsAndKills", (event) => {
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
});

subscribeWorldEvent("entityHurt", "damageAggregates", (event) => {
  const victim = playerName(event.hurtEntity);
  const attacker = playerName(event.damageSource.damagingEntity);
  if (victim) update(victim, (stats) => { stats.damageTaken = round(stats.damageTaken + event.damage); });
  if (attacker) update(attacker, (stats) => { stats.damageDealt = round(stats.damageDealt + event.damage); });
});

subscribeWorldEvent("playerBreakBlock", "blocksBroken", (event) => {
  const type = event.brokenBlockPermutation?.type?.id || "minecraft:unknown";
  update(event.player.name, (stats) => {
    stats.blocksBroken += 1;
    incrementMap(stats.brokenByType, type);
  });
  queueBlockChange(event.player.name, "broken", type);
});

subscribeWorldEvent("playerPlaceBlock", "blocksPlaced", (event) => {
  const type = event.block?.typeId || "minecraft:unknown";
  update(event.player.name, (stats) => {
    stats.blocksPlaced += 1;
    incrementMap(stats.placedByType, type);
  });
  queueBlockChange(event.player.name, "placed", type);
});

subscribeWorldEvent("playerDimensionChange", "dimensionChanges", (event) => {
  update(event.player.name, (stats) => observeDimension(stats, event.toDimension.id, Date.now(), true));
  positions.set(event.player.id, { ...event.toLocation, dimension: event.toDimension.id });
  publish("player.dimension.changed", event.player.name, { from: event.fromDimension.id, to: event.toDimension.id });
});

subscribeScriptEvents((event) => {
  if (event.id === "bedrock_telemetry:sync") system.run(publishSnapshot);
});

startMovementSampling(() => {
  for (const player of world.getAllPlayers()) {
    const previous = positions.get(player.id);
    const current = { ...player.location, dimension: player.dimension.id };
    positions.set(player.id, current);
    if (!previous || previous.dimension !== current.dimension) continue;
    const distance = horizontalDistance(previous, current);
    if (distance <= 0 || distance > 128) continue;
    update(player.name, (stats) => {
      stats.distance = round(stats.distance + distance);
      incrementMap(stats.distanceByDimension, current.dimension, distance, 8);
      stats.distanceByDimension[current.dimension] = round(stats.distanceByDimension[current.dimension]);
      incrementMap(stats.activeTimeByDimension, current.dimension, 5, 8);
      observeDimension(stats, current.dimension, Date.now());
    });
  }
  for (const player of world.getAllPlayers()) {
    const current = readGameMode(player);
    if (current !== null) {
      const previous = gameModes.get(player.id);
      if (previous !== undefined && previous !== current) {
        publish("player.gamemode.changed", player.name, { previous, current });
      }
      gameModes.set(player.id, current);
    }
  }
  publishBlockChanges();
  flush();
}, 100);

system.runTimeout(() => {
  loadState();
  publish("telemetry.started", null, { version: "0.3.2", product: "CraftControl Telemetry Pack", storage: storageStatus(), capabilities: capabilitySnapshot() });
  publishSnapshot();
}, 1);
