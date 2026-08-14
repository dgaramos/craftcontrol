import { connectInvalidation } from "../static/js/core/invalidation.js";

function makeSetup(overrides = {}) {
  const loadState = jest.fn().mockResolvedValue();
  const refreshStatus = jest.fn().mockResolvedValue("online");
  const setStatus = jest.fn();
  let scheduledFn = null;
  let scheduledTimer = null;
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

  test("schedules loadState on state.changed", () => {
    const { listener, schedule } = makeSetup();
    listener({ topic: "state.changed" });
    expect(schedule).toHaveBeenCalled();
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
});
