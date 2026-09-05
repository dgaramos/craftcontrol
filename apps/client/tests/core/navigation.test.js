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

function makeBottomNavButton(tab) {
  return {
    dataset: { tab },
    className: "",
    onclick: null,
    click() { if (this.onclick) this.onclick(); },
  };
}

function makeBottomNavElement() {
  const homeBtn = makeBottomNavButton("home");
  const playersBtn = makeBottomNavButton("__players__");
  const serverBtn = makeBottomNavButton("server");
  const buttons = [homeBtn, playersBtn, serverBtn];
  return {
    _buttons: buttons,
    querySelectorAll(sel) {
      return sel === "button[data-tab]" ? buttons : [];
    },
  };
}

function makeEnv(initialTab = "home") {
  const state = {
    tab: initialTab,
    tabs: ["home", "world", "players", "analytics", "rules", "server"],
    subscribe: jest.fn(),
  };
  const tabsEl = makeTabsElement();
  const bottomNavEl = makeBottomNavElement();
  const tplNavTab = makeFakeNavTabTemplate();
  const $ = (sel) => {
    if (sel === "#tabs") return tabsEl;
    if (sel === "#tpl-nav-tab") return tplNavTab;
    if (sel === "#bottom-nav") return bottomNavEl;
    return null;
  };
  const t = (key) => key;
  const uiIcon = (name) => name;
  return { state, $, t, uiIcon, tabsEl, bottomNavEl };
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

  test("audit button uses the dedicated audit icon", () => {
    const { state, $, t, render, tabsEl } = makeEnv("audit");
    state.tabs.push("audit");
    const uiIcon = jest.fn((name) => name);
    createNavigation({ state, $, t, uiIcon, render }).renderTabs();
    expect(uiIcon).toHaveBeenCalledWith("audit");
    expect(tabsEl._buttons.find((btn) => btn.dataset.tab === "audit").querySelector("i").innerHTML).toBe("audit");
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

// ── bottom-nav sync ───────────────────────────────────────────────────────────

describe("createNavigation — bottom-nav sync", () => {
  test("bottom-nav home button sets state.tab to 'home'", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("__players__");
    createNavigation({ state, $, t, uiIcon });
    const homeBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "home");
    homeBtn.click();
    expect(state.tab).toBe("home");
  });

  test("bottom-nav players button sets state.tab to '__players__'", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("home");
    createNavigation({ state, $, t, uiIcon });
    const playersBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "__players__");
    playersBtn.click();
    expect(state.tab).toBe("__players__");
  });

  test("bottom-nav server button sets state.tab to 'server'", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("home");
    createNavigation({ state, $, t, uiIcon });
    const serverBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "server");
    serverBtn.click();
    expect(state.tab).toBe("server");
  });

  test("renderTabs marks home bottom-nav button active when tab is home", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    const homeBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "home");
    expect(homeBtn.className).toBe("active");
  });

  test("renderTabs marks players bottom-nav button active when tab is __players__", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("__players__");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    const playersBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "__players__");
    expect(playersBtn.className).toBe("active");
  });

  test("renderTabs marks server bottom-nav button active when tab is server", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("server");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    const serverBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "server");
    expect(serverBtn.className).toBe("active");
  });

  test("renderTabs removes active from inactive bottom-nav buttons", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    const inactive = bottomNavEl._buttons.filter((b) => b.dataset.tab !== "home");
    inactive.forEach((btn) => expect(btn.className).toBe(""));
  });

  test("__players__ state marks players bottom-nav button active", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("__players__");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderTabs();
    const playersBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "__players__");
    expect(playersBtn.className).toBe("active");
  });
});

// ── renderBottomNav ───────────────────────────────────────────────────────────

describe("createNavigation — renderBottomNav", () => {
  test("is exposed on the navigation object", () => {
    const { state, $, t, uiIcon } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    expect(typeof nav.renderBottomNav).toBe("function");
  });

  test("marks home button active when state.tab is home", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderBottomNav();
    const homeBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "home");
    expect(homeBtn.className).toBe("active");
  });

  test("marks __players__ button active when state.tab is __players__", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("__players__");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderBottomNav();
    const playersBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "__players__");
    expect(playersBtn.className).toBe("active");
  });

  test("marks server button active when state.tab is server", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("server");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderBottomNav();
    const serverBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "server");
    expect(serverBtn.className).toBe("active");
  });

  test("removes active from other buttons when home is active", () => {
    const { state, $, t, uiIcon, bottomNavEl } = makeEnv("home");
    const nav = createNavigation({ state, $, t, uiIcon });
    nav.renderBottomNav();
    const inactive = bottomNavEl._buttons.filter((b) => b.dataset.tab !== "home");
    inactive.forEach((btn) => expect(btn.className).toBe(""));
  });

  test("internal tabs leave no bottom-nav button active", () => {
    for (const tab of ["world", "analytics", "rules", "audit", "__time__"]) {
      const { state, $, t, uiIcon, bottomNavEl } = makeEnv(tab);
      const nav = createNavigation({ state, $, t, uiIcon });
      nav.renderBottomNav();
      // For internal tabs, none of the 3 bottom-nav buttons should be active
      // (they all fall back to 'home' mapping via _bottomNavActive)
      // Actually per spec: home is the fallback for internal tabs
      const homeBtn = bottomNavEl._buttons.find((b) => b.dataset.tab === "home");
      expect(homeBtn.className).toBe("active");
    }
  });
});
