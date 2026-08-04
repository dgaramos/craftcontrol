import { system, world } from "@minecraft/server";
import { ensurePlayer, horizontalDistance, incrementMap, round } from "./model.js";
import { flush, loadState, mutatePlayer, storageStatus } from "./store.js";
import { publish, publishSnapshot } from "./transport.js";

const positions = new Map();

function playerName(entity) {
  return entity?.typeId === "minecraft:player" ? entity.name : null;
}

function update(name, callback) {
  return mutatePlayer(name, (state) => callback(ensurePlayer(state, name)));
}

world.afterEvents.playerJoin.subscribe((event) => {
  update(event.playerName, (stats) => { stats.joins += 1; });
  publish("player.joined", event.playerName);
});

world.afterEvents.playerLeave.subscribe((event) => {
  positions.delete(event.playerId);
  update(event.playerName, () => {});
  publish("player.left", event.playerName);
});

world.afterEvents.playerSpawn.subscribe((event) => {
  const player = event.player;
  update(player.name, () => {});
  positions.set(player.id, { ...player.location, dimension: player.dimension.id });
  if (!event.initialSpawn) publish("player.respawned", player.name);
});

world.afterEvents.entityDie.subscribe((event) => {
  const victim = playerName(event.deadEntity);
  const killer = playerName(event.damageSource.damagingEntity);
  const cause = String(event.damageSource.cause);
  if (victim) update(victim, (stats) => { stats.deaths += 1; });
  if (killer) update(killer, (stats) => {
    if (victim) stats.playerKills += 1;
    else stats.mobKills += 1;
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

world.afterEvents.entityHurt.subscribe((event) => {
  const victim = playerName(event.hurtEntity);
  const attacker = playerName(event.damageSource.damagingEntity);
  if (victim) update(victim, (stats) => { stats.damageTaken = round(stats.damageTaken + event.damage); });
  if (attacker) update(attacker, (stats) => { stats.damageDealt = round(stats.damageDealt + event.damage); });
});

world.afterEvents.playerBreakBlock.subscribe((event) => {
  const type = event.brokenBlockPermutation?.type?.id || "minecraft:unknown";
  update(event.player.name, (stats) => {
    stats.blocksBroken += 1;
    incrementMap(stats.brokenByType, type);
  });
  publish("block.broken", event.player.name, { blockType: type });
});

world.afterEvents.playerPlaceBlock.subscribe((event) => {
  const type = event.block?.typeId || "minecraft:unknown";
  update(event.player.name, (stats) => {
    stats.blocksPlaced += 1;
    incrementMap(stats.placedByType, type);
  });
  publish("block.placed", event.player.name, { blockType: type });
});

world.afterEvents.playerDimensionChange.subscribe((event) => {
  update(event.player.name, (stats) => incrementMap(stats.dimensions, event.toDimension.id, 1, 8));
  positions.set(event.player.id, { ...event.toLocation, dimension: event.toDimension.id });
  publish("player.dimension.changed", event.player.name, { from: event.fromDimension.id, to: event.toDimension.id });
});

system.afterEvents.scriptEventReceive.subscribe((event) => {
  if (event.id === "bedrock_telemetry:sync") system.run(publishSnapshot);
});

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    const previous = positions.get(player.id);
    const current = { ...player.location, dimension: player.dimension.id };
    positions.set(player.id, current);
    if (!previous || previous.dimension !== current.dimension) continue;
    const distance = horizontalDistance(previous, current);
    if (distance <= 0 || distance > 128) continue;
    update(player.name, (stats) => { stats.distance = round(stats.distance + distance); });
  }
  flush();
}, 100);

system.runTimeout(() => {
  loadState();
  publish("telemetry.started", null, { version: "0.2.2", product: "CraftControl Telemetry Pack", storage: storageStatus() });
  publishSnapshot();
}, 1);
