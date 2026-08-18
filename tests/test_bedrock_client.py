"""Tests for BedrockClient Docker-facing methods (send, query_state, etc.)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from minecraft_manager.bedrock import BedrockClient


def _fake_docker(logs_output: bytes = b"") -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (docker_factory, docker_client, container) mocks."""
    channel = MagicMock()
    channel._sock = MagicMock()
    container = MagicMock()
    container.attach_socket.return_value = channel
    container.logs.return_value = logs_output
    docker_client = MagicMock()
    docker_client.containers.get.return_value = container
    docker_factory = MagicMock(return_value=docker_client)
    return docker_factory, docker_client, container


def _client(docker_factory: MagicMock) -> BedrockClient:
    return BedrockClient("bedrock", ["keepInventory", "pvp"], console_wait_seconds=0, docker_factory=docker_factory)


# ---------------------------------------------------------------------------
# send
# ---------------------------------------------------------------------------

def test_send_dispatches_command_to_container() -> None:
    factory, _, container = _fake_docker()
    _client(factory).send(["time", "set", "day"])
    container.attach_socket.assert_called_once()
    container.attach_socket.return_value._sock.sendall.assert_called_once_with(b"time set day\n")


def test_send_closes_client_on_success() -> None:
    factory, docker_client, _ = _fake_docker()
    _client(factory).send(["list"])
    docker_client.close.assert_called_once()


def test_send_closes_client_on_exception() -> None:
    factory, docker_client, container = _fake_docker()
    container.attach_socket.side_effect = RuntimeError("socket error")
    with pytest.raises(RuntimeError):
        _client(factory).send(["list"])
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# send_and_read
# ---------------------------------------------------------------------------

def test_send_and_read_returns_log_output() -> None:
    factory, _, _container = _fake_docker(b"The time is 6000\n")
    result = _client(factory).send_and_read(["time", "query", "day"])
    assert "The time is 6000" in result


def test_send_and_read_closes_client_on_exception() -> None:
    factory, docker_client, container = _fake_docker()
    container.logs.side_effect = RuntimeError("no logs")
    with pytest.raises(RuntimeError):
        _client(factory).send_and_read(["list"])
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# set_operator
# ---------------------------------------------------------------------------

def test_set_operator_sends_op_command() -> None:
    factory, _, container = _fake_docker()
    _client(factory).set_operator("VonCrush", True)
    sent = container.attach_socket.return_value._sock.sendall.call_args[0][0]
    assert b'op "VonCrush"' in sent


def test_set_operator_sends_deop_command() -> None:
    factory, _, container = _fake_docker()
    _client(factory).set_operator("VonCrush", False)
    sent = container.attach_socket.return_value._sock.sendall.call_args[0][0]
    assert b'deop "VonCrush"' in sent


def test_set_operator_closes_client_after_write() -> None:
    factory, docker_client, _ = _fake_docker()
    _client(factory).set_operator("Nicole", True)
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# request_telemetry_snapshot
# ---------------------------------------------------------------------------

def test_request_telemetry_snapshot_sends_scriptevent() -> None:
    factory, _, container = _fake_docker(b"[Scripting] [BEDROCK_TELEMETRY] {}\n")
    result = _client(factory).request_telemetry_snapshot()
    sent = container.attach_socket.return_value._sock.sendall.call_args[0][0]
    assert b"bedrock_telemetry:sync" in sent
    assert "[BEDROCK_TELEMETRY]" in result


def test_request_telemetry_snapshot_closes_client() -> None:
    factory, docker_client, _ = _fake_docker(b"")
    _client(factory).request_telemetry_snapshot()
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# query_state
# ---------------------------------------------------------------------------

def test_query_state_returns_parsed_result() -> None:
    logs = b"gamerule keepInventory = true\nThere are 1/10 players online:\nVonCrush\n"
    history = b"Player connected: VonCrush, xuid: 999\n"
    container = MagicMock()
    container.attach_socket.return_value._sock = MagicMock()
    container.logs.side_effect = [logs, history]
    docker_client = MagicMock()
    docker_client.containers.get.return_value = container
    factory = MagicMock(return_value=docker_client)

    gamerules, players, online, maximum, xuids = _client(factory).query_state()

    assert gamerules.get("keepInventory") == "true"
    assert "VonCrush" in players
    assert online == 1
    assert maximum == 10
    assert xuids.get("VonCrush") == "999"
    docker_client.close.assert_called_once()


def test_query_state_closes_client_on_exception() -> None:
    factory, docker_client, container = _fake_docker()
    container.logs.side_effect = RuntimeError("lost connection")
    with pytest.raises(RuntimeError):
        _client(factory).query_state()
    docker_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# query_gamerules
# ---------------------------------------------------------------------------

def test_query_gamerules_sends_rules_and_returns_values() -> None:
    factory, docker_client, _container = _fake_docker(b"gamerule pvp = false\n")
    result = _client(factory).query_gamerules({"pvp"})
    assert result.get("pvp") == "false"
    docker_client.close.assert_called_once()


def test_query_gamerules_closes_client_on_exception() -> None:
    factory, docker_client, container = _fake_docker()
    container.logs.side_effect = RuntimeError("no logs")
    with pytest.raises(RuntimeError):
        _client(factory).query_gamerules({"pvp"})
    docker_client.close.assert_called_once()


def test_query_gamerules_does_not_validate_names_in_adapter() -> None:
    # Validation was moved to ReconciliationService; the adapter must not raise
    # ValueError for unknown names — it just passes them through to Docker.
    factory, docker_client, _container = _fake_docker(b"")
    result = _client(factory).query_gamerules({"notarule"})
    assert isinstance(result, dict)
    factory.assert_called_once()
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
