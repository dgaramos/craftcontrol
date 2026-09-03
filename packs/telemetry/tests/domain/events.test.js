import { jest, beforeEach, test, expect } from "@jest/globals";

const mockSubscribeWorldEvent = jest.fn();

jest.unstable_mockModule("../../behavior_pack/scripts/adapters/capabilities.js", () => ({
  subscribeWorldEvent: mockSubscribeWorldEvent,
}));

const { registerEvents } = await import("../../behavior_pack/scripts/domain/events.js");

const EXPECTED_SIGNALS = [
  "playerJoin",
  "playerLeave",
  "playerSpawn",
  "entityDie",
  "entityHurt",
  "playerBreakBlock",
  "playerPlaceBlock",
  "playerDimensionChange",
];

beforeEach(() => {
  jest.clearAllMocks();
});

test("registerEvents registers all eight world event signals", () => {
  registerEvents({});

  const registeredSignals = mockSubscribeWorldEvent.mock.calls.map(([signal]) => signal);
  expect(registeredSignals.sort()).toEqual(EXPECTED_SIGNALS.sort());
});

test("registerEvents calls each subscribeWorldEvent with a capability label and handler", () => {
  registerEvents({});

  for (const call of mockSubscribeWorldEvent.mock.calls) {
    const [signal, label, handler] = call;
    expect(typeof signal).toBe("string");
    expect(typeof label).toBe("string");
    expect(typeof handler).toBe("function");
  }
});

test("playerJoin handler invokes onPlayerJoin with the event", () => {
  const onPlayerJoin = jest.fn();
  registerEvents({ onPlayerJoin });

  const [, , handler] = mockSubscribeWorldEvent.mock.calls.find(([s]) => s === "playerJoin");
  const event = { playerName: "VonCrush" };
  handler(event);

  expect(onPlayerJoin).toHaveBeenCalledWith(event);
});

test("playerLeave handler invokes onPlayerLeave with the event", () => {
  const onPlayerLeave = jest.fn();
  registerEvents({ onPlayerLeave });

  const [, , handler] = mockSubscribeWorldEvent.mock.calls.find(([s]) => s === "playerLeave");
  const event = { playerId: "p1", playerName: "VonCrush" };
  handler(event);

  expect(onPlayerLeave).toHaveBeenCalledWith(event);
});

test("registerEvents does not throw when a handler is not provided", () => {
  // Pass empty handlers — none of the callbacks should be invoked during registration
  expect(() => registerEvents({})).not.toThrow();
});

test("registerEvents does not throw when no argument is passed", () => {
  expect(() => registerEvents()).not.toThrow();
});
