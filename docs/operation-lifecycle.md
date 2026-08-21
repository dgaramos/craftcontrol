# Operation Lifecycle and Evidence Contract

This document is the canonical contract for server operations — specifically
restart-required changes — in CraftControl. Backend services, adapters, and
the frontend consume this contract. Future executor replacements must emit the
same shape; application consumers require no lifecycle redesign when an executor
is swapped.

---

## Scope

An **operation** is any change to server configuration or state that requires
a controlled restart sequence. The contract does not cover backup-only flows or
gamerule changes that apply at runtime without a restart.

---

## Correlation identifier

Every operation is assigned a stable `operation_id` (UUID v4) at the moment the
change is accepted by the application service. The identifier travels through all
stages, persisted records, SSE events, log annotations, and executor payloads. A
single `operation_id` unambiguously links every artefact produced during the
lifecycle of one change.

---

## Stages

Operations progress through a fixed sequence of named stages. A stage
represents a discrete unit of work with a defined owner and observable outcome.

| Stage | Name | Description |
|---|---|---|
| 1 | `REVIEW` | Application validates the requested change against current configuration and RBAC. |
| 2 | `BACKUP_VERIFICATION` | A backup is confirmed as current and healthy before any destructive step proceeds. |
| 3 | `PREPARATION` | Configuration files and environment variables are written. The Compose project is staged. |
| 4 | `RESTART` | The executor (Compose adapter or host agent) issues the restart command. |
| 5 | `HEALTH_WAIT` | The health probe polls until the server reports ready or the deadline elapses. |
| 6 | `VERIFICATION` | The application reads server state and compares it to the intended post-change state. |
| 7 | `CONFIRMATION` | The outcome is recorded, SSE event emitted, and the operation sealed. |

---

## States

Each stage transition produces one of the following operation states. States are
cumulative labels on the operation record, not per-stage fields.

| State | Description |
|---|---|
| `PENDING` | Operation accepted; no stage has begun. |
| `IN_PROGRESS` | At least one stage is running. |
| `APPLIED` | All stages completed and observed state matches intended state. |
| `FAILED` | A stage returned an error and the operation cannot continue. |
| `DIVERGENT` | The executor command succeeded but observed server state disagrees with intended state. |
| `CANCELLED` | The operation was cancelled before reaching `RESTART`. |

`DIVERGENT` is a first-class terminal outcome, not a subtype of `FAILED`. A
divergent result means the platform accepted the command but the resulting state
is unexpected. Callers must not conflate divergence with failure: the failure
path triggers an alert and requires a new operation or manual corrective action
(no automatic rollback occurs within this contract), while the divergence path
triggers an alert and manual review. An operation can transition to `DIVERGENT`
only from `VERIFICATION`.

When state is `FAILED`, the application service records `error_detail`, emits
`operation.failed`, and seals the record. No rollback is initiated
automatically. Corrective action — whether a new operation, a manual restore, or
an operator intervention — is outside the scope of this contract and must be
initiated explicitly by the operator.

---

## Transitions

```text
PENDING
  ├─► CANCELLED    (explicit cancel before first stage begins)
  └─► IN_PROGRESS  (first stage begins)
        ├─► FAILED       (any stage errors)
        ├─► CANCELLED    (explicit cancel before RESTART)
        ├─► DIVERGENT    (VERIFICATION: state mismatch)
        └─► APPLIED      (CONFIRMATION: state matches)
```

`APPLIED`, `FAILED`, `DIVERGENT`, and `CANCELLED` are terminal. No transition
out of a terminal state is valid.

---

## Evidence fields

The following fields are recorded on the operation record. All timestamps are
UTC ISO 8601.

| Field | Type | Description |
|---|---|---|
| `operation_id` | UUID | Stable correlation identifier assigned at acceptance. |
| `operation_type` | string | Identifies the class of change (e.g. `server_settings_update`). |
| `state` | enum | Current operation state (see States). |
| `current_stage` | enum \| null | Active stage name; null when terminal. |
| `initiated_by` | string | Username of the panel user who requested the change. |
| `created_at` | datetime | Timestamp when the operation was accepted. |
| `updated_at` | datetime | Timestamp of the most recent state or stage transition. |
| `completed_at` | datetime \| null | Timestamp of the terminal transition; null while in progress. |
| `stage_log` | list | Ordered log of stage entries (see Stage log entry). |
| `intended_state` | object | Snapshot of the configuration as it should appear after the operation. |
| `observed_state` | object \| null | Snapshot read during VERIFICATION; null until that stage runs. |
| `divergence_detail` | object \| null | Fields where observed state differs from intended state; null when not divergent. |
| `executor_ref` | string \| null | Opaque identifier returned by the executor (e.g. Compose service name + restart token). |
| `error_detail` | object \| null | Structured error populated when state is FAILED. |

#### `error_detail` schema

| Field | Type | Description |
|---|---|---|
| `code` | string | Machine-readable error code (e.g. `executor_timeout`, `health_probe_failed`). |
| `message` | string | Human-readable error description. |
| `stage` | enum | The stage in which the error occurred. |
| `exception_type` | string \| null | Python exception class name, if applicable. |

#### `divergence_detail` schema

A list of objects, one per mismatched field.

| Field | Type | Description |
|---|---|---|
| `field` | string | Dot-separated path to the mismatched field within the state snapshot (e.g. `difficulty`). |
| `intended` | any | The value expected after the operation. |
| `observed` | any | The value read during VERIFICATION. |

### Stage log entry

Each entry in `stage_log` captures one stage attempt.

| Field | Type | Description |
|---|---|---|
| `stage` | enum | Stage name. |
| `started_at` | datetime | When the stage began. |
| `completed_at` | datetime \| null | When the stage finished; null if still running. |
| `outcome` | `ok` \| `error` \| `skipped` | Result of this stage. |
| `detail` | string \| null | Human-readable summary, error message, or skip reason. |

---

## Ownership boundaries

The contract is owned by the **application layer**. Adapters and the UI are
consumers.

| Concern | Owner |
|---|---|
| Assigning `operation_id` | Application service (at acceptance) |
| Validating the change and checking RBAC | Application service (REVIEW stage) |
| Confirming backup currency | Application service via backup port (BACKUP_VERIFICATION stage) |
| Writing configuration files | Compose adapter (PREPARATION stage) |
| Issuing the restart command | Compose adapter or host agent (RESTART stage) |
| Polling health | Compose adapter or host agent (HEALTH_WAIT stage) |
| Reading observed state | Application service via server port (VERIFICATION stage) |
| Comparing intended vs observed state | Application service (VERIFICATION stage) |
| Persisting the operation record and emitting SSE | Application service (all stages) |
| Displaying state and divergence to the user | Frontend, reading SSE and the operations endpoint |

The Compose adapter and the host agent are interchangeable **executors**. An
executor is responsible only for PREPARATION, RESTART, and HEALTH_WAIT. It
reports back a structured result that the application service uses to advance the
stage log. Executors do not write to the operation record directly.

### Executor result shape

An executor must return a plain object with the following fields after completing
its scope (PREPARATION through HEALTH_WAIT):

| Field | Type | Description |
|---|---|---|
| `outcome` | `ok` \| `error` | Whether the executor completed its scope without error. |
| `executor_ref` | string \| null | Opaque executor-local handle for correlation and audit. |
| `health_reached` | bool | True if the health probe confirmed server readiness within the deadline. |
| `detail` | string \| null | Human-readable summary or error message. |

The application service maps this result to stage log entries and advances the
operation state. A future host agent that emits this same shape requires no
changes to the application layer.

---

## Divergent state

A result is divergent when all of the following are true after VERIFICATION:

1. The executor returned `outcome: ok`.
2. The health probe confirmed readiness (`health_reached: true`).
3. One or more fields in `observed_state` do not match the corresponding fields
   in `intended_state`.

`divergence_detail` lists each mismatched field with its intended and observed
values. The operation transitions to `DIVERGENT` and no further automatic
corrective action is taken. An SSE event of type `operation.divergent` is
emitted. The panel displays the divergence detail and prompts the operator for
manual review.

---

## Timestamps and ordering guarantees

`created_at` is the anchor for the operation record. All stage `started_at`
values must be monotonically increasing relative to `created_at`. The
application service enforces this; executors must not backdate timestamps.

`completed_at` is written atomically with the terminal state transition. No
additional updates to `state` or `current_stage` are valid after
`completed_at` is set.

---

## SSE event types

Operations emit the following event types over the SSE stream.

| Event type | When emitted |
|---|---|
| `operation.created` | Operation accepted; PENDING state recorded. |
| `operation.stage_started` | A stage begins. |
| `operation.stage_completed` | A stage finishes (ok, error, or skipped). |
| `operation.applied` | Terminal: all stages succeeded, state matches. |
| `operation.failed` | Terminal: a stage returned an error. |
| `operation.divergent` | Terminal: executor succeeded but observed state mismatches. |
| `operation.cancelled` | Terminal: cancelled before RESTART. |

All events carry `operation_id` and `updated_at` at minimum. Terminal events
additionally carry `completed_at` and the relevant terminal fields
(`divergence_detail`, `error_detail`, or neither).
