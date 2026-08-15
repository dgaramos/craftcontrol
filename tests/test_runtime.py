import queue
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, call

from minecraft_manager.runtime import EventRuntime


class FakeService:
    def players(self):
        return [{"name": "Nicole"}, {"name": "VonCrush"}]


class RuntimeParserTest(unittest.TestCase):
    def test_frames_multiple_and_partial_lines_from_docker_chunks(self) -> None:
        chunks = [b"first line\nsecond", b" line\r\nthird line"]
        self.assertEqual(list(EventRuntime._decoded_log_lines(chunks)), ["first line", "second line", "third line"])

    def setUp(self) -> None:
        self.runtime = object.__new__(EventRuntime)
        self.runtime.service = FakeService()

    def test_recognizes_known_player_death(self) -> None:
        self.assertEqual(
            self.runtime._parse_death("[2026 INFO] Nicole was slain by Zombie"),
            ("Nicole", "was slain by Zombie"),
        )

    def test_ignores_chat_and_unknown_players(self) -> None:
        self.assertIsNone(self.runtime._parse_death("[INFO] Nicole says hello"))
        self.assertIsNone(self.runtime._parse_death("[INFO] Alex was slain by Zombie"))


class RuntimeInitTest(unittest.TestCase):
    def _make_runtime(self, **kwargs):
        broker = MagicMock()
        service = MagicMock()
        service.players.return_value = []
        return EventRuntime(service=service, broker=broker, container="mc", **kwargs), broker, service

    def test_start_launches_three_daemon_threads(self):
        runtime, _, _ = self._make_runtime()
        with patch("threading.Thread") as mock_thread:
            instances = [MagicMock() for _ in range(3)]
            mock_thread.side_effect = instances
            runtime.start()
        self.assertEqual(mock_thread.call_count, 3)
        names = [c.kwargs["name"] for c in mock_thread.call_args_list]
        self.assertIn("bedrock-log-stream", names)
        self.assertIn("docker-event-stream", names)
        self.assertIn("safety-reconciler", names)
        for inst in instances:
            inst.start.assert_called_once()

    def test_start_is_idempotent(self):
        runtime, _, _ = self._make_runtime()
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            runtime.start()
            runtime.start()
        self.assertEqual(mock_thread.call_count, 3)

    def test_default_reconcile_seconds(self):
        runtime, _, _ = self._make_runtime()
        self.assertEqual(runtime.reconcile_seconds, 900)

    def test_custom_reconcile_seconds(self):
        runtime, _, _ = self._make_runtime(reconcile_seconds=60)
        self.assertEqual(runtime.reconcile_seconds, 60)


class RuntimeHandleLogTest(unittest.TestCase):
    def setUp(self):
        broker = MagicMock()
        service = MagicMock()
        service.players.return_value = [{"name": "Nicole"}, {"name": "VonCrush"}]
        service.refreshing = False
        self.runtime = EventRuntime(service=service, broker=broker, container="mc")
        self.broker = broker
        self.service = service

    def test_player_connected_event(self):
        self.runtime._handle_log("[INFO] Player connected: Nicole, xuid: 12345")
        self.service.player_event.assert_called_once_with("Nicole", True, "12345")
        self.broker.publish.assert_called_with("player.connected", "bedrock-log", {"player": "Nicole"})

    def test_player_disconnected_event(self):
        self.runtime._handle_log("[INFO] Player disconnected: VonCrush, xuid: 67890")
        self.service.player_event.assert_called_once_with("VonCrush", False, "67890")
        self.broker.publish.assert_called_with("player.disconnected", "bedrock-log", {"player": "VonCrush"})

    def test_death_event_dispatched(self):
        self.runtime._handle_log("[INFO] Nicole was slain by Zombie")
        self.service.player_death_event.assert_called_once()
        args = self.service.player_death_event.call_args[0]
        self.assertEqual(args[0], "Nicole")

    def test_telemetry_line_dispatched(self):
        from minecraft_manager.telemetry import PREFIX
        self.service.telemetry_event = MagicMock()
        with patch("minecraft_manager.runtime.parse_telemetry_line") as mock_parse:
            mock_parse.return_value = {"type": "snapshot"}
            self.runtime._handle_log(f"[INFO] {PREFIX} {{\"type\": \"snapshot\"}}")
        self.service.telemetry_event.assert_called_once_with({"type": "snapshot"})

    def test_telemetry_json_error_publishes_rejected(self):
        from minecraft_manager.telemetry import PREFIX
        import json
        with patch("minecraft_manager.runtime.parse_telemetry_line", side_effect=json.JSONDecodeError("bad", "", 0)):
            self.runtime._handle_log(f"[INFO] {PREFIX} bad")
        self.broker.publish.assert_called_with("telemetry.event.rejected", "bedrock-log", unittest.mock.ANY)

    def test_telemetry_none_return_skips_service(self):
        from minecraft_manager.telemetry import PREFIX
        with patch("minecraft_manager.runtime.parse_telemetry_line", return_value=None):
            self.runtime._handle_log(f"[INFO] {PREFIX} something")
        self.service.telemetry_event.assert_not_called()

    def test_gamerule_line_triggers_refresh(self):
        from minecraft_manager.schema import GAMERULES
        rule = next(iter(GAMERULES))
        self.runtime._handle_log(f"[INFO] Gamerule {rule} changed")
        self.broker.publish.assert_called_with("gamerule.invalidated", "bedrock-log", unittest.mock.ANY)
        self.service.refresh_gamerules_async.assert_called_once()

    def test_gamerule_skipped_when_refreshing(self):
        from minecraft_manager.schema import GAMERULES
        self.service.refreshing = True
        rule = next(iter(GAMERULES))
        self.runtime._handle_log(f"[INFO] Gamerule {rule} changed")
        self.service.refresh_gamerules_async.assert_not_called()

    def test_permission_line_triggers_refresh(self):
        with patch("threading.Timer") as mock_timer:
            mock_timer.return_value = MagicMock()
            self.runtime._handle_log("[INFO] op PlayerName")
        self.broker.publish.assert_called_with("permissions.invalidated", "bedrock-log")

    def test_unknown_line_is_silent(self):
        self.runtime._handle_log("[INFO] Server started on port 19132")
        self.service.player_event.assert_not_called()
        self.service.player_death_event.assert_not_called()
        self.broker.publish.assert_not_called()


class RuntimeLogsThreadTest(unittest.TestCase):
    def _make_runtime(self):
        broker = MagicMock()
        service = MagicMock()
        service.players.return_value = []
        service.refreshing = False
        runtime = EventRuntime(service=service, broker=broker, container="mc", reconcile_seconds=900)
        return runtime, broker, service

    def test_logs_connects_and_publishes_connected_event(self):
        runtime, broker, service = self._make_runtime()

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
                try:
                    runtime._logs()
                except Exception:
                    pass

        broker.publish.assert_any_call("stream.logs.connected", "docker-logs")

    def test_logs_disconnects_on_exception_and_retries(self):
        runtime, broker, _ = self._make_runtime()
        # Use a real Event but pre-set it so the second loop iteration exits
        stop_event = threading.Event()
        runtime._stop = stop_event

        call_count = 0
        original_from_env = None

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

        broker.publish.assert_any_call(
            "stream.logs.disconnected", "docker-logs", unittest.mock.ANY
        )

    def test_docker_events_connects_and_publishes(self):
        runtime, broker, service = self._make_runtime()

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
            try:
                runtime._docker_events()
            except Exception:
                pass

        broker.publish.assert_any_call("stream.docker.connected", "docker-events")
        broker.publish.assert_any_call("server.start", "docker-events", {"container_id": "abc123"})
        broker.publish.assert_any_call("server.die", "docker-events", {"container_id": "abc123"})
        service.refresh_async.assert_called()
        service.close_online_sessions.assert_called()

    def test_docker_events_disconnects_on_error(self):
        runtime, broker, _ = self._make_runtime()
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

        broker.publish.assert_any_call(
            "stream.docker.disconnected", "docker-events", unittest.mock.ANY
        )

    def test_periodic_reconciles_and_stops(self):
        runtime, broker, service = self._make_runtime()

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

    def test_docker_events_state_changed_published_when_closed(self):
        runtime, broker, service = self._make_runtime()

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
            try:
                runtime._docker_events()
            except Exception:
                pass

        broker.publish.assert_any_call(
            "state.changed", "docker-events",
            {"domains": ["players", "player_profiles"], "players": ["VonCrush"]}
        )

    def test_docker_events_no_state_changed_when_none_closed(self):
        runtime, broker, service = self._make_runtime()

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
            try:
                runtime._docker_events()
            except Exception:
                pass

        calls = [str(c) for c in broker.publish.call_args_list]
        self.assertFalse(any("state.changed" in c for c in calls))
