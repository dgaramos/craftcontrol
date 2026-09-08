import assert from "node:assert/strict";
import { world, system } from "@minecraft/server";
import { captureConsole } from "./console-capture.mjs";

const capture = captureConsole("warn");
const { lines: output } = capture;

const envelopes = () => output
  .filter((line) => line.includes("[BEDROCK_TELEMETRY]"))
  .map((line) => JSON.parse(line.slice(line.indexOf("{"))));

const player = { id: "player-1", name: "VonCrush", typeId: "minecraft:player", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
const use = (typeId) => world.afterEvents.itemUse.emit({ source: player, itemStack: { typeId } });

await import("../../behavior_pack/scripts/main.js");

world.afterEvents.playerJoin.emit({ playerName: "VonCrush" });
world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });

// A pack that was never told to collect item use collects none of it.
use("minecraft:bow");
use("minecraft:bow");
for (const interval of system.intervals) interval();
assert.equal(envelopes().some((item) => item.type === "items.used"), false, "item use was collected before the owner opted in");

system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:metrics", message: "enable itemUse" });
const announced = envelopes().findLast((item) => item.type === "metrics.changed");
assert.deepEqual(announced?.data.metrics, { itemUse: true }, "enabling a metric must be announced");

use("minecraft:bow");
use("minecraft:bow");
use("minecraft:splash_potion");
use("Excalibur");                 // a custom name is not an identifier
for (const interval of system.intervals) interval();

const batch = envelopes().findLast((item) => item.type === "items.used");
assert.equal(batch?.player?.name, "VonCrush");
assert.equal(batch?.data.total, 3, "only namespaced identifiers are counted");
assert.deepEqual(batch?.data.byType, { "minecraft:bow": 2, "minecraft:splash_potion": 1 });

system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });
const snapshot = envelopes().findLast((item) => item.type === "snapshot.player" && item.player?.name === "VonCrush");
assert.equal(snapshot?.data.itemsUsed, 3, "the snapshot must reconcile the counter");
assert.deepEqual(snapshot?.data.usedByType, { "minecraft:bow": 2, "minecraft:splash_potion": 1 });

const started = envelopes().findLast((item) => item.type === "snapshot.started");
assert.deepEqual(started?.data.metrics, { itemUse: true }, "a snapshot must report which metrics are enabled");

// Turning it off stops collection without disturbing what was already counted.
system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:metrics", message: "disable itemUse" });
use("minecraft:bow");
for (const interval of system.intervals) interval();
system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });
const afterDisable = envelopes().findLast((item) => item.type === "snapshot.player" && item.player?.name === "VonCrush");
assert.equal(afterDisable?.data.itemsUsed, 3, "a disabled metric must not keep counting");

const emitted = JSON.stringify(envelopes()).toLowerCase();
for (const forbidden of ["xuid", "inventory", "slot", "enchant", "excalibur"]) {
  assert.equal(emitted.includes(forbidden), false, `item-use telemetry must not emit ${forbidden}`);
}

capture.restore();
