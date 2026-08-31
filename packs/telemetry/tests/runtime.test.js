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

for (const fixture of ["migration-runtime.fixture.mjs", "v2-migration-runtime.fixture.mjs", "corrupt-runtime.fixture.mjs", "shard-runtime.fixture.mjs", "oversize-shard.fixture.mjs", "capability-runtime.fixture.mjs", "gamemode-runtime.fixture.mjs"]) {
  test(`passes runtime fixture ${fixture}`, () => {
    const result = spawnSync(process.execPath, [
      "--no-warnings",
      "--experimental-loader=./tests/minecraft-loader.mjs",
      `./tests/${fixture}`,
    ], { cwd: process.cwd(), encoding: "utf8" });
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  });
}
