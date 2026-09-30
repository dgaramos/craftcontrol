import { createWorldClock } from "../../static/js/core/world-clock.js";
import { createWorldSnapshotController } from "../../static/js/core/world-snapshot.js";

describe("world snapshot composition", () => {
  test("locale refresh preserves the observation anchor and SSE reanchors it", () => {
    let now = 1_000_000;
    const controller = createWorldSnapshotController({ clock: createWorldClock(() => now) });

    expect(controller.showWorld({
      world: { daytime: 1000, weather: "clear" },
      domains: { world: { observed_at: 955 } },
    }).daytime).toBe(1900);

    now += 45_000;
    expect(controller.refreshWorldCells().daytime).toBe(2800);

    expect(controller.showWorld({
      world: { daytime: 5000, weather: "rain" },
      domains: { world: { observed_at: 1045 } },
    }).daytime).toBe(5000);
  });

  test("retains weather while marking an incomplete observation", () => {
    const controller = createWorldSnapshotController({ clock: createWorldClock(() => 1_000_000) });

    const projection = controller.showWorld(
      { world: { daytime: 1000, weather: "clear" }, domains: { world: { observed_at: 1000 } } },
      { partial: true, keys: ["daytime"] },
    );

    expect(projection.world.weather).toBe("clear");
    expect(projection.weatherUnobserved).toBe(true);
    expect(controller.refreshWorldCells().weatherUnobserved).toBe(true);
  });

  test("does not reanchor retained daytime when a partial observation omitted it", () => {
    let now = 1_000_000;
    const controller = createWorldSnapshotController({ clock: createWorldClock(() => now) });
    controller.showWorld(
      { world: { daytime: 1000, weather: "clear" }, domains: { world: { observed_at: 1000 } } },
      { partial: false, keys: ["daytime", "weather"] },
    );
    now += 45_000;

    const projection = controller.showWorld(
      { world: { daytime: 1000, weather: "rain" }, domains: { world: { observed_at: 1045 } } },
      { partial: true, keys: ["weather"] },
    );

    expect(projection.daytime).toBe(1900);
    expect(projection.world.weather).toBe("rain");
  });
});
