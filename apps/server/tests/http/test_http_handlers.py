"""Handler-level tests for the HTTP blueprints (server, players, analytics, core, telemetry)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from controlplane.http.analytics import analytics_api
from controlplane.http.core import core_api
from controlplane.http.players import players_api
from controlplane.http.server import server_api
from controlplane.http.telemetry import telemetry_api
from conftest import make_auth_mock, wire_auth


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_app(manager: MagicMock, *, auth_mode: str = "disabled") -> Flask:
    app = Flask(__name__, template_folder="../../client/templates")
    app.extensions["manager_service"] = manager
    auth = make_auth_mock()
    wire_auth(app, auth, mode=auth_mode)
    app.register_blueprint(core_api)
    app.register_blueprint(server_api)
    app.register_blueprint(players_api)
    app.register_blueprint(analytics_api)
    app.register_blueprint(telemetry_api)
    return app


def assert_capability_required(
    service: MagicMock,
    method: str,
    path: str,
    capability: str,
    **request_kwargs,
) -> None:
    """Assert a route requires authentication (401) and the given capability (403).

    Constructs a local-auth app, verifies an unauthenticated request returns 401,
    then verifies a request whose ``require_capability`` raises ``PermissionError``
    returns 403.
    """
    app = _make_app(service, auth_mode="local")
    auth = app.extensions["auth_service"]
    client = app.test_client()

    auth.authenticate.return_value = None
    assert getattr(client, method.lower())(path, **request_kwargs).status_code == 401

    auth.authenticate.return_value = {"id": "viewer", "role": "viewer", "capabilities": []}
    auth.require_capability.side_effect = PermissionError(capability)
    assert getattr(client, method.lower())(path, **request_kwargs).status_code == 403


@pytest.fixture
def service() -> MagicMock:
    svc = MagicMock()
    svc.public_state.return_value = {"online": []}
    svc.state.return_value = {"settings": {"difficulty": "normal"}, "telemetry": {}, "domains": {}}
    svc.players.return_value = []
    svc.player_profile.return_value = None
    svc.player_activity.return_value = {"events": [], "summary": {}, "page": 1, "pages": 1}
    svc.player_rankings.return_value = {}
    svc.block_analytics.return_value = {}
    svc.combat_analytics.return_value = {}
    svc.exploration_analytics.return_value = {}
    svc.period_analytics.return_value = {}
    svc.docker.status.return_value = {"running": False}
    return svc


@pytest.fixture
def client(service: MagicMock):
    return _make_app(service).test_client()


# ---------------------------------------------------------------------------
# core_api
# ---------------------------------------------------------------------------

def test_health_returns_ok(client) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_diagnostics_returns_manager_data(client, service: MagicMock) -> None:
    service.diagnostics.return_value = {"telemetry": {"accepted": 1}, "broker": {}}
    resp = client.get("/api/diagnostics")
    assert resp.status_code == 200
    assert resp.get_json()["telemetry"]["accepted"] == 1
    service.diagnostics.assert_called_once()


def test_diagnostics_requires_telemetry_manage_capability(service: MagicMock) -> None:
    assert_capability_required(service, "get", "/api/diagnostics", "telemetry.manage")

    app = _make_app(service, auth_mode="local")
    auth = app.extensions["auth_service"]
    client = app.test_client()
    auth.authenticate.return_value = {"id": "1", "role": "owner", "capabilities": ["*"]}
    service.diagnostics.return_value = {"telemetry": {}, "broker": {}, "runtime_refreshing": False}
    assert client.get("/api/diagnostics").status_code == 200


def test_state_returns_public_state(client, service: MagicMock) -> None:
    resp = client.get("/api/state")
    assert resp.status_code == 200
    service.public_state.assert_called_once()


def test_schema_returns_settings_and_gamerules(client) -> None:
    resp = client.get("/api/schema")
    data = resp.get_json()
    assert "settings" in data
    assert "gamerules" in data


def test_config_returns_current_settings(client, service: MagicMock) -> None:
    resp = client.get("/api/config")
    assert resp.status_code == 200
    service.state.assert_called()


def test_config_refreshes_when_settings_empty(client, service: MagicMock) -> None:
    service.state.side_effect = [
        {"settings": None, "telemetry": {}, "domains": {}},
        {"settings": {"difficulty": "hard"}, "telemetry": {}, "domains": {}},
    ]
    resp = client.get("/api/config")
    assert resp.status_code == 200
    service.refresh.assert_called_once()


def test_refresh_returns_202(client, service: MagicMock) -> None:
    resp = client.post("/api/refresh")
    assert resp.status_code == 202
    assert resp.get_json()["ok"] is True
    service.refresh_async.assert_called_once_with(reason="manual")


def test_refresh_requires_server_configure_capability(service: MagicMock) -> None:
    assert_capability_required(service, "post", "/api/refresh", "server.configure")
    service.refresh_async.assert_not_called()


def test_events_returns_event_stream(client) -> None:
    service_mock = client.application.extensions["manager_service"]
    service_mock.broker.stream.return_value = iter([None])
    resp = client.get("/api/events")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.content_type


# ---------------------------------------------------------------------------
# server_api
# ---------------------------------------------------------------------------

def test_status_returns_docker_status(client, service: MagicMock) -> None:
    resp = client.get("/api/status")
    assert resp.status_code == 200
    service.docker.status.assert_called_once()


def test_update_config_saves_and_returns_ok(client, service: MagicMock) -> None:
    service.save_settings.return_value = (["difficulty"], None)
    resp = client.put("/api/config", json={"difficulty": "hard"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["restart_required"] is True
    assert "operation_id" not in data


def test_update_config_includes_operation_id_when_operation_service_is_active(client, service: MagicMock) -> None:
    service.save_settings.return_value = (["difficulty"], "op-abc123")
    resp = client.put("/api/config", json={"difficulty": "hard"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["operation_id"] == "op-abc123"


def test_update_config_returns_409_on_conflicting_operation(client, service: MagicMock) -> None:
    from controlplane.operations import ConflictingOperationError
    service.save_settings.side_effect = ConflictingOperationError("op-xyz already active")
    resp = client.put("/api/config", json={"difficulty": "hard"})
    assert resp.status_code == 409
    assert "op-xyz already active" in resp.get_json()["error"]


def test_update_config_returns_400_on_value_error(client, service: MagicMock) -> None:
    service.save_settings.side_effect = ValueError("campo inválido")
    resp = client.put("/api/config", json={"difficulty": "invalid"})
    assert resp.status_code == 400
    assert "campo inválido" in resp.get_json()["error"]


def test_server_action_start_returns_ok(client, service: MagicMock) -> None:
    resp = client.post("/api/server/start")
    assert resp.status_code == 200
    assert resp.get_json()["action"] == "start"
    service.docker.execute.assert_called_with("start")


def test_server_action_unknown_returns_404(client) -> None:
    resp = client.post("/api/server/explode")
    assert resp.status_code == 404


def test_server_action_runtime_error_returns_500(client, service: MagicMock) -> None:
    service.docker.execute.side_effect = RuntimeError("Docker indisponível")
    resp = client.post("/api/server/stop")
    assert resp.status_code == 500
    assert "Docker indisponível" in resp.get_json()["error"]


def test_set_gamerule_returns_ok(client, service: MagicMock) -> None:
    service.set_gamerule.return_value = "true"
    resp = client.put("/api/gamerules/keepInventory", json={"value": "true"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["value"] == "true"


def test_set_gamerule_unknown_returns_404(client, service: MagicMock) -> None:
    service.set_gamerule.side_effect = KeyError("unknownRule")
    resp = client.put("/api/gamerules/unknownRule", json={"value": "true"})
    assert resp.status_code == 404


def test_set_gamerule_bad_value_returns_400(client, service: MagicMock) -> None:
    service.set_gamerule.side_effect = ValueError("valor inválido")
    resp = client.put("/api/gamerules/keepInventory", json={"value": "bad"})
    assert resp.status_code == 400


def test_world_action_returns_ok(client, service: MagicMock) -> None:
    resp = client.post("/api/world/save")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_world_action_unknown_returns_404(client, service: MagicMock) -> None:
    service.run_world_action.side_effect = KeyError("bogus")
    resp = client.post("/api/world/bogus")
    assert resp.status_code == 404


def test_time_action_returns_ok(client, service: MagicMock) -> None:
    service.time_action.return_value = {"value": 6000}
    resp = client.post("/api/time/query", json={"value": "day"})
    assert resp.status_code == 200
    assert resp.get_json()["value"] == 6000


def test_time_action_unknown_returns_404(client, service: MagicMock) -> None:
    service.time_action.side_effect = KeyError("bogus")
    resp = client.post("/api/time/bogus", json={})
    assert resp.status_code == 404


def test_time_action_value_error_returns_400(client, service: MagicMock) -> None:
    service.time_action.side_effect = ValueError("fora do intervalo")
    resp = client.post("/api/time/set", json={"value": 99999})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# players_api
# ---------------------------------------------------------------------------

def test_players_list_returns_players(client, service: MagicMock) -> None:
    service.players.return_value = [{"name": "VonCrush"}]
    resp = client.get("/api/players")
    assert resp.status_code == 200
    assert resp.get_json()["players"][0]["name"] == "VonCrush"


def test_player_profile_returns_profile(client, service: MagicMock) -> None:
    service.player_profile.return_value = {"name": "VonCrush", "id": "1"}
    resp = client.get("/api/players/profile/VonCrush")
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "VonCrush"


def test_player_profile_not_found_returns_404(client, service: MagicMock) -> None:
    service.player_profile.return_value = None
    resp = client.get("/api/players/profile/Unknown")
    assert resp.status_code == 404


def test_player_operator_enable_returns_ok(client, service: MagicMock) -> None:
    resp = client.put("/api/players/VonCrush/operator", json={"enabled": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["operator"] is True
    service.set_player_operator.assert_called_once_with("VonCrush", True)


def test_player_operator_invalid_value_returns_400(client) -> None:
    resp = client.put("/api/players/VonCrush/operator", json={"enabled": "yes"})
    assert resp.status_code == 400


def test_player_operator_service_error_returns_500(client, service: MagicMock) -> None:
    service.set_player_operator.side_effect = Exception("db error")
    resp = client.put("/api/players/VonCrush/operator", json={"enabled": False})
    assert resp.status_code == 500


def test_player_gamemode_set_returns_ok(client, service: MagicMock) -> None:
    service.set_player_game_mode.return_value = "survival"
    resp = client.put("/api/players/VonCrush/gamemode", json={"mode": "survival"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["player"] == "VonCrush"
    assert data["mode"] == "survival"
    assert data["preferred_game_mode"] == "survival"
    service.set_player_game_mode.assert_called_once_with("VonCrush", "survival")


def test_player_gamemode_missing_mode_returns_400(client) -> None:
    resp = client.put("/api/players/VonCrush/gamemode", json={})
    assert resp.status_code == 400


def test_player_gamemode_invalid_mode_returns_400(client, service: MagicMock) -> None:
    service.set_player_game_mode.side_effect = ValueError("modo de jogo inválido")
    resp = client.put("/api/players/VonCrush/gamemode", json={"mode": "spectator"})
    assert resp.status_code == 400


def test_player_gamemode_service_error_returns_500(client, service: MagicMock) -> None:
    service.set_player_game_mode.side_effect = Exception("console unavailable")
    resp = client.put("/api/players/VonCrush/gamemode", json={"mode": "creative"})
    assert resp.status_code == 500


def test_player_gamemode_requires_authentication(service: MagicMock) -> None:
    assert_capability_required(
        service, "put", "/api/players/VonCrush/gamemode", "players.manage",
        json={"mode": "survival"},
    )


def test_player_gamemode_offline_player_returns_409(client, service: MagicMock) -> None:
    service.set_player_game_mode.side_effect = LookupError("jogador não está online")
    resp = client.put("/api/players/VonCrush/gamemode", json={"mode": "survival"})
    assert resp.status_code == 409


def test_player_gamemode_malformed_json_returns_400(client) -> None:
    resp = client.put(
        "/api/players/VonCrush/gamemode",
        data=b'{"mode": ',
        content_type="application/json",
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# analytics_api
# ---------------------------------------------------------------------------

def test_activity_default_params_returns_200(client, service: MagicMock) -> None:
    resp = client.get("/api/analytics/activity")
    assert resp.status_code == 200
    service.player_activity.assert_called_once_with("all", "", "all", "", 0, 1, 25)


def test_activity_custom_params_forwarded(client, service: MagicMock) -> None:
    client.get("/api/analytics/activity?kind=player&player=VonCrush&page=2&page_size=10")
    service.player_activity.assert_called_once_with("player", "VonCrush", "all", "", 0, 2, 10)


def test_activity_bad_param_returns_400(client, service: MagicMock) -> None:
    service.player_activity.side_effect = ValueError("inválido")
    resp = client.get("/api/analytics/activity?days=bad")
    assert resp.status_code == 400


def test_rankings_returns_200(client, service: MagicMock) -> None:
    resp = client.get("/api/analytics/rankings")
    assert resp.status_code == 200
    service.player_rankings.assert_called_once_with(10)


def test_blocks_returns_200(client, service: MagicMock) -> None:
    resp = client.get("/api/analytics/blocks")
    assert resp.status_code == 200
    service.block_analytics.assert_called_once_with(10)


def test_combat_returns_200(client, service: MagicMock) -> None:
    resp = client.get("/api/analytics/combat")
    assert resp.status_code == 200
    service.combat_analytics.assert_called_once_with(10)


def test_exploration_returns_200(client, service: MagicMock) -> None:
    resp = client.get("/api/analytics/exploration")
    assert resp.status_code == 200
    service.exploration_analytics.assert_called_once_with(10)


def test_periods_returns_200(client, service: MagicMock) -> None:
    resp = client.get("/api/analytics/periods")
    assert resp.status_code == 200
    service.period_analytics.assert_called_once_with(30, 10)


def test_analytics_bad_limit_returns_400(client, service: MagicMock) -> None:
    service.player_rankings.side_effect = ValueError("inválido")
    resp = client.get("/api/analytics/rankings?limit=bad")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# telemetry_api
# ---------------------------------------------------------------------------

def test_telemetry_pack_status_returns_200(client, service: MagicMock) -> None:
    service.state.return_value = {
        "settings": {}, "telemetry": {}, "domains": {"telemetry": {}},
    }
    fake_installer = MagicMock()
    fake_installer.status.return_value.to_dict.return_value = {"installed": True, "world": "Bedrock level"}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.get("/api/telemetry-pack")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["installed"] is True


def test_telemetry_pack_status_error_returns_400(client, service: MagicMock) -> None:
    with patch("controlplane.http.telemetry.telemetry_installer", side_effect=FileNotFoundError("no pack")):
        resp = client.get("/api/telemetry-pack")
    assert resp.status_code == 400


def test_telemetry_pack_install_returns_result(client) -> None:
    fake_installer = MagicMock()
    fake_installer.install.return_value = {"changed": True}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/install")
    assert resp.status_code == 200
    assert resp.get_json()["changed"] is True


def test_telemetry_pack_upgrade_sets_action(client) -> None:
    fake_installer = MagicMock()
    fake_installer.install.return_value = {"changed": False}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/upgrade")
    assert resp.status_code == 200
    assert resp.get_json()["action"] == "upgrade"


def test_telemetry_pack_disable_returns_result(client) -> None:
    fake_installer = MagicMock()
    fake_installer.disable.return_value = {"changed": True, "action": "disable"}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/disable")
    assert resp.status_code == 200


def test_telemetry_pack_rollback_rejected_without_confirmation(client, service: MagicMock) -> None:
    fake_installer = MagicMock()
    service.docker.status.return_value = {"running": False}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/rollback")
    assert resp.status_code == 400
    assert "confirm" in resp.get_json()["error"].lower()


def test_telemetry_pack_rollback_rejected_when_server_running(client, service: MagicMock) -> None:
    fake_installer = MagicMock()
    service.docker.status.return_value = {"running": True}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/rollback?confirm=true")
    assert resp.status_code == 409
    assert "offline" in resp.get_json()["error"].lower()


def test_telemetry_pack_rollback_creates_recovery_copy_and_proceeds(client, service: MagicMock) -> None:
    fake_installer = MagicMock()
    fake_installer.latest_backup_name.return_value = "20240101T000000.000000Z"
    fake_installer.snapshot.return_value = "20240101T000001.000000Z"
    fake_installer.rollback.return_value = {"changed": True, "action": "rollback"}
    service.docker.status.return_value = {"running": False}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/rollback?confirm=true")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["changed"] is True
    assert data["recovery"] == "20240101T000001.000000Z"
    fake_installer.snapshot.assert_called_once()
    fake_installer.rollback.assert_called_once_with("20240101T000000.000000Z")


def test_telemetry_pack_rollback_rejected_with_non_dict_json_body(client, service: MagicMock) -> None:
    fake_installer = MagicMock()
    service.docker.status.return_value = {"running": False}
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post(
            "/api/telemetry-pack/rollback",
            data="true",
            content_type="application/json",
        )
    assert resp.status_code == 400
    assert "confirm" in resp.get_json()["error"].lower()


def test_telemetry_pack_unknown_action_returns_404(client) -> None:
    fake_installer = MagicMock()
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/explode")
    assert resp.status_code == 404


def test_telemetry_pack_action_file_not_found_returns_400(client) -> None:
    fake_installer = MagicMock()
    fake_installer.install.side_effect = FileNotFoundError("world not found")
    with patch("controlplane.http.telemetry.telemetry_installer", return_value=fake_installer):
        resp = client.post("/api/telemetry-pack/install")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# operations_api
# ---------------------------------------------------------------------------

def _make_operations_app(manager: MagicMock, *, auth_mode: str = "disabled") -> Flask:
    from controlplane.http.operations import operations_api as ops_bp
    app = Flask(__name__, template_folder="../../client/templates")
    app.extensions["manager_service"] = manager
    auth = make_auth_mock()
    wire_auth(app, auth, mode=auth_mode)
    app.register_blueprint(ops_bp)
    return app


@pytest.fixture
def op_service() -> MagicMock:
    svc = MagicMock()
    svc.operation_service = MagicMock()
    svc.broker = MagicMock()
    return svc


@pytest.fixture
def op_client(op_service: MagicMock):
    return _make_operations_app(op_service).test_client()


def test_get_latest_operation_returns_200_when_found(op_client, op_service: MagicMock) -> None:
    from controlplane.operations.lifecycle import ServerOperation
    op = ServerOperation.create("default", {"difficulty": "hard"})
    op_service.operation_service.get_latest.return_value = op
    resp = op_client.get("/api/operations/latest")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["operation"]["operation_id"] == op.operation_id


def test_get_latest_operation_returns_null_when_none(op_client, op_service: MagicMock) -> None:
    op_service.operation_service.get_latest.return_value = None
    resp = op_client.get("/api/operations/latest")
    assert resp.status_code == 200
    assert resp.get_json()["operation"] is None


def test_get_active_operation_returns_200_when_found(op_client, op_service: MagicMock) -> None:
    from controlplane.operations.lifecycle import ServerOperation
    op = ServerOperation.create("default", {"difficulty": "hard"})
    op_service.operation_service.get_active.return_value = op
    resp = op_client.get("/api/operations/active")
    assert resp.status_code == 200
    assert resp.get_json()["operation"]["operation_id"] == op.operation_id


def test_get_active_operation_returns_null_when_none(op_client, op_service: MagicMock) -> None:
    op_service.operation_service.get_active.return_value = None
    resp = op_client.get("/api/operations/active")
    assert resp.status_code == 200
    assert resp.get_json()["operation"] is None


def test_get_operation_by_id_returns_200_when_found(op_client, op_service: MagicMock) -> None:
    from controlplane.operations.lifecycle import ServerOperation
    op = ServerOperation.create("default", {"difficulty": "hard"})
    op_service.operation_service.get_operation.return_value = op
    resp = op_client.get(f"/api/operations/{op.operation_id}")
    assert resp.status_code == 200
    assert resp.get_json()["operation"]["operation_id"] == op.operation_id


def test_get_operation_by_id_returns_404_when_not_found(op_client, op_service: MagicMock) -> None:
    op_service.operation_service.get_operation.return_value = None
    resp = op_client.get("/api/operations/does-not-exist")
    assert resp.status_code == 404


def test_list_operations_returns_recent_list(op_client, op_service: MagicMock) -> None:
    from controlplane.operations.lifecycle import ServerOperation
    ops = [ServerOperation.create("default", {"difficulty": "hard"})]
    op_service.operation_service.list_recent.return_value = {
        "operations": ops, "page": 2, "page_size": 1, "total": 2, "pages": 2,
    }
    resp = op_client.get("/api/operations?page=2&limit=1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["operations"]) == 1
    assert data["page"] == 2
    assert data["page_size"] == 1
    assert data["total"] == 2
    assert data["pages"] == 2
    op_service.operation_service.list_recent.assert_called_once_with(page=2, limit=1)


@pytest.mark.parametrize("query", ("?page=0", "?page=nope", "?limit=0", "?limit=101"))
def test_list_operations_rejects_invalid_pagination(op_client, query: str) -> None:
    resp = op_client.get(f"/api/operations{query}")
    assert resp.status_code == 400


def test_stream_operations_returns_event_stream(op_client, op_service: MagicMock) -> None:
    op_service.broker.stream.return_value = iter([None])
    resp = op_client.get("/api/operations/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.content_type


def test_stream_operations_emits_keepalive_comment(op_client, op_service: MagicMock) -> None:
    op_service.broker.stream.return_value = iter([None])
    resp = op_client.get("/api/operations/stream")
    assert ": keepalive\n" in resp.data.decode()


def test_stream_operations_forwards_last_event_id(op_client, op_service: MagicMock) -> None:
    op_service.broker.stream.return_value = iter([None])
    op_client.get("/api/operations/stream", headers={"Last-Event-ID": "17"})
    op_service.broker.stream.assert_called_once_with(17)


def test_stream_operations_defaults_after_id_on_invalid_header(op_client, op_service: MagicMock) -> None:
    op_service.broker.stream.return_value = iter([None])
    op_client.get("/api/operations/stream", headers={"Last-Event-ID": "not-a-number"})
    op_service.broker.stream.assert_called_once_with(0)


def test_stream_operations_emits_operation_events(op_client, op_service: MagicMock) -> None:
    import json as _json
    from controlplane.operations.lifecycle import ServerOperation

    op = ServerOperation.create("default", {"difficulty": "hard"})

    class FakeEvent:
        id = 42
        topic = "operation.updated"
        payload = op.as_dict()

    op_service.broker.stream.return_value = iter([FakeEvent(), None])
    resp = op_client.get("/api/operations/stream")
    body = resp.data.decode()
    assert "event: operation\n" in body
    assert "id: 42\n" in body
    assert op.operation_id in body


def test_stream_operations_skips_non_operation_events(op_client, op_service: MagicMock) -> None:
    class FakeOtherEvent:
        id = 7
        topic = "server.state"
        payload = {"online": True}

    op_service.broker.stream.return_value = iter([FakeOtherEvent(), None])
    resp = op_client.get("/api/operations/stream")
    body = resp.data.decode()
    assert "event: operation\n" not in body
    assert ": skip\n" in body


def test_reconcile_operation_returns_200_when_found(op_client, op_service: MagicMock) -> None:
    from controlplane.operations.lifecycle import ServerOperation
    op = ServerOperation.create("default", {"difficulty": "hard"})
    op_service.operation_service.request_reconciliation.return_value = op
    resp = op_client.post(f"/api/operations/{op.operation_id}/reconcile")
    assert resp.status_code == 200
    assert resp.get_json()["operation"]["operation_id"] == op.operation_id


def test_reconcile_operation_returns_404_when_not_found(op_client, op_service: MagicMock) -> None:
    op_service.operation_service.request_reconciliation.return_value = None
    resp = op_client.post("/api/operations/ghost/reconcile")
    assert resp.status_code == 404
