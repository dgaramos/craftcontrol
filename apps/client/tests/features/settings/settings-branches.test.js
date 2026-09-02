import { jest } from "@jest/globals";
import { createSettingsFeature } from "../../../static/js/features/settings/index.js";
import { makeEl, makeSettingsDeps as makeDeps } from "../../helpers.js";

// ── renderChangesDrawer — removal handler ─────────────────────────────────────

describe("renderChangesDrawer — removal handler", () => {
  test("clicking [data-remove-change] deletes entry and refreshes the active panel", () => {
    const deps = makeDeps({
      changes: { max_players: "20" },
      config: { max_players: "10" },
      schema: {
        settings: {
          max_players: { group: "Geral", label: "Max Players", label_en: "Max Players", description: "d", description_en: "d", type: "number" },
        },
        gamerules: {},
      },
    });
    const removeBtn = makeEl({ dataset: { removeChange: "max_players" } });
    deps.elements["#changes-list"] = makeEl({
      querySelectorAll: jest.fn(() => [removeBtn]),
    });
    deps.elements["#changes-drawer"] = makeEl({ open: false });
    deps.elements["#save"] = makeEl();
    deps.elements["#save-label"] = makeEl();

    const { renderChangesDrawer } = createSettingsFeature(deps);
    renderChangesDrawer();
    removeBtn.onclick();
    expect(deps.state.changes).not.toHaveProperty("max_players");
    expect(deps.refreshActivePanel).toHaveBeenCalled();
  });
});

// ── updateSaveLabel — drawer open branch ──────────────────────────────────────

describe("updateSaveLabel", () => {
  test("when drawer is open, calls renderChangesDrawer", () => {
    const deps = makeDeps({
      changes: { max_players: "20" },
      config: { max_players: "10" },
      schema: {
        settings: {
          max_players: { group: "G", label: "Max", label_en: "Max", description: "d", description_en: "d", type: "number" },
        },
        gamerules: {},
      },
    });
    const saveEl = makeEl({ hidden: false });
    const saveLabelEl = makeEl();
    const changesDrawerEl = makeEl({ open: true });
    const changesListEl = makeEl({ querySelectorAll: jest.fn(() => []) });

    deps.elements["#save"] = saveEl;
    deps.elements["#save-label"] = saveLabelEl;
    deps.elements["#changes-drawer"] = changesDrawerEl;
    deps.elements["#changes-list"] = changesListEl;

    const { updateSaveLabel } = createSettingsFeature(deps);
    updateSaveLabel();
    expect(changesListEl.innerHTML).toContain("max_players");
  });

  test("when no changes, hides #save", () => {
    const deps = makeDeps();
    const saveEl = makeEl({ hidden: false });
    deps.elements["#save"] = saveEl;
    deps.elements["#save-label"] = makeEl();
    deps.elements["#changes-drawer"] = makeEl({ open: false });
    const { updateSaveLabel } = createSettingsFeature(deps);
    updateSaveLabel();
    expect(saveEl.hidden).toBe(true);
  });
});

// ── displayValue — via renderChangesDrawer ────────────────────────────────────

describe("displayValue branches", () => {
  function renderWithFieldType(type, value, configValue) {
    const deps = makeDeps({
      changes: { myfield: value },
      config: { myfield: configValue ?? "old" },
      schema: {
        settings: {
          myfield: { group: "G", label: "Field", label_en: "Field", description: "d", description_en: "d", type },
        },
        gamerules: {},
      },
    });
    const changesListEl = makeEl({ querySelectorAll: jest.fn(() => []) });
    deps.elements["#changes-list"] = changesListEl;
    deps.elements["#changes-drawer"] = makeEl({ open: false });
    deps.elements["#save"] = makeEl();
    deps.elements["#save-label"] = makeEl();
    const { renderChangesDrawer } = createSettingsFeature(deps);
    renderChangesDrawer();
    return changesListEl.innerHTML;
  }

  test("boolean true renders enabled", () => {
    const html = renderWithFieldType("boolean", "true", "false");
    expect(html).toContain("enabled");
  });

  test("boolean false renders disabled", () => {
    const html = renderWithFieldType("boolean", "false", "true");
    expect(html).toContain("disabled");
  });

  test("select type renders option label", () => {
    const html = renderWithFieldType("select", "hard", "easy");
    expect(html).toContain("hard");
  });

  test("text type renders value as string", () => {
    const html = renderWithFieldType("text", "hello world", "old");
    expect(html).toContain("hello world");
  });
});

// ── bindSettingFields — persistent field ─────────────────────────────────────

describe("bindSettingFields — persistent field", () => {
  function makeFieldDeps(fieldType = "number") {
    const deps = makeDeps({
      changes: {},
      config: { max_players: "10" },
      schema: {
        settings: {
          max_players: { group: "Geral", label: "Max", label_en: "Max", description: "d", description_en: "d", type: fieldType },
        },
        gamerules: {},
      },
    });
    const fieldEl = makeEl({ value: "20", checked: false });
    deps.elements["#field-max_players"] = fieldEl;
    deps.elements["#save"] = makeEl();
    deps.elements["#save-label"] = makeEl();
    deps.elements["#changes-drawer"] = makeEl({ open: false });
    return { deps, fieldEl };
  }

  test("change event with different value adds to state.changes", () => {
    const { deps, fieldEl } = makeFieldDeps();
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["Geral"]);
    const handler = fieldEl.addEventListener.mock.calls.find(([ev]) => ev === "change")[1];
    handler();
    expect(deps.state.changes).toHaveProperty("max_players", "20");
  });

  test("change event equal to config removes from state.changes", () => {
    const { deps, fieldEl } = makeFieldDeps();
    fieldEl.value = "10"; // same as config
    deps.state.changes["max_players"] = "10";
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["Geral"]);
    const handler = fieldEl.addEventListener.mock.calls.find(([ev]) => ev === "change")[1];
    handler();
    expect(deps.state.changes).not.toHaveProperty("max_players");
  });

  test("boolean field calls updateToggleLabel on change", () => {
    const { deps, fieldEl } = makeFieldDeps("boolean");
    fieldEl.checked = true;
    const toggleControl = makeEl({
      querySelector: jest.fn(() => makeEl({ textContent: "", classList: { remove: jest.fn() } })),
    });
    fieldEl.closest = jest.fn(() => toggleControl);
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["Geral"]);
    const handler = fieldEl.addEventListener.mock.calls.find(([ev]) => ev === "change")[1];
    // Should not throw
    expect(() => handler()).not.toThrow();
  });
});

// ── bindSettingFields — live gamerule field ───────────────────────────────────

describe("bindSettingFields — live gamerule field", () => {
  function makeLiveDeps() {
    const deps = makeDeps({
      changes: {},
      config: {},
      gamerules: { showcoordinates: "true" },
      schema: {
        settings: {},
        gamerules: {
          showcoordinates: { group: "Geral", label: "Show coords", label_en: "Show coords", description: "d", description_en: "d", type: "boolean" },
        },
      },
    });
    const labelEl = makeEl({ textContent: "", classList: { remove: jest.fn() } });
    const toggleControl = makeEl({ querySelector: jest.fn(() => labelEl) });
    const fieldEl = makeEl({ value: "false", checked: false, closest: jest.fn(() => toggleControl) });
    deps.elements["#field-showcoordinates"] = fieldEl;
    return { deps, fieldEl };
  }

  test("change event calls api PUT for gamerule", async () => {
    const { deps, fieldEl } = makeLiveDeps();
    deps.api = jest.fn().mockResolvedValue({});
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["Geral"]);
    const handler = fieldEl.addEventListener.mock.calls.find(([ev]) => ev === "change")[1];
    await handler();
    expect(deps.api).toHaveBeenCalledWith(
      "/api/gamerules/showcoordinates",
      expect.objectContaining({ method: "PUT" })
    );
  });

  test("success updates state.gamerules and calls toast", async () => {
    const { deps, fieldEl } = makeLiveDeps();
    deps.api = jest.fn().mockResolvedValue({});
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["Geral"]);
    const handler = fieldEl.addEventListener.mock.calls.find(([ev]) => ev === "change")[1];
    await handler();
    expect(deps.state.gamerules.showcoordinates).toBe("false");
    expect(deps.toast).toHaveBeenCalled();
  });

  test("api error rolls back gamerule and refreshes the active panel", async () => {
    const { deps, fieldEl } = makeLiveDeps();
    deps.api = jest.fn().mockRejectedValue(new Error("PUT failed"));
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["Geral"]);
    const handler = fieldEl.addEventListener.mock.calls.find(([ev]) => ev === "change")[1];
    await handler();
    expect(deps.state.gamerules.showcoordinates).toBe("true"); // rolled back
    expect(deps.toast).toHaveBeenCalledWith("PUT failed", true);
    expect(deps.refreshActivePanel).toHaveBeenCalled();
  });
});

// ── updateToggleLabel ─────────────────────────────────────────────────────────

describe("updateToggleLabel", () => {
  test("checked=true sets textContent to enabled and removes unknown class", () => {
    const deps = makeDeps();
    const labelEl = makeEl({ textContent: "", classList: { remove: jest.fn() } });
    const toggleControl = makeEl({ querySelector: jest.fn(() => labelEl) });
    const checkbox = makeEl({ checked: true, closest: jest.fn(() => toggleControl) });
    const { updateToggleLabel } = createSettingsFeature(deps);
    updateToggleLabel(checkbox);
    expect(labelEl.textContent).toBe("enabled");
    expect(labelEl.classList.remove).toHaveBeenCalledWith("unknown");
  });

  test("checked=false sets textContent to disabled", () => {
    const deps = makeDeps();
    const labelEl = makeEl({ textContent: "", classList: { remove: jest.fn() } });
    const toggleControl = makeEl({ querySelector: jest.fn(() => labelEl) });
    const checkbox = makeEl({ checked: false, closest: jest.fn(() => toggleControl) });
    const { updateToggleLabel } = createSettingsFeature(deps);
    updateToggleLabel(checkbox);
    expect(labelEl.textContent).toBe("disabled");
  });

  test("renders locale, boolean, select, and numeric field variants", () => {
    const deps = makeDeps({
      locale: "es", tab: "server", user: { capabilities: [] },
      changes: {}, config: { limit: null }, gamerules: {}, domains: { settings: {} },
      schema: { settings: { limit: { group: "G", type: "number", label: "PT", label_en: "EN", label_es: "ES", description: "d", description_en: "de", description_es: "des", min: 1, max: 9, warning: "warn", warning_en: "warning" } }, gamerules: {} },
    });
    const feature = createSettingsFeature(deps);
    expect(feature.booleanControl("detail-operator", "unknown")).toContain("Solo lectura");
    feature.renderSettingsGroups(["G"]);
    expect(deps.content.innerHTML).toContain("serverIntro");
    expect(deps.content.innerHTML).toContain('min="1"');
    expect(deps.content.innerHTML).toContain("ES");
  });

  test("renders English controls with change overrides and observed domains", () => {
    const deps = makeDeps({
      locale: "en", tab: "rules", user: { capabilities: ["players.manage_permissions"] },
      changes: { mode: "hard" }, config: { enabled: "false", mode: "easy" }, gamerules: { live: "true" },
      domains: { settings: { observed_at: 1 } },
      schema: { settings: {
        enabled: { group: "G", type: "boolean", label: "PT", label_en: "Enabled", description: "d", description_en: "English" },
        mode: { group: "G", type: "select", label: "PT", label_en: "Mode", description: "d", description_en: "English", options: ["easy", "hard"], warning_en: "Careful" },
      }, gamerules: { live: { group: "G", type: "boolean", label: "Live", label_en: "Live", description: "d", description_en: "English" } } },
    });
    createSettingsFeature(deps).renderSettingsGroups(["G"]);
    expect(deps.content.innerHTML).toContain("rulesIntro");
    expect(deps.content.innerHTML).toContain("checked");
    expect(deps.content.innerHTML).toContain('data-choice="hard"');
    expect(deps.content.innerHTML).toContain("Careful");
  });
});

// ── operation lock ────────────────────────────────────────────────────────────

describe("operation lock", () => {
  function makeLockedDeps() {
    return makeDeps({
      operationActive: true,
      changes: {},
      config: { max_players: "10" },
      gamerules: { showcoordinates: "true" },
      schema: {
        settings: {
          max_players: { group: "G", label: "Max", label_en: "Max", description: "d", description_en: "d", type: "number" },
        },
        gamerules: {
          showcoordinates: { group: "G", label: "Coords", label_en: "Coords", description: "d", description_en: "d", type: "boolean" },
        },
      },
    });
  }

  test("renderSettingsGroups includes mutation-lock-notice when operationActive", () => {
    const deps = makeLockedDeps();
    createSettingsFeature(deps).renderSettingsGroups(["G"]);
    expect(deps.content.innerHTML).toContain("mutation-lock-notice");
    expect(deps.content.innerHTML).toContain("operationLocked");
  });

  test("renderSettingsGroups omits mutation-lock-notice when operation is not active", () => {
    const deps = makeDeps({ operationActive: false, schema: { settings: {}, gamerules: {} } });
    createSettingsFeature(deps).renderSettingsGroups([]);
    expect(deps.content.innerHTML).not.toContain("mutation-lock-notice");
  });

  test("bindSettingFields disables all fields when operationActive", () => {
    const deps = makeLockedDeps();
    const settingsEl = makeEl();
    const gameruleEl = makeEl();
    deps.elements["#field-max_players"] = settingsEl;
    deps.elements["#field-showcoordinates"] = gameruleEl;
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["G"]);
    expect(settingsEl.disabled).toBe(true);
    expect(gameruleEl.disabled).toBe(true);
  });

  test("bindSettingFields disables segmented-control buttons when operationActive", () => {
    const deps = makeLockedDeps();
    const segmentBtn = makeEl();
    const segmentedContainer = makeEl({ querySelectorAll: jest.fn(() => [segmentBtn]) });
    const hiddenInput = makeEl({ closest: jest.fn(() => segmentedContainer) });
    deps.elements["#field-max_players"] = hiddenInput;
    deps.elements["#field-showcoordinates"] = makeEl();
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["G"]);
    expect(segmentBtn.disabled).toBe(true);
  });

  test("bindSettingFields skips event binding when operationActive", () => {
    const deps = makeLockedDeps();
    const settingsEl = makeEl();
    deps.elements["#field-max_players"] = settingsEl;
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["G"]);
    // addEventListener should not be called because we returned early
    expect(settingsEl.addEventListener).not.toHaveBeenCalled();
  });

  test("updateSaveLabel hides save when operationActive even with pending changes", () => {
    const deps = makeLockedDeps();
    deps.state.changes = { max_players: "20" };
    const saveEl = makeEl({ hidden: false });
    deps.elements["#save"] = saveEl;
    deps.elements["#save-label"] = makeEl();
    deps.elements["#changes-drawer"] = makeEl({ open: false });
    const { updateSaveLabel } = createSettingsFeature(deps);
    updateSaveLabel();
    expect(saveEl.hidden).toBe(true);
  });
});
