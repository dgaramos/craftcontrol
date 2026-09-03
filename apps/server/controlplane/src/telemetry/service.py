"""Telemetry reconciliation use cases.

This module is intentionally separate from telemetry.py, which validates the wire
protocol, and telemetry/installer.py, which manages pack files.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from typing import Any

from ..ports import EventPublisher, TelemetryStore


class TelemetryService:
    def __init__(self, repository: TelemetryStore, events: EventPublisher) -> None:
        self.repository = repository
        self.events = events
        self._lock = threading.RLock()
        self._diagnostics: dict[str, float | int] = {"accepted": 0, "rejected": 0, "duplicates": 0, "old": 0, "attempted": 0, "duration_total_ms": 0.0, "duration_max_ms": 0.0}
        self._topic_diagnostics: dict[str, dict[str, int]] = {}
        self._sequence_diagnostics = {"lost": 0, "gaps": 0, "resets": 0}
        self._batch_diagnostics: dict[str, int] = {"count": 0, "total_blocks_declared": 0, "max_blocks_declared": 0}
        self._snapshot_diagnostics: dict[str, int | float | None] = {"count": 0, "duration_ms_total": 0.0, "duration_ms_max": 0.0, "last_player_count": None}
        self._pending_snapshot_started_at: float | None = None

    def _topic_metrics(self, topic: str) -> dict[str, int]:
        return self._topic_diagnostics.setdefault(topic, {
            "accepted": 0, "rejected": 0, "duplicates": 0, "old": 0,
            "gaps": 0, "resets": 0,
        })

    def diagnostics(self) -> dict[str, float | int]:
        with self._lock:
            accepted = int(self._diagnostics["accepted"])
            attempted = int(self._diagnostics["attempted"])
            return {
                "accepted": accepted,
                "rejected": int(self._diagnostics["rejected"]),
                "duplicates": int(self._diagnostics["duplicates"]),
                "old": int(self._diagnostics["old"]),
                "by_topic": {topic: dict(values) for topic, values in sorted(self._topic_diagnostics.items())},
                "sequence": dict(self._sequence_diagnostics),
                "ingestion_duration_ms_average": round(float(self._diagnostics["duration_total_ms"]) / attempted, 2) if attempted else 0,
                "ingestion_duration_ms_max": round(float(self._diagnostics["duration_max_ms"]), 2),
                "blocks": dict(self._batch_diagnostics),
                "snapshots": dict(self._snapshot_diagnostics),
            }

    def ingest(self, envelope: dict[str, Any], request_snapshot: Callable[[str], None]) -> None:
        started = time.perf_counter()
        def record_duration() -> None:
            duration = (time.perf_counter() - started) * 1000
            self._diagnostics["attempted"] += 1
            self._diagnostics["duration_total_ms"] += duration
            self._diagnostics["duration_max_ms"] = max(float(self._diagnostics["duration_max_ms"]), duration)
        with self._lock:
            topic = envelope["type"]
            _raw_seq = envelope["sequence"]
            if isinstance(_raw_seq, bool):
                raise ValueError(f"sequence must be an integer, got bool: {_raw_seq!r}")
            sequence = int(_raw_seq)
            snapshot_topic = topic.startswith("snapshot.")
            topic_metrics = self._topic_metrics(topic)
            telemetry = self.repository.snapshot().get("telemetry", {})
            last_sequence = int(telemetry["sequence"]) if telemetry.get("sequence", "").isdigit() else None
            status = telemetry.get("status", "waiting")
            resync_reason: str | None = None
            storage = envelope.get("data", {}).get("storage")
            storage = storage if isinstance(storage, dict) else None
            capabilities = envelope.get("data", {}).get("capabilities")
            capabilities = capabilities if isinstance(capabilities, dict) else None
            storage_blocked = bool(storage and (storage.get("persistenceBlocked") is True or storage.get("status") == "blocked"))
            known_storage_blocked = storage_blocked or telemetry.get("persistence_blocked") == "true"

            pack_reset = topic == "telemetry.started" and last_sequence is not None and sequence < last_sequence
            if not snapshot_topic and last_sequence is not None and sequence <= last_sequence and not pack_reset:
                self._diagnostics["rejected"] += 1
                self._diagnostics["duplicates" if sequence == last_sequence else "old"] += 1
                topic_metrics["rejected"] += 1
                topic_metrics["duplicates" if sequence == last_sequence else "old"] += 1
                record_duration()
                self.events.publish("telemetry.sequence.rejected", "behavior-pack", {
                    "sequence": sequence, "last_sequence": last_sequence, "topic": topic,
                })
                return

            updates = {
                "schema": str(envelope["schema"]), "sequence": str(sequence),
                "expected_sequence": str(sequence + 1), "last_topic": topic,
                "last_event_at": str(time.time()),
            }
            if topic == "telemetry.started" and isinstance(envelope.get("data", {}).get("version"), str):
                updates["pack_version"] = envelope["data"]["version"][:32]
            if storage:
                updates.update(
                    storage_version=str(storage.get("storageVersion", "")),
                    storage_status=str(storage.get("status", "unknown")),
                    persistence_blocked="true" if storage_blocked else "false",
                )
                updates["storage_migrated_from"] = str(storage["migratedFrom"]) if storage.get("migratedFrom") is not None else ""
            if capabilities:
                supported = sum(1 for value in capabilities.values() if isinstance(value, dict) and value.get("supported") is True)
                updates.update(
                    capabilities=json.dumps(capabilities, ensure_ascii=False, sort_keys=True),
                    capability_status="full" if supported == len(capabilities) else "limited",
                    capabilities_supported=str(supported),
                    capabilities_total=str(len(capabilities)),
                )
            if snapshot_topic:
                if topic == "snapshot.started":
                    updates.update(status="degraded" if storage_blocked else "syncing", snapshot_started_at=str(time.time()))
                    self._pending_snapshot_started_at = time.perf_counter()
                elif topic == "snapshot.finished":
                    if known_storage_blocked:
                        updates.update(status="degraded", last_error="telemetry pack persistence is blocked")
                    else:
                        updates.update(status="healthy", last_snapshot_at=str(time.time()), last_error="")
            elif last_sequence is not None and sequence > last_sequence + 1:
                missing = sequence - last_sequence - 1
                topic_metrics["gaps"] += 1
                self._sequence_diagnostics["gaps"] += 1
                self._sequence_diagnostics["lost"] += missing
                updates.update(
                    status="degraded",
                    gap_count=str(int(telemetry.get("gap_count", "0")) + 1),
                    missing_events=str(int(telemetry.get("missing_events", "0")) + missing),
                    last_gap=f"{last_sequence + 1}-{sequence - 1}",
                    last_error=f"sequence gap: expected {last_sequence + 1}, received {sequence}",
                )
                resync_reason = "sequence-gap"
            elif topic == "telemetry.started":
                updates["status"] = "syncing"
                if pack_reset:
                    topic_metrics["resets"] += 1
                    self._sequence_diagnostics["resets"] += 1
                    updates.update(
                        reset_count=str(int(telemetry.get("reset_count", "0")) + 1),
                        last_error=f"pack sequence reset: {last_sequence} -> {sequence}",
                    )
                resync_reason = "pack-started"
            elif status not in {"syncing", "degraded"}:
                updates["status"] = "healthy"

            if storage_blocked:
                updates.update(status="degraded", last_error=str(storage.get("error") or "telemetry pack persistence is blocked")[:240])

            accepted, players = self.repository.ingest_telemetry(envelope)
            if not accepted:
                self._diagnostics["rejected"] += 1
                topic_metrics["rejected"] += 1
                record_duration()
                return
            self.repository.store("telemetry", updates, "behavior-pack")
            self._diagnostics["accepted"] += 1
            topic_metrics["accepted"] += 1
            if topic == "blocks.changed":
                data = envelope.get("data") or {}
                broken_total = int((data.get("broken") or {}).get("total") or 0)
                placed_total = int((data.get("placed") or {}).get("total") or 0)
                batch_total = broken_total + placed_total
                self._batch_diagnostics["count"] += 1
                self._batch_diagnostics["total_blocks_declared"] += batch_total
                self._batch_diagnostics["max_blocks_declared"] = max(int(self._batch_diagnostics["max_blocks_declared"]), batch_total)
            elif topic == "snapshot.finished":
                pending = self._pending_snapshot_started_at
                self._pending_snapshot_started_at = None
                if pending is not None:
                    duration_ms = (time.perf_counter() - pending) * 1000
                    self._snapshot_diagnostics["count"] = int(self._snapshot_diagnostics["count"]) + 1
                    self._snapshot_diagnostics["duration_ms_total"] = float(self._snapshot_diagnostics["duration_ms_total"]) + duration_ms
                    self._snapshot_diagnostics["duration_ms_max"] = max(float(self._snapshot_diagnostics["duration_ms_max"]), duration_ms)
                players_field = (envelope.get("data") or {}).get("players")
                self._snapshot_diagnostics["last_player_count"] = len(players_field) if isinstance(players_field, list) else None
            record_duration()

        self.events.publish(f"telemetry.{topic}", "behavior-pack", {"players": players, "sequence": envelope["sequence"]})
        if players or topic in {"snapshot.finished", "telemetry.started"}:
            self.events.publish("state.changed", "behavior-pack", {"domains": ["telemetry", "player_profiles"], "players": players})
        if resync_reason:
            self.events.publish("telemetry.reconciliation.required", "behavior-pack", {
                "reason": resync_reason, "sequence": sequence,
            })
            request_snapshot(resync_reason)
