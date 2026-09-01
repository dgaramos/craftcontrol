import json
import threading
import time
from pathlib import Path

import pytest

from minecraft_manager.files import ServerFiles
from minecraft_manager.services import ManagerService
from conftest import make_manager_service as _make_service
from fakes import FakeBedrock, FakeDocker, FakeRuntime


# ---------------------------------------------------------------------------
# Time actions
# ---------------------------------------------------------------------------

def test_supports_every_named_time_preset(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    for preset in ManagerService.TIME_PRESETS:
        service.time_action("preset", {"value": preset})
        assert bedrock.commands[-1] == ["time", "set", preset]


def test_reset_days_sets_time_to_zero(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    service.time_action("reset-days", {})
    assert bedrock.commands[-1] == ["time", "set", "0"]


def test_rejects_exact_time_outside_one_day(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(ValueError, match="fora do intervalo"):
        service.time_action("set", {"value": 24001})


def test_queries_day_count(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    result = service.time_action("query", {"value": "day"})
    assert result["value"] == 34
    assert bedrock.commands[-1] == ["time", "query", "day"]


def test_operator_access_can_be_enabled_and_disabled(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    service.set_player_operator("VonCrush", True)
    assert bedrock.commands[-1] == ["op", "VonCrush"]
    assert service.players()[0]["name"] == "VonCrush"
    assert service.players()[0]["operator"]
    service.set_player_operator("VonCrush", False)
    assert bedrock.commands[-1] == ["deop", "VonCrush"]


def test_player_disconnect_preserves_profile_and_closes_session(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.player_event("Nicole", True, "123")
    service.player_event("Nicole", False, "123")
    profile = service.players()[0]
    assert profile["name"] == "Nicole"
    assert not profile["online"]
    assert profile["sessions_count"] == 1


def test_death_counter_is_deduplicated(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.player_event("Nicole", True, "123")
    raw = "[INFO] Nicole was slain by Zombie"
    assert service.player_death_event("Nicole", "was slain by Zombie", raw)
    assert not service.player_death_event("Nicole", "was slain by Zombie", raw)
    assert service.players()[0]["deaths_count"] == 1


def test_snapshot_response_is_ingested_without_log_stream(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.request_telemetry_snapshot_async("test")
    deadline = time.time() + 2
    while time.time() < deadline and service.state().get("telemetry", {}).get("status") != "healthy":
        time.sleep(0.01)
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "healthy"
    assert telemetry["sequence"] == "12"


def test_manual_snapshot_is_ingested_synchronously(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    assert service.request_telemetry_snapshot("manual") == 2
    assert service.state()["telemetry"]["last_topic"] == "snapshot.finished"


def test_diagnostics_summarize_telemetry_and_broker_counters(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event({"schema": 1, "sequence": 10, "type": "blocks.changed", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 10, "type": "blocks.changed", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 9, "type": "blocks.changed", "timestamp": 3, "player": {"name": "VonCrush"}, "data": {}})

    diagnostics = service.diagnostics()

    assert diagnostics["telemetry"]["accepted"] == 1
    assert diagnostics["telemetry"]["rejected"] == 2
    assert diagnostics["telemetry"]["duplicates"] == 1
    assert diagnostics["telemetry"]["old"] == 1
    assert diagnostics["telemetry"]["by_topic"]["blocks.changed"] == {
        "accepted": 1, "rejected": 2, "duplicates": 1, "old": 1,
        "gaps": 0, "resets": 0,
    }
    assert diagnostics["telemetry"]["ingestion_duration_ms_max"] >= 0
    assert diagnostics["broker"]["events_by_topic"]["telemetry.sequence.rejected"] == 2
    assert diagnostics["persistence"].keys() == {"connections", "wait_ms_average", "wait_ms_max", "contention_failures", "retries", "database_size_bytes"}
    assert diagnostics["runtime"].keys() == {"refreshing", "pending_gamerule_refreshes", "gamerule_worker_running", "snapshot_running"}
    assert diagnostics["telemetry_state"].keys() == {"status", "sequence", "expected_sequence", "gap_count", "missing_events", "reset_count", "last_snapshot_at", "last_event_at"}


def test_telemetry_event_rejects_boolean_sequence(tmp_path: Path) -> None:
    service = _make_service(tmp_path)

    with pytest.raises(ValueError, match="sequence must be an integer"):
        service.telemetry_event({"schema": 1, "sequence": True, "type": "blocks.changed", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})


def test_diagnostics_tolerate_a_broker_without_diagnostics(tmp_path: Path) -> None:
    service = _make_service(tmp_path, manager_broker=object())
    assert service.diagnostics()["broker"] == {}


def test_diagnostics_count_repository_rejection_by_snapshot_topic(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    envelope = {"schema": 1, "sequence": 1, "type": "snapshot.started", "timestamp": 1, "player": None, "data": {}}

    service.telemetry_event(envelope)
    service.telemetry_event(envelope)

    assert service.diagnostics()["telemetry"]["by_topic"]["snapshot.started"]["rejected"] == 1


def test_empty_snapshot_response_is_degraded_instead_of_stuck_syncing(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.telemetry_output = ""
    service = _make_service(tmp_path, bedrock)
    assert service.request_telemetry_snapshot("test-empty") == 0
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "degraded"
    assert telemetry["last_error"] == "snapshot returned no envelopes"


def test_sequence_gap_degrades_and_requests_reconciliation(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    requested: list[str] = []
    service.request_telemetry_snapshot_async = requested.append  # type: ignore[method-assign]
    service.telemetry_event({"schema": 1, "sequence": 10, "type": "blocks.changed", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 13, "type": "blocks.changed", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {}})
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "degraded"
    assert telemetry["gap_count"] == "1"
    assert telemetry["missing_events"] == "2"
    assert telemetry["last_gap"] == "11-12"
    assert requested == ["sequence-gap"]
    assert service.diagnostics()["telemetry"]["sequence"]["lost"] == 2
    assert service.diagnostics()["telemetry"]["by_topic"]["blocks.changed"]["gaps"] == 1


def test_snapshot_repairs_degraded_state_and_stale_delta_is_rejected(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
    service.telemetry_event({"schema": 1, "sequence": 10, "type": "blocks.changed", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 12, "type": "blocks.changed", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 11, "type": "player.joined", "timestamp": 3, "player": {"name": "VonCrush"}, "data": {}})
    assert service.state()["telemetry"]["sequence"] == "12"
    service.telemetry_event({"schema": 1, "sequence": 12, "type": "snapshot.started", "timestamp": 4, "player": None, "data": {"players": 0}})
    service.telemetry_event({"schema": 1, "sequence": 12, "type": "snapshot.finished", "timestamp": 5, "player": None, "data": {}})
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "healthy"
    assert telemetry["last_error"] == ""
    assert "last_snapshot_at" in telemetry


def test_pack_sequence_reset_requests_snapshot(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    requested: list[str] = []
    service.request_telemetry_snapshot_async = requested.append  # type: ignore[method-assign]
    service.telemetry_event({"schema": 1, "sequence": 20, "type": "blocks.changed", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 1, "type": "telemetry.started", "timestamp": 2, "player": None, "data": {"version": "0.2.0"}})
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "syncing"
    assert telemetry["reset_count"] == "1"
    assert requested == ["pack-started"]
    assert service.diagnostics()["telemetry"]["by_topic"]["telemetry.started"]["resets"] == 1
    assert service.diagnostics()["telemetry"]["sequence"]["resets"] == 1


def test_sequence_losses_are_global_when_a_different_topic_detects_the_gap(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
    service.telemetry_event({"schema": 1, "sequence": 10, "type": "player.joined", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 13, "type": "blocks.changed", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {}})

    telemetry = service.diagnostics()["telemetry"]
    assert telemetry["sequence"] == {"lost": 2, "gaps": 1, "resets": 0}
    assert telemetry["by_topic"]["player.joined"]["gaps"] == 0
    assert telemetry["by_topic"]["blocks.changed"]["gaps"] == 1


def test_blocked_pack_storage_stays_degraded_after_snapshot(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
    storage = {"status": "blocked", "storageVersion": 1, "persistenceBlocked": True, "error": "invalid persisted state"}
    service.telemetry_event({"schema": 1, "sequence": 1, "type": "telemetry.started", "timestamp": 1, "player": None, "data": {"storage": storage}})
    service.telemetry_event({"schema": 1, "sequence": 1, "type": "snapshot.started", "timestamp": 2, "player": None, "data": {"players": 0, "storage": storage}})
    service.telemetry_event({"schema": 1, "sequence": 1, "type": "snapshot.finished", "timestamp": 3, "player": None, "data": {}})
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "degraded"
    assert telemetry["persistence_blocked"] == "true"
    assert telemetry["storage_version"] == "1"
    assert telemetry["last_error"] == "telemetry pack persistence is blocked"


def test_pack_storage_migration_is_reported_separately_from_protocol(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
    storage = {"status": "migrated", "storageVersion": 1, "migratedFrom": 0, "persistenceBlocked": False}
    service.telemetry_event({"schema": 1, "sequence": 8, "type": "telemetry.started", "timestamp": 1, "player": None, "data": {"storage": storage}})
    telemetry = service.state()["telemetry"]
    assert telemetry["schema"] == "1"
    assert telemetry["storage_version"] == "1"
    assert telemetry["storage_migrated_from"] == "0"
    assert telemetry["storage_status"] == "migrated"


def test_pack_capabilities_are_persisted_without_degrading_supported_metrics(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
    capabilities = {
        "blocksBroken": {"supported": True},
        "dimensionChanges": {"supported": False},
    }
    service.telemetry_event({"schema": 1, "sequence": 4, "type": "telemetry.started", "timestamp": 1, "player": None, "data": {"capabilities": capabilities}})
    telemetry = service.state()["telemetry"]
    assert telemetry["capability_status"] == "limited"
    assert telemetry["capabilities_supported"] == "1"
    assert telemetry["capabilities_total"] == "2"
    assert json.loads(telemetry["capabilities"]) == capabilities


# ---------------------------------------------------------------------------
# Refresh tests
# ---------------------------------------------------------------------------

def test_refresh_stores_settings_and_server_info(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    gamerules = {"keepInventory": "false"}
    bedrock.query_state_result = (gamerules, ["Alice"], 1, 10, {"Alice": "111"})
    service.refresh("test")
    state = service.state()
    assert state["online"] == 1
    assert state["max_players"] == 10
    assert state["gamerules"]["keepInventory"] == "false"


def test_refresh_max_players_does_not_read_deployment_env(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    (tmp_path / ".env").write_text("MAX_PLAYERS=20\n")
    bedrock.query_state_result = ({}, [], 0, 0, {})
    service.refresh("test")
    assert service.state()["max_players"] == 0


def test_refresh_error_publishes_failed_event_and_reraises(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    bedrock.query_state_error = RuntimeError("docker gone")
    events: list[str] = []
    original_publish = service.broker.publish

    def capture(topic: str, *args, **kwargs):
        events.append(topic)
        return original_publish(topic, *args, **kwargs)

    service.broker.publish = capture  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        service.refresh("test")
    assert "state.reconciliation.failed" in events


def test_concurrent_refresh_is_skipped(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    entered = threading.Event()
    release = threading.Event()
    original_query = bedrock.query_state
    call_count = 0

    def slow_query():
        nonlocal call_count
        call_count += 1
        entered.set()
        release.wait(timeout=3)
        return original_query()

    bedrock.query_state = slow_query  # type: ignore[method-assign]
    t = threading.Thread(target=service.refresh, args=("bg",))
    t.start()
    assert entered.wait(timeout=3)
    service.refresh("concurrent")
    release.set()
    t.join(timeout=3)
    assert call_count == 1


def test_public_state_hides_known_players_and_bootstrap(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    bedrock.query_state_result = ({}, ["Alice"], 1, 5, {"Alice": "111"})
    service.refresh("test")
    pub = service.public_state()
    assert "known_players" not in pub
    assert "bootstrap" not in pub
    assert "online" in pub


def test_refreshing_flag_is_false_after_refresh(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.refresh("test")
    assert not service.refreshing


# ---------------------------------------------------------------------------
# Initialize tests
# ---------------------------------------------------------------------------

def test_initialize_without_runtime_starts_refresh(tmp_path: Path) -> None:
    refreshed = threading.Event()
    service = _make_service(tmp_path)
    original = service._reconciliation.refresh

    def refresh_and_signal(reason: str = "manual") -> None:
        original(reason)
        refreshed.set()

    service._reconciliation.refresh = refresh_and_signal  # type: ignore[method-assign]
    service.initialize()
    assert refreshed.wait(timeout=10), "refresh did not run"


def test_initialize_starts_runtime_when_attached(tmp_path: Path) -> None:
    refreshed = threading.Event()
    service = _make_service(tmp_path)
    original = service._reconciliation.refresh

    def refresh_and_signal(reason: str = "manual") -> None:
        original(reason)
        refreshed.set()

    service._reconciliation.refresh = refresh_and_signal  # type: ignore[method-assign]
    runtime = FakeRuntime()
    service.attach_runtime(runtime)  # type: ignore[arg-type]
    service.initialize()
    assert refreshed.wait(timeout=10), "refresh did not run"
    assert runtime.started


def test_attach_runtime_twice_raises(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    runtime = FakeRuntime()
    service.attach_runtime(runtime)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        service.attach_runtime(runtime)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Save settings tests
# ---------------------------------------------------------------------------

def test_save_known_setting_persists_to_bedrock_properties_and_returns_keys(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    changed, operation_id = service.save_settings({"SERVER_NAME": "TestServer"})
    assert changed == ["SERVER_NAME"]
    assert operation_id is None  # no operation_service wired in this fixture
    properties = ServerFiles(tmp_path / ".env", tmp_path / "server.properties").read_properties()
    assert properties.get("server-name") == "TestServer"


def test_save_settings_rejects_non_dict(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(TypeError):
        service.save_settings("bad")  # type: ignore[arg-type]


def test_save_settings_rejects_unknown_keys(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(ValueError):
        service.save_settings({"__unknown__": "value"})


# ---------------------------------------------------------------------------
# Set gamerule tests
# ---------------------------------------------------------------------------

def test_set_known_gamerule_sends_command(tmp_path: Path) -> None:
    from minecraft_manager.schema import GAMERULES
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    rule = next(iter(GAMERULES))
    schema = GAMERULES[rule]
    value = schema.get("default", "false")
    service.set_gamerule(rule, value)
    assert ["gamerule", rule, str(value)] in bedrock.commands


def test_set_unknown_gamerule_raises_key_error(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(KeyError):
        service.set_gamerule("__not_a_rule__", "true")


# ---------------------------------------------------------------------------
# World action tests
# ---------------------------------------------------------------------------

def test_run_valid_world_action_sends_command(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    service.run_world_action("day")
    assert bedrock.commands[-1] == ["time", "set", "day"]


def test_run_invalid_world_action_raises_key_error(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(KeyError):
        service.run_world_action("__nope__")


# ---------------------------------------------------------------------------
# Time action edge cases
# ---------------------------------------------------------------------------

def test_add_time_valid(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    result = service.time_action("add", {"value": 100})
    assert result["action"] == "add"
    assert bedrock.commands[-1] == ["time", "add", "100"]


def test_add_time_out_of_range_raises(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(ValueError, match="fora do intervalo"):
        service.time_action("add", {"value": 0})


def test_set_time_at_boundary_is_valid(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    service.time_action("set", {"value": 24000})
    assert bedrock.commands[-1] == ["time", "set", "24000"]


def test_weather_action_with_duration(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    result = service.time_action("weather", {"value": "rain", "duration": "500"})
    assert result["value"] == "rain"
    assert bedrock.commands[-1] == ["weather", "rain", "500"]


def test_weather_action_without_duration(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    service.time_action("weather", {"value": "clear"})
    assert bedrock.commands[-1] == ["weather", "clear"]


def test_weather_duration_out_of_range_raises(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(ValueError, match="fora do intervalo"):
        service.time_action("weather", {"value": "rain", "duration": "0"})


def test_weather_query_returns_weather_type(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    bedrock.send_and_read = lambda parts: "It is currently clear"  # type: ignore[method-assign]
    result = service.time_action("weather-query", {})
    assert result["value"] == "clear"


def test_weather_query_returns_unknown_for_unrecognised_output(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    bedrock.send_and_read = lambda parts: "something else"  # type: ignore[method-assign]
    result = service.time_action("weather-query", {})
    assert result["value"] == "unknown"


def test_invalid_action_raises_key_error(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(KeyError):
        service.time_action("__bad__", {})


def test_invalid_preset_raises_key_error(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    with pytest.raises(KeyError):
        service.time_action("preset", {"value": "__bad__"})


# ---------------------------------------------------------------------------
# Telemetry coalescing
# ---------------------------------------------------------------------------

def test_second_request_within_cooldown_is_coalesced(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    first_started = threading.Event()
    call_count = 0
    original_snapshot = service._reconciliation.request_telemetry_snapshot

    def counted_snapshot(reason: str) -> int:
        nonlocal call_count
        call_count += 1
        first_started.set()
        return original_snapshot(reason)

    service._reconciliation.request_telemetry_snapshot = counted_snapshot  # type: ignore[method-assign]

    events: list[str] = []
    original_publish = service.broker.publish

    def capture(topic: str, *args, **kwargs):
        events.append(topic)
        return original_publish(topic, *args, **kwargs)

    service.broker.publish = capture  # type: ignore[method-assign]

    service.request_telemetry_snapshot_async("first")
    service.request_telemetry_snapshot_async("second")
    first_started.wait(timeout=3)
    assert "telemetry.snapshot.coalesced" in events
    assert call_count == 1


# ---------------------------------------------------------------------------
# Player delegation
# ---------------------------------------------------------------------------

def test_players_returns_known_player_fields(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.player_event("VonCrush", True, "xuid-1")
    players = service.players()
    assert len(players) == 1
    assert players[0]["name"] == "VonCrush"
    assert "online" in players[0]


def test_player_profile_returns_none_for_unknown(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    assert service.player_profile("__nobody__") is None


def test_player_profile_returns_profile_for_known_player(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.player_event("VonCrush", True, "xuid-1")
    player_id = service.players()[0]["id"]
    profile = service.player_profile(player_id)
    assert profile is not None
    assert profile["name"] == "VonCrush"


def test_close_online_sessions_returns_list(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.player_event("Bob", True, "999")
    closed = service.close_online_sessions("server-stop")
    assert "Bob" in closed


# ---------------------------------------------------------------------------
# Constructor guard tests
# ---------------------------------------------------------------------------

def test_missing_player_service_raises_type_error(tmp_path: Path) -> None:
    from minecraft_manager.events import EventBroker
    from minecraft_manager.files import ServerFiles
    from minecraft_manager.reconciliation import ReconciliationService
    from minecraft_manager.repository import StateRepository
    from minecraft_manager.server import WorldService
    from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository
    from minecraft_manager.telemetry_service import TelemetryService
    from fakes import FakeBedrock, FakeDocker
    db_path = tmp_path / "state.db"
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    bedrock = FakeBedrock()
    docker = FakeDocker()
    broker = EventBroker(repo)
    telemetry_service = TelemetryService(SQLiteTelemetryRepository(db_path), broker)
    world_service = WorldService(bedrock, broker)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="player_service is required"):
        ManagerService(
            repo, files, bedrock, docker, broker=broker,  # type: ignore[arg-type]
            player_service=None,
            telemetry_service=telemetry_service,
            world_service=world_service,
            reconciliation_service=None,
        )


def test_missing_telemetry_service_raises_type_error(tmp_path: Path) -> None:
    from minecraft_manager.events import EventBroker
    from minecraft_manager.files import ServerFiles
    from minecraft_manager.players import PlayerService, SQLitePlayerRepository
    from minecraft_manager.repository import StateRepository
    from minecraft_manager.server import WorldService
    from fakes import FakeBedrock, FakeDocker
    db_path = tmp_path / "state.db"
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    bedrock = FakeBedrock()
    docker = FakeDocker()
    broker = EventBroker(repo)
    player_service = PlayerService(SQLitePlayerRepository(db_path), files, bedrock, broker)  # type: ignore[arg-type]
    world_service = WorldService(bedrock, broker)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="telemetry_service is required"):
        ManagerService(
            repo, files, bedrock, docker, broker=broker,  # type: ignore[arg-type]
            player_service=player_service,
            telemetry_service=None,
            world_service=world_service,
            reconciliation_service=None,
        )


def test_missing_world_service_raises_type_error(tmp_path: Path) -> None:
    from minecraft_manager.events import EventBroker
    from minecraft_manager.files import ServerFiles
    from minecraft_manager.players import PlayerService, SQLitePlayerRepository
    from minecraft_manager.repository import StateRepository
    from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository
    from minecraft_manager.telemetry_service import TelemetryService
    from fakes import FakeBedrock, FakeDocker
    db_path = tmp_path / "state.db"
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    bedrock = FakeBedrock()
    docker = FakeDocker()
    broker = EventBroker(repo)
    player_service = PlayerService(SQLitePlayerRepository(db_path), files, bedrock, broker)  # type: ignore[arg-type]
    telemetry_service = TelemetryService(SQLiteTelemetryRepository(db_path), broker)
    with pytest.raises(TypeError, match="world_service is required"):
        ManagerService(
            repo, files, bedrock, docker, broker=broker,  # type: ignore[arg-type]
            player_service=player_service,
            telemetry_service=telemetry_service,
            world_service=None,
            reconciliation_service=None,
        )


def test_missing_reconciliation_service_raises_type_error(tmp_path: Path) -> None:
    from minecraft_manager.events import EventBroker
    from minecraft_manager.files import ServerFiles
    from minecraft_manager.players import PlayerService, SQLitePlayerRepository
    from minecraft_manager.repository import StateRepository
    from minecraft_manager.server import WorldService
    from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository
    from minecraft_manager.telemetry_service import TelemetryService
    from fakes import FakeBedrock, FakeDocker
    db_path = tmp_path / "state.db"
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    bedrock = FakeBedrock()
    docker = FakeDocker()
    broker = EventBroker(repo)
    player_service = PlayerService(SQLitePlayerRepository(db_path), files, bedrock, broker)  # type: ignore[arg-type]
    telemetry_service = TelemetryService(SQLiteTelemetryRepository(db_path), broker)
    world_service = WorldService(bedrock, broker)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reconciliation_service is required"):
        ManagerService(
            repo, files, bedrock, docker, broker=broker,  # type: ignore[arg-type]
            player_service=player_service,
            telemetry_service=telemetry_service,
            world_service=world_service,
            reconciliation_service=None,
        )


# ---------------------------------------------------------------------------
# Analytics delegation tests
# ---------------------------------------------------------------------------

# Sentinel used to verify pass-through behaviour without inspecting internals.
_SENTINEL: dict = {"__sentinel__": True}


class _FakeReconciliation:
    """Minimal ReconciliationService fake that records refresh_gamerules_async calls."""

    def __init__(self) -> None:
        self.gamerules_calls: list[set] = []

    def refresh_gamerules_async(self, rules: set) -> None:  # noqa: D401
        self.gamerules_calls.append(rules)

    # Stubs required so ManagerService can be constructed without errors.
    def refresh(self, reason: str = "manual") -> None:  # noqa: D401
        pass

    def refresh_async(self, reason: str = "manual") -> None:  # noqa: D401
        pass

    def request_telemetry_snapshot_async(self, reason: str) -> None:  # noqa: D401
        pass

    def request_telemetry_snapshot(self, reason: str) -> int:  # noqa: D401
        return 0


class _FakePlayerService:
    """Minimal PlayerService fake that records calls and returns _SENTINEL."""

    def __init__(self) -> None:
        self.permissions_calls: list[bool] = []
        self.activity_calls: list[tuple] = []
        self.rankings_calls: list[int] = []
        self.blocks_calls: list[int] = []
        self.combat_calls: list[int] = []
        self.exploration_calls: list[int] = []
        self.periods_calls: list[tuple] = []

    def refresh_permissions(self, publish: bool = True) -> None:  # noqa: D401
        self.permissions_calls.append(publish)

    def activity(self, kind: str, player: str, source: str, search: str, days: int, page: int, page_size: int) -> dict:
        self.activity_calls.append((kind, player, source, search, days, page, page_size))
        return _SENTINEL

    def rankings(self, limit: int = 10) -> dict:
        self.rankings_calls.append(limit)
        return _SENTINEL

    def blocks(self, limit: int = 10) -> dict:
        self.blocks_calls.append(limit)
        return _SENTINEL

    def combat(self, limit: int = 10) -> dict:
        self.combat_calls.append(limit)
        return _SENTINEL

    def exploration(self, limit: int = 10) -> dict:
        self.exploration_calls.append(limit)
        return _SENTINEL

    def periods(self, days: int = 30, limit: int = 10) -> dict:
        self.periods_calls.append((days, limit))
        return _SENTINEL

    # Stubs required by ManagerService methods called in other tests.
    def observe_presence(self, player: str, connected: bool, xuid: str = "") -> None:
        pass

    def close_online_sessions(self, reason: str) -> list:
        return []

    def record_derived_death(self, player: str, cause: str, raw: str) -> bool:
        return False

    def list_profiles(self) -> list:
        return []

    def profile(self, identity: str) -> dict | None:
        return None

    def set_operator(self, player: str, enabled: bool) -> None:
        pass


def _make_service_with_fakes(
    tmp_path: Path,
    reconciliation: _FakeReconciliation | None = None,
    player_service: _FakePlayerService | None = None,
) -> "ManagerService":
    """Build a ManagerService with injected fakes instead of real services."""
    from minecraft_manager.events import EventBroker
    from minecraft_manager.files import ServerFiles
    from minecraft_manager.repository import StateRepository
    from minecraft_manager.server import WorldService
    from minecraft_manager.services import ManagerService
    from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository
    from minecraft_manager.telemetry_service import TelemetryService
    from fakes import FakeBedrock, FakeDocker

    db_path = tmp_path / "state.db"
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    bedrock = FakeBedrock()
    docker = FakeDocker()
    broker = EventBroker(repo)
    telemetry_service = TelemetryService(SQLiteTelemetryRepository(db_path), broker)
    world_service = WorldService(bedrock, broker)  # type: ignore[arg-type]

    return ManagerService(
        repo,
        files,
        bedrock,  # type: ignore[arg-type]
        docker,  # type: ignore[arg-type]
        broker=broker,
        player_service=player_service or _FakePlayerService(),  # type: ignore[arg-type]
        telemetry_service=telemetry_service,
        world_service=world_service,
        reconciliation_service=reconciliation or _FakeReconciliation(),  # type: ignore[arg-type]
    )


def test_refresh_gamerules_async_delegates(tmp_path: Path) -> None:
    fake_reconciliation = _FakeReconciliation()
    service = _make_service_with_fakes(tmp_path, reconciliation=fake_reconciliation)
    rules = {"keepInventory", "doFireTick"}
    service.refresh_gamerules_async(rules)
    assert fake_reconciliation.gamerules_calls == [rules]


def test_refresh_permissions_delegates(tmp_path: Path) -> None:
    fake_player = _FakePlayerService()
    service = _make_service_with_fakes(tmp_path, player_service=fake_player)
    service.refresh_permissions(publish=False)
    assert fake_player.permissions_calls == [False]


def test_player_activity_delegates(tmp_path: Path) -> None:
    fake_player = _FakePlayerService()
    service = _make_service_with_fakes(tmp_path, player_service=fake_player)
    result = service.player_activity("joins", "VonCrush", "all", "", 30, 1, 10)
    assert result is _SENTINEL
    assert fake_player.activity_calls == [("joins", "VonCrush", "all", "", 30, 1, 10)]


def test_player_rankings_delegates(tmp_path: Path) -> None:
    fake_player = _FakePlayerService()
    service = _make_service_with_fakes(tmp_path, player_service=fake_player)
    result = service.player_rankings(limit=5)
    assert result is _SENTINEL
    assert fake_player.rankings_calls == [5]


def test_block_analytics_delegates(tmp_path: Path) -> None:
    fake_player = _FakePlayerService()
    service = _make_service_with_fakes(tmp_path, player_service=fake_player)
    result = service.block_analytics(limit=5)
    assert result is _SENTINEL
    assert fake_player.blocks_calls == [5]


def test_combat_analytics_delegates(tmp_path: Path) -> None:
    fake_player = _FakePlayerService()
    service = _make_service_with_fakes(tmp_path, player_service=fake_player)
    result = service.combat_analytics(limit=5)
    assert result is _SENTINEL
    assert fake_player.combat_calls == [5]


def test_exploration_analytics_delegates(tmp_path: Path) -> None:
    fake_player = _FakePlayerService()
    service = _make_service_with_fakes(tmp_path, player_service=fake_player)
    result = service.exploration_analytics(limit=5)
    assert result is _SENTINEL
    assert fake_player.exploration_calls == [5]


def test_period_analytics_delegates(tmp_path: Path) -> None:
    fake_player = _FakePlayerService()
    service = _make_service_with_fakes(tmp_path, player_service=fake_player)
    result = service.period_analytics(days=7, limit=5)
    assert result is _SENTINEL
    assert fake_player.periods_calls == [(7, 5)]


# ---------------------------------------------------------------------------
# save_settings routes through operation_service (issue #190)
# ---------------------------------------------------------------------------

def _make_service_with_operation_service(tmp_path: Path) -> "ManagerService":
    """Build a ManagerService wired with a real ServerOperationService.

    ``operation_service`` is passed to the constructor so that the composition
    follows the constructor-injection guideline.  The DB is initialised by
    ``make_manager_service``; ``SQLiteOperationRepository`` uses the same path
    and the schema is idempotent.
    """
    from conftest import make_manager_service
    from minecraft_manager.operations.repository import SQLiteOperationRepository
    from minecraft_manager.operations.service import ServerOperationService
    from minecraft_manager.repository import StateRepository

    class InlineThread:
        def __init__(self, *, target, args, **_kwargs) -> None:
            self._target = target
            self._args = args

        def start(self) -> None:
            self._target(*self._args)

    from unittest.mock import MagicMock

    docker_mock = MagicMock()
    docker_mock.status.return_value = {"state": "running", "online": True}
    docker_mock.execute.return_value = None

    # Initialise the DB first so the operation repository can share the schema.
    db_path = tmp_path / "state.db"
    StateRepository(db_path).initialize()

    configuration = MagicMock()
    configuration.read_properties.return_value = {"server-name": "NewName"}

    op_service = ServerOperationService(
        operation_repository=SQLiteOperationRepository(db_path),
        docker=docker_mock,
        broker=MagicMock(),
        configuration=configuration,
        thread_factory=InlineThread,
        server_id="default",
        health_timeout=1,
    )
    return make_manager_service(tmp_path, docker=docker_mock, operation_service=op_service)  # type: ignore[arg-type]


def test_save_settings_routes_through_operation_service_and_returns_operation_id(tmp_path: Path) -> None:
    service = _make_service_with_operation_service(tmp_path)
    (tmp_path / ".env").write_text("SERVER_NAME=old\n")
    changed, operation_id = service.save_settings({"SERVER_NAME": "NewName"})
    assert changed == ["SERVER_NAME"]
    assert operation_id is not None
    assert len(operation_id) > 8  # uuid-shaped


def test_save_settings_raises_conflicting_operation_on_concurrent_request(tmp_path: Path) -> None:
    from minecraft_manager.operations.service import ConflictingOperationError
    from minecraft_manager.operations.lifecycle import ServerOperation
    from minecraft_manager.operations.repository import SQLiteOperationRepository
    service = _make_service_with_operation_service(tmp_path)
    # Persist a non-terminal (PENDING) operation in the real repository so that
    # get_active returns it and save_settings raises ConflictingOperationError.
    db_path = tmp_path / "state.db"
    repo = SQLiteOperationRepository(db_path)
    blocking_op = ServerOperation.create("default", {"SERVER_NAME": "Blocker"})
    repo.save(blocking_op)
    with pytest.raises(ConflictingOperationError):
        service.save_settings({"SERVER_NAME": "Conflict"})


# ---------------------------------------------------------------------------
# Batch and snapshot diagnostics — issue #276
# ---------------------------------------------------------------------------

def _blocks_changed(sequence: int, broken_total: int = 0, placed_total: int = 0) -> dict:
    return {
        "schema": 1, "sequence": sequence, "type": "blocks.changed", "timestamp": sequence,
        "player": {"name": "VonCrush"},
        "data": {
            "broken": {"total": broken_total, "byType": {}},
            "placed": {"total": placed_total, "byType": {}},
        },
    }


def _snapshot_started(sequence: int) -> dict:
    return {
        "schema": 1, "sequence": sequence, "type": "snapshot.started",
        "timestamp": sequence, "player": None, "data": {},
    }


def _snapshot_finished(sequence: int, players: list | None = None) -> dict:
    data: dict = {}
    if players is not None:
        data["players"] = players
    return {
        "schema": 1, "sequence": sequence, "type": "snapshot.finished",
        "timestamp": sequence, "player": None, "data": data,
    }


def test_batch_diagnostics_start_empty(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    blocks = service.diagnostics()["telemetry"]["blocks"]
    assert blocks == {"count": 0, "total_blocks_declared": 0, "max_blocks_declared": 0}


def test_batch_diagnostics_single_batch(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_blocks_changed(10, broken_total=3, placed_total=2))
    blocks = service.diagnostics()["telemetry"]["blocks"]
    assert blocks["count"] == 1
    assert blocks["total_blocks_declared"] == 5
    assert blocks["max_blocks_declared"] == 5


def test_batch_diagnostics_multiple_batches(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_blocks_changed(10, broken_total=2, placed_total=1))   # 3
    service.telemetry_event(_blocks_changed(11, broken_total=5, placed_total=2))   # 7
    service.telemetry_event(_blocks_changed(12, broken_total=1, placed_total=1))   # 2
    blocks = service.diagnostics()["telemetry"]["blocks"]
    assert blocks["count"] == 3
    assert blocks["total_blocks_declared"] == 12
    assert blocks["max_blocks_declared"] == 7


def test_batch_diagnostics_missing_total(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    envelope = {
        "schema": 1, "sequence": 10, "type": "blocks.changed", "timestamp": 10,
        "player": {"name": "VonCrush"}, "data": {},
    }
    service.telemetry_event(envelope)
    blocks = service.diagnostics()["telemetry"]["blocks"]
    assert blocks["count"] == 1
    assert blocks["total_blocks_declared"] == 0
    assert blocks["max_blocks_declared"] == 0


def test_batch_rejected_does_not_count(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_blocks_changed(10, broken_total=3, placed_total=2))
    # duplicate — should be rejected
    service.telemetry_event(_blocks_changed(10, broken_total=3, placed_total=2))
    blocks = service.diagnostics()["telemetry"]["blocks"]
    assert blocks["count"] == 1


def test_snapshot_diagnostics_empty(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    snapshots = service.diagnostics()["telemetry"]["snapshots"]
    assert snapshots["count"] == 0
    assert snapshots["duration_ms_total"] == 0
    assert snapshots["duration_ms_max"] == 0
    assert snapshots["last_player_count"] is None


def test_snapshot_diagnostics_complete(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_snapshot_started(1))
    service.telemetry_event(_snapshot_finished(2))
    snapshots = service.diagnostics()["telemetry"]["snapshots"]
    assert snapshots["count"] == 1
    assert snapshots["duration_ms_total"] >= 0
    assert snapshots["duration_ms_max"] >= 0


def test_snapshot_diagnostics_multiple(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_snapshot_started(1))
    service.telemetry_event(_snapshot_finished(2))
    service.telemetry_event(_snapshot_started(3))
    service.telemetry_event(_snapshot_finished(4))
    snapshots = service.diagnostics()["telemetry"]["snapshots"]
    assert snapshots["count"] == 2
    assert snapshots["duration_ms_total"] >= snapshots["duration_ms_max"]


def test_snapshot_last_player_count(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_snapshot_started(1))
    service.telemetry_event(_snapshot_finished(2, players=["p1", "p2"]))
    assert service.diagnostics()["telemetry"]["snapshots"]["last_player_count"] == 2


def test_snapshot_no_players_field(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_snapshot_started(1))
    service.telemetry_event(_snapshot_finished(2))
    assert service.diagnostics()["telemetry"]["snapshots"]["last_player_count"] is None


def test_snapshot_started_without_finished(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_snapshot_started(1))
    assert service.diagnostics()["telemetry"]["snapshots"]["count"] == 0


def test_mixed_ingest_no_cross_contamination(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.telemetry_event(_blocks_changed(10, broken_total=5, placed_total=0))
    service.telemetry_event(_snapshot_started(11))
    service.telemetry_event(_snapshot_finished(12, players=["VonCrush"]))
    blocks = service.diagnostics()["telemetry"]["blocks"]
    snapshots = service.diagnostics()["telemetry"]["snapshots"]
    assert blocks["count"] == 1
    assert blocks["total_blocks_declared"] == 5
    assert snapshots["count"] == 1
    assert snapshots["last_player_count"] == 1
