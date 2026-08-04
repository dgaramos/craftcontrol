from __future__ import annotations

import re
import threading
import time
from typing import TYPE_CHECKING, Any

from .events import EventBroker
from .schema import GAMERULES

if TYPE_CHECKING:
    from .services import ManagerService


class EventRuntime:
    def __init__(self, service: "ManagerService", broker: EventBroker, container: str, reconcile_seconds: int = 900) -> None:
        self.service = service
        self.broker = broker
        self.container = container
        self.reconcile_seconds = reconcile_seconds
        self._started = False
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        for name, target in (
            ("bedrock-log-stream", self._logs),
            ("docker-event-stream", self._docker_events),
            ("safety-reconciler", self._periodic),
        ):
            threading.Thread(target=target, name=name, daemon=True).start()

    def _logs(self) -> None:
        import docker as docker_sdk

        backoff = 2
        while not self._stop.is_set():
            client: Any = None
            try:
                client = docker_sdk.from_env()
                container = client.containers.get(self.container)
                self.broker.publish("stream.logs.connected", "docker-logs")
                threading.Timer(3, lambda: self.service.refresh_async(reason="log-stream-connected")).start()
                for raw in container.logs(stream=True, follow=True, since=int(time.time()) - 2):
                    if self._stop.is_set():
                        return
                    self._handle_log(raw.decode("utf-8", errors="replace").strip())
                backoff = 2
            except Exception as error:
                self.broker.publish("stream.logs.disconnected", "docker-logs", {"error": str(error)[:240]})
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                if client is not None:
                    client.close()

    def _handle_log(self, line: str) -> None:
        connected = re.search(r"Player connected:\s*([^,]+),\s*xuid:\s*([^,\s]+)", line, re.IGNORECASE)
        disconnected = re.search(r"Player disconnected:\s*([^,]+),\s*xuid:\s*([^,\s]+)", line, re.IGNORECASE)
        if connected:
            name, xuid = connected.group(1).strip(), connected.group(2).strip()
            self.service.player_event(name, True, xuid)
            self.broker.publish("player.connected", "bedrock-log", {"player": name})
            return
        if disconnected:
            name, xuid = disconnected.group(1).strip(), disconnected.group(2).strip()
            self.service.player_event(name, False, xuid)
            self.broker.publish("player.disconnected", "bedrock-log", {"player": name})
            return
        if self.service.refreshing:
            return
        lowered = line.lower()
        if "gamerule" in lowered:
            affected = {rule for rule in GAMERULES if rule in lowered}
            if affected:
                self.broker.publish("gamerule.invalidated", "bedrock-log", {"rules": sorted(affected)})
                self.service.refresh_gamerules_async(affected)
        if re.search(r"\b(op|deop|permission)\b", lowered):
            self.broker.publish("permissions.invalidated", "bedrock-log")
            threading.Timer(2, self.service.refresh_permissions).start()

    def _docker_events(self) -> None:
        import docker as docker_sdk

        backoff = 2
        while not self._stop.is_set():
            client: Any = None
            try:
                client = docker_sdk.from_env()
                self.broker.publish("stream.docker.connected", "docker-events")
                filters = {"type": "container", "container": self.container, "event": ["start", "restart", "die", "destroy"]}
                for event in client.events(decode=True, filters=filters):
                    action = event.get("Action", "unknown")
                    self.broker.publish(f"server.{action}", "docker-events", {"container_id": event.get("id", "")})
                    if action in {"start", "restart"}:
                        self.service.refresh_async(reason=f"docker.{action}")
            except Exception as error:
                self.broker.publish("stream.docker.disconnected", "docker-events", {"error": str(error)[:240]})
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                if client is not None:
                    client.close()

    def _periodic(self) -> None:
        while not self._stop.wait(self.reconcile_seconds):
            self.broker.publish("state.reconciliation.requested", "safety-timer", {"scope": "full"})
            self.service.refresh_async(reason="safety-timer")
