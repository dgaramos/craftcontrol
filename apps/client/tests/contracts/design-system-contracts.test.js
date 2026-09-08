/**
 * The design system document, checked against the stylesheets (#588).
 *
 * Three of the last four review findings were in `docs/design-system.md`, not in
 * code: it claimed selection was sand when the panel used gold, promised 44px of
 * touch height for a control that has always been 36px, and described a rule the
 * icon variant did not have. The document was the only part of the system that
 * nothing verified, which made it a source of bugs rather than a guard against
 * them. These tests fail when the document and the stylesheets disagree.
 */

import { readFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const STATIC = join(ROOT, "static");
const DOCUMENT = readFileSync(join(ROOT, "..", "..", "docs", "design-system.md"), "utf8");

const STYLESHEETS = ["app.css", "players.css", "analytics.css", "auth.css"];
const CSS = Object.fromEntries(
  STYLESHEETS.map((name) => [name, readFileSync(join(STATIC, name), "utf8")])
);
const ALL_CSS = Object.values(CSS).join("\n");

/** The gold every selected state is drawn with. */
const SELECTION_GOLD = "#f0c040";

/** Rules that carry `.active` but are not a selection inside a screen. */
const NOT_A_SELECTION = [
  // Navigation, not a choice: it uses the nav tokens the shell defines.
  ".bottom-nav-tab.active",
];

/** Every rule whose selector marks a selected state. */
function selectionRules() {
  const rules = [];
  for (const [file, css] of Object.entries(CSS)) {
    const pattern = /([^{}]*\.active[^{}]*)\{([^}]*)\}/g;
    let match;
    while ((match = pattern.exec(css)) !== null) {
      const selector = match[1].trim();
      if (selector.includes(":hover") || selector.includes(":not(.active)")) continue;
      if (NOT_A_SELECTION.some((exception) => selector.includes(exception))) continue;
      rules.push({ file, selector, body: match[2] });
    }
  }
  return rules;
}

describe("design system — selection", () => {
  test("the document names gold as the selection colour", () => {
    expect(DOCUMENT).toMatch(/Selection is gold/);
    expect(DOCUMENT).not.toMatch(/Selection is sand/);
  });

  test("every selected state is drawn with that gold", () => {
    const rules = selectionRules();
    expect(rules.length).toBeGreaterThan(0);
    for (const rule of rules) {
      expect(rule.body).toContain(SELECTION_GOLD);
    }
  });

  test("no selected state borrows green, the live and save colour", () => {
    // #4d9735 and #78c34d are the panel's greens; either one marking a choice
    // would make "chosen" and "healthy" the same signal.
    for (const rule of selectionRules()) {
      expect(rule.body).not.toMatch(/#(78c34d|4b9c34|80cc52|4d9d35)/);
    }
  });
});

describe("design system — choice controls", () => {
  test("the text choice is 36px tall in 10px display type", () => {
    const rule = ALL_CSS.match(/\.choice-group > button[^{]*\{([^}]*)\}/);
    expect(rule).not.toBeNull();
    expect(rule[1]).toContain("min-height: 36px");
    expect(rule[1]).toContain("font-size: 10px");
    expect(DOCUMENT).toContain("36px");
  });

  test("the Players filter is that same control, not a copy of it", () => {
    const shared = ALL_CSS.match(/\.choice-group > button[^{]*\{/)[0];
    expect(shared).toContain(".player-filters > button");
  });

  test("an icon selection keeps the dark surface and takes a gold edge", () => {
    const rule = ALL_CSS.match(/\.analytics-view-switch > button\.active[^{]*\{([^}]*)\}/);
    expect(rule).not.toBeNull();
    expect(rule[1]).toContain(`border-top-color: ${SELECTION_GOLD}`);
    // Filling it would put multi-colour pixel art on a gold ground.
    expect(rule[1]).not.toContain(`background: linear-gradient(${SELECTION_GOLD}`);
  });
});

describe("design system — touch targets", () => {
  test("inputs and selects are at least 44px, as the document promises", () => {
    const rule = ALL_CSS.match(/\.settings-screen \.field input[^{]*\{([^}]*)\}/);
    expect(rule).not.toBeNull();
    expect(rule[1]).toContain("min-height: 44px");
    expect(DOCUMENT).toContain("44px");
  });

  test("the document does not promise 44px for the choice chips", () => {
    // They have always been 36px; the promise used to cover them and was false.
    expect(DOCUMENT).toMatch(/choice chips are 36px/);
  });
});

describe("design system — screen anatomy", () => {
  test("the heading paragraph is a shared rule, not a per-screen exception", () => {
    const rule = CSS["app.css"].match(/\.inner-heading p \{([^}]*)\}/);
    expect(rule).not.toBeNull();
    expect(rule[1]).toContain("font-size: 11px");
    expect(CSS["players.css"]).not.toContain(".player-server-settings .inner-heading p");
  });
});
