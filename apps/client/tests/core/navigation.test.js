import { jest } from "@jest/globals";
import { createNavigation } from "../../static/js/core/navigation.js";

let _savedWindow;
beforeEach(() => {
  _savedWindow = global.window;
  if (typeof global.window === "undefined") {
    global.window = {};
  }
  global.window.scrollTo = jest.fn();
  global.window.history = { replaceState: jest.fn() };
  global.window.location = { hash: "" };
});
afterEach(() => { global.window = _savedWindow; });

// ── Stubs ─────────────────────────────────────────────────────────────────────

function makeFakeNavTabButton(tab) {
  const iEl = { innerHTML: "" };
  const spanEl = { textContent: "" };
  return {
    dataset: { tab },
    onclick: null,
    className: "",
    click() { if (this.onclick) this.onclick(); },
    querySelector(sel) {
      if (sel === "i") return iEl;
      if (sel === "span") return spanEl;
      return null;
    },
  };
}

function makeFakeNavTabTemplate() {
  return {
    content: {
      cloneNode() {
        const btn = makeFakeNavTabButton("");
        return {
          _button: btn,
          querySelector: (sel) => (sel === "button" ? btn : null),
        };
      },
    },
  };
}

function makeTabsElement() {
  const buttons = [];
  const replaceChildren = jest.fn(() => { buttons.length = 0; });
  return {
    _buttons: buttons,
    replaceChildren,
    appendChild(fragment) { if (fragment._button) buttons.push(fragment._button); },
    querySelectorAll(sel) { return sel === "button" ? buttons : []; },
  };
}

function makeEnv(initialTab = "home") {
  const state = {
    tab: initialTab,
    tabs: ["home", "world", "players", "analytics", "rules", "server"],
  };
  const tabsEl = makeTabsElement();
  const tplNavTab = makeFakeNavTabTemplate();
  const $ = (sel) => {
    if (sel === "#tabs") return tabsEl;
    if (sel === "#tpl-nav-tab") return tplNavTab;
    return null;
  };
  const t = (key) => key;
  const uiIcon = (name) => name;
  return { state, $, t, uiIcon, tabsEl };
}

// ── renderTabs ────────────────────────────────────────────────────────────────

describe("createNavigation — renderTabs", () => {
  test("appends all 6 tab buttons to #tabs", () => {
    const { state, $, t, uiIcon, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    expect(tabsEl._buttons).toHaveLength(6);
  });

  test("each button has the correct data-tab value", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    const tabs = tabsEl._buttons.map((btn) => btn.dataset.tab);
    expect(tabs).toEqual(["home", "world", "players", "analytics", "rules", "server"]);
  });

  test("active tab button has active class", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("world");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    const worldBtn = tabsEl._buttons.find((btn) => btn.dataset.tab === "world");
    expect(worldBtn.className).toBe("active");
  });

  test("inactive tabs have no active class", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("world");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    const inactiveButtons = tabsEl._buttons.filter((btn) => btn.dataset.tab !== "world");
    inactiveButtons.forEach((btn) => expect(btn.className).toBe(""));
  });

  test("__players__ state marks players button active", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("__players__");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    const playersBtn = tabsEl._buttons.find((btn) => btn.dataset.tab === "players");
    expect(playersBtn.className).toBe("active");
  });

  test("__time__ state marks world button active", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("__time__");
    createNavigation({ state, $, t, uiIcon, render }).renderTabs();
    expect(tabsEl._buttons.find((btn) => btn.dataset.tab === "world").className).toBe("active");
  });

  test("server button uses settings translation key", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const tFn = jest.fn((key) => key);
    const nav = createNavigation({ state, $, t: tFn, uiIcon, render });
    nav.renderTabs();
    expect(tFn).toHaveBeenCalledWith("settings");
  });

  test("clicking players button sets tab to __players__", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    const playersBtn = tabsEl._buttons.find((btn) => btn.dataset.tab === "players");
    playersBtn.click();
    expect(state.tab).toBe("__players__");
  });

  test("clicking non-players button sets tab to button value", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    const worldBtn = tabsEl._buttons.find((btn) => btn.dataset.tab === "world");
    worldBtn.click();
    expect(state.tab).toBe("world");
  });

  test("clicking a tab changes only the selected state", () => {
    const { state, $, t, uiIcon, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    const worldBtn = tabsEl._buttons.find((btn) => btn.dataset.tab === "world");
    worldBtn.click();
    expect(state.tab).toBe("world");
  });

  test("replaceChildren is called to clear tabs on every render", () => {
    const { state, $, t, uiIcon, render, tabsEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    expect(tabsEl.replaceChildren).toHaveBeenCalled();
  });
});

// ── openPlayers ───────────────────────────────────────────────────────────────

describe("createNavigation — openPlayers", () => {
  test("sets tab to __players__", () => {
    const { state, $, t, uiIcon, render } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon, render });
    nav.renderTabs();
    nav.openPlayers();
    expect(state.tab).toBe("__players__");
  });

  test("leaves rendering to the tab subscription", () => {
    const { state, $, t, uiIcon } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    nav.openPlayers();
    expect(state.tab).toBe("__players__");
  });
});
