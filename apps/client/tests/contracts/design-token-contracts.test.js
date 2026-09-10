import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..", "..");
const STATIC = join(FRONTEND, "static");
const REPO = resolve(FRONTEND, "..", "..");

/* The four component stylesheets. `light.css` is deliberately absent: it is the
   re-tint layer, and #611-#614 empty it by migrating call sites, not by editing
   it directly. */
const COMPONENT_SHEETS = ["app.css", "analytics.css", "players.css", "auth.css"];

/* Sprites keep their own palette in both themes by existing decision
   (docs/design-system.md, light.css). Rather than enumerating their hex values
   — a list that would rot on every sprite tweak — each stylesheet marks the
   exclusion by location, and the budget skips whatever those regions contain. */
const SPRITE_REGION_OPEN = "/* region: sprites";
const SPRITE_REGION_CLOSE = "/* endregion: sprites */";

/** Mirrors `grep -oiE '#[0-9a-f]{3,8}\b'`, the command that produced the
    grandfathered baseline recorded in issue #610. */
function hexLiterals(css) {
  return css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
}

/** Removes every `/* region: sprites … *​/ … /* endregion: sprites *​/` block.
    Unterminated regions are left in place so a malformed marker shows up as a
    budget failure instead of silently exempting the rest of the file. */
function stripSpriteRegions(css) {
  let out = "";
  let cursor = 0;
  for (;;) {
    const open = css.indexOf(SPRITE_REGION_OPEN, cursor);
    if (open === -1) break;
    const close = css.indexOf(SPRITE_REGION_CLOSE, open);
    if (close === -1) break;
    out += css.slice(cursor, open);
    cursor = close + SPRITE_REGION_CLOSE.length;
  }
  return out + css.slice(cursor);
}

/* The token vocabulary is the sanctioned home for literal values: tier 1 is
   where a raw ramp step is allowed to be written down. Counting it would make
   the budget punish the very thing it exists to encourage, so it is excluded
   and the budget measures untokenized color AT CALL SITES. */
const VOCABULARY_OPEN = "/* token-layer: primitives */";
const VOCABULARY_CLOSE = "/* token-layer: end */";

function stripVocabulary(css) {
  const open = css.indexOf(VOCABULARY_OPEN);
  if (open === -1) return css;
  const close = css.indexOf(VOCABULARY_CLOSE, open);
  if (close === -1) return css;
  return css.slice(0, open) + css.slice(close + VOCABULARY_CLOSE.length);
}

function sheet(name) {
  return readFileSync(join(STATIC, name), "utf8");
}

function countAcross(transform) {
  const all = COMPONENT_SHEETS.flatMap((name) => hexLiterals(transform(stripVocabulary(sheet(name)))));
  return {
    occurrences: all.length,
    unique: new Set(all.map((hex) => hex.toLowerCase())).size,
  };
}

describe("design token contracts — hex counting helper", () => {
  test("counts three-, four-, six- and eight-digit hex literals", () => {
    const css = "a{color:#fff;background:#0009;border-color:#a0df63;outline:#33442b14}";
    expect(hexLiterals(css)).toEqual(["#fff", "#0009", "#a0df63", "#33442b14"]);
  });

  test("counts upper-case hex and folds case only when de-duplicating", () => {
    const css = "a{color:#A0DF63}b{color:#a0df63}";
    expect(hexLiterals(css)).toHaveLength(2);
    expect(new Set(hexLiterals(css).map((hex) => hex.toLowerCase())).size).toBe(1);
  });

  test("counts a hex written inside a comment", () => {
    // A literal parked in a comment is still an untokenized decision waiting to
    // be pasted back into a declaration, so the budget must see it.
    expect(hexLiterals("/* was #112233 */ a{color:var(--x)}")).toEqual(["#112233"]);
  });

  test("does not count a bare fragment or id selector", () => {
    expect(hexLiterals("a[href='#top']{color:var(--x)} #tabs{display:none}")).toEqual([]);
  });
});

describe("design token contracts — sprite region helper", () => {
  test("drops the hex literals inside a named sprite region", () => {
    const css = [
      ".a{color:#111111}",
      "/* region: sprites — own palette */",
      ".shield{background:#222222;border-color:#333333}",
      "/* endregion: sprites */",
      ".b{color:#444444}",
    ].join("\n");
    expect(hexLiterals(stripSpriteRegions(css))).toEqual(["#111111", "#444444"]);
  });

  test("drops every region when a stylesheet marks more than one", () => {
    const css = [
      "/* region: sprites */ .a{color:#111111} /* endregion: sprites */",
      ".keep{color:#222222}",
      "/* region: sprites */ .b{color:#333333} /* endregion: sprites */",
    ].join("\n");
    expect(hexLiterals(stripSpriteRegions(css))).toEqual(["#222222"]);
  });

  test("keeps an unterminated region so a malformed marker cannot exempt the file", () => {
    const css = "/* region: sprites */ .a{color:#111111} .b{color:#222222}";
    expect(hexLiterals(stripSpriteRegions(css))).toEqual(["#111111", "#222222"]);
  });

  test("a stylesheet with no region is returned unchanged", () => {
    const css = ".a{color:#111111}";
    expect(stripSpriteRegions(css)).toBe(css);
  });
});

describe("design token contracts — vocabulary exclusion helper", () => {
  test("drops the literals that define the token vocabulary", () => {
    const css = [
      ":root{--legacy:#111111;",
      "/* token-layer: primitives */",
      "--stone-950:#222222;",
      "/* token-layer: end */",
      "--other:#333333}",
    ].join("\n");
    expect(hexLiterals(stripVocabulary(css))).toEqual(["#111111", "#333333"]);
  });

  test("keeps an unterminated vocabulary block so a malformed marker cannot exempt the file", () => {
    const css = "/* token-layer: primitives */ --a:#111111; --b:#222222;";
    expect(hexLiterals(stripVocabulary(css))).toEqual(["#111111", "#222222"]);
  });

  test("a stylesheet with no vocabulary block is returned unchanged", () => {
    const css = ".a{color:#111111}";
    expect(stripVocabulary(css)).toBe(css);
  });
});

/* Two budgets, because the issue's headline figure and the figure that actually
   measures progress are not the same number.

   Both exclude the token vocabulary itself, for the reason given above.

   WHOLE-FILE counts every call-site literal. The figure recorded in #610 was
   754 occurrences / 406 unique, reproduced against the pre-token tree by:
     cat app.css analytics.css players.css auth.css | grep -oiE '#[0-9a-f]{3,8}\b' | wc -l
   This step already retired four of them — --surface-raised, --surface-inset
   and the two panel stripes moved into the vocabulary — so the ceiling is
   pinned at the value measured after that move rather than at the historical
   754/406. A ceiling with slack in it does not ratchet.

   OUTSIDE-SPRITE-REGIONS additionally excludes the sprite palettes that are
   deliberately never tokenized. This is the number that measures tokenization
   progress in #611-#614; the whole-file number can only follow it down.

   Both are ceilings. Lower them as call sites migrate. Never raise either one —
   a raise means an untokenized color was added, which is the exact regression
   this contract exists to catch. */
const WHOLE_FILE_BUDGET = { occurrences: 750, unique: 405 };
const OUTSIDE_SPRITES_BUDGET = { occurrences: 728, unique: 386 };

describe("design token contracts — literal hex budget", () => {
  test("whole-file literal hex occurrences do not exceed the #610 baseline", () => {
    expect(countAcross((css) => css).occurrences).toBeLessThanOrEqual(WHOLE_FILE_BUDGET.occurrences);
  });

  test("whole-file unique literal hex values do not exceed the #610 baseline", () => {
    expect(countAcross((css) => css).unique).toBeLessThanOrEqual(WHOLE_FILE_BUDGET.unique);
  });

  test("literal hex occurrences outside sprite regions do not exceed the budget", () => {
    expect(countAcross(stripSpriteRegions).occurrences).toBeLessThanOrEqual(
      OUTSIDE_SPRITES_BUDGET.occurrences,
    );
  });

  test("unique literal hex values outside sprite regions do not exceed the budget", () => {
    expect(countAcross(stripSpriteRegions).unique).toBeLessThanOrEqual(OUTSIDE_SPRITES_BUDGET.unique);
  });

  test("the sprite regions actually exempt something, so the budgets differ", () => {
    // Guards against the exclusion silently becoming a no-op if a future edit
    // drops the markers: the two budgets would then measure the same thing.
    expect(countAcross(stripSpriteRegions).occurrences).toBeLessThan(countAcross((css) => css).occurrences);
  });
});

describe("design token contracts — named sprite regions", () => {
  test("app.css encloses every sprite rule in a named region", () => {
    const stripped = stripSpriteRegions(sheet("app.css"));
    for (const selector of [".grass-edge", ".shield", ".server-status-shield"]) {
      expect(stripped).not.toContain(selector);
    }
  });

  test("every opened sprite region in app.css is closed", () => {
    const css = sheet("app.css");
    const opened = css.split(SPRITE_REGION_OPEN).length - 1;
    const closed = css.split(SPRITE_REGION_CLOSE).length - 1;
    expect(opened).toBeGreaterThan(0);
    expect(opened).toBe(closed);
  });
});

/* The token vocabulary is delimited by machine-readable markers so this
   contract reads the layers rather than guessing at them from position. */
function tokenLayer(name) {
  const css = sheet("app.css");
  const start = css.indexOf(`/* token-layer: ${name} */`);
  expect(start).toBeGreaterThan(-1);
  const end = css.indexOf("/* token-layer:", start + 1);
  return css.slice(start, end === -1 ? css.length : end);
}

function declaredTokens(block) {
  return [...block.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gim)].map((match) => match[1]);
}

/* A tier-2 name says what a token DOES. It may never say what it looks like or
   which theme it belongs to — that is what lets light.css re-tint a token
   without the name turning into a lie. Matched per hyphen segment, so
   `--edge-highlight` is fine and `--edge-light` is not. */
const APPEARANCE_WORDS = new Set([
  "dark", "light", "bright", "dim", "night", "day",
  "green", "red", "blue", "yellow", "purple", "orange", "white", "black",
  "gray", "grey", "brown", "pink", "cyan", "magenta", "gold", "silver",
  "amber", "teal", "violet", "olive", "beige",
]);

describe("design token contracts — three-layer vocabulary", () => {
  test("app.css declares all three token layers", () => {
    for (const layer of ["primitives", "semantic", "component"]) {
      expect(declaredTokens(tokenLayer(layer)).length).toBeGreaterThan(0);
    }
  });

  test("every primitive is named by Minecraft material and numeric step", () => {
    const primitives = declaredTokens(tokenLayer("primitives"));
    expect(primitives.length).toBeGreaterThanOrEqual(30);
    for (const token of primitives) {
      expect(token).toMatch(/^--(stone|grass|copper|sand|water|redstone|amethyst)-\d{3}$/);
    }
  });

  test("no semantic token name describes an appearance or a theme", () => {
    for (const token of declaredTokens(tokenLayer("semantic"))) {
      for (const segment of token.replace(/^--/, "").split("-")) {
        expect(APPEARANCE_WORDS.has(segment)).toBe(false);
      }
    }
  });

  test("no component token name describes an appearance or a theme", () => {
    for (const token of declaredTokens(tokenLayer("component"))) {
      for (const segment of token.replace(/^--/, "").split("-")) {
        expect(APPEARANCE_WORDS.has(segment)).toBe(false);
      }
    }
  });

  test("the semantic layer covers the six documented families", () => {
    const semantic = declaredTokens(tokenLayer("semantic")).join(" ");
    for (const family of [
      "--surface-base", "--surface-raised", "--surface-overlay",
      "--edge-highlight", "--edge-shadow", "--shadow-pixel",
      "--border-base", "--border-focus",
      "--text-primary", "--text-secondary", "--text-on-accent",
      "--success-fg", "--danger-fg", "--warning-fg", "--info-fg", "--selected-fg", "--neutral-fg",
      "--state-focus-ring", "--state-disabled-fg",
    ]) {
      expect(semantic).toContain(family);
    }
  });

  test("every semantic accent family carries the full fg/bg/border triplet", () => {
    const semantic = declaredTokens(tokenLayer("semantic"));
    for (const family of ["success", "danger", "warning", "info", "selected", "neutral"]) {
      for (const role of ["fg", "bg", "border"]) {
        expect(semantic).toContain(`--${family}-${role}`);
      }
    }
  });

  test("semantic tokens resolve through primitives rather than fresh literals", () => {
    // The point of the tier is that it renames primitives; a literal here would
    // be a fourth, undocumented palette.
    expect(hexLiterals(tokenLayer("semantic"))).toEqual([]);
  });
});

describe("design token contracts — documentation", () => {
  /* Whitespace-normalized so the assertions survive a prose reflow: the rule
     matters, the line breaks do not. */
  const doc = () =>
    readFileSync(join(REPO, "docs", "design-system.md"), "utf8")
      .toLowerCase()
      .replace(/\s+/g, " ");

  test("the design system documents all three token layers", () => {
    for (const layer of ["primitive", "semantic alias", "component token"]) {
      expect(doc()).toContain(layer);
    }
  });

  test("the design system states the re-tint rule", () => {
    expect(doc()).toContain("re-tints tokens and never re-declares a selector");
  });

  test("the design system forbids call sites from reaching past the semantic tier", () => {
    // This corollary is what keeps #611-#614 honest: without it, a call site
    // can bind to a raw ramp step and the re-tint layer loses its seam.
    expect(doc()).toContain("never reference a primitive directly");
  });
});

describe("design token contracts — cache busting", () => {
  test("index.html references app.css?v=64", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain("/static/app.css?v=64");
  });
});
