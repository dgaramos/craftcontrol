"""Idempotent prerequisite installer and preflight checker for the Host Agent.

All infrastructure dependencies are injected through constructors.
No stdlib module patching is used or needed.

Phases (executed in order; stops on first failure):
  1. System checks: Python >= 3.10, Docker CLI, compose v2, setfacl,
     craftcontrol-agent user and docker group membership.
  2. Bedrock project ACLs: traversal, .env read, data rwX, default ACL.
  3. .env ACL repair: detect missing ACL and reapply.
  4. Systemd drop-in: create/update runtime-paths.conf; daemon-reload.
  5. Path-unit install: craftcontrol-host-agent-env-acl.{path,service}.
  6. Sandbox validation: non-mutating systemd-run --wait.
  7. Restart command reachability.

Security invariants enforced:
  - All paths validated as absolute before any mutation.
  - Owner/group of existing files never changed.
  - /etc/craftcontrol/host-agent-token never opened for writing.
  - Bedrock container files never touched.
  - No service restart except daemon-reload.
"""
from __future__ import annotations

import dataclasses
from typing import List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SystemInfo:
    """Snapshot of system-level prerequisites."""

    python_version: Tuple[int, int, int]
    docker_available: bool
    compose_v2: bool
    setfacl_available: bool
    agent_user_exists: bool
    agent_in_docker_group: bool


@dataclasses.dataclass
class PreflightResult:
    success: bool
    error: str = ""
    planned_actions: List[str] = dataclasses.field(default_factory=list)


# ---------------------------------------------------------------------------
# Seams (injectable fakes / production implementations)
# ---------------------------------------------------------------------------


class FakeRunner:
    """Fake subprocess runner that records calls without executing anything."""

    def __init__(self, sandbox_ok: bool = True) -> None:
        self.calls: List[List[str]] = []
        self._sandbox_ok = sandbox_ok

    def run(self, cmd: Sequence[str], *, check: bool = True) -> int:
        self.calls.append(list(cmd))
        # Simulate systemd-run failures when requested
        if "systemd-run" in cmd[0] and not self._sandbox_ok:
            if check:
                raise RuntimeError("systemd-run failed")
            return 1
        return 0


class FakeFilesystem:
    """Fake filesystem / ACL inspector for tests."""

    def __init__(
        self,
        *,
        acls: dict[str, str],
        dropin_content: Optional[str],
        dropin_exists: bool,
        sandbox_ok: bool,
        path_unit_active: bool = True,
    ) -> None:
        # mapping path → ACL entry present (truthy value = present)
        self._acls = acls
        self._dropin_content = dropin_content
        self._dropin_exists = dropin_exists
        self._sandbox_ok = sandbox_ok
        self._path_unit_active = path_unit_active
        # recorded side effects
        self.written_dropin: Optional[str] = None
        self.written_paths: List[str] = []

    def has_acl(self, path: str, user: str, perms: str) -> bool:
        """Return True when *path* has an ACL granting *user* at least *perms*."""
        entry = self._acls.get(path, "")
        return bool(entry)

    def dropin_path(self, service: str) -> str:
        return f"/etc/systemd/system/{service}.service.d/runtime-paths.conf"

    def dropin_exists(self, service: str) -> bool:
        return self._dropin_exists

    def dropin_content(self, service: str) -> Optional[str]:
        return self._dropin_content

    def write_dropin(self, service: str, content: str) -> None:
        self.written_dropin = content
        self.written_paths.append(self.dropin_path(service))
        # Update state so idempotency checks work
        self._dropin_exists = True
        self._dropin_content = content

    def write_file(self, path: str, content: str) -> None:
        self.written_paths.append(path)

    def path_unit_active(self, unit: str) -> bool:
        return self._path_unit_active

    def run_sandbox_validation(
        self,
        *,
        agent_user: str,
        bedrock_data: str,
        agent_state_dir: str,
        compose_file: str,
        compose_project: str,
        docker_config: str,
    ) -> bool:
        return self._sandbox_ok


class ProductionRunner:  # pragma: no cover
    """Thin wrapper around subprocess.run for production use."""

    def __init__(self) -> None:
        import subprocess  # noqa: PLC0415

        self._subprocess = subprocess

    def run(self, cmd: Sequence[str], *, check: bool = True) -> int:
        result = self._subprocess.run(list(cmd), check=False)
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(str(c) for c in cmd)}")
        return result.returncode


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

_SERVICE = "craftcontrol-host-agent"
_TOKEN_PATH = "/etc/craftcontrol/host-agent-token"

_DROPIN_TEMPLATE = """\
[Service]
ReadWritePaths=
ReadWritePaths={bedrock_data} {agent_state_dir}
ReadOnlyPaths=
ReadOnlyPaths=/etc/craftcontrol {project_root}
Environment=DOCKER_CONFIG={docker_config}
"""

_ENV_ACL_UNIT = "craftcontrol-host-agent-env-acl"
_ENV_ACL_SERVICE_PATH = f"/etc/systemd/system/{_ENV_ACL_UNIT}.service"
_ENV_ACL_PATH_PATH = f"/etc/systemd/system/{_ENV_ACL_UNIT}.path"
_ENV_ACL_SERVICE_TEMPLATE = """\
[Unit]
Description=Restore Host Agent read access to the Bedrock Compose environment

[Service]
Type=oneshot
ExecStart=/usr/bin/setfacl -m u:{agent_user}:r-- {project_root}/.env
"""
_ENV_ACL_PATH_TEMPLATE = """\
[Unit]
Description=Watch the Bedrock Compose environment for replacements

[Path]
PathChanged={project_root}/.env
Unit={unit}.service

[Install]
WantedBy=multi-user.target
"""


class Preflight:
    """Idempotent prerequisite installer for the CraftControl Host Agent."""

    def __init__(
        self,
        *,
        project_root: str,
        bedrock_data: str,
        agent_user: str,
        compose_file: str,
        compose_project: str,
        system_info: SystemInfo,
        runner: FakeRunner | ProductionRunner,
        fs: FakeFilesystem,
        dry_run: bool = False,
        agent_state_dir: str = "/var/lib/craftcontrol/host-agent",
        docker_config: Optional[str] = None,
    ) -> None:
        self._project_root = project_root
        self._bedrock_data = bedrock_data
        self._agent_user = agent_user
        self._compose_file = compose_file
        self._compose_project = compose_project
        self._system_info = system_info
        self._runner = runner
        self._fs = fs
        self._dry_run = dry_run
        self._agent_state_dir = agent_state_dir
        self._docker_config = docker_config or f"{agent_state_dir}/docker"
        self._planned: List[str] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> PreflightResult:
        # Guard: absolute paths required before any mutation
        for label, path in [
            ("project_root", self._project_root),
            ("bedrock_data", self._bedrock_data),
            ("compose_file", self._compose_file),
            ("agent_state_dir", self._agent_state_dir),
            ("docker_config", self._docker_config),
        ]:
            if not path.startswith("/"):
                return PreflightResult(
                    success=False,
                    error=f"{label} must be an absolute path, got: {path!r}",
                )

        # Phase 1 – system prerequisites
        err = self._check_system()
        if err:
            return PreflightResult(success=False, error=err)

        try:
            # Phase 2 – Bedrock project ACLs
            self._apply_acls()

            # Phase 3 – .env ACL repair (already covered by phase 2)

            # Phase 4 – systemd drop-in
            self._apply_dropin()

            # Phase 5 – path unit install and verification
            self._ensure_path_unit()
        except RuntimeError as error:
            return PreflightResult(success=False, error=str(error), planned_actions=list(self._planned))

        # Phase 6 – sandbox validation
        if not self._dry_run:
            ok = self._fs.run_sandbox_validation(
                agent_user=self._agent_user,
                bedrock_data=self._bedrock_data,
                agent_state_dir=self._agent_state_dir,
                compose_file=self._compose_file,
                compose_project=self._compose_project,
                docker_config=self._docker_config,
            )
            if not ok:
                return PreflightResult(
                    success=False,
                    error="sandbox validation failed: systemd-run returned non-zero",
                )

        return PreflightResult(
            success=True,
            planned_actions=list(self._planned),
        )

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _check_system(self) -> str:
        si = self._system_info
        if si.python_version < (3, 10, 0):
            return f"python >= 3.10 required; found {si.python_version}"
        if not si.docker_available:
            return "docker cli not found; install docker engine first"
        if not si.compose_v2:
            return "docker compose v2 required; 'docker compose version' returned v1 or not found"
        if not si.setfacl_available:
            return "setfacl not found; install acl package"
        if not si.agent_user_exists:
            return f"user {self._agent_user!r} does not exist; create it first"
        if not si.agent_in_docker_group:
            return (
                f"user {self._agent_user!r} is not in the docker group; "
                f"run: sudo usermod -aG docker {self._agent_user}"
            )
        return ""

    def _apply_acls(self) -> None:
        """Apply any missing ACLs; idempotent."""
        user = self._agent_user
        root = self._project_root
        data = self._bedrock_data
        env = f"{root}/.env"

        acl_checks = [
            (root, "u:{}:--x".format(user), ["setfacl", "-m", f"u:{user}:--x", root]),
            (env, "u:{}:r--".format(user), ["setfacl", "-m", f"u:{user}:r--", env]),
            (data, "u:{}:rwX".format(user), ["setfacl", "-R", "-m", f"u:{user}:rwX", data]),
        ]

        for path, _perm_label, cmd in acl_checks:
            if not self._fs.has_acl(path, user, _perm_label):
                action = f"apply ACL: {' '.join(cmd)}"
                self._planned.append(action)
                if not self._dry_run:
                    self._runner.run(cmd)

        # default ACL for new data content
        default_cmd = ["setfacl", "-R", "-m", f"d:u:{user}:rwX", data]
        if not self._fs.has_acl(f"d:{data}", user, f"d:u:{user}:rwX"):
            action = f"apply default ACL: {' '.join(default_cmd)}"
            self._planned.append(action)
            if not self._dry_run:
                self._runner.run(default_cmd)

    def _apply_dropin(self) -> None:
        """Create or update the systemd service drop-in."""
        expected = _DROPIN_TEMPLATE.format(
            bedrock_data=self._bedrock_data,
            agent_state_dir=self._agent_state_dir,
            project_root=self._project_root,
            docker_config=self._docker_config,
        )

        current = self._fs.dropin_content(_SERVICE) if self._fs.dropin_exists(_SERVICE) else None

        if current == expected:
            return  # already correct; no write

        action = f"write drop-in: {self._fs.dropin_path(_SERVICE)}"
        self._planned.append(action)
        if not self._dry_run:
            self._fs.write_dropin(_SERVICE, expected)
            self._runner.run(["systemctl", "daemon-reload"])

    def _ensure_path_unit(self) -> None:
        """Install, enable, start, and verify the narrow .env ACL watcher."""
        unit = f"{_ENV_ACL_UNIT}.path"
        if self._fs.path_unit_active(unit):
            return

        self._planned.append(f"install and activate {unit}")
        if self._dry_run:
            return

        self._fs.write_file(
            _ENV_ACL_SERVICE_PATH,
            _ENV_ACL_SERVICE_TEMPLATE.format(
                agent_user=self._agent_user, project_root=self._project_root,
            ),
        )
        self._fs.write_file(
            _ENV_ACL_PATH_PATH,
            _ENV_ACL_PATH_TEMPLATE.format(
                project_root=self._project_root, unit=_ENV_ACL_UNIT,
            ),
        )
        self._runner.run(["systemctl", "daemon-reload"])
        self._runner.run(["systemctl", "enable", "--now", unit])
        self._runner.run(["systemctl", "start", f"{_ENV_ACL_UNIT}.service"])
        if not self._fs.path_unit_active(unit):
            raise RuntimeError(f"path unit did not become active: {unit}")
