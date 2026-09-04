# Observability

CraftControl exposes a Prometheus-compatible metrics endpoint and ships a
Grafana dashboard for monitoring service health.

## Metrics endpoint

The backend serves metrics at:

```
GET /metrics
```

The endpoint uses the [Prometheus text exposition format (0.0.4)][prom-format].
It contains no PII and no player XUIDs.

### What is exported

| Metric | Type | Description |
|---|---|---|
| `craftcontrol_domain_age_seconds` | gauge | Age of each event-sourced domain snapshot |
| `craftcontrol_sequence_gap_total` | counter | Cumulative sequence gaps detected |
| `craftcontrol_telemetry_events_total` | counter | Accepted / rejected / duplicate events per topic |
| `craftcontrol_sqlite_contentions_total` | counter | SQLite write contention failures |
| `craftcontrol_sqlite_wait_ms` | gauge | Average and max connection wait time |
| `craftcontrol_db_size_bytes` | gauge | SQLite database file size |
| `craftcontrol_reconciliation_duration_ms` | gauge | Reconciliation loop duration (last, max, total) |
| `craftcontrol_last_snapshot_age_seconds` | gauge | Seconds since the last world snapshot |

### Authentication

By default the endpoint is public. To require a bearer token, set the
`SCRAPE_SECRET` environment variable on the backend. Scrapers must then send:

```
Authorization: Bearer <secret>
```

Without `SCRAPE_SECRET` the endpoint is open — appropriate for deployments
where the scraper and the service share a private network.

### nginx proxy

When running behind the bundled nginx frontend, `/metrics` is proxied to the
backend automatically. Target the frontend host and port from your scraper —
no direct access to the backend container is needed.

## Prometheus

Add a scrape job to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'craftcontrol'
    static_configs:
      - targets: ['<host>:<port>']
```

If `SCRAPE_SECRET` is set:

```yaml
scrape_configs:
  - job_name: 'craftcontrol'
    authorization:
      credentials: '<secret>'
    static_configs:
      - targets: ['<host>:<port>']
```

Reload Prometheus after editing (`kill -HUP <pid>` or `POST /-/reload`).

## Grafana dashboard

The dashboard JSON is versioned at:

```
infra/grafana/dashboards/craftcontrol-health.json
```

Import it once and it stays in your Grafana instance. Re-import to pick up
updates shipped in new versions.

### Importing

1. Open Grafana → **Dashboards** → **Import**.
2. Upload `craftcontrol-health.json` or paste its contents.
3. Select your Prometheus datasource when prompted (the variable is named
   `DS_PROMETHEUS`).
4. Click **Import**.

The dashboard UID is `craftcontrol-health`. Re-importing with the same UID
shows an overwrite prompt — safe to confirm.

### Panels

| Section | What it shows |
|---|---|
| Overview | Domain freshness age, sequence gap, SQLite contentions, DB size |
| Ingestion | Accepted / rejected / duplicate events per telemetry topic |
| Reconciliation & Snapshots | Reconciliation run count, last snapshot age |
| SQLite | Connection pool waits, contention failures, retries |

Default refresh: 30 s. Default timezone: `America/Sao_Paulo` — change it in
**Dashboard settings → Time** after import if needed.

[prom-format]: https://prometheus.io/docs/instrumenting/exposition_formats/
