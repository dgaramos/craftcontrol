import tempfile
import unittest
import json
from pathlib import Path

from minecraft_manager.files import ServerFiles
from minecraft_manager.repository import StateRepository
from minecraft_manager.services import ManagerService


class FakeBedrock:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.telemetry_output: str | None = None
        self.query_state_result: tuple = ({}, [], 0, 0, {})
        self.query_state_error: Exception | None = None
        self.gamerule_result: dict = {}

    def send(self, parts: list[str]) -> None:
        self.commands.append(parts)

    def send_and_read(self, parts: list[str]) -> str:
        self.commands.append(parts)
        return "The time is 34"

    def set_operator(self, player: str, enabled: bool) -> None:
        self.commands.append(["op" if enabled else "deop", player])

    def query_state(self) -> tuple:
        if self.query_state_error is not None:
            raise self.query_state_error
        return self.query_state_result

    def query_gamerules(self, rules: set) -> dict:
        return self.gamerule_result

    def request_telemetry_snapshot(self) -> str:
        if self.telemetry_output is not None:
            return self.telemetry_output
        payloads = (
            {"schema": 1, "sequence": 12, "type": "snapshot.started", "timestamp": 1, "player": None, "data": {"players": 0}},
            {"schema": 1, "sequence": 12, "type": "snapshot.finished", "timestamp": 1, "player": None, "data": {}},
        )
        return "\n".join(f"[Scripting] [BEDROCK_TELEMETRY] {json.dumps(payload)}" for payload in payloads)


class FakeDocker:
    pass


class FakeRuntime:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True


class TimeActionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.directory.name)
        self.bedrock = FakeBedrock()
        repository = StateRepository(root / "state.db")
        repository.initialize()
        self.service = ManagerService(
            repository,
            ServerFiles(root / ".env", root / "server.properties"),
            self.bedrock,  # type: ignore[arg-type]
            FakeDocker(),  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_supports_every_named_time_preset(self) -> None:
        for preset in ManagerService.TIME_PRESETS:
            self.service.time_action("preset", {"value": preset})
            self.assertEqual(self.bedrock.commands[-1], ["time", "set", preset])

    def test_reset_days_sets_time_to_zero(self) -> None:
        self.service.time_action("reset-days", {})
        self.assertEqual(self.bedrock.commands[-1], ["time", "set", "0"])

    def test_rejects_exact_time_outside_one_day(self) -> None:
        with self.assertRaisesRegex(ValueError, "fora do intervalo"):
            self.service.time_action("set", {"value": 24001})

    def test_queries_day_count(self) -> None:
        result = self.service.time_action("query", {"value": "day"})
        self.assertEqual(result["value"], 34)
        self.assertEqual(self.bedrock.commands[-1], ["time", "query", "day"])

    def test_operator_access_can_be_enabled_and_disabled(self) -> None:
        self.service.set_player_operator("VonCrush", True)
        self.assertEqual(self.bedrock.commands[-1], ["op", "VonCrush"])
        self.assertEqual(self.service.players()[0]["name"], "VonCrush")
        self.assertTrue(self.service.players()[0]["operator"])
        self.service.set_player_operator("VonCrush", False)
        self.assertEqual(self.bedrock.commands[-1], ["deop", "VonCrush"])

    def test_player_disconnect_preserves_profile_and_closes_session(self) -> None:
        self.service.player_event("Nicole", True, "123")
        self.service.player_event("Nicole", False, "123")
        profile = self.service.players()[0]
        self.assertEqual(profile["name"], "Nicole")
        self.assertFalse(profile["online"])
        self.assertEqual(profile["sessions_count"], 1)

    def test_death_counter_is_deduplicated(self) -> None:
        self.service.player_event("Nicole", True, "123")
        raw = "[INFO] Nicole was slain by Zombie"
        self.assertTrue(self.service.player_death_event("Nicole", "was slain by Zombie", raw))
        self.assertFalse(self.service.player_death_event("Nicole", "was slain by Zombie", raw))
        self.assertEqual(self.service.players()[0]["deaths_count"], 1)

    def test_snapshot_response_is_ingested_without_log_stream(self) -> None:
        self.service.request_telemetry_snapshot_async("test")
        import time
        deadline = time.time() + 2
        while time.time() < deadline and self.service.state().get("telemetry", {}).get("status") != "healthy":
            time.sleep(0.01)
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "healthy")
        self.assertEqual(telemetry["sequence"], "12")

    def test_manual_snapshot_is_ingested_synchronously(self) -> None:
        self.assertEqual(self.service.request_telemetry_snapshot("manual"), 2)
        self.assertEqual(self.service.state()["telemetry"]["last_topic"], "snapshot.finished")

    def test_empty_snapshot_response_is_degraded_instead_of_stuck_syncing(self) -> None:
        self.bedrock.telemetry_output = ""
        self.assertEqual(self.service.request_telemetry_snapshot("test-empty"), 0)
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "degraded")
        self.assertEqual(telemetry["last_error"], "snapshot returned no envelopes")

    def test_sequence_gap_degrades_and_requests_reconciliation(self) -> None:
        requested: list[str] = []
        self.service.request_telemetry_snapshot_async = requested.append  # type: ignore[method-assign]
        self.service.telemetry_event({"schema": 1, "sequence": 10, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:stone"}})
        self.service.telemetry_event({"schema": 1, "sequence": 13, "type": "block.broken", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:dirt"}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "degraded")
        self.assertEqual(telemetry["gap_count"], "1")
        self.assertEqual(telemetry["missing_events"], "2")
        self.assertEqual(telemetry["last_gap"], "11-12")
        self.assertEqual(requested, ["sequence-gap"])

    def test_snapshot_repairs_degraded_state_and_stale_delta_is_rejected(self) -> None:
        self.service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
        self.service.telemetry_event({"schema": 1, "sequence": 10, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
        self.service.telemetry_event({"schema": 1, "sequence": 12, "type": "block.broken", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {}})
        self.service.telemetry_event({"schema": 1, "sequence": 11, "type": "block.placed", "timestamp": 3, "player": {"name": "VonCrush"}, "data": {}})
        self.assertEqual(self.service.state()["telemetry"]["sequence"], "12")
        self.service.telemetry_event({"schema": 1, "sequence": 12, "type": "snapshot.started", "timestamp": 4, "player": None, "data": {"players": 0}})
        self.service.telemetry_event({"schema": 1, "sequence": 12, "type": "snapshot.finished", "timestamp": 5, "player": None, "data": {}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "healthy")
        self.assertEqual(telemetry["last_error"], "")
        self.assertIn("last_snapshot_at", telemetry)

    def test_pack_sequence_reset_requests_snapshot(self) -> None:
        requested: list[str] = []
        self.service.request_telemetry_snapshot_async = requested.append  # type: ignore[method-assign]
        self.service.telemetry_event({"schema": 1, "sequence": 20, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
        self.service.telemetry_event({"schema": 1, "sequence": 1, "type": "telemetry.started", "timestamp": 2, "player": None, "data": {"version": "0.2.0"}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "syncing")
        self.assertEqual(telemetry["reset_count"], "1")
        self.assertEqual(requested, ["pack-started"])

    def test_blocked_pack_storage_stays_degraded_after_snapshot(self) -> None:
        self.service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
        storage = {"status": "blocked", "storageVersion": 1, "persistenceBlocked": True, "error": "invalid persisted state"}
        self.service.telemetry_event({"schema": 1, "sequence": 1, "type": "telemetry.started", "timestamp": 1, "player": None, "data": {"storage": storage}})
        self.service.telemetry_event({"schema": 1, "sequence": 1, "type": "snapshot.started", "timestamp": 2, "player": None, "data": {"players": 0, "storage": storage}})
        self.service.telemetry_event({"schema": 1, "sequence": 1, "type": "snapshot.finished", "timestamp": 3, "player": None, "data": {}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "degraded")
        self.assertEqual(telemetry["persistence_blocked"], "true")
        self.assertEqual(telemetry["storage_version"], "1")
        self.assertEqual(telemetry["last_error"], "telemetry pack persistence is blocked")

    def test_pack_storage_migration_is_reported_separately_from_protocol(self) -> None:
        self.service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
        storage = {"status": "migrated", "storageVersion": 1, "migratedFrom": 0, "persistenceBlocked": False}
        self.service.telemetry_event({"schema": 1, "sequence": 8, "type": "telemetry.started", "timestamp": 1, "player": None, "data": {"storage": storage}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["schema"], "1")
        self.assertEqual(telemetry["storage_version"], "1")
        self.assertEqual(telemetry["storage_migrated_from"], "0")
        self.assertEqual(telemetry["storage_status"], "migrated")

    def test_pack_capabilities_are_persisted_without_degrading_supported_metrics(self) -> None:
        self.service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
        capabilities = {
            "blocksBroken": {"supported": True},
            "dimensionChanges": {"supported": False},
        }
        self.service.telemetry_event({"schema": 1, "sequence": 4, "type": "telemetry.started", "timestamp": 1, "player": None, "data": {"capabilities": capabilities}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["capability_status"], "limited")
        self.assertEqual(telemetry["capabilities_supported"], "1")
        self.assertEqual(telemetry["capabilities_total"], "2")
        self.assertEqual(json.loads(telemetry["capabilities"]), capabilities)


def _make_service(directory: Path, bedrock: FakeBedrock | None = None, docker: FakeDocker | None = None) -> ManagerService:
    repo = StateRepository(directory / "state.db")
    repo.initialize()
    return ManagerService(
        repo,
        ServerFiles(directory / ".env", directory / "server.properties"),
        bedrock or FakeBedrock(),  # type: ignore[arg-type]
        docker or FakeDocker(),  # type: ignore[arg-type]
    )


class RefreshTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.bedrock = FakeBedrock()
        self.service = _make_service(Path(self.directory.name), self.bedrock)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_refresh_stores_settings_and_server_info(self) -> None:
        gamerules = {"keepInventory": "false"}
        self.bedrock.query_state_result = (gamerules, ["Alice"], 1, 10, {"Alice": "111"})
        self.service.refresh("test")
        state = self.service.state()
        self.assertEqual(state["online"], 1)
        self.assertEqual(state["max_players"], 10)
        self.assertEqual(state["gamerules"]["keepInventory"], "false")

    def test_refresh_max_players_falls_back_to_env(self) -> None:
        root = Path(self.directory.name)
        (root / ".env").write_text("MAX_PLAYERS=20\n")
        self.bedrock.query_state_result = ({}, [], 0, 0, {})
        self.service.refresh("test")
        state = self.service.state()
        self.assertEqual(state["max_players"], 20)

    def test_refresh_error_publishes_failed_event_and_reraises(self) -> None:
        self.bedrock.query_state_error = RuntimeError("docker gone")
        events: list[str] = []
        original_publish = self.service.broker.publish

        def capture(topic: str, *args, **kwargs):
            events.append(topic)
            return original_publish(topic, *args, **kwargs)

        self.service.broker.publish = capture  # type: ignore[method-assign]
        with self.assertRaises(RuntimeError):
            self.service.refresh("test")
        self.assertIn("state.reconciliation.failed", events)

    def test_concurrent_refresh_is_skipped(self) -> None:
        import threading
        barrier = threading.Barrier(2)
        original_query = self.bedrock.query_state

        call_count = 0

        def slow_query():
            nonlocal call_count
            call_count += 1
            barrier.wait(timeout=2)
            return original_query()

        self.bedrock.query_state = slow_query  # type: ignore[method-assign]

        t = threading.Thread(target=self.service.refresh, args=("bg",))
        t.start()
        barrier.wait(timeout=2)
        self.service.refresh("concurrent")  # should be skipped
        t.join(timeout=3)
        self.assertEqual(call_count, 1)

    def test_public_state_hides_known_players_and_bootstrap(self) -> None:
        self.bedrock.query_state_result = ({}, ["Alice"], 1, 5, {"Alice": "111"})
        self.service.refresh("test")
        pub = self.service.public_state()
        self.assertNotIn("known_players", pub)
        self.assertNotIn("bootstrap", pub)
        self.assertIn("online", pub)

    def test_refreshing_flag_is_false_after_refresh(self) -> None:
        self.service.refresh("test")
        self.assertFalse(self.service.refreshing)


class InitializeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_initialize_without_runtime_starts_refresh(self) -> None:
        import threading
        refreshed = threading.Event()
        service = _make_service(Path(self.directory.name))
        original = service.refresh

        def refresh_and_signal(reason: str = "manual") -> None:
            original(reason)
            refreshed.set()

        service.refresh = refresh_and_signal  # type: ignore[method-assign]
        service.initialize()
        self.assertTrue(refreshed.wait(timeout=3), "refresh did not run")

    def test_initialize_starts_runtime_when_attached(self) -> None:
        import threading
        refreshed = threading.Event()
        service = _make_service(Path(self.directory.name))
        original = service.refresh

        def refresh_and_signal(reason: str = "manual") -> None:
            original(reason)
            refreshed.set()

        service.refresh = refresh_and_signal  # type: ignore[method-assign]
        runtime = FakeRuntime()
        service.attach_runtime(runtime)  # type: ignore[arg-type]
        service.initialize()
        self.assertTrue(refreshed.wait(timeout=3), "refresh did not run")
        self.assertTrue(runtime.started)

    def test_attach_runtime_twice_raises(self) -> None:
        service = _make_service(Path(self.directory.name))
        runtime = FakeRuntime()
        service.attach_runtime(runtime)  # type: ignore[arg-type]
        with self.assertRaises(RuntimeError):
            service.attach_runtime(runtime)  # type: ignore[arg-type]


class SaveSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.service = _make_service(Path(self.directory.name))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_save_known_setting_persists_and_returns_keys(self) -> None:
        root = Path(self.directory.name)
        changed = self.service.save_settings({"SERVER_NAME": "TestServer"})
        self.assertEqual(changed, ["SERVER_NAME"])
        _, env_values = ServerFiles(root / ".env", root / "server.properties").read_env()
        self.assertEqual(env_values.get("SERVER_NAME"), "TestServer")

    def test_save_settings_rejects_non_dict(self) -> None:
        with self.assertRaises(TypeError):
            self.service.save_settings("bad")

    def test_save_settings_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            self.service.save_settings({"__unknown__": "value"})


class SetGameruleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.bedrock = FakeBedrock()
        self.service = _make_service(Path(self.directory.name), self.bedrock)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_set_known_gamerule_sends_command(self) -> None:
        from minecraft_manager.schema import GAMERULES
        rule = next(iter(GAMERULES))
        schema = GAMERULES[rule]
        value = schema.get("default", "false")
        self.service.set_gamerule(rule, value)
        self.assertIn(["gamerule", rule, str(value)], self.bedrock.commands)

    def test_set_unknown_gamerule_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.service.set_gamerule("__not_a_rule__", "true")


class WorldActionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.bedrock = FakeBedrock()
        self.service = _make_service(Path(self.directory.name), self.bedrock)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_run_valid_world_action_sends_command(self) -> None:
        self.service.run_world_action("day")
        self.assertEqual(self.bedrock.commands[-1], ["time", "set", "day"])

    def test_run_invalid_world_action_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.service.run_world_action("__nope__")


class TimeActionEdgeCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.bedrock = FakeBedrock()
        self.service = _make_service(Path(self.directory.name), self.bedrock)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_add_time_valid(self) -> None:
        result = self.service.time_action("add", {"value": 100})
        self.assertEqual(result["action"], "add")
        self.assertEqual(self.bedrock.commands[-1], ["time", "add", "100"])

    def test_add_time_out_of_range_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "fora do intervalo"):
            self.service.time_action("add", {"value": 0})

    def test_set_time_at_boundary_is_valid(self) -> None:
        self.service.time_action("set", {"value": 24000})
        self.assertEqual(self.bedrock.commands[-1], ["time", "set", "24000"])

    def test_weather_action_with_duration(self) -> None:
        result = self.service.time_action("weather", {"value": "rain", "duration": "500"})
        self.assertEqual(result["value"], "rain")
        self.assertEqual(self.bedrock.commands[-1], ["weather", "rain", "500"])

    def test_weather_action_without_duration(self) -> None:
        self.service.time_action("weather", {"value": "clear"})
        self.assertEqual(self.bedrock.commands[-1], ["weather", "clear"])

    def test_weather_duration_out_of_range_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "fora do intervalo"):
            self.service.time_action("weather", {"value": "rain", "duration": "0"})

    def test_weather_query_returns_weather_type(self) -> None:
        self.bedrock.send_and_read = lambda parts: "It is currently clear"  # type: ignore[method-assign]
        result = self.service.time_action("weather-query", {})
        self.assertEqual(result["value"], "clear")

    def test_weather_query_returns_unknown_for_unrecognised_output(self) -> None:
        self.bedrock.send_and_read = lambda parts: "something else"  # type: ignore[method-assign]
        result = self.service.time_action("weather-query", {})
        self.assertEqual(result["value"], "unknown")

    def test_invalid_action_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.service.time_action("__bad__", {})

    def test_invalid_preset_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.service.time_action("preset", {"value": "__bad__"})


class TelemetryCoalescingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.service = _make_service(Path(self.directory.name))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_second_request_within_cooldown_is_coalesced(self) -> None:
        import threading
        first_started = threading.Event()
        call_count = 0
        original_snapshot = self.service.request_telemetry_snapshot

        def counted_snapshot(reason: str) -> int:
            nonlocal call_count
            call_count += 1
            first_started.set()
            return original_snapshot(reason)

        self.service.request_telemetry_snapshot = counted_snapshot  # type: ignore[method-assign]

        events: list[str] = []
        original_publish = self.service.broker.publish

        def capture(topic: str, *args, **kwargs):
            events.append(topic)
            return original_publish(topic, *args, **kwargs)

        self.service.broker.publish = capture  # type: ignore[method-assign]

        # First async call sets _telemetry_last_request; second within 5s is coalesced.
        self.service.request_telemetry_snapshot_async("first")
        self.service.request_telemetry_snapshot_async("second")
        first_started.wait(timeout=3)
        self.assertIn("telemetry.snapshot.coalesced", events)
        self.assertEqual(call_count, 1)


class PlayerDelegationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.service = _make_service(Path(self.directory.name))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_players_returns_list(self) -> None:
        self.assertIsInstance(self.service.players(), list)

    def test_player_profile_returns_none_for_unknown(self) -> None:
        self.assertIsNone(self.service.player_profile("__nobody__"))

    def test_close_online_sessions_returns_list(self) -> None:
        self.service.player_event("Bob", True, "999")
        closed = self.service.close_online_sessions("server-stop")
        self.assertIn("Bob", closed)
