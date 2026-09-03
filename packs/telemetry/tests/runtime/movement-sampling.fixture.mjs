/**
 * Movement sampling edge-case fixture.
 *
 * Covers four cases where distance must NOT be accumulated:
 *   1. Teleport (horizontal displacement > 128 blocks)
 *   2. Dimension mismatch between two consecutive samples
 *   3. First tick / no previous position yet
 *   4. Standing still (displacement == 0)
 *
 * Each case uses an isolated module import so that the runtime state
 * (positions Map, gameModes Map) is always fresh.  The minecraft-loader
 * virtual module system resets between fixture files, so a single import
 * chain per fixture run is sufficient.
 */

import assert from "node:assert/strict";
import { world, system } from "@minecraft/server";
import { captureConsole } from "./console-capture.mjs";

const capture = captureConsole("warn");
const { lines: output } = capture;

await import("../../behavior_pack/scripts/main.js");

const overworld = "minecraft:overworld";
const nether = "minecraft:nether";

// Helper: parse every snapshot.player envelope for a given player name.
function snapshotsFor(name) {
  return output
    .filter((line) => line.includes("[BEDROCK_TELEMETRY]"))
    .map((line) => JSON.parse(line.slice(line.indexOf("{"))))
    .filter((env) => env.type === "snapshot.player" && env.player?.name === name);
}

// ── 1. Teleport > 128 blocks ────────────────────────────────────────────────
// The player spawns at (0,64,0) and is then found 200 blocks away.
// That displacement exceeds the 128-block guard, so distanceByDimension must
// stay at 0 and the standing-still snapshot distance must also be 0.
{
  const player = {
    id: "teleport-player",
    name: "TeleportPlayer",
    typeId: "minecraft:player",
    location: { x: 0, y: 64, z: 0 },
    dimension: { id: overworld },
  };

  world.afterEvents.playerJoin.emit({ playerName: "TeleportPlayer" });
  world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });

  // First interval: records initial position, no previous to compare against.
  world.players = [player];
  for (const interval of system.intervals) interval();

  // Move the player >128 blocks horizontally.
  player.location = { x: 200, y: 64, z: 0 };

  // Second interval: displacement is 200 > 128 → must be skipped.
  for (const interval of system.intervals) interval();

  system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

  const snapshots = snapshotsFor("TeleportPlayer");
  assert.ok(snapshots.length > 0, "snapshot.player must exist for TeleportPlayer");
  const last = snapshots.at(-1);
  assert.equal(
    last.data.distanceByDimension?.[overworld] ?? 0,
    0,
    "teleport > 128 blocks must not accumulate distance",
  );
}

// ── 2. Dimension mismatch ────────────────────────────────────────────────────
// Previous position is recorded in the nether; next position is in the
// overworld (not via playerDimensionChange, which updates positions atomically).
// The sampling loop sees different dimension ids and must skip the comparison.
{
  const player = {
    id: "dim-player",
    name: "DimPlayer",
    typeId: "minecraft:player",
    location: { x: 100, y: 64, z: 100 },
    dimension: { id: nether },
  };

  world.afterEvents.playerJoin.emit({ playerName: "DimPlayer" });
  world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });

  // First interval: records position in the nether.
  world.players = [player];
  for (const interval of system.intervals) interval();

  // Dimension changes without going through the official event.
  player.dimension = { id: overworld };
  player.location = { x: 101, y: 64, z: 100 };

  // Second interval: previous.dimension !== current.dimension → must skip.
  for (const interval of system.intervals) interval();

  system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

  const snapshots = snapshotsFor("DimPlayer");
  assert.ok(snapshots.length > 0, "snapshot.player must exist for DimPlayer");
  const last = snapshots.at(-1);
  const overworldDist = last.data.distanceByDimension?.[overworld] ?? 0;
  assert.equal(
    overworldDist,
    0,
    "dimension mismatch must not accumulate overworld distance",
  );
}

// ── 3. No previous position (first tick) ────────────────────────────────────
// A player who spawns and is sampled for the very first time has no entry in
// the positions Map yet.  The loop must set the initial position and skip
// distance accumulation for that tick.
{
  const player = {
    id: "first-tick-player",
    name: "FirstTickPlayer",
    typeId: "minecraft:player",
    location: { x: 50, y: 64, z: 50 },
    dimension: { id: overworld },
  };

  world.afterEvents.playerJoin.emit({ playerName: "FirstTickPlayer" });
  // Note: no playerSpawn event — positions Map never gets seeded from spawn.
  // This simulates a player that appears in getAllPlayers() before spawn fires.

  world.players = [player];
  // Single interval: positions.get(player.id) is undefined → must skip.
  for (const interval of system.intervals) interval();

  system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

  const snapshots = snapshotsFor("FirstTickPlayer");
  assert.ok(snapshots.length > 0, "snapshot.player must exist for FirstTickPlayer");
  const last = snapshots.at(-1);
  assert.equal(
    last.data.distanceByDimension?.[overworld] ?? 0,
    0,
    "first-tick player must not accumulate distance on the initial sample",
  );
}

// ── 4. Standing still (displacement == 0) ───────────────────────────────────
// A player who does not move between two consecutive samples should have
// distance remain at 0 — the `distance <= 0` guard must drop the update.
{
  const player = {
    id: "still-player",
    name: "StillPlayer",
    typeId: "minecraft:player",
    location: { x: 10, y: 64, z: 10 },
    dimension: { id: overworld },
  };

  world.afterEvents.playerJoin.emit({ playerName: "StillPlayer" });
  world.afterEvents.playerSpawn.emit({ player, initialSpawn: true });

  // First interval: records initial position.
  world.players = [player];
  for (const interval of system.intervals) interval();

  // Location unchanged → horizontal distance is 0.
  for (const interval of system.intervals) interval();

  system.afterEvents.scriptEventReceive.emit({ id: "bedrock_telemetry:sync", message: "full" });

  const snapshots = snapshotsFor("StillPlayer");
  assert.ok(snapshots.length > 0, "snapshot.player must exist for StillPlayer");
  const last = snapshots.at(-1);
  assert.equal(
    last.data.distanceByDimension?.[overworld] ?? 0,
    0,
    "standing still must not accumulate distance",
  );
}

capture.restore();
