export function connectInvalidation({ connectEventStream, loadState, refreshStatus, setStatus, schedule = setTimeout, cancel = clearTimeout }) {
  let timer = null;
  connectEventStream((event) => {
    if (event.topic !== "state.changed" && !event.topic.startsWith("server.")) return;
    cancel(timer);
    timer = schedule(async () => {
      await loadState();
      if (event.topic.startsWith("server.")) setStatus(await refreshStatus());
    }, 300);
  });
}
