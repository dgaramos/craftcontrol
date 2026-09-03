import { jest } from "@jest/globals";

export function makeEl(extra = {}) {
  // content.cloneNode returns a clone that itself has querySelector returning makeEl(),
  // so template cloning in workspace/navigation code never throws on property access.
  const el = {
    renderedMarkup: "",
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
    // DOM mutation methods needed by template cloning
    children: [],
    replaceChildren: jest.fn(function (...children) {
      this.children = children;
      this.renderedMarkup = children.filter((child) => typeof child === "string").join("");
    }),
    appendChild: jest.fn(),
    insertAdjacentHTML: jest.fn(),
    append: jest.fn(),
    setAttribute: jest.fn(),
    ...extra,
  };
  Object.defineProperty(el, "innerHTML", {
    configurable: true,
    get: () => el.renderedMarkup,
    set: (value) => { el.renderedMarkup = String(value); },
  });
  // Add template content stub so any makeEl() can stand in for a <template>.
  // deepEl() is a lazy recursive factory: each level of querySelector returns
  // another deepEl(), so multi-level chains (e.g. span > b) never throw.
  if (!el.content) {
    const deepEl = () => makeEl({ querySelector: jest.fn(() => deepEl()), append: jest.fn() });
    el.content = { cloneNode: () => deepEl() };
  }
  return el;
}

export function makeDom() {
  const createNode = (tagName = "fragment") => {
    const node = {
      tagName,
      children: [],
      textContent: "",
      className: "",
      dataset: {},
      title: "",
      id: "",
      type: "",
      onclick: null,
      classList: {
        toggle: jest.fn((name, active) => {
          const classes = new Set(node.className.split(/\s+/).filter(Boolean));
          if (active) classes.add(name); else classes.delete(name);
          node.className = [...classes].join(" ");
        }),
        add: jest.fn((...names) => {
          const classes = new Set(node.className.split(/\s+/).filter(Boolean));
          names.forEach((n) => classes.add(n));
          node.className = [...classes].join(" ");
        }),
        remove: jest.fn((...names) => {
          const classes = new Set(node.className.split(/\s+/).filter(Boolean));
          names.forEach((n) => classes.delete(n));
          node.className = [...classes].join(" ");
        }),
      },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      querySelectorAll(selector) {
        const attribute = selector.match(/^\[data-([\w-]+)\]$/)?.[1];
        const key = attribute?.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
        const descendants = this.children.flatMap((child) => [child, ...(child?.querySelectorAll ? child.querySelectorAll(selector) : [])]);
        return key ? descendants.filter((child) => child?.dataset && key in child.dataset) : [];
      },
    };
    return node;
  };
  const document = {
    createElement: (tag) => createNode(tag),
    createDocumentFragment: () => createNode(),
    createRange: () => ({ createContextualFragment: () => createNode() }),
    createTextNode: (text) => { const node = createNode("#text"); node.textContent = String(text); return node; },
  };
  return { document, createNode };
}

export function findNodes(node, predicate) {
  return [node, ...(node.children || []).flatMap((child) => findNodes(child, predicate))].filter(predicate);
}

/**
 * Creates a minimal stub that behaves like a <template> element.
 * The `content.cloneNode(true)` call returns a clone whose querySelector
 * delegates to a provided selector map — any unlisted selector returns a makeEl().
 *
 * @param {Record<string, object>} [selMap] Optional map of CSS selector → stub element.
 */
export function makeTemplateStub(selMap = {}) {
  return {
    content: {
      cloneNode: () => ({
        querySelector: (sel) => (sel in selMap ? selMap[sel] : makeEl()),
        querySelectorAll: jest.fn(() => []),
        replaceChildren: jest.fn(),
        appendChild: jest.fn(),
      }),
    },
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
  const content = { renderedMarkup: "", children: [], replaceChildren(...children) { this.children = children; this.renderedMarkup = children.filter((child) => typeof child === "string").join(""); }, querySelectorAll: jest.fn(() => []) };
  Object.defineProperty(content, "innerHTML", { get: () => content.renderedMarkup, set: (value) => { content.renderedMarkup = String(value); } });
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

export function makeSettingsDeps(stateOverrides = {}) {
  const elements = {};
  const $ = jest.fn((sel) => {
    if (!elements[sel]) elements[sel] = makeEl();
    return elements[sel];
  });
  const document = { querySelector: jest.fn(() => ({ classList: { toggle: jest.fn() } })) };
  const state = {
    locale: "en",
    tab: "world",
    user: { role: "owner", capabilities: ["*"] },
    changes: {},
    config: {},
    gamerules: {},
    domains: {},
    schema: { settings: {}, gamerules: {} },
    frontendVersion: null,
    operationActive: false,
    ...stateOverrides,
  };
  const content = { innerHTML: "", querySelectorAll: jest.fn(() => []) };
  const t = (key, ...args) => (args.length ? `${key}(${args.join(",")})` : key);
  const escapeHtml = (s) => String(s ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]);
  const uiIcon = (name) => `<svg data-icon="${name}"/>`;
  const optionLabel = (v) => v;
  const localeTag = () => "en-US";
  const groupLabel = (g) => g;
  const api = jest.fn();
  const toast = jest.fn();
  const refreshActivePanel = jest.fn();
  return { state, $, content, t, escapeHtml, uiIcon, optionLabel, localeTag, groupLabel, toast, api, render: refreshActivePanel, refreshActivePanel, document, elements };
}

export function makeStorage(initial = {}) {
  const store = { ...initial };
  return {
    getItem: jest.fn((key) => (key in store ? store[key] : null)),
    setItem: jest.fn((key, value) => { store[key] = String(value); }),
    removeItem: jest.fn((key) => { delete store[key]; }),
    _store: store,
  };
}

export class FakeEventSource {
  constructor(url) {
    this.url = url;
    this._listeners = {};
  }
  addEventListener(event, handler) {
    this._listeners[event] = handler;
  }
  set onerror(fn) { this._onerror = fn; }
  emit(event, data) {
    if (this._listeners[event]) this._listeners[event]({ data: JSON.stringify(data) });
  }
}
