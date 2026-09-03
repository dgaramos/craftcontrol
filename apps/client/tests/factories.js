/**
 * Domain object builders for client tests.
 *
 * Each factory returns a minimal valid API-shaped object with sensible
 * defaults. Pass an overrides map to customise individual fields.
 * Builders here mirror the domain contracts defined in the backend —
 * keep them in sync when the API shapes change.
 */

export function makeOperation(overrides = {}) {
  return {
    operation_id: "op-1",
    server_id: "default",
    state: "running",
    requested_changes: { SERVER_NAME: "MyWorld" },
    stages: [
      { stage: "review",        result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
      { stage: "backup_verify", result: "running",   started_at: 1700000002, completed_at: null,       evidence: { backup_path: "/backups/world" }, error: null },
      { stage: "prepare",       result: "pending",   started_at: null,       completed_at: null,       evidence: {}, error: null },
      { stage: "restart",       result: "pending",   started_at: null,       completed_at: null,       evidence: {}, error: null },
      { stage: "health_wait",   result: "pending",   started_at: null,       completed_at: null,       evidence: {}, error: null },
      { stage: "verify",        result: "pending",   started_at: null,       completed_at: null,       evidence: {}, error: null },
      { stage: "confirm",       result: "pending",   started_at: null,       completed_at: null,       evidence: {}, error: null },
    ],
    created_at: 1700000000,
    updated_at: 1700000002,
    completed_at: null,
    terminal_error: null,
    observation: {},
    correlation_id: null,
    ...overrides,
  };
}

export function makePlayer(overrides = {}) {
  return {
    id: "abc123",
    name: "Alice",
    online: false,
    deaths_count: 2,
    total_play_seconds: 3600,
    operator: false,
    last_seen_at: 1000,
    connected_at: null,
    ...overrides,
  };
}
