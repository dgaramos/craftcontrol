import { createGameTerms } from "../static/js/i18n/game-terms.js";

function makeTerms(locale) {
  const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  return createGameTerms({ getLocale: () => locale, escapeHtml });
}

describe("createGameTerms — blockName via blockTermMarkup", () => {
  test("known block returns pt name", () => {
    const terms = makeTerms("pt");
    const html = terms.blockTermMarkup("diamond_ore");
    expect(html).toContain("Minério de diamante");
  });

  test("known block returns en name", () => {
    const terms = makeTerms("en");
    const html = terms.blockTermMarkup("diamond_ore");
    expect(html).toContain("Diamond ore");
  });

  test("known block returns es name", () => {
    const terms = makeTerms("es");
    const html = terms.blockTermMarkup("diamond_ore");
    expect(html).toContain("Mena de diamante");
  });

  test("minecraft: prefix is stripped", () => {
    const terms = makeTerms("en");
    const html = terms.blockTermMarkup("minecraft:diamond_ore");
    expect(html).toContain("Diamond ore");
  });

  test("unknown block generates from identifier words in en", () => {
    const terms = makeTerms("en");
    const html = terms.blockTermMarkup("custom_block_name");
    expect(html).toContain("Custom block name");
  });

  test("unknown block generates localized words in pt", () => {
    const terms = makeTerms("pt");
    const html = terms.blockTermMarkup("oak_log");
    expect(html).toContain("Tronco de carvalho");
  });

  test("null identifier is handled", () => {
    const terms = makeTerms("en");
    expect(() => terms.blockTermMarkup(null)).not.toThrow();
  });
});

describe("createGameTerms — blockIcon", () => {
  test("returns SVG string", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("diamond_ore");
    expect(svg).toContain("<svg");
    expect(svg).toContain("block-icon");
  });

  test("diamond ore gets diamond icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("diamond_ore");
    expect(svg).toContain("block-icon-diamond");
  });

  test("water gets water icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("water");
    expect(svg).toContain("block-icon-water");
  });

  test("lava gets lava icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("lava");
    expect(svg).toContain("block-icon-lava");
  });

  test("ancient_debris gets ancient-debris icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("ancient_debris");
    expect(svg).toContain("block-icon-ancient-debris");
  });

  test("oak_log gets log icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("oak_log");
    expect(svg).toContain("block-icon-log");
  });

  test("glass gets glass icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("glass");
    expect(svg).toContain("block-icon-glass");
  });

  test("stone gets stone icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("stone");
    expect(svg).toContain("block-icon-stone");
  });

  test("unknown block gets unknown icon", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("furnace");
    expect(svg).toContain("block-icon-unknown");
  });

  test("with label adds role and aria-label", () => {
    const terms = makeTerms("en");
    const svg = terms.blockIcon("water", "water label");
    expect(svg).toContain('role="img"');
    expect(svg).toContain("water label");
  });
});

describe("createGameTerms — dimensionName", () => {
  test("overworld in en", () => {
    const terms = makeTerms("en");
    expect(terms.dimensionName("overworld")).toBe("Overworld");
  });

  test("the_end in en returns The End", () => {
    const terms = makeTerms("en");
    expect(terms.dimensionName("the_end")).toBe("The End");
  });

  test("the_end in pt returns O End", () => {
    const terms = makeTerms("pt");
    expect(terms.dimensionName("the_end")).toBe("O End");
  });

  test("the_end in es returns El End", () => {
    const terms = makeTerms("es");
    expect(terms.dimensionName("the_end")).toBe("El End");
  });

  test("nether in pt", () => {
    const terms = makeTerms("pt");
    expect(terms.dimensionName("nether")).toBe("Nether");
  });

  test("minecraft: prefix is stripped", () => {
    const terms = makeTerms("en");
    expect(terms.dimensionName("minecraft:the_end")).toBe("The End");
  });
});

describe("createGameTerms — gameLabel", () => {
  test("zombie in pt", () => {
    const terms = makeTerms("pt");
    expect(terms.gameLabel("zombie")).toBe("Zumbi");
  });

  test("zombie in en", () => {
    const terms = makeTerms("en");
    expect(terms.gameLabel("zombie")).toBe("Zombie");
  });

  test("zombie in es", () => {
    const terms = makeTerms("es");
    expect(terms.gameLabel("zombie")).toBe("Zombi");
  });

  test("cause fall in pt", () => {
    const terms = makeTerms("pt");
    expect(terms.gameLabel("fall", "cause")).toBe("Queda");
  });

  test("cause entityExplosion in en", () => {
    const terms = makeTerms("en");
    expect(terms.gameLabel("entityExplosion", "cause")).toBe("Entity explosion");
  });

  test("unknown entity is titlecased", () => {
    const terms = makeTerms("en");
    const label = terms.gameLabel("cave_spider");
    expect(label).toBe("Cave spider");
  });

  test("camelCase entity name is split", () => {
    const terms = makeTerms("en");
    const label = terms.gameLabel("someNewMob");
    expect(label.toLowerCase()).toContain("some");
  });
});

describe("createGameTerms — uiIcon", () => {
  test("returns SVG with icon name", () => {
    const terms = makeTerms("en");
    const svg = terms.uiIcon("home");
    expect(svg).toContain("cc-icon-home");
  });

  test("invalid name (with spaces) falls back to blocks", () => {
    const terms = makeTerms("en");
    const svg = terms.uiIcon("bad name!");
    expect(svg).toContain("cc-icon-blocks");
  });

  test("with label adds aria-label", () => {
    const terms = makeTerms("en");
    const svg = terms.uiIcon("home", "Go home");
    expect(svg).toContain("Go home");
    expect(svg).toContain('role="img"');
  });
});
