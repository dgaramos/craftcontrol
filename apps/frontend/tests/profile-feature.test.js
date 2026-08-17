import { jest } from "@jest/globals";
import { createPlayerProfile } from "../static/js/features/players/profile.js";
import { makeEl } from "./helpers.js";

function makeDeps() {
  const elements = {};
  const state = { locale: "en", analytics: {}, tab: "players" };
  const $ = jest.fn((selector) => elements[selector] ||= makeEl());
  const content = { renderedMarkup: "", replaceChildren(...children) { this.children = children; this.renderedMarkup = children.filter((child) => typeof child === "string").join(""); }, querySelectorAll: jest.fn(() => []) };
  Object.defineProperty(content, "innerHTML", { get: () => content.renderedMarkup, set: (value) => { content.renderedMarkup = String(value); } });
  const api = jest.fn().mockResolvedValue({ profile: { name: "Alice", history: [], online: true, connected_at: 100, operator: false } });
  return {
    state, content, $, api, elements,
    t: (key) => key, localized: (pt, en) => en, escapeHtml: (value) => String(value),
    formatDate: () => "2024-01-01", formatDuration: (value) => `${value}s`,
    playerDataMarkup: jest.fn(() => ""), profileMarkup: jest.fn(() => ""), booleanControl: jest.fn(() => ""),
    panelAccessDetailMarkup: jest.fn(() => ""), renderPlayersPanel: jest.fn(), renderAnalyticsPanel: jest.fn(),
    renderTabs: jest.fn(), updateToggleLabel: jest.fn(), toast: jest.fn(), bindPlayerAccess: jest.fn(),
  };
}

describe("createPlayerProfile", () => {
  test("renders a profile and wires navigation", async () => {
    const deps = makeDeps();
    const back = jest.fn();
    await createPlayerProfile(deps)({ id: "player-1" }, { role: "owner" }, back);
    expect(deps.content.innerHTML).toContain("player-detail-screen");
    expect(deps.elements["#back-to-players"].onclick).toBe(back);
    const previousWindow = globalThis.window;
    globalThis.window = { history: { replaceState: jest.fn() }, location: { hash: "" } };
    try {
      deps.elements["#compare-player-data"].onclick();
      expect(deps.state.tab).toBe("analytics");
      expect(deps.state.analytics.player).toBe("Alice");
    } finally {
      globalThis.window = previousWindow;
    }
  });

  test("shows an API error", async () => {
    const deps = makeDeps();
    deps.api.mockRejectedValueOnce(new Error("profile unavailable"));
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    expect(deps.content.innerHTML).toContain("profile unavailable");
  });
});
