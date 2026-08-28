# Backend checklist

- Preserve HTTP → use cases → ports/adapters. Routes do not reach repositories
  or adapters; runtime supervisors call application-facing ports.
- Inject dependencies through constructors and assemble production in the
  composition root. Use `Protocol` only for meaningful replaceable boundaries.
- Preserve XUID as internal identity, permanent player profiles, idempotent
  ingestion, and the separation of player history from operational retention.
- Migrate SQLite without deleting user data. Do not add locks or transactions
  that harm runtime reconciliation or SSE delivery.
- Enforce capabilities, allowlists, and CSRF. Do not expose arbitrary console
  access, session identifiers, credentials, or XUIDs.
