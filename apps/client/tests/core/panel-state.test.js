import { indicatorState, isNightTick, worldPresentation } from "../../static/js/core/panel-state.js";

describe("indicatorState", () => {
  test("shows nothing when there is nothing to report", () => {
    expect(indicatorState()).toEqual({ showOperation: false, showChanges: false, stalled: false });
  });

  test("shows the changes bar only when changes exist", () => {
    expect(indicatorState({ changesCount: 0 }).showChanges).toBe(false);
    expect(indicatorState({ changesCount: 2 }).showChanges).toBe(true);
  });

  test("never shows both bars at once — the operation wins", () => {
    // This is the pairing the user reported twice: both strips on screen.
    const running = indicatorState({ changesCount: 3, operationActive: true });
    expect(running).toEqual({ showOperation: true, showChanges: false, stalled: false });

    const stalled = indicatorState({ changesCount: 3, operationStalled: true });
    expect(stalled).toEqual({ showOperation: true, showChanges: false, stalled: true });
  });

  test("an unresponsive operation still holds the bar, flagged as stalled", () => {
    // operationActive goes false so the app unblocks, but the operation must
    // not vanish silently: it still needs a decision.
    const state = indicatorState({ operationActive: false, operationStalled: true });
    expect(state.showOperation).toBe(true);
    expect(state.stalled).toBe(true);
  });
});

describe("isNightTick", () => {
  test("covers the Minecraft night window", () => {
    expect(isNightTick(12999)).toBe(false);
    expect(isNightTick(13000)).toBe(true);
    expect(isNightTick(22999)).toBe(true);
    expect(isNightTick(23000)).toBe(false);
  });

  test("an unknown clock is not night", () => {
    expect(isNightTick(NaN)).toBe(false);
    expect(isNightTick(undefined)).toBe(false);
  });
});

describe("worldPresentation", () => {
  test("clear weather follows the clock", () => {
    expect(worldPresentation({ weather: "clear", daytime: 6000 }))
      .toEqual({ timeIcon: "ui-sun", weatherIcon: "ui-sun", weatherKey: "clear" });
    expect(worldPresentation({ weather: "clear", daytime: 18000 }))
      .toEqual({ timeIcon: "ui-moon", weatherIcon: "ui-moon", weatherKey: "clear-night" });
  });

  test("thunder has its own symbol, not the rain one", () => {
    // These shared ui-rain before, so a storm looked like ordinary rain.
    expect(worldPresentation({ weather: "thunder", daytime: 6000 }).weatherIcon).toBe("ui-thunder");
    expect(worldPresentation({ weather: "rain", daytime: 6000 }).weatherIcon).toBe("ui-rain");
  });

  test("rain and thunder read the same by day or night, but the clock icon still turns", () => {
    const day = worldPresentation({ weather: "rain", daytime: 6000 });
    const night = worldPresentation({ weather: "rain", daytime: 18000 });
    expect(day.weatherIcon).toBe(night.weatherIcon);
    expect(day.timeIcon).toBe("ui-sun");
    expect(night.timeIcon).toBe("ui-moon");
  });

  test("an unknown world falls back to the daylight reading", () => {
    expect(worldPresentation()).toEqual({ timeIcon: "ui-sun", weatherIcon: "ui-sun", weatherKey: "clear" });
  });
});
