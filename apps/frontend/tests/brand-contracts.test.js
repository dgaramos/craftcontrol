import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..");
const STATIC = join(FRONTEND, "static");
const JS = join(STATIC, "js");

function frontendScript() {
  return [
    readFileSync(join(STATIC, "app.js"), "utf8"),
    readFileSync(join(JS, "composition.js"), "utf8"),
    readFileSync(join(JS, "features", "settings", "index.js"), "utf8"),
  ].join("\n");
}

describe("brand contracts — entrypoint structure", () => {
  test("app.js is only bootstrap and composition (≤5 lines)", () => {
    const entrypoint = readFileSync(join(STATIC, "app.js"), "utf8");
    expect(entrypoint.split("\n").length).toBeLessThanOrEqual(5);
  });

  test("app.js calls startApplication", () => {
    const entrypoint = readFileSync(join(STATIC, "app.js"), "utf8");
    expect(entrypoint).toContain("startApplication");
  });

  test("composition.js exports createNavigation", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    expect(composition).toContain("createNavigation");
  });

  test("composition.js exports connectInvalidation", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    expect(composition).toContain("connectInvalidation");
  });

  test("settings feature exports createSettingsFeature", () => {
    const settings = readFileSync(join(JS, "features", "settings", "index.js"), "utf8");
    expect(settings).toContain("createSettingsFeature");
  });
});

describe("brand contracts — CSRF and API versioning", () => {
  test("api.js attaches X-CSRF-Token header", () => {
    const api = readFileSync(join(JS, "api.js"), "utf8");
    expect(api).toContain('headers["X-CSRF-Token"] = csrfToken');
  });

  test("api.js validates csrf_token type", () => {
    const api = readFileSync(join(JS, "api.js"), "utf8");
    expect(api).toContain('typeof data.csrf_token === "string"');
  });

  test("composition.js references api.js?v=7", () => {
    const script = frontendScript();
    expect(script).toContain("./api.js?v=7");
  });

  test("auth.js references api.js?v=7", () => {
    const auth = readFileSync(join(JS, "auth.js"), "utf8");
    expect(auth).toContain("./api.js?v=7");
  });
});

describe("brand contracts — mobile scroll behaviour", () => {
  test("app.css sets overscroll-behavior-y: none", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    expect(css).toContain("overscroll-behavior-y: none");
  });

  test("app.css sets min-height: 100dvh", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    expect(css).toContain("min-height: 100dvh");
  });

  test("app.css sets overflow-x: clip", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    expect(css).toContain("overflow-x: clip");
  });

  test("navigation.js scrolls to top on tab change", () => {
    const nav = readFileSync(join(JS, "core", "navigation.js"), "utf8");
    expect(nav).toContain('window.scrollTo({ top: 0, left: 0, behavior: "auto" })');
  });

  test("index.html references app.css?v=25", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain("/static/app.css?v=25");
  });

  test("index.html references app.js?v=64", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain("/static/app.js?v=64");
  });
});

describe("brand contracts — core module ownership (state and dom)", () => {
  test("composition.js imports from core/state.js?v=7", () => {
    const script = frontendScript();
    expect(script).toContain('from "./core/state.js?v=7"');
  });

  test("composition.js imports from core/dom.js?v=7", () => {
    const script = frontendScript();
    expect(script).toContain('from "./core/dom.js?v=7"');
  });

  test("core/state.js exports state", () => {
    const state = readFileSync(join(JS, "core", "state.js"), "utf8");
    expect(state).toContain("export const state");
  });

  test("core/dom.js exports escapeHtml", () => {
    const dom = readFileSync(join(JS, "core", "dom.js"), "utf8");
    expect(dom).toContain("export function escapeHtml");
  });

  test("composition.js does not inline state", () => {
    const script = frontendScript();
    expect(script).not.toContain("const state = {");
  });

  test("composition.js does not inline escapeHtml", () => {
    const script = frontendScript();
    expect(script).not.toContain("function escapeHtml");
  });
});

describe("brand contracts — component module ownership (feedback and time)", () => {
  test("composition.js imports from components/feedback.js?v=7", () => {
    const script = frontendScript();
    expect(script).toContain('from "./components/feedback.js?v=7"');
  });

  test("composition.js imports from components/time.js?v=7", () => {
    const script = frontendScript();
    expect(script).toContain('from "./components/time.js?v=7"');
  });

  test("components/feedback.js exports toast", () => {
    const feedback = readFileSync(join(JS, "components", "feedback.js"), "utf8");
    expect(feedback).toContain("export function toast");
  });

  test("components/time.js exports timelineTimestamp", () => {
    const time = readFileSync(join(JS, "components", "time.js"), "utf8");
    expect(time).toContain("export function timelineTimestamp");
  });

  test("components/time.js exports formatDuration", () => {
    const time = readFileSync(join(JS, "components", "time.js"), "utf8");
    expect(time).toContain("export function formatDuration");
  });

  test("composition.js does not inline toast", () => {
    const script = frontendScript();
    expect(script).not.toContain("function toast");
  });

  test("composition.js does not inline formatDuration", () => {
    const script = frontendScript();
    expect(script).not.toContain("function formatDuration");
  });
});

describe("brand contracts — players feature composition (regression #156)", () => {
  test("composition.js does not pass bindSegmentedControls as a direct dep to createPlayersFeature", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    const createPlayersCall = composition.slice(composition.indexOf("createPlayersFeature({"), composition.indexOf("});", composition.indexOf("createPlayersFeature({")));
    expect(createPlayersCall).not.toContain("bindSegmentedControls");
  });

  test("composition.js does not pass bindSettingFields as a direct dep to createPlayersFeature", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    const createPlayersCall = composition.slice(composition.indexOf("createPlayersFeature({"), composition.indexOf("});", composition.indexOf("createPlayersFeature({")));
    expect(createPlayersCall).not.toContain("bindSettingFields");
  });
});
