import assert from "node:assert/strict";
import { world, system } from "@minecraft/server";
import { captureConsole } from "./console-capture.mjs";

const capture = captureConsole("warn");
const { lines: output } = capture;

await import("../../behavior_pack/scripts/main.js");

world.afterEvents.playerJoin.emit({ playerName: "VonCrush" });
const player = { id: "player-1", name: "VonCrush", typeId: "minecraft:player", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });
world.afterEvents.entityDie.emit({
  deadEntity: { typeId: "minecraft:zombie" },
  damageSource: { damagingEntity: player, damagingProjectile: null, cause: "entityAttack" },
});
world.afterEvents.playerBreakBlock.emit({
  player: { name: "VonCrush" },
  brokenBlockPermutation: { type: { id: "minecraft:stone" } },
});
world.players = [{ ...player, location: { x: 3, y: 64, z: 4 } }];
for (const interval of system.intervals) interval();
world.afterEvents.playerLeave.emit({ playerId: "player-1", playerName: "VonCrush" });
system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

const envelopes = output
  .filter((line) => line.includes("[BEDROCK_TELEMETRY]"))
  .map((line) => JSON.parse(line.slice(line.indexOf("{") )));
const blockEvent = envelopes.find((item) => item.type === "blocks.changed");
const snapshot = envelopes.findLast((item) => item.type === "snapshot.player" && item.player?.name === "VonCrush");

const blockIndex = envelopes.indexOf(blockEvent);
const snapshotStartedIndex = envelopes.findIndex((item, index) => index > blockIndex && item.type === "snapshot.started");
const snapshotPlayerIndex = envelopes.findIndex((item, index) => index > snapshotStartedIndex && item.type === "snapshot.player");
const snapshotFinishedIndex = envelopes.findIndex((item, index) => index > snapshotPlayerIndex && item.type === "snapshot.finished");
assert.ok(blockIndex < snapshotStartedIndex);
assert.ok(snapshotStartedIndex < snapshotPlayerIndex);
assert.ok(snapshotPlayerIndex < snapshotFinishedIndex);

for (const [previous, current] of envelopes.slice(1).map((item, index) => [envelopes[index], item])) {
  assert.ok(current.sequence >= previous.sequence, "telemetry sequences must not decrease");
}

const emitted = JSON.stringify(envelopes).toLowerCase();
for (const forbiddenField of ["xuid", "location", "inventory", "chat"]) {
  assert.equal(emitted.includes(forbiddenField), false, `telemetry must not emit ${forbiddenField}`);
}

assert.equal(blockEvent?.data.broken.total, 1);
assert.equal(blockEvent?.data.broken.byType["minecraft:stone"], 1);
assert.equal(snapshot?.data.joins, 1);
assert.equal(snapshot?.data.blocksBroken, 1);
assert.equal(snapshot?.data.brokenByType["minecraft:stone"], 1);
assert.equal(snapshot?.data.killsByType["minecraft:zombie"], 1);
assert.equal(snapshot?.data.distanceByDimension["minecraft:overworld"], 5);
assert.equal(snapshot?.data.activeTimeByDimension["minecraft:overworld"], 5);
assert.ok(snapshot?.data.firstDimensionVisitAt["minecraft:overworld"] > 0);
capture.restore();
