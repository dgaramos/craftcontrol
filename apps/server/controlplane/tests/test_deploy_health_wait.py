"""Integration tests for the deploy scripts' shared health wait.

The wait is exercised through bash with a stub `docker` on PATH, so the
scenarios that matter in production — a container that flaps behind a restart
policy, one that dies, one that comes up healthy — are asserted without a
Docker daemon.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[4]
HELPER = ROOT / "bin" / "lib" / "wait-for-health.sh"
BASH = "/bin/bash"


def run_wait(tmp_path: Path, docker_stub: str) -> subprocess.CompletedProcess[str]:
    """Run the wait against a stub docker, returning the completed process."""
    stub = tmp_path / "docker"
    stub.write_text("#!/bin/bash\n" + docker_stub)
    stub.chmod(0o755)
    script = tmp_path / "wait.sh"
    script.write_text(
        "set -euo pipefail\n"
        'fail() { echo "refused: $*" >&2; exit 1; }\n'
        f'source "{HELPER}"\n'
        # Three attempts keep the failing cases fast; the sleep is neutralised.
        "sleep() { :; }\n"
        'wait_for_container_health craftcontrol-backend "backend" 3\n'
        'echo "healthy"\n'
    )
    return subprocess.run(
        [BASH, str(script)],
        env={"PATH": f"{tmp_path}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
    )


HEALTHY_STUB = """
case "$*" in
  *RestartCount*) echo 0 ;;
  *State.Status*) echo running ;;
  *Health.Status*) echo healthy ;;
  logs) ;;
esac
"""

# The container crashes and its restart policy puts it straight back: the
# status is "running" again and the health check starts over, so only the
# restart counter distinguishes this from a slow but healthy start.
FLAPPING_STUB = """
count_file="$HOME/restarts"
case "$*" in
  *RestartCount*)
    previous="$(cat "$count_file" 2>/dev/null || echo 0)"
    echo $((previous + 1)) > "$count_file"
    echo "$previous"
    ;;
  *State.Status*) echo running ;;
  *Health.Status*) echo healthy ;;
  *) echo "container log line" ;;
esac
"""

DEAD_STUB = """
case "$*" in
  *RestartCount*) echo 0 ;;
  *State.Status*) echo exited ;;
  *Health.Status*) echo unhealthy ;;
  *) echo "container log line" ;;
esac
"""

STARTING_STUB = """
case "$*" in
  *RestartCount*) echo 0 ;;
  *State.Status*) echo running ;;
  *Health.Status*) echo starting ;;
  *) echo "container log line" ;;
esac
"""


def test_wait_accepts_a_container_that_reports_healthy(tmp_path: Path) -> None:
    result = run_wait(tmp_path, HEALTHY_STUB)
    assert result.returncode == 0, result.stderr
    assert "healthy" in result.stdout


def test_wait_refuses_a_container_that_restarted_during_the_wait(tmp_path: Path) -> None:
    """A flapping container must never be accepted, however healthy it then looks."""
    result = run_wait(tmp_path, FLAPPING_STUB)
    assert result.returncode == 1
    assert "backend restarted while starting" in result.stderr
    # The failure must carry the container logs; an opaque refusal is what
    # made the original deploy failure undiagnosable.
    assert "container log line" in result.stderr


def test_wait_refuses_a_container_that_left_the_running_state(tmp_path: Path) -> None:
    result = run_wait(tmp_path, DEAD_STUB)
    assert result.returncode == 1
    assert "backend stopped while starting (state=exited)" in result.stderr
    assert "container log line" in result.stderr


def test_wait_refuses_a_container_that_never_becomes_healthy(tmp_path: Path) -> None:
    result = run_wait(tmp_path, STARTING_STUB)
    assert result.returncode == 1
    assert "backend did not become healthy" in result.stderr
    assert "container log line" in result.stderr


@pytest.mark.parametrize(
    "script", ["deploy-craftcontrol", "deploy-craftcontrol-backend", "deploy-craftcontrol-frontend"]
)
def test_deploy_scripts_use_the_shared_wait(script: str) -> None:
    text = (ROOT / "bin" / script).read_text()
    assert "wait_for_container_health " in text
    assert 'source "$(dirname "${BASH_SOURCE[0]}")/lib/wait-for-health.sh"' in text
