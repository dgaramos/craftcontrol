import { createNavTrail } from "../../static/js/core/route.js";

describe("createNavTrail", () => {
  test("an inner screen remembers where it was opened from", () => {
    // Rules is reachable from Home and from the Server hub. A hard-coded
    // destination would send half the users somewhere they never were.
    const fromHome = createNavTrail();
    fromHome.record("rules", "home");
    expect(fromHome.peek()).toBe("home");

    const fromServer = createNavTrail();
    fromServer.record("rules", "server");
    expect(fromServer.peek()).toBe("server");
  });

  test("unwinds one step at a time along the real path", () => {
    const trail = createNavTrail();
    trail.record("world", "server");
    trail.record("__time__", "world");
    expect(trail.peek()).toBe("world");
    expect(trail.back()).toBe("world");
    // Returning must not be recorded as a step forward, or back would bounce.
    trail.record("world", "__time__");
    expect(trail.peek()).toBe("server");
    expect(trail.back()).toBe("server");
  });

  test("landing on a root tab clears the trail", () => {
    const trail = createNavTrail();
    trail.record("world", "server");
    trail.record("__time__", "world");
    expect(trail.depth).toBe(2);
    trail.record("home", "__time__");
    expect(trail.depth).toBe(0);
    expect(trail.peek()).toBe("home");
  });

  test("falls back to home when there is nothing to unwind", () => {
    const trail = createNavTrail();
    expect(trail.peek()).toBe("home");
    expect(trail.back()).toBe("home");
  });

  test("ignores non-transitions and stays bounded", () => {
    const trail = createNavTrail({ limit: 3 });
    trail.record("rules", "rules");
    trail.record("rules", null);
    expect(trail.depth).toBe(0);
    ["a", "b", "c", "d", "e"].forEach((tab, i, all) => trail.record(tab, all[i - 1] ?? "world"));
    expect(trail.depth).toBe(3);
  });
});
