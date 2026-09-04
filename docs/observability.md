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

### Authentication

By default the endpoint is public. To require a bearer token, set the
`SCRAPE_SECRET` environment variable in the backend container. Prometheus
must then send it as `Authorization: Bearer <secret>`.

Without `SCRAPE_SECRET` the endpoint is open — suitable for homelab
deployments where Prometheus and CraftControl are on the same private network.

### nginx proxy

The frontend container (nginx) proxies `/metrics` to the backend. No special
configuration is needed on the scraper side: target the frontend host and
port (e.g. `192.168.15.50:8082`) directly.

## Prometheus scrape job

Add a job to your `prometheus.yml`:

```yaml
- job_name: 'craftcontrol'
  static_configs:
    - targets: ['<host>:<port>']   # frontend host:port, e.g. 192.168.15.50:8082
```

If `SCRAPE_SECRET` is set:

```yaml
- job_name: 'craftcontrol'
  authorization:
    credentials: '<secret>'
  static_configs:
    - targets: ['<host>:<port>']
```

Reload Prometheus after editing (`kill -HUP <pid>` or the `/-/reload` endpoint).

## Grafana dashboard

The dashboard JSON is versioned at:

```
infra/grafana/dashboards/craftcontrol-health.json
```

### Importing

1. Open Grafana → **Dashboards** → **Import**.
2. Upload `craftcontrol-health.json` or paste its contents.
3. Select your Prometheus datasource when prompted (the dashboard variable is
   named `DS_PROMETHEUS`).
4. Click **Import**.

The dashboard UID is `craftcontrol-health`. Importing again with the same UID
will offer an overwrite prompt — safe to confirm when updating.

### Panels

| Section | What it shows |
|---|---|
| Overview | Domain freshness age, sequence gap, SQLite contentions, DB size |
| Ingestion | Accepted / rejected / duplicate events per telemetry topic |
| Reconciliation & Snapshots | Reconciliation run count, last snapshot age |
| SQLite | Connection pool waits, contention failures, retries |

Refresh interval: 30 s. Timezone: `America/Sao_Paulo` (configurable in dashboard settings).

### Datasource UID

The dashboard references the datasource by the variable `DS_PROMETHEUS`. At
import time Grafana maps this to whichever datasource you select. If you need
to re-point it later, edit the variable in **Dashboard settings → Variables**.

[prom-format]: https://prometheus.io/docs/instrumenting/exposition_formats/
