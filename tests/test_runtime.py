import json
import queue
import threading
import time
from unittest.mock import ANY, MagicMock, patch, call

import pytest

from minecraft_manager.runtime import EventRuntime


class FakeService:
    def players(self):
        return [{"name": "Nicole"}, {"name": "VonCrush"}]


def _make_runtime(**kwargs):
    broker = MagicMock()
    service = MagicMock()
    service.players.return_value = []
    return EventRuntime(service=service, broker=broker, container="mc", **kwargs), broker, service


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_frames_multiple_and_partial_lines_from_docker_chunks() -> None:
    chunks = [b"first line\nsecond", b" line\r\nthird line"]
    assert list(EventRuntime._decoded_log_lines(chunks)) == ["first line", "second line", "third line"]


@pytest.fixture
def parser_runtime():
    runtime = object.__new__(EventRuntime)
    runtime.service = FakeService()
    return runtime


def test_recognizes_known_player_death(parser_runtime) -> None:
    assert parser_runtime._parse_death("[2026 INFO] Nicole was slain by Zombie") == ("Nicole", "was slain by Zombie")


def test_ignores_chat_and_unknown_players(parser_runtime) -> None:
    assert parser_runtime._parse_death("[INFO] Nicole says hello") is None
    assert parser_runtime._parse_death("[INFO] Alex was slain by Zombie") is None


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------

def test_start_launches_three_daemon_threads() -> None:
    runtime, _, _ = _make_runtime()
    with patch("threading.Thread") as mock_thread:
        instances = [MagicMock() for _ in range(3)]
        mock_thread.side_effect = instances
        runtime.start()
    assert mock_thread.call_count == 3
    names = [c.kwargs["name"] for c in mock_thread.call_args_list]
    assert "bedrock-log-stream" in names
    assert "docker-event-stream" in names
    assert "safety-reconciler" in names
    for inst in instances:
        inst.start.assert_called_once()


def test_start_is_idempotent() -> None:
    runtime, _, _ = _make_runtime()
    with patch("threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        runtime.start()
        runtime.start()
    assert mock_thread.call_count == 3


def test_default_reconcile_seconds() -> None:
    runtime, _, _ = _make_runtime()
    assert runtime.reconcile_seconds == 900


def test_custom_reconcile_seconds() -> None:
    runtime, _, _ = _make_runtime(reconcile_seconds=60)
    assert runtime.reconcile_seconds == 60


# ---------------------------------------------------------------------------
# Handle log tests
# ---------------------------------------------------------------------------

@pytest.fixture
def log_runtime():
    broker = MagicMock()
    service = MagicMock()
    service.players.return_value = [{"name": "Nicole"}, {"name": "VonCrush"}]
    service.refreshing = False
    runtime = EventRuntime(service=service, broker=broker, container="mc")
    return runtime, broker, service


def test_player_connected_event(log_runtime) -> None:
    runtime, broker, service = log_runtime
    runtime._handle_log("[INFO] Player connected: Nicole, xuid: 12345")
    service.player_event.assert_called_once_with("Nicole", True, "12345")
    broker.publish.assert_called_with("player.connected", "bedrock-log", {"player": "Nicole"})


def test_player_disconnected_event(log_runtime) -> None:
    runtime, broker, service = log_runtime
    runtime._handle_log("[INFO] Player disconnected: VonCrush, xuid: 67890")
    service.player_event.assert_called_once_with("VonCrush", False, "67890")
    broker.publish.assert_called_with("player.disconnected", "bedrock-log", {"player": "VonCrush"})


def test_death_event_dispatched(log_runtime) -> None:
    runtime, broker, service = log_runtime
    runtime._handle_log("[INFO] Nicole was slain by Zombie")
    service.player_death_event.assert_called_once()
    args = service.player_death_event.call_args[0]
    assert args[0] == "Nicole"


def test_telemetry_line_dispatched(log_runtime) -> None:
    runtime, broker, service = log_runtime
    from minecraft_manager.telemetry import PREFIX
    service.telemetry_event = MagicMock()
    with patch("minecraft_manager.runtime.parse_telemetry_line") as mock_parse:
        mock_parse.return_value = {"type": "snapshot"}
        runtime._handle_log(f"[INFO] {PREFIX} {{\"type\": \"snapshot\"}}")
    service.telemetry_event.assert_called_once_with({"type": "snapshot"})


def test_telemetry_json_error_publishes_rejected(log_runtime) -> None:
    runtime, broker, service = log_runtime
    from minecraft_manager.telemetry import PREFIX
    with patch("minecraft_manager.runtime.parse_telemetry_line", side_effect=json.JSONDecodeError("bad", "", 0)):
        runtime._handle_log(f"[INFO] {PREFIX} bad")
    broker.publish.assert_called_with("telemetry.event.rejected", "bedrock-log", ANY)


def test_telemetry_none_return_skips_service(log_runtime) -> None:
    runtime, broker, service = log_runtime
    from minecraft_manager.telemetry import PREFIX
    with patch("minecraft_manager.runtime.parse_telemetry_line", return_value=None):
        runtime._handle_log(f"[INFO] {PREFIX} something")
    service.telemetry_event.assert_not_called()


def test_gamerule_line_triggers_refresh(log_runtime) -> None:
    runtime, broker, service = log_runtime
    from minecraft_manager.schema import GAMERULES
    rule = next(iter(GAMERULES))
    runtime._handle_log(f"[INFO] Gamerule {rule} changed")
    broker.publish.assert_called_with("gamerule.invalidated", "bedrock-log", ANY)
    service.refresh_gamerules_async.assert_called_once()


def test_gamerule_skipped_when_refreshing(log_runtime) -> None:
    runtime, broker, service = log_runtime
    from minecraft_manager.schema import GAMERULES
    service.refreshing = True
    rule = next(iter(GAMERULES))
    runtime._handle_log(f"[INFO] Gamerule {rule} changed")
    service.refresh_gamerules_async.assert_not_called()


def test_permission_line_triggers_refresh(log_runtime) -> None:
    runtime, broker, service = log_runtime
    with patch("threading.Timer") as mock_timer:
        mock_timer.return_value = MagicMock()
        runtime._handle_log("[INFO] op PlayerName")
    broker.publish.assert_called_with("permissions.invalidated", "bedrock-log")


def test_unknown_line_is_silent(log_runtime) -> None:
    runtime, broker, service = log_runtime
    runtime._handle_log("[INFO] Server started on port 19132")
    service.player_event.assert_not_called()
    service.player_death_event.assert_not_called()
    broker.publish.assert_not_called()


# ---------------------------------------------------------------------------
# Logs thread tests
# ---------------------------------------------------------------------------

def test_logs_connects_and_publishes_connected_event() -> None:
    runtime, broker, service = _make_runtime()
    service.refreshing = False

    fake_container = MagicMock()
    fake_container.logs.return_value = iter([])

    fake_client = MagicMock()
    fake_client.containers.get.return_value = fake_container

    call_count = 0

    def stop_after_first(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fake_client
        runtime._stop.set()
        raise Exception("stopped")

    fake_docker = MagicMock()
    fake_docker.from_env.side_effect = stop_after_first

    with patch("minecraft_manager.runtime.threading.Timer"):
        with patch.dict("sys.modules", {"docker": fake_docker}):
            runtime._logs()

    broker.publish.assert_any_call("stream.logs.connected", "docker-logs")


def test_logs_disconnects_on_exception_and_retries() -> None:
    runtime, broker, _ = _make_runtime()
    stop_event = threading.Event()
    runtime._stop = stop_event

    call_count = 0

    def fake_from_env():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            stop_event.set()
        raise Exception("docker gone")

    fake_docker = MagicMock()
    fake_docker.from_env.side_effect = fake_from_env

    with patch.dict("sys.modules", {"docker": fake_docker}):
        runtime._logs()

    broker.publish.assert_any_call("stream.logs.disconnected", "docker-logs", ANY)


def test_docker_events_connects_and_publishes() -> None:
    runtime, broker, service = _make_runtime()
    service.refreshing = False

    start_event = {"Action": "start", "id": "abc123"}
    die_event = {"Action": "die", "id": "abc123"}

    fake_client = MagicMock()
    fake_client.events.return_value = iter([start_event, die_event])
    service.close_online_sessions.return_value = ["Nicole"]

    call_count = 0

    def stop_after_first(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fake_client
        runtime._stop.set()
        raise Exception("stopped")

    fake_docker = MagicMock()
    fake_docker.from_env.side_effect = stop_after_first

    with patch.dict("sys.modules", {"docker": fake_docker}):
        runtime._docker_events()

    broker.publish.assert_any_call("stream.docker.connected", "docker-events")
    broker.publish.assert_any_call("server.start", "docker-events", {"container_id": "abc123"})
    broker.publish.assert_any_call("server.die", "docker-events", {"container_id": "abc123"})
    service.refresh_async.assert_called()
    service.close_online_sessions.assert_called()


def test_docker_events_disconnects_on_error() -> None:
    runtime, broker, _ = _make_runtime()
    stop_event = threading.Event()
    runtime._stop = stop_event

    call_count = 0

    def fake_from_env():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            stop_event.set()
        raise Exception("no docker")

    fake_docker = MagicMock()
    fake_docker.from_env.side_effect = fake_from_env

    with patch.dict("sys.modules", {"docker": fake_docker}):
        runtime._docker_events()

    broker.publish.assert_any_call("stream.docker.disconnected", "docker-events", ANY)


def test_periodic_reconciles_and_stops() -> None:
    runtime, broker, service = _make_runtime()

    call_count = 0

    def fake_wait(seconds):
        nonlocal call_count
        call_count += 1
        return call_count >= 2

    runtime._stop.wait = fake_wait
    runtime._periodic()

    broker.publish.assert_called_once_with(
        "state.reconciliation.requested", "safety-timer", {"scope": "full"}
    )
    service.refresh_async.assert_called_once_with(reason="safety-timer")


def test_docker_events_state_changed_published_when_closed() -> None:
    runtime, broker, service = _make_runtime()

    die_event = {"Action": "die", "id": "abc"}
    service.close_online_sessions.return_value = ["VonCrush"]

    fake_client = MagicMock()
    fake_client.events.return_value = iter([die_event])

    call_count = 0

    def stop_after_first(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fake_client
        runtime._stop.set()
        raise Exception("stopped")

    fake_docker = MagicMock()
    fake_docker.from_env.side_effect = stop_after_first

    with patch.dict("sys.modules", {"docker": fake_docker}):
        runtime._docker_events()

    broker.publish.assert_any_call(
        "state.changed", "docker-events",
        {"domains": ["players", "player_profiles"], "players": ["VonCrush"]}
    )


def test_docker_events_no_state_changed_when_none_closed() -> None:
    runtime, broker, service = _make_runtime()

    die_event = {"Action": "die", "id": "abc"}
    service.close_online_sessions.return_value = []

    fake_client = MagicMock()
    fake_client.events.return_value = iter([die_event])

    call_count = 0

    def stop_after_first(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fake_client
        runtime._stop.set()
        raise Exception("stopped")

    fake_docker = MagicMock()
    fake_docker.from_env.side_effect = stop_after_first

    with patch.dict("sys.modules", {"docker": fake_docker}):
        runtime._docker_events()

    calls = [str(c) for c in broker.publish.call_args_list]
    assert not any("state.changed" in c for c in calls)
