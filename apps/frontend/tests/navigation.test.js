import { jest } from "@jest/globals";
import { createNavigation } from "../static/js/core/navigation.js";

// navigation.js calls window.scrollTo; route.js uses window.history/location — stub for node env
if (typeof global.window === "undefined") {
  global.window = {};
}
global.window.scrollTo = jest.fn();
global.window.history = { replaceState: jest.fn() };
global.window.location = { hash: "" };

function makeButton(tab) {
  const btn = { dataset: { tab }, onclick: null, className: "" };
  btn.click = () => btn.onclick && btn.onclick();
  return btn;
}

function makeTabsElement() {
  const buttons = [];
  const el = {
    get innerHTML() { return ""; },
    set innerHTML(html) {
      el._html = html;
      el._buttons = [];
    },
    _buttons: buttons,
    querySelectorAll: (sel) => {
      if (sel === "button") return el._buttons;
      return [];
    },
  };
  return el;
}

function makeEnv(initialTab = "home") {
  const state = {
    tab: initialTab,
    tabs: ["home", "world", "players", "analytics", "rules", "server"],
  };
  const tabsEl = makeTabsElement();
  const $ = (sel) => sel === "#tabs" ? tabsEl : null;
  const t = (key) => key;
  const uiIcon = (name) => name;
  const render = jest.fn();
  return { state, $, t, uiIcon, render, tabsEl };
}

describe("createNavigation — renderTabs", () => {
  test("sets innerHTML on #tabs element", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    expect(typeof tabsEl._html).toBe("string");
    expect(tabsEl._html.length).toBeGreaterThan(0);
  });

  test("generated html contains all 6 tabs", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    for (const tab of ["home", "world", "players", "analytics", "rules", "server"]) {
      expect(tabsEl._html).toContain(`data-tab="${tab}"`);
    }
  });

  test("active tab gets active class in html", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("world");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    expect(tabsEl._html).toContain('<button class="active" data-tab="world"');
  });

  test("__players__ state marks players button active", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("__players__");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    const activeIdx = tabsEl._html.indexOf('class="active"');
    const playersIdx = tabsEl._html.indexOf('data-tab="players"');
    expect(activeIdx).toBeGreaterThanOrEqual(0);
    expect(Math.abs(activeIdx - playersIdx)).toBeLessThan(60);
  });

  test("server button uses settings translation key", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    expect(tabsEl._html).toContain("settings");
  });

  test("clicking players button sets tab to __players__", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const playersBtn = makeButton("players");
    tabsEl.querySelectorAll = (sel) => sel === "button" ? [playersBtn] : [];
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    playersBtn.click();
    expect(state.tab).toBe("__players__");
  });

  test("clicking non-players button sets tab to button value", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const worldBtn = makeButton("world");
    tabsEl.querySelectorAll = (sel) => sel === "button" ? [worldBtn] : [];
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    worldBtn.click();
    expect(state.tab).toBe("world");
  });

  test("clicking a tab calls render", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const btn = makeButton("world");
    tabsEl.querySelectorAll = (sel) => sel === "button" ? [btn] : [];
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    btn.click();
    expect(render).toHaveBeenCalled();
  });
});

describe("createNavigation — openPlayers", () => {
  test("sets tab to __players__", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    tabsEl.querySelectorAll = () => [];
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    nav.openPlayers();
    expect(state.tab).toBe("__players__");
  });

  test("calls render", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    tabsEl.querySelectorAll = () => [];
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    render.mockClear();
    nav.openPlayers();
    expect(render).toHaveBeenCalled();
  });
});
