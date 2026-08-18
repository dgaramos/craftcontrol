from __future__ import annotations

import re
import time
from typing import Any, Callable

from minecraft_manager.schema import GAMERULES


def _default_docker_factory() -> Any:
    import docker as docker_sdk
    return docker_sdk.from_env()


class BedrockClient:
    def __init__(
        self,
        container_name: str,
        gamerules: list[str],
        console_wait_seconds: float = 1.0,
        docker_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.container_name = container_name
        self.gamerules = gamerules
        self.console_wait_seconds = console_wait_seconds
        self._docker_factory = docker_factory or _default_docker_factory

    def send(self, parts: list[str]) -> None:
        if not parts or any(not re.fullmatch(r"[a-z0-9_-]+", part, re.IGNORECASE) for part in parts):
            raise ValueError("Comando inválido")
        client = self._docker_factory()
        try:
            container = client.containers.get(self.container_name)
            self._write(container, " ".join(parts) + "\n")
        finally:
            client.close()

    def send_and_read(self, parts: list[str]) -> str:
        if not parts or any(not re.fullmatch(r"[a-z0-9_-]+", part, re.IGNORECASE) for part in parts):
            raise ValueError("Comando inválido")
        client = self._docker_factory()
        try:
            container = client.containers.get(self.container_name)
            since = int(time.time()) - 1
            self._write(container, " ".join(parts) + "\n")
            time.sleep(self.console_wait_seconds)
            return container.logs(since=since, tail=50).decode("utf-8", errors="replace")
        finally:
            client.close()

    def set_operator(self, player: str, enabled: bool) -> None:
        if not re.fullmatch(r"[a-z0-9 _-]{1,32}", player, re.IGNORECASE):
            raise ValueError("Jogador inválido")
        client = self._docker_factory()
        try:
            container = client.containers.get(self.container_name)
            self._write(container, f'{"op" if enabled else "deop"} "{player}"\n')
        finally:
            client.close()

    def request_telemetry_snapshot(self) -> str:
        client = self._docker_factory()
        try:
            container = client.containers.get(self.container_name)
            since = int(time.time()) - 1
            self._write(container, "scriptevent bedrock_telemetry:sync full\n")
            time.sleep(self.console_wait_seconds)
            return container.logs(since=since, tail=250).decode("utf-8", errors="replace")
        finally:
            client.close()

    @staticmethod
    def _write(container: Any, commands: str) -> None:
        channel = container.attach_socket(params={"stdin": 1, "stream": 1, "stdout": 0, "stderr": 0})
        try:
            raw_socket = getattr(channel, "_sock", channel)
            raw_socket.sendall(commands.encode("utf-8"))
        finally:
            channel.close()

    @staticmethod
    def parse_gamerules(logs: str, gamerules: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for rule in gamerules:
            matches = re.findall(rf"{re.escape(rule)}[^\r\n]*?\b(true|false|-?\d+)\b", logs, re.IGNORECASE)
            if matches:
                values[rule] = matches[-1].lower()
        return values

    @staticmethod
    def parse_players(logs: str, history: str) -> tuple[list[str], int, int]:
        players: list[str] = []
        online = maximum = 0
        markers = list(re.finditer(r"There are\s+(\d+)/(\d+)\s+players online:?", logs, re.IGNORECASE))
        if markers:
            current = markers[-1]
            online, maximum = int(current.group(1)), int(current.group(2))
            if online == 0:
                return [], 0, maximum
            for line in logs[current.end():].splitlines():
                clean = re.sub(r"^\[[^]]+\]\s*", "", line).strip()
                if not clean or re.search(r"gamerule|Game rule|INFO|WARN|ERROR", clean, re.IGNORECASE):
                    continue
                players.extend(name.strip() for name in clean.split(",") if name.strip())
                if len(players) >= online:
                    break
        if not players:
            connected: dict[str, str] = {}
            for line in history.splitlines():
                joined = re.search(r"Player connected:\s*([^,]+),\s*xuid:", line, re.IGNORECASE)
                left = re.search(r"Player disconnected:\s*([^,]+),\s*xuid:", line, re.IGNORECASE)
                if joined:
                    name = joined.group(1).strip()
                    connected[name.casefold()] = name
                elif left:
                    connected.pop(left.group(1).strip().casefold(), None)
            players = list(connected.values())
            online = len(players)
        return players[:online], online, maximum

    @staticmethod
    def parse_xuids(history: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for name, xuid in re.findall(r"Player connected:\s*([^,]+),\s*xuid:\s*([^,\s]+)", history, re.IGNORECASE):
            result[name.strip()] = xuid.strip()
        return result

    def query_state(self) -> tuple[dict[str, str], list[str], int, int, dict[str, str]]:
        client = self._docker_factory()
        try:
            container = client.containers.get(self.container_name)
            since = int(time.time()) - 1
            commands = "".join(f"gamerule {rule}\n" for rule in self.gamerules) + "list\n"
            self._write(container, commands)
            time.sleep(self.console_wait_seconds)
            logs = container.logs(since=since, tail=250).decode("utf-8", errors="replace")
            history = container.logs(tail=5000).decode("utf-8", errors="replace")
        finally:
            client.close()
        gamerules = self.parse_gamerules(logs, self.gamerules)
        players, online, maximum = self.parse_players(logs, history)
        return gamerules, players, online, maximum, self.parse_xuids(history)

    def query_gamerules(self, rules: set[str]) -> dict[str, str]:
        unknown = rules - GAMERULES.keys()
        if unknown:
            raise ValueError(f"Unknown gamerule names: {sorted(unknown)}")
        client = self._docker_factory()
        try:
            container = client.containers.get(self.container_name)
            since = int(time.time()) - 1
            self._write(container, "".join(f"gamerule {rule}\n" for rule in sorted(rules)))
            time.sleep(self.console_wait_seconds)
            logs = container.logs(since=since, tail=max(30, len(rules) * 5)).decode("utf-8", errors="replace")
        finally:
            client.close()
        return self.parse_gamerules(logs, sorted(rules))
