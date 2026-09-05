import { jest } from "@jest/globals";
import { createHomeFeature } from "../../../static/js/features/home/index.js";
import { makeEl } from "../../helpers.js";

function makeDeps(overrides = {}) {
  const buttons = {
    modes: [makeEl({ dataset: { homeGamemode: "creative" } })],
    tabs: [makeEl({ dataset: { homeTab: "rules" } })],
  };
  const content = {
    innerHTML: "",
    querySelectorAll(selector) {
      if (selector === "[data-home-gamemode]") return buttons.modes;
      if (selector === "[data-home-tab]") return buttons.tabs;
      return [];
    },
  };
  const state = { config: { GAMEMODE: "survival" }, changes: {}, ...overrides.state };
  const getSettingsFeature = () => ({ updateSaveLabel: overrides.updateSaveLabel || (() => {}) });
  return { state, content, t: (key) => key, getSettingsFeature, buttons };
}

describe("createHomeFeature", () => {
  test("renders game-mode controls and the three dashboard shortcuts", () => {
    const deps = makeDeps();
    createHomeFeature(deps).render();

    expect(deps.content.innerHTML).toContain('data-home-gamemode="survival"');
    expect(deps.content.innerHTML).toContain('data-home-gamemode="creative"');
    expect(deps.content.innerHTML).toContain('data-home-tab="rules"');
    expect(deps.content.innerHTML).toContain('data-home-tab="server"');
    expect(deps.content.innerHTML).toContain('data-home-tab="audit"');
  });

  test("stages a selected game mode for the existing review flow", () => {
    const updateSaveLabel = jest.fn();
    const deps = makeDeps({ updateSaveLabel });
    createHomeFeature(deps).render();

    deps.buttons.modes[0].onclick();

    expect(deps.state.changes).toEqual({ GAMEMODE: "creative" });
    expect(updateSaveLabel).toHaveBeenCalled();
  });

  test("shortcut changes the active tab", () => {
    const deps = makeDeps();
    createHomeFeature(deps).render();

    deps.buttons.tabs[0].onclick();

    expect(deps.state.tab).toBe("rules");
  });
});
