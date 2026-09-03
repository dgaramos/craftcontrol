export function captureConsole(method) {
  const original = console[method];
  const lines = [];

  console[method] = (...args) => lines.push(args.map(String).join(" "));

  return {
    lines,
    restore() {
      console[method] = original;
    },
  };
}
