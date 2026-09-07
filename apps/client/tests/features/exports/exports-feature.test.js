import { jest } from "@jest/globals";
import { createExportsFeature } from "../../../static/js/features/exports/index.js";
import { createI18n } from "../../../static/js/i18n/index.js";

function makeDeps(locale = "en") {
  const elements = {};
  // Buttons the panel binds by attribute; the handlers land here so a test can
  // drive the panel the way a click does.
  const buttons = { "[data-export-family]": {}, "[data-export-format]": {} };
  const state = { locale, user: { role: "owner" } };
  const content = {
    innerHTML: "",
    querySelectorAll: jest.fn((selector) => {
      const group = buttons[selector];
      if (!group) return [];
      const attribute = selector.slice(1, -1);
      const key = attribute.replace(/^data-/, "").replace(/-(\w)/g, (_, c) => c.toUpperCase());
      return ["players", "analytics", "json", "csv"]
        .filter((value) => (key === "exportFamily") === ["players", "analytics"].includes(value))
        .map((value) => {
          const button = group[value] || (group[value] = { dataset: { [key]: value }, onclick: null });
          return button;
        });
    }),
  };
  const $ = jest.fn((selector) => elements[selector] || null);
  const escapeHtml = (value) => String(value ?? "").replace(
    /[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );
  return {
    state, content, t: createI18n(() => state.locale).t, $, escapeHtml,
    toast: jest.fn(), download: jest.fn().mockResolvedValue("file.json"), elements, buttons,
  };
}

/** Drive the resource select the way a click would, then return the markup. */
function selectResource(deps, resource) {
  deps.elements["#export-resource"] = { value: resource, onchange: null };
  const feature = createExportsFeature(deps);
  feature.renderExportsPanel();
  deps.elements["#export-resource"].onchange();
  return { feature, html: deps.content.innerHTML };
}

describe("createExportsFeature — scope", () => {
  test("describes the selected resource before it is exported", () => {
    const deps = makeDeps();
    createExportsFeature(deps).renderExportsPanel();
    expect(deps.content.innerHTML).toContain("Player profiles");
    expect(deps.content.innerHTML).toContain("Lifetime totals for every player.");
  });

  test("builds the documented URL for the default scope", () => {
    expect(createExportsFeature(makeDeps()).exportUrl()).toBe(
      "/api/exports/players/profiles?format=json"
    );
  });

  test("only offers a period where the API accepts one", () => {
    const deps = makeDeps();
    const withoutPeriod = selectResource(deps, "profiles").html;
    expect(withoutPeriod).not.toContain('id="export-days"');
    const withPeriod = selectResource(makeDeps(), "activity").html;
    expect(withPeriod).toContain('id="export-days"');
  });

  test("states the privacy floor and the ceiling before any download", () => {
    const deps = makeDeps();
    createExportsFeature(deps).renderExportsPanel();
    expect(deps.content.innerHTML).toContain("never contain XUIDs");
    expect(deps.content.innerHTML).toContain("10,000 records");
  });
});

describe("createExportsFeature — no misleading download", () => {
  test("a resource that requires a player keeps the button disabled", () => {
    const { html } = selectResource(makeDeps(), "sessions");
    expect(html).toContain("disabled");
    expect(html).toContain("This resource requires one player.");
  });

  test("a refusal is explained with the measurement, never downloaded", () => {
    const feature = createExportsFeature(makeDeps());
    const message = feature.exportError({
      status: 422, payload: { limit: "record", measured: 20000, allowed: 10000 },
    });
    expect(message).toContain("20000");
    expect(message).toContain("10000");
  });

  test("a denial is explained as an ownership requirement", () => {
    expect(createExportsFeature(makeDeps()).exportError({ status: 403 })).toBe(
      "Only an owner can export data."
    );
  });

  test("an unexpected failure keeps the server's own message", () => {
    expect(createExportsFeature(makeDeps()).exportError(new Error("backend unavailable"))).toBe(
      "backend unavailable"
    );
  });
});

describe("createExportsFeature — localization", () => {
  test.each([
    ["pt", "Exportar dados"],
    ["en", "Data export"],
    ["es", "Exportar datos"],
  ])("renders its copy in %s", (locale, title) => {
    const deps = makeDeps(locale);
    createExportsFeature(deps).renderExportsPanel();
    expect(deps.content.innerHTML).toContain(title);
    expect(deps.content.innerHTML).not.toContain("exportTitle");
  });
});


describe("createExportsFeature — controls", () => {
  test("switching to analytics resets the resource and offers a limit", () => {
    const deps = makeDeps();
    const feature = createExportsFeature(deps);
    feature.renderExportsPanel();
    deps.buttons["[data-export-family]"].analytics.onclick();
    expect(feature.exportUrl()).toBe("/api/exports/analytics/rankings?format=json&limit=10");
    expect(deps.content.innerHTML).toContain('id="export-limit"');
  });

  test("switching the format changes the requested representation", () => {
    const deps = makeDeps();
    const feature = createExportsFeature(deps);
    feature.renderExportsPanel();
    deps.buttons["[data-export-format]"].csv.onclick();
    expect(feature.exportUrl()).toBe("/api/exports/players/profiles?format=csv");
  });

  test("a player filter reaches the request only where it is supported", () => {
    const deps = makeDeps();
    deps.elements["#export-resource"] = { value: "activity", onchange: null };
    deps.elements["#export-player"] = { value: "Steve", oninput: null };
    const feature = createExportsFeature(deps);
    feature.renderExportsPanel();
    deps.elements["#export-resource"].onchange();
    deps.elements["#export-player"].oninput();
    expect(feature.exportUrl()).toContain("player=Steve");
    expect(feature.exportUrl()).toContain("days=0");
  });

  test("the period and limit selections reach the request", () => {
    const deps = makeDeps();
    deps.elements["#export-resource"] = { value: "activity", onchange: null };
    deps.elements["#export-days"] = { value: "7", onchange: null };
    const feature = createExportsFeature(deps);
    feature.renderExportsPanel();
    deps.elements["#export-resource"].onchange();
    deps.elements["#export-days"].onchange();
    expect(feature.exportUrl()).toContain("days=7");

    const analytics = makeDeps();
    analytics.elements["#export-limit"] = { value: "25", onchange: null };
    const other = createExportsFeature(analytics);
    other.renderExportsPanel();
    analytics.buttons["[data-export-family]"].analytics.onclick();
    analytics.elements["#export-limit"].onchange();
    expect(other.exportUrl()).toContain("limit=25");
  });
});

describe("createExportsFeature — running an export", () => {
  test("a completed export hands the URL to the browser and confirms", async () => {
    const deps = makeDeps();
    deps.elements["#export-download"] = { onclick: null };
    createExportsFeature(deps).renderExportsPanel();
    await deps.elements["#export-download"].onclick();
    expect(deps.download).toHaveBeenCalledWith("/api/exports/players/profiles?format=json");
    expect(deps.toast).toHaveBeenCalledWith("Export ready");
  });

  test("a refusal is surfaced as an error and nothing is announced as ready", async () => {
    const deps = makeDeps();
    deps.elements["#export-download"] = { onclick: null };
    deps.download.mockRejectedValue(Object.assign(new Error("too large"), {
      status: 422, payload: { limit: "record", measured: 20000, allowed: 10000 },
    }));
    createExportsFeature(deps).renderExportsPanel();
    await deps.elements["#export-download"].onclick();
    expect(deps.toast).toHaveBeenCalledWith(expect.stringContaining("20000"), true);
    expect(deps.toast).not.toHaveBeenCalledWith("Export ready");
  });

  test("a blocked scope never reaches the browser", async () => {
    const deps = makeDeps();
    deps.elements["#export-resource"] = { value: "sessions", onchange: null };
    deps.elements["#export-download"] = { onclick: null };
    const feature = createExportsFeature(deps);
    feature.renderExportsPanel();
    deps.elements["#export-resource"].onchange();
    if (deps.elements["#export-download"].onclick) {
      await deps.elements["#export-download"].onclick();
    }
    expect(deps.download).not.toHaveBeenCalled();
  });
});
