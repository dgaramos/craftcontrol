import { jest } from "@jest/globals";
import { createSettingsFeature } from "../static/js/features/settings/index.js";

function makeDeps(overrides = {}) {
  const state = {
    locale: "en",
    tab: "world",
    user: { role: "owner", capabilities: ["*"] },
    changes: {},
    config: {},
    gamerules: {},
    domains: {},
    schema: {
      settings: {},
      gamerules: {},
    },
    ...overrides.state,
  };
  const $ = jest.fn(() => ({ hidden: false, textContent: "", open: false }));
  const content = { innerHTML: "", querySelectorAll: jest.fn(() => []) };
  const t = (key, ...args) => args.length ? `${key}(${args.join(",")})` : key;
  const api = jest.fn();
  const escapeHtml = (s) => String(s).replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const toast = jest.fn();
  const uiIcon = (name) => `<svg data-icon="${name}"/>`;
  const optionLabel = (v) => v;
  const localeTag = () => "en-US";
  const groupLabel = (g) => g;
  const render = jest.fn();
  return { state, $, content, t, api, escapeHtml, toast, uiIcon, optionLabel, localeTag, groupLabel, render, ...overrides };
}

describe("booleanControl", () => {
  test("renders enabled toggle for true value", () => {
    const { booleanControl } = createSettingsFeature(makeDeps());
    const html = booleanControl("field-foo", "true");
    expect(html).toContain("enabled");
    expect(html).toContain('checked');
  });

  test("renders disabled toggle for false value", () => {
    const { booleanControl } = createSettingsFeature(makeDeps());
    const html = booleanControl("field-foo", "false");
    expect(html).toContain("disabled");
    expect(html).not.toContain('checked');
  });

  test("renders unknown badge for unrecognized value", () => {
    const { booleanControl } = createSettingsFeature(makeDeps());
    const html = booleanControl("field-foo", "maybe");
    expect(html).toContain("unknown");
  });

  test("renders read-only badge for detail-operator without permission", () => {
    const deps = makeDeps({ state: { user: { capabilities: [] } } });
    const { booleanControl } = createSettingsFeature(deps);
    const html = booleanControl("detail-operator", "true");
    expect(html).toContain("Read only");
  });

  test("renders pt read-only label", () => {
    const deps = makeDeps({ state: { locale: "pt", user: { capabilities: [] } } });
    const { booleanControl } = createSettingsFeature(deps);
    const html = booleanControl("detail-operator", "true");
    expect(html).toContain("Somente leitura");
  });

  test("wildcard capability allows operator toggle", () => {
    const deps = makeDeps({ state: { user: { capabilities: ["*"] } } });
    const { booleanControl } = createSettingsFeature(deps);
    const html = booleanControl("detail-operator", "true");
    expect(html).toContain("toggle-control");
  });

  test("specific capability allows operator toggle", () => {
    const deps = makeDeps({ state: { user: { capabilities: ["players.manage_permissions"] } } });
    const { booleanControl } = createSettingsFeature(deps);
    const html = booleanControl("detail-operator", "true");
    expect(html).toContain("toggle-control");
  });
});

describe("playerSettingsMarkup", () => {
  test("renders section with player settings from schema", () => {
    const deps = makeDeps({
      state: {
        schema: {
          settings: {
            max_players: {
              group: "Jogadores",
              label: "Max players",
              label_en: "Max players",
              description: "desc",
              description_en: "desc",
              type: "number",
              min: 1, max: 30,
            },
          },
          gamerules: {},
        },
        config: { max_players: "10" },
        changes: {},
      },
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain("player-server-settings");
    expect(html).toContain("Max players");
  });

  test("renders gamerule fields", () => {
    const deps = makeDeps({
      state: {
        schema: {
          settings: {},
          gamerules: {
            showcoordinates: {
              group: "Jogadores",
              label: "Show coords",
              label_en: "Show coords",
              description: "Show coordinates",
              description_en: "Show coordinates",
              type: "boolean",
            },
          },
        },
        gamerules: { showcoordinates: "true" },
        config: {},
        changes: {},
      },
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain("Show coords");
    expect(html).toContain("enabled");
  });

  test("uses changes over config values", () => {
    const deps = makeDeps({
      state: {
        schema: {
          settings: {
            max_players: {
              group: "Jogadores",
              label: "Max players",
              label_en: "Max players",
              description: "d",
              description_en: "d",
              type: "number",
            },
          },
          gamerules: {},
        },
        config: { max_players: "10" },
        changes: { max_players: "20" },
      },
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain('value="20"');
  });

  test("renders pt locale heading", () => {
    const deps = makeDeps({ state: { locale: "pt", schema: { settings: {}, gamerules: {} }, config: {}, changes: {} } });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain("REGRAS GERAIS");
  });
});

describe("booleanControl — select type via inputFor via playerSettingsMarkup", () => {
  test("select type renders segmented control", () => {
    const deps = makeDeps({
      state: {
        schema: {
          settings: {
            difficulty: {
              group: "Jogadores",
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
        config: { difficulty: "normal" },
        changes: {},
      },
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain("segmented");
    expect(html).toContain("easy");
    expect(html).toContain("normal");
  });
});

