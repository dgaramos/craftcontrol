/**
 * Structural contract tests for game-terms i18n and dimensionName composition.
 * Mirrors test_interface_uses_custom_icons_and_bilingual_block_labels and
 * test_players_and_analytics_receive_localized_dimension_names removed from
 * tests/test_brand.py (issue #161).
 */

import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..");
const STATIC = join(FRONTEND, "static");
const JS = join(STATIC, "js");

const gameTermsSource = readFileSync(join(JS, "i18n", "game-terms.js"), "utf8");
const compositionSource = readFileSync(join(JS, "composition.js"), "utf8");
const i18nIndex = readFileSync(join(JS, "i18n", "index.js"), "utf8");
const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");

function frontendScript() {
  return [
    readFileSync(join(STATIC, "app.js"), "utf8"),
    compositionSource,
    readFileSync(join(JS, "features", "settings", "index.js"), "utf8"),
  ].join("\n");
}

describe("i18n contracts — block translations in game-terms.js (PT/EN)", () => {
  test('stone has PT/EN translations', () => {
    expect(gameTermsSource).toContain('stone: ["Pedra", "Stone"]');
  });

  test('diamond_ore has PT/EN translations', () => {
    expect(gameTermsSource).toContain('diamond_ore: ["Minério de diamante", "Diamond ore"]');
  });

  test('cobblestone_wall has PT/EN translations', () => {
    expect(gameTermsSource).toContain('cobblestone_wall: ["Muro de pedregulho", "Cobblestone wall"]');
  });

  test('leaf_litter has PT/EN translations', () => {
    expect(gameTermsSource).toContain('leaf_litter: ["Folhiço", "Leaf litter"]');
  });

  test('stone_stairs has PT/EN translations', () => {
    expect(gameTermsSource).toContain('stone_stairs: ["Escadas de pedra", "Stone stairs"]');
  });

  test('stripped_birch_log has PT/EN translations', () => {
    expect(gameTermsSource).toContain('stripped_birch_log: ["Tronco de bétula descascado", "Stripped birch log"]');
  });

  test('reeds (sugar cane) has PT/EN translations', () => {
    expect(gameTermsSource).toContain('reeds: ["Cana-de-açúcar", "Sugar cane"]');
  });
});

describe("i18n contracts — ES block overrides in game-terms.js", () => {
  test('cobblestone has ES translation "Adoquín"', () => {
    expect(gameTermsSource).toContain('cobblestone: "Adoquín"');
  });

  test('leaf_litter has ES translation "Hojarasca"', () => {
    expect(gameTermsSource).toContain('leaf_litter: "Hojarasca"');
  });
});

describe("i18n contracts — SVG sprite usage in game-terms.js", () => {
  test("game-terms.js uses craftcontrol-blocks.svg sprite", () => {
    expect(gameTermsSource).toContain("/static/craftcontrol-blocks.svg#block-");
  });

  test("game-terms.js uses craftcontrol-ui.svg sprite", () => {
    expect(gameTermsSource).toContain("/static/craftcontrol-ui.svg#ui-");
  });

  test("game-terms.js exports blockTermMarkup function", () => {
    expect(gameTermsSource).toContain("function blockTermMarkup");
  });
});

describe("i18n contracts — ES locale wired up in i18n index", () => {
  test('i18n/index.js imports es.js', () => {
    expect(i18nIndex).toContain('from "./es.js?v=8"');
  });
});

describe("i18n contracts — template locale and flag icons", () => {
  test('template sets data-locale="es"', () => {
    expect(template).toContain('data-locale="es"');
  });

  test("template includes PT flag icon (ui-flag-br)", () => {
    expect(template).toContain("ui-flag-br");
  });

  test("template includes EN flag icon (ui-flag-us)", () => {
    expect(template).toContain("ui-flag-us");
  });

  test("template includes ES flag icon (ui-flag-es)", () => {
    expect(template).toContain("ui-flag-es");
  });
});

describe("i18n contracts — no legacy Unicode icons in bundled script or template", () => {
  const legacyIconPattern = /[☀☠⚔♛♟⚙◆◇◈▦▥▤☷⌂⌛♥▶↝➶✦✓↻⛏⚡⚠]/;

  test("frontend script bundle has no legacy Unicode icons", () => {
    expect(legacyIconPattern.test(frontendScript())).toBe(false);
  });

  test("index.html template has no legacy Unicode icons", () => {
    expect(legacyIconPattern.test(template)).toBe(false);
  });
});

describe("i18n contracts — dimensionName exported from game-terms.js", () => {
  test("game-terms.js defines function dimensionName(identifier)", () => {
    expect(gameTermsSource).toContain("function dimensionName(identifier)");
  });
});

describe("i18n contracts — dimensionName threaded through composition to players and analytics", () => {
  test("composition.js passes blockIcon, dimensionName, gameTermMarkup to players feature", () => {
    expect(compositionSource).toContain("blockIcon, dimensionName, gameTermMarkup");
  });

  test("composition.js passes blockTermMarkup, dimensionName, formatRankingValue to analytics", () => {
    expect(compositionSource).toContain("blockTermMarkup, dimensionName, formatRankingValue");
  });

  test("composition.js passes formatDuration, dimensionName, localeTag to analytics", () => {
    expect(compositionSource).toContain("formatDuration, dimensionName, localeTag");
  });
});
