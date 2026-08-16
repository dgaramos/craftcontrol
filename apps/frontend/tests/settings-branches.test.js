import { jest } from "@jest/globals";
import { createSettingsFeature } from "../static/js/features/settings/index.js";
import { makeEl, makeSettingsDeps as makeDeps } from "./helpers.js";

// ── renderChangesDrawer — removal handler ─────────────────────────────────────

describe("renderChangesDrawer — removal handler", () => {
  test("clicking [data-remove-change] deletes entry from state.changes and calls render", () => {
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
    expect(deps.render).toHaveBeenCalled();
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
    // renderChangesDrawer sets innerHTML on #changes-list when called
    expect(changesListEl.innerHTML).not.toBe(undefined);
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

  test("api error rolls back gamerule and calls toast with error and render", async () => {
    const { deps, fieldEl } = makeLiveDeps();
    deps.api = jest.fn().mockRejectedValue(new Error("PUT failed"));
    const { bindSettingFields } = createSettingsFeature(deps);
    bindSettingFields(["Geral"]);
    const handler = fieldEl.addEventListener.mock.calls.find(([ev]) => ev === "change")[1];
    await handler();
    expect(deps.state.gamerules.showcoordinates).toBe("true"); // rolled back
    expect(deps.toast).toHaveBeenCalledWith("PUT failed", true);
    expect(deps.render).toHaveBeenCalled();
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
});
