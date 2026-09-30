export function createWorldClock(now = Date.now) {
  let anchorDaytime = NaN;
  let anchorAt = NaN;

  return {
    anchor(daytime, observedAt) {
      const anchoredAt = now();
      const observationAge = Number.isFinite(observedAt)
        ? Math.max(0, anchoredAt / 1000 - observedAt) * 20
        : 0;
      anchorDaytime = (daytime + observationAge) % 24000;
      anchorAt = anchoredAt;
      return this.current();
    },
    current() {
      return (anchorDaytime + Math.max(0, now() - anchorAt) / 50) % 24000;
    },
    clear() {
      anchorDaytime = NaN;
      anchorAt = NaN;
    },
  };
}
