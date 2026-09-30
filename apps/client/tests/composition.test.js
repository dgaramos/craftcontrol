/** @jest-environment jsdom */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { jest } from "@jest/globals";

async function settle() {
  for (let turn = 0; turn < 10; turn += 1) await Promise.resolve();
}

describe("application world composition", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    document.documentElement.innerHTML = readFileSync(join(process.cwd(), "templates", "index.html"), "utf8");
    window.matchMedia = jest.fn(() => ({ matches: false, addEventListener: jest.fn() }));
    window.scrollTo = jest.fn();
    globalThis.requestAnimationFrame = (callback) => callback();
    HTMLDialogElement.prototype.close = jest.fn();
    HTMLDialogElement.prototype.showModal = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test("public locale, SSE, and refresh paths never reanchor unobserved daytime", async () => {
    jest.unstable_mockModule("../static/js/auth.js?v=8", () => ({
      requireSession: jest.fn().mockResolvedValue({ name: "Owner", role: "owner", capabilities: ["*"] }),
      showSessions: jest.fn(),
      showPasswordChange: jest.fn(),
    }));
    const { startApplication } = await import("../static/js/composition.js");
    let now = 1_000_000;
    jest.spyOn(Date, "now").mockImplementation(() => now);
    const snapshot = {
      settings: {}, gamerules: {}, players: [], online: 0, max_players: 10,
      world: { daytime: 1000, day: 4, weather: "clear" },
      domains: { world: { observed_at: 955 } },
    };
    globalThis.fetch = jest.fn(async (url) => {
      const payloads = {
        "/api/schema": { settings: {}, gamerules: {} },
        "/api/state": snapshot,
        "/api/status": { online: true },
        "/api/telemetry-pack": {},
        "/api/operations/latest": { operation: null },
        "/version.json": { service: "frontend", version: "test" },
        "/api/refresh": {},
      };
      return { ok: true, status: 200, json: async () => payloads[url] || {} };
    });
    const streams = [];
    globalThis.EventSource = class {
      constructor(url) { this.url = url; this.listeners = {}; streams.push(this); }
      addEventListener(name, listener) { this.listeners[name] = listener; }
      emit(name, data) { this.listeners[name]?.({ data: JSON.stringify(data) }); }
    };

    startApplication();
    await settle();
    expect(Number(document.querySelector('[data-world="ticks"]').textContent.replace(/\D/g, ""))).toBe(1900);

    now += 45_000;
    document.querySelector('[data-locale="en"]').click();
    expect(Number(document.querySelector('[data-world="ticks"]').textContent.replace(/\D/g, ""))).toBe(2800);

    const stateStream = streams.find((stream) => stream.url === "/api/events");
    stateStream.emit("state", { topic: "state.changed", payload: { domains: ["world"], partial: true, keys: ["daytime", "day"] } });
    await jest.advanceTimersByTimeAsync(300);
    expect(document.querySelector("[data-world-observation]").hidden).toBe(false);

    stateStream.emit("state", { topic: "state.changed", payload: { domains: ["settings"], keys: ["SERVER_NAME"] } });
    await jest.advanceTimersByTimeAsync(300);
    expect(document.querySelector("[data-world-observation]").hidden).toBe(false);
    expect(Number(document.querySelector('[data-world="ticks"]').textContent.replace(/\D/g, ""))).toBe(2800);

    document.querySelector("#refresh").click();
    await settle();
    await jest.advanceTimersByTimeAsync(1800);
    expect(Number(document.querySelector('[data-world="ticks"]').textContent.replace(/\D/g, ""))).toBe(2800);
  });
});
