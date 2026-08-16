import json
import threading
import time
from pathlib import Path

import pytest

from minecraft_manager.files import ServerFiles
from minecraft_manager.repository import StateRepository
from minecraft_manager.services import ManagerService
from tests.fakes import FakeBedrock, FakeDocker, FakeRuntime


def _make_service(directory: Path, bedrock: FakeBedrock | None = None, docker: FakeDocker | None = None) -> ManagerService:
    repo = StateRepository(directory / "state.db")
    repo.initialize()
    return ManagerService(
        repo,
        ServerFiles(directory / ".env", directory / "server.properties"),
        bedrock or FakeBedrock(),  # type: ignore[arg-type]
        docker or FakeDocker(),  # type: ignore[arg-type]
    )


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
    service.telemetry_event({"schema": 1, "sequence": 10, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:stone"}})
    service.telemetry_event({"schema": 1, "sequence": 13, "type": "block.broken", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:dirt"}})
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "degraded"
    assert telemetry["gap_count"] == "1"
    assert telemetry["missing_events"] == "2"
    assert telemetry["last_gap"] == "11-12"
    assert requested == ["sequence-gap"]


def test_snapshot_repairs_degraded_state_and_stale_delta_is_rejected(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
    service.telemetry_event({"schema": 1, "sequence": 10, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 12, "type": "block.broken", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 11, "type": "block.placed", "timestamp": 3, "player": {"name": "VonCrush"}, "data": {}})
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
    service.telemetry_event({"schema": 1, "sequence": 20, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
    service.telemetry_event({"schema": 1, "sequence": 1, "type": "telemetry.started", "timestamp": 2, "player": None, "data": {"version": "0.2.0"}})
    telemetry = service.state()["telemetry"]
    assert telemetry["status"] == "syncing"
    assert telemetry["reset_count"] == "1"
    assert requested == ["pack-started"]


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


def test_refresh_max_players_falls_back_to_env(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    service = _make_service(tmp_path, bedrock)
    (tmp_path / ".env").write_text("MAX_PLAYERS=20\n")
    bedrock.query_state_result = ({}, [], 0, 0, {})
    service.refresh("test")
    assert service.state()["max_players"] == 20


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
    original = service.refresh

    def refresh_and_signal(reason: str = "manual") -> None:
        original(reason)
        refreshed.set()

    service.refresh = refresh_and_signal  # type: ignore[method-assign]
    service.initialize()
    assert refreshed.wait(timeout=10), "refresh did not run"


def test_initialize_starts_runtime_when_attached(tmp_path: Path) -> None:
    refreshed = threading.Event()
    service = _make_service(tmp_path)
    original = service.refresh

    def refresh_and_signal(reason: str = "manual") -> None:
        original(reason)
        refreshed.set()

    service.refresh = refresh_and_signal  # type: ignore[method-assign]
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

def test_save_known_setting_persists_and_returns_keys(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    changed = service.save_settings({"SERVER_NAME": "TestServer"})
    assert changed == ["SERVER_NAME"]
    _, env_values = ServerFiles(tmp_path / ".env", tmp_path / "server.properties").read_env()
    assert env_values.get("SERVER_NAME") == "TestServer"


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
    original_snapshot = service.request_telemetry_snapshot

    def counted_snapshot(reason: str) -> int:
        nonlocal call_count
        call_count += 1
        first_started.set()
        return original_snapshot(reason)

    service.request_telemetry_snapshot = counted_snapshot  # type: ignore[method-assign]

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

def test_players_returns_list(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    assert isinstance(service.players(), list)


def test_player_profile_returns_none_for_unknown(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    assert service.player_profile("__nobody__") is None


def test_close_online_sessions_returns_list(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.player_event("Bob", True, "999")
    closed = service.close_online_sessions("server-stop")
    assert "Bob" in closed
