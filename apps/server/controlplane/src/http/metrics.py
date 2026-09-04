"""Prometheus text exposition endpoint (GET /metrics).

Renders the existing diagnostics data from the manager service into
standard Prometheus text format (version 0.0.4). No new data collection;
no third-party dependencies — the format is generated with plain string
formatting.

Authentication:
  If the SCRAPE_SECRET environment variable is set at startup, the endpoint
  requires ``Authorization: Bearer <secret>``. If unset, the endpoint is open
  (standard Prometheus convention for private-network deployments).

Privacy:
  The output must not contain player identities, XUIDs, credentials, or any
  world-specific data. Only aggregate counts and durations are emitted.
"""

from __future__ import annotations

import os
from typing import Any

from flask import Blueprint, Response, current_app, request

from .dependencies import manager

# ---------------------------------------------------------------------------
# Public constant used by tests to know the env-var name
# ---------------------------------------------------------------------------

_SCRAPE_SECRET_ENV = "SCRAPE_SECRET"

metrics_api = Blueprint("metrics_api", __name__)


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _check_bearer() -> Response | None:
    """Return a 401 Response if bearer auth is required and fails; else None."""
    secret = current_app.config.get(_SCRAPE_SECRET_ENV) or os.environ.get(_SCRAPE_SECRET_ENV)
    if not secret:
        return None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[len("Bearer "):] == secret:
        return None

    return Response(
        "Unauthorized",
        status=401,
        headers={"WWW-Authenticate": "Bearer"},
        mimetype="text/plain",
    )


# ---------------------------------------------------------------------------
# Prometheus text formatter
# ---------------------------------------------------------------------------


def _gauge(name: str, value: float | int | None, labels: dict[str, str] | None = None) -> str:
    label_str = _labels(labels)
    v = 0 if value is None else value
    return f"{name}{label_str} {v}"


def _counter(name: str, value: float | int | None, labels: dict[str, str] | None = None) -> str:
    return _gauge(name, value, labels)


def _labels(labels: dict[str, str] | None) -> str:
    if not labels:
        return ""
    parts = ", ".join(f'{k}="{v}"' for k, v in labels.items())
    return "{" + parts + "}"


def _family(metric_type: str, name: str, help_text: str, samples: list[str]) -> str:
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} {metric_type}"]
    lines.extend(samples)
    return "\n".join(lines)


def format_prometheus(data: dict[str, Any]) -> str:
    """Convert the manager diagnostics dict to Prometheus text format."""
    sections: list[str] = []

    persistence = data.get("persistence") or {}
    runtime = data.get("runtime") or {}
    telemetry = data.get("telemetry") or {}
    telemetry_state = data.get("telemetry_state") or {}
    domains = data.get("domains") or {}

    reconciliation = runtime.get("reconciliation") or {}
    snapshots = telemetry.get("snapshots") or {}
    by_topic = telemetry.get("by_topic") or {}

    # --- SQLite metrics ---
    sections.append(_family("gauge", "craftcontrol_sqlite_connections_total",
        "SQLite connection count",
        [_gauge("craftcontrol_sqlite_connections_total", persistence.get("connections"))]))

    sections.append(_family("gauge", "craftcontrol_sqlite_wait_ms_average",
        "Average SQLite wait time (ms)",
        [_gauge("craftcontrol_sqlite_wait_ms_average", persistence.get("wait_ms_average"))]))

    sections.append(_family("gauge", "craftcontrol_sqlite_wait_ms_max",
        "Max SQLite wait time (ms)",
        [_gauge("craftcontrol_sqlite_wait_ms_max", persistence.get("wait_ms_max"))]))

    sections.append(_family("counter", "craftcontrol_sqlite_contention_failures_total",
        "SQLite contention failures",
        [_counter("craftcontrol_sqlite_contention_failures_total", persistence.get("contention_failures"))]))

    sections.append(_family("counter", "craftcontrol_sqlite_retries_total",
        "SQLite retries",
        [_counter("craftcontrol_sqlite_retries_total", persistence.get("retries"))]))

    sections.append(_family("gauge", "craftcontrol_sqlite_database_size_bytes",
        "SQLite database file size (bytes)",
        [_gauge("craftcontrol_sqlite_database_size_bytes", persistence.get("database_size_bytes"))]))

    # --- Reconciliation metrics ---
    sections.append(_family("counter", "craftcontrol_reconciliation_total",
        "Reconciliation runs",
        [_counter("craftcontrol_reconciliation_total", reconciliation.get("count"))]))

    sections.append(_family("counter", "craftcontrol_reconciliation_duration_ms_total",
        "Cumulative reconciliation duration (ms)",
        [_counter("craftcontrol_reconciliation_duration_ms_total", reconciliation.get("duration_ms_total"))]))

    sections.append(_family("gauge", "craftcontrol_reconciliation_duration_ms_max",
        "Max reconciliation duration (ms)",
        [_gauge("craftcontrol_reconciliation_duration_ms_max", reconciliation.get("duration_ms_max"))]))

    # --- Snapshot metrics ---
    sections.append(_family("counter", "craftcontrol_snapshot_total",
        "Snapshot operations",
        [_counter("craftcontrol_snapshot_total", snapshots.get("count"))]))

    sections.append(_family("counter", "craftcontrol_snapshot_duration_ms_total",
        "Cumulative snapshot duration (ms)",
        [_counter("craftcontrol_snapshot_duration_ms_total", snapshots.get("duration_ms_total"))]))

    sections.append(_family("gauge", "craftcontrol_snapshot_duration_ms_max",
        "Max snapshot duration (ms)",
        [_gauge("craftcontrol_snapshot_duration_ms_max", snapshots.get("duration_ms_max"))]))

    # --- Ingestion per-topic metrics ---
    accepted_samples = [
        _counter("craftcontrol_ingestion_accepted_total", v.get("accepted"), {"topic": topic})
        for topic, v in sorted(by_topic.items())
    ]
    rejected_samples = [
        _counter("craftcontrol_ingestion_rejected_total", v.get("rejected"), {"topic": topic})
        for topic, v in sorted(by_topic.items())
    ]
    sections.append(_family("counter", "craftcontrol_ingestion_accepted_total",
        "Accepted ingestion events per topic", accepted_samples))
    sections.append(_family("counter", "craftcontrol_ingestion_rejected_total",
        "Rejected ingestion events per topic", rejected_samples))

    # --- Domain metrics ---
    age_samples = []
    fresh_samples = []
    for domain, info in sorted(domains.items()):
        lbl = {"domain": domain}
        age = info.get("age_seconds")
        stale = info.get("stale", True)
        age_samples.append(_gauge("craftcontrol_domain_age_seconds", age, lbl))
        fresh_samples.append(_gauge("craftcontrol_domain_fresh", 0 if stale else 1, lbl))

    if age_samples:
        sections.append(_family("gauge", "craftcontrol_domain_age_seconds",
            "Age of each domain's last update (seconds)", age_samples))
        sections.append(_family("gauge", "craftcontrol_domain_fresh",
            "Freshness flag per domain (1=fresh, 0=stale)", fresh_samples))

    # --- Telemetry sequence metrics ---
    sections.append(_family("gauge", "craftcontrol_telemetry_sequence",
        "Current telemetry sequence number",
        [_gauge("craftcontrol_telemetry_sequence", telemetry_state.get("sequence"))]))

    sections.append(_family("gauge", "craftcontrol_telemetry_expected_sequence",
        "Expected telemetry sequence number",
        [_gauge("craftcontrol_telemetry_expected_sequence", telemetry_state.get("expected_sequence"))]))

    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@metrics_api.get("/metrics")
def metrics():
    """Expose operational metrics in Prometheus text exposition format."""
    auth_error = _check_bearer()
    if auth_error is not None:
        return auth_error

    data = manager().diagnostics()
    body = format_prometheus(data)
    return Response(body, status=200, mimetype="text/plain; version=0.0.4")
