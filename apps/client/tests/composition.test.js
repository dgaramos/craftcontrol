/** @jest-environment jsdom */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { jest } from "@jest/globals";
import { startApplication } from "../static/js/composition.js";

describe("application world composition", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    document.documentElement.innerHTML = readFileSync(join(process.cwd(), "templates", "index.html"), "utf8");
    window.matchMedia = jest.fn(() => ({ matches: false, addEventListener: jest.fn() }));
    window.scrollTo = jest.fn();
    globalThis.requestAnimationFrame = (callback) => callback();
    globalThis.fetch = jest.fn(() => new Promise(() => {}));
    globalThis.EventSource = class {};
    HTMLDialogElement.prototype.close = jest.fn();
    HTMLDialogElement.prototype.showModal = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test("locale refresh preserves the observed-at projection without reanchoring", () => {
    let now = 1_000_000;
    jest.spyOn(Date, "now").mockImplementation(() => now);
    const app = startApplication();
    app.showWorld({
      world: { daytime: 1000, day: 4, weather: "clear" },
      domains: { world: { observed_at: 955 } },
    }, { partial: false, keys: ["daytime", "day", "weather"] });
    expect(Number(document.querySelector('[data-world="ticks"]').textContent.replace(/\D/g, ""))).toBe(1900);

    now += 45_000;
    app.applyLocale();

    expect(Number(document.querySelector('[data-world="ticks"]').textContent.replace(/\D/g, ""))).toBe(2800);
  });

  test("an unrelated state change preserves the partial-world notice", async () => {
    let now = 1_000_000;
    jest.spyOn(Date, "now").mockImplementation(() => now);
    const app = startApplication();
    const snapshot = {
      settings: {}, gamerules: {}, players: [], online: 0, max_players: 10,
      world: { daytime: 1000, day: 4, weather: "clear" },
      domains: { world: { observed_at: 955 } },
    };
    app.showWorld(snapshot, { domains: ["world"], partial: true, keys: ["daytime", "day"] });
    expect(document.querySelector("[data-world-observation]").hidden).toBe(false);
    now += 45_000;
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => snapshot });

    await app.loadState({ topic: "state.changed", payload: { domains: ["settings"] } });

    expect(document.querySelector("[data-world-observation]").hidden).toBe(false);
    expect(Number(document.querySelector('[data-world="ticks"]').textContent.replace(/\D/g, ""))).toBe(2800);
  });
});
