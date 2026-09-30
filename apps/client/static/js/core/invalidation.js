export function connectInvalidation({ connectEventStream, loadState, refreshStatus, setStatus, schedule = setTimeout, cancel = clearTimeout }) {
  let timer = null;
  let pendingServerEvent = false;
  let pendingStateEvent = null;
  connectEventStream((event) => {
    if (typeof event?.topic !== "string") return;
    if (event.topic !== "state.changed" && !event.topic.startsWith("server.")) return;
    if (event.topic.startsWith("server.")) pendingServerEvent = true;
    if (event.topic === "state.changed") pendingStateEvent = event;
    cancel(timer);
    timer = schedule(async () => {
      const needsStatus = pendingServerEvent;
      const stateEvent = pendingStateEvent;
      pendingServerEvent = false;
      pendingStateEvent = null;
      await loadState(stateEvent);
      if (needsStatus) setStatus(await refreshStatus());
    }, 300);
  });
}
