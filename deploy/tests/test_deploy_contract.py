"""Deploy contract tests.

These tests verify shell scripts, Dockerfiles, and CI workflows — not the
Python package. They live in deploy/tests/ to reflect that ownership.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backend_cli_module_path_matches_dockerfile_copy_destination() -> None:
    dockerfile = (ROOT / "apps" / "server" / "controlplane" / "Dockerfile").read_text()
    entrypoint = (ROOT / "bin" / "craftcontrol").read_text()
    # COPY destination and python -m target in bin/craftcontrol must agree.
    # A mismatch produces ModuleNotFoundError at backup/restore time inside the container.
    assert "COPY apps/server/controlplane/src ./src" in dockerfile
    assert "python -m src.cli" in entrypoint


def test_backend_deploy_syncs_server_directory_not_stale_backend_alias() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol-backend").read_text()
    # rsync must copy apps/server/ so the Dockerfile and source reach DEPLOY_ROOT.
    # apps/backend/ does not exist in git and silently skips all app files.
    assert "apps/server" in script
    assert "apps/backend" not in script


def test_backend_deploy_backup_runs_inside_container_not_on_host() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol-backend").read_text()
    # Backup must run via compose exec so it uses the running container's own
    # craftcontrol binary. Calling the host-side binary fails when module paths differ.
    assert "compose exec -T craftcontrol-backend craftcontrol backup create" in script
    lines_with_backup = [l for l in script.splitlines() if "craftcontrol backup create" in l]
    assert all("exec" in l for l in lines_with_backup), (
        "craftcontrol backup create must only appear inside a 'compose exec' call"
    )


def test_split_runtime_gate_exercises_cli_inside_container() -> None:
    canary = (ROOT / "bin" / "check-split-runtime").read_text()
    assert "craftcontrol backup list" in canary
    assert "'backups' in d" in canary
