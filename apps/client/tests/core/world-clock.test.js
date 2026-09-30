import { createWorldClock } from "../../static/js/core/world-clock.js";

describe("world clock projection", () => {
  test("compensates observation age forward with the correct magnitude", () => {
    let now = 1_000_000;
    const clock = createWorldClock(() => now);

    expect(clock.anchor(1000, 900)).toBe(3000);

    now += 550;
    expect(clock.current()).toBe(3011);
  });

  test("a fresh observation reanchors the projected clock", () => {
    let now = 1_000_000;
    const clock = createWorldClock(() => now);
    clock.anchor(1000, 1000);
    now += 45_000;
    expect(clock.current()).toBe(1900);

    expect(clock.anchor(5000, 1045)).toBe(5000);
  });

  test("clear removes the current projection", () => {
    const clock = createWorldClock(() => 1_000_000);
    clock.anchor(1000, 1000);

    clock.clear();

    expect(clock.current()).toBeNaN();
  });
});
