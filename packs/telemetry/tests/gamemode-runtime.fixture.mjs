import assert from "node:assert/strict";
import { world, system } from "@minecraft/server";

// --- setup ---
const output = [];
console.warn = (line) => output.push(String(line));

// Give the mock player a getGameMode method returning "survival"
const player = {
  id: "player-gm",
  name: "TestPlayer",
  typeId: "minecraft:player",
  location: { x: 0, y: 64, z: 0 },
  dimension: { id: "minecraft:overworld" },
  getGameMode: () => "survival",
};

await import("../behavior_pack/scripts/main.js");

// --- join + spawn ---
world.afterEvents.playerJoin.emit({ playerName: "TestPlayer" });
world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });

// --- first sampling interval: mode is "survival" ---
world.players = [player];
for (const interval of system.intervals) interval();

// --- snapshot after first cycle ---
system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

const parse = (line) => JSON.parse(line.slice(line.indexOf("{")));
const envelopes = () => output
  .filter((line) => line.includes("[BEDROCK_TELEMETRY]"))
  .map(parse);

// gameModeReading is probed lazily on first sampling cycle with players,
// so it may be absent from telemetry.started (no players yet at startup)
// but must be present and supported in snapshot.started (after first cycle)
const startedEnv = envelopes().find((e) => e.type === "telemetry.started");
assert.ok(startedEnv, "telemetry.started envelope must exist");

const snapshotStartedEnv = envelopes().findLast((e) => e.type === "snapshot.started");
assert.ok(snapshotStartedEnv, "snapshot.started envelope must exist");
assert.equal(snapshotStartedEnv.data.capabilities.gameModeReading?.supported, true,
  "gameModeReading must be supported after first sampling cycle with players");

// snapshot.player must include gameMode === "survival" (happy path)
const snapshot1 = envelopes().findLast((e) => e.type === "snapshot.player" && e.player?.name === "TestPlayer");
assert.ok(snapshot1, "snapshot.player envelope must exist");
assert.equal(snapshot1.data.gameMode, "survival", "snapshot.player must include gameMode survival");

// --- second sampling cycle: mode changes to "creative" ---
output.length = 0;
player.getGameMode = () => "creative";
for (const interval of system.intervals) interval();

system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

const envelopes2 = envelopes();

// player.gamemode.changed event must have been emitted
const changeEvent = envelopes2.find((e) => e.type === "player.gamemode.changed");
assert.ok(changeEvent, "player.gamemode.changed event must be emitted when mode changes");
assert.equal(changeEvent.player?.name, "TestPlayer");
assert.equal(changeEvent.data.previous, "survival");
assert.equal(changeEvent.data.current, "creative");

// snapshot after second cycle must include updated gameMode
const snapshot2 = envelopes2.findLast((e) => e.type === "snapshot.player" && e.player?.name === "TestPlayer");
assert.ok(snapshot2, "snapshot.player envelope must exist after mode change");
assert.equal(snapshot2.data.gameMode, "creative", "snapshot.player must reflect new gameMode");

// --- edge case: player without getGameMode (older runtime) ---
output.length = 0;
world.players = [];
world.afterEvents.playerLeave.emit({ playerId: "player-gm", playerName: "TestPlayer" });

// A player with no getGameMode joining should not cause errors
const playerNoGM = {
  id: "player-nogm",
  name: "NoGMPlayer",
  typeId: "minecraft:player",
  location: { x: 0, y: 64, z: 0 },
  dimension: { id: "minecraft:overworld" },
  // intentionally no getGameMode
};
world.afterEvents.playerJoin.emit({ playerName: "NoGMPlayer" });
world.afterEvents.playerSpawn.emit({ player: playerNoGM, initialSpawn: true });
world.players = [playerNoGM];
for (const interval of system.intervals) interval();
system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

const envelopes3 = envelopes();
const snapshot3 = envelopes3.findLast((e) => e.type === "snapshot.player" && e.player?.name === "NoGMPlayer");
assert.ok(snapshot3, "snapshot.player must exist for player without getGameMode");
// gameMode field must be absent (not undefined-forced or erroring)
assert.ok(!("gameMode" in snapshot3.data) || snapshot3.data.gameMode === null || snapshot3.data.gameMode === undefined,
  "gameMode must be absent or null when getGameMode is not supported");
