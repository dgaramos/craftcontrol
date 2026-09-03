import assert from "node:assert/strict";
import { world, system } from "@minecraft/server";
import { captureConsole } from "./console-capture.mjs";

const capture = captureConsole("warn");
const { lines: output } = capture;

// Player without getGameMode (runtime that does not support it)
const player = {
  id: "player-nogm",
  name: "NoGMPlayer",
  typeId: "minecraft:player",
  location: { x: 0, y: 64, z: 0 },
  dimension: { id: "minecraft:overworld" },
  // intentionally no getGameMode
};

await import("../../behavior_pack/scripts/main.js");

world.afterEvents.playerJoin.emit({ playerName: "NoGMPlayer" });
world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });
world.players = [player];

for (const interval of system.intervals) interval();
system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

const parse = (line) => JSON.parse(line.slice(line.indexOf("{")));
const envelopes = output
  .filter((line) => line.includes("[BEDROCK_TELEMETRY]"))
  .map(parse);

// gameModeReading must be registered as supported: false when no player has getGameMode
const snapshotStarted = envelopes.findLast((e) => e.type === "snapshot.started");
assert.ok(snapshotStarted, "snapshot.started must exist");
assert.equal(snapshotStarted.data.capabilities.gameModeReading?.supported, false,
  "gameModeReading must be supported:false when runtime lacks getGameMode");

// no player.gamemode.changed events should be emitted
const changeEvent = envelopes.find((e) => e.type === "player.gamemode.changed");
assert.ok(!changeEvent, "player.gamemode.changed must not be emitted when getGameMode is unsupported");

// snapshot.player must not include gameMode field
const snapshotPlayer = envelopes.findLast((e) => e.type === "snapshot.player" && e.player?.name === "NoGMPlayer");
assert.ok(snapshotPlayer, "snapshot.player must exist");
assert.ok(!("gameMode" in snapshotPlayer.data), "gameMode must be absent when getGameMode is unsupported");
capture.restore();
