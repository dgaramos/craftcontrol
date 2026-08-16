"""Tests for BedrockClient Docker-facing methods (send, query_state, etc.)."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from minecraft_manager.bedrock import BedrockClient


@pytest.fixture
def client() -> BedrockClient:
    return BedrockClient("bedrock", ["keepInventory", "pvp"], console_wait_seconds=0)


def _fake_docker(logs_output: bytes = b"") -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (docker_module, docker_client, container) mocks."""
    channel = MagicMock()
    channel._sock = MagicMock()
    container = MagicMock()
    container.attach_socket.return_value = channel
    container.logs.return_value = logs_output
    docker_client = MagicMock()
    docker_client.containers.get.return_value = container
    docker_module = MagicMock()
    docker_module.from_env.return_value = docker_client
    return docker_module, docker_client, container


# ---------------------------------------------------------------------------
# send
# ---------------------------------------------------------------------------

def test_send_dispatches_command_to_container(client: BedrockClient) -> None:
    docker_mod, _, container = _fake_docker()
    with patch.dict("sys.modules", {"docker": docker_mod}):
        client.send(["time", "set", "day"])
    container.attach_socket.assert_called_once()
    container.attach_socket.return_value._sock.sendall.assert_called_once_with(b"time set day\n")


def test_send_closes_client_on_success(client: BedrockClient) -> None:
    docker_mod, docker_client, _ = _fake_docker()
    with patch.dict("sys.modules", {"docker": docker_mod}):
        client.send(["list"])
    docker_client.close.assert_called_once()


def test_send_closes_client_on_exception(client: BedrockClient) -> None:
    docker_mod, docker_client, container = _fake_docker()
    container.attach_socket.side_effect = RuntimeError("socket error")
    with patch.dict("sys.modules", {"docker": docker_mod}):
        with pytest.raises(RuntimeError):
            client.send(["list"])
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# send_and_read
# ---------------------------------------------------------------------------

def test_send_and_read_returns_log_output(client: BedrockClient) -> None:
    docker_mod, _, _container = _fake_docker(b"The time is 6000\n")
    with patch.dict("sys.modules", {"docker": docker_mod}):
        result = client.send_and_read(["time", "query", "day"])
    assert "The time is 6000" in result


def test_send_and_read_closes_client_on_exception(client: BedrockClient) -> None:
    docker_mod, docker_client, container = _fake_docker()
    container.logs.side_effect = RuntimeError("no logs")
    with patch.dict("sys.modules", {"docker": docker_mod}):
        with pytest.raises(RuntimeError):
            client.send_and_read(["list"])
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# set_operator
# ---------------------------------------------------------------------------

def test_set_operator_sends_op_command(client: BedrockClient) -> None:
    docker_mod, _, container = _fake_docker()
    with patch.dict("sys.modules", {"docker": docker_mod}):
        client.set_operator("VonCrush", True)
    sent = container.attach_socket.return_value._sock.sendall.call_args[0][0]
    assert b'op "VonCrush"' in sent


def test_set_operator_sends_deop_command(client: BedrockClient) -> None:
    docker_mod, _, container = _fake_docker()
    with patch.dict("sys.modules", {"docker": docker_mod}):
        client.set_operator("VonCrush", False)
    sent = container.attach_socket.return_value._sock.sendall.call_args[0][0]
    assert b'deop "VonCrush"' in sent


def test_set_operator_closes_client_after_write(client: BedrockClient) -> None:
    docker_mod, docker_client, _ = _fake_docker()
    with patch.dict("sys.modules", {"docker": docker_mod}):
        client.set_operator("Nicole", True)
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# request_telemetry_snapshot
# ---------------------------------------------------------------------------

def test_request_telemetry_snapshot_sends_scriptevent(client: BedrockClient) -> None:
    docker_mod, _, container = _fake_docker(b"[Scripting] [BEDROCK_TELEMETRY] {}\n")
    with patch.dict("sys.modules", {"docker": docker_mod}):
        result = client.request_telemetry_snapshot()
    sent = container.attach_socket.return_value._sock.sendall.call_args[0][0]
    assert b"bedrock_telemetry:sync" in sent
    assert "[BEDROCK_TELEMETRY]" in result


def test_request_telemetry_snapshot_closes_client(client: BedrockClient) -> None:
    docker_mod, docker_client, _ = _fake_docker(b"")
    with patch.dict("sys.modules", {"docker": docker_mod}):
        client.request_telemetry_snapshot()
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# query_state
# ---------------------------------------------------------------------------

def test_query_state_returns_parsed_result(client: BedrockClient) -> None:
    logs = b"gamerule keepInventory = true\nThere are 1/10 players online:\nVonCrush\n"
    history = b"Player connected: VonCrush, xuid: 999\n"
    container = MagicMock()
    container.attach_socket.return_value._sock = MagicMock()
    container.logs.side_effect = [logs, history]
    docker_client = MagicMock()
    docker_client.containers.get.return_value = container
    docker_mod = MagicMock()
    docker_mod.from_env.return_value = docker_client

    with patch.dict("sys.modules", {"docker": docker_mod}):
        gamerules, players, online, maximum, xuids = client.query_state()

    assert gamerules.get("keepInventory") == "true"
    assert "VonCrush" in players
    assert online == 1
    assert maximum == 10
    assert xuids.get("VonCrush") == "999"
    docker_client.close.assert_called_once()


def test_query_state_closes_client_on_exception(client: BedrockClient) -> None:
    docker_mod, docker_client, container = _fake_docker()
    container.logs.side_effect = RuntimeError("lost connection")
    with patch.dict("sys.modules", {"docker": docker_mod}):
        with pytest.raises(RuntimeError):
            client.query_state()
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# query_gamerules
# ---------------------------------------------------------------------------

def test_query_gamerules_sends_rules_and_returns_values(client: BedrockClient) -> None:
    logs = b"gamerule pvp = false\n"
    docker_mod, docker_client, container = _fake_docker(logs)
    with patch.dict("sys.modules", {"docker": docker_mod}):
        result = client.query_gamerules({"pvp"})
    assert result.get("pvp") == "false"
    docker_client.close.assert_called_once()


def test_query_gamerules_closes_client_on_exception(client: BedrockClient) -> None:
    docker_mod, docker_client, container = _fake_docker()
    container.logs.side_effect = RuntimeError("no logs")
    with patch.dict("sys.modules", {"docker": docker_mod}):
        with pytest.raises(RuntimeError):
            client.query_gamerules({"pvp"})
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# _write
# ---------------------------------------------------------------------------

def test_write_uses_channel_directly_when_no_sock_attribute() -> None:
    channel = MagicMock(spec=["sendall", "close"])  # no _sock attribute
    container = MagicMock()
    container.attach_socket.return_value = channel
    BedrockClient._write(container, "list\n")
    channel.sendall.assert_called_once_with(b"list\n")
    channel.close.assert_called_once()
