import { jest } from "@jest/globals";
import { createWorldFeature } from "../static/js/features/world/index.js";
import { makeEl } from "./helpers.js";

function makeDeps(overrides = {}) {
  const elements = {};
  const $ = jest.fn((sel) => {
    if (!elements[sel]) elements[sel] = makeEl();
    return elements[sel];
  });
  const state = {
    locale: "en",
    tab: "world",
    gamerules: { dodaylightcycle: "true", doweathercycle: "true" },
    ...overrides.state,
  };
  const content = {
    innerHTML: "",
    querySelectorAll: jest.fn(() => []),
  };
  const t = (key) => key;
  const uiIcon = (name) => `<svg icon="${name}"/>`;
  const booleanControl = jest.fn(() => `<div class="toggle-control"></div>`);
  const updateToggleLabel = jest.fn();
  const toast = jest.fn();
  const renderSettingsGroups = jest.fn();
  const renderTabs = jest.fn();
  const api = jest.fn().mockResolvedValue({});
  return { state, content, t, api, $, uiIcon, booleanControl, updateToggleLabel, toast, renderSettingsGroups, renderTabs, elements, ...overrides };
}

describe("createWorldFeature — factory", () => {
  test("returns renderWorld, renderTimePanel, openTimeControls", () => {
    const { renderWorld, renderTimePanel, openTimeControls } = createWorldFeature(makeDeps());
    expect(typeof renderWorld).toBe("function");
    expect(typeof renderTimePanel).toBe("function");
    expect(typeof openTimeControls).toBe("function");
  });
});

describe("renderWorld", () => {
  test("calls renderSettingsGroups with ['Geral', 'Mundo']", () => {
    const deps = makeDeps();
    const { renderWorld } = createWorldFeature(deps);
    renderWorld();
    expect(deps.renderSettingsGroups).toHaveBeenCalledWith(["Geral", "Mundo"], expect.any(String));
  });

  test("sets #open-time onclick to openTimeControls", () => {
    const deps = makeDeps();
    const { renderWorld, openTimeControls } = createWorldFeature(deps);
    renderWorld();
    // The onclick is set after renderSettingsGroups, on the #open-time element
    expect(deps.$).toHaveBeenCalledWith("#open-time");
    const el = deps.elements["#open-time"];
    expect(typeof el.onclick).toBe("function");
  });
});

describe("renderTimePanel", () => {
  test("sets content.innerHTML with time-screen markup", () => {
    const deps = makeDeps();
    const { renderTimePanel } = createWorldFeature(deps);
    // Need querySelectorAll to return arrays to avoid forEach errors
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    renderTimePanel();
    expect(deps.content.innerHTML).toContain("time-screen");
  });

  test("HTML contains all six preset buttons", () => {
    const deps = makeDeps();
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    const presets = ["sunrise", "day", "noon", "sunset", "night", "midnight"];
    presets.forEach((preset) => {
      expect(deps.content.innerHTML).toContain(`data-time-preset="${preset}"`);
    });
  });

  test("HTML contains weather buttons", () => {
    const deps = makeDeps();
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    expect(deps.content.innerHTML).toContain('data-weather="clear"');
    expect(deps.content.innerHTML).toContain('data-weather="rain"');
    expect(deps.content.innerHTML).toContain('data-weather="thunder"');
  });

  test("HTML contains time query buttons", () => {
    const deps = makeDeps();
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    expect(deps.content.innerHTML).toContain("data-time-query");
  });

  test("PT locale renders Portuguese text", () => {
    const deps = makeDeps({ state: { locale: "pt", gamerules: {} } });
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    expect(deps.content.innerHTML).toContain("Escolha um momento predefinido");
  });
});

describe("renderTimePanel — bindings", () => {
  function makeSetup(stateOverrides = {}) {
    const deps = makeDeps({ state: { locale: "en", gamerules: { dodaylightcycle: "true", doweathercycle: "true" }, ...stateOverrides } });
    const buttons = [];
    deps.content.querySelectorAll = jest.fn((sel) => {
      if (sel === "[data-time-preset]" || sel === "[data-weather]" || sel === "[data-time-query]") {
        const btn = makeEl({ dataset: sel.includes("preset") ? { timePreset: "day" } : sel.includes("weather") ? { weather: "rain" } : { timeQuery: "daytime" } });
        buttons.push(btn);
        return [btn];
      }
      return [];
    });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    return { deps, buttons };
  }

  test("preset button onclick calls api /api/time/preset", async () => {
    const { deps, buttons } = makeSetup();
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await buttons[0].onclick();
    expect(deps.api).toHaveBeenCalledWith("/api/time/preset", expect.objectContaining({ method: "POST" }));
  });

  test("preset button onclick calls toast on api error", async () => {
    const { deps, buttons } = makeSetup();
    deps.api = jest.fn().mockRejectedValue(new Error("timeout"));
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await buttons[0].onclick();
    expect(deps.toast).toHaveBeenCalledWith("timeout", true);
  });

  test("gamerule toggle onchange calls api /api/gamerules/dodaylightcycle", async () => {
    const { deps } = makeSetup();
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    const toggle = deps.elements["#time-daylight-cycle"];
    const fakeEl = { checked: true };
    await toggle.onchange({ target: fakeEl });
    expect(deps.api).toHaveBeenCalledWith(
      "/api/gamerules/dodaylightcycle",
      expect.objectContaining({ method: "PUT" })
    );
  });

  test("#reset-days with confirm=false does nothing", async () => {
    const { deps } = makeSetup();
    global.confirm = jest.fn(() => false);
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await deps.elements["#reset-days"].onclick();
    expect(deps.api).not.toHaveBeenCalledWith(expect.stringContaining("reset-days"), expect.anything());
  });

  test("#reset-days with confirm=true calls api /api/time/reset-days", async () => {
    const { deps } = makeSetup();
    global.confirm = jest.fn(() => true);
    deps.api = jest.fn().mockResolvedValue({});
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await deps.elements["#reset-days"].onclick();
    expect(deps.api).toHaveBeenCalledWith("/api/time/reset-days", expect.anything());
  });
});

describe("openTimeControls", () => {
  test("sets state.tab, calls renderTabs, renders time panel markup, and scrolls to top", () => {
    const deps = makeDeps();
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const scrollTo = jest.fn();
    global.window = { history: { replaceState: jest.fn() }, location: { hash: "" }, scrollTo };
    const { openTimeControls } = createWorldFeature(deps);
    openTimeControls();
    expect(deps.state.tab).toBe("__time__");
    expect(deps.renderTabs).toHaveBeenCalled();
    expect(deps.content.innerHTML).toContain("time-screen");
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });
});
