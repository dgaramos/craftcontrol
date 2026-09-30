export function createWorldSnapshotController({ clock }) {
  let world = {};
  let observation = null;

  function view() {
    return {
      world,
      daytime: clock.current(),
      weatherUnobserved: observation?.partial === true
        && Array.isArray(observation.keys)
        && !observation.keys.includes("weather"),
    };
  }

  return {
    showWorld(snapshot, nextObservation = undefined) {
      world = snapshot.world || {};
      if (nextObservation !== undefined) observation = nextObservation;
      const daytime = Number(world.daytime);
      const observedDaytime = nextObservation === null
        || (nextObservation !== undefined && (
          !Array.isArray(nextObservation.keys) || nextObservation.keys.includes("daytime")
        ));
      if (Number.isFinite(daytime) && observedDaytime) {
        clock.anchor(daytime, Number(snapshot.domains?.world?.observed_at));
      } else if (!Number.isFinite(daytime)) {
        clock.clear();
      }
      return view();
    },

    refreshWorldCells() {
      return view();
    },
  };
}
