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
    playerDataMarkup: jest.fn(() => ""), profileMarkup: jest.fn(() => ""),
    panelAccessDetailMarkup: jest.fn(() => ""), renderPlayersPanel: jest.fn(), renderAnalyticsPanel: jest.fn(),
    toast: jest.fn(), bindPlayerAccess: jest.fn(),
    getSettingsFeature: () => ({ booleanControl: jest.fn(() => ""), updateToggleLabel: jest.fn() }),
    getNavigation: () => ({ renderTabs: jest.fn() }),
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

  test("rejects a profile without history", async () => {
    const deps = makeDeps();
    deps.api.mockResolvedValueOnce({ profile: { name: "Alice" } });
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    expect(deps.content.innerHTML).toContain("historyUnavailable");
  });

  test("handles an offline operator update failure", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce({ profile: { name: "Alice", history: [], online: false, operator: true } })
      .mockRejectedValueOnce(new Error("operator unavailable"));
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    await deps.elements["#detail-operator"].onchange({ target: { checked: false } });
    expect(deps.toast).toHaveBeenCalledWith("operator unavailable", true);
  });

  test("renders a profile without an operator control", async () => {
    const deps = makeDeps();
    deps.$ = jest.fn((selector) => selector === "#detail-operator" ? null : deps.elements[selector] ||= makeEl());
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    expect(deps.content.innerHTML).toContain("player-detail-screen");
  });

  test("shows FORCE_GAMEMODE notice and wires settings link when forceGameMode is true", async () => {
    const deps = makeDeps();
    deps.state.server = { settings: { FORCE_GAMEMODE: "true" } };
    const forceNotice = makeEl();
    forceNotice.hidden = true;
    const settingsLink = makeEl();
    deps.elements["#detail-gamemode-force-notice"] = forceNotice;
    deps.$ = jest.fn((selector) => {
      if (selector === "#detail-gamemode-force-notice") return forceNotice;
      if (selector === "#detail-gamemode-settings-link") return settingsLink;
      return deps.elements[selector] ||= makeEl();
    });
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    expect(forceNotice.hidden).toBe(false);
    settingsLink.onclick();
    expect(deps.state.tab).toBe("settings");
  });

  test("apply game mode button calls API and shows toast on success", async () => {
    const deps = makeDeps();
    const applyBtn = makeEl();
    const modeSelect = { value: "creative" };
    deps.elements["#detail-gamemode-apply"] = applyBtn;
    deps.elements["#detail-gamemode-select"] = modeSelect;
    deps.api = jest.fn()
      .mockResolvedValueOnce({ profile: { name: "Alice", history: [], online: true, connected_at: 100, operator: false } })
      .mockResolvedValueOnce({ ok: true });
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    await applyBtn.onclick();
    expect(deps.api).toHaveBeenCalledWith(
      "/api/players/Alice/gamemode",
      expect.objectContaining({ method: "PUT" })
    );
    expect(deps.toast).toHaveBeenCalledWith("gameModeUpdated");
    expect(applyBtn.disabled).toBe(false);
  });

  test("apply game mode button shows error toast on API failure", async () => {
    const deps = makeDeps();
    const applyBtn = makeEl();
    const modeSelect = { value: "survival" };
    deps.elements["#detail-gamemode-apply"] = applyBtn;
    deps.elements["#detail-gamemode-select"] = modeSelect;
    deps.api = jest.fn()
      .mockResolvedValueOnce({ profile: { name: "Alice", history: [], online: true, connected_at: 100, operator: false } })
      .mockRejectedValueOnce(new Error("server error"));
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    await applyBtn.onclick();
    expect(deps.toast).toHaveBeenCalledWith("server error", true);
    expect(applyBtn.disabled).toBe(false);
  });

  test("pre-selects game mode from profile.game_mode when valid", async () => {
    const deps = makeDeps();
    const modeSelect = makeEl();
    deps.api = jest.fn().mockResolvedValue({ profile: { name: "Alice", history: [], online: true, connected_at: 100, operator: false, game_mode: "creative" } });
    deps.$ = jest.fn((selector) => {
      if (selector === "#detail-gamemode-select") return modeSelect;
      return deps.elements[selector] ||= makeEl();
    });
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    expect(modeSelect.value).toBe("creative");
  });

  test("does not pre-select game mode when profile.game_mode is invalid", async () => {
    const deps = makeDeps();
    const modeSelect = makeEl();
    deps.api = jest.fn().mockResolvedValue({ profile: { name: "Alice", history: [], online: true, connected_at: 100, operator: false, game_mode: "spectator" } });
    deps.$ = jest.fn((selector) => {
      if (selector === "#detail-gamemode-select") return modeSelect;
      return deps.elements[selector] ||= makeEl();
    });
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    expect(modeSelect.value).toBe("");
  });

  test("apply game mode button does nothing when select is missing", async () => {
    const deps = makeDeps();
    const applyBtn = makeEl();
    deps.elements["#detail-gamemode-apply"] = applyBtn;
    deps.$ = jest.fn((selector) => {
      if (selector === "#detail-gamemode-select") return null;
      return deps.elements[selector] ||= makeEl();
    });
    deps.api = jest.fn().mockResolvedValue({ profile: { name: "Alice", history: [], online: true, connected_at: 100, operator: false } });
    await createPlayerProfile(deps)({ id: "player-1" }, {});
    await applyBtn.onclick();
    expect(deps.api).toHaveBeenCalledTimes(1);
  });
});
