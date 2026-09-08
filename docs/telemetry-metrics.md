# Opt-in telemetry metrics

The Telemetry Pack already collects joins, deaths, kills, block totals, damage
and sampled movement. Epic #21 adds item use and interaction metrics, which are
closer to a player's behaviour than anything collected so far. This document is
the policy those additions follow: what may be counted, how far it may grow,
how it is switched on, and what happens when the runtime cannot provide it.

It exists so the pack does not become an invasive or unbounded collector one
useful-looking field at a time.

## What may be collected

Only bounded aggregates, per player, in the shape the pack already uses: a
counter, and optionally a map from a Minecraft identifier to a count.

**Item use** — how often a player used an item, and of which types. One counter
(`itemsUsed`) and one bounded map (`usedByType`).

**Interactions** — how often a player interacted with a block, an entity or a
container, and with which types. One counter and one bounded map per kind
(`blockInteractions` / `interactedBlocksByType`, `entityInteractions` /
`interactedEntitiesByType`, `containerOpens` / `openedContainersByType`).

A metric that cannot be expressed as a count of a bounded key is out of scope.
That rules out sequences, durations between two actions, and anything that
reconstructs what a player did in order.

## What is never collected

These are excluded by policy, not by omission, and an implementation that finds
a way to obtain them is still forbidden from doing so:

- inventory contents, slot indices, and item quantities held;
- enchantments, durability, and item components;
- custom item, entity or container names — a player-authored name is player
  text, not a game identifier;
- chat, sign text, book contents, and any other free-form input;
- continuous location: interaction metrics carry no coordinates at all, and the
  existing five-second movement sampling stays the only positional signal.

The existing rule that public payloads never expose XUIDs applies unchanged.

## Bounds

Keys are Minecraft namespaced identifiers (`minecraft:oak_door`). A key that
does not match that shape is discarded rather than stored, which keeps a
player-authored name from becoming a map entry.

Each map is bounded with the eviction the pack already implements: when the
limit is exceeded, the lowest counts are dropped. The counters that accompany
them stay exact, so a total is never distorted by eviction — only the breakdown
loses its long tail.

The block maps this pack already keeps are bounded to `MAX_BLOCK_TYPES` (128).
Opt-in metric maps are bounded to `MAX_METRIC_TYPES` (24), and that number came
from measurement rather than preference: at 128 entries the four maps this epic
adds push a full player shard past the 30 KB dynamic-property budget by more
than half, and a shard that does not fit is a shard the store refuses to write.
At 24 the worst case — every map full of the longest identifiers Minecraft
ships — stays inside the budget. The packing test in the pack is that
measurement, and it fails if a later metric spends the remaining headroom: a
metric enabled at runtime is a metric that must fit at runtime.

## Enabling a metric

Every metric ships disabled. Nothing in this document is collected until an
owner turns it on, and turning one on does not turn on another.

Enablement travels the channel that already exists between the manager and the
pack — the dedicated-server console, where CraftControl sends
`/scriptevent bedrock_telemetry:sync full` today. Metric state arrives the same
way as `/scriptevent bedrock_telemetry:metrics enable <metric>`, is persisted in
its own dynamic property, and survives a restart. A pack that has never been
told anything collects nothing beyond what it collected before this epic.

The state lives outside the player shards on purpose: it is a handful of
booleans that change only on an owner's command, and keeping it separate means a
blocked player-state write can never silently re-enable collection. Every
accepted command is answered with a `metrics.changed` envelope, so the manager
learns the resulting state without asking.

Each metric is independent: enabling item use says nothing about interactions,
and a metric can be disabled without disturbing the others or the aggregates
collected before it.

## When the runtime cannot provide it

Each metric declares a capability, reported in `telemetry.started` and
`snapshot.started` beside the existing ones:

| Capability | Feature |
| --- | --- |
| `itemUse` | `world.afterEvents.itemUse` subscription |
| `blockInteractions` | `playerInteractWithBlock` event subscription |
| `entityInteractions` | `playerInteractWithEntity` event subscription |
| `containerInteractions` | container open detection |

An unsupported capability is reported `supported: false` with its bounded error
string, exactly as today. Collection continues for everything else — a missing
event subscription never stops the pack.

An unsupported metric is **unavailable, not zero**. The panel says the server
cannot report it; it does not draw a zero, because zero is a measurement and
this is the absence of one. This is the same distinction the analytics screens
already make between "nothing observed yet" and "not collected".

## Protocol and recovery

New fields are additive: they appear in `snapshot.player` alongside the existing
aggregates, so protocol schema `1` is unchanged and a consumer that does not
know them ignores them.

Storage version stays at `3`. The design issue expected a bump, and the pack
says otherwise: the loader already normalizes a missing aggregate to zero and a
missing map to empty, so an existing world reads its full history without a
migration. Raising the version would buy nothing and cost a whole-world
migration that writes a backup shard per player — real risk against no
compatibility gain. A version rises when an old reader would misread new data;
here it would not.

Snapshots stay authoritative. Incremental events update the counters live, and
the next snapshot reconciles them after downtime or a detected sequence gap,
which is the rule the pack already follows for blocks and damage. A snapshot can
repair a total; it cannot reconstruct when the actions happened.

## Performance

Item use and interactions fire far more often than joins or deaths, so the
implementation measures rather than assumes:

- the per-event handler cost, which must stay flat as a map saturates — the
  bound is what keeps the eviction sort small, and a quadratic regression there
  would only appear on a busy server;
- the number of log lines, which must not grow with the number of actions: item
  use is coalesced into one `items.used` envelope per player per five-second
  cycle, exactly as block activity is;
- the serialized size of a player shard, which must stay inside the 30 KB
  budget with every metric enabled and every map full.

A metric whose measurements exceed those bounds is disabled rather than shipped
slower, and the measurement — not an opinion about it — decides.
