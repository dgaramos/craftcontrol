export function connectInvalidation({ connectEventStream, loadState, refreshStatus, setStatus, schedule = setTimeout, cancel = clearTimeout }) {
  let timer = null;
  let pendingServerEvent = false;
  connectEventStream((event) => {
    if (event.topic !== "state.changed" && !event.topic.startsWith("server.")) return;
    if (event.topic.startsWith("server.")) pendingServerEvent = true;
    cancel(timer);
    timer = schedule(async () => {
      const needsStatus = pendingServerEvent;
      pendingServerEvent = false;
      await loadState();
      if (needsStatus) setStatus(await refreshStatus());
    }, 300);
  });
}
