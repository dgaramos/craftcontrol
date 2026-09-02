import { jest } from "@jest/globals";
import { tabFromLocation, persistTab } from "../../static/js/core/route.js";

function loc(hash) {
  return { hash };
}

describe("tabFromLocation", () => {
  test("empty hash defaults to home", () => expect(tabFromLocation(loc(""))).toBe("home"));
  test("unknown hash defaults to home", () => expect(tabFromLocation(loc("#/unknown"))).toBe("home"));
  test("#/world maps to world", () => expect(tabFromLocation(loc("#/world"))).toBe("world"));
  test("#/players maps to __players__", () => expect(tabFromLocation(loc("#/players"))).toBe("__players__"));
  test("#/data maps to analytics", () => expect(tabFromLocation(loc("#/data"))).toBe("analytics"));
  test("#/rules maps to rules", () => expect(tabFromLocation(loc("#/rules"))).toBe("rules"));
  test("#/server maps to server", () => expect(tabFromLocation(loc("#/server"))).toBe("server"));
  test("#/home maps to home", () => expect(tabFromLocation(loc("#/home"))).toBe("home"));
  test("strips query string from hash", () =>
    expect(tabFromLocation(loc("#/world?foo=bar"))).toBe("world")
  );
});

describe("persistTab", () => {
  test("calls replaceState when hash differs", () => {
    const history = { replaceState: jest.fn() };
    persistTab("world", history, loc(""));
    expect(history.replaceState).toHaveBeenCalledWith(null, "", "#/world");
  });

  test("skips replaceState when hash already matches", () => {
    const history = { replaceState: jest.fn() };
    persistTab("world", history, loc("#/world"));
    expect(history.replaceState).not.toHaveBeenCalled();
  });

  test("unknown tab defaults to home route", () => {
    const history = { replaceState: jest.fn() };
    persistTab("nonexistent", history, loc(""));
    expect(history.replaceState).toHaveBeenCalledWith(null, "", "#/home");
  });
});
