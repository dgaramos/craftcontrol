import { jest } from "@jest/globals";
import { connectInvalidation } from "../../static/js/core/invalidation.js";

function makeSetup(overrides = {}) {
  const loadState = jest.fn().mockResolvedValue();
  const refreshStatus = jest.fn().mockResolvedValue("online");
  const setStatus = jest.fn();
  let scheduledFn = null;
  let scheduledTimer = 0;
  const schedule = jest.fn((fn, _delay) => { scheduledFn = fn; return ++scheduledTimer; });
  const cancel = jest.fn();
  let listener = null;
  const connectEventStream = jest.fn((cb) => { listener = cb; });

  connectInvalidation({ connectEventStream, loadState, refreshStatus, setStatus, schedule, cancel, ...overrides });

  return { listener, loadState, refreshStatus, setStatus, schedule, cancel };
}

describe("connectInvalidation", () => {
  test("registers a stream listener", () => {
    const { listener } = makeSetup();
    expect(typeof listener).toBe("function");
  });

  test("ignores events not matching state.changed or server.*", () => {
    const { listener, schedule } = makeSetup();
    listener({ topic: "player.joined" });
    expect(schedule).not.toHaveBeenCalled();
  });

  test("ignores events without a string topic", () => {
    const { listener, schedule } = makeSetup();
    listener(null);
    listener({});
    expect(schedule).not.toHaveBeenCalled();
  });

  test("schedules loadState on state.changed", () => {
    const { listener, schedule } = makeSetup();
    listener({ topic: "state.changed" });
    expect(schedule).toHaveBeenCalled();
  });

  test("uses default scheduling dependencies and refreshes only state on state.changed", async () => {
    let listener;
    const connectEventStream = jest.fn((callback) => { listener = callback; });
    const loadState = jest.fn().mockResolvedValue();
    const refreshStatus = jest.fn();
    const setStatus = jest.fn();
    connectInvalidation({ connectEventStream, loadState, refreshStatus, setStatus });

    listener({ topic: "ignored" });
    expect(loadState).not.toHaveBeenCalled();

    const schedule = jest.fn((callback) => callback());
    connectInvalidation({ connectEventStream, loadState, refreshStatus, setStatus, schedule });
    listener({ topic: "state.changed" });
    await Promise.resolve();
    expect(loadState).toHaveBeenCalled();
    expect(refreshStatus).not.toHaveBeenCalled();
    expect(setStatus).not.toHaveBeenCalled();
  });

  test("schedules loadState on server.* topics", () => {
    const { listener, schedule } = makeSetup();
    listener({ topic: "server.started" });
    expect(schedule).toHaveBeenCalled();
  });

  test("cancels previous timer before scheduling a new one", () => {
    const { listener, cancel, schedule } = makeSetup();
    listener({ topic: "state.changed" });
    listener({ topic: "state.changed" });
    expect(cancel).toHaveBeenCalledTimes(2);
    expect(schedule).toHaveBeenCalledTimes(2);
  });

  test("calls loadState and setStatus after debounce on server.* event", async () => {
    let fn;
    const schedule = jest.fn((cb) => { fn = cb; return 1; });
    const { loadState, refreshStatus, setStatus } = makeSetup({ schedule });
    const { listener } = makeSetup({ schedule, loadState, refreshStatus, setStatus });
    listener({ topic: "server.stopped" });
    await fn();
    expect(loadState).toHaveBeenCalled();
    expect(setStatus).toHaveBeenCalledWith("online");
  });

  test("preserves a coalesced server status refresh after state.changed", async () => {
    let callback;
    const schedule = jest.fn((fn) => { callback = fn; return 1; });
    const { listener, refreshStatus, setStatus } = makeSetup({ schedule });

    listener({ topic: "server.started" });
    listener({ topic: "state.changed" });
    await callback();

    expect(refreshStatus).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalledWith("online");
  });
});
