# Operations checklist

- Keep the panel usable without Prometheus, Grafana, the exporter, or the
  Telemetry Pack. Derived events retain evidence and never become authoritative.
- Pack lifecycle uses the shared installer, persistent Bedrock data, backups,
  atomic association updates, and an explicit restart decision.
- Coordinated backups pause saves only for the copy window and resume in
  `finally`. Restore is offline, confirmed, creates a recovery copy, and never
  restores `.env` automatically.
- Do not deploy with bare Compose from a development checkout. Protect `.env`,
  SQLite, and world data from overwrite or development bind mounts.
