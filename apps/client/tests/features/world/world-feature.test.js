import { jest } from "@jest/globals";
import { createWorldFeature } from "../../../static/js/features/world/index.js";
import { createI18n } from "../../../static/js/i18n/index.js";
import { makeEl } from "../../helpers.js";

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
  const t = createI18n(() => state.locale).t;
  const uiIcon = (name) => `<svg icon="${name}"/>`;
  const booleanControl = jest.fn(() => `<div class="toggle-control"></div>`);
  const updateToggleLabel = jest.fn();
  const toast = jest.fn();
  const renderSettingsGroups = jest.fn();
  const renderTabs = jest.fn();
  const getSettingsFeature = () => ({ booleanControl, updateToggleLabel, renderSettingsGroups });
  const getNavigation = () => ({ renderTabs });
  const api = jest.fn().mockResolvedValue({});
  return { state, content, t, api, $, uiIcon, toast, getSettingsFeature, getNavigation, booleanControl, updateToggleLabel, renderSettingsGroups, renderTabs, elements, ...overrides };
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

  test.each([
    ["pt", "Desative para congelar o horário atual.", "Tempo e clima"],
    ["en", "Disable to freeze the current time.", "Time & weather"],
    ["es", "Desactiva para congelar la hora actual.", "Hora y clima"],
  ])("renders the time screen copy and heading in %s", (locale, cycleHelp, title) => {
    const deps = makeDeps({ state: { locale, gamerules: {} } });
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    expect(deps.content.innerHTML).toContain(cycleHelp);
    expect(deps.content.innerHTML).toContain('<header class="inner-heading">');
    expect(deps.content.innerHTML).toContain(title);
  });
});

describe("renderTimePanel — bindings", () => {
  let savedConfirm;
  beforeEach(() => { savedConfirm = global.confirm; });
  afterEach(() => { global.confirm = savedConfirm; });
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

  test("weather and time queries use translated values and safe fallbacks", async () => {
    const { deps, buttons } = makeSetup();
    deps.t = jest.fn((key) => key === "rain" ? "Rain" : key);
    deps.api = jest.fn()
      .mockResolvedValueOnce({ value: "rain" })
      .mockResolvedValueOnce({ value: undefined })
      .mockResolvedValueOnce({ value: "1200" });
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();

    await deps.elements["#weather-query"].onclick();
    await buttons[2].onclick();
    await buttons[2].onclick();

    expect(deps.elements["#time-query-result"].textContent).toContain("1200");
    expect(deps.api).toHaveBeenCalledWith("/api/time/weather-query", expect.anything());
    expect(deps.api).toHaveBeenCalledWith("/api/time/query", expect.anything());
    expect(deps.toast).not.toHaveBeenCalledWith("timeUpdated");
  });
});

describe("openTimeControls", () => {
  let _savedWindow;
  beforeEach(() => { _savedWindow = global.window; });
  afterEach(() => { global.window = _savedWindow; });

  test("sets state.tab, renders the time panel and scrolls to top", () => {
    const deps = makeDeps();
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const scrollTo = jest.fn();
    global.window = { history: { replaceState: jest.fn() }, location: { hash: "" }, scrollTo };
    const { openTimeControls } = createWorldFeature(deps);
    openTimeControls();
    expect(deps.state.tab).toBe("__time__");
    expect(deps.content.innerHTML).toContain("time-screen");
    // <main> owns the scroll in the mobile shell; the window is reset too, for
    // any layout where the document is what scrolls.
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "smooth" });
  });
});

describe("time screen carries its own context", () => {
  // The Home hero is hidden outside the Home tab, so without this panel the
  // screen would offer time controls with no reading of the current time.
  // The back affordance is not here: composition prepends one to every inner
  // screen, because this one has two entry points (Home and World).
  test("renders the day/time/weather panel wired to the shared world cells", () => {
    const deps = makeDeps({ state: { locale: "pt", gamerules: {} } });
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    expect(deps.content.innerHTML).toContain("time-world");
    expect(deps.content.innerHTML).toContain("grass-edge");
    expect(deps.content.innerHTML).toContain('data-world="day"');
    expect(deps.content.innerHTML).toContain('data-world="time"');
    expect(deps.content.innerHTML).toContain('data-world-cell="weather"');
  });

  test("asks composition to populate the shared cells after mounting", () => {
    const refreshWorldCells = jest.fn();
    const deps = makeDeps({ state: { locale: "en", gamerules: {} } });
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn(() => makeEl());
    const { renderTimePanel } = createWorldFeature({ ...deps, refreshWorldCells });
    renderTimePanel();
    expect(refreshWorldCells).toHaveBeenCalled();
  });
});

describe("renderTimePanel — remaining control paths", () => {
  function setup(stateOverrides = {}) {
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

  test("setting an exact time sends the field value", async () => {
    const { deps } = setup();
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    deps.$("#exact-time").value = "6000";
    await deps.elements["#set-exact-time"].onclick();
    expect(deps.api).toHaveBeenCalledWith("/api/time/set", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(deps.api.mock.calls.at(-1)[1].body)).toEqual({ value: "6000" });
  });

  test("advancing time sends the field value", async () => {
    const { deps } = setup();
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    deps.$("#add-time").value = "1000";
    await deps.elements["#add-time-button"].onclick();
    expect(JSON.parse(deps.api.mock.calls.at(-1)[1].body)).toEqual({ value: "1000" });
  });

  test("a weather button sends the type and the duration together", async () => {
    const { deps, buttons } = setup();
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    deps.$("#weather-duration").value = "600";
    const weatherButton = buttons.find((b) => b.dataset.weather);
    await weatherButton.onclick();
    expect(JSON.parse(deps.api.mock.calls.at(-1)[1].body)).toEqual({ value: "rain", duration: "600" });
  });

  test("a failing weather command surfaces the error", async () => {
    const { deps, buttons } = setup();
    deps.api = jest.fn().mockRejectedValue(new Error("no connection"));
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await buttons.find((b) => b.dataset.weather).onclick();
    expect(deps.toast).toHaveBeenCalledWith("no connection", true);
  });

  test("the weather query writes the translated result", async () => {
    const { deps } = setup();
    deps.api = jest.fn().mockResolvedValue({ value: "rain" });
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await deps.elements["#weather-query"].onclick();
    expect(deps.elements["#time-query-result"].textContent).toContain("Rain");
  });

  test("a failing weather query surfaces the error", async () => {
    const { deps } = setup();
    deps.api = jest.fn().mockRejectedValue(new Error("timeout"));
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await deps.elements["#weather-query"].onclick();
    expect(deps.toast).toHaveBeenCalledWith("timeout", true);
  });

  test("a time query falls back when the server reports no value", async () => {
    const { deps, buttons } = setup();
    deps.api = jest.fn().mockResolvedValue({});
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await buttons.find((b) => b.dataset.timeQuery).onclick();
    expect(deps.elements["#time-query-result"].textContent).toContain("The server did not return a readable value.");
  });

  test("a failing time query surfaces the error", async () => {
    const { deps, buttons } = setup();
    deps.api = jest.fn().mockRejectedValue(new Error("offline"));
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await buttons.find((b) => b.dataset.timeQuery).onclick();
    expect(deps.toast).toHaveBeenCalledWith("offline", true);
  });

  test("a gamerule toggle rolls back and warns when the request fails", async () => {
    const { deps } = setup();
    deps.api = jest.fn().mockRejectedValue(new Error("rejected"));
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await deps.elements["#time-daylight-cycle"].onchange({ target: { checked: true } });
    expect(deps.toast).toHaveBeenCalledWith("rejected", true);
  });

  test("an active operation locks the gamerule toggles", async () => {
    const { deps } = setup({ operationActive: true });
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await deps.elements["#time-weather-cycle"].onchange({ target: { checked: false } });
    expect(deps.toast).toHaveBeenCalledWith("Changes are locked while a server operation is in progress.", true);
    expect(deps.api).not.toHaveBeenCalled();
  });

  test("an active operation blocks mutating commands", async () => {
    const { deps, buttons } = setup({ operationActive: true });
    const { renderTimePanel } = createWorldFeature(deps);
    renderTimePanel();
    await buttons.find((b) => b.dataset.timePreset).onclick();
    expect(deps.toast).toHaveBeenCalledWith("Changes are locked while a server operation is in progress.", true);
    expect(deps.api).not.toHaveBeenCalled();
  });
});
