let source = null;

export function connectEventStream(onStateEvent) {
  if (source) return source;
  source = new EventSource("/api/events");
  source.addEventListener("state", (message) => onStateEvent(JSON.parse(message.data)));
  source.onerror = () => {
    // EventSource reconnects automatically and sends Last-Event-ID.
  };
  return source;
}
