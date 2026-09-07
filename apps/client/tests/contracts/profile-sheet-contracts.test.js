/**
 * Structural contract tests for profile sheet wiring (T06).
 * Verifies that composition.js wires #profile-btn → sheet open/close,
 * fills user identity, and that the old language-picker is hidden or removed.
 */

import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..", "..");
const STATIC = join(FRONTEND, "static");
const JS = join(STATIC, "js");

const composition = readFileSync(join(JS, "composition.js"), "utf8");
const indexTemplate = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");

describe("profile sheet contracts — open/close wiring", () => {
  test("composition.js wires #profile-btn onclick to open #profile-sheet", () => {
    expect(composition).toContain("profile-btn");
    expect(composition).toContain("profile-sheet");
  });

  test("composition.js removes hidden on #profile-sheet to open it", () => {
    expect(composition).toContain("openProfileSheet");
    expect(composition).toMatch(/sheet\.hidden\s*=\s*false/);
  });

  test("composition.js wires bottom-sheet-backdrop click to close the sheet", () => {
    expect(composition).toContain("bottom-sheet-backdrop");
  });

  test("composition.js sets hidden=true to close the profile sheet", () => {
    expect(composition).toContain("closeProfileSheet");
    expect(composition).toMatch(/sheet\.hidden\s*=\s*true/);
  });
});

describe("profile sheet contracts — user identity fill", () => {
  test("composition.js populates #profile-sheet-initial from state.user.name", () => {
    expect(composition).toContain("profile-sheet-initial");
    expect(composition).toContain("state.user");
  });

  test("composition.js populates #profile-sheet-name from state.user.name", () => {
    expect(composition).toContain("profile-sheet-name");
  });

  test("composition.js populates #profile-sheet-role from state.user.role", () => {
    expect(composition).toContain("profile-sheet-role");
  });

  test("composition.js fills #profile-initial topbar icon from state.user.name", () => {
    expect(composition).toContain("profile-initial");
  });
});

describe("profile sheet contracts — locale buttons in sheet", () => {
  test("index.html has [data-locale] buttons inside #profile-sheet", () => {
    const sheetStart = indexTemplate.indexOf('id="profile-sheet"');
    expect(sheetStart).toBeGreaterThan(-1);
    const sheetEnd = indexTemplate.indexOf('</div>\n  </div>', sheetStart);
    const sheetChunk = indexTemplate.slice(sheetStart, sheetEnd + 20);
    expect(sheetChunk).toContain('data-locale="pt"');
    expect(sheetChunk).toContain('data-locale="en"');
    expect(sheetChunk).toContain('data-locale="es"');
  });

  test("composition.js applies aria-selected to all [data-locale] elements", () => {
    expect(composition).toContain('[data-locale]');
    expect(composition).toContain("aria-selected");
  });
});

describe("profile sheet contracts — old language-picker removed", () => {
  test("index.html does not render the legacy topbar #language-picker", () => {
    // The language picker was removed from the topbar; locale switching now
    // lives exclusively in #profile-sheet via [data-locale] buttons.
    expect(indexTemplate).not.toContain('id="language-picker"');
  });
});
