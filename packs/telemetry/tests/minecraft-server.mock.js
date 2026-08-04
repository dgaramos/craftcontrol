class Signal {
  constructor() { this.handlers = []; }
  subscribe(handler) { this.handlers.push(handler); }
  emit(event) { for (const handler of this.handlers) handler(event); }
}

const properties = new Map();

export const world = {
  afterEvents: {
    playerJoin: new Signal(),
    playerLeave: new Signal(),
    playerSpawn: new Signal(),
    entityDie: new Signal(),
    entityHurt: new Signal(),
    playerBreakBlock: new Signal(),
    playerPlaceBlock: new Signal(),
    playerDimensionChange: new Signal(),
  },
  players: [],
  getAllPlayers() { return this.players; },
  getDynamicProperty(key) { return properties.get(key); },
  setDynamicProperty(key, value) { properties.set(key, value); },
  getDynamicPropertyIds() { return [...properties.keys()]; },
};

export function setMockDynamicProperty(key, value) { properties.set(key, value); }
export function getMockDynamicProperty(key) { return properties.get(key); }

export const system = {
  afterEvents: { scriptEventReceive: new Signal() },
  intervals: [],
  run(handler) { handler(); },
  runInterval(handler) { this.intervals.push(handler); },
  runTimeout(handler) { handler(); },
};
