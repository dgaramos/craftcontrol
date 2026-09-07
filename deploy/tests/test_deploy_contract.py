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
    lines_with_backup = [line for line in script.splitlines() if "craftcontrol backup create" in line]
    assert all("exec" in line for line in lines_with_backup), (
        "craftcontrol backup create must only appear inside a 'compose exec' call"
    )


def test_backend_deploy_validates_the_shared_internal_tls_before_mutating() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol-backend").read_text()
    # The frontend verifies the backend certificate with the CA from the shared
    # volume. When that volume is recreated the running frontend keeps an empty
    # mount and every proxied request answers 502. The pairing must be checked
    # in the preflight, before the backend container is replaced.
    assert "validate_internal_tls" in script
    preflight = script.index("backend deploy preflight: ok")
    assert script.index("validate_internal_tls()") < preflight
    assert script.index("\nvalidate_internal_tls\n") < preflight


def test_backend_deploy_reports_a_broken_proxy_instead_of_a_bare_curl_error() -> None:
    script = (ROOT / "bin" / "deploy-craftcontrol-backend").read_text()
    # A 502 from the proxied health check used to surface as "curl: (22)" with
    # no indication of the cause.
    health_check = [line for line in script.splitlines() if "$frontend_port/api/health" in line]
    assert health_check, "the deploy must check /api/health through the frontend"
    assert "did not answer /api/health" in script


def test_split_runtime_gate_exercises_cli_inside_container() -> None:
    canary = (ROOT / "bin" / "check-split-runtime").read_text()
    assert "craftcontrol backup list" in canary
    assert "'backups' in d" in canary


def test_homelab_deploy_script_is_versioned_in_repository() -> None:
    script = ROOT / "deploy" / "craftcontrol-homelab-deploy.sh"
    assert script.is_file(), "deploy/craftcontrol-homelab-deploy.sh must be tracked in the repo"
    text = script.read_text()
    assert "deploy-craftcontrol-release --check" in text
    assert "deploy-craftcontrol-release" in text
    assert script.stat().st_mode & 0o111, "deploy script must be executable"
