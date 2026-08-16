from __future__ import annotations

import re
import json
import threading
import time
from typing import Any, Callable

from .events import EventBroker
from .schema import GAMERULES
from .telemetry import PREFIX as TELEMETRY_PREFIX, parse_telemetry_line
from .ports import EventPublisher, RuntimeApplication


def _default_docker_factory() -> Any:
    import docker as docker_sdk
    return docker_sdk.from_env()


class EventRuntime:
    DEATH_PHRASES = (
        "was slain by", "was shot by", "was killed by", "was blown up by", "was fireballed by",
        "drowned", "fell from", "hit the ground", "burned to death", "went up in flames",
        "tried to swim in lava", "suffocated", "starved to death", "was pricked to death",
        "was struck by lightning", "froze to death", "was impaled by", "was squashed by",
        "died", "foi morto", "morreu", "afogou", "caiu de", "queimou", "tentou nadar em lava",
    )
    def __init__(
        self,
        service: RuntimeApplication,
        broker: EventPublisher,
        container: str,
        reconcile_seconds: int = 900,
        docker_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.service = service
        self.broker = broker
        self.container = container
        self.reconcile_seconds = reconcile_seconds
        self._docker_factory = docker_factory or _default_docker_factory
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
        backoff = 2
        while not self._stop.is_set():
            client: Any = None
            try:
                client = self._docker_factory()
                container = client.containers.get(self.container)
                self.broker.publish("stream.logs.connected", "docker-logs")
                threading.Timer(3, lambda: self.service.refresh_async(reason="log-stream-connected")).start()
                threading.Timer(5, lambda: self.service.request_telemetry_snapshot_async("log-stream-connected")).start()
                for line in self._decoded_log_lines(container.logs(stream=True, follow=True, since=int(time.time()) - 2)):
                    if self._stop.is_set():
                        return
                    self._handle_log(line)
                raise RuntimeError("Bedrock log stream ended")
            except Exception as error:
                self.broker.publish("stream.logs.disconnected", "docker-logs", {"error": str(error)[:240]})
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                if client is not None:
                    client.close()

    @staticmethod
    def _decoded_log_lines(chunks: Any):
        pending = ""
        for raw in chunks:
            pending += raw.decode("utf-8", errors="replace")
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                if line.strip():
                    yield line.rstrip("\r")
        if pending.strip():
            yield pending.rstrip("\r")

    def _handle_log(self, line: str) -> None:
        if TELEMETRY_PREFIX in line:
            try:
                envelope = parse_telemetry_line(line)
                if envelope:
                    self.service.telemetry_event(envelope)
            except (ValueError, json.JSONDecodeError) as error:
                self.broker.publish("telemetry.event.rejected", "bedrock-log", {"error": str(error)[:240]})
            return
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
        death = self._parse_death(line)
        if death:
            self.service.player_death_event(*death, line)
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

    def _parse_death(self, line: str) -> tuple[str, str] | None:
        lowered = line.casefold()
        if not any(phrase in lowered for phrase in self.DEATH_PHRASES):
            return None
        profiles = self.service.players()
        matches = [item["name"] for item in profiles if re.search(rf"(?<![\w]){re.escape(item['name'])}(?![\w])", line, re.IGNORECASE)]
        if not matches:
            return None
        player = min(matches, key=lambda name: line.casefold().find(name.casefold()))
        text = re.sub(r"^.*?\b(INFO|WARN|ERROR)\]\s*", "", line, flags=re.IGNORECASE).strip()
        cause = text[len(player):].strip(" :-") if text.casefold().startswith(player.casefold()) else text
        return player, cause[:240] or "unknown"

    def _docker_events(self) -> None:
        backoff = 2
        while not self._stop.is_set():
            client: Any = None
            try:
                client = self._docker_factory()
                self.broker.publish("stream.docker.connected", "docker-events")
                filters = {"type": "container", "container": self.container, "event": ["start", "restart", "die", "destroy"]}
                for event in client.events(decode=True, filters=filters):
                    action = event.get("Action", "unknown")
                    self.broker.publish(f"server.{action}", "docker-events", {"container_id": event.get("id", "")})
                    if action in {"start", "restart"}:
                        self.service.refresh_async(reason=f"docker.{action}")
                    elif action in {"die", "destroy"}:
                        closed = self.service.close_online_sessions(f"docker.{action}")
                        if closed:
                            self.broker.publish("state.changed", "docker-events", {"domains": ["players", "player_profiles"], "players": closed})
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
