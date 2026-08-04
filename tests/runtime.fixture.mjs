import assert from "node:assert/strict";
import { world, system } from "@minecraft/server";

const output = [];
console.warn = (line) => output.push(String(line));

await import("../behavior_pack/scripts/main.js");

world.afterEvents.playerJoin.emit({ playerName: "VonCrush" });
world.afterEvents.playerBreakBlock.emit({
  player: { name: "VonCrush" },
  brokenBlockPermutation: { type: { id: "minecraft:stone" } },
});
world.afterEvents.playerLeave.emit({ playerId: "player-1", playerName: "VonCrush" });
system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

const envelopes = output
  .filter((line) => line.includes("[BEDROCK_TELEMETRY]"))
  .map((line) => JSON.parse(line.slice(line.indexOf("{") )));
const blockEvent = envelopes.find((item) => item.type === "block.broken");
const snapshot = envelopes.findLast((item) => item.type === "snapshot.player" && item.player?.name === "VonCrush");

assert.equal(blockEvent?.data.blockType, "minecraft:stone");
assert.equal(snapshot?.data.joins, 1);
assert.equal(snapshot?.data.blocksBroken, 1);
assert.equal(snapshot?.data.brokenByType["minecraft:stone"], 1);
