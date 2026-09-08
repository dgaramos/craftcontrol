import assert from "node:assert/strict";
import { world, system } from "@minecraft/server";
import { captureConsole } from "./console-capture.mjs";

const capture = captureConsole("warn");
const { lines: output } = capture;

const envelopes = () => output
  .filter((line) => line.includes("[BEDROCK_TELEMETRY]"))
  .map((line) => JSON.parse(line.slice(line.indexOf("{"))));

const player = { id: "player-1", name: "VonCrush", typeId: "minecraft:player", location: { x: 12, y: 64, z: -40 }, dimension: { id: "minecraft:overworld" } };
const chest = { typeId: "minecraft:chest", getComponent: (name) => (name === "minecraft:inventory" ? { container: {} } : null) };
const door = { typeId: "minecraft:oak_door", getComponent: () => null };

const touchBlock = (block) => world.afterEvents.playerInteractWithBlock.emit({ player, block, blockFace: "Up" });
const touchEntity = (typeId) => world.afterEvents.playerInteractWithEntity.emit({ player, target: { typeId } });
const command = (message) => system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:metrics", message });
const cycle = () => { for (const interval of system.intervals) interval(); };

await import("../../behavior_pack/scripts/main.js");

world.afterEvents.playerJoin.emit({ playerName: "VonCrush" });
world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });

// Nothing is collected before the owner opts in.
touchBlock(chest);
touchEntity("minecraft:villager");
cycle();
assert.equal(envelopes().some((item) => item.type === "interactions.changed"), false, "interactions were collected before the opt-in");

// The runtime is probed anyway, so the panel can tell unavailable from zero.
const capabilities = envelopes().findLast((item) => item.type === "snapshot.started")?.data.capabilities
  || envelopes().find((item) => item.type === "telemetry.started")?.data.capabilities;
assert.ok(capabilities.blockInteractions, "the block interaction capability must be reported");
assert.ok(capabilities.entityInteractions, "the entity interaction capability must be reported");

// Each metric is enabled on its own.
command("enable blockInteractions");
touchBlock(chest);
touchBlock(door);
touchEntity("minecraft:villager");
cycle();

const blocksOnly = envelopes().findLast((item) => item.type === "interactions.changed");
assert.equal(blocksOnly.data.block.total, 2);
assert.deepEqual(blocksOnly.data.block.byType, { "minecraft:chest": 1, "minecraft:oak_door": 1 });
assert.equal(blocksOnly.data.entity.total, 0, "entity interactions must stay off until they are enabled");
assert.equal(blocksOnly.data.container.total, 0, "container opens must stay off until they are enabled");

command("enable containerInteractions");
command("enable entityInteractions");
touchBlock(chest);
touchBlock(door);
touchEntity("minecraft:villager");
touchEntity("Fluffy");            // a custom name is not an identifier
cycle();

const all = envelopes().findLast((item) => item.type === "interactions.changed");
assert.equal(all.data.container.total, 1, "only the block holding an inventory is a container open");
assert.deepEqual(all.data.container.byType, { "minecraft:chest": 1 });
assert.equal(all.data.entity.total, 1, "a custom entity name must not be counted");

system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });
const snapshot = envelopes().findLast((item) => item.type === "snapshot.player" && item.player?.name === "VonCrush");
assert.equal(snapshot.data.blockInteractions, 4);
assert.equal(snapshot.data.entityInteractions, 1);
assert.equal(snapshot.data.containerOpens, 1);
assert.deepEqual(snapshot.data.interactedEntitiesByType, { "minecraft:villager": 1 });
assert.deepEqual(snapshot.data.openedContainersByType, { "minecraft:chest": 1 });

// Turning one off leaves the others collecting.
command("disable blockInteractions");
touchBlock(chest);
cycle();
const afterDisable = envelopes().findLast((item) => item.type === "interactions.changed");
assert.equal(afterDisable.data.block.total, 0, "a disabled metric must stop counting");
assert.equal(afterDisable.data.container.total, 1, "disabling one metric must not disable another");

const emitted = JSON.stringify(envelopes()).toLowerCase();
for (const forbidden of ["xuid", "inventory", "\"x\":", "\"z\":", "location", "fluffy", "blockface"]) {
  assert.equal(emitted.includes(forbidden), false, `interaction telemetry must not emit ${forbidden}`);
}

capture.restore();
