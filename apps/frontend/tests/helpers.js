import { jest } from "@jest/globals";

export function makeEl(extra = {}) {
  return {
    innerHTML: "",
    textContent: "",
    hidden: false,
    value: "",
    checked: false,
    open: false,
    onchange: null,
    onclick: null,
    oninput: null,
    className: "",
    dataset: {},
    close: jest.fn(),
    showModal: jest.fn(),
    addEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
    querySelector: jest.fn(() => null),
    querySelectorAll: jest.fn(() => []),
    closest: jest.fn(() => null),
    classList: { add: jest.fn(), remove: jest.fn(), toggle: jest.fn() },
    ...extra,
  };
}

export function makeAnalyticsDeps(stateOverrides = {}) {
  const elements = {};
  const $ = jest.fn((sel) => {
    if (!elements[sel]) elements[sel] = makeEl();
    return elements[sel];
  });
  const state = {
    locale: "en",
    analytics: {
      kind: "rankings",
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
      ...stateOverrides,
    },
  };
  const content = { innerHTML: "", querySelectorAll: jest.fn(() => []) };
  const t = (key, ...args) => (args.length ? `${key}(${args.join(",")})` : key);
  const escapeHtml = (s) => String(s ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]);
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
  const formatDuration = (s) => `${s ?? 0}s`;
  const blockTermMarkup = (v) => `<span>${v}</span>`;
  const blockIcon = (v) => `<svg block="${v}"/>`;
  const oreLabel = (v) => v;
  const dimensionName = (v) => String(v);
  const localeTag = () => "en-US";
  const api = jest.fn().mockRejectedValue(new Error("no api"));
  const openAnalyticsPlayer = jest.fn();
  const requestRender = jest.fn();

  return {
    state, content, t, escapeHtml, uiIcon, optionLabel, gameTermMarkup,
    timelineTimestamp, rankingDefinitions, formatRankingValue, formatDate,
    formatDuration, blockTermMarkup, blockIcon, oreLabel, dimensionName,
    localeTag, api, openAnalyticsPlayer, requestRender, $, elements,
  };
}
