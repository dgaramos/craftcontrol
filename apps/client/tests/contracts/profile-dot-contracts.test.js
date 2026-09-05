/**
 * Structural contract tests for profile-dot reactive wiring (T07).
 * Verifies that composition.js subscribes to state "changes" so the
 * #profile-dot notification indicator is reactively updated whenever
 * state.changes is assigned (e.g. discard-all, apply-changes).
 */

import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..", "..");
const JS = join(FRONTEND, "static", "js");

const composition = readFileSync(join(JS, "composition.js"), "utf8");

describe("profile-dot contracts — reactive changes subscription", () => {
  test("composition.js subscribes to state 'changes'", () => {
    expect(composition).toMatch(/state\.subscribe\(\s*["']changes["']/);
  });

  test("composition.js calls updateSaveLabel inside the changes subscription", () => {
    // The subscription callback must invoke updateSaveLabel to sync the dot.
    expect(composition).toMatch(/state\.subscribe\(\s*["']changes["'][^;]*updateSaveLabel/s);
  });

  test("index.html contains #profile-dot element", () => {
    const indexTemplate = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(indexTemplate).toContain('id="profile-dot"');
  });

  test("profile-dot is hidden by default in index.html", () => {
    const indexTemplate = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(indexTemplate).toMatch(/id="profile-dot"[^>]*hidden/);
  });
});
