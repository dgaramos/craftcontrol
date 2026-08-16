import { jest } from "@jest/globals";
import { createAnalyticsFeature } from "../static/js/features/analytics/index.js";
import { makeEl } from "./helpers.js";

function makeAnalyticsDeps(kindOverride = "rankings") {
  const elements = {};
  const $ = jest.fn((sel) => {
    if (!elements[sel]) elements[sel] = makeEl();
    return elements[sel];
  });

  const state = {
    locale: "en",
    analytics: {
      kind: kindOverride,
      player: "",
      source: "all",
      search: "",
      days: 0,
      page: 1,
      rankingCategory: "activity",
      rankingMetric: "play_time",
      blocksMode: "mining",
      selectedOre: "diamond",
      combatMetric: "mob_kills",
      explorationMetric: "distance",
      periodDays: 30,
      periodMetric: "play_seconds",
    },
  };
  const content = { innerHTML: "", querySelectorAll: jest.fn(() => []) };
  const t = (key) => key;
  const escapeHtml = (s) => String(s ?? "").replace(/</g, "&lt;");
  const uiIcon = (name) => `<svg icon="${name}"/>`;
  const optionLabel = (v) => v;
  const gameTermMarkup = (v) => `<span>${escapeHtml(String(v))}</span>`;
  const timelineTimestamp = (ts) => ts ? `<time>${ts}</time>` : "<span>—</span>";
  const rankingDefinitions = {
    play_time: { category: "activity", label: "rankPlayTime", format: "duration" },
    sessions: { category: "activity", label: "rankSessions", format: "number" },
  };
  const formatRankingValue = (v) => String(v ?? 0);
  const formatDate = (ts) => ts ? "2024-01-01" : "—";
  const formatDuration = (s) => `${s}s`;
  const blockTermMarkup = (v) => `<span>${v}</span>`;
  const blockIcon = (v) => `<svg block="${v}"/>`;
  const oreLabel = (v) => v;
  const dimensionName = (v) => String(v);
  const localeTag = () => "en-US";
  const api = jest.fn().mockRejectedValue(new Error("no api"));
  const openAnalyticsPlayer = jest.fn();
  const requestRender = jest.fn();

  return { state, content, t, escapeHtml, uiIcon, optionLabel, gameTermMarkup, timelineTimestamp, rankingDefinitions, formatRankingValue, formatDate, formatDuration, blockTermMarkup, blockIcon, oreLabel, dimensionName, localeTag, api, openAnalyticsPlayer, requestRender, $ };
}

describe("createAnalyticsFeature — factory setup", () => {
  test("returns a render function", () => {
    const deps = makeAnalyticsDeps();
    const feature = createAnalyticsFeature(deps);
    expect(typeof feature.render).toBe("function");
  });

  test("analyticsViewSwitch called during render sets content", async () => {
    const deps = makeAnalyticsDeps("all");
    // api returns empty results to avoid full DOM wiring
    deps.api = jest.fn().mockResolvedValue({ events: [], pages: 1, page: 1, total: 0, summary: {}, players: [] });
    deps.$ = jest.fn((sel) => {
      const el = makeEl({ value: "all" });
      return el;
    });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain("analytics-screen");
  });

  test("render delegates to renderRankingsPanel for rankings kind", async () => {
    const deps = makeAnalyticsDeps("rankings");
    deps.api = jest.fn().mockResolvedValue({ metrics: { play_time: [{ player: { id: "1", name: "P" }, value: 100, source: "server" }] }, generated_at: 0 });
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain("rankings-screen");
  });

  test("render delegates to renderBlocksPanel for blocks kind", async () => {
    const deps = makeAnalyticsDeps("blocks");
    deps.api = jest.fn().mockResolvedValue({
      ores: { diamond: 5 },
      rankings: { miners: [], builders: [], ores: {} },
      top_broken: [],
      top_placed: [],
      players: [],
      totals: { broken: 10, placed: 5 },
      generated_at: 0,
    });
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain("blocks-screen");
  });

  test("render with kind=combat falls through to renderCombatPanel", async () => {
    const deps = makeAnalyticsDeps("combat");
    deps.api = jest.fn().mockRejectedValue(new Error("api error"));
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await expect(render()).resolves.toBeUndefined();
  });

  test("render with kind=exploration falls through", async () => {
    const deps = makeAnalyticsDeps("exploration");
    deps.api = jest.fn().mockRejectedValue(new Error("api error"));
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await expect(render()).resolves.toBeUndefined();
  });

  test("render with kind=trends falls through", async () => {
    const deps = makeAnalyticsDeps("trends");
    deps.api = jest.fn().mockRejectedValue(new Error("api error"));
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await expect(render()).resolves.toBeUndefined();
  });
});
