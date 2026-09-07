# Data exports

CraftControl exports the data the panel already shows, in JSON and CSV, so an
owner can archive or analyze it without direct SQLite access. This document is
the contract every export resource follows. It exists so the implementations do
not invent per-endpoint rules for identity, time, bounds, or refusal.

Exports read the same repositories the panel reads. They never widen what the
API already exposes: a field excluded from an endpoint stays excluded from its
export.

## Authorization

Exports require the `data.export` capability. `ROLE_CAPABILITIES` grants `*` to
`owner` and lists `viewer` and `operator` capabilities explicitly, so naming a
new capability makes exports owner-only without a second rule. Requests without
it answer `403` through the existing error envelope, and every attempt is
audited whether it succeeds or fails.

Exports are mutating in the audit sense but not in the state sense: they never
write world, player, or configuration data, and never take the operation lock.

## Resources

Two families, because their filters and aggregation differ.

**Player resources** — `profiles`, `sessions`, `activity`, `deaths`. They export
the durable records behind the Players and Data workspaces, using the shapes the
API already defines (`PlayerSummary`, `PlayerSession`, `ActivityEvent`). Filters
are an optional player, an optional period in days, and for `activity` the same
`kind` and `source` allowlists the activity endpoint accepts.

**Analytics resources** — `rankings`, `periods`, `blocks`, `combat`,
`exploration`. They export the bounded aggregates behind the analytics
endpoints. Filters are the category or metric selection each endpoint already
allowlists, plus the period where the endpoint supports one.

A resource that the API does not serve today is not exportable. Adding one means
adding the endpoint first, so the export never becomes a second, wider read path
into the database.

## Formats

`format=json` returns one object with a `manifest` and a `records` array.
`format=csv` returns the same records as `text/csv`.

The manifest is part of the contract because a bare array cannot say what it
contains:

| field | meaning |
| --- | --- |
| `export_schema_version` | integer, starts at `1`, incremented on a breaking change to any export shape |
| `resource` | the exported resource name |
| `format` | `json` or `csv` |
| `filters` | the effective filters after allowlisting and clamping, not the raw query |
| `generated_at` | UNIX timestamp of the export |
| `row_count` | number of records in the payload |
| `row_limit` | the ceiling that applied to this request |
| `truncated` | always `false`; an export that would exceed the ceiling is refused, never silently cut |

CSV carries the manifest in headers rather than in the body, so the file stays
loadable by a spreadsheet: `X-CraftControl-Export-Manifest` holds the same object
as compact JSON. A CSV body is a header row followed by data rows, RFC 4180
quoting, UTF-8 without a byte-order mark, and LF line endings. Nested values are
flattened with dotted column names (`player.id`, `player.name`); a null is an
empty field, never the string `null`. Column order is the declared order of the
resource's fields and is stable across releases within an
`export_schema_version`.

Both formats are served as a download through `Content-Disposition`, with the
file name `craftcontrol-<resource>-<YYYYMMDD>T<HHMMSS>Z.<json|csv>`.

## Time

Instants are UNIX timestamps in JSON, matching every other endpoint, and RFC
3339 in UTC in CSV (`2026-09-07T15:35:53Z`), because a spreadsheet cannot be
trusted to interpret an epoch number. Durations stay integer seconds in both.

Calendar days are not UTC. Daily aggregates bucket by the deployment's `TZ`
(`America/Sao_Paulo` unless configured otherwise), the same boundary the period
rankings use. Any exported day key therefore means a local day, and the manifest
records the timezone that produced it so an archive remains interpretable after
the deployment's `TZ` changes.

Exports inherit the provenance rules of the endpoints they read: where the API
labels a value's source and observation time, the export carries both. It does
not promise more precision than the panel does — a snapshot-backed lifetime
total is still a lifetime total, and the caveats in
[Activity and death analytics](analytics.md) apply unchanged.

## Privacy

An export never contains XUIDs, password hashes, session tokens, invitation
codes, cookie values, IP addresses, panel session identifiers, or raw console
and log evidence. Players are identified exactly as the API identifies them: the
opaque public ID and the current Gamertag, with preserved aliases where the
profile already exposes them.

Event detail is the bounded, allowlisted set the activity endpoint emits.
Coordinates appear only where a structured event already supplies them and the
API already returns them.

This list is a floor, not a summary: a field that is private in an endpoint is
private in its export, and an export must never be the reason a field becomes
public.

## Bounds and delivery

Exports are synchronous and bounded. A request is refused, not truncated, when
it would exceed either ceiling:

- **10 000 records** per export;
- **5 MiB** of serialized payload.

The ceilings are enforced by counting before serializing, so refusal costs a
count query rather than a full materialization, and the panel's single worker is
never occupied producing a file it will discard.

A refusal answers `422` with the standard error envelope, naming which ceiling
was reached, the count that triggered it, and the filter that narrows the
request — a period, a player, or a category. The same request with the same data
always produces the same outcome: no partial file, no timeout-shaped failure, no
retry that succeeds by luck.

There is deliberately no export job queue. An asynchronous boundary is reserved
for the first resource that cannot be bounded by filters — a full-history
archive, say — and would arrive as its own resource with a job identifier and a
retrieval endpoint. Until such a resource exists, "bounded and refused" is the
contract, and an implementation must not introduce a background writer, a
temporary file, or a partial download to work around a ceiling.

## Audit

Every export attempt writes one `audit_log` record through the shared audit
boundary: action `data.export`, target `<resource>:<format>`, result `ok` or
`failed`, and metadata carrying the effective filters and the row count. A
refusal is recorded with the ceiling that stopped it.

Audit metadata never contains exported rows, player identities beyond the filter
the actor supplied, or the file itself. The audit trail answers who exported
what and when, not what the file said.

## Errors

Exports use the existing error envelope and status codes: `400` for a malformed
or non-allowlisted filter, `403` for a missing capability, `404` for an unknown
resource, and `422` for a request that exceeds a ceiling. An unexpected failure
answers `500` without partial content, and the audit record for it is written
with result `failed`.
