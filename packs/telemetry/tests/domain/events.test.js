import { jest, beforeEach, test, expect } from "@jest/globals";
import { registerEvents } from "../../behavior_pack/scripts/domain/events.js";

const mockSubscribeWorldEvent = jest.fn();

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
  registerEvents({}, mockSubscribeWorldEvent);

  const registeredSignals = mockSubscribeWorldEvent.mock.calls.map(([signal]) => signal);
  expect(registeredSignals.sort()).toEqual(EXPECTED_SIGNALS.sort());
});

test("registerEvents calls each subscribeWorldEvent with a capability label and handler", () => {
  registerEvents({}, mockSubscribeWorldEvent);

  for (const call of mockSubscribeWorldEvent.mock.calls) {
    const [signal, label, handler] = call;
    expect(typeof signal).toBe("string");
    expect(typeof label).toBe("string");
    expect(typeof handler).toBe("function");
  }
});

test("playerJoin handler invokes onPlayerJoin with the event", () => {
  const onPlayerJoin = jest.fn();
  registerEvents({ onPlayerJoin }, mockSubscribeWorldEvent);

  const [, , handler] = mockSubscribeWorldEvent.mock.calls.find(([s]) => s === "playerJoin");
  const event = { playerName: "VonCrush" };
  handler(event);

  expect(onPlayerJoin).toHaveBeenCalledWith(event);
});

test("playerLeave handler invokes onPlayerLeave with the event", () => {
  const onPlayerLeave = jest.fn();
  registerEvents({ onPlayerLeave }, mockSubscribeWorldEvent);

  const [, , handler] = mockSubscribeWorldEvent.mock.calls.find(([s]) => s === "playerLeave");
  const event = { playerId: "p1", playerName: "VonCrush" };
  handler(event);

  expect(onPlayerLeave).toHaveBeenCalledWith(event);
});

test.each([
  ["playerSpawn", "onPlayerSpawn"],
  ["playerDimensionChange", "onPlayerDimensionChange"],
  ["entityDie", "onEntityDie"],
  ["entityHurt", "onEntityHurt"],
  ["playerBreakBlock", "onPlayerBreakBlock"],
  ["playerPlaceBlock", "onPlayerPlaceBlock"],
])("%s handler invokes %s with the event", (signal, handlerName) => {
  const handler = jest.fn();
  registerEvents({ [handlerName]: handler }, mockSubscribeWorldEvent);

  const [, , subscribedHandler] = mockSubscribeWorldEvent.mock.calls.find(([registeredSignal]) => registeredSignal === signal);
  const event = { signal };
  subscribedHandler(event);

  expect(handler).toHaveBeenCalledWith(event);
});

test("registerEvents does not throw when a handler is not provided", () => {
  // Pass empty handlers — none of the callbacks should be invoked during registration
  expect(() => registerEvents({}, mockSubscribeWorldEvent)).not.toThrow();
});

test("registerEvents does not throw when no argument is passed", () => {
  expect(() => registerEvents()).not.toThrow();
});
