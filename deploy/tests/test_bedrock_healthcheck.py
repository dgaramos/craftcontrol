"""Contract tests for the transport-aware Bedrock container healthcheck.

The script runs inside the itzg/minecraft-bedrock-server container, so the
tests exercise it with ``sh`` against temporary fixtures instead of Docker.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "bedrock" / "bedrock-healthcheck.sh"

# /proc/net/udp{,6} rows: local_address is hex host:port; 0x1D7F == 7551.
_PROC_HEADER = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode ref pointer drops\n"
_NETHERNET_ROW = " 3729: 00000000000000000000000000000000:1D7F 00000000000000000000000000000000:0000 07 00000000:00000000 00:00000000 00000000  1000        0 3622934 2 0000000098d3fbf4 0\n"
_OTHER_ROW = "   1: 00000000:0035 00000000:0000 07 00000000:00000000 00:00000000 00000000     0        0 1 2 0000000000000000 0\n"


def _fixture(tmp_path: Path, *, transport: str | None, port: str = "19132", udp6_rows: str = "", mc_monitor_exit: int = 0) -> dict[str, str]:
    props = tmp_path / "server.properties"
    lines = [f"server-port={port}\n", "# transport=commented-out\n"]
    if transport is not None:
        lines.append(f"transport={transport}\n")
    props.write_text("".join(lines))
    udp = tmp_path / "udp"
    udp6 = tmp_path / "udp6"
    udp.write_text(_PROC_HEADER + _OTHER_ROW)
    udp6.write_text(_PROC_HEADER + udp6_rows)
    monitor = tmp_path / "mc-monitor"
    monitor.write_text(f'#!/bin/sh\necho "$@" > "{tmp_path}/mc-monitor.args"\nexit {mc_monitor_exit}\n')
    monitor.chmod(monitor.stat().st_mode | stat.S_IXUSR)
    return {
        **os.environ,
        "BEDROCK_PROPERTIES": str(props),
        "BEDROCK_PROC_NET_UDP": str(udp),
        "BEDROCK_PROC_NET_UDP6": str(udp6),
        "MC_MONITOR": str(monitor),
    }


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=10, check=False)


def test_healthcheck_script_is_tracked_and_syntax_checked_by_the_deploy_gate() -> None:
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR
    gate = (ROOT / "bin" / "check-deploy").read_text()
    assert "sh -n deploy/bedrock/bedrock-healthcheck.sh" in gate


def test_raknet_transport_delegates_to_mc_monitor_on_the_configured_port(tmp_path: Path) -> None:
    env = _fixture(tmp_path, transport="raknet", port="19200")
    result = _run(env)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "mc-monitor.args").read_text().split() == [
        "status-bedrock", "--host", "127.0.0.1", "--port", "19200",
    ]


def test_missing_transport_defaults_to_raknet(tmp_path: Path) -> None:
    env = _fixture(tmp_path, transport=None)
    assert _run(env).returncode == 0
    assert "--port 19132" in (tmp_path / "mc-monitor.args").read_text()


def test_raknet_transport_reports_the_mc_monitor_failure(tmp_path: Path) -> None:
    env = _fixture(tmp_path, transport="raknet", mc_monitor_exit=1)
    assert _run(env).returncode == 1


def test_nethernet_transport_is_healthy_when_the_discovery_socket_is_bound(tmp_path: Path) -> None:
    env = _fixture(tmp_path, transport="nethernet", udp6_rows=_NETHERNET_ROW)
    result = _run(env)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "mc-monitor.args").exists(), "NetherNet must not use the RakNet ping"


def test_nethernet_transport_is_unhealthy_until_the_discovery_socket_is_bound(tmp_path: Path) -> None:
    env = _fixture(tmp_path, transport="NetherNet", udp6_rows="")
    result = _run(env)
    assert result.returncode == 1
    assert "7551" in result.stderr
    assert not (tmp_path / "mc-monitor.args").exists()


def test_unsupported_transport_is_never_healthy(tmp_path: Path) -> None:
    env = _fixture(tmp_path, transport="quic", udp6_rows=_NETHERNET_ROW)
    result = _run(env)
    assert result.returncode == 1
    assert "quic" in result.stderr


def test_missing_properties_file_is_unhealthy(tmp_path: Path) -> None:
    env = _fixture(tmp_path, transport="nethernet", udp6_rows=_NETHERNET_ROW)
    env["BEDROCK_PROPERTIES"] = str(tmp_path / "absent.properties")
    assert _run(env).returncode == 1


@pytest.mark.parametrize("shell", ["sh", "bash"])
def test_script_parses_under_posix_shells(shell: str) -> None:
    assert subprocess.run([shell, "-n", str(SCRIPT)], capture_output=True, check=False).returncode == 0
