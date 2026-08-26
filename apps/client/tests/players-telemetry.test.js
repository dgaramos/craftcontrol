import { createPlayerTelemetry } from "../static/js/features/players/telemetry.js";

function makeDeps(locale = "en") {
  const state = { locale };
  const t = (key) => key;
  const escapeHtml = (s) => String(s).replace(/</g, "&lt;");
  const gameTermMarkup = (v) => `<span>${escapeHtml(String(v))}</span>`;
  const blockTermMarkup = (v) => `<span>${escapeHtml(String(v))}</span>`;
  const dimensionName = (v) => String(v);
  const formatRankingValue = (v) => String(v);
  const uiIcon = (name) => `<svg data-icon="${name}"/>`;
  const gameIcon = (v) => `<svg data-mob="${v}"/>`;
  const formatDate = (ts) => ts ? "2024-01-01" : "—";
  return { state, t, escapeHtml, gameTermMarkup, blockTermMarkup, dimensionName, formatRankingValue, uiIcon, gameIcon, formatDate };
}

describe("sortedTelemetryEntries", () => {
  const { sortedTelemetryEntries } = createPlayerTelemetry(makeDeps());

  test("returns empty array for null", () => expect(sortedTelemetryEntries(null)).toEqual([]));
  test("returns empty array for array input", () => expect(sortedTelemetryEntries([])).toEqual([]));
  test("returns empty array for non-object", () => expect(sortedTelemetryEntries("str")).toEqual([]));
  test("filters out zero-count entries", () => {
    const result = sortedTelemetryEntries({ diamond: 5, coal: 0 });
    expect(result).toHaveLength(1);
    expect(result[0][0]).toBe("diamond");
  });
  test("sorts by count descending", () => {
    const result = sortedTelemetryEntries({ coal: 2, diamond: 10, iron: 5 });
    expect(result[0][0]).toBe("diamond");
    expect(result[1][0]).toBe("iron");
    expect(result[2][0]).toBe("coal");
  });
  test("respects limit parameter", () => {
    const data = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`block_${i}`, i + 1]));
    expect(sortedTelemetryEntries(data, 5)).toHaveLength(5);
  });
  test("defaults to limit 12", () => {
    const data = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`block_${i}`, i + 1]));
    expect(sortedTelemetryEntries(data)).toHaveLength(12);
  });
  test("ties are broken by key alphabetically", () => {
    const result = sortedTelemetryEntries({ b: 5, a: 5 });
    expect(result[0][0]).toBe("a");
    expect(result[1][0]).toBe("b");
  });
});

describe("playerBreakdownMarkup", () => {
  const { playerBreakdownMarkup } = createPlayerTelemetry(makeDeps());

  test("returns empty message for no entries", () =>
    expect(playerBreakdownMarkup([], "entity", "Nothing")).toContain("Nothing"));

  test("renders entity entries", () => {
    const html = playerBreakdownMarkup([["zombie", 5]], "entity", "empty");
    expect(html).toContain("player-data-ranking");
    expect(html).toContain("zombie");
  });

  test("renders block entries", () => {
    const html = playerBreakdownMarkup([["diamond_ore", 3]], "block", "empty");
    expect(html).toContain("diamond_ore");
  });

  test("renders dimension entries", () => {
    const html = playerBreakdownMarkup([["overworld", 10]], "dimension", "empty");
    expect(html).toContain("overworld");
  });

  test("shows rank numbers", () => {
    const html = playerBreakdownMarkup([["a", 10], ["b", 5]], "entity", "empty");
    expect(html).toContain("<b>1</b>");
    expect(html).toContain("<b>2</b>");
  });
});

describe("playerDataMarkup", () => {
  test("returns waiting message when no telemetry_updated_at", () => {
    const { playerDataMarkup } = createPlayerTelemetry(makeDeps());
    const html = playerDataMarkup({ name: "P", telemetry_updated_at: null, telemetry: {} });
    expect(html).toContain("telemetryWaiting");
  });

  test("renders full stats when telemetry_updated_at set", () => {
    const { playerDataMarkup } = createPlayerTelemetry(makeDeps());
    const profile = {
      name: "Hero",
      telemetry_updated_at: 1700000000,
      telemetry: {
        playerKills: 1, mobKills: 2, blocksBroken: 3, blocksPlaced: 4,
        damageDealt: 5.5, damageTaken: 3.2, distance: 100,
        dimensions: { overworld: 5 },
        killsByType: { zombie: 2 },
        brokenByType: { diamond_ore: 1 },
        placedByType: { oak_planks: 3 },
      },
    };
    const html = playerDataMarkup(profile);
    expect(html).toContain("player-data-workspace");
    expect(html).toContain("Hero");
  });

  test("handles missing telemetry fields gracefully", () => {
    const { playerDataMarkup } = createPlayerTelemetry(makeDeps());
    const profile = { name: "X", telemetry_updated_at: 1700000000, telemetry: {} };
    expect(() => playerDataMarkup(profile)).not.toThrow();
  });

  test("pt locale uses pt labels", () => {
    const { playerDataMarkup } = createPlayerTelemetry(makeDeps("pt"));
    const profile = { name: "Herói", telemetry_updated_at: 1700000000, telemetry: {} };
    const html = playerDataMarkup(profile);
    expect(html).toContain("Herói");
  });
});
