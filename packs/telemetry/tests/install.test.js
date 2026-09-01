import { test } from "@jest/globals";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("installer publishes readable pack files and associates the world", () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "craftcontrol-telemetry-"));
  const project = path.resolve(__dirname, "..");
  const world = path.join(temporary, "worlds", "TestWorld");
  const legacy = path.join(temporary, "behavior_packs", "minecraft-bedrock-telemetry");
  fs.mkdirSync(world, { recursive: true });
  fs.mkdirSync(legacy, { recursive: true });
  fs.writeFileSync(path.join(legacy, "legacy.txt"), "old");
  const result = spawnSync(process.execPath, [path.join(project, "scripts", "install.mjs"), project, temporary, "TestWorld"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const installedScript = path.join(temporary, "behavior_packs", "craftcontrol-telemetry", "scripts", "main.js");
  assert.equal(fs.statSync(installedScript).mode & 0o777, 0o644);
  assert.equal(fs.statSync(path.dirname(installedScript)).mode & 0o777, 0o755);
  assert.equal(fs.existsSync(legacy), false);
  const packs = JSON.parse(fs.readFileSync(path.join(world, "world_behavior_packs.json"), "utf8"));
  assert.equal(packs[0].pack_id, "8c916948-76c6-4aa5-91e0-97671dfd3830");
  assert.deepEqual(packs[0].version, [0, 4, 0]);
});
