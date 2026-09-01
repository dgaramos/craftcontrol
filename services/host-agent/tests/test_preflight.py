"""Tests for the preflight/prerequisite installer module.

All infrastructure dependencies are injected; no stdlib patching.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(_AGENT_DIR) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(_AGENT_DIR))

import pytest

from preflight import (
    Preflight,
    PreflightResult,
    SystemInfo,
    FakeRunner,
    FakeFilesystem,
    _DROPIN_TEMPLATE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DEFAULT_PROJECT_ROOT = "/opt/craftcontrol"
_DEFAULT_BEDROCK_DATA = "/opt/minecraft-bedrock"
_DEFAULT_AGENT_USER = "craftcontrol-agent"
_DEFAULT_AGENT_STATE_DIR = "/var/lib/craftcontrol/host-agent"
_DEFAULT_DOCKER_CONFIG = f"{_DEFAULT_AGENT_STATE_DIR}/docker"

_CORRECT_DROPIN = _DROPIN_TEMPLATE.format(
    bedrock_data=_DEFAULT_BEDROCK_DATA,
    agent_state_dir=_DEFAULT_AGENT_STATE_DIR,
    project_root=_DEFAULT_PROJECT_ROOT,
    docker_config=_DEFAULT_DOCKER_CONFIG,
)


def _ok_system() -> SystemInfo:
    """Return a SystemInfo that satisfies all phase-1 checks."""
    return SystemInfo(
        python_version=(3, 10, 0),
        docker_available=True,
        compose_v2=True,
        setfacl_available=True,
        agent_user_exists=True,
        agent_in_docker_group=True,
    )


def _make_preflight(
    *,
    project_root: str = "/opt/craftcontrol",
    bedrock_data: str = "/opt/minecraft-bedrock",
    agent_user: str = "craftcontrol-agent",
    compose_file: str = "/opt/craftcontrol/docker-compose.yml",
    compose_project: str = "minecraft-bedrock",
    system_info: SystemInfo | None = None,
    runner: FakeRunner | None = None,
    fs: FakeFilesystem | None = None,
    dry_run: bool = False,
) -> Preflight:
    return Preflight(
        project_root=project_root,
        bedrock_data=bedrock_data,
        agent_user=agent_user,
        compose_file=compose_file,
        compose_project=compose_project,
        system_info=system_info or _ok_system(),
        runner=runner or FakeRunner(),
        fs=fs or FakeFilesystem(
            acls={
                project_root: f"u:{agent_user}:--x",
                f"{project_root}/.env": f"u:{agent_user}:r--",
                bedrock_data: f"u:{agent_user}:rwX",
                f"d:{bedrock_data}": f"d:u:{agent_user}:rwX",
            },
            dropin_content=_CORRECT_DROPIN,
            dropin_exists=True,
            sandbox_ok=True,
        ),
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_preflight_all_ok():
    """All checks pass; no mutations applied."""
    runner = FakeRunner()
    fs = FakeFilesystem(
        acls={
            "/opt/craftcontrol": "u:craftcontrol-agent:--x",
            "/opt/craftcontrol/.env": "u:craftcontrol-agent:r--",
            "/opt/minecraft-bedrock": "u:craftcontrol-agent:rwX",
            "d:/opt/minecraft-bedrock": "d:u:craftcontrol-agent:rwX",
        },
        dropin_content=_CORRECT_DROPIN,
        dropin_exists=True,
        sandbox_ok=True,
    )
    pf = _make_preflight(runner=runner, fs=fs)
    result = pf.run()

    assert result.success
    assert runner.calls == []  # no mutations needed
    assert not result.planned_actions


def test_preflight_applies_missing_acl():
    """ACL missing on data/; setfacl called with correct args."""
    runner = FakeRunner()
    fs = FakeFilesystem(
        acls={
            "/opt/craftcontrol": "u:craftcontrol-agent:--x",
            "/opt/craftcontrol/.env": "u:craftcontrol-agent:r--",
            # data dir ACL intentionally absent
        },
        dropin_content=_CORRECT_DROPIN,
        dropin_exists=True,
        sandbox_ok=True,
    )
    pf = _make_preflight(runner=runner, fs=fs)
    result = pf.run()

    assert result.success
    assert any(
        "setfacl" in " ".join(call) and "rwX" in " ".join(call)
        for call in runner.calls
    ), f"Expected setfacl rwX call; got {runner.calls}"


def test_preflight_creates_dropin():
    """Drop-in absent; filesystem records correct content."""
    runner = FakeRunner()
    fs = FakeFilesystem(
        acls={
            "/opt/craftcontrol": "u:craftcontrol-agent:--x",
            "/opt/craftcontrol/.env": "u:craftcontrol-agent:r--",
            "/opt/minecraft-bedrock": "u:craftcontrol-agent:rwX",
        },
        dropin_content=None,  # does not exist yet
        dropin_exists=False,
        sandbox_ok=True,
    )
    pf = _make_preflight(runner=runner, fs=fs)
    result = pf.run()

    assert result.success
    assert fs.written_dropin is not None
    assert "ReadWritePaths" in fs.written_dropin


def test_dry_run_no_mutations():
    """dry-run: runner never called; result reports planned actions."""
    runner = FakeRunner()
    fs = FakeFilesystem(
        acls={},  # everything missing → lots of work to do
        dropin_content=None,
        dropin_exists=False,
        sandbox_ok=True,
    )
    pf = _make_preflight(
        runner=runner,
        fs=fs,
        system_info=_ok_system(),
        dry_run=True,
    )
    result = pf.run()

    assert runner.calls == []
    assert result.planned_actions  # at least one action would be taken


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_preflight_fails_if_docker_missing():
    """Missing Docker exits 1 before any ACL work."""
    runner = FakeRunner()
    sysinfo = SystemInfo(
        python_version=(3, 10, 0),
        docker_available=False,
        compose_v2=True,
        setfacl_available=True,
        agent_user_exists=True,
        agent_in_docker_group=True,
    )
    pf = _make_preflight(runner=runner, system_info=sysinfo)
    result = pf.run()

    assert not result.success
    assert "docker" in result.error.lower()
    assert runner.calls == []


def test_preflight_fails_if_compose_v1():
    """Compose v1 detected; exits 1 with v2 message."""
    sysinfo = SystemInfo(
        python_version=(3, 10, 0),
        docker_available=True,
        compose_v2=False,
        setfacl_available=True,
        agent_user_exists=True,
        agent_in_docker_group=True,
    )
    pf = _make_preflight(system_info=sysinfo)
    result = pf.run()

    assert not result.success
    assert "compose" in result.error.lower() and "v2" in result.error.lower()


def test_preflight_fails_if_agent_user_missing():
    """Missing craftcontrol-agent user exits 1."""
    sysinfo = SystemInfo(
        python_version=(3, 10, 0),
        docker_available=True,
        compose_v2=True,
        setfacl_available=True,
        agent_user_exists=False,
        agent_in_docker_group=False,
    )
    pf = _make_preflight(system_info=sysinfo)
    result = pf.run()

    assert not result.success
    assert "user" in result.error.lower()


def test_preflight_fails_if_agent_not_in_docker_group():
    """Agent user not in docker group exits 1."""
    sysinfo = SystemInfo(
        python_version=(3, 10, 0),
        docker_available=True,
        compose_v2=True,
        setfacl_available=True,
        agent_user_exists=True,
        agent_in_docker_group=False,
    )
    pf = _make_preflight(system_info=sysinfo)
    result = pf.run()

    assert not result.success
    assert "docker" in result.error.lower()


def test_preflight_sandbox_validation_fails():
    """systemd-run fake returns failure; exits 1."""
    fs = FakeFilesystem(
        acls={
            "/opt/craftcontrol": "u:craftcontrol-agent:--x",
            "/opt/craftcontrol/.env": "u:craftcontrol-agent:r--",
            "/opt/minecraft-bedrock": "u:craftcontrol-agent:rwX",
        },
        dropin_content=_CORRECT_DROPIN,
        dropin_exists=True,
        sandbox_ok=False,  # systemd-run will "fail"
    )
    pf = _make_preflight(fs=fs)
    result = pf.run()

    assert not result.success
    assert "sandbox" in result.error.lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_preflight_env_acl_missing_after_recreate():
    """.env exists but its ACL is absent; ACL reapplied correctly."""
    runner = FakeRunner()
    fs = FakeFilesystem(
        acls={
            "/opt/craftcontrol": "u:craftcontrol-agent:--x",
            # .env ACL intentionally absent (file recreated atomically)
            "/opt/minecraft-bedrock": "u:craftcontrol-agent:rwX",
        },
        dropin_content=_CORRECT_DROPIN,
        dropin_exists=True,
        sandbox_ok=True,
    )
    pf = _make_preflight(runner=runner, fs=fs)
    result = pf.run()

    assert result.success
    assert any(
        "setfacl" in " ".join(call) and ".env" in " ".join(call)
        for call in runner.calls
    ), f"Expected setfacl on .env; got {runner.calls}"


def test_preflight_dropin_already_correct():
    """Drop-in exists with correct content; write not repeated."""
    runner = FakeRunner()
    fs = FakeFilesystem(
        acls={
            "/opt/craftcontrol": "u:craftcontrol-agent:--x",
            "/opt/craftcontrol/.env": "u:craftcontrol-agent:r--",
            "/opt/minecraft-bedrock": "u:craftcontrol-agent:rwX",
        },
        dropin_content=_CORRECT_DROPIN,
        dropin_exists=True,
        sandbox_ok=True,
    )
    pf = _make_preflight(runner=runner, fs=fs)
    result = pf.run()

    assert result.success
    assert fs.written_dropin is None  # no write occurred


def test_preflight_path_not_absolute():
    """Relative project_root path exits 1 without mutation."""
    runner = FakeRunner()
    pf = _make_preflight(project_root="relative/path", runner=runner)
    result = pf.run()

    assert not result.success
    assert "absolute" in result.error.lower()
    assert runner.calls == []


def test_dry_run_reports_failures():
    """dry-run with inconsistent state exits 1 listing missing actions."""
    sysinfo = SystemInfo(
        python_version=(3, 10, 0),
        docker_available=False,  # would block
        compose_v2=True,
        setfacl_available=True,
        agent_user_exists=True,
        agent_in_docker_group=True,
    )
    pf = _make_preflight(system_info=sysinfo, dry_run=True)
    result = pf.run()

    assert not result.success
    assert result.error  # error message present even in dry-run


# ---------------------------------------------------------------------------
# Regression guards
# ---------------------------------------------------------------------------


def test_preflight_never_restarts_bedrock():
    """No fake runner call contains a Bedrock restart command."""
    runner = FakeRunner()
    fs = FakeFilesystem(
        acls={},
        dropin_content=None,
        dropin_exists=False,
        sandbox_ok=True,
    )
    pf = _make_preflight(runner=runner, fs=fs)
    pf.run()

    for call in runner.calls:
        cmd = " ".join(str(c) for c in call)
        assert "restart" not in cmd, f"Unexpected restart command: {cmd}"


def test_preflight_never_writes_token_file():
    """Token file path is never opened for writing."""
    fs = FakeFilesystem(
        acls={
            "/opt/craftcontrol": "u:craftcontrol-agent:--x",
            "/opt/craftcontrol/.env": "u:craftcontrol-agent:r--",
            "/opt/minecraft-bedrock": "u:craftcontrol-agent:rwX",
        },
        dropin_content=_CORRECT_DROPIN,
        dropin_exists=True,
        sandbox_ok=True,
    )
    pf = _make_preflight(fs=fs)
    pf.run()

    token_path = "/etc/craftcontrol/host-agent-token"
    assert token_path not in fs.written_paths, (
        f"Token file was opened for writing: {token_path}"
    )
