import { jest } from "@jest/globals";

describe("state module", () => {
  let storageMock;

  beforeEach(() => {
    storageMock = (() => {
      const store = {};
      return {
        getItem: jest.fn((k) => store[k] ?? null),
        setItem: jest.fn((k, v) => { store[k] = String(v); }),
        removeItem: jest.fn((k) => { delete store[k]; }),
        clear: jest.fn(() => { Object.keys(store).forEach((k) => delete store[k]); }),
      };
    })();
    Object.defineProperty(global, "localStorage", { value: storageMock, writable: true, configurable: true });
    Object.defineProperty(global, "window", { value: { location: { hash: "" } }, writable: true, configurable: true });
    jest.resetModules();
  });

  test("defaults locale to pt when localStorage is empty", async () => {
    storageMock.getItem.mockReturnValue(null);
    const { state } = await import("../static/js/core/state.js");
    expect(state.locale).toBe("pt");
  });

  test("uses stored craftcontrol-locale when valid", async () => {
    storageMock.getItem.mockImplementation((k) => k === "craftcontrol-locale" ? "en" : null);
    const { state } = await import("../static/js/core/state.js");
    expect(state.locale).toBe("en");
  });

  test("uses legacy manager-locale when craftcontrol-locale is absent", async () => {
    storageMock.getItem.mockImplementation((k) => k === "manager-locale" ? "es" : null);
    const { state } = await import("../static/js/core/state.js");
    expect(state.locale).toBe("es");
  });

  test("defaults to pt for invalid stored locale", async () => {
    storageMock.getItem.mockReturnValue("zh");
    const { state } = await import("../static/js/core/state.js");
    expect(state.locale).toBe("pt");
  });

  test("initial tab is home for empty hash", async () => {
    storageMock.getItem.mockReturnValue(null);
    const { state } = await import("../static/js/core/state.js");
    expect(state.tab).toBe("home");
  });

  test("initial tab is home for unknown hash", async () => {
    global.window = { location: { hash: "#/unknown-tab", replace: jest.fn() }, history: { replaceState: jest.fn() } };
    jest.resetModules();
    storageMock.getItem.mockReturnValue(null);
    const { state } = await import("../static/js/core/state.js");
    expect(state.tab).toBe("home");
  });

  test("initial tab reflects known permitted hash", async () => {
    global.window = { location: { hash: "#/world", replace: jest.fn() }, history: { replaceState: jest.fn() } };
    jest.resetModules();
    storageMock.getItem.mockReturnValue(null);
    const { state } = await import("../static/js/core/state.js");
    expect(state.tab).toBe("world");
  });

  test("state has expected top-level keys", async () => {
    storageMock.getItem.mockReturnValue(null);
    const { state } = await import("../static/js/core/state.js");
    for (const key of ["schema", "config", "gamerules", "players", "online", "maxPlayers", "changes", "tab", "tabs", "status", "analytics", "locale", "user"]) {
      expect(state).toHaveProperty(key);
    }
  });

  test("tabs array contains the six expected tabs", async () => {
    storageMock.getItem.mockReturnValue(null);
    const { state } = await import("../static/js/core/state.js");
    expect(state.tabs).toEqual(["home", "world", "players", "analytics", "rules", "server"]);
  });

  test("notifies only subscribers for the changed state key", async () => {
    const { createState } = await import("../static/js/core/state.js");
    const reactiveState = createState({ players: [], tab: "home" });
    const playersChanged = jest.fn();
    const tabChanged = jest.fn();
    reactiveState.subscribe("players", playersChanged);
    reactiveState.subscribe("tab", tabChanged);

    reactiveState.players = ["Alex"];

    expect(playersChanged).toHaveBeenCalledWith(["Alex"], []);
    expect(tabChanged).not.toHaveBeenCalled();
  });

  test("stops notifying after a subscription is removed", async () => {
    const { createState } = await import("../static/js/core/state.js");
    const reactiveState = createState({ tab: "home" });
    const callback = jest.fn();
    const unsubscribe = reactiveState.subscribe("tab", callback);

    unsubscribe();
    reactiveState.tab = "world";

    expect(callback).not.toHaveBeenCalled();
  });

  test("coalesces notifications made in one batch", async () => {
    const { createState } = await import("../static/js/core/state.js");
    const reactiveState = createState({ config: {}, gamerules: {} });
    const configChanged = jest.fn();
    const gamerulesChanged = jest.fn();
    reactiveState.subscribe("config", configChanged);
    reactiveState.subscribe("gamerules", gamerulesChanged);

    reactiveState.batch(() => {
      reactiveState.config = { SERVER_NAME: "Craft" };
      reactiveState.config = { SERVER_NAME: "Control" };
      reactiveState.gamerules = { keepinventory: "true" };
    });

    expect(configChanged).toHaveBeenCalledTimes(1);
    expect(configChanged).toHaveBeenCalledWith({ SERVER_NAME: "Control" });
    expect(gamerulesChanged).toHaveBeenCalledWith({ keepinventory: "true" });
  });

  test("preserves errors raised by a nested batch", async () => {
    const { createState } = await import("../static/js/core/state.js");
    const reactiveState = createState({ config: {} });

    expect(() => reactiveState.batch(() => reactiveState.batch(() => {
      throw new Error("nested failure");
    }))).toThrow("nested failure");
  });
});
