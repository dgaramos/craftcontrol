import { jest } from "@jest/globals";
import { createSettingsFeature } from "../../../static/js/features/settings/index.js";
import { createI18n } from "../../../static/js/i18n/index.js";
import { makeSettingsDeps as makeDeps } from "../../helpers.js";

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

  test.each([
    ["en", "Read only"],
    ["pt", "Somente leitura"],
    ["es", "Solo lectura"],
  ])("renders the read-only badge for detail-operator without permission in %s", (locale, label) => {
    const deps = makeDeps({ locale, user: { capabilities: [] } });
    deps.t = createI18n(() => locale).t;
    const { booleanControl } = createSettingsFeature(deps);
    const html = booleanControl("detail-operator", "true");
    expect(html).toContain('class="read-only-badge"');
    expect(html).toContain(label);
  });

  test("wildcard capability allows operator toggle", () => {
    const deps = makeDeps({ user: { capabilities: ["*"] } });
    const { booleanControl } = createSettingsFeature(deps);
    const html = booleanControl("detail-operator", "true");
    expect(html).toContain("toggle-control");
  });

  test("specific capability allows operator toggle", () => {
    const deps = makeDeps({ user: { capabilities: ["players.manage_permissions"] } });
    const { booleanControl } = createSettingsFeature(deps);
    const html = booleanControl("detail-operator", "true");
    expect(html).toContain("toggle-control");
  });
});

describe("playerSettingsMarkup", () => {
  test("renders section with player settings from schema", () => {
    const deps = makeDeps({
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
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain("player-server-settings");
    expect(html).toContain("Max players");
  });

  test("renders gamerule fields", () => {
    const deps = makeDeps({
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
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain("Show coords");
    expect(html).toContain("enabled");
  });

  test("uses changes over config values", () => {
    const deps = makeDeps({
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
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain('value="20"');
  });

  test.each([
    ["pt", "Regras gerais", "Configurações para todos os jogadores"],
    ["en", "General rules", "Settings for every player"],
    ["es", "Reglas generales", "Configuración para todos los jugadores"],
  ])("renders the general rules heading in %s", (locale, eyebrow, title) => {
    const deps = makeDeps({ locale, schema: { settings: {}, gamerules: {} }, config: {}, changes: {} });
    deps.t = createI18n(() => locale).t;
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain(eyebrow);
    expect(html).toContain(title);
  });
});

describe("booleanControl — select type via inputFor via playerSettingsMarkup", () => {
  test("select type renders segmented control", () => {
    const deps = makeDeps({
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
    });
    const { playerSettingsMarkup } = createSettingsFeature(deps);
    const html = playerSettingsMarkup();
    expect(html).toContain("segmented");
    expect(html).toContain("easy");
    expect(html).toContain("normal");
  });
});

describe("createSettingsFeature — renderChangesDrawer", () => {
  test("closes drawer when no changes", () => {
    const deps = makeDeps();
    const { renderChangesDrawer } = createSettingsFeature(deps);
    renderChangesDrawer();
    expect(deps.$).toHaveBeenCalledWith("#changes-drawer");
    const drawerEl = deps.$("#changes-drawer");
    expect(drawerEl.close).toHaveBeenCalled();
  });

  test("renders change entries to #changes-list", () => {
    const deps = makeDeps({
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
    const deps = makeDeps();
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
    const deps = makeDeps({ changes: { foo: "bar" } });
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
    const deps = makeDeps({
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
    const deps = makeDeps({
      tab: "rules",
      schema: { settings: {}, gamerules: {} },
    });
    const { renderSettingsGroups } = createSettingsFeature(deps);
    renderSettingsGroups(["Interface"]);
    expect(deps.content.innerHTML).toContain("rulesIntro");
  });

  test.each([
    ["world", "configuration", "worldIntro"],
    ["rules", "instant", "rulesIntro"],
    ["__server_settings__", "infrastructure", "serverIntro"],
  ])("wraps the %s screen in the shared inner heading", (tab, kicker, title) => {
    const deps = makeDeps({ tab, schema: { settings: {}, gamerules: {} } });
    createSettingsFeature(deps).renderSettingsGroups(["Geral"]);
    expect(deps.content.innerHTML).toContain('<section class="settings-screen">');
    expect(deps.content.innerHTML).toContain('<header class="inner-heading">');
    expect(deps.content.innerHTML).toContain(`<span class="eyebrow">${kicker}</span>`);
    expect(deps.content.innerHTML).toContain(`<h2>${title}</h2>`);
  });

  test("renders settings from schema in accordion", () => {
    const deps = makeDeps({
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

describe("pending changes stay reactive", () => {
  // state.changes is only observable when reassigned: the reactive state proxy
  // traps top-level sets, so in-place mutation would leave the indicator bar
  // and the save affordance showing a list that is already empty.
  function makeReactiveDeps(initialChanges) {
    const deps = makeDeps({ changes: initialChanges });
    const assignments = [];
    let changes = initialChanges;
    Object.defineProperty(deps.state, "changes", {
      configurable: true,
      get: () => changes,
      set: (value) => { changes = value; assignments.push(value); },
    });
    return { deps, assignments, current: () => changes };
  }

  test("removing the last pending change reassigns state.changes", () => {
    const { deps, assignments, current } = makeReactiveDeps({ MAX_PLAYERS: "20" });
    const removeButton = { dataset: { removeChange: "MAX_PLAYERS" }, onclick: null };
    deps.elements["#changes-list"] = {
      innerHTML: "",
      querySelectorAll: jest.fn(() => [removeButton]),
    };
    deps.elements["#changes-drawer"] = { open: false, close: jest.fn() };
    deps.state.schema.settings.MAX_PLAYERS = { type: "number", label: "Max players", label_en: "Max players" };

    const feature = createSettingsFeature(deps);
    feature.renderChangesDrawer();
    removeButton.onclick();

    expect(assignments).toHaveLength(1);
    expect(current()).toEqual({});
    expect(deps.refreshActivePanel).toHaveBeenCalled();
  });

  test("editing a field reassigns state.changes instead of mutating it", () => {
    const { deps, assignments, current } = makeReactiveDeps({});
    deps.state.config.MAX_PLAYERS = "10";
    deps.state.schema.settings.MAX_PLAYERS = { type: "number", group: "Rede", label: "Max players", label_en: "Max players" };
    const field = { value: "20", addEventListener: jest.fn((_, handler) => { field._change = handler; }) };
    deps.elements["#field-MAX_PLAYERS"] = field;

    const feature = createSettingsFeature(deps);
    feature.bindSettingFields(["Rede"]);
    field._change();

    expect(assignments).toHaveLength(1);
    expect(current()).toEqual({ MAX_PLAYERS: "20" });
  });

  test("reverting a field to the configured value drops the key by reassignment", () => {
    const { deps, assignments, current } = makeReactiveDeps({ MAX_PLAYERS: "20" });
    deps.state.config.MAX_PLAYERS = "10";
    deps.state.schema.settings.MAX_PLAYERS = { type: "number", group: "Rede", label: "Max players", label_en: "Max players" };
    const field = { value: "10", addEventListener: jest.fn((_, handler) => { field._change = handler; }) };
    deps.elements["#field-MAX_PLAYERS"] = field;

    const feature = createSettingsFeature(deps);
    feature.bindSettingFields(["Rede"]);
    field._change();

    expect(assignments).toHaveLength(1);
    expect(current()).toEqual({});
  });
});
