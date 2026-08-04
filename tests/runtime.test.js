import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

test("captures a real runtime join, block break, leave, and snapshot flow", () => {
  const result = spawnSync(process.execPath, [
    "--no-warnings",
    "--experimental-loader=./tests/minecraft-loader.mjs",
    "./tests/runtime.fixture.mjs",
  ], { cwd: process.cwd(), encoding: "utf8" });
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});
