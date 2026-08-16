import { jest } from "@jest/globals";
import { createRulesFeature } from "../static/js/features/rules/index.js";
import { createSettingsFeature } from "../static/js/features/settings/index.js";
import { createServerFeature } from "../static/js/features/server/index.js";

// ─── createRulesFeature ────────────────────────────────────────────────────

describe("createRulesFeature", () => {
  test("renderRules calls renderSettingsGroups with the six rule groups", () => {
    const renderSettingsGroups = jest.fn();
    const { renderRules } = createRulesFeature({ renderSettingsGroups });
    renderRules();
    expect(renderSettingsGroups).toHaveBeenCalledTimes(1);
    const [groups] = renderSettingsGroups.mock.calls[0];
    expect(groups).toEqual([
      "Interface", "Jogabilidade", "Tempo e clima",
      "Criaturas", "Drops", "Comandos",
    ]);
  });
});

// ─── createSettingsFeature — additional coverage ───────────────────────────

function makeSettingsDeps(extraState = {}) {
  const domElements = {};
  const makeFakeEl = () => ({
    hidden: false,
    textContent: "",
    open: false,
    innerHTML: "",
    value: "",
    checked: false,
    closest: jest.fn(() => ({ querySelector: jest.fn(() => ({ textContent: "", classList: { remove: jest.fn() } })) })),
    classList: { toggle: jest.fn(), remove: jest.fn() },
    querySelector: jest.fn(() => null),
    querySelectorAll: jest.fn(() => []),
    addEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
    close: jest.fn(),
  });
  const $ = jest.fn((sel) => {
    if (!domElements[sel]) domElements[sel] = makeFakeEl();
    return domElements[sel];
  });

  // Patch document.querySelector for footer (used by updateSaveLabel)
  if (typeof global.document === "undefined") {
    global.document = { querySelector: jest.fn(() => ({ classList: { toggle: jest.fn() } })) };
  } else {
    global.document.querySelector = jest.fn(() => ({ classList: { toggle: jest.fn() } }));
  }

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
    ...extraState,
  };
  const content = {
    innerHTML: "",
    querySelectorAll: jest.fn(() => []),
  };
  const t = (key, ...args) => args.length ? `${key}(${args.join(",")})` : key;
  const escapeHtml = (s) => String(s ?? "").replace(/</g, "&lt;");
  const uiIcon = (name) => `<svg icon="${name}"/>`;
  const optionLabel = (v) => v;
  const localeTag = () => "en-US";
  const groupLabel = (g) => g;
  const toast = jest.fn();
  const api = jest.fn();
  const render = jest.fn();
  return { state, $, content, t, escapeHtml, uiIcon, optionLabel, localeTag, groupLabel, toast, api, render };
}

describe("createSettingsFeature — renderChangesDrawer", () => {
  test("closes drawer when no changes", () => {
    const deps = makeSettingsDeps();
    const { renderChangesDrawer } = createSettingsFeature(deps);
    renderChangesDrawer();
    expect(deps.$).toHaveBeenCalledWith("#changes-drawer");
    const drawerEl = deps.$("#changes-drawer");
    expect(drawerEl.close).toHaveBeenCalled();
  });

  test("renders change entries to #changes-list", () => {
    const deps = makeSettingsDeps({
      changes: { difficulty: "hard" },
      config: { difficulty: "normal" },
      schema: {
        settings: {
          difficulty: {
            group: "Geral",
            label: "Difficulty",
            label_en: "Difficulty",
            description: "d",
            description_en: "d",
            type: "select",
            options: ["easy", "normal", "hard"],
          },
        },
        gamerules: {},
      },
    });
    const { renderChangesDrawer } = createSettingsFeature(deps);
    renderChangesDrawer();
    const listEl = deps.$("#changes-list");
    expect(listEl.innerHTML).toContain("difficulty");
  });
});

describe("createSettingsFeature — updateSaveLabel", () => {
  test("hides save button when no changes", () => {
    const deps = makeSettingsDeps();
    const saveEl = { hidden: false, textContent: "" };
    deps.$ = jest.fn((sel) => {
      if (sel === "#save") return saveEl;
      if (sel === "#save-label") return { textContent: "" };
      if (sel === "#changes-drawer") return { open: false };
      return { hidden: false };
    });
    const { updateSaveLabel } = createSettingsFeature(deps);
    updateSaveLabel();
    expect(saveEl.hidden).toBe(true);
  });

  test("shows save button when changes present", () => {
    const deps = makeSettingsDeps({ changes: { foo: "bar" } });
    const saveEl = { hidden: true, textContent: "" };
    deps.$ = jest.fn((sel) => {
      if (sel === "#save") return saveEl;
      if (sel === "#save-label") return { textContent: "" };
      if (sel === "#changes-drawer") return { open: false };
      return { hidden: false };
    });
    const { updateSaveLabel } = createSettingsFeature(deps);
    updateSaveLabel();
    expect(saveEl.hidden).toBe(false);
  });
});

describe("createSettingsFeature — renderSettingsGroups", () => {
  test("sets content.innerHTML and calls bindSegmentedControls", () => {
    const deps = makeSettingsDeps({
      tab: "world",
      schema: {
        settings: {},
        gamerules: {},
      },
    });
    const { renderSettingsGroups } = createSettingsFeature(deps);
    renderSettingsGroups(["Geral"]);
    expect(deps.content.innerHTML).toContain("accordion-list");
    expect(deps.content.querySelectorAll).toHaveBeenCalledWith(".segmented");
  });

  test("uses rulesIntro title for rules tab", () => {
    const deps = makeSettingsDeps({
      tab: "rules",
      schema: { settings: {}, gamerules: {} },
    });
    const { renderSettingsGroups } = createSettingsFeature(deps);
    renderSettingsGroups(["Interface"]);
    expect(deps.content.innerHTML).toContain("rulesIntro");
  });

  test("renders settings from schema in accordion", () => {
    const deps = makeSettingsDeps({
      tab: "world",
      schema: {
        settings: {
          seed: {
            group: "Mundo",
            label: "Seed",
            label_en: "Seed",
            description: "World seed",
            description_en: "World seed",
            type: "text",
          },
        },
        gamerules: {},
      },
      config: { seed: "42" },
      domains: { settings: { observed_at: 1700000000 } },
    });
    const { renderSettingsGroups } = createSettingsFeature(deps);
    renderSettingsGroups(["Mundo"]);
    expect(deps.content.innerHTML).toContain("Seed");
    expect(deps.content.innerHTML).toContain('value="42"');
  });
});

// ─── createServerFeature — renderReleaseTags ───────────────────────────────

describe("createServerFeature — renderReleaseTags", () => {
  test("returns early when #release-tags element is absent", () => {
    const $ = jest.fn(() => null);
    const deps = {
      state: { frontendVersion: null },
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $,
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      renderSettingsGroups: jest.fn(),
    };
    const { renderReleaseTags } = createServerFeature(deps);
    expect(() => renderReleaseTags({})).not.toThrow();
  });

  test("sets innerHTML on release-tags element", () => {
    const releaseEl = { innerHTML: "" };
    const $ = jest.fn((sel) => sel === "#release-tags" ? releaseEl : null);
    const deps = {
      state: { frontendVersion: "1.2.3" },
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $,
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "2024-01-01",
      toast: jest.fn(),
      renderSettingsGroups: jest.fn(),
    };
    const { renderReleaseTags } = createServerFeature(deps);
    renderReleaseTags({ application: { version: "2.0.0", started_at: 0 }, runtime_version: "1.0", last_response_at: 0 });
    expect(releaseEl.innerHTML).toContain("1.2.3");
    expect(releaseEl.innerHTML).toContain("2.0.0");
  });
});

describe("createServerFeature — loadFrontendVersion", () => {
  test("updates state.frontendVersion on success", async () => {
    const state = { frontendVersion: null };
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({ service: "frontend", version: "3.1.4" }),
    });
    global.fetch = mockFetch;
    const deps = {
      state,
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $: jest.fn(() => null),
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      renderSettingsGroups: jest.fn(),
    };
    const { loadFrontendVersion } = createServerFeature(deps);
    await loadFrontendVersion();
    expect(state.frontendVersion).toBe("3.1.4");
  });

  test("ignores non-ok responses", async () => {
    const state = { frontendVersion: null };
    global.fetch = jest.fn().mockResolvedValue({ ok: false });
    const deps = {
      state,
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $: jest.fn(() => null),
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      renderSettingsGroups: jest.fn(),
    };
    const { loadFrontendVersion } = createServerFeature(deps);
    await loadFrontendVersion();
    expect(state.frontendVersion).toBeNull();
  });

  test("swallows fetch errors silently", async () => {
    const state = { frontendVersion: null };
    global.fetch = jest.fn().mockRejectedValue(new Error("network"));
    const deps = {
      state,
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $: jest.fn(() => null),
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      renderSettingsGroups: jest.fn(),
    };
    const { loadFrontendVersion } = createServerFeature(deps);
    await expect(loadFrontendVersion()).resolves.toBeUndefined();
    expect(state.frontendVersion).toBeNull();
  });
});
